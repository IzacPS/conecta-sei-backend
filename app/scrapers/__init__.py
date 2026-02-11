# ConectaSEI v2.0 - Scraper plugin package
#
# Import built-in scrapers so they register with the registry at startup.
# The registry is in-memory (not the database); list via GET /pipelines/available-versions.

from app.scrapers.sei_v4.v4_2_0 import SEIv4_2_0  # noqa: F401 - registers SEI 4.2.0

__all__ = ["SEIv4_2_0"]
