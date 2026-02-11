from connect_mongo import get_database
import datetime

def load_notification_settings():
    db = get_database()
    collection = db.configuracoes
    
    settings = collection.find_one({"tipo": "email_notifications"})
    if not settings:
        default_settings = {
            "tipo": "email_notifications",
            "emails": ["sei@unotrade.com"],
            "notification_settings": {
                "new_docs": True,
                "status_change": True,
                "errors": True
            },
            "ultima_atualizacao": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        collection.insert_one(default_settings)
        return default_settings
    return settings

def save_notification_settings(emails, notification_settings):
    db = get_database()
    collection = db.configuracoes
    
    settings = {
        "tipo": "email_notifications",
        "emails": emails,
        "notification_settings": notification_settings,
        "ultima_atualizacao": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    collection.update_one(
        {"tipo": "email_notifications"},
        {"$set": settings},
        upsert=True
    )

def get_notification_emails():
    try:
        settings = load_notification_settings()
        return settings.get("emails", ["luismelloleite@gmail.com"])
    except Exception as e:
        print(f"Erro ao buscar emails de notificação: {str(e)}")
        return ["sei@unotrade.com"]