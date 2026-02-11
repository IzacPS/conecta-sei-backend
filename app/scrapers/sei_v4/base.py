"""
ConectaSEI v2.0 - SEI v4 Family Base Scraper

Base class for all SEI v4.x scrapers.
Implements common functionality shared across v4 family.
"""

from abc import abstractmethod
from typing import Dict, Optional
from playwright.sync_api import Page
from app.scrapers.base import SEIScraperBase


class SEIv4Base(SEIScraperBase):
    """
    Base scraper for SEI v4.x family.

    All v4-specific scrapers should inherit from this class.
    This class implements common v4 behavior while allowing
    version-specific overrides.

    SEI v4 introduced significant UI changes compared to v3:
    - New Bootstrap-based interface
    - Improved accessibility
    - Better mobile support
    - Enhanced document viewer
    """

    FAMILY = "v4"
    VERSION = "4.0.0"  # Override in subclasses
    VERSION_RANGE = ">=4.0.0 <5.0.0"

    def get_version_info(self) -> Dict[str, str]:
        """Get version information for this scraper."""
        return {
            "version": self.VERSION,
            "version_range": self.VERSION_RANGE,
            "family": self.FAMILY,
            "description": f"SEI v4 Family Scraper (v{self.VERSION})"
        }

    def detect_version(self, page: Page) -> Optional[str]:
        """
        Detect if page is SEI v4.

        Common detection strategies for v4:
        - Check data-version attribute
        - Check v4-specific meta tags
        - Check Bootstrap classes
        - Check modern UI elements
        """
        try:
            # Strategy 1: Check data-version attribute
            version_attr = page.locator('[data-sei-version]').get_attribute("data-sei-version")
            if version_attr and version_attr.startswith("4."):
                return version_attr

            # Strategy 2: Check meta tag (v4+ standard)
            meta_version = page.locator('meta[name="sei-version"]').get_attribute("content")
            if meta_version and meta_version.startswith("4."):
                return meta_version

            # Strategy 3: Check JavaScript global variable
            js_version = page.evaluate("window.SEI_VERSION || window.seiVersion")
            if js_version and str(js_version).startswith("4."):
                return str(js_version)

            # Strategy 4: Check v4-specific UI elements
            v4_indicators = page.locator(".sei-v4, #sei-navbar, .sei-modern-ui").count()
            if v4_indicators > 0:
                return self.VERSION  # Return generic v4 version

        except Exception:
            pass

        return None

    # ==================== Authentication ====================

    def get_login_selectors(self) -> Dict[str, str]:
        """
        Common login selectors for SEI v4.

        v4 uses standard Bootstrap form elements.
        Override if specific version has different selectors.
        """
        return {
            "email": "#txtUsuario",
            "password": "#pwdSenha",
            "submit": "#sbmLogin",
            "error": ".alert-danger, #divInfraMsg"
        }

    def login(self, page: Page, email: str, password: str) -> bool:
        """
        Perform login to SEI v4.

        Standard v4 login flow with Bootstrap validation.
        """
        selectors = self.get_login_selectors()

        try:
            # Wait for login form
            page.wait_for_selector(selectors["email"], timeout=10000)

            # Fill credentials
            page.fill(selectors["email"], email)
            page.fill(selectors["password"], password)

            # Submit
            page.click(selectors["submit"])

            # Wait for navigation
            page.wait_for_load_state("networkidle", timeout=30000)

            # Check for errors
            error_selector = selectors.get("error")
            if error_selector and page.locator(error_selector).count() > 0:
                error_msg = page.locator(error_selector).text_content()
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

        v4 has consistent user menu in navbar.
        """
        return page.locator("#lnkUsuarioSistema, .usuario-logado, #divUsuario").count() > 0

    # ==================== Process Discovery ====================

    def get_process_list_url(self) -> str:
        """
        Get URL for process list page.

        v4 uses controller pattern.
        """
        return "/controlador.php?acao=procedimento_controlar"

    @abstractmethod
    def extract_process_list(self, page: Page) -> Dict:
        """
        Extract process list - must be implemented by version-specific scraper.

        v4 family has consistent table structure but minor variations.
        """
        pass

    # ==================== Link Validation ====================

    def get_access_type_selectors(self) -> Dict[str, str]:
        """
        Selectors to determine access type in v4.

        Common across v4 family.
        """
        return {
            "integral_indicator": "#divArvoreAcoes",
            "parcial_indicator": ".acesso-parcial, .visualizacao-parcial",
            "restricted_msg": "#divMensagemAcessoRestrito"
        }

    # ==================== Authority Extraction ====================

    def get_authority_selectors(self) -> Dict[str, str]:
        """
        Selectors for authority field in v4.

        Typically in process information panel.
        """
        return {
            "authority_field": "#txtAutoridade, [name='txtAutoridade']",
            "authority_label": "label:has-text('Autoridade')",
            "info_panel": "#divInformacao, .processo-info"
        }

    # ==================== Document Management ====================

    def get_document_list_selectors(self) -> Dict[str, str]:
        """
        Selectors for document list in v4.

        v4 uses data tables with consistent structure.
        """
        return {
            "document_table": "#tblDocumentos, .tabela-documentos",
            "document_rows": "tr.documento-row",
            "document_number": "td.doc-numero",
            "document_type": "td.doc-tipo",
            "document_date": "td.doc-data"
        }

    # ==================== Utility Methods ====================

    def get_system_url(self) -> str:
        """Get base URL - should be set by configuration."""
        return getattr(self, "_system_url", "https://sei.example.com")

    def wait_for_page_load(self, page: Page, timeout: int = 30000) -> bool:
        """
        Wait for page to load.

        v4 has better loading indicators.
        """
        try:
            # Wait for network idle
            page.wait_for_load_state("networkidle", timeout=timeout)

            # Wait for v4-specific loading indicator to disappear
            page.wait_for_selector(".loading, #divCarregando", state="hidden", timeout=5000)

            return True
        except Exception:
            # Loading indicator might not exist, continue anyway
            return True

    # Placeholder implementations for abstract methods
    # These should be overridden by specific version scrapers

    def validate_link(self, page: Page, link: str) -> Dict:
        raise NotImplementedError("Must be implemented by version-specific scraper")

    def extract_authority(self, page: Page) -> Optional[str]:
        raise NotImplementedError("Must be implemented by version-specific scraper")

    def extract_documents(self, page: Page) -> Dict:
        raise NotImplementedError("Must be implemented by version-specific scraper")

    def get_document_download_url(self, document_link: str) -> str:
        raise NotImplementedError("Must be implemented by version-specific scraper")

    def download_document(self, page: Page, document_link: str, output_path: str) -> bool:
        raise NotImplementedError("Must be implemented by version-specific scraper")
