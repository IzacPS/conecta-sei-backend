from playwright.sync_api import sync_playwright, Page
import datetime
import json
from typing import Dict, List, Optional, Set, Tuple
from utils import (
    load_process_data,
    save_process_data,
    create_process_entry,
)
from logger_system import UILogger
from email_api_ms import notify_new_processes
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


def extract_process_info_fast(page: Page) -> Dict[str, dict]:
    """
    Versão ultra-otimizada - coleta APENAS números e links dos processos
    SEM abrir nenhum processo individual (autoridade será coletada depois)
    """
    logger = UILogger()
    processes = {}
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    try:
        page.wait_for_selector('//*[@id="tblDocumentos"]', state="visible", timeout=30000)
        rows = page.query_selector_all('//*[@id="tblDocumentos"]/tbody/tr[position()>1]')
                
        for row_index, row in enumerate(rows, 1):
            try:
                link_element = row.query_selector('td[align="center"] a')
                if link_element:
                    href = link_element.get_attribute("href")
                    process_number = link_element.inner_text().strip()

                    if not process_number:
                        continue

                    normalized_href = normalize_link(href) if href else None
                    if not normalized_href:
                        continue

                    if process_number not in processes:
                        processes[process_number] = create_process_entry(process_number)

                    processes[process_number]["links"][normalized_href] = {
                        "status": "ativo",
                        "tipo_acesso": None,
                        "ultima_verificacao": current_time,
                        "historico": [],
                    }
                    
                    # NOTA: Autoridade será coletada nas etapas 2 ou 3 quando já abrirmos os processos
                    
            except Exception as e:
                logger.log(f"Erro ao processar linha {row_index}: {str(e)}")
                continue
                
    except Exception as e:
        logger.log(f"Erro ao extrair informações da página: {str(e)}")
        return {}
    
    logger.log(f"✓ {len(processes)} processos coletados!")
    return processes


def try_next_page(page: Page) -> bool:
    """Tenta navegar para a próxima página"""
    logger = UILogger()
    try:
        next_button = page.locator('//*[@id="lnkInfraProximaPaginaSuperior"]')
        if next_button.count() > 0:
            logger.log("Navegando para a próxima página...")
            next_button.click()
            page.wait_for_load_state("networkidle")
            return True
        else:
            logger.log("Última página alcançada")
            return False
    except Exception as e:
        logger.log(f"Erro ao tentar próxima página: {str(e)}")
        return False


def normalize_link(full_url: str) -> str:
    """Normaliza o link removendo a base URL"""
    try:
        if "/sei/" in full_url:
            return full_url.split("/sei/")[1]
        return full_url
    except (IndexError, AttributeError):
        return full_url


def compare_processes(old_processes: Dict[str, dict], new_processes: Dict[str, dict]) -> List[str]:
    """Compara processos antigos e novos para identificar novos processos"""
    if not old_processes:
        return []
    return list(set(new_processes.keys()) - set(old_processes.keys()))


def merge_process_data(existing_processes: Dict[str, dict], all_processes: Dict[str, dict]) -> Dict[str, dict]:
    """Merge dados existentes com novos dados, preservando informações importantes"""
    logger = UILogger()
    
    # Preservar dados dos processos existentes
    for process_number, old_data in existing_processes.items():
        if process_number in all_processes:
            # Campos que devem ser preservados dos dados antigos
            preserve_fields = [
                "categoria",
                "status_categoria", 
                "tipo_acesso_atual",
                "documentos",
                "apelido",
                "novos_documentos",
                "unidade",
                "sem_link_validos",
                "Autoridade"  # ← PRESERVAR AUTORIDADE se já existir
            ]
            
            for field in preserve_fields:
                if field in old_data:
                    all_processes[process_number][field] = old_data[field]
            
            # Merge de links preservando histórico e tipo de acesso
            for href, old_link_data in old_data.get("links", {}).items():
                if href in all_processes[process_number]["links"]:
                    # Preservar histórico e tipo de acesso
                    all_processes[process_number]["links"][href].update({
                        "historico": old_link_data.get("historico", []),
                        "tipo_acesso": old_link_data.get("tipo_acesso"),
                    })
                else:
                    # Adicionar link antigo que não foi encontrado na nova varredura
                    all_processes[process_number]["links"][href] = old_link_data
            
            # Preservar melhor link atual se ainda existir
            if (old_data.get("melhor_link_atual") and 
                old_data["melhor_link_atual"] in all_processes[process_number]["links"]):
                all_processes[process_number]["melhor_link_atual"] = old_data["melhor_link_atual"]
    
    return all_processes


def update_processos() -> Optional[Dict]:
    """Função principal para atualizar a lista de processos"""
    logger = UILogger()
    browser = None
    page = None
    playwright = None
    
    logger.log("=== INICIANDO ATUALIZAÇÃO DE PROCESSOS ===")
    
    start_time = datetime.datetime.now()

    try:
        # Inicializar browser
        logger.log("Inicializando browser...")
        browser, page, playwright = init_browser()
        
        init_time = datetime.datetime.now()
        logger.log(f"Browser inicializado em {(init_time - start_time).total_seconds():.1f}s")
        
        logger.log("Efetuando login...")
        login(page)
        
        login_time = datetime.datetime.now()
        logger.log(f"Login concluído em {(login_time - init_time).total_seconds():.1f}s")
        
        all_processes = {}
        page_count = 0

        # Processar todas as páginas
        process_start_time = datetime.datetime.now()
        
        while True:
            page_count += 1
            
            # Usar a nova função ultra-otimizada (sem abrir processos)
            current_processes = extract_process_info_fast(page)
            
            # Merge dos resultados
            for number, process_data in current_processes.items():
                if number not in all_processes:
                    all_processes[number] = process_data
                else:
                    # Merge de links se processo já existir (pode acontecer em casos raros)
                    for href, link_data in process_data["links"].items():
                        if href not in all_processes[number]["links"]:
                            all_processes[number]["links"][href] = link_data

            # Tentar próxima página
            if not try_next_page(page):
                break

        process_end_time = datetime.datetime.now()
        process_duration = (process_end_time - process_start_time).total_seconds()
        
        # Carregar dados existentes e fazer comparação
        existing_processes = load_process_data()
        
        if existing_processes:
            # Identificar novos processos
            new_processes = compare_processes(existing_processes, all_processes)
            if new_processes:
                logger.log(f"Novos processos encontrados: {', '.join(new_processes)}")
                notify_new_processes([{"process_number": pn, "link": ""} for pn in new_processes])
            else:
                logger.log("Nenhum processo novo encontrado")
            
            # Merge com dados existentes
            all_processes = merge_process_data(existing_processes, all_processes)
        else:
            logger.log("Primeira execução - todos os processos são novos")

        # Salvar dados atualizados
        save_process_data(all_processes)
                
        return all_processes

    except Exception as e:
        logger.log(f"Erro crítico ao atualizar processos: {str(e)}")
        import traceback
        logger.log(f"Stack trace: {traceback.format_exc()}")
        return None

    finally:
        # Cleanup
        if browser:
            try:
                browser.close()
            except Exception as e:
                logger.log(f"Erro ao fechar browser: {str(e)}")
        if playwright:
            try:
                playwright.stop()
            except Exception as e:
                logger.log(f"Erro ao parar playwright: {str(e)}")


if __name__ == "__main__":
    result = update_processos()
    if result:
        print(f"Atualização concluída com sucesso! {len(result)} processos processados.")
    else:
        print("Falha na atualização de processos.")