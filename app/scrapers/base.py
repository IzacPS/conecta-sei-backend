"""
ConectaSEI v2.0 - Base Scraper Interface

This module defines the abstract base class for all SEI scrapers.
All version-specific scrapers must inherit from SEIScraperBase and implement
the required abstract methods.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from playwright.sync_api import Page


class SEIScraperBase(ABC):
    """
    Abstract base class for all SEI scrapers.

    This class defines the interface that all SEI version scrapers must implement.
    Each scraper plugin represents a specific version of the SEI system and knows
    how to navigate and extract data from that version.

    Attributes:
        VERSION: Semantic version string (e.g., "4.2.0")
        VERSION_RANGE: Semver range this scraper supports (e.g., ">=4.2.0 <4.3.0")
        FAMILY: SEI version family (e.g., "v4", "v3")
    """

    VERSION: str = "0.0.0"
    VERSION_RANGE: str = ">=0.0.0"
    FAMILY: str = "unknown"

    @abstractmethod
    def get_version_info(self) -> Dict[str, str]:
        """
        Get version information for this scraper.

        Returns:
            Dict with keys: 'version', 'version_range', 'family', 'description'
        """
        pass

    @abstractmethod
    def detect_version(self, page: Page) -> Optional[str]:
        """
        Attempt to detect if this scraper is compatible with the current SEI page.

        This method should check page elements, meta tags, or other indicators
        to determine if the loaded SEI system matches this scraper's version.

        Args:
            page: Playwright Page object with SEI system loaded

        Returns:
            Version string if detected (e.g., "4.2.0"), None if not compatible
        """
        pass

    # ==================== Authentication ====================

    @abstractmethod
    def get_login_selectors(self) -> Dict[str, str]:
        """
        Get CSS selectors for login form elements.

        Returns:
            Dict with keys: 'email', 'password', 'submit', 'error' (optional)
        """
        pass

    @abstractmethod
    def login(self, page: Page, email: str, password: str) -> bool:
        """
        Perform login to SEI system.

        Args:
            page: Playwright Page object
            email: User email/username
            password: User password

        Returns:
            True if login successful, False otherwise

        Raises:
            Exception: If login fails with error message
        """
        pass

    @abstractmethod
    def is_logged_in(self, page: Page) -> bool:
        """
        Check if user is currently logged in.

        Args:
            page: Playwright Page object

        Returns:
            True if logged in, False otherwise
        """
        pass

    # ==================== Process Discovery (Stage 1) ====================

    @abstractmethod
    def get_process_list_url(self) -> str:
        """
        Get the URL for the process list page.

        Returns:
            URL string (may be relative or absolute)
        """
        pass

    @abstractmethod
    def extract_process_list(self, page: Page) -> Dict[str, Dict[str, Any]]:
        """
        Extract list of all visible processes from the process list page.

        This is Stage 1 of the pipeline: fast discovery of process numbers
        and their access links without opening individual processes.

        Args:
            page: Playwright Page object on the process list page

        Returns:
            Dict mapping process_number to process data:
            {
                "numero_processo": str,
                "links": Dict[str, Dict],  # {link_url: {"status": "desconhecido", "tipo": None}}
                "unidade": str (optional),
            }
        """
        pass

    # ==================== Link Validation & Authority (Stage 2) ====================

    @abstractmethod
    def validate_link(self, page: Page, link: str) -> Dict[str, Any]:
        """
        Navigate to process link and validate access type.

        This is Stage 2 of the pipeline: determines if link is valid and
        whether access is "integral" (full) or "parcial" (partial).
        Also opportunistically collects authority data.

        Args:
            page: Playwright Page object
            link: Process link URL to validate

        Returns:
            Dict with keys:
                - "valid": bool - whether link is accessible
                - "tipo_acesso": str - "integral" or "parcial"
                - "autoridade": str (optional) - authority if found
                - "error": str (optional) - error message if invalid
        """
        pass

    @abstractmethod
    def get_access_type_selectors(self) -> Dict[str, str]:
        """
        Get CSS selectors to determine access type.

        Returns:
            Dict with keys identifying integral vs parcial access elements
        """
        pass

    # ==================== Authority Collection ====================

    @abstractmethod
    def get_authority_selectors(self) -> Dict[str, str]:
        """
        Get CSS selectors for extracting authority information.

        Returns:
            Dict with selectors for authority field
        """
        pass

    @abstractmethod
    def extract_authority(self, page: Page) -> Optional[str]:
        """
        Extract authority (Autoridade) from process page.

        This is called opportunistically when process is already open
        to avoid redundant navigation.

        Args:
            page: Playwright Page object on process page

        Returns:
            Authority string if found, None otherwise
        """
        pass

    # ==================== Document Discovery (Stage 3) ====================

    @abstractmethod
    def get_document_list_selectors(self) -> Dict[str, str]:
        """
        Get CSS selectors for document list elements.

        Returns:
            Dict with selectors for document table/list
        """
        pass

    @abstractmethod
    def extract_documents(self, page: Page) -> Dict[str, Dict[str, Any]]:
        """
        Extract all documents from process page.

        This is Stage 3 of the pipeline: discovers new or updated documents.
        Should only be called if should_process_documents() returns True.

        Args:
            page: Playwright Page object on process page

        Returns:
            Dict mapping document_number to document data:
            {
                "numero": str,
                "tipo": str,
                "data": str,
                "link": str,
                "tamanho": str (optional),
                "assinantes": List[str] (optional),
            }
        """
        pass

    # ==================== Document Download (Stage 4) ====================

    @abstractmethod
    def get_document_download_url(self, document_link: str) -> str:
        """
        Convert document view link to download URL.

        Args:
            document_link: Link from document list

        Returns:
            Direct download URL for PDF
        """
        pass

    @abstractmethod
    def download_document(
        self,
        page: Page,
        document_link: str,
        output_path: str
    ) -> bool:
        """
        Download a document and save to output_path.

        Handles both PDF documents and HTML documents that need conversion.

        Args:
            page: Playwright Page object
            document_link: Link to document
            output_path: Where to save the downloaded file

        Returns:
            True if download successful, False otherwise
        """
        pass

    # ==================== Utility Methods ====================

    @abstractmethod
    def get_system_url(self) -> str:
        """
        Get the base URL for the SEI system.

        Returns:
            Base URL (e.g., "https://sei.example.com")
        """
        pass

    @abstractmethod
    def wait_for_page_load(self, page: Page, timeout: int = 30000) -> bool:
        """
        Wait for page to fully load.

        Args:
            page: Playwright Page object
            timeout: Maximum wait time in milliseconds

        Returns:
            True if page loaded, False if timeout
        """
        pass

    def get_scraper_name(self) -> str:
        """
        Get human-readable name for this scraper.

        Returns:
            Name string (e.g., "SEI v4.2.0 Scraper")
        """
        return f"SEI {self.FAMILY} {self.VERSION} Scraper"

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} version={self.VERSION} family={self.FAMILY}>"
