"""
ConectaSEI v2.0 - SEI v2 Family Base Scraper (Legacy)

Base class for all SEI v2.x scrapers.
SEI v2 is a legacy version - most institutions have migrated to v3+.
"""

from abc import abstractmethod
from typing import Dict, Optional
from playwright.sync_api import Page
from app.scrapers.base import SEIScraperBase


class SEIv2Base(SEIScraperBase):
    """
    Base scraper for SEI v2.x family (Legacy).

    SEI v2 characteristics:
    - Older UI without Bootstrap
    - Table-based layouts
    - Limited JavaScript
    - Basic AJAX support
    """

    FAMILY = "v2"
    VERSION = "2.0.0"  # Override in subclasses
    VERSION_RANGE = ">=2.0.0 <3.0.0"

    def get_version_info(self) -> Dict[str, str]:
        """Get version information for this scraper."""
        return {
            "version": self.VERSION,
            "version_range": self.VERSION_RANGE,
            "family": self.FAMILY,
            "description": f"SEI v2 Family Scraper (Legacy v{self.VERSION})"
        }

    def detect_version(self, page: Page) -> Optional[str]:
        """Detect if page is SEI v2."""
        try:
            # v2 specific detection
            footer_text = page.locator("footer, #rodape").text_content()
            if footer_text and "SEI 2." in footer_text:
                import re
                match = re.search(r"SEI[- ]?(2\.\d+\.\d+)", footer_text)
                if match:
                    return match.group(1)

            # Check v2-specific classes
            v2_indicators = page.locator("#infraMenuSistema, .sei-v2").count()
            if v2_indicators > 0:
                return self.VERSION

        except Exception:
            pass

        return None

    def get_login_selectors(self) -> Dict[str, str]:
        """Common login selectors for SEI v2."""
        return {
            "email": "#txtUsuario",
            "password": "#pwdSenha",
            "submit": "#Acessar",
            "error": "#divErro"
        }

    def login(self, page: Page, email: str, password: str) -> bool:
        """Perform login to SEI v2."""
        selectors = self.get_login_selectors()

        try:
            page.fill(selectors["email"], email)
            page.fill(selectors["password"], password)
            page.click(selectors["submit"])
            page.wait_for_load_state("networkidle", timeout=30000)

            if page.locator(selectors.get("error", "")).count() > 0:
                raise Exception("Login failed")

            return True
        except Exception as e:
            raise Exception(f"Login error: {str(e)}")

    def is_logged_in(self, page: Page) -> bool:
        """Check if user is logged in."""
        return page.locator("#lnkInfraSair, #lnkSair").count() > 0

    def get_process_list_url(self) -> str:
        """Get URL for process list page."""
        return "/sei/controlador.php?acao=procedimento_controlar"

    def get_system_url(self) -> str:
        """Get base URL."""
        return getattr(self, "_system_url", "https://sei.example.com")

    def wait_for_page_load(self, page: Page, timeout: int = 30000) -> bool:
        """Wait for page to load."""
        try:
            page.wait_for_load_state("networkidle", timeout=timeout)
            return True
        except Exception:
            return False

    # Abstract methods - must be implemented by specific versions
    @abstractmethod
    def extract_process_list(self, page: Page) -> Dict:
        pass

    def validate_link(self, page: Page, link: str) -> Dict:
        raise NotImplementedError("Must be implemented by version-specific scraper")

    def get_access_type_selectors(self) -> Dict[str, str]:
        raise NotImplementedError("Must be implemented by version-specific scraper")

    def get_authority_selectors(self) -> Dict[str, str]:
        raise NotImplementedError("Must be implemented by version-specific scraper")

    def extract_authority(self, page: Page) -> Optional[str]:
        raise NotImplementedError("Must be implemented by version-specific scraper")

    def get_document_list_selectors(self) -> Dict[str, str]:
        raise NotImplementedError("Must be implemented by version-specific scraper")

    def extract_documents(self, page: Page) -> Dict:
        raise NotImplementedError("Must be implemented by version-specific scraper")

    def get_document_download_url(self, document_link: str) -> str:
        raise NotImplementedError("Must be implemented by version-specific scraper")

    def download_document(self, page: Page, document_link: str, output_path: str) -> bool:
        raise NotImplementedError("Must be implemented by version-specific scraper")
