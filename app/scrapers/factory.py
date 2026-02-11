"""
ConectaSEI v2.0 - Scraper Factory

This module provides factory methods for creating scraper instances.
It handles version detection, compatibility checking, and fallback strategies.
"""

from typing import Optional, List
from playwright.sync_api import Page
from app.scrapers.base import SEIScraperBase
from app.scrapers.registry import get_registry
import logging

logger = logging.getLogger(__name__)


class ScraperFactory:
    """
    Factory for creating SEI scraper instances.

    This class provides various methods to create scrapers:
    - By exact version
    - By auto-detection
    - With fallback strategies
    - By family preference
    """

    @staticmethod
    def create(version: str) -> Optional[SEIScraperBase]:
        """
        Create a scraper instance for a specific version.

        Args:
            version: Exact version string (e.g., "4.2.0")

        Returns:
            Scraper instance if version found, None otherwise

        Example:
            scraper = ScraperFactory.create("4.2.0")
            if scraper:
                scraper.login(page, email, password)
        """
        registry = get_registry()
        scraper_class = registry.get(version)

        if scraper_class is None:
            logger.warning(f"No scraper found for version {version}")
            return None

        logger.info(f"Created scraper for version {version}")
        return scraper_class()

    @staticmethod
    def create_by_family(family: str, prefer_latest: bool = True) -> Optional[SEIScraperBase]:
        """
        Create a scraper from a specific family.

        Args:
            family: Family name (e.g., "v4", "v3")
            prefer_latest: If True, returns latest version in family

        Returns:
            Scraper instance, or None if family not found

        Example:
            scraper = ScraperFactory.create_by_family("v4")
        """
        registry = get_registry()
        scrapers = registry.get_by_family(family)

        if not scrapers:
            logger.warning(f"No scrapers found for family {family}")
            return None

        if prefer_latest:
            # Sort by version and get the latest
            scrapers.sort(key=lambda s: s.VERSION, reverse=True)

        scraper_class = scrapers[0]
        logger.info(f"Created scraper from family {family}: {scraper_class.VERSION}")
        return scraper_class()

    @staticmethod
    def create_compatible(target_version: str) -> Optional[SEIScraperBase]:
        """
        Create a scraper compatible with the target version.

        Uses prefix matching to find compatible scrapers.
        Returns the newest compatible version.

        Args:
            target_version: Version to match (e.g., "4.2" matches "4.2.0", "4.2.1")

        Returns:
            Scraper instance, or None if no compatible version found

        Example:
            scraper = ScraperFactory.create_compatible("4.2")
        """
        registry = get_registry()
        compatible = registry.find_compatible(target_version)

        if not compatible:
            logger.warning(f"No compatible scraper found for version {target_version}")
            return None

        scraper_class = compatible[0]  # Already sorted newest first
        logger.info(
            f"Created compatible scraper for {target_version}: "
            f"{scraper_class.VERSION}"
        )
        return scraper_class()

    @staticmethod
    def auto_detect(page: Page, families: Optional[List[str]] = None) -> Optional[SEIScraperBase]:
        """
        Auto-detect SEI version from page and create appropriate scraper.

        Tries each registered scraper's detect_version() method until one succeeds.
        Can be limited to specific families for faster detection.

        Args:
            page: Playwright Page object with SEI system loaded
            families: Optional list of families to check (e.g., ["v4"])

        Returns:
            Scraper instance if detection successful, None otherwise

        Example:
            page.goto("https://sei.example.com")
            scraper = ScraperFactory.auto_detect(page)
            if scraper:
                print(f"Detected version: {scraper.VERSION}")
        """
        registry = get_registry()

        # Get scrapers to test
        if families:
            scrapers_to_test = []
            for family in families:
                scrapers_to_test.extend(registry.get_by_family(family))
        else:
            scrapers_to_test = list(registry.get_all().values())

        if not scrapers_to_test:
            logger.error("No scrapers registered for auto-detection")
            return None

        # Sort by version descending (test newest first)
        scrapers_to_test.sort(key=lambda s: s.VERSION, reverse=True)

        logger.info(f"Auto-detecting version from {len(scrapers_to_test)} scrapers...")

        for scraper_class in scrapers_to_test:
            try:
                scraper = scraper_class()
                detected_version = scraper.detect_version(page)

                if detected_version:
                    logger.info(
                        f"Version detected: {detected_version} "
                        f"using {scraper_class.__name__}"
                    )
                    return scraper

            except Exception as e:
                logger.debug(
                    f"Detection failed for {scraper_class.__name__}: {e}"
                )
                continue

        logger.warning("Auto-detection failed - no compatible scraper found")
        return None

    @staticmethod
    def create_with_fallback(
        page: Page,
        preferred_version: Optional[str] = None,
        fallback_family: Optional[str] = None
    ) -> Optional[SEIScraperBase]:
        """
        Create scraper with fallback strategy.

        Strategy:
        1. Try exact version if provided
        2. Try auto-detection
        3. Try fallback family (latest version)

        Args:
            page: Playwright Page object with SEI system loaded
            preferred_version: Try this version first
            fallback_family: Use this family as last resort

        Returns:
            Scraper instance, or None if all strategies fail

        Example:
            scraper = ScraperFactory.create_with_fallback(
                page,
                preferred_version="4.2.0",
                fallback_family="v4"
            )
        """
        # Strategy 1: Try exact version
        if preferred_version:
            scraper = ScraperFactory.create(preferred_version)
            if scraper:
                logger.info(f"Using preferred version: {preferred_version}")
                return scraper
            logger.debug(f"Preferred version {preferred_version} not found")

        # Strategy 2: Auto-detect
        logger.info("Attempting auto-detection...")
        scraper = ScraperFactory.auto_detect(page)
        if scraper:
            return scraper

        # Strategy 3: Fallback to family
        if fallback_family:
            logger.info(f"Falling back to family: {fallback_family}")
            scraper = ScraperFactory.create_by_family(fallback_family)
            if scraper:
                return scraper

        logger.error("All creation strategies failed")
        return None

    @staticmethod
    def create_with_retry(
        page: Page,
        max_attempts: int = 3,
        preferred_version: Optional[str] = None
    ) -> Optional[SEIScraperBase]:
        """
        Create scraper with retry logic for auto-detection.

        Sometimes page loads slowly or detection can be flaky.
        This method retries auto-detection multiple times.

        Args:
            page: Playwright Page object with SEI system loaded
            max_attempts: Maximum number of detection attempts
            preferred_version: Try this version first

        Returns:
            Scraper instance, or None if all attempts fail

        Example:
            scraper = ScraperFactory.create_with_retry(page, max_attempts=3)
        """
        # Try preferred version first
        if preferred_version:
            scraper = ScraperFactory.create(preferred_version)
            if scraper:
                return scraper

        # Retry auto-detection
        for attempt in range(1, max_attempts + 1):
            logger.info(f"Auto-detection attempt {attempt}/{max_attempts}")

            try:
                scraper = ScraperFactory.auto_detect(page)
                if scraper:
                    return scraper

                # Wait a bit before retry
                if attempt < max_attempts:
                    page.wait_for_timeout(1000)

            except Exception as e:
                logger.warning(f"Attempt {attempt} failed: {e}")

        logger.error(f"Failed to create scraper after {max_attempts} attempts")
        return None

    @staticmethod
    def list_available() -> List[str]:
        """
        List all available scraper versions.

        Returns:
            List of version strings

        Example:
            versions = ScraperFactory.list_available()
            print(f"Available: {', '.join(versions)}")
        """
        registry = get_registry()
        return registry.list_versions()

    @staticmethod
    def get_info(version: str) -> Optional[dict]:
        """
        Get information about a specific scraper version.

        Args:
            version: Version string

        Returns:
            Dict with version info, or None if not found

        Example:
            info = ScraperFactory.get_info("4.2.0")
            print(info["description"])
        """
        scraper = ScraperFactory.create(version)
        if scraper:
            return scraper.get_version_info()
        return None
