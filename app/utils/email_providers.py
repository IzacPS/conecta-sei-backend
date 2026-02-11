"""
Email Providers - Abstração de provedores de email

Define interface base para provedores de email e implementações específicas.

Provedores disponíveis:
- MicrosoftGraphProvider: Microsoft Graph API (atual)
- SMTPProvider: SMTP genérico (Gmail, Outlook, etc.) - futuro
- SendGridProvider: SendGrid API - futuro
- AWSESProvider: AWS Simple Email Service - futuro

Uso:
    from app.utils.email_providers import get_email_provider

    provider = get_email_provider()
    provider.send_email(subject="Test", body="<p>Hello</p>", recipients=["user@example.com"])
"""

from abc import ABC, abstractmethod
import logging
import os
from typing import List, Optional

import requests

logger = logging.getLogger(__name__)

# Env vars para Microsoft Graph (evita credenciais no código)
MS_GRAPH_CLIENT_ID = os.getenv("MS_GRAPH_CLIENT_ID")
MS_GRAPH_CLIENT_SECRET = os.getenv("MS_GRAPH_CLIENT_SECRET")
MS_GRAPH_TENANT_ID = os.getenv("MS_GRAPH_TENANT_ID")
MS_GRAPH_USER_ID = os.getenv("MS_GRAPH_USER_ID")  # email/user id que envia (ex: sei@unotrade.com)


class EmailProvider(ABC):
    """
    Interface base para provedores de email.

    Todos os provedores devem implementar esta interface.
    """

    @abstractmethod
    def send_email(self, subject: str, body: str, recipients: List[str]) -> bool:
        """
        Envia email.

        Args:
            subject: Assunto do email
            body: Corpo do email (HTML)
            recipients: Lista de emails destinatários

        Returns:
            True se enviado com sucesso, False caso contrário
        """
        pass

    @abstractmethod
    def get_name(self) -> str:
        """Retorna nome do provider"""
        pass


class MicrosoftGraphProvider(EmailProvider):
    """
    Provider Microsoft Graph API.

    Usa OAuth 2.0 client credentials flow para autenticação.

    Variáveis de ambiente (recomendado):
    - MS_GRAPH_CLIENT_ID
    - MS_GRAPH_CLIENT_SECRET
    - MS_GRAPH_TENANT_ID
    - MS_GRAPH_USER_ID (conta que envia, ex: sei@unotrade.com)

    Se não definidas, usa fallback de desenvolvimento (evitar em produção).
    """

    # Fallback apenas para desenvolvimento local (não usar em produção)
    _DEFAULT_CLIENT_ID = os.environ.get("MS_GRAPH_CLIENT_ID", "")
    _DEFAULT_CLIENT_SECRET = os.environ.get("MS_GRAPH_CLIENT_SECRET", "")
    _DEFAULT_TENANT_ID = os.environ.get("MS_GRAPH_TENANT_ID", "")
    _DEFAULT_USER_ID = os.environ.get("MS_GRAPH_USER_ID", "")

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ):
        self.client_id = client_id or MS_GRAPH_CLIENT_ID or self._DEFAULT_CLIENT_ID
        self.client_secret = client_secret or MS_GRAPH_CLIENT_SECRET or self._DEFAULT_CLIENT_SECRET
        self.tenant_id = tenant_id or MS_GRAPH_TENANT_ID or self._DEFAULT_TENANT_ID
        self.user_id = user_id or MS_GRAPH_USER_ID or self._DEFAULT_USER_ID
        self.token_url = f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"
        self.send_mail_url = f"https://graph.microsoft.com/v1.0/users/{self.user_id}/sendMail"
        self._token_cache: Optional[str] = None

    def get_name(self) -> str:
        return "Microsoft Graph API"

    def _get_token(self) -> Optional[str]:
        """
        Obtém token de acesso do Microsoft Graph API.

        Returns:
            Access token ou None se falhar
        """
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        data = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "scope": "https://graph.microsoft.com/.default",
        }

        try:
            response = requests.post(self.token_url, headers=headers, data=data)
            if response.status_code == 200:
                self._token_cache = response.json().get("access_token")
                return self._token_cache
            else:
                logger.warning(
                    "Erro ao obter token Microsoft Graph: %s %s",
                    response.status_code,
                    response.text,
                )
                return None
        except Exception as e:
            logger.exception("Exceção ao obter token Microsoft Graph: %s", e)
            return None

    def send_email(self, subject: str, body: str, recipients: List[str]) -> bool:
        """
        Envia email via Microsoft Graph API.

        Args:
            subject: Assunto do email
            body: Corpo do email (HTML)
            recipients: Lista de emails destinatários

        Returns:
            True se enviado com sucesso, False caso contrário
        """
        if not recipients:
            logger.warning("Nenhum destinatário fornecido")
            return False

        token = self._get_token()
        if not token:
            logger.warning("Falha ao obter token Microsoft Graph")
            return False

        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

        email_data = {
            "message": {
                "subject": f"SEI Automação - {subject}",
                "body": {"contentType": "HTML", "content": body},
                "toRecipients": [
                    {"emailAddress": {"address": recipient}} for recipient in recipients
                ],
            }
        }

        try:
            response = requests.post(self.send_mail_url, headers=headers, json=email_data)

            if response.status_code == 202:
                logger.info("Email enviado via Microsoft Graph para %s", recipients)
                return True
            logger.warning(
                "Erro ao enviar email via Microsoft Graph: %s %s",
                response.status_code,
                response.text,
            )
            return False
        except Exception as e:
            logger.exception("Exceção ao enviar email via Microsoft Graph: %s", e)
            return False


class SMTPProvider(EmailProvider):
    """
    Provider SMTP genérico (placeholder para implementação futura).

    Pode ser usado com Gmail, Outlook, ou qualquer servidor SMTP.

    TODO: Implementar quando necessário
    """

    def __init__(self, smtp_server: str, smtp_port: int, username: str, password: str):
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.username = username
        self.password = password

    def get_name(self) -> str:
        return f"SMTP ({self.smtp_server})"

    def send_email(self, subject: str, body: str, recipients: List[str]) -> bool:
        """
        TODO: Implementar envio via SMTP

        Usar smtplib:
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        """
        raise NotImplementedError("SMTP provider ainda não implementado")


# Provider ativo (pode ser alterado via configuração)
_active_provider: Optional[EmailProvider] = None


def get_email_provider() -> EmailProvider:
    """
    Retorna o provider de email ativo.

    Por padrão, usa MicrosoftGraphProvider.
    Para trocar de provider, chame set_email_provider().

    Returns:
        EmailProvider ativo
    """
    global _active_provider

    if _active_provider is None:
        # Default: Microsoft Graph
        _active_provider = MicrosoftGraphProvider()

    return _active_provider


def set_email_provider(provider: EmailProvider) -> None:
    """
    Define o provider de email ativo.

    Exemplo:
        # Trocar para SMTP
        smtp = SMTPProvider("smtp.gmail.com", 587, "user@gmail.com", "password")
        set_email_provider(smtp)

    Args:
        provider: Instância do provider a ser usado
    """
    global _active_provider
    _active_provider = provider
    logger.info("Email provider alterado para: %s", provider.get_name())
