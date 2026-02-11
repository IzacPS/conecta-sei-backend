# Como testar o fluxo Scraper + Pagamento (v2.0)

Este guia descreve como subir o ambiente e testar o fluxo completo: solicitação → orçamento → aceite/pagamento → entrega, usando dados de seed e modo dev (sem Firebase).

## Tipos de teste

| Tipo | O que testa | Como rodar |
|------|-------------|------------|
| **API** | Endpoints FastAPI (institutions, auth, health, admin, orders) | `pytest tests/ -v` (exclui E2E) ou `pytest tests/ -v -m "not e2e"` |
| **Scraping** | Scraper SEI v4.2.0 com fixtures HTML (sem SEI ao vivo) | `pytest tests/scraping/ -v` |
| **E2E** | Frontend no browser (Playwright) — cliente e admin | `pytest -m e2e -v` (exige API + frontend rodando) |

**Validar tudo (API + scraping, sem E2E):**

```bash
# 1. Subir Postgres (mesmo do dev): docker-compose up -d
# 2. .env.test usa o mesmo DATABASE_URL (5432) por padrão
# 3. Para scraping com browser: playwright install chromium
pytest tests/ -v -m "not e2e"
```

- **API:** exige PostgreSQL rodando (ex.: `docker-compose up -d`).
- **Scraping (Playwright):** testes com fixture HTML exigem `playwright install chromium`; caso contrário são pulados.

**Validar incluindo E2E** (com API e frontend já rodando):

```bash
pytest tests/ -v
```

## Pré-requisitos

- **Docker** (PostgreSQL via `docker-compose`)
- **Python 3.11+** (backend)
- **Node 18+** (frontend Nuxt)
- **.env** configurado a partir de `.env.example`

## 1. Configurar ambiente

### 1.1 Variáveis de ambiente

Na raiz do projeto:

```bash
cp .env.example .env
```

Edite `.env` e confira pelo menos:

- `DATABASE_URL=postgresql://automasei:automasei_dev_password@localhost:5432/automasei`
- `AUTH_DEV_MODE=true` (para testar sem token Firebase)
- `PAYMENT_PROVIDER=manual` (admin confirma pagamento no painel)

Firebase pode ficar em branco em dev.

### 1.2 Subir banco e migrations

**Windows (PowerShell):**

```powershell
.\scripts\run-local.ps1
```

Isso cria `.env` se não existir, sobe o PostgreSQL com Docker e roda `alembic upgrade head`.

**Ou manualmente:**

```bash
docker-compose up -d
alembic upgrade head
```

### 1.3 Seed de dados de teste

Cria usuário admin, usuário cliente e uma solicitação em `pending_scraper`:

```bash
python scripts/seed-test-data.py
```

Saída esperada:

- Admin: `dev@automasei.local` (role=admin)
- Cliente: `client@automasei.local` (role=user)
- Instituição inativa "SEI Teste"
- Uma `PipelineRequest` em `pending_scraper` do cliente

## 2. Subir API e frontend

**Terminal 1 – API:**

```bash
uvicorn app.api.main:app --reload --host 0.0.0.0 --port 8000
```

**Terminal 2 – Frontend:**

```bash
cd frontend && npm install && npm run dev
```

- Frontend: http://localhost:3000  
- API docs: http://localhost:8000/docs  
- ReDoc: http://localhost:8000/redoc  

## 3. Modo dev e impersonation

Com `AUTH_DEV_MODE=true`:

- **Sem header:** a API trata como **admin** (`dev@automasei.local`).
- **Com header** `X-Dev-User-Email: client@automasei.local`: a API trata como **cliente** (útil para testar endpoints do cliente no Swagger ou em chamadas manuais).

