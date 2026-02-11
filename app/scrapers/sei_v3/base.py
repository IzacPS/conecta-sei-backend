"""
ConectaSEI v2.0 - SEI v3 Family Base Scraper

Base class for all SEI v3.x scrapers.
Implements common functionality shared across v3 family.
"""

from abc import abstractmethod
from typing import Dict, Optional
from playwright.sync_api import Page
from app.scrapers.base import SEIScraperBase


class SEIv3Base(SEIScraperBase):
    """
    Base scraper for SEI v3.x family.

    All v3-specific scrapers should inherit from this class.
    This class implements common v3 behavior while allowing
    version-specific overrides.
    """

    FAMILY = "v3"
    VERSION = "3.0.0"  # Override in subclasses
    VERSION_RANGE = ">=3.0.0 <4.0.0"

    def get_version_info(self) -> Dict[str, str]:
        """Get version information for this scraper."""
        return {
            "version": self.VERSION,
            "version_range": self.VERSION_RANGE,
            "family": self.FAMILY,
            "description": f"SEI v3 Family Scraper (v{self.VERSION})"
        }

    def detect_version(self, page: Page) -> Optional[str]:
        """
        Detect if page is SEI v3.

        Common detection strategies for v3:
        - Check meta tags
        - Check footer version string
        - Check specific v3 CSS classes
        """
        try:
            # Strategy 1: Check meta tag
            meta_version = page.locator('meta[name="sei-version"]').get_attribute("content")
            if meta_version and meta_version.startswith("3."):
                return meta_version

            # Strategy 2: Check footer
            footer_text = page.locator("footer, .rodape").text_content()
            if footer_text and "SEI 3." in footer_text:
                # Extract version from footer
                import re
                match = re.search(r"SEI[- ]?(3\.\d+\.\d+)", footer_text)
                if match:
                    return match.group(1)

            # Strategy 3: Check v3-specific classes
            v3_indicators = page.locator(".sei-v3-container, #divSEIv3").count()
            if v3_indicators > 0:
                return self.VERSION  # Return generic v3 version

        except Exception:
            pass

        return None

    # ==================== Authentication ====================

    def get_login_selectors(self) -> Dict[str, str]:
        """
        Common login selectors for SEI v3.

        Override if specific version has different selectors.
        """
        return {
            "email": "#txtUsuario",
            "password": "#pwdSenha",
            "submit": "#sbmLogin",
            "error": "#divErro, .erro"
        }

    def login(self, page: Page, email: str, password: str) -> bool:
        """
        Perform login to SEI v3.

        Standard v3 login flow.
        """
        selectors = self.get_login_selectors()

        try:
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

            return True

        except Exception as e:
            raise Exception(f"Login error: {str(e)}")

    def is_logged_in(self, page: Page) -> bool:
        """Check if user is logged in."""
        # v3 typically has user menu when logged in
        return page.locator("#divMenuUsuario, .usuario-logado").count() > 0

    # ==================== Process Discovery ====================

    def get_process_list_url(self) -> str:
        """Get URL for process list page."""
        return "/controlador.php?acao=procedimento_controlar"

    @abstractmethod
    def extract_process_list(self, page: Page) -> Dict:
        """
        Extract process list - must be implemented by version-specific scraper.

        v3 family has variations in table structure across versions.
        """
        pass

    # ==================== Other Methods ====================

    def get_system_url(self) -> str:
        """Get base URL - should be set by configuration."""
        # This will be set by InstitutionService based on institution config
        return getattr(self, "_system_url", "https://sei.example.com")

    def wait_for_page_load(self, page: Page, timeout: int = 30000) -> bool:
        """Wait for page to load."""
        try:
            page.wait_for_load_state("networkidle", timeout=timeout)
            return True
        except Exception:
            return False

    # Placeholder implementations for abstract methods
    # These should be overridden by specific version scrapers

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
