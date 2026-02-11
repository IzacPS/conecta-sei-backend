"""
ConectaSEI v2.0 - Document Downloader

Módulo para download de documentos do SEI.

CONFORMIDADE COM LEGACY:
- Baseado em get_docs_download.py
- Fluxo: Download → Conversão HTML→PDF → Registro de histórico
- Ver LEGACY_DOWNLOADER_FLOW.md para detalhes completos

Uso:
    from core.document_downloader import DocumentDownloader

    downloader = DocumentDownloader()
    result = downloader.download_documents(process_id="uuid", doc_numbers=["12345678"])
"""

from playwright.sync_api import sync_playwright, Page, Browser, Playwright, Download
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime
import re
import logging

from app.database.session import get_session
from app.database.repositories.process_repository import ProcessRepository
from app.database.models.process import Process
from app.database.models.document_history import DocumentHistory
from app.utils.file_utils import get_app_data_dir
from app.utils.playwright_utils import login_to_sei

logger = logging.getLogger(__name__)


class DocumentDownloader:
    """
    Gerencia download de documentos do SEI.

    CONFORMIDADE COM LEGACY:
    - Download via Playwright (ALT+Click)
    - Conversão HTML→PDF quando necessário
    - Registro de histórico no PostgreSQL

    Attributes:
        browser: Playwright browser instance
        page: Playwright page instance
        playwright: Playwright instance
        temp_dir: Diretório temporário para downloads
    """

    def __init__(self):
        """Inicializa downloader (browser será criado sob demanda)."""
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        self.playwright: Optional[Playwright] = None
        self.temp_dir = self._get_temp_download_dir()

    def _get_temp_download_dir(self) -> Path:
        """
        Retorna diretório temporário para downloads.

        CONFORMIDADE COM LEGACY:
        - get_docs_download.py:71-74

        Returns:
            Path do diretório temp_downloads/
        """
        temp_dir = get_app_data_dir() / "temp_downloads"
        temp_dir.mkdir(parents=True, exist_ok=True)
        return temp_dir

    def _init_browser(self) -> None:
        """
        Inicializa browser Playwright e faz login.

        CONFORMIDADE COM LEGACY:
        - get_docs_download.py:20-35
        """
        if self.browser is not None:
            return  # Já inicializado

        logger.info("Inicializando browser Playwright")

        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(headless=True)
        self.page = self.browser.new_page()
        self.page.set_default_timeout(30000)

        # Login no SEI
        login_to_sei(self.page)

        logger.info("Browser inicializado e login realizado")

    def _cleanup_browser(self) -> None:
        """Limpa recursos do browser."""
        if self.browser:
            self.browser.close()
            self.browser = None

        if self.playwright:
            self.playwright.stop()
            self.playwright = None

        self.page = None

    def _process_filename(
        self,
        suggested_filename: str,
        doc_number: str,
        doc_info: Dict[str, Any]
    ) -> str:
        """
        Processa nome do arquivo para incluir tipo do documento.

        CONFORMIDADE COM LEGACY:
        - get_docs_download.py:41-48

        Ex: "12345678.pdf" → "Despacho_12345678.pdf"

        Args:
            suggested_filename: Nome sugerido pelo browser
            doc_number: Número do documento (8 dígitos)
            doc_info: Informações do documento (tipo, data, etc.)

        Returns:
            Nome processado do arquivo
        """
        filename_without_ext = Path(suggested_filename).stem

        # Se nome é apenas o número (8 dígitos)
        if filename_without_ext.isdigit() and len(filename_without_ext) == 8:
            ext = Path(suggested_filename).suffix

            # Adicionar tipo do documento
            doc_tipo = doc_info.get("tipo", "Documento")
            new_filename = f"{doc_tipo}_{filename_without_ext}{ext}"

            # Sanitizar caracteres inválidos para filesystem
            new_filename = re.sub(r'[<>:"/\\|?*]', "_", new_filename)

            return new_filename

        return suggested_filename

    def _handle_downloaded_file(
        self,
        temp_path: Path,
        doc_number: str,
        doc_info: Dict[str, Any]
    ) -> Path:
        """
        Processa arquivo baixado (converte HTML→PDF se necessário).

        CONFORMIDADE COM LEGACY:
        - get_docs_download.py:51-68

        Args:
            temp_path: Path do arquivo baixado
            doc_number: Número do documento
            doc_info: Informações do documento

        Returns:
            Path do arquivo final (PDF se convertido)
        """
        if temp_path.suffix.lower() == ".html":
            try:
                logger.info(f"Convertendo HTML→PDF: {doc_number}")

                pdf_path = temp_path.with_suffix(".pdf")

                # Abrir HTML no browser e converter para PDF
                self.page.goto(f"file:///{temp_path}")
                self.page.wait_for_load_state("load")
                self.page.pdf(path=str(pdf_path), format="A4")

                # Remover HTML original
                temp_path.unlink()

                logger.info(f"Conversão concluída: {pdf_path.name}")

                return pdf_path

            except Exception as e:
                logger.error(f"Erro ao converter HTML→PDF para {doc_number}: {e}")
                return temp_path  # Retornar HTML original

        return temp_path

    def _handle_dialog(self, dialog):
        """
        Handler para dialogs JavaScript durante download.

        CONFORMIDADE COM LEGACY:
        - get_docs_download.py:37-38
        """
        dialog.dismiss()

    def _download_single_document(
        self,
        doc_number: str,
        doc_info: Dict[str, Any],
        process_number: str,
        process_data: Dict[str, Any]
    ) -> bool:
        """
        Baixa um documento individual.

        CONFORMIDADE COM LEGACY:
        - get_docs_download.py:77-175

        Fluxo:
        1. Download do SEI → temp_downloads/
        2. Conversão HTML→PDF (se necessário)
        3. Registro de histórico
        4. Limpeza de arquivos temp

        Args:
            doc_number: Número do documento (8 dígitos)
            doc_info: Informações do documento
            process_number: Número do processo
            process_data: Dados completos do processo

        Returns:
            True se download + upload foram bem-sucedidos
        """
        logger.info(f"Baixando documento {doc_number} do processo {process_number}")

        temp_file = None
        timestamp_inicio = datetime.utcnow()

        # Preparar registro de histórico
        history_record = {
            "process_id": process_data.get("id"),
            "document_number": doc_number,
            "action": "download",
            "timestamp_inicio": timestamp_inicio,
            "details": {
                "tipo_documento": doc_info.get("tipo", "Desconhecido"),
                "data_documento": doc_info.get("data", ""),
                "signatario": doc_info.get("signatario", "Não identificado"),
                "processo_numero": process_number,
                "apelido_processo": process_data.get("apelido", "")
            }
        }

        try:
            # Configurar handler para dialogs
            self.page.on("dialog", self._handle_dialog)

            # Localizar link do documento
            doc_link = self.page.locator(f'a:text("{doc_number}")')
            doc_link.wait_for(state="visible", timeout=30000)

            # Iniciar download (ALT+Click)
            history_record["details"]["timestamp_download_inicio"] = datetime.utcnow()

            with self.page.expect_download(timeout=30000) as download_info:
                self.page.keyboard.down("Alt")
                doc_link.click()
                self.page.keyboard.up("Alt")

            download: Download = download_info.value
            suggested_filename = download.suggested_filename

            if not suggested_filename:
                raise ValueError("Nome de arquivo sugerido não disponível")

            # Processar nome do arquivo
            final_filename = self._process_filename(suggested_filename, doc_number, doc_info)
            temp_path = self.temp_dir / final_filename

            # Salvar arquivo localmente
            download.save_as(temp_path)

            history_record["details"]["timestamp_download_fim"] = datetime.utcnow()
            history_record["details"]["tamanho_arquivo_bytes"] = temp_path.stat().st_size
            history_record["details"]["nome_arquivo"] = temp_path.name

            # Calcular duração do download
            download_duration = (
                history_record["details"]["timestamp_download_fim"] -
                history_record["details"]["timestamp_download_inicio"]
            ).total_seconds() * 1000
            history_record["details"]["duracao_download_ms"] = download_duration

            # Processar arquivo (conversão HTML→PDF se necessário)
            final_path = self._handle_downloaded_file(temp_path, doc_number, doc_info)
            temp_file = final_path

            # Upload to Firebase Storage bucket
            history_record["details"]["timestamp_upload_inicio"] = datetime.utcnow()

            from app.utils.storage_service import upload_document
            institution_id = process_data.get("institution_id", "legacy")

            upload_success, storage_path = upload_document(
                local_file_path=str(final_path),
                process_number=process_number,
                document_number=doc_number,
                institution_id=institution_id,
            )

            history_record["details"]["timestamp_upload_fim"] = datetime.utcnow()

            if upload_success:
                history_record["details"]["resultado"] = "sucesso"
                history_record["details"]["storage_path"] = storage_path

                # Update Document.storage_path in the database
                self._update_document_storage_path(
                    process_data.get("id"),
                    doc_number,
                    storage_path,
                )

                logger.info(
                    f"Document {doc_number} uploaded to bucket: {storage_path}"
                )
                return True
            else:
                # Download succeeded but upload failed — partial success
                history_record["details"]["resultado"] = "sucesso_parcial"
                history_record["details"]["aviso"] = (
                    "Upload to Firebase Storage failed; "
                    "file kept locally as fallback"
                )
                logger.warning(
                    f"Document {doc_number} downloaded but upload to bucket failed"
                )
                return True

        except Exception as e:
            history_record["details"]["resultado"] = "falha"
            history_record["details"]["erro"] = str(e)
            logger.error(f"Erro ao baixar documento {doc_number}: {e}")
            return False

        finally:
            # Remover listener de dialog
            self.page.remove_listener("dialog", self._handle_dialog)

            # Calcular durações finais
            history_record["details"]["timestamp_fim"] = datetime.utcnow()
            total_duration = (
                history_record["details"]["timestamp_fim"] - timestamp_inicio
            ).total_seconds() * 1000
            history_record["details"]["duracao_total_ms"] = total_duration

            # Salvar histórico no PostgreSQL
            self._save_history(history_record)

            # Limpar arquivos temporários
            if temp_file and temp_file.exists():
                try:
                    temp_file.unlink()
                    logger.debug(f"Arquivo temporário removido: {temp_file}")
                except Exception as e:
                    logger.warning(f"Erro ao remover arquivo temporário: {e}")

    def _save_history(self, history_record: Dict[str, Any]) -> None:
        """
        Persist a history record in PostgreSQL.

        Args:
            history_record: Dict with process_id, document_number, action, details.
        """
        try:
            with get_session() as session:
                history = DocumentHistory(
                    process_id=history_record["process_id"],
                    document_number=history_record["document_number"],
                    action=history_record["action"],
                    extra_metadata=history_record.get("details", {}),
                )
                session.add(history)
                session.commit()

                logger.debug(
                    f"History saved for document {history_record['document_number']}"
                )

        except Exception as e:
            logger.error(f"Failed to save history: {e}")

    def _update_document_storage_path(
        self,
        process_id: Optional[str],
        doc_number: str,
        storage_path: str,
    ) -> None:
        """
        Update the Document row with the Firebase Storage blob path.

        This allows the API to generate signed download URLs on demand.
        """
        if not process_id:
            return

        try:
            from app.database.models.document import Document

            with get_session() as session:
                doc = session.query(Document).filter(
                    Document.process_id == process_id,
                    Document.document_number == doc_number,
                ).first()

                if doc:
                    doc.storage_path = storage_path
                    doc.status = "downloaded"
                    session.commit()
                    logger.debug(
                        f"Document {doc_number} storage_path updated: {storage_path}"
                    )
        except Exception as e:
            logger.warning(f"Failed to update Document storage_path: {e}")

    def download_documents(
        self,
        process_id: str,
        doc_numbers: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Baixa documentos de um processo específico.

        Args:
            process_id: UUID do processo
            doc_numbers: Lista de números de documentos (None = todos novos)

        Returns:
            Dict com resultado:
            {
                "process_id": str,
                "total_documents": int,
                "successful": int,
                "failed": int,
                "downloaded": List[str],
                "errors": Dict[str, str]
            }
        """
        try:
            # Inicializar browser
            self._init_browser()

            # Buscar processo
            with get_session() as session:
                repo = ProcessRepository(session)
                process = repo.get_by_id(process_id)

                if not process:
                    raise ValueError(f"Processo '{process_id}' não encontrado")

                # Verificar se tem links válidos
                if process.sem_link_validos:
                    raise ValueError("Processo sem links válidos")

                # Determinar quais documentos baixar
                if doc_numbers is None:
                    # Baixar todos os marcados como novos
                    doc_numbers = process.metadata.get("novos_documentos", [])

                if not doc_numbers:
                    return {
                        "process_id": process_id,
                        "total_documents": 0,
                        "successful": 0,
                        "failed": 0,
                        "downloaded": [],
                        "errors": {}
                    }

                # Navegar para o processo
                best_link = process.melhor_link_atual
                if not best_link:
                    raise ValueError("Processo sem link válido disponível")

                base_url = "https://colaboragov.sei.gov.br/sei/"
                process_url = f"{base_url}{best_link}"

                self.page.goto(process_url)
                self.page.wait_for_selector("#tblDocumentos", timeout=30000)

                # Baixar cada documento
                successful = []
                errors = {}

                for doc_number in doc_numbers:
                    # Voltar para página do processo se necessário
                    current_url = self.page.url
                    if current_url != process_url:
                        try:
                            self.page.go_back()
                            self.page.wait_for_selector("#tblDocumentos", timeout=15000)
                        except Exception:
                            self.page.goto(process_url)
                            self.page.wait_for_selector("#tblDocumentos", timeout=30000)

                    # Obter informações do documento
                    doc_info = process.documentos.get(doc_number, {})

                    # Baixar documento
                    success = self._download_single_document(
                        doc_number,
                        doc_info,
                        process.numero_processo,
                        {
                            "id": process.id,
                            "apelido": getattr(process, 'apelido', None)
                        }
                    )

                    if success:
                        successful.append(doc_number)

                        # Atualizar status do documento
                        if doc_number in process.documentos:
                            process.documentos[doc_number]["status"] = "baixado"
                    else:
                        errors[doc_number] = "Falha no download ou upload"

                # Atualizar lista de novos documentos
                if "novos_documentos" in process.metadata:
                    remaining = [d for d in process.metadata["novos_documentos"] if d not in successful]
                    if remaining:
                        process.metadata["novos_documentos"] = remaining
                    else:
                        del process.metadata["novos_documentos"]

                # Salvar alterações
                repo.update(
                    process_id,
                    documentos=process.documentos,
                    metadata=process.metadata
                )

                return {
                    "process_id": process_id,
                    "total_documents": len(doc_numbers),
                    "successful": len(successful),
                    "failed": len(errors),
                    "downloaded": successful,
                    "errors": errors
                }

        finally:
            self._cleanup_browser()
