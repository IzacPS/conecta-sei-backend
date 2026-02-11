# Guia de Email Providers

**AutomaSEI v2.0** - Sistema modular de envio de emails

---

## Arquitetura

O sistema de email usa o **padrão Strategy** para permitir troca fácil de provedores de email.

**Arquivos:**
- `email_providers.py`: Define interface `EmailProvider` e implementações específicas
- `email_service.py`: Funções de alto nível (notify_new_processes, etc.) - usa provider configurado

**Provider Padrão:** Microsoft Graph API

---

## Provedores Disponíveis

### 1. Microsoft Graph API (Atual)

**Classe:** `MicrosoftGraphProvider`

**Uso:**
- OAuth 2.0 client credentials flow
- Envia via conta corporativa Microsoft
- Requer CLIENT_ID, CLIENT_SECRET, TENANT_ID

**Configuração:**
```python
from app.utils.email_providers import MicrosoftGraphProvider, set_email_provider

# Já é o padrão, não precisa configurar
# Mas se quiser explicitamente:
provider = MicrosoftGraphProvider()
set_email_provider(provider)
```

**Credenciais (usar variáveis de ambiente):**
```python
CLIENT_ID = os.environ.get("MS_GRAPH_CLIENT_ID")
CLIENT_SECRET = os.environ.get("MS_GRAPH_CLIENT_SECRET")
TENANT_ID = os.environ.get("MS_GRAPH_TENANT_ID")
USER_ID = os.environ.get("MS_GRAPH_USER_ID")  # ex: sei@unotrade.com
```

---

### 2. SMTP (Futuro - Placeholder)

**Classe:** `SMTPProvider`

**Status:** NÃO IMPLEMENTADO

**Uso Planejado:**
```python
from app.utils.email_providers import SMTPProvider, set_email_provider

# Gmail
smtp = SMTPProvider(
    smtp_server="smtp.gmail.com",
    smtp_port=587,
    username="your-email@gmail.com",
    password="your-app-password"
)
set_email_provider(smtp)

# Outlook
smtp = SMTPProvider(
    smtp_server="smtp-mail.outlook.com",
    smtp_port=587,
    username="your-email@outlook.com",
    password="your-password"
)
set_email_provider(smtp)
```

**Implementação necessária:**
```python
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def send_email(self, subject: str, body: str, recipients: List[str]) -> bool:
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = self.username
    msg['To'] = ', '.join(recipients)

    html_part = MIMEText(body, 'html')
    msg.attach(html_part)

    with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
        server.starttls()
        server.login(self.username, self.password)
        server.send_message(msg)

    return True
```

---

### 3. SendGrid (Futuro)

**Classe:** `SendGridProvider` (não criada ainda)

**Exemplo de implementação:**
```python
import sendgrid
from sendgrid.helpers.mail import Mail, Email, To, Content

class SendGridProvider(EmailProvider):
    def __init__(self, api_key: str):
        self.sg = sendgrid.SendGridAPIClient(api_key)

    def get_name(self) -> str:
        return "SendGrid"

    def send_email(self, subject: str, body: str, recipients: List[str]) -> bool:
        message = Mail(
            from_email="noreply@automatsei.com",
            to_emails=recipients,
            subject=subject,
            html_content=body
        )

        try:
            response = self.sg.send(message)
            return response.status_code == 202
        except Exception as e:
            print(f"Erro SendGrid: {e}")
            return False
```

**Uso:**
```python
from app.utils.email_providers import SendGridProvider, set_email_provider

provider = SendGridProvider(api_key="SG.xxxxxxxxxxxx")
set_email_provider(provider)
```

---

### 4. AWS SES (Futuro)

**Classe:** `AWSESProvider` (não criada ainda)

**Exemplo de implementação:**
```python
import boto3

class AWSESProvider(EmailProvider):
    def __init__(self, region: str = "us-east-1"):
        self.ses = boto3.client('ses', region_name=region)

    def get_name(self) -> str:
        return "AWS SES"

    def send_email(self, subject: str, body: str, recipients: List[str]) -> bool:
        try:
            response = self.ses.send_email(
                Source="noreply@automatsei.com",
                Destination={'ToAddresses': recipients},
                Message={
                    'Subject': {'Data': subject},
                    'Body': {'Html': {'Data': body}}
                }
            )
            return response['ResponseMetadata']['HTTPStatusCode'] == 200
        except Exception as e:
            print(f"Erro AWS SES: {e}")
            return False
```

**Uso:**
```python
from app.utils.email_providers import AWSESProvider, set_email_provider

provider = AWSESProvider(region="us-east-1")
set_email_provider(provider)
```

---

## Como Trocar de Provider

### Opção 1: No Código

Edite o arquivo onde inicializa o sistema:

