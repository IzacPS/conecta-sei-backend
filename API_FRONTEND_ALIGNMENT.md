# Alinhamento Backend ↔ Frontend (v2)

Verificação feita entre o frontend Nuxt atual e a API FastAPI. O backend está **alinhado** com o que o frontend consome.

---

## Resumo

| Área | Status | Observações |
|------|--------|-------------|
| Auth | ✅ | GET/PUT `/auth/me`, POST `/auth/register` |
| Institutions | ✅ | CRUD, `/stats`, `/schedule`, `/schedule/toggle` |
| Processes | ✅ | List, get, put, pending-categorization, search |
| Documents | ✅ | `/history`, `/by-process/:id/urls`; `total` em history corrigido para paginação |
| Extraction | ✅ | POST extract, GET extraction-tasks (global e por instituição) |
| Pipelines | ✅ | POST `/pipelines/request`, GET `/pipelines/available-versions` |
| Pipeline progress (SSE) | ✅ | GET `/institutions/:id/pipeline/progress/:taskId` (pipeline_stages) |
| Schedules | ✅ | GET/POST `/institutions/:id/schedule`, POST `.../schedule/toggle` |
| Admin | ✅ | stats, pipeline-requests, orders (CRUD, confirm-payment, deliver) |
| Orders (cliente) | ✅ | GET /orders, GET /orders/:id, accept, reject, checkout |

---

## Endpoints usados pelo frontend

### Auth
- `GET /auth/me` – perfil do usuário (layout, settings)
- `PUT /auth/me` – atualizar perfil (display_name, avatar_url)
- `POST /auth/register` – registrar/sincronizar usuário (Firebase → DB)

### Institutions
- `GET /institutions` – lista (items, total)
- `GET /institutions/:id` – detalhe
- `PUT /institutions/:id` – atualizar (name, sei_url, is_active)
- `DELETE /institutions/:id` – excluir
- `GET /institutions/:id/stats` – estatísticas
- `GET /institutions/:id/schedule` – agendamento (404 quando não existe; frontend trata no `catch`)
- `POST /institutions/:id/schedule` – criar/atualizar agendamento
- `POST /institutions/:id/schedule/toggle` – ativar/desativar
- `POST /institutions/:id/processes/extract` – iniciar extração

### Processes
- `GET /processes` – lista (params: institution_id, access_type, category, skip, limit) → items, total
- `GET /processes/pending-categorization` – total de pendentes
- `GET /processes/:id` – detalhe (incl. documents_data)
- `PUT /processes/:id` – atualizar (nickname, category, category_status)
- `POST /processes/search` – busca BM25 (body: query, institution_id, limit)

### Documents
- `GET /documents/history` – histórico (params: limit, skip) → items, **total** (total geral para paginação)
- `GET /documents/by-process/:process_id/urls` – URLs de download por processo

### Extraction
- `GET /extraction-tasks` – todas as tarefas do usuário (params: limit, skip) → tasks, total
- `GET /institutions/:id/extraction-tasks` – tarefas da instituição
- `GET /extraction-tasks/:id` – status de uma tarefa (uso implícito / progresso)

### Pipelines
- `POST /pipelines/request` – solicitar pipeline (body: institution_name, sei_url, sei_email, sei_password, sei_version?)
- `GET /pipelines/available-versions` – versões SEI disponíveis para o select

### Pipeline progress (SSE)
- `GET /institutions/:institution_id/pipeline/progress/:task_id` – stream SSE (status, progress, complete, error)  
  Implementado em `app/api/routers/pipeline_stages.py`.

### Admin
- `GET /admin/stats` – estatísticas admin
- `GET /admin/pipeline-requests` – lista (param: status)
- `POST /admin/orders` – criar orçamento (body: pipeline_request_id, setup_price, monthly_price, …)
- `GET /admin/orders` – lista (param: status)
- `GET /admin/orders/:id` – detalhe
- `PUT /admin/orders/:id` – atualizar
- `POST /admin/orders/:id/confirm-payment` – confirmar pagamento
- `POST /admin/orders/:id/deliver` – marcar como entregue

### Orders (cliente)
- `GET /orders` – meus pedidos
- `GET /orders/:id` – detalhe
- `POST /orders/:id/accept` – aceitar orçamento
- `POST /orders/:id/reject` – rejeitar
- `POST /orders/:id/checkout?payment_type=setup` – gerar checkout

---

## Ajuste feito

- **GET /documents/history**: o campo `total` passou a retornar o **total de registros** (count sem limit), e não apenas `len(items)`, para que a paginação no frontend funcione corretamente.

---

## Observações opcionais (não bloqueantes)

1. **GET /institutions/:id/schedule** – Quando não existe agendamento, a API retorna 404. O frontend trata no `catch` e mantém os valores default do formulário. Opcionalmente, a API poderia retornar 200 com um objeto “default” (ex.: schedule_type: interval, active: false) para evitar 404.
2. **Perfil (auth/me)** – O frontend exibe `profile?.created_at` em Settings; o schema atual de perfil não inclui `created_at`. Pode ser adicionado no backend se quiser exibir “Membro desde” com dados reais.
