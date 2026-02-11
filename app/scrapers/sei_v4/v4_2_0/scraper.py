"""
ConectaSEI v2.0 - SEI v4.2.0 Scraper Implementation

This scraper implements all extraction logic for SEI v4.2.0.
Migrated from legacy codebase (get_*.py files) to new plugin architecture.
"""

import re
import datetime
from typing import Dict, List, Optional, Any
from playwright.sync_api import Page
from bs4 import BeautifulSoup

from app.scrapers.sei_v4.base import SEIv4Base
from app.scrapers.registry import register_scraper
from .selectors import (
    LOGIN,
    PROCESS_LIST,
    LINK_VALIDATION,
    AUTHORITY,
    DOCUMENTS,
    UNIT,
    INDICATORS,
)


@register_scraper()
class SEIv4_2_0(SEIv4Base):
    """
    SEI v4.2.0 Scraper

    Implements all scraping logic for SEI version 4.2.0.
    This is currently the production version being used.

    Migrated from:
    - utils.py: login_to_sei()
    - get_process_update.py: extract_process_info_fast()
    - get_process_links_status.py: verify_access_type(), collect_authority_if_missing()
    - get_process_docs_update.py: process_documents_page()
    """

    VERSION = "4.2.0"
    VERSION_RANGE = ">=4.2.0 <4.3.0"

    def get_version_info(self) -> Dict[str, str]:
        """Get version information."""
        return {
            "version": self.VERSION,
            "version_range": self.VERSION_RANGE,
            "family": self.FAMILY,
            "description": "SEI v4.2.0 Scraper (Production)"
        }

    # ==================== Authentication ====================

    def get_login_selectors(self) -> Dict[str, str]:
        """
        Login selectors for v4.2.0.

        Source: utils.py:login_to_sei()
        """
        return LOGIN

    def login(self, page: Page, email: str, password: str) -> bool:
        """
        Perform login to SEI v4.2.0.

        Migrated from: utils.py:login_to_sei()

        Args:
            page: Playwright page
            email: User email
            password: User password

        Returns:
            True if login successful

        Raises:
            Exception: If login fails
        """
        selectors = self.get_login_selectors()

        try:
            # Navigate to login page (URL set by institution config)
            # page.goto() should be called by the caller with institution's sei_url

            # Fill credentials
            page.fill(selectors["email"], email)
            page.fill(selectors["password"], password)

            # Submit
            page.click(selectors["submit"])

            # Wait for navigation
            page.wait_for_load_state("networkidle", timeout=30000)

            # Check for errors
            if page.locator(selectors.get("error", "")).count() > 0:
                error_msg = page.locator(selectors["error"]).text_content()
                raise Exception(f"Login failed: {error_msg}")

            # Verify login success
            if not self.is_logged_in(page):
                raise Exception("Login verification failed")

            return True

        except Exception as e:
            raise Exception(f"Login error: {str(e)}")

    def is_logged_in(self, page: Page) -> bool:
        """
        Check if user is logged in.

        v4.2.0 has logout link when logged in.
        """
        return page.locator(INDICATORS["logged_in"]).count() > 0

    # ==================== Process Discovery (Stage 1) ====================

    def get_process_list_url(self) -> str:
        """Get URL for process list page."""
        return "/controlador.php?acao=procedimento_controlar"

    def extract_process_list(self, page: Page) -> Dict[str, Dict[str, Any]]:
        """
        Extract list of processes from the process list page.

        Migrated from: get_process_update.py:extract_process_info_fast()

        This is Stage 1: Fast discovery - collects ONLY process numbers
        and links without opening individual processes.

        Authority will be collected later in Stage 2/3 when processes are opened.

        Args:
            page: Playwright page on process list

        Returns:
            Dict mapping process_number to process data with links
        """
        processes = {}
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        try:
            # Wait for table
            page.wait_for_selector(PROCESS_LIST["table"], state="visible", timeout=30000)

            # Get all rows (excluding header)
            rows = page.query_selector_all(PROCESS_LIST["rows"])

            for row in rows:
                try:
                    # Extract link element
                    link_element = row.query_selector(PROCESS_LIST["link_element"])
                    if not link_element:
                        continue

                    # Get href and process number
                    href = link_element.get_attribute("href")
                    process_number = link_element.inner_text().strip()

                    if not process_number or not href:
                        continue

                    # Normalize link
                    normalized_href = self._normalize_link(href)
                    if not normalized_href:
                        continue

                    # Create process entry if doesn't exist
                    if process_number not in processes:
                        processes[process_number] = {
                            "numero_processo": process_number,
                            "links": {},
                            "documentos": {},
                            "tipo_acesso_atual": None,
                            "melhor_link_atual": None,
                            "categoria": None,
                            "status_categoria": None,
                            "unidade": None,
                            "Autoridade": None,  # Will be collected in Stage 2/3
                            "sem_link_validos": False,
                            "apelido": None,
                        }

                    # Add link with initial status
                    processes[process_number]["links"][normalized_href] = {
                        "status": "ativo",
                        "tipo_acesso": None,  # Will be determined in Stage 2
                        "ultima_verificacao": current_time,
                        "historico": [],
                    }

                except Exception:
                    continue

        except Exception as e:
            raise Exception(f"Failed to extract process list: {str(e)}")

        return processes

    def _normalize_link(self, full_url: str) -> Optional[str]:
        """
        Normalize a process link to extract the ID parameter.

        Migrated from: get_process_update.py:normalize_link()
        """
        if not full_url:
            return None

        try:
            match = re.search(r'id_procedimento_externo=([^&]+)', full_url)
            if match:
                return match.group(1)
        except Exception:
            pass

        return None

    # ==================== Link Validation & Authority (Stage 2) ====================

    def validate_link(self, page: Page, link: str) -> Dict[str, Any]:
        """
        Navigate to process link and validate access type.

        Migrated from: get_process_links_status.py:verify_access_type()

        This is Stage 2: Determines if link is valid and access type.
        Also opportunistically collects authority while process is open.

        Args:
            page: Playwright page
            link: Process link (normalized ID)

        Returns:
            Dict with:
                - valid: bool
                - tipo_acesso: "integral" or "parcial"
                - autoridade: str (optional)
                - error: str (optional)
        """
        try:
            # Navigate to process (build full URL with link ID)
            # Note: Caller should have base URL from institution config
            # Full URL format: {base_url}/controlador_externo.php?acao=procedimento_visualizar&id_procedimento_externo={link}

            # Wait for page to load
            page.wait_for_load_state("networkidle", timeout=30000)

            # Determine access type
            access_type = self._get_access_type(page)

            if access_type == "error":
                return {
                    "valid": False,
                    "tipo_acesso": None,
                    "error": "Failed to determine access type"
                }

            # Collect authority opportunistically
            authority = self.extract_authority(page)

            return {
                "valid": True,
                "tipo_acesso": access_type,
                "autoridade": authority
            }

        except Exception as e:
            return {
                "valid": False,
                "tipo_acesso": None,
                "error": str(e)
            }

    def _get_access_type(self, page: Page) -> str:
        """
        Determine access type from location bar.

        Migrated from: get_process_links_status.py:verify_access_type()
        """
        try:
            locator = page.locator(LINK_VALIDATION["location_bar"])
            if locator.count() > 0:
                text = locator.inner_text()

                # Check for integral access
                for keyword in LINK_VALIDATION["integral_keywords"]:
                    if keyword in text:
                        return "integral"

                # Check for parcial access
                for keyword in LINK_VALIDATION["parcial_keywords"]:
                    if keyword in text:
                        return "parcial"

            return "error"

        except Exception:
            return "error"

    def get_access_type_selectors(self) -> Dict[str, str]:
        """Get selectors for determining access type."""
        return LINK_VALIDATION

    # ==================== Authority Extraction ====================

    def get_authority_selectors(self) -> Dict[str, str]:
        """Get selectors for authority field."""
        return AUTHORITY

    def extract_authority(self, page: Page) -> Optional[str]:
        """
        Extract authority (Autoridade) from process page.

        Migrated from: get_process_links_status.py:collect_authority_if_missing()

        Called opportunistically when process is already open.

        Args:
            page: Playwright page on process view

        Returns:
            Authority string if found, None otherwise
        """
        try:
            authority_element = page.query_selector(AUTHORITY["authority_xpath"])
            if not authority_element:
                return None

            full_authority = authority_element.inner_text().strip()
            if not full_authority:
                return None

            # Parse authority (format: "XXX - YYY - Authority Name")
            parts = full_authority.split("-")
            if len(parts) >= 3:
                return parts[2].strip()
            elif len(parts) >= 2:
                return parts[1].strip()
            else:
                return full_authority.strip()

        except Exception:
            return None

    # ==================== Document Discovery (Stage 3) ====================

    def get_document_list_selectors(self) -> Dict[str, str]:
        """Get selectors for document list."""
        return DOCUMENTS

    def extract_documents(self, page: Page) -> Dict[str, Dict[str, Any]]:
        """
        Extract all documents from process page.

        Migrated from: get_process_docs_update.py:process_documents_page()

        This is Stage 3: Discovers new or updated documents.
        Should only be called if should_process_documents() returns True.

        Args:
            page: Playwright page on process view

        Returns:
            Dict mapping document_number to document data
        """
        try:
            # Wait for document table
            page.wait_for_selector(DOCUMENTS["table"], timeout=60000)

        except Exception as e:
            raise Exception(f"Document table not found: {str(e)}")

        try:
            # Get HTML content for BeautifulSoup parsing
            html_content = page.content()
            soup = BeautifulSoup(html_content, "html.parser")

            # Process documents
            documents = {}
            rows = soup.select("#tblDocumentos tr.infraTrClara")

            for row in rows:
                try:
                    # Get document link
                    doc_link = row.select_one("td:nth-child(2) a")
                    if not doc_link:
                        continue

                    # Check for access restrictions (onclick with alert)
                    onclick_attr = doc_link.get("onclick", "")
                    if onclick_attr and "alert(" in onclick_attr:
                        continue  # Skip restricted documents

                    # Get document number
                    doc_number = doc_link.get_text(strip=True)
                    if not re.match(r'^\d{8}$', doc_number):
                        continue  # Invalid document number

                    # Extract document data
                    tipo_cell = row.select_one("td:nth-child(3)")
                    data_cell = row.select_one("td:nth-child(4)")

                    if not tipo_cell or not data_cell:
                        continue

                    documents[doc_number] = {
                        "numero": doc_number,
                        "tipo": tipo_cell.get_text(strip=True),
                        "data": data_cell.get_text(strip=True),
                        "status": "nao_baixado",
                        "data_descoberta": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    }

                except Exception:
                    continue

            return documents

        except Exception as e:
            raise Exception(f"Failed to extract documents: {str(e)}")

    # ==================== Document Download (Stage 4) ====================

    def get_document_download_url(self, document_link: str) -> str:
        """
        Convert document view link to download URL.

        Note: SEI v4.2.0 uses same URL for viewing and downloading.
        Download is triggered by browser behavior.
        """
        return document_link

    def download_document(
        self,
        page: Page,
        document_link: str,
        output_path: str
    ) -> bool:
        """
        Download a document and save to output_path.

        Note: Actual download implementation will be in Sprint 2.3
        (document downloader module).

        For now, this is a placeholder.
        """
        raise NotImplementedError("Document download will be implemented in Sprint 2.3")

    # ==================== Utility Methods ====================

    def wait_for_page_load(self, page: Page, timeout: int = 30000) -> bool:
        """Wait for page to fully load."""
        try:
            page.wait_for_load_state("networkidle", timeout=timeout)

            # Wait for loading indicator to disappear
            try:
                page.wait_for_selector(
                    INDICATORS["loading"],
                    state="hidden",
                    timeout=5000
                )
            except Exception:
                pass  # Loading indicator might not exist

            return True

        except Exception:
            return False
