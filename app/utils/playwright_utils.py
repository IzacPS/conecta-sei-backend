"""
Playwright Utilities - Inicialização de browser e login no SEI

Funções para gerenciamento de browser Playwright e autenticação no SEI.

IMPORTANTE - Gerenciamento de Sessão SEI:
O SEI NÃO mantém sessão entre diferentes operações. Por isso:
1. Cada worker/thread deve ter seu próprio Page (browser.new_page())
2. Cada Page deve fazer login antes de qualquer operação
3. Não reutilizar Pages entre diferentes processos
4. Browser pode ser compartilhado, mas Pages são isoladas

Funções:
- init_browser(): Inicializa browser Playwright (Chromium headless)
- create_page_with_login(): Cria nova página E faz login automaticamente (helper)
- login_to_sei(): Faz login no SEI usando credenciais configuradas
- is_logged_in(): Verifica se página está autenticada
- close_browser(): Fecha browser e limpa recursos
"""

from playwright.sync_api import sync_playwright, Browser, Page, Playwright
from typing import Optional, Tuple
from app.utils.credentials import load_credentials, credentials_are_complete

# Global playwright instance (singleton)
_playwright: Optional[Playwright] = None


def init_browser(headless: bool = True) -> Browser:
    """
    Inicializa browser Playwright (Chromium).

    Args:
        headless: Se True, roda em modo headless (sem UI)

    Returns:
        Browser Playwright inicializado

    Raises:
        Exception: Se falhar ao inicializar browser
    """
    global _playwright

    try:
        if _playwright is None:
            _playwright = sync_playwright().start()

        browser = _playwright.chromium.launch(headless=headless)

        logger = UILogger()
        mode = "headless" if headless else "headed"
        logger.log(f"Browser Chromium inicializado ({mode})")

        return browser

    except Exception as e:
        logger = UILogger()
        logger.log(f"Erro ao inicializar browser: {str(e)}")
        raise


def create_page_with_login(browser: Browser) -> Page:
    """
    Cria nova página e faz login automaticamente (helper).

    IMPORTANTE: Use esta função para cada worker/thread que precisa de uma página autenticada.
    O SEI não mantém sessão, então cada página precisa fazer login.

    Args:
        browser: Browser Playwright

    Returns:
        Page autenticada e pronta para uso

    Raises:
        Exception: Se login falhar
    """
    page = browser.new_page()

    try:
        login_to_sei(page)
        return page
    except Exception as e:
        page.close()
        raise


def is_logged_in(page: Page) -> bool:
    """
    Verifica se página está autenticada no SEI.

    Args:
        page: Página Playwright

    Returns:
        True se logado, False caso contrário
    """
    try:
        # Verifica se existe elemento que só aparece quando logado
        # Exemplo: menu de usuário, logo do sistema, etc.
        # Ajustar selector conforme SEI específico
        return page.query_selector("#main-menu") is not None or \
               page.query_selector("#divInfraBarraSistema") is not None
    except Exception:
        return False


def login_to_sei(page: Page) -> None:
    """
    Faz login no SEI usando credenciais configuradas.

    IMPORTANTE: Verifica se credenciais estão completas antes de tentar login.

    Args:
        page: Página Playwright

    Raises:
        Exception: Se credenciais não configuradas ou login falhar
    """
    if not credentials_are_complete():
        raise Exception(
            "Credenciais não configuradas ou incompletas. "
            "Configure nas Configurações primeiro."
        )

    credentials = load_credentials()
    logger = UILogger()
    source = credentials.get("source", "unknown")
    logger.log(f"Fazendo login no SEI (credenciais de: {source})")

    try:
        # Navegar para página de login
        page.goto(credentials["site_url"])

        # Preencher formulário de login
        page.fill("#txtEmail", credentials["email"])
        page.fill("#pwdSenha", credentials["senha"])

        # Submeter formulário
        page.click("#sbmLogin")

        # Aguardar carregamento completo
        page.wait_for_load_state("networkidle")

        logger.log("Login realizado com sucesso")

    except Exception as e:
        logger.log(f"Erro ao fazer login no SEI: {str(e)}")
        raise


def close_browser(browser: Browser) -> None:
    """
    Fecha browser e limpa recursos.

    Args:
        browser: Browser Playwright a ser fechado
    """
    try:
        browser.close()
        logger = UILogger()
        logger.log("Browser fechado com sucesso")
    except Exception as e:
        logger = UILogger()
        logger.log(f"Erro ao fechar browser: {str(e)}")


def cleanup_playwright() -> None:
    """
    Limpa recursos globais do Playwright.

    IMPORTANTE: Chamar apenas ao final da aplicação.
    """
    global _playwright

    try:
        if _playwright is not None:
            _playwright.stop()
            _playwright = None
            logger = UILogger()
            logger.log("Playwright resources cleaned up")
    except Exception as e:
        logger = UILogger()
        logger.log(f"Erro ao limpar recursos Playwright: {str(e)}")
