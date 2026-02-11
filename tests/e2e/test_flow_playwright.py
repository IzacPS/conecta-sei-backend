"""
E2E tests using Playwright (same lib used for SEI scraping).

Requer API e frontend rodando (seed aplicado). Executar com:
  pytest tests/e2e/test_flow_playwright.py -m e2e -v

Antes: uvicorn app.api.main:app --port 8000  (em outro terminal)
       cd frontend && npm run dev              (em outro terminal)
       python scripts/seed-test-data.py
"""

import os
import pytest
from playwright.sync_api import sync_playwright

FRONTEND_URL = os.getenv("E2E_FRONTEND_URL", "http://localhost:3000")
PAGE_TIMEOUT_MS = 15000


def _frontend_available() -> bool:
    """Quick check if frontend responds (avoids hanging if not running)."""
    try:
        import urllib.request
        urllib.request.urlopen(FRONTEND_URL, timeout=2)
        return True
    except Exception:
        return False


@pytest.mark.e2e
def test_e2e_client_my_requests_sees_page():
    """Como cliente (devUserEmail), /my-requests exibe a página 'Minhas solicitações'."""
    if not _frontend_available():
        pytest.skip(f"Frontend not reachable at {FRONTEND_URL}. Start it with: cd frontend && npm run dev")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        page.set_default_timeout(PAGE_TIMEOUT_MS)
        try:
            page.goto(FRONTEND_URL)
            # Impersonar cliente (backend AUTH_DEV_MODE + X-Dev-User-Email)
            page.evaluate("() => localStorage.setItem('devUserEmail', 'client@automasei.local')")
            page.goto(f"{FRONTEND_URL}/my-requests")
            page.wait_for_load_state("networkidle")
            content = page.content()
            assert "Minhas solicitações" in content, "Página do cliente deve exibir 'Minhas solicitações'"
        finally:
            browser.close()


@pytest.mark.e2e
def test_e2e_admin_requests_sees_page():
    """Como admin (sem header), /admin/requests exibe 'Solicitações de pipeline'."""
    if not _frontend_available():
        pytest.skip(f"Frontend not reachable at {FRONTEND_URL}. Start it with: cd frontend && npm run dev")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        page.set_default_timeout(PAGE_TIMEOUT_MS)
        try:
            # Sem devUserEmail = admin (dev-uid-001)
            page.goto(f"{FRONTEND_URL}/admin/requests")
            page.wait_for_load_state("networkidle")
            content = page.content()
            assert "Solicitações de pipeline" in content, "Painel admin deve exibir 'Solicitações de pipeline'"
        finally:
            browser.close()
