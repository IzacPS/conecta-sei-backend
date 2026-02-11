from playwright.sync_api import sync_playwright, Page
from bs4 import BeautifulSoup
import datetime
import re
import json
from typing import Dict, Optional, List, Set, Tuple
from utils import (
    load_process_data,
    save_process_data,
    should_process_documents,
)
from logger_system import UILogger
from email_api_ms import notify_new_documents, send_email, create_email_template
from utils import get_app_data_dir

def init_browser():
    playwright = sync_playwright().start()
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_page()
    return browser, page, playwright

def login(page: Page):
    from utils import login_to_sei
    try:
        login_to_sei(page)
    except Exception as e:
        logger = UILogger()
        logger.log(f"Erro de login: {str(e)}")
        raise


def collect_authority_if_missing(page: Page, process_number: str, process_data: dict) -> None:
    """
    Coleta a autoridade do processo APENAS se ainda não tiver sido coletada.
    APROVEITA que já estamos com o processo aberto.
    """
    logger = UILogger()
    
    # ✅ SÓ PROCESSAR SE NÃO TIVER AUTORIDADE
    if process_data.get("Autoridade"):
        return  # Já tem autoridade, não gastar processamento
    
    try:
        authority_element = page.query_selector('//*[@id="tblDocumentos"]/tbody/tr[2]/td[5]/a')
        if authority_element:
            full_authority = authority_element.inner_text().strip()
            if full_authority:
                parts = full_authority.split("-")
                if len(parts) >= 3:
                    process_data["Autoridade"] = parts[2].strip()
                elif len(parts) >= 2:
                    process_data["Autoridade"] = parts[1].strip()
                else:
                    process_data["Autoridade"] = full_authority.strip()
                
                logger.log(f"✓ Autoridade coletada para {process_number}: {process_data['Autoridade']}")
            else:
                process_data["Autoridade"] = "N/A"
        else:
            process_data["Autoridade"] = "N/A"
            
    except Exception as e:
        logger.log(f"Erro ao coletar autoridade de {process_number}: {str(e)}")
        process_data["Autoridade"] = "N/A"
    
def process_receipt_content(content: str) -> Tuple[Set[str], Optional[str]]:
    soup = BeautifulSoup(content, "html.parser")
    doc_numbers = set()
    signatario = None

    for td in soup.find_all("td"):
        text = td.get_text(strip=True)
        if re.match(r'^\d{8}$', text):
            doc_numbers.add(text)

    signatario_row = soup.find("td", text=re.compile(r'Usuário Externo \(signatário\):'))
    if signatario_row:
        signatario_cell = signatario_row.find_next_sibling("td")
        if signatario_cell:
            signatario = signatario_cell.get_text(strip=True)

    return doc_numbers, signatario


def process_receipt(page: Page, receipt_number: str, receipt_href: str) -> Dict:
    try:
        with page.context.expect_page() as new_page_info:
            page.evaluate(f"window.open('{receipt_href}', '_blank')")
        receipt_page = new_page_info.value
        receipt_page.wait_for_load_state("networkidle")

        content = receipt_page.content()
        doc_numbers, signatario = process_receipt_content(content)
        
        receipt_page.close()
        
        return {
            "numero": receipt_number,
            "data_processamento": datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            "documentos": list(doc_numbers),
            "signatario": signatario
        }
    except Exception as e:
        logger = UILogger()
        logger.log(f"Erro ao processar recibo {receipt_number}: {str(e)}")
        return {
            "numero": receipt_number,
            "data_processamento": datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            "documentos": [],
            "signatario": None,
            "erro": str(e)
        }

