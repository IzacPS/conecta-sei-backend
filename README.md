# ConectaSEI Backend

API REST do ConectaSEI (FastAPI + PostgreSQL/ParadeDB). Autenticação Firebase; multi-tenant (instituições + processos SEI).

## Repositório

- **GitHub**: [IzacPS/conecta-sei-backend](https://github.com/IzacPS/conecta-sei-backend)

## Quick start

```bash
# Dependências
pip install -r requirements-new.txt

# Postgres + API com Docker
docker compose up -d
# API: http://localhost:8000  |  Docs: http://localhost:8000/docs

# Ou local: configure .env (copie de .env.example) e
alembic upgrade head
uvicorn app.api.main:app --reload --host 0.0.0.0 --port 8000
```

## Variáveis de ambiente

Copie `.env.example` para `.env`. Principais: `DATABASE_URL`, `FIREBASE_CREDENTIALS` (JSON inline), `FIREBASE_STORAGE_BUCKET`, `CONECTASEI_ENCRYPTION_KEY`, `AUTH_DEV_MODE`.

## Documentação

- [RUN_LOCAL.md](RUN_LOCAL.md) – rodar local
- [MONGODB_TO_POSTGRES_MIGRATION.md](MONGODB_TO_POSTGRES_MIGRATION.md) – migração do legado
- [CLAUDE.md](CLAUDE.md) – visão geral para assistentes de código

## Publicar neste repositório

Se este conteúdo foi gerado a partir do monorepo e o repositório remoto já existe:

```bash
cd conecta-sei-backend
git init
git remote add origin https://github.com/IzacPS/conecta-sei-backend.git
git add .
git commit -m "chore: initial backend split from monorepo"
git branch -M main
git push -u origin main
```
