# Validar tudo e colocar em produção

Guia objetivo: o que rodar para **validar** antes de release e o que configurar para **produção**.

---

## 1. Validar tudo (antes de subir / fazer release)

### 1.1 Ambiente mínimo

- **PostgreSQL** rodando (ex.: `docker-compose up -d`).
- **.env** na raiz (pode copiar de `.env.example`) com pelo menos:
  - `DATABASE_URL` apontando para o banco (ex.: `postgresql://automasei:automasei_dev_password@localhost:5432/automasei`).
  - `AUTH_DEV_MODE=true` para os testes de API sem token.

### 1.2 Migrations

```bash
alembic upgrade head
```

### 1.3 Testes automatizados

```bash
# Browsers do Playwright (uma vez por máquina)
playwright install chromium

# Testes de API + scraping (sem E2E) — exige Postgres rodando
pytest tests/ -v -m "not e2e"
```

- Se o Postgres não estiver rodando, os testes de API falham (connection refused).
- Se o Chromium do Playwright não estiver instalado, os testes de scraping com browser falham; os unitários do scraper (ex.: `_normalize_link`) rodam igual.

### 1.4 (Opcional) Testes E2E

Com **API e frontend** rodando em dois terminais:

```bash
# Terminal 1
uvicorn app.api.main:app --host 0.0.0.0 --port 8000

# Terminal 2
cd frontend && npm run dev
```

Depois:

```bash
pytest -m e2e -v
```

### 1.5 (Opcional) Validação manual do fluxo

1. Rodar seed: `python scripts/seed-test-data.py`
2. Abrir frontend (ex.: http://localhost:3000) e admin (ex.: http://localhost:3000/admin/requests).
3. Seguir o fluxo: criar orçamento → aceitar como cliente (usando `localStorage.devUserEmail`) → confirmar pagamento e entregar como admin.

Detalhes no [TESTING.md](TESTING.md).

---

## 2. Colocar em produção

### 2.1 Variáveis de ambiente (obrigatórias)

| Variável | Produção |
|----------|----------|
| `AUTH_DEV_MODE` | **false** (obrigatório; senão a API aceita qualquer request sem token). |
| `DATABASE_URL` | URL do PostgreSQL de produção (ex.: serviço gerenciado ou container). |
| `AUTOMASEI_ENCRYPTION_KEY` | Chave Fernet em base64 para criptografar credenciais SEI. Gerar: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`. |
| `FIREBASE_CREDENTIALS` | Caminho para o JSON da service account do Firebase (Auth + Storage). |
| `FIREBASE_STORAGE_BUCKET` | Nome do bucket (ex.: `seu-projeto.appspot.com`). |
| `PAYMENT_PROVIDER` | Ex.: `manual` (admin confirma) ou o provider que for usar. |

### 2.2 Firebase

- Projeto Firebase com **Authentication** (e-mail/senha ou o método que o frontend usar).
- **Storage** para os documentos; configurar regras e CORS conforme necessário.
- Service account com permissão para Auth e Storage; arquivo JSON em servidor seguro e `FIREBASE_CREDENTIALS` apontando para ele.

### 2.3 Banco de dados

- PostgreSQL de produção criado (ex.: RDS, Cloud SQL, ou container).
- Rodar migrations na base de produção: `alembic upgrade head`.
- **Não** rodar `scripts/seed-test-data.py` em produção (só para ambiente de teste).

### 2.4 Deploy da API

- Expor a API (ex.: container com uvicorn, ou Gunicorn + Uvicorn atrás de um proxy).
- Garantir que o processo leia o `.env` ou as variáveis de ambiente de produção (sem `AUTH_DEV_MODE=true`).
- Em Docker: usar `env_file` ou variáveis no `docker-compose` / orquestrador.

### 2.5 Deploy do frontend

- Build: `cd frontend && npm run build`.
- Configurar `NUXT_PUBLIC_API_BASE` para a URL pública da API (ex.: `https://api.seudominio.com`).
- Servir o output (ex.: `output/` do Nuxt) com Nginx, CDN ou serviço de hospedagem estática.

### 2.6 Checklist rápido

- [ ] `AUTH_DEV_MODE=false`
- [ ] `DATABASE_URL` de produção
- [ ] `AUTOMASEI_ENCRYPTION_KEY` definida
- [ ] Firebase: credentials + bucket
- [ ] `alembic upgrade head` no banco de produção
- [ ] API no ar e acessível
- [ ] Frontend com `NUXT_PUBLIC_API_BASE` apontando para a API
- [ ] (Opcional) HTTPS e domínio configurados

---

Resumindo: **validar** = Postgres + migrations + `pytest tests/ -v -m "not e2e"` (e, se quiser, E2E e fluxo manual). **Produção** = desligar modo dev, configurar banco, Firebase, chave de criptografia e fazer deploy da API e do frontend com as variáveis corretas.
