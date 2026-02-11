# Rodar AutomaSEI v2 localmente (versão mínima)

Para testar a aplicação na sua máquina **sem Firebase** e **sem Playwright** (apenas API + frontend + banco).

---

## Opção 1: Tudo com Docker (recomendado para “subir tudo”)

Com **um comando** você sobe Postgres, backend e frontend em containers:

```powershell
docker compose up -d
```

- **Frontend:** http://localhost:3000  
- **Backend API / Docs:** http://localhost:8000 e http://localhost:8000/docs  
- As migrations rodam automaticamente na subida do backend.

Para ver os logs: `docker compose logs -f`. Para parar: `docker compose down`.

**Rebuildar um container** (ex.: frontend após mudar código): `docker compose up -d --build frontend`. Para backend: `docker compose up -d --build backend`.

**Frontend não atualiza (versão antiga)?** Rebuild sem cache: `docker compose build --no-cache frontend` e depois `docker compose up -d frontend`. Se ainda vir a tela antiga, **Ctrl+Shift+R** no navegador ou aba anônima.

**Porta 3000 em uso?** Ver processo: `Get-NetTCPConnection -LocalPort 3000 -State Listen | % { Get-Process -Id $_.OwningProcess }`. Matar: `Stop-Process -Id <PID> -Force`.

---

## Opção 2: Banco no Docker, backend e frontend no host

Use os passos abaixo (1–5) se quiser rodar backend e frontend na sua máquina (com hot-reload) e só o Postgres no Docker.

---

## Pré-requisitos

- **Docker** (para PostgreSQL + ParadeDB) — obrigatório na Opção 1
- **Python 3.11+** (backend) — Opção 2
- **Node.js 18+** (frontend) — Opção 2

---

## 1. Subir o banco

```powershell
cd c:\Users\izacc\dev\git\SEI_Uno_Trade
docker-compose up -d
```

Isso sobe o PostgreSQL (ParadeDB) na porta **5432** com:
- usuário: `automasei`
- senha: `automasei_dev_password`
- banco: `automasei`

---

## 2. Configurar o backend

Crie um arquivo **`.env`** na raiz do projeto (ou copie de `.env.example`):

```env
# Obrigatório para rodar local
DATABASE_URL=postgresql://automasei:automasei_dev_password@localhost:5432/automasei
AUTH_DEV_MODE=true

# Opcional (já tem valor padrão para dev)
# AUTOMASEI_ENCRYPTION_KEY=automasei-v2-default-key-CHANGE-IN-PRODUCTION
```

- **`AUTH_DEV_MODE=true`** faz a API aceitar requisições **sem token**. Um usuário fixo `dev@automasei.local` é usado. Assim você não precisa de Firebase para testar.

---

## 3. Migrations

```powershell
# Na raiz do projeto, com o venv ativado
alembic upgrade head
```

---

## 4. Instalar dependências e rodar o backend

```powershell
# Criar venv (se ainda não tiver)
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Instalar dependências
pip install -r requirements-new.txt

# Subir a API
uvicorn app.api.main:app --reload --host 0.0.0.0 --port 8000
```

A API fica em **http://localhost:8000**  
- Docs: http://localhost:8000/docs  
- Health: http://localhost:8000/health  

---

## 5. Frontend

Em **outro terminal**:

```powershell
cd frontend
npm install
npm run dev
```

O frontend sobe em **http://localhost:3000**.

Se você **não** configurou variáveis Firebase no frontend, o app usa um usuário de desenvolvimento e você já entra “logado” (sem tela de login de verdade).  
Para usar login real (Firebase), configure no `.env` do frontend ou em `nuxt.config.ts` as variáveis `FIREBASE_*` e defina `NUXT_PUBLIC_API_BASE=http://localhost:8000` se a API estiver em outra porta.

---

## Resumo dos comandos (versão mínima)

| Onde        | Comando |
|------------|---------|
| Raiz       | `docker-compose up -d` |
| Raiz       | `alembic upgrade head` |
| Raiz       | `uvicorn app.api.main:app --reload --host 0.0.0.0 --port 8000` |
| frontend/  | `npm install` e `npm run dev` |

Abra **http://localhost:3000** e use o fluxo (dashboard, instituições, etc.). A API não exige token quando `AUTH_DEV_MODE=true`.

---

## O que **não** está na versão mínima

- **Firebase Auth**: login real (com e-mail/senha) exige projeto Firebase e variáveis no frontend.
- **Firebase Storage**: upload de PDFs para o bucket exige `FIREBASE_CREDENTIALS` e `FIREBASE_STORAGE_BUCKET` no backend.
- **Extração/Playwright**: rodar extração de processos do SEI exige Playwright instalado (`playwright install chromium`) e credenciais SEI configuradas (instituição com credenciais).

Para apenas **testar a API** sem frontend: use **http://localhost:8000/docs** (Swagger). Com `AUTH_DEV_MODE=true`, endpoints protegidos aceitam requisições sem header `Authorization`.

---

## Migração MongoDB → Postgres (quando tiver dados do v1)

Se você usa o v1 com MongoDB e quer trazer esses dados para o Postgres local (v2), use o script de migração e o guia completo:

- **[RUN_LOCAL_AND_MIGRATION.md](RUN_LOCAL_AND_MIGRATION.md)** — quando migrar, como rodar o script atualizado (`scripts/migrate-mongo-to-postgres.py`) e o que fazer depois.
