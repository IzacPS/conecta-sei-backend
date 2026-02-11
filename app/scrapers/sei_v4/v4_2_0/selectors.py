"""
CSS Selectors for SEI v4.2.0

This file contains all CSS selectors and XPath expressions used
to interact with SEI v4.2.0. Extracted from the legacy codebase.

Source files:
- utils.py (login)
- get_process_update.py (process list)
- get_process_links_status.py (link validation, authority)
- get_process_docs_update.py (documents, authority)
"""

# ==================== Login Selectors ====================

LOGIN = {
    "email": "#txtEmail",
    "password": "#pwdSenha",
    "submit": "#sbmLogin",
    "error": "#divInfraMsg, .alert-danger",
}

# ==================== Process List Selectors ====================

PROCESS_LIST = {
    # Main table
    "table": '//*[@id="tblDocumentos"]',
    "rows": '//*[@id="tblDocumentos"]/tbody/tr[position()>1]',

    # Row elements
    "link_element": 'td[align="center"] a',

    # Pagination
    "next_button": '//*[@id="lnkInfraProximaPaginaSuperior"]',
}

# ==================== Link Validation Selectors ====================

LINK_VALIDATION = {
    # Access type indicator
    "location_bar": "#divInfraBarraLocalizacao",

    # Keywords in location bar to determine access type
    "integral_keywords": ["Visualização Integral"],
    "parcial_keywords": ["Acesso Parcial", "Visualização Parcial"],
}

# ==================== Authority Selectors ====================

AUTHORITY = {
    # XPath for authority element in process table
    "authority_xpath": '//*[@id="tblDocumentos"]/tbody/tr[2]/td[5]/a',

    # Alternative selectors
    "authority_field": "#txtAutoridade",
    "authority_label": "label:has-text('Autoridade')",
}

# ==================== Document List Selectors ====================

DOCUMENTS = {
    # Main documents table
    "table": "#tblDocumentos",
    "rows": "#tblDocumentos tbody tr",

    # Document row elements
    "doc_link": "a[href*='acao=procedimento_visualizar']",
    "doc_number": "td:nth-child(1)",
    "doc_type": "td:nth-child(2)",
    "doc_date": "td:nth-child(3)",

    # Alert check (for restricted documents)
    "onclick_alert": "onclick",  # attribute to check
}

# ==================== Unit Selector ====================

UNIT = {
    "selector": "#selInfraUnidades",
}

# ==================== Pagination ====================

PAGINATION = {
    "next_page": '//*[@id="lnkInfraProximaPaginaSuperior"]',
    "previous_page": '//*[@id="lnkInfraPaginaAnteriorSuperior"]',
}

# ==================== Common Indicators ====================

INDICATORS = {
    # Logged in indicator
    "logged_in": "#lnkUsuarioSistema, #lnkInfraSair",

    # Loading indicator
    "loading": "#divCarregando, .loading",

    # Error messages
    "error_message": "#divInfraMsg, .alert-danger",
}

# ==================== Helper Functions ====================

def get_all_selectors():
    """Get all selectors as a flat dictionary."""
    return {
        "login": LOGIN,
        "process_list": PROCESS_LIST,
        "link_validation": LINK_VALIDATION,
        "authority": AUTHORITY,
        "documents": DOCUMENTS,
        "unit": UNIT,
        "pagination": PAGINATION,
        "indicators": INDICATORS,
    }