No Swagger (http://localhost:8000/docs), em "Authorize" não é necessário preencher Bearer. Para simular o cliente, adicione um header customizado (se o Swagger permitir) ou use curl/Postman:

```bash
curl -H "X-Dev-User-Email: client@automasei.local" http://localhost:8000/api/orders/
```

## 4. Fluxo de teste E2E

### 4.1 Como admin (sem header)

1. **Listar solicitações pendentes de orçamento**  
   `GET /api/admin/requests?status=pending_scraper`  
   Deve aparecer a solicitação criada pelo seed.

2. **Criar orçamento (ScraperOrder)**  
   `POST /api/admin/requests/{pipeline_request_id}/quote`  
   Body exemplo: `{"setup_price": 100, "monthly_price": 50, "currency": "BRL", "admin_notes": "Orçamento teste"}`

3. **Listar pedidos**  
   `GET /api/admin/orders`  
   O pedido deve estar com status `quote_sent`.

4. **Quando o “cliente” aceitar e “pagar”:** confirmar pagamento  
   `POST /api/admin/orders/{order_id}/confirm-payment`  
   (Body conforme o endpoint, ex. `payment_id` se houver.)

5. **Marcar como entregue**  
   `POST /api/admin/orders/{order_id}/deliver`  
   (Body conforme o endpoint.)

### 4.2 Como cliente (com `X-Dev-User-Email: client@automasei.local`)

1. **Minhas solicitações**  
   `GET /api/pipelines/requests` ou `GET /api/orders/`  
   Deve listar a solicitação em `pending_scraper` e, após o admin criar orçamento, o pedido em `quote_sent`.

2. **Detalhe da solicitação**  
   `GET /api/pipelines/requests/{id}` ou `GET /api/orders/{order_id}`  
   Ver orçamento (setup_price, monthly_price, etc.).

3. **Aceitar orçamento**  
   `POST /api/orders/{order_id}/accept`  
   (Body conforme o schema.)

4. **Pagamento:** com `PAYMENT_PROVIDER=manual`, o cliente não paga online; o admin confirma no painel (passo 4.1.4).

### 4.3 Frontend

- **Cliente:** http://localhost:3000/my-requests (e detalhe em `/my-requests/{id}`).  
  Em dev, o frontend envia o header `X-Dev-User-Email` quando existe `localStorage.devUserEmail`. No console do navegador: `localStorage.setItem('devUserEmail', 'client@automasei.local')` e recarregue a página para agir como cliente.

- **Admin:** http://localhost:3000/admin, http://localhost:3000/admin/requests, http://localhost:3000/admin/orders e detalhe do pedido (sem definir `devUserEmail` = admin).

## 5. Testes E2E com Playwright

O projeto já usa **Playwright** no backend (scraping SEI). Os mesmos binários servem para testes E2E da aplicação: o Playwright abre o frontend no navegador e valida o fluxo.

### 5.1 Pré-requisitos

- API e frontend rodando (passos 1 e 2 acima).
- Seed aplicado (`python scripts/seed-test-data.py`).
- Playwright instalado: `pip install -r requirements-new.txt` (já inclui `playwright`). Na primeira vez: `playwright install chromium`.

### 5.2 Executar os E2E

Na raiz do projeto:

```bash
pytest tests/e2e/test_flow_playwright.py -m e2e -v
```

Se o frontend não estiver em execução, os testes são **pulados** (não falham). Para rodar só os E2E (sem os testes unitários da API):

```bash
pytest -m e2e -v
```

Variável opcional para outra URL do frontend:

```bash
E2E_FRONTEND_URL=http://localhost:3000 pytest -m e2e -v
```

### 5.3 O que os E2E cobrem

- **Cliente:** abre `/my-requests` com `devUserEmail=client@automasei.local` e verifica que a página "Minhas solicitações" carrega.
- **Admin:** abre `/admin/requests` (sem impersonation) e verifica que "Solicitações de pipeline" aparece.

Assim você automatiza o “teste manual” do fluxo usando o mesmo Playwright que já está no projeto.

## 6. Resumo rápido

| Passo | Quem    | Ação |
|-------|--------|------|
| 1     | Você    | `.\scripts\run-local.ps1` → `python scripts/seed-test-data.py` |
| 2     | Você    | Subir API (uvicorn) e frontend (npm run dev) |
| 3     | Admin   | Listar solicitações → criar orçamento para a solicitação do seed |
| 4     | Cliente | Aceitar orçamento (Swagger/curl com X-Dev-User-Email ou frontend com `localStorage.devUserEmail`) |
| 5     | Admin   | Confirmar pagamento → marcar como entregue |
| E2E   | Automático | `pytest -m e2e -v` (com API e frontend rodando) |

Tudo pode ser testado com `.env` (sem credenciais hardcoded) e com Docker apenas para o PostgreSQL; o restante roda local.

**Validar tudo e colocar em produção:** ver [VALIDATION_AND_PRODUCTION.md](VALIDATION_AND_PRODUCTION.md).
