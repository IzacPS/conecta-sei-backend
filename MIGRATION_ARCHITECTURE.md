# AutomaSEI - Arquitetura de Migração Web

**Data:** 2025-12-13
**Versão Atual:** 1.0.10 (Desktop Python/tkinter)
**Versão Alvo:** 2.0.0 (Web Application)

---

## Visão Geral da Migração

Migração completa do AutomaSEI de aplicação desktop para aplicação web moderna full-stack.

### Objetivos

1. **Frontend Moderno**: Nuxt 4 + Nuxt UI v4 + Tailwind CSS v3.4+
2. **Arquitetura API-First**: Backend FastAPI totalmente separado
3. **Banco de Dados**: MongoDB Atlas → PostgreSQL 15+
4. **Pipeline Otimizado**: Melhorias na extração e monitoramento
5. **Multi-usuário**: Suporte a múltiplos usuários e organizações
6. **Real-time**: WebSocket para atualizações em tempo real

---

## Stack Tecnológico

### Frontend
- **Framework**: Nuxt 4 (latest - Vue 3 + Vite 5)
- **UI Library**: Nuxt UI v4 (Radix Vue + Tailwind CSS v3.4+)
- **Estilização**: Tailwind CSS v3.4+ com configuração customizada
- **State Management**: Pinia 2.x (store oficial do Vue)
- **HTTP Client**: ofetch (built-in do Nuxt 4)
- **Real-time**: WebSocket nativo ou Socket.io-client
- **Autenticação**: JWT + httpOnly cookies
- **Charts**: Chart.js ou Apache ECharts
- **Tables**: TanStack Table Vue
- **Forms**: Vee-Validate + Zod
- **Dates**: date-fns ou Day.js
- **PDF Viewer**: Vue-PDF-Embed

### Backend
- **Framework**: FastAPI 0.104+ (Python 3.11+)
- **ASGI Server**: Uvicorn com workers
- **ORM**: SQLAlchemy 2.0 + Alembic (migrations)
- **Validation**: Pydantic v2
- **Database**: PostgreSQL 15+
- **Cache**: Redis 7+
- **Task Queue**: Celery 5.3+ + Redis broker
- **Web Automation**: Playwright (mantido)
- **API Docs**: OpenAPI/Swagger (auto-gerado)
- **Auth**: JWT (python-jose) + OAuth2
- **Email**: Microsoft Graph API (mantido)

### Infrastructure & DevOps
- **Containers**: Docker + Docker Compose
- **Reverse Proxy**: Nginx
- **Monitoring**: Prometheus + Grafana
- **Logs**: Loki + Promtail
- **CI/CD**: GitHub Actions
- **Environment**: Dev Containers

---

## Arquitetura de Alto Nível

```
┌─────────────────────────────────────────────────────────────┐
│                  FRONTEND (Nuxt 4 SPA)                      │
│                                                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │Dashboard │  │Processos │  │Documentos│  │  Jobs    │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                 │
│  │Settings  │  │Reports   │  │ Profile  │                 │
│  └──────────┘  └──────────┘  └──────────┘                 │
└─────────────────────────────────────────────────────────────┘
                            │
                    HTTPS / WebSocket
                            │
┌─────────────────────────────────────────────────────────────┐
│              NGINX (Reverse Proxy + SSL)                    │
└─────────────────────────────────────────────────────────────┘
                            │
              ┌─────────────┴─────────────┐
              │                           │
              ▼                           ▼
┌──────────────────────┐      ┌──────────────────────┐
│  FastAPI Backend     │      │  WebSocket Server    │
│  (REST API)          │      │  (Real-time events)  │
│                      │      └──────────────────────┘
│  • Authentication    │
│  • Business Logic    │
│  • Data Access       │
└──────────────────────┘
            │
    ┌───────┼────────┬────────┬────────┐
    │       │        │        │        │
    ▼       ▼        ▼        ▼        ▼
┌────────┐ ┌─────┐ ┌──────┐ ┌──────┐ ┌─────────┐
│Postgres│ │Redis│ │Celery│ │S3/   │ │Playwright│
│  DB    │ │Cache│ │Worker│ │Share │ │ Browser │
└────────┘ └─────┘ └──────┘ │Point │ └─────────┘
                             └──────┘
```

