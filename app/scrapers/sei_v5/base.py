"""
ConectaSEI v2.0 - SEI v5 Family Base Scraper

Base class for all SEI v5.x scrapers.
SEI v5 represents next-generation architecture with modern web standards.
"""

from abc import abstractmethod
from typing import Dict, Optional
from playwright.sync_api import Page
from app.scrapers.base import SEIScraperBase


class SEIv5Base(SEIScraperBase):
    """
    Base scraper for SEI v5.x family.

    SEI v5 expected features:
    - Modern SPA architecture (possibly React/Vue)
    - REST API backend
    - WebSocket support for real-time updates
    - Improved accessibility (WCAG 2.1)
    - Mobile-first responsive design
    - Enhanced security features
    """

    FAMILY = "v5"
    VERSION = "5.0.0"  # Override in subclasses
    VERSION_RANGE = ">=5.0.0 <6.0.0"

    def get_version_info(self) -> Dict[str, str]:
        """Get version information for this scraper."""
        return {
            "version": self.VERSION,
            "version_range": self.VERSION_RANGE,
            "family": self.FAMILY,
            "description": f"SEI v5 Family Scraper (v{self.VERSION})"
        }

    def detect_version(self, page: Page) -> Optional[str]:
        """
        Detect if page is SEI v5.

        v5 detection strategies (to be updated when v5 is released):
        - Check data-sei-version attribute
        - Check API version endpoint
        - Check modern SPA indicators
        """
        try:
            # Strategy 1: Check data attribute
            version_attr = page.locator('[data-sei-version]').get_attribute("data-sei-version")
            if version_attr and version_attr.startswith("5."):
                return version_attr

            # Strategy 2: Check meta tag
            meta_version = page.locator('meta[name="sei-version"]').get_attribute("content")
            if meta_version and meta_version.startswith("5."):
                return meta_version

            # Strategy 3: Check JavaScript global
            js_version = page.evaluate("window.SEI_VERSION")
            if js_version and str(js_version).startswith("5."):
                return str(js_version)

            # Strategy 4: API version check (if v5 exposes API)
            try:
                api_response = page.evaluate("""
                    fetch('/api/version')
                        .then(r => r.json())
                        .then(d => d.version)
                """)
                if api_response and api_response.startswith("5."):
                    return api_response
            except Exception:
                pass

        except Exception:
            pass

        return None

    # ==================== Authentication ====================

    def get_login_selectors(self) -> Dict[str, str]:
        """
        Login selectors for SEI v5.

        Note: These are placeholder selectors.
        Update when v5 is actually released.
        """
        return {
            "email": "#email, [name='email']",
            "password": "#password, [name='password']",
            "submit": "button[type='submit']",
            "error": ".alert-error, [role='alert']"
        }

    def login(self, page: Page, email: str, password: str) -> bool:
        """
        Perform login to SEI v5.

        v5 may use modern authentication (OAuth, SSO, etc).
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

            # Wait for SPA navigation
            page.wait_for_load_state("networkidle", timeout=30000)

            # Check for errors
            if page.locator(selectors.get("error", "")).count() > 0:
                error_msg = page.locator(selectors["error"]).text_content()
                raise Exception(f"Login failed: {error_msg}")

            if not self.is_logged_in(page):
                raise Exception("Login verification failed")

            return True

        except Exception as e:
            raise Exception(f"Login error: {str(e)}")

    def is_logged_in(self, page: Page) -> bool:
        """
        Check if user is logged in.

        v5 may store auth state in localStorage/sessionStorage.
        """
        # Check DOM for user indicator
        if page.locator("[data-logged-in='true'], .user-authenticated").count() > 0:
            return True

        # Check JavaScript state (SPA)
        try:
            is_logged = page.evaluate("window.__SEI_STATE__?.user?.authenticated || false")
            return bool(is_logged)
        except Exception:
            return False

    # ==================== Process Discovery ====================

    def get_process_list_url(self) -> str:
        """
        Get URL for process list.

        v5 may use REST API endpoints instead of PHP controllers.
        """
        return "/processos"  # SPA route

    @abstractmethod
    def extract_process_list(self, page: Page) -> Dict:
        """
        Extract process list - must be implemented by version-specific scraper.

        v5 may return JSON from API instead of scraping HTML.
        """
        pass

    # ==================== Utility Methods ====================

    def get_system_url(self) -> str:
        """Get base URL."""
        return getattr(self, "_system_url", "https://sei.example.com")

    def wait_for_page_load(self, page: Page, timeout: int = 30000) -> bool:
        """
        Wait for page to load.

        v5 SPA may need different waiting strategy.
        """
        try:
            # Wait for network idle
            page.wait_for_load_state("networkidle", timeout=timeout)

            # Wait for SPA hydration (if applicable)
            page.evaluate("document.readyState === 'complete'")

            return True
        except Exception:
            return True

    # Abstract methods - must be implemented by specific versions
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
