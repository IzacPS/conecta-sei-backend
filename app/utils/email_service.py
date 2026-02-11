"""
Email Service - Envio de emails e notificações

Sistema de notificação por email com abstração de provider.

- get_process_nickname(): Usa Process (PostgreSQL)
- get_recipients(): SystemConfiguration (notification_emails / email_notifications) ou env NOTIFICATION_EMAILS

ARQUITETURA:
- Usa abstração EmailProvider (app.utils.email_providers)
- Provider padrão: Microsoft Graph API (credenciais via MS_GRAPH_* em .env)
- Trocar provider: set_email_provider() em email_providers.py

Funções:
- notify_new_processes(): Notifica novos processos encontrados
- notify_categorization_needed(): Notifica processos que precisam de categorização
- notify_new_documents(): Notifica novos documentos encontrados
- notify_process_update(): Notifica alterações em processos
"""

import datetime
import logging
import os
from typing import Dict, List

from app.database.session import get_session
from app.database.models.process import Process
from app.database.models.system_configuration import SystemConfiguration
from app.utils.email_providers import get_email_provider

logger = logging.getLogger(__name__)


def get_recipients() -> List[str]:
    """
    Obtém lista de emails para notificações do PostgreSQL.

    SystemConfiguration: key="notification_emails" ou "email_notifications",
    value JSONB com {"emails": ["..."]}.

    Returns:
        Lista de emails de destinatários
    """
    try:
        with get_session() as session:
            for key in ("notification_emails", "email_notifications"):
                config = session.query(SystemConfiguration).filter_by(key=key).first()
                if not config or not config.value:
                    continue
                val = config.value
                if isinstance(val, dict) and "emails" in val:
                    emails = val["emails"]
                    if isinstance(emails, list) and emails:
                        return emails
                if isinstance(val, list) and val:
                    return val
    except Exception as e:
        logger.exception("Erro ao carregar emails de notificação: %s", e)

    # Fallback: variável de ambiente (ex: NOTIFICATION_EMAILS=email1@x.com,email2@x.com)
    env_emails = os.getenv("NOTIFICATION_EMAILS", "").strip()
    if env_emails:
        return [e.strip() for e in env_emails.split(",") if e.strip()]
    logger.warning("Nenhum destinatário de notificação configurado (SystemConfiguration ou NOTIFICATION_EMAILS)")
    return []


def get_process_nickname(process_number: str) -> str:
    """
    Busca apelido do processo no PostgreSQL.

    Args:
        process_number: Número do processo

    Returns:
        Apelido do processo, ou o número se não tiver apelido
    """
    try:
        with get_session() as session:
            processo = session.query(Process).filter_by(process_number=process_number).first()
            if processo and processo.nickname and processo.nickname.strip():
                return processo.nickname
    except Exception as e:
        logger.exception("Erro ao buscar apelido do processo: %s", e)

    return process_number


def format_process_display(process_number: str) -> str:
    """
    Formata exibição do processo com apelido se disponível.

    Args:
        process_number: Número do processo

    Returns:
        String formatada "Apelido (Número)" ou apenas "Número"
    """
    nickname = get_process_nickname(process_number)
    if nickname != process_number:
        return f"{nickname} ({process_number})"
    return process_number


def create_email_template(content: str) -> str:
    """
    Cria template HTML para email.

    Args:
        content: Conteúdo do email (HTML)

    Returns:
        Template completo formatado
    """
    return f"""
    <html>
    <head>
        <style>
            body {{
                font-family: Arial, sans-serif;
                color: #333;
                background-color: #f4f4f4;
                margin: 0;
                padding: 20px;
            }}
            .container {{
                max-width: 600px;
                margin: 0 auto;
                background-color: #fff;
                padding: 20px;
                border-radius: 10px;
                box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
            }}
            h2 {{
                color: #4CAF50;
            }}
            a {{
                color: #1E90FF;
                text-decoration: none;
            }}
            a:hover {{
                text-decoration: underline;
            }}
            .footer {{
                margin-top: 20px;
                font-size: 12px;
                color: #777;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h2>ConectaSEI</h2>
            <p>{content}</p>
            <div class="footer">
                <p>Este é um email automático, por favor não responda.</p>
            </div>
        </div>
    </body>
    </html>
    """