---

## Estrutura de Diretórios Completa

```
SEI_Uno_Trade/
│
├── frontend/                              # Aplicação Nuxt 4
│   ├── .nuxt/                            # Build artifacts (gitignored)
│   ├── .output/                          # Production build (gitignored)
│   │
│   ├── app/                              # Nuxt 4 app directory
│   │   ├── assets/                       # Assets (CSS, SCSS, fonts)
│   │   │   ├── css/
│   │   │   │   └── main.css             # Tailwind base
│   │   │   └── fonts/
│   │   │
│   │   ├── components/                   # Vue components
│   │   │   ├── dashboard/
│   │   │   │   ├── StatsCard.vue
│   │   │   │   ├── ProcessChart.vue
│   │   │   │   ├── RecentActivity.vue
│   │   │   │   └── QuickActions.vue
│   │   │   │
│   │   │   ├── process/
│   │   │   │   ├── ProcessTable.vue
│   │   │   │   ├── ProcessDetail.vue
│   │   │   │   ├── ProcessFilters.vue
│   │   │   │   ├── ProcessForm.vue
│   │   │   │   ├── CategoryBadge.vue
│   │   │   │   └── LinksList.vue
│   │   │   │
│   │   │   ├── document/
│   │   │   │   ├── DocumentTable.vue
│   │   │   │   ├── DocumentViewer.vue
│   │   │   │   ├── DocumentPreview.vue
│   │   │   │   └── DocumentTimeline.vue
│   │   │   │
│   │   │   ├── job/
│   │   │   │   ├── JobCard.vue
│   │   │   │   ├── JobProgress.vue
│   │   │   │   ├── JobLogs.vue
│   │   │   │   └── PipelineControls.vue
│   │   │   │
│   │   │   ├── ui/                       # Base UI components
│   │   │   │   ├── Button.vue
│   │   │   │   ├── Card.vue
│   │   │   │   ├── Modal.vue
│   │   │   │   ├── Table.vue
│   │   │   │   ├── Pagination.vue
│   │   │   │   ├── Loading.vue
│   │   │   │   ├── Toast.vue
│   │   │   │   └── EmptyState.vue
│   │   │   │
│   │   │   └── layout/
│   │   │       ├── AppHeader.vue
│   │   │       ├── AppSidebar.vue
│   │   │       ├── AppFooter.vue
│   │   │       └── Breadcrumbs.vue
│   │   │
│   │   ├── composables/                  # Vue composables
│   │   │   ├── useAuth.ts               # Authentication
│   │   │   ├── useApi.ts                # API client
│   │   │   ├── useProcessos.ts          # Process operations
│   │   │   ├── useDocumentos.ts         # Document operations
│   │   │   ├── useJobs.ts               # Job management
│   │   │   ├── useWebSocket.ts          # Real-time updates
│   │   │   ├── useNotifications.ts      # Toast notifications
│   │   │   ├── useFilters.ts            # Table filters
│   │   │   └── usePagination.ts         # Pagination logic
│   │   │
│   │   ├── layouts/                      # Nuxt layouts
│   │   │   ├── default.vue              # Main layout (sidebar + header)
│   │   │   ├── auth.vue                 # Auth layout (login/register)
│   │   │   └── minimal.vue              # Minimal layout (no sidebar)
│   │   │
│   │   ├── middleware/                   # Route middleware
│   │   │   ├── auth.ts                  # Require authentication
│   │   │   ├── guest.ts                 # Guest only (login page)
│   │   │   └── admin.ts                 # Admin only
│   │   │
│   │   ├── pages/                        # Pages (auto-routing)
│   │   │   ├── index.vue                # Dashboard (/)
│   │   │   ├── login.vue                # Login page
│   │   │   │
│   │   │   ├── processos/
│   │   │   │   ├── index.vue            # Process list
│   │   │   │   └── [id]/
│   │   │   │       ├── index.vue        # Process detail
│   │   │   │       └── documentos.vue   # Process documents
│   │   │   │
│   │   │   ├── documentos/
│   │   │   │   └── index.vue            # All documents
│   │   │   │
│   │   │   ├── jobs/
│   │   │   │   ├── index.vue            # Jobs dashboard
│   │   │   │   └── [id].vue             # Job detail
│   │   │   │
│   │   │   ├── configuracoes/
│   │   │   │   ├── index.vue            # Settings menu
│   │   │   │   ├── credenciais.vue      # SEI credentials
│   │   │   │   ├── notificacoes.vue     # Notifications
│   │   │   │   └── perfil.vue           # User profile
│   │   │   │
│   │   │   └── relatorios/
│   │   │       └── index.vue            # Reports
│   │   │
│   │   ├── plugins/                      # Nuxt plugins
│   │   │   ├── api.ts                   # API client setup
│   │   │   ├── websocket.client.ts      # WebSocket client
│   │   │   └── chart.client.ts          # Chart.js setup
│   │   │
│   │   └── utils/                        # Utility functions
│   │       ├── constants.ts
│   │       ├── formatters.ts            # Date, number formatters
│   │       ├── validators.ts            # Form validators
│   │       └── helpers.ts
│   │
│   ├── public/                           # Static files
│   │   ├── favicon.ico
│   │   ├── logo.svg
│   │   └── robots.txt
│   │
│   ├── server/                           # Nuxt server (optional)
│   │   └── api/
│   │       └── health.ts                # Health check
│   │
│   ├── stores/                           # Pinia stores
│   │   ├── auth.ts                      # Auth state
│   │   ├── processos.ts                 # Processes state
│   │   ├── documentos.ts                # Documents state
│   │   ├── jobs.ts                      # Jobs state
│   │   └── ui.ts                        # UI state (sidebar, theme)
│   │
│   ├── types/                            # TypeScript types
│   │   ├── api.ts                       # API response types
│   │   ├── models.ts                    # Data models
│   │   ├── enums.ts                     # Enums
│   │   └── index.ts                     # Re-exports
│   │
│   ├── .env.example                      # Environment template
│   ├── .gitignore
│   ├── nuxt.config.ts                   # Nuxt 4 config
│   ├── tailwind.config.ts               # Tailwind config
│   ├── tsconfig.json                    # TypeScript config
│   ├── package.json
│   └── README.md
│
├── backend/                              # FastAPI Backend
│   ├── alembic/                         # Database migrations
│   │   ├── versions/
│   │   │   └── 001_initial_schema.py
│   │   ├── env.py
│   │   └── script.py.mako
│   │
│   ├── app/
│   │   ├── api/                         # API endpoints
│   │   │   ├── v1/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── auth.py             # POST /login, /register, /refresh
│   │   │   │   ├── processos.py        # CRUD processes
│   │   │   │   ├── documentos.py       # CRUD documents
│   │   │   │   ├── jobs.py             # Job control
│   │   │   │   ├── configuracoes.py    # Settings
│   │   │   │   ├── relatorios.py       # Reports
│   │   │   │   └── usuarios.py         # User management
│   │   │   │
│   │   │   └── deps.py                 # Dependencies (get_db, get_current_user)
│   │   │
│   │   ├── core/                        # Core configuration
│   │   │   ├── __init__.py
│   │   │   ├── config.py               # Settings (Pydantic BaseSettings)
│   │   │   ├── security.py             # JWT, password hashing
│   │   │   ├── logging.py              # Logging setup
│   │   │   └── events.py               # Startup/shutdown events
│   │   │
│   │   ├── db/                          # Database
│   │   │   ├── __init__.py
│   │   │   ├── base.py                 # Base class, imports
│   │   │   ├── session.py              # Async session factory
│   │   │   └── init_db.py              # DB initialization
│   │   │
│   │   ├── models/                      # SQLAlchemy models
│   │   │   ├── __init__.py
│   │   │   ├── user.py                 # User model
│   │   │   ├── processo.py             # Processo model
│   │   │   ├── processo_link.py        # ProcessoLink model
│   │   │   ├── documento.py            # Documento model
│   │   │   ├── documento_history.py    # DocumentoHistory model
│   │   │   ├── configuracao.py         # Configuracao model
│   │   │   ├── notificacao.py          # Notificacao model
│   │   │   └── job_execution.py        # JobExecution model
│   │   │
│   │   ├── schemas/                     # Pydantic schemas (DTOs)
│   │   │   ├── __init__.py
│   │   │   ├── user.py                 # UserCreate, UserRead, UserUpdate
│   │   │   ├── processo.py             # ProcessoCreate, ProcessoRead, etc.
│   │   │   ├── documento.py            # DocumentoCreate, DocumentoRead, etc.
│   │   │   ├── auth.py                 # Token, LoginRequest
│   │   │   ├── job.py                  # JobCreate, JobRead, JobStatus
│   │   │   └── common.py               # Pagination, Response wrappers
│   │   │
│   │   ├── services/                    # Business logic
│   │   │   ├── __init__.py
│   │   │   ├── auth_service.py         # Authentication logic
│   │   │   ├── processo_service.py     # Process operations
│   │   │   ├── documento_service.py    # Document operations
│   │   │   ├── job_service.py          # Job management
│   │   │   ├── email_service.py        # Email notifications
│   │   │   └── sharepoint_service.py   # SharePoint integration
│   │   │
│   │   ├── scrapers/                    # Web scraping (refactored)
│   │   │   ├── __init__.py
│   │   │   ├── base_scraper.py         # Base class for scrapers
│   │   │   ├── playwright_manager.py   # Browser pool manager
│   │   │   ├── process_discovery.py    # Stage 1: Discover processes
│   │   │   ├── link_validation.py      # Stage 2: Validate links
│   │   │   ├── document_discovery.py   # Stage 3: Discover documents
│   │   │   └── document_download.py    # Stage 4: Download docs
│   │   │
│   │   ├── workers/                     # Celery workers
│   │   │   ├── __init__.py
│   │   │   ├── celery_app.py           # Celery instance
│   │   │   ├── tasks/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── scraper_tasks.py    # Scraping tasks
│   │   │   │   ├── document_tasks.py   # Document processing
│   │   │   │   └── notification_tasks.py # Email tasks
│   │   │   │
│   │   │   └── scheduler.py            # Celery beat schedule
│   │   │
│   │   ├── integrations/                # External integrations
│   │   │   ├── __init__.py
│   │   │   ├── microsoft_graph.py      # MS Graph API
│   │   │   ├── sharepoint.py           # SharePoint API
│   │   │   └── playwright_helper.py    # Playwright utilities
│   │   │
│   │   ├── websocket/                   # WebSocket
│   │   │   ├── __init__.py
│   │   │   ├── manager.py              # Connection manager
│   │   │   └── events.py               # Event handlers
│   │   │
│   │   ├── utils/                       # Utilities
│   │   │   ├── __init__.py
│   │   │   ├── validators.py
│   │   │   ├── formatters.py
│   │   │   └── helpers.py
│   │   │
│   │   ├── main.py                      # FastAPI app entry
│   │   └── __init__.py
│   │
│   ├── tests/                            # Tests
│   │   ├── __init__.py
│   │   ├── conftest.py
│   │   ├── api/
│   │   │   ├── test_auth.py
│   │   │   ├── test_processos.py
│   │   │   └── test_documentos.py
│   │   ├── services/
│   │   └── scrapers/
│   │
│   ├── .env.example
│   ├── .gitignore
│   ├── alembic.ini
│   ├── pyproject.toml                   # Poetry config
│   ├── requirements.txt                 # Or use Poetry
│   └── README.md
│
├── docker/                               # Docker configs
│   ├── frontend/
│   │   ├── Dockerfile
│   │   └── .dockerignore
│   ├── backend/
│   │   ├── Dockerfile
│   │   └── .dockerignore
│   ├── nginx/
│   │   ├── Dockerfile
│   │   └── nginx.conf
│   └── celery/
│       └── Dockerfile
│
├── scripts/                              # Utility scripts
│   ├── migrate_mongo_to_postgres.py     # Data migration
│   ├── seed_database.py                 # Seed data
│   └── backup_restore.py                # Backup/restore
│
├── docs/                                 # Documentation
│   ├── API.md                           # API documentation
│   ├── DEPLOYMENT.md                    # Deployment guide
│   ├── DEVELOPMENT.md                   # Dev setup
│   └── CONTRIBUTING.md
│
├── .github/
│   └── workflows/
│       ├── ci.yml                       # CI pipeline
│       └── deploy.yml                   # Deployment
│
├── docker-compose.yml                    # Development
├── docker-compose.prod.yml               # Production
├── .gitignore
├── README.md
├── CLAUDE.md                             # AI instructions (existing)
└── MIGRATION_ARCHITECTURE.md             # This file
```

