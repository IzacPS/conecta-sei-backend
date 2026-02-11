import datetime
from typing import Dict, Optional, Union
from pathlib import Path
import os
import shutil
from logger_system import UILogger
from connect_mongo import get_database
import json


def get_app_data_dir() -> Path:
    base_dir = Path(os.getenv("LOCALAPPDATA")) / "SEI_UNO_TRADE"
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir


def get_backup_dir() -> Path:
    backup_dir = get_app_data_dir() / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    return backup_dir

def cleanup_old_backups(phase_name: str, keep_count: int = 5) -> None:
    backup_dir = get_backup_dir()
    phase_backups = sorted(
        [f for f in backup_dir.glob(f"processos_atuais_{phase_name}_*.json")],
        reverse=True,
    )

    for old_backup in phase_backups[keep_count:]:
        try:
            old_backup.unlink()
        except Exception as e:
            logger = UILogger()
            logger.log(f"Erro ao remover backup antigo {old_backup}: {str(e)}")


def load_process_data() -> Dict:
    try:
        db = get_database()
        collection = db.processos

        processos = {}
        for processo in collection.find({}, {"_id": 0}):
            numero = processo.pop("numero_processo")
            processos[numero] = processo

        return processos

    except Exception as e:
        logger = UILogger()
        logger.log(f"Erro ao carregar dados do MongoDB: {str(e)}")
        return {}


