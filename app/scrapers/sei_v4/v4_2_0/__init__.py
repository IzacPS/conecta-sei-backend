# ConectaSEI v2.0 - SEI v4.2.0 Scraper

"""
SEI v4.2.0 Scraper

This is the first concrete implementation of a version-specific scraper.
It inherits from SEIv4Base and implements SEI v4.2.0 specific behavior.

This scraper was migrated from the legacy codebase:
- utils.py (login logic)
- get_process_update.py (process discovery)
- get_process_links_status.py (link validation, authority)
- get_process_docs_update.py (document extraction)
"""

from .scraper import SEIv4_2_0

__all__ = ["SEIv4_2_0"]

__version__ = "4.2.0"