---

## Modelo de Dados PostgreSQL

### Schema SQL

```sql
-- Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm"; -- Full-text search

-- Users
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    is_active BOOLEAN DEFAULT TRUE,
    is_superuser BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_users_email ON users(email);

-- Processos
CREATE TABLE processos (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    numero_processo VARCHAR(50) UNIQUE NOT NULL,
    unidade VARCHAR(255),
    categoria VARCHAR(50),
    status_categoria VARCHAR(50),
    tipo_acesso_atual VARCHAR(20), -- 'integral' | 'parcial'
    autoridade VARCHAR(255),
    apelido VARCHAR(255),
    sem_link_valido BOOLEAN DEFAULT FALSE,
    metadata JSONB DEFAULT '{}',
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_processos_numero ON processos(numero_processo);
CREATE INDEX idx_processos_categoria ON processos(categoria);
CREATE INDEX idx_processos_user_id ON processos(user_id);
CREATE INDEX idx_processos_metadata ON processos USING GIN(metadata);

-- Processo Links
CREATE TABLE processo_links (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    processo_id UUID NOT NULL REFERENCES processos(id) ON DELETE CASCADE,
    url TEXT NOT NULL,
    tipo_acesso VARCHAR(20), -- 'integral' | 'parcial'
    status VARCHAR(20) DEFAULT 'ativo', -- 'ativo' | 'inativo'
    ultima_verificacao TIMESTAMPTZ,
    historico JSONB DEFAULT '[]',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_processo_links_processo_id ON processo_links(processo_id);

-- Documentos
CREATE TABLE documentos (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    processo_id UUID NOT NULL REFERENCES processos(id) ON DELETE CASCADE,
    numero_documento VARCHAR(50) NOT NULL,
    tipo_documento VARCHAR(100),
    data_documento DATE,
    descricao TEXT,
    pdf_url TEXT,
    sharepoint_url TEXT,
    sharepoint_file_id VARCHAR(255),
    is_downloaded BOOLEAN DEFAULT FALSE,
    file_hash VARCHAR(64),
    file_size_bytes BIGINT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(processo_id, numero_documento)
);

CREATE INDEX idx_documentos_processo_id ON documentos(processo_id);
CREATE INDEX idx_documentos_tipo ON documentos(tipo_documento);

-- Documento History
CREATE TABLE documento_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    documento_id UUID NOT NULL REFERENCES documentos(id) ON DELETE CASCADE,
    tipo_operacao VARCHAR(50),
    timestamp_inicio TIMESTAMPTZ,
    timestamp_fim TIMESTAMPTZ,
    duracao_ms INTEGER,
    resultado VARCHAR(20),
    erro TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Configuracoes
CREATE TABLE configuracoes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tipo VARCHAR(50) NOT NULL,
    chave VARCHAR(100) NOT NULL,
    valor JSONB NOT NULL,
    is_global BOOLEAN DEFAULT FALSE,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tipo, chave, user_id)
);

-- Notificacoes
CREATE TABLE notificacoes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tipo VARCHAR(50) NOT NULL,
    destinatarios TEXT[] NOT NULL,
    assunto VARCHAR(255) NOT NULL,
    corpo JSONB NOT NULL,
    enviado BOOLEAN DEFAULT FALSE,
    enviado_em TIMESTAMPTZ,
    erro TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Job Executions
CREATE TABLE job_executions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_type VARCHAR(50) NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    result JSONB,
    error_message TEXT,
    progress_percentage INTEGER DEFAULT 0,
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Triggers
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_processos_updated_at BEFORE UPDATE ON processos
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_processo_links_updated_at BEFORE UPDATE ON processo_links
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_documentos_updated_at BEFORE UPDATE ON documentos
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_configuracoes_updated_at BEFORE UPDATE ON configuracoes
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
```