def save_process_data(processes: Dict) -> None:
    try:
        db = get_database()
        collection = db.processos

        collection.delete_many({})

        documents = []
        for processo_num, processo_data in processes.items():
            documento = {
                "numero_processo": processo_num,
                **processo_data,
                "ultima_atualizacao": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
            documents.append(documento)

        if documents:
            collection.insert_many(documents)

    except Exception as e:
        logger = UILogger()
        logger.log(f"Erro ao salvar dados no MongoDB: {str(e)}")


def notify_process_update(message: str, process_id: str) -> None:
    logger = UILogger()
    logger.log(f"[PROCESSO {process_id}] {message}")


def check_access_type(process_data: Dict) -> str:
    links = process_data.get("links", {})
    return (
        "integral"
        if any(link.get("tipo_acesso") == "integral" for link in links.values())
        else "parcial"
    )


def should_process_documents(process_data: Dict) -> bool:
    if not process_data:
        return False

    if process_data.get("sem_link_validos", False):
        return False

    access_type = process_data.get("tipo_acesso_atual", "")

    if access_type == "integral":
        return True

    if access_type == "parcial":
        status = process_data.get("status_categoria", "")

        category = process_data.get("categoria", "")

        if status == "pendente":
            return False

        return category in ["restrito"]

    return False


def create_process_entry(process_number: str) -> Dict:
    return {
        "links": {},
        "melhor_link_atual": None,
        "categoria": None,
        "status_categoria": "pendente",
        "tipo_acesso_atual": None,
        "documentos": {},
        "unidade": None,
        "sem_link_validos": True,
        "ultima_verificacao": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "ultima_atualizacao": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def validate_process_status(process_data: Dict) -> bool:
    required_fields = [
        "links",
        "categoria",
        "status_categoria",
        "tipo_acesso_atual",
        "documentos",
        "unidade",
    ]

    return all(field in process_data for field in required_fields)

def get_credentials_file_path() -> Path:
    return get_app_data_dir() / "credenciais.json"

def load_credentials_from_mongodb() -> dict:
    """Carrega credenciais do MongoDB (fonte autoritativa)"""
    try:
        db = get_database()
        config_collection = db.configuracoes
        
        # Buscar URL do sistema
        url_config = config_collection.find_one({"tipo": "url_sistema"})
        site_url = url_config.get("valor", "") if url_config else ""
        
        # Buscar credenciais de acesso
        credentials_config = config_collection.find_one({"tipo": "credenciais_acesso"})
        if credentials_config:
            return {
                "site_url": site_url,
                "email": credentials_config.get("email", ""),
                "senha": credentials_config.get("senha", ""),
                "last_update": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "source": "mongodb"
            }
    except Exception as e:
        logger = UILogger()
        logger.log(f"Erro ao carregar credenciais do MongoDB: {str(e)}")
    
    return {}

def load_credentials_from_file() -> dict:
    """Carrega credenciais do arquivo JSON local (fallback)"""
    try:
        credentials_path = get_credentials_file_path()
        if credentials_path.exists():
            with open(credentials_path, "r", encoding="utf-8") as f:
                credentials = json.load(f)
                # Verificar se os campos obrigatórios existem
                required_fields = ["site_url", "email", "senha"]
                if all(field in credentials for field in required_fields):
                    credentials["source"] = "local_file"
                    return credentials
    except Exception as e:
        logger = UILogger()
        logger.log(f"Erro ao carregar credenciais do arquivo: {str(e)}")
    
    return {}

def sync_credentials_to_file(credentials: dict) -> bool:
    """Sincroniza credenciais do MongoDB para arquivo local"""
    try:
        credentials_path = get_credentials_file_path()
        credentials_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Remover campo source antes de salvar
        clean_credentials = {k: v for k, v in credentials.items() if k != "source"}
        clean_credentials["last_update"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        with open(credentials_path, "w", encoding="utf-8") as f:
            json.dump(clean_credentials, f, ensure_ascii=False, indent=2)
        
        logger = UILogger()
        logger.log("Credenciais sincronizadas do MongoDB para arquivo local")
        return True
    except Exception as e:
        logger = UILogger()
        logger.log(f"Erro ao sincronizar credenciais para arquivo: {str(e)}")
        return False

def load_credentials() -> dict:
    """
    Carrega credenciais com MongoDB como fonte autoritativa
    Ordem de prioridade:
    1. MongoDB (autoritativo)
    2. Arquivo local (fallback)
    3. Credenciais vazias (última opção)
    """
    logger = UILogger()
    
    # 1. Tentar carregar do MongoDB (fonte autoritativa)
    mongodb_credentials = load_credentials_from_mongodb()
    if mongodb_credentials and all(mongodb_credentials.get(field, "").strip() 
                                  for field in ["site_url", "email", "senha"]):
        logger.log("Credenciais carregadas do MongoDB (fonte autoritativa)")
        # Sincronizar para arquivo local para cache
        sync_credentials_to_file(mongodb_credentials)
        return mongodb_credentials
    
    # 2. Fallback: tentar carregar do arquivo local
    file_credentials = load_credentials_from_file()
    if file_credentials and all(file_credentials.get(field, "").strip() 
                               for field in ["site_url", "email", "senha"]):
        logger.log("Credenciais carregadas do arquivo local (fallback)")
        return file_credentials
    
    # 3. Última opção: credenciais vazias
    logger.log("Nenhuma credencial válida encontrada - retornando credenciais vazias")
    return create_empty_credentials()

def create_empty_credentials() -> dict:
    return {
        "site_url": "",
        "email": "",
        "senha": "",
        "last_update": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source": "empty"
    }

def save_credentials(credentials: dict) -> bool:
    """
    Salva credenciais no MongoDB (autoritativo) e sincroniza para arquivo local
    """
    try:
        db = get_database()
        config_collection = db.configuracoes
        
        # Salvar URL do sistema
        config_collection.update_one(
            {"tipo": "url_sistema"},
            {"$set": {
                "valor": credentials.get("site_url", ""),
                "ultima_atualizacao": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }},
            upsert=True
        )
        
        # Salvar credenciais de acesso
        config_collection.update_one(
            {"tipo": "credenciais_acesso"},
            {"$set": {
                "email": credentials.get("email", ""),
                "senha": credentials.get("senha", ""),
                "ultima_atualizacao": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }},
            upsert=True
        )
        
        # Sincronizar para arquivo local
        sync_credentials_to_file(credentials)
        
        logger = UILogger()
        logger.log("Credenciais salvas no MongoDB e sincronizadas para arquivo local")
        return True
        
    except Exception as e:
        logger = UILogger()
        logger.log(f"Erro ao salvar credenciais: {str(e)}")
        return False

def get_sei_url() -> str:
    credentials = load_credentials()
    return credentials.get("site_url", "")

def credentials_are_complete() -> bool:
    """Verifica se as credenciais estão completas e válidas"""
    credentials = load_credentials()
    required_fields = ["site_url", "email", "senha"]
    
    # Verificar se todos os campos existem e não estão vazios
    complete = all(credentials.get(field, "").strip() for field in required_fields)
    
    if not complete:
        logger = UILogger()
        source = credentials.get("source", "unknown")
        logger.log(f"Credenciais incompletas (fonte: {source})")
    
    return complete

def login_to_sei(page):
    """Faz login no SEI verificando credenciais primeiro"""
    if not credentials_are_complete():
        raise Exception("Credenciais não configuradas ou incompletas. Configure nas Configurações primeiro.")
    
    credentials = load_credentials()
    logger = UILogger()
    source = credentials.get("source", "unknown")
    logger.log(f"Fazendo login no SEI (credenciais de: {source})")
    
    page.goto(credentials["site_url"])
    page.fill("#txtEmail", credentials["email"])
    page.fill("#pwdSenha", credentials["senha"])
    page.click("#sbmLogin")
    page.wait_for_load_state("networkidle")