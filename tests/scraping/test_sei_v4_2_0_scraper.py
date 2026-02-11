"""
Testes do scraper SEI v4.2.0 usando fixtures HTML (sem SEI ao vivo).

- Testes unitários: _normalize_link (sem browser).
- Testes com Playwright: detect_version e extract_process_list usando
  tests/fixtures/sei_v4/*.html.

Executar: pytest tests/scraping/ -v
"""

import os
import pytest
from pathlib import Path

# Fixtures path (relativo à raiz do projeto)
TESTS_DIR = Path(__file__).resolve().parent.parent
FIXTURES_SEI_V4 = TESTS_DIR / "fixtures" / "sei_v4"


# ---------------------------------------------------------------------------
# Unit (sem Playwright)
# ---------------------------------------------------------------------------

class TestSEIv4_2_0_normalize_link:
    """Testes unitários de _normalize_link (regex do id_procedimento_externo)."""

    def test_normalize_link_extracts_id(self):
        from app.scrapers.sei_v4.v4_2_0.scraper import SEIv4_2_0
        scraper = SEIv4_2_0()
        assert scraper._normalize_link("?acao=procedimento_visualizar&id_procedimento_externo=1001") == "1001"
        assert scraper._normalize_link("controlador.php?id_procedimento_externo=1002&outro=1") == "1002"

    def test_normalize_link_returns_none_when_missing(self):
        from app.scrapers.sei_v4.v4_2_0.scraper import SEIv4_2_0
        scraper = SEIv4_2_0()
        assert scraper._normalize_link("") is None
        assert scraper._normalize_link("http://sei.gov.br/sem_id") is None


# ---------------------------------------------------------------------------
# Scraping com Playwright + fixtures HTML
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def process_list_html():
    path = FIXTURES_SEI_V4 / "process_list.html"
    if not path.exists():
        pytest.skip(f"Fixture not found: {path}")
    return path.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def page_with_version_html():
    path = FIXTURES_SEI_V4 / "page_with_version.html"
    if not path.exists():
        pytest.skip(f"Fixture not found: {path}")
    return path.read_text(encoding="utf-8")


def test_sei_v4_2_0_detect_version(page_with_version_html):
    """detect_version retorna 4.2.0 quando a página tem data-sei-version ou meta sei-version."""
    from playwright.sync_api import sync_playwright
    from app.scrapers.sei_v4.v4_2_0.scraper import SEIv4_2_0

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.set_content(page_with_version_html)
            scraper = SEIv4_2_0()
            version = scraper.detect_version(page)
            browser.close()
    except Exception as e:
        if "Executable doesn't exist" in str(e) or "playwright" in str(e).lower():
            pytest.skip("Playwright browsers not installed. Run: playwright install chromium")
        raise
    assert version is not None
    assert version.startswith("4.")


def test_sei_v4_2_0_extract_process_list(process_list_html):
    """extract_process_list extrai números e links da tabela (fixture SEI v4)."""
    from playwright.sync_api import sync_playwright
    from app.scrapers.sei_v4.v4_2_0.scraper import SEIv4_2_0

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.set_content(process_list_html)
            scraper = SEIv4_2_0()
            processes = scraper.extract_process_list(page)
            browser.close()
    except Exception as e:
        if "Executable doesn't exist" in str(e) or "playwright" in str(e).lower():
            pytest.skip("Playwright browsers not installed. Run: playwright install chromium")
        raise

    assert isinstance(processes, dict)
    assert len(processes) >= 2
    assert "1001.000001/2024-00" in processes
    assert "1002.000002/2024-00" in processes
    for num, data in processes.items():
        assert data.get("numero_processo") == num
        assert "links" in data
        assert len(data["links"]) >= 1
