"""
ConectaSEI v2.0 - Scraper Plugin Registry

This module manages the registration and discovery of scraper plugins.
It maintains a central registry of all available scrapers and provides
methods to query and retrieve them by version or compatibility.
"""

from typing import Dict, List, Optional, Type
from app.scrapers.base import SEIScraperBase
import logging

logger = logging.getLogger(__name__)


class ScraperRegistry:
    """
    Central registry for all SEI scraper plugins.

    This singleton class maintains a registry of all available scraper
    implementations and provides methods to query them by version,
    family, or compatibility requirements.
    """

    _instance: Optional['ScraperRegistry'] = None
    _registry: Dict[str, Type[SEIScraperBase]] = {}
    _family_index: Dict[str, List[str]] = {}

    def __new__(cls):
        """Singleton pattern - only one registry instance exists."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        """Initialize the registry."""
        self._registry = {}
        self._family_index = {}
        logger.info("ScraperRegistry initialized")

    def register(
        self,
        scraper_class: Type[SEIScraperBase],
        version: Optional[str] = None
    ) -> None:
        """
        Register a scraper plugin.

        Args:
            scraper_class: The scraper class to register (must inherit from SEIScraperBase)
            version: Optional version override (uses scraper_class.VERSION if not provided)

        Raises:
            TypeError: If scraper_class doesn't inherit from SEIScraperBase
            ValueError: If version is already registered
        """
        if not issubclass(scraper_class, SEIScraperBase):
            raise TypeError(
                f"{scraper_class.__name__} must inherit from SEIScraperBase"
            )

        version_key = version or scraper_class.VERSION
        family = scraper_class.FAMILY

        if version_key in self._registry:
            existing = self._registry[version_key]
            logger.warning(
                f"Scraper for version {version_key} already registered "
                f"({existing.__name__}), overwriting with {scraper_class.__name__}"
            )

        self._registry[version_key] = scraper_class

        # Update family index
        if family not in self._family_index:
            self._family_index[family] = []
        if version_key not in self._family_index[family]:
            self._family_index[family].append(version_key)

        logger.info(
            f"Registered scraper: {scraper_class.__name__} "
            f"(version={version_key}, family={family})"
        )

    def unregister(self, version: str) -> bool:
        """
        Unregister a scraper by version.

        Args:
            version: Version string to unregister

        Returns:
            True if scraper was unregistered, False if not found
        """
        if version not in self._registry:
            return False

        scraper_class = self._registry[version]
        family = scraper_class.FAMILY

        del self._registry[version]

        # Update family index
        if family in self._family_index:
            self._family_index[family].remove(version)
            if not self._family_index[family]:
                del self._family_index[family]

        logger.info(f"Unregistered scraper for version {version}")
        return True

    def get(self, version: str) -> Optional[Type[SEIScraperBase]]:
        """
        Get scraper class by exact version match.

        Args:
            version: Exact version string (e.g., "4.2.0")

        Returns:
            Scraper class if found, None otherwise
        """
        return self._registry.get(version)

    def get_by_family(self, family: str) -> List[Type[SEIScraperBase]]:
        """
        Get all scrapers for a specific family.

        Args:
            family: Family name (e.g., "v4", "v3")

        Returns:
            List of scraper classes in that family
        """
        versions = self._family_index.get(family, [])
        return [self._registry[v] for v in versions]

    def get_all(self) -> Dict[str, Type[SEIScraperBase]]:
        """
        Get all registered scrapers.

        Returns:
            Dict mapping version strings to scraper classes
        """
        return self._registry.copy()

    def list_versions(self) -> List[str]:
        """
        Get list of all registered versions.

        Returns:
            List of version strings
        """
        return list(self._registry.keys())

    def list_families(self) -> List[str]:
        """
        Get list of all available families.

        Returns:
            List of family names
        """
        return list(self._family_index.keys())

    def find_compatible(self, target_version: str) -> List[Type[SEIScraperBase]]:
        """
        Find scrapers compatible with a target version.

        This performs a simple prefix match. For example:
        - target_version="4.2" matches "4.2.0", "4.2.1", etc.
        - target_version="4" matches "4.0.0", "4.2.0", etc.

        Args:
            target_version: Version to match against

        Returns:
            List of compatible scraper classes, sorted by version (descending)
        """
        compatible = []
        for version, scraper_class in self._registry.items():
            if version.startswith(target_version):
                compatible.append(scraper_class)

        # Sort by version descending (newest first)
        compatible.sort(
            key=lambda s: s.VERSION,
            reverse=True
        )
        return compatible

    def get_latest(self, family: Optional[str] = None) -> Optional[Type[SEIScraperBase]]:
        """
        Get the latest scraper, optionally filtered by family.

        Args:
            family: Optional family filter (e.g., "v4")

        Returns:
            Latest scraper class, or None if no scrapers registered
        """
        scrapers = self.get_by_family(family) if family else list(self._registry.values())

        if not scrapers:
            return None

        # Sort by version descending
        scrapers.sort(key=lambda s: s.VERSION, reverse=True)
        return scrapers[0]

    def clear(self) -> None:
        """
        Clear all registered scrapers.

        Warning: This is mainly for testing. Use with caution.
        """
        count = len(self._registry)
        self._registry.clear()
        self._family_index.clear()
        logger.warning(f"Registry cleared ({count} scrapers removed)")

    def __len__(self) -> int:
        """Return number of registered scrapers."""
        return len(self._registry)

    def __contains__(self, version: str) -> bool:
        """Check if version is registered."""
        return version in self._registry

    def __repr__(self) -> str:
        return f"<ScraperRegistry scrapers={len(self._registry)} families={len(self._family_index)}>"


# Decorator for easy registration
def register_scraper(version: Optional[str] = None):
    """
    Decorator to automatically register a scraper class.

    Usage:
        @register_scraper()
        class SEIv4_2_0(SEIv4Base):
            VERSION = "4.2.0"
            ...

    Args:
        version: Optional version override
    """
    def decorator(scraper_class: Type[SEIScraperBase]):
        registry = ScraperRegistry()
        registry.register(scraper_class, version)
        return scraper_class
    return decorator


# Singleton instance accessor
def get_registry() -> ScraperRegistry:
    """
    Get the global scraper registry instance.

    Returns:
        ScraperRegistry singleton
    """
    return ScraperRegistry()