def process_documents_page(page: Page, process_data: Dict) -> Dict[str, dict]:
    logger = UILogger()
    
    try:
        # Verificar se a página carregou corretamente
        page.wait_for_selector("#tblDocumentos", timeout=60000)
        logger.log("Tabela de documentos localizada com sucesso")
        
    except Exception as e:
        logger.log(f"ERRO: Tabela de documentos não encontrada - {str(e)}")
        return None
    
    try:
        html_content = page.content()
        soup = BeautifulSoup(html_content, "html.parser")
        
        # Processar documentos existentes
        documents = {}
        rows = soup.select("#tblDocumentos tr.infraTrClara")
        
        logger.log(f"Encontradas {len(rows)} linhas de documentos para processar")
        
        if len(rows) == 0:
            logger.log("AVISO: Nenhuma linha de documento encontrada na tabela")
            return {}
        
        for row_index, row in enumerate(rows):
            try:
                doc_link = row.select_one("td:nth-child(2) a")
                
                if not doc_link:
                    logger.log(f"Linha {row_index + 1}: Sem link de documento")
                    continue
                
                onclick_attr = doc_link.get("onclick", "")
                if onclick_attr and "alert(" in onclick_attr:
                    logger.log(f"Linha {row_index + 1}: Documento com restrição de acesso")
                    continue
                
                doc_number = doc_link.get_text(strip=True)
                if not re.match(r'^\d{8}$', doc_number):
                    logger.log(f"Linha {row_index + 1}: Número de documento inválido: {doc_number}")
                    continue

                # Extrair dados do documento
                tipo_cell = row.select_one("td:nth-child(3)")
                data_cell = row.select_one("td:nth-child(4)")
                
                if not tipo_cell or not data_cell:
                    logger.log(f"Documento {doc_number}: Células de tipo ou data não encontradas")
                    continue

                documents[doc_number] = {
                    "tipo": tipo_cell.get_text(strip=True),
                    "data": data_cell.get_text(strip=True),
                    "status": "nao_baixado",
                    "ultima_verificacao": datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                    "signatario": "Autoridade Competente"
                }
                
                logger.log(f"Documento {doc_number} processado com sucesso")
                
            except Exception as e:
                logger.log(f"ERRO ao processar linha {row_index + 1}: {str(e)}")
                continue
        
        # Processar recibos
        logger.log("Iniciando processamento de recibos eletrônicos...")
        recibos_processados = process_data.get("recibos_processados", {})
        receipt_rows = soup.find_all("tr", class_="infraTrClara")
        
        receipts_found = 0
        for row in receipt_rows:
            cells = row.find_all("td")
            if len(cells) >= 3 and "Recibo Eletrônico de Protocolo" in cells[2].get_text():
                receipts_found += 1
                receipt_number = cells[1].get_text(strip=True)
                
                if receipt_number in recibos_processados:
                    logger.log(f"Recibo {receipt_number}: Já processado anteriormente")
                    continue
                
                try:
                    receipt_link = cells[1].find("a")
                    if not receipt_link:
                        logger.log(f"Recibo {receipt_number}: Link não encontrado")
                        continue
                        
                    receipt_href = receipt_link.get("href")
                    if not receipt_href:
                        logger.log(f"Recibo {receipt_number}: Href não encontrado")
                        continue

                    logger.log(f"Processando recibo {receipt_number}...")
                    receipt_info = process_receipt(page, receipt_number, receipt_href)
                    recibos_processados[receipt_number] = receipt_info
                    
                    # Atualizar signatários dos documentos
                    if receipt_info.get("signatario"):
                        for doc_number in receipt_info.get("documentos", []):
                            if doc_number in documents:
                                documents[doc_number]["signatario"] = receipt_info["signatario"]
                                logger.log(f"Documento {doc_number}: Signatário atualizado para {receipt_info['signatario']}")
                
                except Exception as e:
                    logger.log(f"ERRO ao processar recibo {receipt_number}: {str(e)}")
                    continue
        
        logger.log(f"Processamento concluído: {receipts_found} recibos encontrados, {len(documents)} documentos finais")
        process_data["recibos_processados"] = recibos_processados
        return documents
        
    except Exception as e:
        logger.log(f"ERRO CRÍTICO no processamento da página: {str(e)}")
        return None

def extract_unit_info(page: Page) -> str:
    try:
        unit_element = page.query_selector("#selInfraUnidades")
        if unit_element:
            return unit_element.evaluate("node => node.options[node.selectedIndex].text")
        return "Unidade não identificada"
    except Exception:
        return "Unidade não identificada"


