from playwright.sync_api import sync_playwright, Page
import datetime
import time
from connect_mongo import get_database
from utils import notify_process_update
from email_api_ms import notify_categorization_needed
import json
from utils import get_app_data_dir
from logger_system import UILogger

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

def verify_access_type(page: Page) -> str:
    locator = page.locator("#divInfraBarraLocalizacao")
    if locator.count() > 0:
        text = locator.inner_text()
        if "Acesso Externo com Acompanhamento Integral" in text:
            return "integral"
        elif "Acesso Externo com Disponibilização Parcial" in text:
            return "parcial"
    return "error"


def collect_authority_if_missing(page: Page, process_number: str, process_data: dict) -> None:
    """
    Coleta a autoridade do processo APENAS se ainda não tiver sido coletada.
    APROVEITA que já estamos com o processo aberto.
    """
    logger = UILogger()
    
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


def update_process_link_status(
    process_data: dict,
    link: str,
    access_type: str,
    process_number: str,
    processos_para_email: list,
):
    if not process_data:
        process_data = {}

    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    old_access_type = process_data.get("tipo_acesso_atual", "parcial")

    if access_type == "error":
        return process_data

    process_data["sem_link_validos"] = False

    if link not in process_data.get("links", {}):
        process_data["links"] = process_data.get("links", {})
        process_data["links"][link] = {
            "status": "Ativo",
            "tipo_acesso": access_type,
            "ultima_verificacao": current_time,
            "historico": [],
        }

    link_data = process_data["links"][link]

    if link_data["tipo_acesso"] != access_type or link_data["status"] == "Inativo":
        link_data["historico"].append(
            {"data": current_time, "status": "Ativo", "tipo_acesso": access_type}
        )

    link_data["status"] = "Ativo"
    link_data["tipo_acesso"] = access_type
    link_data["ultima_verificacao"] = current_time

    if access_type == "integral":
        process_data["tipo_acesso_atual"] = "integral"
        process_data["categoria"] = "restrito"
        process_data["status_categoria"] = "categorizado"
        process_data["melhor_link_atual"] = link
        if old_access_type == "parcial":
            notify_process_update(
                "Processo obteve acesso integral (anterior: parcial) - categorizado como restrito",
                process_number,
            )
    elif (
        access_type == "parcial" and process_data.get("tipo_acesso_atual") != "integral"
    ):
        process_data["tipo_acesso_atual"] = "parcial"
        process_data["melhor_link_atual"] = link
        if process_data.get("status_categoria") != "categorizado":
            process_data["status_categoria"] = "pendente"
            notify_process_update(
                "Processo com acesso parcial necessita de categorização", process_number
            )
            processos_para_email.append(process_number)

    return process_data


def reconstruct_link(partial_link: str) -> str:
    base_url = "https://colaboragov.sei.gov.br/sei/"
    return base_url + partial_link


def check_process_links(
    page: Page, process_number: str, links: list, processos_para_email: list
) -> dict:
    logger = UILogger()
    process_data = {"links": {}, "melhor_link_atual": None}
    db = get_database()
    collection = db.processos

    try:
        processo = collection.find_one({"numero_processo": process_number})
        if processo and "melhor_link_atual" in processo:
            melhor_link = processo["melhor_link_atual"]
            if melhor_link in links:
                page.goto(reconstruct_link(melhor_link))
                access_type = verify_access_type(page)
                process_data = update_process_link_status(
                    process_data,
                    melhor_link,
                    access_type,
                    process_number,
                    processos_para_email,
                )
                
                if access_type != "error":
                    collect_authority_if_missing(page, process_number, process_data)
                
                if access_type == "integral":
                    return process_data
    except Exception:
        pass

    link_parcial_backup = None
    for link in links:
        if link in process_data["links"]:
            continue

        try:
            page.goto(reconstruct_link(link))
            time.sleep(1)
            access_type = verify_access_type(page)

            process_data = update_process_link_status(
                process_data, link, access_type, process_number, processos_para_email
            )
            
            if access_type != "error":
                collect_authority_if_missing(page, process_number, process_data)

            if access_type == "integral":
                return process_data
            elif access_type == "parcial" and not link_parcial_backup:
                link_parcial_backup = link

        except Exception as e:
            logger.log(f"Erro ao verificar link {link}: {str(e)}")
            continue

    if link_parcial_backup:
        process_data["melhor_link_atual"] = link_parcial_backup

    return process_data


def enviar_categorizacoes_pendentes():
    db = get_database()
    collection = db.processos

    try:
        processos_pendentes = []
        cursor = collection.find({"status_categoria": "pendente"})

        for processo in cursor:
            melhor_link = processo.get("melhor_link_atual")
            if melhor_link:
                processos_pendentes.append(
                    {"process_number": processo["numero_processo"], "link": melhor_link}
                )

        if processos_pendentes:
            notify_categorization_needed(processos_pendentes)
            print(
                f"E-mail enviado com {len(processos_pendentes)} processos pendentes para categorização."
            )
        else:
            print("Nenhum processo pendente encontrado para categorização.")

    except Exception as e:
        print(f"Erro ao enviar processos pendentes para categorização: {str(e)}")


def update_documentos_processos():
    logger = UILogger()
    logger.log("=== INICIANDO ETAPA 2: VERIFICAÇÃO DE LINKS E COLETA DE AUTORIDADES ===")
    
    db = get_database()
    collection = db.processos

    browser, page, playwright = init_browser()
    autoridades_coletadas = 0
    
    try:
        login(page)
        processos = collection.find({})
        total_processos = collection.count_documents({})
        
        logger.log(f"Verificando {total_processos} processos...")

        for i, processo in enumerate(processos, 1):
            process_number = processo["numero_processo"]
            logger.log(f"Verificando processo {process_number} ({i}/{total_processos})")
            
            links = list(processo.get("links", {}).keys())
            if not links:
                continue

            updated_data = {k: v for k, v in processo.items() if k != '_id'}
            link_valido_encontrado = False
            had_authority_before = bool(updated_data.get("Autoridade"))

            for link in links:
                try:
                    page.goto(reconstruct_link(link))
                    page.wait_for_timeout(1000)
                    access_type = verify_access_type(page)

                    if access_type != "error":
                        link_valido_encontrado = True
                        
                        collect_authority_if_missing(page, process_number, updated_data)

                    process_data = update_process_link_status(
                        updated_data, link, access_type, process_number, []
                    )
                    if process_data:
                        updated_data = process_data

                except Exception as e:
                    logger.log(f"Erro ao verificar link {link}: {str(e)}")
                    continue

            if not link_valido_encontrado:
                updated_data["sem_link_validos"] = True

            if "tipo_acesso_atual" not in updated_data:
                updated_data["tipo_acesso_atual"] = "parcial"

            # Contabilizar autoridades coletadas
            if not had_authority_before and updated_data.get("Autoridade"):
                autoridades_coletadas += 1

            collection.update_one(
                {"numero_processo": process_number}, 
                {"$set": updated_data}
            )
        
        enviar_categorizacoes_pendentes()

    except Exception as e:
        logger.log(f"Erro ao verificar links: {str(e)}")
    finally:
        browser.close()
        playwright.stop()


if __name__ == "__main__":
    update_documentos_processos()