def send_email(subject: str, body: str) -> bool:
    """
    Envia email usando o provider configurado.

    Args:
        subject: Assunto do email
        body: Corpo do email (HTML)

    Returns:
        True se enviado com sucesso, False caso contrário
    """
    recipients = get_recipients()
    if not recipients:
        logger.warning("Nenhum destinatário configurado")
        return False

    provider = get_email_provider()
    return provider.send_email(subject, body, recipients)


def notify_new_processes(processes: List[dict]) -> bool:
    """
    Notifica sobre novos processos encontrados.

    Args:
        processes: Lista de dicts com process_number e link

    Returns:
        True se email enviado com sucesso
    """
    subject = "Novos Processos Encontrados"
    body = "Foram encontrados os seguintes processos:<br/><br/>"

    for process in processes:
        process_number = process["process_number"]
        link = process.get("link", "")
        display_name = format_process_display(process_number)
        body += f"- <a href='https://colaboragov.sei.gov.br/sei/{link}'>{display_name}</a><br/>"

    return send_email(subject, create_email_template(body))


def notify_categorization_needed(process_set: List[dict]) -> bool:
    """
    Notifica sobre processos que precisam de categorização.

    Args:
        process_set: Lista de dicts com process_number e link

    Returns:
        True se email enviado com sucesso
    """
    subject = "Processos Necessitam de Categorização"
    body = "Os seguintes processos necessitam ser categorizados:<br/><br/>"

    for process in process_set:
        process_number = process["process_number"]
        link = process.get("link", "")
        display_name = format_process_display(process_number)
        body += f"- <a href='https://colaboragov.sei.gov.br/sei/{link}'>{display_name}</a><br/>"

    body += "<br/>Esses processos possuem acesso parcial e requerem análise."

    return send_email(subject, create_email_template(body))


def notify_new_documents(process_data: Dict[str, Dict]) -> bool:
    """
    Notifica sobre novos documentos encontrados.

    Args:
        process_data: Dict com {processo: {apelido, documentos_por_signatario}}

    Returns:
        True se email enviado com sucesso
    """
    subject = "Novos Documentos Encontrados"
    content = []

    for processo, info in process_data.items():
        apelido = info.get("apelido", "")
        display_name = f"{apelido} ({processo})" if apelido else processo
        content.append(f"<p><strong>Processo:</strong> {display_name}</p>")
        content.append("<p><strong>Signatários e Documentos Enviados:</strong></p>")

        documentos_por_signatario = info.get("documentos_por_signatario", {})
        for signatario, documentos in documentos_por_signatario.items():
            content.append(f"<p>* <strong>{signatario}:</strong></p>")
            for doc in documentos:
                content.append(f"<p>&nbsp;&nbsp;&nbsp;- {doc}</p>")

        content.append("<br>")

    content.append(f"<p>Data: {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}</p>")

    return send_email(subject, create_email_template("\n".join(content)))


def notify_process_update(process_number: str, new_docs: List[str]) -> bool:
    """
    Notifica sobre alterações detectadas em um processo.

    Args:
        process_number: Número do processo
        new_docs: Lista de novos documentos

    Returns:
        True se email enviado com sucesso
    """
    subject = "Alteração Detectada em Processo"
    display_name = format_process_display(process_number)
    body = f"Foram detectadas alterações no processo {display_name}:<br/><br/>"

    if new_docs:
        body += "Novos documentos:<br/>"
        for doc in new_docs:
            body += f"- {doc}<br/>"

    return send_email(subject, create_email_template(body))
