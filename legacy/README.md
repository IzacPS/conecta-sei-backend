# Código legado (v1.0.10 – desktop e MongoDB)

Esta pasta concentra o código do AutomaSEI v1.0.10 que **não é usado** pela API v2.0.

- **Não importe** nada daqui a partir de `app/` ou dos scripts ativos.
- Mantida apenas para referência, rollback ou migração pontual (ex.: script de migração Mongo → Postgres usa variável `MONGO_URI`; o script atual está em `scripts/migrate-mongo-to-postgres.py` e não depende destes arquivos).

## Modelo single-user (um usuário específico)

No legado **já existiam credenciais de um usuário que o app usava**: o sistema guardava e utilizava o **email + senha de um único usuário** para logar no SEI e rodar o pipeline (descoberta de processos, download, etc.). Ou seja, não era multi-usuário: era **um usuário cujas credenciais estavam salvas** (no MongoDB em `configuracoes` e/ou em `credenciais.json`) e que o desktop usava em todas as operações.

Resumo do que ficava salvo e era usado:

- **Uma URL do SEI** – `configuracoes` com `tipo: "url_sistema"` (um `valor` só).
- **Credenciais desse usuário** – `configuracoes` com `tipo: "credenciais_acesso"` (email + senha desse usuário para login no SEI).
- **Uma lista de notificações** – `configuracoes` com `tipo: "email_notifications"` (emails + opções de notificação).
- **Processos** – coleção `processos` sem vínculo a “instituição”; um único conjunto de processos acessados com essas credenciais.

No v2 (ConectaSEI) isso equivale a **uma instituição** com as credenciais (URL + email/senha) daquele mesmo tipo de uso: um usuário cujas credenciais a instituição guarda e usa para acessar o SEI.

## Conteúdo

- **UI (desktop):** `ui_*.py`, `main.py` – aplicação tkinter/ttkbootstrap
- **Pipeline legado:** `get_*.py` – descoberta/validação/download de processos (MongoDB)
- **MongoDB:** `connect_mongo.py`, `mongo_config.py`, `dump_mongo.py`, `kill_connections.py`
- **Utilitários antigos:** `utils.py`, `logger_system.py`, `backup_system.py`, `config_system.py`, etc.
- **Migração antiga:** `migrate_mongodb_to_postgres.py` (substituído por `scripts/migrate-mongo-to-postgres.py`)

O projeto v2 usa **PostgreSQL**, **FastAPI** e o código em `app/`.
