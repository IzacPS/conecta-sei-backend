from playwright.sync_api import sync_playwright, Page
import json
import os
from typing import Optional, List, Dict
from documento_historico import salvar_historico_documento
import datetime
import re
from utils import (
    load_process_data,
    save_process_data,
    should_process_documents,
    get_app_data_dir,
)
from logger_system import UILogger
from pathlib import Path
from sharepoint_api import upload_to_sharepoint
import shutil


def init_browser():
    playwright = sync_playwright().start()
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_page()
    page.set_default_timeout(30000)
    return browser, page, playwright


def login(page: Page):
    from utils import login_to_sei
    try:
        login_to_sei(page)
    except Exception as e:
        logger = UILogger()
        logger.log(f"Erro de login: {str(e)}")
        raise

def handle_dialog(dialog):
    dialog.dismiss()


def process_filename(suggested_filename: str, doc_number: str, doc_info: dict) -> str:
    filename_without_ext = os.path.splitext(suggested_filename)[0]
    if filename_without_ext.isdigit() and len(filename_without_ext) == 8:
        _, ext = os.path.splitext(suggested_filename)
        new_filename = f"{doc_info['tipo']}_{filename_without_ext}{ext}"
        new_filename = re.sub(r'[<>:"/\\|?*]', "_", new_filename)
        return new_filename
    return suggested_filename


def handle_downloaded_file(
    temp_path: Path, doc_number: str, doc_info: dict, page: Page
) -> Path:
    logger = UILogger()

    if temp_path.suffix.lower() == ".html":
        try:
            pdf_path = temp_path.with_suffix(".pdf")
            page.goto(f"file:///{temp_path}")
            page.wait_for_load_state("load")
            page.pdf(path=str(pdf_path), format="A4")
            temp_path.unlink()
            return pdf_path
        except Exception as e:
            logger.log(f"Erro ao converter documento {doc_number} para PDF: {str(e)}")
            return temp_path

    return temp_path


def get_temp_download_dir() -> Path:
    temp_dir = get_app_data_dir() / "temp_downloads"
    temp_dir.mkdir(parents=True, exist_ok=True)
    return temp_dir


def download_document(
    page: Page,
    doc_number: str,
    doc_info: dict,
    process_number: str,
    process_data: Dict,
) -> bool:
    logger = UILogger()
    temp_file = None
    
    # Criar registro inicial para histórico
    timestamp_inicio = datetime.datetime.now()
    registro_historico = {
        "processo_numero": process_number,
        "documento_numero": doc_number,
        "tipo_documento": doc_info.get("tipo", "Desconhecido"),
        "data_documento": doc_info.get("data", ""),
        "signatario": doc_info.get("signatario", "Não identificado"),
        "timestamp_inicio": timestamp_inicio,
        "tipo_operacao": "completo",
        "resultado": "pendente",
        "apelido_processo": process_data.get("apelido", "")
    }
    
    try:
        page.on("dialog", handle_dialog)
        doc_link = page.locator(f'a:text("{doc_number}")')
        doc_link.wait_for(state="visible", timeout=30000)

        temp_dir = get_temp_download_dir()

        # Iniciar download
        registro_historico["timestamp_download_inicio"] = datetime.datetime.now()
        with page.expect_download(timeout=30000) as download_info:
            page.keyboard.down("Alt")
            doc_link.click()
            page.keyboard.up("Alt")

        download = download_info.value
        suggested_filename = download.suggested_filename
        
        if suggested_filename:
            final_filename = process_filename(suggested_filename, doc_number, doc_info)
            temp_path = temp_dir / final_filename
            
            # Salvar arquivo localmente
            download.save_as(temp_path)
            registro_historico["tamanho_arquivo_bytes"] = temp_path.stat().st_size if temp_path.exists() else 0
            registro_historico["timestamp_download_fim"] = datetime.datetime.now()
            registro_historico["duracao_download_ms"] = (registro_historico["timestamp_download_fim"] - registro_historico["timestamp_download_inicio"]).total_seconds() * 1000
            
            # Processar arquivo se necessário (como converter HTML para PDF)
            final_path = handle_downloaded_file(temp_path, doc_number, doc_info, page)
            temp_file = final_path
            registro_historico["nome_arquivo"] = final_path.name

            # Iniciar upload para SharePoint
            registro_historico["timestamp_upload_inicio"] = datetime.datetime.now()
            upload_success = upload_to_sharepoint(final_path, process_number, process_data)
            registro_historico["timestamp_upload_fim"] = datetime.datetime.now()
            registro_historico["duracao_upload_ms"] = (registro_historico["timestamp_upload_fim"] - registro_historico["timestamp_upload_inicio"]).total_seconds() * 1000
            
            if upload_success:
                registro_historico["resultado"] = "sucesso"
                logger.log(f"Documento {doc_number} enviado com sucesso para o SharePoint")
                return True
            else:
                registro_historico["resultado"] = "falha"
                registro_historico["erro"] = "Falha no upload para SharePoint"
                logger.log(f"Falha no upload para SharePoint do documento {doc_number}")
                return False

        else:
            registro_historico["resultado"] = "falha"
            registro_historico["erro"] = "Nome de arquivo sugerido não disponível"
            return False

    except Exception as e:
        registro_historico["resultado"] = "falha"
        registro_historico["erro"] = str(e)
        logger.log(f"Erro ao baixar documento {doc_number}: {str(e)}")
        return False
    finally:
        page.remove_listener("dialog", handle_dialog)
        
        # Calcular tempos finais e salvar histórico
        registro_historico["timestamp_fim"] = datetime.datetime.now()
        registro_historico["duracao_total_ms"] = (registro_historico["timestamp_fim"] - registro_historico["timestamp_inicio"]).total_seconds() * 1000
        
        # Salvar histórico no MongoDB
        salvar_historico_documento(registro_historico)
        
        # Limpar arquivos temporários
        if temp_file and temp_file.exists():
            try:
                temp_file.unlink()
            except Exception as e:
                logger.log(f"Erro ao remover arquivo temporário {temp_file}: {str(e)}")