---

## API REST - Endpoints

### Authentication
```
POST   /api/v1/auth/register          # Register user
POST   /api/v1/auth/login             # Login (returns JWT)
POST   /api/v1/auth/refresh           # Refresh token
POST   /api/v1/auth/logout            # Logout
GET    /api/v1/auth/me                # Current user
PUT    /api/v1/auth/me                # Update user
PUT    /api/v1/auth/password          # Change password
```

### Processos
```
GET    /api/v1/processos                     # List (with filters, pagination)
POST   /api/v1/processos                     # Create
GET    /api/v1/processos/{id}                # Get by ID
PUT    /api/v1/processos/{id}                # Update
DELETE /api/v1/processos/{id}                # Delete
PATCH  /api/v1/processos/{id}/categoria      # Update category
PATCH  /api/v1/processos/{id}/apelido        # Update nickname

GET    /api/v1/processos/{id}/links          # Get links
POST   /api/v1/processos/{id}/links          # Add link
PUT    /api/v1/processos/{id}/links/{linkId} # Update link
DELETE /api/v1/processos/{id}/links/{linkId} # Delete link

GET    /api/v1/processos/stats               # Statistics
```

### Documentos
```
GET    /api/v1/documentos                    # List all
GET    /api/v1/documentos/{id}               # Get by ID
GET    /api/v1/documentos/{id}/download      # Download file
GET    /api/v1/documentos/{id}/history       # History

GET    /api/v1/processos/{id}/documentos     # By process
```