```python
# No início da aplicação (main.py ou api/main.py)
from app.utils.email_providers import SMTPProvider, set_email_provider

# Configurar provider
smtp = SMTPProvider(
    smtp_server="smtp.gmail.com",
    smtp_port=587,
    username="automatsei@gmail.com",
    password="app-password-here"
)
set_email_provider(smtp)

# Agora todas as notificações usarão SMTP
```

### Opção 2: Via Variável de Ambiente (Futuro)

Modificar `email_providers.py` para suportar:

```python
import os

def get_email_provider() -> EmailProvider:
    provider_type = os.getenv("EMAIL_PROVIDER", "microsoft_graph")

    if provider_type == "smtp":
        return SMTPProvider(
            smtp_server=os.getenv("SMTP_SERVER"),
            smtp_port=int(os.getenv("SMTP_PORT", "587")),
            username=os.getenv("SMTP_USERNAME"),
            password=os.getenv("SMTP_PASSWORD")
        )
    elif provider_type == "sendgrid":
        return SendGridProvider(api_key=os.getenv("SENDGRID_API_KEY"))
    elif provider_type == "aws_ses":
        return AWSESProvider(region=os.getenv("AWS_REGION", "us-east-1"))
    else:
        # Default: Microsoft Graph
        return MicrosoftGraphProvider()
```

**Uso:**
```bash
# .env
EMAIL_PROVIDER=smtp
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=automatsei@gmail.com
SMTP_PASSWORD=app-password
```

### Opção 3: Via PostgreSQL SystemConfiguration (Futuro)

Armazenar configuração no banco:

```python
def get_email_provider() -> EmailProvider:
    from app.database.session import get_session
    from app.database.models.system_configuration import SystemConfiguration

    with get_session() as session:
        config = session.query(SystemConfiguration).filter_by(
            key="email_provider"
        ).first()

        if config and isinstance(config.value, dict):
            provider_type = config.value.get("type", "microsoft_graph")

            if provider_type == "smtp":
                return SMTPProvider(
                    smtp_server=config.value["smtp_server"],
                    smtp_port=config.value["smtp_port"],
                    username=config.value["username"],
                    password=config.value["password"]
                )
            # ... outros providers

    # Default
    return MicrosoftGraphProvider()
```

---

## Funções de Alto Nível (email_service.py)

Estas funções **não mudam** ao trocar de provider:

```python
from app.utils.email_service import (
    notify_new_processes,
    notify_categorization_needed,
    notify_new_documents,
    notify_process_update
)

# Sempre funcionam, independente do provider
notify_new_processes([
    {"process_number": "23080.000001/2024-00", "link": "12345"}
])
```

---

## Criando um Novo Provider

1. **Herdar de `EmailProvider`:**

```python
from app.utils.email_providers import EmailProvider

class MyCustomProvider(EmailProvider):
    def __init__(self, config_param: str):
        self.config = config_param

    def get_name(self) -> str:
        return "My Custom Provider"

    def send_email(self, subject: str, body: str, recipients: List[str]) -> bool:
        # Implementar lógica de envio
        try:
            # ... código de envio ...
            return True
        except Exception as e:
            print(f"Erro: {e}")
            return False
```

2. **Adicionar ao `email_providers.py`:**

```python
# No final do arquivo
class MyCustomProvider(EmailProvider):
    # ... implementação ...
```

3. **Usar:**

```python
from app.utils.email_providers import MyCustomProvider, set_email_provider

provider = MyCustomProvider(config_param="value")
set_email_provider(provider)
```

---

## Testando Providers

```python
# test_email_providers.py
from app.utils.email_providers import MicrosoftGraphProvider, set_email_provider
from app.utils.email_service import send_email

# Testar Microsoft Graph
provider = MicrosoftGraphProvider()
set_email_provider(provider)

result = send_email(
    subject="Teste",
    body="<p>Email de teste</p>"
)

print(f"Email enviado: {result}")
```

---

## Notas Importantes

1. **Provider é global:** `set_email_provider()` afeta toda a aplicação
2. **Thread-safe:** Trocar provider durante execução pode causar problemas
3. **Credenciais:** Mover hardcoded credentials para environment variables
4. **Fallback:** Sistema sempre tem email padrão em `get_recipients()`
5. **Logging:** Todos os providers devem logar erros via `UILogger()`

---

## Roadmap

- [ ] Implementar `SMTPProvider`
- [ ] Implementar `SendGridProvider`
- [ ] Implementar `AWSESProvider`
- [ ] Suporte a configuração via environment variables
- [ ] Suporte a configuração via PostgreSQL
- [ ] Retry logic para falhas de envio
- [ ] Queue system para envios em lote
- [ ] Templates de email personalizáveis

---

**Última Atualização:** 2025-12-15 (Sprint 2.2)
