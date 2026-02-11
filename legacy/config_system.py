from pathlib import Path
import os
import json
import datetime

DEFAULT_CONFIG = {
    "site_url": "https://colaboragov.sei.gov.br/sei/controlador_externo.php?acao=usuario_externo_logar&id_orgao_acesso_externo=0",
    "email": "",
    "senha": "",
    "last_update": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
}

def get_config_path() -> Path:
    base_dir = Path(os.getenv("LOCALAPPDATA")) / "SEI_UNO_TRADE" / "config"
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir / "credenciais.json"

def initialize_config():
    config_path = get_config_path()
    if not config_path.exists():
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_CONFIG, f, ensure_ascii=False, indent=2)
    return config_path

def load_config() -> dict:
    config_path = get_config_path()
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return DEFAULT_CONFIG

def save_config(settings: dict):
    config_path = get_config_path()
    settings["last_update"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)