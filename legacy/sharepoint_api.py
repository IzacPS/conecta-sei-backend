import os
import requests
from pathlib import Path
from documento_historico import salvar_historico_documento
import datetime
from typing import Optional, Dict, List
from logger_system import UILogger


class SharePointClient:
    # Use env vars in production; placeholders for repo safety
    TENANT_ID = os.environ.get("SHAREPOINT_TENANT_ID", "your-tenant-id")
    CLIENT_ID = os.environ.get("SHAREPOINT_CLIENT_ID", "your-client-id")
    CLIENT_SECRET = os.environ.get("SHAREPOINT_CLIENT_SECRET", "your-client-secret")
    DRIVE_ID = os.environ.get("SHAREPOINT_DRIVE_ID", "your-drive-id")
    ROOT_FOLDER_ID = os.environ.get("SHAREPOINT_ROOT_FOLDER_ID", "your-root-folder-id")

    def __init__(self):
        self.token = None
        self.token_expires = None
        self.logger = UILogger()
        self._refresh_token()

    def _refresh_token(self) -> None:
        token_url = (
            f"https://login.microsoftonline.com/{self.TENANT_ID}/oauth2/v2.0/token"
        )
        data = {
            "grant_type": "client_credentials",
            "client_id": self.CLIENT_ID,
            "client_secret": self.CLIENT_SECRET,
            "scope": "https://graph.microsoft.com/.default",
        }

        response = requests.post(token_url, data=data)
        response.raise_for_status()

        token_data = response.json()
        self.token = token_data["access_token"]
        self.token_expires = datetime.datetime.now().timestamp() + token_data["expires_in"]

    def _ensure_valid_token(self) -> None:
        if not self.token or datetime.datetime.now().timestamp() >= self.token_expires:
            self._refresh_token()

    def _make_request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        self._ensure_valid_token()
        headers = {"Authorization": f"Bearer {self.token}", **kwargs.pop("headers", {})}

        url = f"https://graph.microsoft.com/v1.0/{endpoint}"
        response = requests.request(method, url, headers=headers, **kwargs)
        response.raise_for_status()
        return response

    def get_folder_children(self, folder_id: str) -> List[dict]:
        try:
            endpoint = f"drives/{self.DRIVE_ID}/items/{folder_id}/children"
            response = self._make_request("GET", endpoint)
            return response.json().get("value", [])
        except Exception as e:
            self.logger.log(f"Erro ao listar conteúdo da pasta: {str(e)}")
            return []

    def find_folder_by_name(self, parent_id: str, folder_name: str) -> Optional[dict]:
        children = self.get_folder_children(parent_id)
        for child in children:
            if child.get("name") == folder_name and "folder" in child:
                #self.logger.log(f"Pasta encontrada: {folder_name}")
                return child
        return None

    def create_folder(self, parent_id: str, folder_name: str) -> Optional[dict]:
        try:
            endpoint = f"drives/{self.DRIVE_ID}/items/{parent_id}/children"
            data = {
                "name": folder_name,
                "folder": {},
                "@microsoft.graph.conflictBehavior": "replace",
            }

            response = self._make_request("POST", endpoint, json=data)
            folder_data = response.json()
            self.logger.log(f"Nova pasta criada: {folder_name}")
            return folder_data
        except Exception as e:
            self.logger.log(f"Erro ao criar pasta {folder_name}: {str(e)}")
            return None

    def ensure_folder_exists(self, parent_id: str, folder_name: str) -> Optional[str]:
        folder = self.find_folder_by_name(parent_id, folder_name)
        if folder:
            return folder.get("id")

        created_folder = self.create_folder(parent_id, folder_name)
        return created_folder.get("id") if created_folder else None

    def upload_file(self, file_path: Path, process_folder_name: str) -> bool:
        try:
            process_folder = self.find_folder_by_name(
                self.ROOT_FOLDER_ID, process_folder_name
            )
            if not process_folder:
                self.logger.log(
                    f"Pasta do processo não encontrada, criando: {process_folder_name}"
                )
                process_folder = self.create_folder(
                    self.ROOT_FOLDER_ID, process_folder_name
                )
                if not process_folder:
                    return False

            process_folder_id = process_folder.get("id")

            organizing_folder_id = self.ensure_folder_exists(
                process_folder_id, "a-organizar"
            )
            if not organizing_folder_id:
                return False

            date_folder_name = datetime.datetime.now().strftime("%d-%m-%Y")
            date_folder_id = self.ensure_folder_exists(
                organizing_folder_id, date_folder_name
            )
            if not date_folder_id:
                return False

            with open(file_path, "rb") as f:
                file_content = f.read()

            endpoint = f"drives/{self.DRIVE_ID}/items/{date_folder_id}:/{ file_path.name }:/content"
            headers = {"Content-Type": "application/octet-stream"}
            self._make_request("PUT", endpoint, headers=headers, data=file_content)

            self.logger.log(f"Arquivo {file_path.name} enviado com sucesso")
            return True

        except Exception as e:
            self.logger.log(
                f"Erro ao fazer upload do arquivo {file_path.name}: {str(e)}"
            )
            return False


def sanitize_process_number(process_number: str) -> str:
    return process_number.replace(".", "-").replace("/", "-")


def upload_to_sharepoint(
    file_path: Path, process_number: str, process_data: Dict
) -> bool:
    try:
        timestamp_inicio = datetime.datetime.now()
        registro_historico = {
            "processo_numero": process_number,
            "documento_numero": process_data.get("documento_atual", "desconhecido"),
            "nome_arquivo": file_path.name,
            "tamanho_arquivo_bytes": file_path.stat().st_size if file_path.exists() else 0,
            "timestamp_inicio": timestamp_inicio,
            "tipo_operacao": "upload",
            "resultado": "pendente",
            "apelido_processo": process_data.get("apelido", "")
        }
        
        client = SharePointClient()
        process_folder_name = (
            process_data.get("apelido")
            if process_data.get("apelido")
            else sanitize_process_number(process_number)
        )
        
        resultado = client.upload_file(file_path, process_folder_name)
        
        registro_historico["timestamp_fim"] = datetime.datetime.now()
        registro_historico["duracao_ms"] = (registro_historico["timestamp_fim"] - registro_historico["timestamp_inicio"]).total_seconds() * 1000
        registro_historico["resultado"] = "sucesso" if resultado else "falha"
        
        if not resultado:
            registro_historico["erro"] = "Falha no upload para SharePoint"
        
        salvar_historico_documento(registro_historico)
        
        return resultado
        
    except Exception as e:
        logger = UILogger()
        logger.log(f"Erro ao enviar arquivo para SharePoint: {str(e)}")
        
        try:
            registro_historico = {
                "processo_numero": process_number,
                "documento_numero": process_data.get("documento_atual", "desconhecido"),
                "nome_arquivo": file_path.name if file_path else "desconhecido",
                "timestamp_inicio": datetime.datetime.now() - datetime.timedelta(seconds=1),
                "timestamp_fim": datetime.datetime.now(),
                "duracao_ms": 1000,
                "tipo_operacao": "upload",
                "resultado": "falha",
                "erro": str(e),
                "apelido_processo": process_data.get("apelido", "")
            }
            salvar_historico_documento(registro_historico)
        except:
            pass
        
        return False