def process_single_document(page: Page, process_number: str, process_data: Dict) -> tuple[Dict, str]:
   logger = UILogger()
   base_url = "https://colaboragov.sei.gov.br/sei/"
   
   available_links = list(process_data.get("links", {}).keys())
   
   if not available_links:
       logger.log(f"Processo {process_number}: Nenhum link disponível")
       return {}, "Unidade não identificada"
   
   current_best_link = process_data.get("melhor_link_atual")
   
   # Lista de links para testar: melhor link primeiro, depois os outros
   links_to_test = []
   
   if current_best_link and current_best_link in available_links:
       links_to_test.append(current_best_link)
       other_links = [link for link in available_links if link != current_best_link]
       links_to_test.extend(other_links)
       logger.log(f"Processo {process_number}: Testando melhor link primeiro, depois {len(other_links)} outros")
   else:
       links_to_test = available_links
       logger.log(f"Processo {process_number}: Sem melhor link definido, testando todos os {len(available_links)} links")
   
   # Testar links sequencialmente
   for link_index, link in enumerate(links_to_test):
       try:
           full_url = f"{base_url}{link}"
           
           # Indicar se é o melhor link atual ou não
           is_current_best = (link == current_best_link)
           link_type = "MELHOR LINK" if is_current_best else f"Link {link_index + 1}"
           
           logger.log(f"Processo {process_number}: Testando {link_type}")
           
           page.goto(full_url)
           page.wait_for_selector("#tblDocumentos", timeout=60000)
           
           # 🎯 APROVEITAR que já estamos no processo para coletar autoridade
           collect_authority_if_missing(page, process_number, process_data)
           
           documents = process_documents_page(page, process_data)
           unit = extract_unit_info(page)
           
           if documents is None:
               logger.log(f"Processo {process_number}: {link_type} - ERRO no processamento da página")
               continue
               
           if documents:
               # Link funcionou!
               if not is_current_best:
                   # Encontrou um link melhor que o atual
                   logger.log(f"Processo {process_number}: NOVO melhor link encontrado! {len(documents)} documentos")
                   process_data["melhor_link_atual"] = link
               else:
                   # Melhor link continua funcionando
                   logger.log(f"Processo {process_number}: Melhor link confirmado funcionando - {len(documents)} documentos")
               
               return documents, unit
           else:
               logger.log(f"Processo {process_number}: {link_type} acessível mas SEM documentos")
               continue
               
       except Exception as e:
           link_type = "MELHOR LINK" if (link == current_best_link) else f"Link {link_index + 1}"
           logger.log(f"Processo {process_number}: ERRO no {link_type}: {str(e)}")
           continue
   
   # Se chegou aqui, nenhum link funcionou
   logger.log(f"Processo {process_number}: FALHA TOTAL - {len(links_to_test)} links testados, nenhum retornou documentos")
   
   # Limpar o melhor_link_atual se ele não funcionou
   if current_best_link:
       logger.log(f"Processo {process_number}: Removendo melhor_link_atual inválido")
       process_data["melhor_link_atual"] = None
   
   return {}, "Unidade não identificada"


def update_document_statuses(existing_docs: Dict, new_docs: Dict, process_number: str) -> List[str]:
    new_doc_numbers = []
    logger = UILogger()

    for doc_number, new_doc in new_docs.items():
        is_new = doc_number not in existing_docs
        is_eight_digits = len(re.sub(r"\D", "", doc_number)) == 8

        if is_new and is_eight_digits:
            new_doc["status"] = "nao_baixado"
            new_doc["primeira_visualizacao"] = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            new_doc_numbers.append(doc_number)
            logger.log(f"Processo {process_number}: Novo documento encontrado: {doc_number}")
        elif doc_number in existing_docs:
            existing_doc = existing_docs[doc_number]
            new_doc["status"] = existing_doc.get("status", "nao_baixado")
            
            # Preservar a primeira_visualizacao no formato original ou converter se estiver em formato diferente
            if "primeira_visualizacao" in existing_doc:
                primeira_vis = existing_doc["primeira_visualizacao"]
                # Verificar se está no formato americano (YYYY-MM-DD)
                if re.match(r"\d{4}-\d{2}-\d{2}", primeira_vis):
                    try:
                        dt = datetime.datetime.strptime(primeira_vis, "%Y-%m-%d %H:%M:%S")
                        new_doc["primeira_visualizacao"] = dt.strftime("%d/%m/%Y %H:%M:%S")
                    except:
                        new_doc["primeira_visualizacao"] = primeira_vis
                else:
                    new_doc["primeira_visualizacao"] = primeira_vis
            
            if existing_doc.get("signatario") and not new_doc.get("signatario"):
                new_doc["signatario"] = existing_doc["signatario"]

    return new_doc_numbers