### Jobs
```
POST   /api/v1/jobs/process-discovery        # Start stage 1
POST   /api/v1/jobs/link-validation          # Start stage 2
POST   /api/v1/jobs/document-discovery       # Start stage 3
POST   /api/v1/jobs/document-download        # Start stage 4
POST   /api/v1/jobs/full-pipeline            # Full pipeline

GET    /api/v1/jobs                          # List jobs
GET    /api/v1/jobs/{id}                     # Job status
POST   /api/v1/jobs/{id}/cancel              # Cancel job
GET    /api/v1/jobs/{id}/logs                # Job logs (streaming)
```

### Configurações
```
GET    /api/v1/configuracoes                 # All settings
GET    /api/v1/configuracoes/{tipo}          # By type
PUT    /api/v1/configuracoes/{tipo}          # Update

GET    /api/v1/configuracoes/credenciais     # SEI credentials
PUT    /api/v1/configuracoes/credenciais     # Update credentials
GET    /api/v1/configuracoes/notificacoes    # Notification settings
PUT    /api/v1/configuracoes/notificacoes    # Update notifications
```

### Relatórios
```
GET    /api/v1/relatorios/processos          # Process report
GET    /api/v1/relatorios/documentos         # Document report
GET    /api/v1/relatorios/timeline           # Activity timeline
GET    /api/v1/relatorios/export             # Export (CSV/Excel)
```

