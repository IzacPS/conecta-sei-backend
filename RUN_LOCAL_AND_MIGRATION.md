# Rodar tudo localmente e migração MongoDB → Postgres

## 1. Rodar a aplicação localmente

### Passo a passo (Windows)

1. **Ambiente e banco**
   ```powershell
   .\scripts\run-local.ps1
   ```
   Isso cria/atualiza `.env`, sobe o PostgreSQL (Docker) e roda `alembic upgrade head`.

2. **Dados de teste (opcional)**
   ```powershell
   python scripts/seed-test-data.py
   ```
   Cria usuário admin, cliente e uma solicitação `pending_scraper` para testar o fluxo.

3. **API**
   ```powershell
   uvicorn app.api.main:app --reload --host 0.0.0.0 --port 8000
   ```
   Docs: http://localhost:8000/docs

4. **Frontend**
   ```powershell
   cd frontend && npm install && npm run dev
   ```
   App: http://localhost:3000

5. **Testes**
   ```powershell
   playwright install chromium   # uma vez
   pytest tests/ -v -m "not e2e"
   ```
   (E2E: só com API + frontend rodando: `pytest -m e2e -v`.)

Detalhes: [RUN_LOCAL.md](RUN_LOCAL.md), [TESTING.md](TESTING.md), [VALIDATION_AND_PRODUCTION.md](VALIDATION_AND_PRODUCTION.md).

---

## 2. Preciso migrar do MongoDB para a base local?

Só se você **já usa o v1 (MongoDB)** e quer trazer esses dados para o **Postgres local (v2)**.

- **Não tem dados no MongoDB (ou está começando do zero):** não precisa migrar. Use só o Postgres (run-local, seed, API, frontend).
- **Tem processos/configurações no MongoDB do v1:** aí faz sentido rodar a migração para ter os mesmos dados no Postgres e testar o v2 com dados reais.

Resumo:

| Situação                         | Ação |
|----------------------------------|------|
| Só testar v2 com dados de teste | Seed + API + frontend. Migração não necessária. |
| Trazer dados do v1 (Mongo) pro v2 (Postgres) | Rodar o script de migração (ver seção 3). |

---

## 3. Como fazer a migração MongoDB → Postgres

### 3.1 O que é migrado

- **MongoDB** (v1): collections `processos` e `configuracoes` (database `sei_database`).
- **PostgreSQL** (v2): tabelas `processes`, `system_configuration` e uma instituição “Legacy” para vincular os processos.

O script lê só do MongoDB (não altera) e escreve no Postgres. Faz backup em JSON do Mongo antes (opcional).

### 3.2 Conexão do MongoDB

O script usa a conexão definida em `connect_mongo.py` (raiz do projeto). Para não depender da connection string hardcoded, você pode:

- Colocar a URL no ambiente, por exemplo: `MONGO_URI=mongodb+srv://...`
- Ajustar `connect_mongo.py` para usar `os.getenv("MONGO_URI", CONNECTION_STRING)`.

(Se não tiver MongoDB rodando ou acessível, o script falha ao conectar.)

### 3.3 Script atualizado (schema v2)

O arquivo **`migrate_mongodb_to_postgres.py`** na raiz foi feito para um schema antigo (outros imports e nomes de colunas). O schema v2 atual usa, por exemplo:

- **Process:** `process_number` (não `numero_processo`), `access_type`, `best_current_link`, `documents_data`, `category`, `category_status`, `no_valid_links`, `nickname`, etc.
- **Institution:** `id` inteiro (não string), `name`, `sei_url`, `is_active`, `user_id`, `extra_metadata` (sem campos como `scraper_version` do script antigo).

Por isso existe um script atualizado que segue o schema v2:

- **`scripts/migrate-mongo-to-postgres.py`** — usa `app.database` e os modelos atuais (Institution, Process, SystemConfiguration).

### 3.4 Como rodar a migração

1. **Postgres** rodando e migrations aplicadas:
   ```powershell
   docker-compose up -d
   alembic upgrade head
   ```

2. **.env** com `DATABASE_URL` apontando para o Postgres local (ou de teste).

3. **MongoDB** acessível (e, se quiser, `MONGO_URI` no ambiente).

4. **Dry-run** (só simula, não grava no Postgres):
   ```powershell
   python scripts/migrate-mongo-to-postgres.py --dry-run
   ```

5. **Migração de verdade** (com backup do Mongo):
   ```powershell
   python scripts/migrate-mongo-to-postgres.py
   ```

6. **Limpar Postgres e migrar de novo** (cuidado: apaga dados atuais do Postgres):
   ```powershell
   python scripts/migrate-mongo-to-postgres.py --clear-postgres
   ```
   (O script pede confirmação.)

Opções úteis: `--skip-backup`, `--verbose`, `--batch-size 200`. Ver `python scripts/migrate-mongo-to-postgres.py --help`.

### 3.5 Depois da migração

- Os processos ficam ligados à instituição **“Legacy (MongoDB)”**.
- Configure as **credenciais de acesso ao SEI** para essa instituição no v2 (pela API ou admin), pois o script não migra senhas para o novo modelo de credenciais.
- As configurações do Mongo (`configuracoes`) viram linhas em `system_configuration` (campo `key` = tipo, `value` = JSONB).

---

## 4. Resumo

| Objetivo                         | O que fazer |
|----------------------------------|-------------|
| Rodar tudo local e testar       | `run-local.ps1` → seed → API → frontend → pytest (opcional). |
| Validar antes de produção       | Ver [VALIDATION_AND_PRODUCTION.md](VALIDATION_AND_PRODUCTION.md). |
| Trazer dados do Mongo para Postgres | Usar `scripts/migrate-mongo-to-postgres.py` (dry-run antes). |

Se o script de migração der erro de import ou de coluna, confira se está usando o script em `scripts/migrate-mongo-to-postgres.py` (atualizado para o schema v2) e não o `migrate_mongodb_to_postgres.py` da raiz (antigo).