def update_process_documents():
   processes = load_process_data()
   if not processes:
       return

   all_new_docs = {}
   browser = page = playwright = None
   logger = UILogger()
   
   logger.log("=== INICIANDO ETAPA 3: VERIFICAÇÃO DE DOCUMENTOS E COLETA DE AUTORIDADES ===")
   autoridades_coletadas = 0

   try:
       browser, page, playwright = init_browser()
       page.set_default_timeout(60000)
       login(page)

       valid_processes = {
           k: v for k, v in processes.items()
           if v and v.get("melhor_link_atual") 
           and not v.get("sem_link_validos", False)
           and should_process_documents(v)
       }

       process_count = len(valid_processes)
       logger.log(f"Total de processos válidos para verificar: {process_count}")

       for idx, (process_number, process_data) in enumerate(valid_processes.items(), 1):
           logger.log(f"Processando {process_number} ({idx}/{process_count})")
           
           # Verificar se já tem autoridade antes
           had_authority_before = bool(process_data.get("Autoridade"))
           
           try:
               found_documents, unit = process_single_document(page, process_number, process_data)
               
               # Contabilizar autoridades coletadas
               if not had_authority_before and process_data.get("Autoridade"):
                   autoridades_coletadas += 1
               
               if found_documents is None:
                   logger.log(f"Processo {process_number}: ERRO ao processar - logs acima")
                   continue
                   
               if not found_documents:
                   logger.log(f"Processo {process_number}: Página acessível mas SEM DOCUMENTOS encontrados")
                   continue
               
               logger.log(f"Processo {process_number}: {len(found_documents)} documentos encontrados")

               existing_docs = process_data.get("documentos", {})
               new_doc_numbers = update_document_statuses(existing_docs, found_documents, process_number)

               process_data["documentos"] = found_documents
               process_data["unidade"] = unit

               if new_doc_numbers:
                   process_data["novos_documentos"] = new_doc_numbers
                   all_new_docs[process_number] = new_doc_numbers
                   logger.log(f"Processo {process_number}: {len(new_doc_numbers)} novos documentos encontrados")
               elif "novos_documentos" in process_data:
                   del process_data["novos_documentos"]

               processes[process_number] = process_data
               save_process_data(processes)
               
           except Exception as e:
               logger.log(f"Processo {process_number}: EXCEÇÃO não tratada - {str(e)}")
               import traceback
               logger.log(f"Stack trace: {traceback.format_exc()}")
               continue

   except Exception as e:
       logger.log(f"Erro crítico na atualização: {str(e)}")
       import traceback
       logger.log(f"Stack trace crítico: {traceback.format_exc()}")

   finally:
       if browser:
           browser.close()
       if playwright:
           playwright.stop()
   
   if all_new_docs:
       logger.log("Novos documentos encontrados:")
       process_data_grouped = {}
       
       for processo, docs in all_new_docs.items():
           processo_info = processes[processo]
           documentos_por_signatario = {}
           
           for doc_number in docs:
               documento = processo_info["documentos"][doc_number]
               signatario = documento.get("signatario", "Não identificado")
               tipo_doc = documento["tipo"]
               
               if signatario not in documentos_por_signatario:
                   documentos_por_signatario[signatario] = set()
                   
               documentos_por_signatario[signatario].add(tipo_doc)
               
               logger.log(
                   f"Processo: {processo} | Documento: {tipo_doc} | "
                   f"Signatário: {signatario}"
               )
           
           process_data_grouped[processo] = {
               "apelido": processo_info.get("apelido", ""),
               "documentos_por_signatario": {
                   sig: sorted(list(docs)) 
                   for sig, docs in documentos_por_signatario.items()
               }
           }
       
       notify_new_documents(process_data_grouped)
   else:
       subject = "Verificação de Documentos Concluída"
       content = f"<p>Nenhum documento novo encontrado.</p><p>Data: {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}</p>"
       send_email(subject, create_email_template(content))

if __name__ == "__main__":
    update_process_documents()
