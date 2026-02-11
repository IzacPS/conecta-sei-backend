import os
import requests
import json
from typing import List, Dict
from mongo_config import get_notification_emails
from connect_mongo import get_database
import datetime

CLIENT_ID = os.environ.get("MS_GRAPH_CLIENT_ID", "your-client-id")
CLIENT_SECRET = os.environ.get("MS_GRAPH_CLIENT_SECRET", "your-client-secret")
TENANT_ID = os.environ.get("MS_GRAPH_TENANT_ID", "your-tenant-id")
USER_ID = os.environ.get("MS_GRAPH_USER_ID", "noreply@example.com")

token_url = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"
send_mail_url = f"https://graph.microsoft.com/v1.0/users/{USER_ID}/sendMail"

def get_recipients() -> List[str]:
    try:
        return get_notification_emails()
    except Exception as e:
        print(f"Error loading recipients: {e}")
        return ["luismelloleite@gmail.com"]

def get_token():
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = {
        "grant_type": "client_credentials",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "scope": "https://graph.microsoft.com/.default",
    }
    response = requests.post(token_url, headers=headers, data=data)
    if response.status_code == 200:
        return response.json().get("access_token")
    else:
        print(f"Error fetching token: {response.status_code} {response.text}")
        return None

def get_process_nickname(process_number: str) -> str:
    try:
        db = get_database()
        collection = db.processos
        processo = collection.find_one({"numero_processo": process_number})
        if processo and "apelido" in processo:
            return processo["apelido"]
    except Exception as e:
        print(f"Error fetching nickname: {e}")
    return process_number

def format_process_display(process_number: str) -> str:
    nickname = get_process_nickname(process_number)
    if nickname != process_number:
        return f"{nickname} ({process_number})"
    return process_number

def send_email(subject: str, body: str):
    recipients = get_recipients()
    if not recipients:
        print("Recipientes não encontrados.")
        recipients = ["luismelloleite@gmail.com"]

    token = get_token()
    if not token:
        print("Falha em obter token de acesso.")
        return

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

    response = requests.post(send_mail_url, headers=headers, json=email_data)

    if response.status_code == 202:
        print(f"E-mail enviado para {recipients}")
    else:
        print(f"Erro ao enviar e-mail: {response.status_code} {response.text}")

def create_email_template(content: str) -> str:
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
            <h2>AutomaSEI</h2>
            <p>{content}</p>
            <div class="footer">
                <p>Este é um email automático, por favor não responda.</p>
            </div>
        </div>
    </body>
    </html>
    """

def notify_new_processes(processes: List[dict]):
    subject = "Novos Processos Encontrados"
    body = "Foram encontrados os seguintes processos:<br/><br/>"

    for process in processes:
        process_number = process["process_number"]
        link = process["link"]
        display_name = format_process_display(process_number)
        body += f"- <a href='https://colaboragov.sei.gov.br/sei/{link}'>{display_name}</a><br/>"

    send_email(subject, create_email_template(body))

def notify_categorization_needed(process_set: List[dict]):
    subject = "Processos Necessitam de Categorização"
    body = "Os seguintes processos necessitam ser categorizados:<br/><br/>"

    for process in process_set:
        process_number = process["process_number"]
        link = process["link"]
        display_name = format_process_display(process_number)
        body += f"- <a href='https://colaboragov.sei.gov.br/sei/{link}'>{display_name}</a><br/>"

    body += "<br/>Esses processos possuem acesso parcial e requerem análise."

    send_email(subject, create_email_template(body))

def notify_new_documents(process_data: Dict[str, Dict]):
    subject = "Novos Documentos Encontrados"
    content = []
    
    for processo, info in process_data.items():
        apelido = info["apelido"]
        display_name = f"{apelido} ({processo})" if apelido else processo
        content.append(f"<p><strong>Processo:</strong> {display_name}</p>")
        content.append("<p><strong>Signatários e Documentos Enviados:</strong></p>")
        
        for signatario, documentos in info["documentos_por_signatario"].items():
            content.append(f"<p>* <strong>{signatario}:</strong></p>")
            for doc in documentos:
                content.append(f"<p>&nbsp;&nbsp;&nbsp;- {doc}</p>")
        
        content.append("<br>")
    
    content.append(f"<p>Data: {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}</p>")
    
    send_email(subject, create_email_template("\n".join(content)))

def notify_process_update(process_number: str, new_docs: List[str]):
    subject = "Alteração Detectada em Processo"
    display_name = format_process_display(process_number)
    body = f"Foram detectadas alterações no processo {display_name}:<br/><br/>"

    send_email(subject, create_email_template(body))