### WebSocket
```
WS     /ws                                   # WebSocket connection
       Events: job_progress, new_document, process_updated, etc.
```

---

## Configuração Nuxt 4

```typescript
// frontend/nuxt.config.ts

export default defineNuxtConfig({
  future: {
    compatibilityVersion: 4, // Nuxt 4
  },

  modules: [
    '@nuxt/ui',      // Nuxt UI v4
    '@pinia/nuxt',   // State management
    '@vueuse/nuxt',  // Vue composables
  ],

  ui: {
    // Nuxt UI v4 uses Radix Vue + Tailwind
    // Configuration for components
  },

  css: ['~/assets/css/main.css'],

  runtimeConfig: {
    public: {
      apiBase: process.env.NUXT_PUBLIC_API_BASE || 'http://localhost:8000',
      wsUrl: process.env.NUXT_PUBLIC_WS_URL || 'ws://localhost:8000/ws',
    }
  },

  typescript: {
    strict: true,
    typeCheck: true,
  },

  devtools: { enabled: true },

  ssr: false, // SPA mode (can enable SSR later)

  vite: {
    server: {
      proxy: {
        '/api': {
          target: process.env.NUXT_PUBLIC_API_BASE || 'http://localhost:8000',
          changeOrigin: true,
        }
      }
    }
  },

  tailwindcss: {
    config: {
      theme: {
        extend: {
          colors: {
            // Custom color palette
          }
        }
      }
    }
  }
})
```

