"""
ProcessExtractor - Módulo de extração de processos (Sprint 2.1)

Este módulo implementa o pipeline de extração de processos em 2 etapas:
1. Stage 1: Descoberta rápida de processos (tabela principal)
2. Stage 2+3 (merged): Validação de links + Extração de documentos (navegação individual)

Características:
- Multithreading com ThreadPoolExecutor (5-10 workers)
- Detecção de novos processos e documentos
- Notificações para ambos os casos
- Integração com PostgreSQL + ParadeDB via repositories
- Uso do InstitutionService para seleção de scraper correto
- Abstração via SEIScraperBase (plugin system)
"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple
from playwright.sync_api import Page, Browser

from app.core.services.institution_service import InstitutionService
from app.database.repositories.process_repository import ProcessRepository
from app.database.repositories.institution_repository import InstitutionRepository
from app.scrapers.base import SEIScraperBase
from app.utils import email_service as email_svc

logger = logging.getLogger(__name__)


class ProcessExtractor:
    """
    Extrator de processos do SEI com pipeline otimizado.

    Pipeline:
    1. discover_process_list() - Lista processos da tabela principal (rápido)
    2. process_worker() - Para cada processo: valida link + extrai documentos (paralelo)
    3. Detecta novos processos e documentos
    4. Envia notificações apropriadas

    Utiliza o plugin system de scrapers via InstitutionService para garantir
    compatibilidade com diferentes versões do SEI.
    """

    def __init__(
        self,
        process_repo: ProcessRepository,
        institution_repo: InstitutionRepository,
        institution_service: InstitutionService,
        max_workers: int = 5
    ):
        """
        Inicializa o ProcessExtractor.

        Args:
            process_repo: Repositório de processos
            institution_repo: Repositório de instituições
            institution_service: Serviço de gerenciamento de instituições
            max_workers: Número de threads para processamento paralelo
        """
        self.process_repo = process_repo
        self.institution_repo = institution_repo
        self.institution_service = institution_service
        self.max_workers = max_workers

        # Caches para otimização
        self._existing_processes: Dict[str, dict] = {}
        self._new_processes: List[str] = []
        self._new_documents: Dict[str, List[str]] = {}

    def discover_process_list(
        self,
        page: Page,
        scraper: SEIScraperBase,
        institution_id: str
    ) -> Dict[str, dict]:
        """
        Stage 1: Descoberta rápida de processos da tabela principal.

        Esta etapa é ultra-otimizada:
        - Delega para scraper.extract_process_list() (versão-específico)
        - Apenas lê a tabela HTML da página principal
        - Extrai números de processos e links
        - NÃO navega para processos individuais
        - NÃO coleta dados de autoridade (será feito em Stage 2+3)

        Args:
            page: Página Playwright já logada
            scraper: Scraper específico da versão SEI
            institution_id: ID da instituição

        Returns:
            Dict com {numero_processo: {processo_data}}
        """
        logger.info("=== STAGE 1: Descoberta de processos ===")

        try:
            # Navega para página de listagem de processos
            list_url = scraper.get_process_list_url()
            page.goto(list_url, timeout=30000)
            scraper.wait_for_page_load(page)

            # Extrai processos usando scraper específico da versão
            processes = scraper.extract_process_list(page)

            # Adiciona metadados
            for process_number in processes:
                processes[process_number]["institution_id"] = institution_id
                processes[process_number]["discovered_at"] = datetime.now().isoformat()

            logger.info(f"Stage 1 concluído: {len(processes)} processos descobertos")
            return processes

        except Exception as e:
            logger.error(f"Erro na descoberta de processos: {e}")
            raise

    def _compare_processes(self, old_processes: Set[str], new_processes: Set[str]) -> List[str]:
        """
        Compara processos antigos e novos para identificar novos processos.

        Args:
            old_processes: Set de números de processos já existentes no banco
            new_processes: Set de números de processos descobertos no SEI

        Returns:
            Lista de números de processos novos
        """
        if not old_processes:
            return list(new_processes)

        new = new_processes - old_processes
        return sorted(list(new))

    def process_worker(
        self,
        browser: Browser,
        process_number: str,
        process_data: dict,
        scraper: SEIScraperBase,
        institution_id: str
    ) -> Optional[dict]:
        """
        Stage 2+3 (merged): Valida link + Extrai documentos em uma única navegação.

        Esta função é executada em paralelo por múltiplos workers.

        Fluxo:
        1. Abre nova página no browser
        2. Navega para o link do processo (via scraper.validate_link)
        3. Valida se o link é válido (Stage 2)
        4. Determina tipo de acesso: "integral" ou "parcial" (Stage 2)
        5. Coleta autoridade se estiver faltando (Stage 2)
        6. Se should_process_documents() == True: extrai documentos (Stage 3)
        7. Detecta novos documentos (Stage 3)

        Args:
            browser: Browser Playwright (thread-safe)
            process_number: Número do processo
            process_data: Dados do processo (links, etc)
            scraper: Scraper específico da versão SEI
            institution_id: ID da instituição

        Returns:
            Dict com dados atualizados do processo, ou None se erro
        """
        page = None
        try:
            # Cria nova página (thread-safe)
            page = browser.new_page()

            logger.info(f"[{process_number}] Iniciando processamento (Stage 2+3)")

            # Extrai melhor link disponível
            links = process_data.get("links", {})
            if not links:
                logger.error(f"[{process_number}] Nenhum link encontrado")
                return None

            # Pega primeiro link disponível (Stage 1 já encontrou)
            link = list(links.keys())[0]

            # === STAGE 2: Validação de link ===
            logger.info(f"[{process_number}] Validando link...")

            validation_result = scraper.validate_link(page, link)

            if not validation_result.get("valid"):
                logger.warning(f"[{process_number}] Link inválido: {validation_result.get('error', 'Desconhecido')}")
                return {
                    "process_number": process_number,
                    "link_valid": False,
                    "access_type": None,
                    "authority": None,
                    "documents": {},
                    "error": validation_result.get("error")
                }

            # Link válido - extrai informações
            access_type = validation_result.get("tipo_acesso", "desconhecido")
            authority = validation_result.get("autoridade")

            logger.info(f"[{process_number}] Link válido - Tipo de acesso: {access_type}")

            # === STAGE 3: Extração de documentos ===

            documents = {}

            # Verifica se deve processar documentos
            if self._should_process_documents(access_type, process_data):
                logger.info(f"[{process_number}] Extraindo documentos...")

                try:
                    documents = scraper.extract_documents(page)
                    logger.info(f"[{process_number}] {len(documents)} documentos extraídos")
                except Exception as e:
                    logger.error(f"[{process_number}] Erro ao extrair documentos: {e}")
            else:
                logger.info(f"[{process_number}] Pula extração de documentos (should_process_documents=False)")

            return {
                "process_number": process_number,
                "link": link,
                "link_valid": True,
                "access_type": access_type,
                "authority": authority,
                "documents": documents,
                "updated_at": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"[{process_number}] Erro no processamento: {e}")
            return None

        finally:
            if page:
                page.close()

    def _should_process_documents(self, access_type: str, process_data: dict) -> bool:
        """
        Determina se deve processar documentos do processo.

        Lógica (replicada do legado utils.py:93-115):
        - Se access_type == "integral": sempre processar
        - Se access_type == "parcial":
            - Se status_categoria == "pendente": NÃO processar
            - Se categoria == "restrito": processar
            - Caso contrário: NÃO processar

        Args:
            access_type: "integral" ou "parcial"
            process_data: Dados do processo com categoria e status

        Returns:
            True se deve processar documentos, False caso contrário
        """
        if access_type == "integral":
            return True

        # Acesso parcial: só processa em casos específicos
        status_categoria = process_data.get("status_categoria")
        categoria = process_data.get("categoria")

        if status_categoria == "pendente":
            return False

        if categoria == "restrito":
            return True

        return False

    def _detect_new_documents(
        self,
        process_number: str,
        existing_docs: Dict[str, dict],
        new_docs: Dict[str, dict]
    ) -> List[str]:
        """
        Detecta novos documentos comparando com documentos existentes.

        Args:
            process_number: Número do processo
            existing_docs: Documentos já existentes no banco
            new_docs: Documentos extraídos agora do SEI

        Returns:
            Lista de números de documentos novos
        """
        new_doc_numbers = []

        for doc_number in new_docs.keys():
            # Documento é novo se não existe no banco
            if doc_number not in existing_docs:
                new_doc_numbers.append(doc_number)
                logger.info(f"[{process_number}] Novo documento detectado: {doc_number}")

        return new_doc_numbers

    def run_extraction(
        self,
        browser: Browser,
        page: Page,
        institution_id: str
    ) -> Tuple[int, int, int]:
        """
        Executa o pipeline completo de extração.

        Fluxo:
        1. Obtém scraper correto via InstitutionService
        2. Stage 1: discover_process_list() - lista processos (rápido, sequencial)
        3. Carrega processos existentes do banco
        4. Detecta novos processos
        5. Stage 2+3: process_worker() - processa cada processo (paralelo, multithreading)
        6. Salva resultados no banco
        7. Detecta novos documentos
        8. Envia notificações

        Args:
            browser: Browser Playwright
            page: Página Playwright já logada
            institution_id: ID da instituição

        Returns:
            Tupla (total_processos, novos_processos, novos_documentos)
        """
        logger.info("=== INICIANDO PIPELINE DE EXTRAÇÃO ===")

        # === Obtém scraper correto ===
        scraper = self.institution_service.get_scraper(institution_id)
        logger.info(f"Usando scraper: {scraper.get_scraper_name()}")

        # === STAGE 1: Descoberta de processos ===
        discovered_processes = self.discover_process_list(page, scraper, institution_id)
        total_processes = len(discovered_processes)

        if total_processes == 0:
            logger.warning("Nenhum processo descoberto. Encerrando.")
            return (0, 0, 0)

        # === Carrega processos existentes do banco ===
        existing_processes_data = self.process_repo.get_all_by_institution(institution_id)
        existing_process_numbers = {p["process_number"] for p in existing_processes_data}
        self._existing_processes = {p["process_number"]: p for p in existing_processes_data}

        logger.info(f"Processos existentes no banco: {len(existing_process_numbers)}")

        # === Detecta novos processos ===
        discovered_process_numbers = set(discovered_processes.keys())
        self._new_processes = self._compare_processes(existing_process_numbers, discovered_process_numbers)

        logger.info(f"Novos processos detectados: {len(self._new_processes)}")
        if self._new_processes:
            logger.info(f"Lista: {', '.join(self._new_processes[:10])}{'...' if len(self._new_processes) > 10 else ''}")

        # === STAGE 2+3: Processamento paralelo ===
        logger.info(f"=== STAGE 2+3: Processamento paralelo ({self.max_workers} workers) ===")

        processed_count = 0
        self._new_documents = {}

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submete todos os processos para processamento
            future_to_process = {
                executor.submit(
                    self.process_worker,
                    browser,
                    process_number,
                    process_data,
                    scraper,
                    institution_id
                ): process_number
                for process_number, process_data in discovered_processes.items()
            }

            # Processa resultados conforme completam
            for future in as_completed(future_to_process):
                process_number = future_to_process[future]

                try:
                    result = future.result()

                    if result:
                        processed_count += 1

                        # Salva resultado no banco
                        self._save_process_result(result)

                        # Detecta novos documentos
                        if result.get("documents"):
                            existing_docs = self._existing_processes.get(process_number, {}).get("documents", {})
                            new_docs = self._detect_new_documents(
                                process_number,
                                existing_docs,
                                result["documents"]
                            )

                            if new_docs:
                                self._new_documents[process_number] = new_docs

                        logger.info(f"Progresso: {processed_count}/{total_processes} processos")

                except Exception as e:
                    logger.error(f"Erro ao processar resultado de {process_number}: {e}")

        # === Envia notificações ===
        total_new_docs = sum(len(docs) for docs in self._new_documents.values())

        logger.info(f"\n=== RESUMO DA EXTRAÇÃO ===")
        logger.info(f"Total de processos: {total_processes}")
        logger.info(f"Novos processos: {len(self._new_processes)}")
        logger.info(f"Processos com novos documentos: {len(self._new_documents)}")
        logger.info(f"Total de novos documentos: {total_new_docs}")

        # Notificações (usa discovered_processes para montar links nos emails)
        self._send_notifications(discovered_processes)

        return (total_processes, len(self._new_processes), total_new_docs)

    def _save_process_result(self, result: dict) -> None:
        """
        Salva resultado do processamento no banco.

        Args:
            result: Dict com dados do processo processado
        """
        process_number = result["process_number"]

        try:
            # Verifica se processo já existe
            existing = self.process_repo.get_by_number(process_number)

            if existing:
                # Atualiza processo existente
                self.process_repo.update(
                    process_number,
                    {
                        "link_valid": result["link_valid"],
                        "access_type": result["access_type"],
                        "authority": result.get("authority"),
                        "documents": result.get("documents", {}),
                        "updated_at": result["updated_at"]
                    }
                )
            else:
                # Cria novo processo
                self.process_repo.create({
                    "process_number": process_number,
                    "link_valid": result["link_valid"],
                    "access_type": result["access_type"],
                    "authority": result.get("authority"),
                    "documents": result.get("documents", {}),
                    "created_at": datetime.now().isoformat(),
                    "updated_at": result["updated_at"]
                })

        except Exception as e:
            logger.error(f"Erro ao salvar processo {process_number}: {e}")

    def _send_notifications(self, discovered_processes: Dict[str, dict]) -> None:
        """
        Envia notificações por email sobre novos processos e documentos.

        Mantém comportamento do legado:
        - Notificação de novos processos (se houver)
        - Notificação de novos documentos (se houver, independente se processo é novo)

        NÃO filtra documentos de processos novos - ambas notificações são enviadas.
        """
        if self._new_processes:
            logger.info(f"\n📧 NOTIFICAÇÃO: {len(self._new_processes)} novos processos")
            # Monta lista com process_number e link para o email (discovered_processes: {process_number: {links: {...}}})
            payload = []
            for p in self._new_processes:
                data = discovered_processes.get(p, {})
                link = ""
                if isinstance(data, dict):
                    links = data.get("links", {})
                    if links:
                        link = next(iter(links.keys()), "")
                payload.append({"process_number": p, "link": link})
            try:
                if email_svc.notify_new_processes(payload):
                    logger.info("Email de novos processos enviado.")
                else:
                    logger.warning("Falha ao enviar email de novos processos.")
            except Exception as e:
                logger.exception("Erro ao enviar notificação de novos processos: %s", e)

        if self._new_documents:
            total_docs = sum(len(docs) for docs in self._new_documents.values())
            logger.info(f"\n📧 NOTIFICAÇÃO: {total_docs} novos documentos em {len(self._new_documents)} processos")
            # Formato esperado por notify_new_documents: {processo: {apelido, documentos_por_signatario}}
            process_data = {}
            for process_number, doc_list in self._new_documents.items():
                apelido = email_svc.get_process_nickname(process_number)
                process_data[process_number] = {
                    "apelido": apelido or "",
                    "documentos_por_signatario": {"Novos documentos": doc_list},
                }
            try:
                if email_svc.notify_new_documents(process_data):
                    logger.info("Email de novos documentos enviado.")
                else:
                    logger.warning("Falha ao enviar email de novos documentos.")
            except Exception as e:
                logger.exception("Erro ao enviar notificação de novos documentos: %s", e)