def download_new_documents():
    logger = UILogger()
    processes = load_process_data()
    if not processes:
        return

    try:
        browser, page, playwright = init_browser()
        login(page)

        for process_number, process_data in processes.items():
            if not process_data.get("novos_documentos"):
                continue

            if process_data.get("sem_link_validos", False):
                logger.log(f"Processo {process_number}: Pulando Download - Sem Links Válidos")
                del process_data["novos_documentos"]
                continue

            if not should_process_documents(process_data):
                logger.log(f"Processo {process_number}: Pulando Download - Acesso Restrito ou confidencial")
                continue

            process_display = process_number
            if process_data.get("apelido"):
                process_display = f"{process_data['apelido']} ({process_number})"

            logger.log(f"Iniciando download de documentos do processo {process_display}")

            best_link = process_data.get("melhor_link_atual")
            if not best_link:
                logger.log(f"Processo {process_display}: Sem link válido disponível")
                continue

            base_url = "https://colaboragov.sei.gov.br/sei/"
            process_url = f"{base_url}{best_link}"
            page.goto(process_url)
            page.wait_for_selector("#tblDocumentos", timeout=30000)

            successful_downloads = []
            new_docs = process_data["novos_documentos"]

            for doc_number in new_docs:
                logger.log(f"Baixando documento {doc_number}")
                
                current_url = page.url
                if current_url != process_url:
                    try:
                        page.go_back()
                        page.wait_for_selector("#tblDocumentos", timeout=15000)
                    except Exception as e:
                        logger.log(f"Erro ao voltar para a página anterior: {str(e)}, tentando redirecionamento")
                        page.goto(process_url)
                        page.wait_for_selector("#tblDocumentos", timeout=30000)
                
                doc_info = process_data["documentos"].get(doc_number, {})
                
                process_data["documento_atual"] = doc_number

                # O download_document agora retorna True apenas se o upload para o SharePoint for bem-sucedido
                if download_document(page, doc_number, doc_info, process_number, process_data):
                    if doc_number in process_data["documentos"]:
                        process_data["documentos"][doc_number]["status"] = "baixado"
                    successful_downloads.append(doc_number)

            process_data["novos_documentos"] = [
                doc for doc in new_docs if doc not in successful_downloads
            ]

            if not process_data["novos_documentos"]:
                del process_data["novos_documentos"]
                
            if "documento_atual" in process_data:
                del process_data["documento_atual"]

            save_process_data(processes)

    except Exception as e:
        logger.log(f"Erro crítico durante download: {str(e)}")

    finally:
        if browser:
            browser.close()
        if playwright:
            playwright.stop()

        temp_dir = get_temp_download_dir()
        if temp_dir.exists():
            try:
                shutil.rmtree(temp_dir)
            except Exception as e:
                logger.log(f"Erro ao limpar diretório temporário: {str(e)}")

if __name__ == "__main__":
    download_new_documents()