---

## Docker Compose

```yaml
# docker-compose.yml

version: '3.9'

services:
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_USER: sei_user
      POSTGRES_PASSWORD: sei_password
      POSTGRES_DB: sei_database
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U sei_user"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 5

  backend:
    build:
      context: ./backend
      dockerfile: ../docker/backend/Dockerfile
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
    volumes:
      - ./backend:/app
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgresql+asyncpg://sei_user:sei_password@postgres:5432/sei_database
      REDIS_URL: redis://redis:6379/0
      SECRET_KEY: dev-secret-key-change-in-production
      PLAYWRIGHT_BROWSERS_PATH: /ms-playwright
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    env_file:
      - ./backend/.env

  celery_worker:
    build:
      context: ./backend
      dockerfile: ../docker/celery/Dockerfile
    command: celery -A app.workers.celery_app worker --loglevel=info --concurrency=4
    volumes:
      - ./backend:/app
    environment:
      DATABASE_URL: postgresql+asyncpg://sei_user:sei_password@postgres:5432/sei_database
      REDIS_URL: redis://redis:6379/0
      PLAYWRIGHT_BROWSERS_PATH: /ms-playwright
    depends_on:
      - postgres
      - redis
      - backend

  celery_beat:
    build:
      context: ./backend
      dockerfile: ../docker/celery/Dockerfile
    command: celery -A app.workers.celery_app beat --loglevel=info
    volumes:
      - ./backend:/app
    environment:
      DATABASE_URL: postgresql+asyncpg://sei_user:sei_password@postgres:5432/sei_database
      REDIS_URL: redis://redis:6379/0
    depends_on:
      - redis
      - backend

  frontend:
    build:
      context: ./frontend
      dockerfile: ../docker/frontend/Dockerfile
    command: npm run dev
    volumes:
      - ./frontend:/app
      - /app/node_modules
      - /app/.nuxt
    ports:
      - "3000:3000"
    environment:
      NUXT_PUBLIC_API_BASE: http://backend:8000
      NUXT_PUBLIC_WS_URL: ws://backend:8000/ws
    depends_on:
      - backend

  nginx:
    build:
      context: ./docker/nginx
    ports:
      - "80:80"
    depends_on:
      - backend
      - frontend
    volumes:
      - ./docker/nginx/nginx.conf:/etc/nginx/nginx.conf:ro

volumes:
  postgres_data:
  redis_data:
```

---

## Pipeline de Scraping Melhorado

### Melhorias Propostas

1. **Paralelização**: Pool de browsers Playwright
2. **Retry Logic**: Backoff exponencial
3. **Checkpointing**: Salvar progresso
4. **Rate Limiting**: Respeitar limites do servidor
5. **Priorização**: Processos urgentes primeiro

### Celery Tasks

```python
# backend/app/workers/tasks/scraper_tasks.py

from app.workers.celery_app import celery_app
from celery import chain, group

@celery_app.task(bind=True, max_retries=3)
def discover_processes_task(self, user_id: str):
    """Stage 1: Process Discovery"""
    try:
        # Implementation
        pass
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60 * 2 ** self.request.retries)

@celery_app.task(bind=True, max_retries=3)
def validate_links_task(self, process_ids: list[str]):
    """Stage 2: Link Validation"""
    # Implementation with progress updates via WebSocket
    pass

@celery_app.task(bind=True, max_retries=3)
def discover_documents_task(self, process_ids: list[str]):
    """Stage 3: Document Discovery"""
    # Implementation
    pass

@celery_app.task(bind=True, max_retries=3)
def download_documents_task(self, document_ids: list[str]):
    """Stage 4: Document Download"""
    # Implementation
    pass

@celery_app.task
def run_full_pipeline(user_id: str):
    """Full pipeline orchestration"""
    return chain(
        discover_processes_task.s(user_id),
        validate_links_task.s(),
        discover_documents_task.s(),
        download_documents_task.s()
    ).apply_async()
```

---

## Frontend - Páginas Principais

### 1. Dashboard (/)
- Stats cards (processos, documentos, jobs)
- Charts (timeline, categorias)
- Recent activity
- Quick actions

### 2. Processos (/processos)
- Table com filtros avançados
- Busca full-text
- Bulk actions
- Export CSV/Excel

### 3. Processo Detail (/processos/[id])
- Info geral
- Links list
- Documents table
- Timeline

### 4. Jobs (/jobs)
- Pipeline controls
- Active jobs com progress
- Job history
- Logs viewer

### 5. Configurações (/configuracoes)
- SEI credentials
- Notifications
- User profile

---

## Plano de Implementação

### Fase 1: Setup (Semana 1-2)
- [ ] Estrutura de diretórios
- [ ] Docker Compose
- [ ] PostgreSQL + Alembic
- [ ] FastAPI base
- [ ] Nuxt 4 base
- [ ] Redis + Celery

### Fase 2: Auth & CRUD (Semana 3-4)
- [ ] JWT authentication
- [ ] User management
- [ ] Processo CRUD
- [ ] Frontend auth
- [ ] Layout & routing

### Fase 3: Scrapers (Semana 5-7)
- [ ] Refactor scrapers
- [ ] Celery tasks
- [ ] WebSocket updates
- [ ] Job management UI

### Fase 4: Documentos (Semana 8-9)
- [ ] Document CRUD
- [ ] PDF viewer
- [ ] SharePoint integration
- [ ] Email notifications

### Fase 5: Features (Semana 10-11)
- [ ] Dashboard
- [ ] Reports
- [ ] Settings
- [ ] UX improvements

### Fase 6: Migration & Deploy (Semana 12-13)
- [ ] Data migration script
- [ ] Testing
- [ ] Production deploy
- [ ] Documentation

---

## Próximos Passos

1. **Validar arquitetura** com stakeholders
2. **Setup inicial** do projeto
3. **Criar repositório** Git
4. **Definir timeline** exato
5. **Começar implementação**

---

## Tecnologias - Versões Específicas

```json
// frontend/package.json
{
  "name": "automasei-frontend",
  "version": "2.0.0",
  "type": "module",
  "scripts": {
    "dev": "nuxt dev",
    "build": "nuxt build",
    "preview": "nuxt preview"
  },
  "dependencies": {
    "nuxt": "^4.0.0",
    "@nuxt/ui": "^4.0.0",
    "@pinia/nuxt": "^0.5.0",
    "@vueuse/nuxt": "^11.0.0",
    "pinia": "^2.2.0",
    "vue": "^3.5.0"
  },
  "devDependencies": {
    "@nuxtjs/tailwindcss": "^6.12.0",
    "typescript": "^5.6.0"
  }
}
```

```toml
# backend/pyproject.toml
[tool.poetry]
name = "automasei-backend"
version = "2.0.0"
description = "AutomaSEI Backend API"

[tool.poetry.dependencies]
python = "^3.11"
fastapi = "^0.104.0"
uvicorn = { extras = ["standard"], version = "^0.24.0" }
sqlalchemy = "^2.0.0"
alembic = "^1.12.0"
asyncpg = "^0.29.0"
pydantic = "^2.5.0"
pydantic-settings = "^2.1.0"
python-jose = { extras = ["cryptography"], version = "^3.3.0" }
passlib = { extras = ["bcrypt"], version = "^1.7.4" }
python-multipart = "^0.0.6"
celery = "^5.3.0"
redis = "^5.0.0"
playwright = "^1.40.0"
httpx = "^0.25.0"

[tool.poetry.dev-dependencies]
pytest = "^7.4.0"
pytest-asyncio = "^0.21.0"
```

---

**Fim da Arquitetura**
