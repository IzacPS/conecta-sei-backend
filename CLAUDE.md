# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## ⚠️ IMPORTANT: v2.0 Refactoring in Progress

**Current Status:** Project is being refactored from v1.0.10 (desktop app) to v2.0 (REST API).

**Active Branch:** `refactor/v2` (87% complete - 13/15 sprints done)

**What's New in v2.0:**
- FastAPI REST API replacing desktop GUI
- PostgreSQL + ParadeDB replacing MongoDB
- Multi-tenant architecture (multiple institutions)
- Plugin system for SEI version management
- Firebase Storage for document persistence
- Repository pattern for database abstraction
- Merged pipeline stages (50% faster extraction)

**Documentation:**
- [PROJECT_STATUS.md](PROJECT_STATUS.md) - Overall project status and progress
- [API_LEGACY_COMPLIANCE.md](API_LEGACY_COMPLIANCE.md) - API conformance with legacy
- [MIGRATION_PLAN.md](MIGRATION_PLAN.md) - MongoDB → PostgreSQL migration strategy

**Frontend / MVP de referência:** O layout e as seções do dashboard (ConectaSEI) seguem o MVP estático em **`C:\Users\izacc\dev\SEI_Uno_Trade-frontend-mvp\SEI_Uno_Trade-frontend-mvp`** (raiz: `index.html` + `js/app.js`). Use esse repositório como referência de estrutura (sidebar, stats, Processos Recentes, Próximos Prazos, Assistente IA, Atividade Recente), não o `index.html` na raiz do SEI_Uno_Trade atual.

**Legacy Code:** Código legado (v1.0.10) está em [legacy/](legacy/). Não importe nada de `legacy/` a partir de `app/` ou scripts ativos. Migração Mongo → Postgres: use `scripts/migrate-mongo-to-postgres.py` e `MONGO_URI` em `.env`. O legado era **single-user**: já tinha credenciais de um usuário que o app usava (email + senha guardadas em `configuracoes` / `credenciais.json` para logar no SEI); uma URL do SEI e uma lista de notificações. No v2 isso equivale a uma instituição com essas credenciais.

---

## Project Overview (v1.0.10 - Legacy)

AutomaSEI v1.0.10 is a Windows desktop application that automates the extraction, monitoring, and management of legal processes from the SEI (Sistema Eletrônico de Informações) system.

**Legacy Version:** 1.0.10 (being phased out)

## Technology Stack

### v2.0 (Current Development):
- **Backend:** FastAPI + SQLAlchemy + PostgreSQL + ParadeDB
- **Storage:** Firebase Storage (document persistence)
- **Web Automation:** Playwright (Chromium headless browser)
- **Patterns:** Repository, Strategy, Plugin System
- **Email:** Microsoft Graph API (via provider abstraction)

### v1.0.10 (Legacy):
- **UI Framework:** ttkbootstrap (modern themed tkinter)
- **Database:** MongoDB Atlas (cloud-hosted)
- **Build System:** PyInstaller + Inno Setup

## v2.0 Architecture (Refactored)

### Core Components

**API Layer** ([app/api/](app/api/)):
- [main.py](app/api/main.py) - FastAPI application with middleware, health checks, CORS
- [schemas](app/api/schemas/) - Pydantic models (legacy compliance)
- [routers/](app/api/routers/) - REST endpoints (institutions, processes, documents, extraction)

**Business Logic** ([app/core/](app/core/)):
- [process_extractor.py](app/core/process_extractor.py) - Pipeline com stages merged
- [document_downloader.py](app/core/document_downloader.py) - Downloads + HTML→PDF + Firebase Storage
- [institution_service.py](app/core/services/institution_service.py) - Institution management + scraper selection

**Database Layer** ([app/database/](app/database/)):
- [models/](app/database/models/) - Institution, Process, DocumentHistory, SystemConfiguration, etc.
- [repositories/](app/database/repositories/) - Repository pattern
- [session.py](app/database/session.py) - SQLAlchemy session management (sync)

**Scrapers** ([app/scrapers/](app/scrapers/)):
- Registry e factory por versão SEI (v2, v3, v4, v5)
- [sei_v4/v4_2_0/](app/scrapers/sei_v4/v4_2_0/) - SEI v4.2.0 implementation

**Utilities** ([app/utils/](app/utils/)):
- [storage_service.py](app/utils/storage_service.py) - Firebase Storage (thread-safe)
- [email_service.py](app/utils/email_service.py) - Email notifications (PostgreSQL SystemConfiguration key/value)
- [email_providers.py](app/utils/email_providers.py) - Provider abstraction (Microsoft Graph, SMTP)
- [credentials.py](app/utils/credentials.py) - Credentials (PostgreSQL key/value + file fallback)
- [encryption.py](app/utils/encryption.py) - Fernet symmetric encryption

### API Endpoints (18 total)

**Institutions** (6 endpoints):
- `GET /institutions` - List with pagination
- `GET /institutions/{id}` - Get by ID
- `POST /institutions` - Create
- `PUT /institutions/{id}` - Update
- `DELETE /institutions/{id}` - Delete with CASCADE
- `GET /institutions/{id}/stats` - Statistics

**Processes** (8 endpoints):
- `GET /processes` - List with filters + pagination (multi-tenant)
- `GET /processes/{id}` - Get by ID
- `GET /processes/by-number/{number}` - Get by process number
- `GET /processes/pending-categorization` - Pending processes
- `POST /processes` - Create
- `PUT /processes/{id}` - Update
- `DELETE /processes/{id}` - Delete
- `POST /processes/search` - ParadeDB BM25 full-text search

**Documents** (4 endpoints):
- `POST /documents/download` - Download in background
- `GET /documents/download/{task_id}/status` - Check task status
- `GET /documents/history` - Download history
- `DELETE /documents/download/{task_id}` - Cancel/remove task

**Extraction** (3 endpoints):
- `POST /institutions/{id}/processes/extract` - Start extraction (background task)
- `GET /extraction-tasks/{task_id}` - Get extraction status
- `GET /institutions/{id}/extraction-tasks` - List institution's extraction history

### Firebase Storage Integration

**File:** [app/utils/storage_service.py](app/utils/storage_service.py)

**Features:**
- Thread-safe document upload (double-checked locking pattern)
- Singleton bucket initialization
- Structured paths: `{institution_id}/{process_number}/{document_number}.pdf`
- Graceful fallback: marks as "sucesso_parcial" if upload fails but download succeeded
- Environment configuration:
  - `FIREBASE_CREDENTIALS` - Path to Firebase credentials JSON
  - `FIREBASE_STORAGE_BUCKET` - Bucket name (e.g., "automasei-documents")

**Architecture:**
```
ProcessExtractor (ThreadPool 5 workers)
   ├─ Worker 1 → DocumentDownloader → upload_document_to_storage()
   ├─ Worker 2 → DocumentDownloader → upload_document_to_storage()
   ├─ Worker 3 → DocumentDownloader → upload_document_to_storage()
   ├─ Worker 4 → DocumentDownloader → upload_document_to_storage()
   └─ Worker 5 → DocumentDownloader → upload_document_to_storage()
                                           ↓
                           Firebase Storage (thread-safe bucket)
```

**Functions:**
- `init_firebase_storage()` - Initialize Firebase Admin SDK (thread-safe)
- `upload_document_to_storage()` - Upload PDF to bucket
- `delete_document_from_storage()` - Remove document
- `get_document_url()` - Get public URL

### Running v2.0 API

**1. Start PostgreSQL + ParadeDB:**
```bash
docker-compose up -d
```

**2. Run Alembic migrations:**
```bash
alembic upgrade head
```

**3. Start FastAPI server:**
```bash
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

**4. Access documentation:**
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- Health check: http://localhost:8000/health

---

## Testing Environment

The project uses **Docker Compose** to provide an isolated testing environment with PostgreSQL and Firebase Emulator.

### Quick Start

**Windows (PowerShell):**
```powershell
.\scripts\test-env.ps1 start    # Start test environment
.\scripts\test-env.ps1 test     # Run tests
.\scripts\test-env.ps1 coverage # Run with coverage report
```

**Linux/Mac (Bash):**
```bash
./scripts/test-env.sh start     # Start test environment
./scripts/test-env.sh test      # Run tests
./scripts/test-env.sh coverage  # Run with coverage report
```

### Test Infrastructure

**Services:**
- **PostgreSQL Test**: Port 5433 (isolated from dev DB on 5432)
- **Firebase Emulator**:
  - Storage: Port 9199
  - UI: Port 4000 (http://localhost:4000)

**Configuration:**
- Environment variables: [.env.test](.env.test)
- Docker Compose: [docker-compose.test.yml](docker-compose.test.yml)
- Pytest config: [tests/conftest.py](tests/conftest.py)
- Firebase config: [tests/firebase/](tests/firebase/)

**Available Fixtures:**
- `db_session`: Isolated database session (rollback after each test)
- `test_client`: FastAPI TestClient with DB override
- `firebase_storage`: Firebase Storage Emulator reference
- `sample_institution_data`, `sample_process_data`, `sample_document_data`: Test data

**Test Structure:**
```
tests/
├── conftest.py                     # Global pytest configuration
├── README.md                       # Detailed testing documentation
├── test_api/                       # API endpoint tests
├── test_core/                      # Business logic tests
├── test_database/                  # Repository tests
├── test_utils/                     # Utility tests
└── test_integration/               # E2E tests
```

For detailed documentation, see [tests/README.md](tests/README.md).

---

## Development Commands (Legacy v1.0.10)

### Building the Application

1. **Set Playwright environment** (must be done before every build):
```powershell
$env:PLAYWRIGHT_BROWSERS_PATH="0"
# OR
set PLAYWRIGHT_BROWSERS_PATH=0
```

2. **Install Playwright browsers**:
```bash
playwright install chromium
```

3. **Build executable with PyInstaller**:
```bash
pyinstaller main.py --clean --name AutomaSEI --icon=sei.ico --add-data "sei.ico;." --add-data "sei.png;." --add-data "7za.exe;." --contents-directory "." --noconsole --noconfirm
```

4. **Create installer** (requires Inno Setup):
- Compile `AutomaSEISetup.iss` using Inno Setup Compiler
- Output: `AutomaSEISetup.exe`

### Version Updates

When updating the version, change in **both** files:
- [main.py:22](main.py#L22) - `Config.APP_VERSION`
- [AutomaSEISetup.iss:3](AutomaSEISetup.iss#L3) - `AppVersion`

## Architecture

### Data Flow Pipeline

The application follows a 4-stage pipeline for process monitoring:

1. **Stage 1: Process Discovery** ([get_process_update.py](get_process_update.py))
   - Scrapes SEI system for all visible processes
   - Extracts process numbers and access links
   - Creates initial process entries
   - Does NOT collect authority data yet (optimized for speed)

2. **Stage 2: Link Validation** ([get_process_links_status.py](get_process_links_status.py))
   - Verifies each process link is valid
   - Determines access type: "integral" (full access) or "parcial" (partial access)
   - Collects authority data while process is already open
   - Updates link status and detects invalid links
   - Triggers categorization email notifications for new processes

3. **Stage 3: Document Discovery** ([get_process_docs_update.py](get_process_docs_update.py))
   - Scans processes for new or updated documents
   - Only processes if `should_process_documents()` returns true:
     - Always processes "integral" access
     - For "parcial" access, only if category is "restrito" and status is not "pendente"
   - Collects authority data if still missing
   - Sends email notifications for new documents
   - Extracts document metadata (type, date, number)

4. **Stage 4: Document Download** ([get_docs_download.py](get_docs_download.py))
   - Downloads PDF documents from SEI
   - Converts HTML documents to PDF when necessary
   - Uploads files to SharePoint
   - Records document history
   - Cleans up temporary files

### Core Systems

#### MongoDB Collections

Database name: `sei_database`

- **processos**: Main process data
  - `numero_processo` (key): Process identifier
  - `links`: Dictionary of access links with status and type
  - `melhor_link_atual`: Current best working link
  - `categoria`: Process category ("restrito", etc.)
  - `status_categoria`: Categorization status ("pendente", etc.)
  - `tipo_acesso_atual`: Current access type ("integral"/"parcial")
  - `documentos`: Dictionary of documents by number
  - `unidade`: Administrative unit
  - `Autoridade`: Authority extracted from process (collected opportunistically)
  - `sem_link_validos`: Boolean flag for invalid links
  - `apelido`: User-defined nickname

- **configuracoes**: System configuration
  - `tipo: "url_sistema"`: SEI system URL
  - `tipo: "credenciais_acesso"`: Login credentials (email/password)
  - `tipo: "email_notifications"`: Notification emails and settings

#### Credential Management

Credentials use MongoDB as the authoritative source with local file fallback:

1. **Load priority** ([utils.py:213-241](utils.py#L213-L241)):
   - MongoDB (authoritative source)
   - Local file `credenciais.json` (fallback/cache)
   - Empty credentials (last resort)

2. **Save flow** ([utils.py:252-291](utils.py#L252-L291)):
   - Always save to MongoDB first
   - Sync to local file for caching
   - Check completeness with `credentials_are_complete()`

3. **Login function** ([utils.py:312-326](utils.py#L312-L326)):
   - Validates credentials before attempting login
   - Uses `login_to_sei(page)` for Playwright automation
   - Throws exception if credentials incomplete

#### UI Module Pattern

All UI modules follow a consistent pattern:

- Inherit from `ttk.Toplevel`
- Accept parent window in `__init__`
- Load icon from `sei.ico` or fallback to `sei.png`
- Use `queue.Queue` for thread-safe logging
- Set up custom `AppUserModelID` for Windows taskbar
- Implement `on_closing()` for cleanup

**Main UI modules:**
- [ui_scraper.py](ui_scraper.py): Automated process extraction with scheduling
- [ui_push_process.py](ui_push_process.py): Real-time single process monitor
- [ui_file_comparator.py](ui_file_comparator.py): Compare local files with SEI documents
- [ui_process_manager.py](ui_process_manager.py): Manage categories, links, nicknames
- [ui_settings.py](ui_settings.py): Configure credentials and notifications

#### Logging System

Uses singleton pattern with thread-safe queue:

- [logger_system.py](logger_system.py): `UILogger` singleton redirects stdout
- `setup_logging(log_queue)`: Initialize for each UI window
- Format: `[YYYY-MM-DD HH:MM:SS] message`
- UI reads from queue with `monitor_log_queue()`

### Key Utility Functions

- **Data Management** ([utils.py](utils.py)):
  - `load_process_data()`: Load all processes from MongoDB
  - `save_process_data(processes)`: Save all processes to MongoDB
  - `create_process_entry(process_number)`: Initialize new process structure
  - `should_process_documents(process_data)`: Determine if documents should be extracted
  - `get_app_data_dir()`: Returns `%LOCALAPPDATA%\SEI_UNO_TRADE`

- **Browser Automation**:
  - `init_browser()`: Create Playwright browser instance (headless Chromium)
  - `login(page)`: Wrapper around `login_to_sei()` with error handling
  - All scraper modules follow: init → login → process → cleanup

## Important Notes

### Security Considerations

- MongoDB connection string is hardcoded in [connect_mongo.py:3](connect_mongo.py#L3)
- Microsoft Graph API credentials in [email_api_ms.py:8-11](email_api_ms.py#L8-L11)
- User credentials stored in MongoDB `configuracoes` collection
- These files should be excluded from version control in production

### Process Access Logic

The `should_process_documents()` function ([utils.py:93-115](utils.py#L93-L115)) is critical:
- Returns `False` if no valid links
- Returns `True` for "integral" access (full permissions)
- For "parcial" access:
  - Returns `False` if status is "pendente"
  - Returns `True` only if category is "restrito"

### Authority Collection Strategy

Authority data is collected opportunistically to minimize browser operations:
- NOT collected in Stage 1 (process discovery) - speed optimization
- Collected in Stage 2 or 3 when process is already open for other operations
- Uses `collect_authority_if_missing()` to avoid redundant work
- Stored in `process_data["Autoridade"]` field

### Email Notifications

Three notification types via Microsoft Graph API:
1. **New processes**: When categorization is needed
2. **New documents**: When documents are discovered
3. **Status changes**: Category or access type changes

Recipient list loaded from MongoDB `configuracoes` collection.

### File Paths and Data Storage

- Application data: `%LOCALAPPDATA%\SEI_UNO_TRADE\`
- Backups: `%LOCALAPPDATA%\SEI_UNO_TRADE\backups\`
- Temporary downloads: `%LOCALAPPDATA%\SEI_UNO_TRADE\temp_downloads\`
- Credentials cache: `%LOCALAPPDATA%\SEI_UNO_TRADE\credenciais.json`

### PyInstaller Packaging

The spec file ([AutomaSEI.spec](AutomaSEI.spec)) includes:
- No console window (`console=False`)
- Embedded data files: `sei.ico`, `sei.png`, `7za.exe`
- Icon set for executable
- UPX compression enabled

## Common Patterns

### Opening Windows from Main App

```python
self.open_window("window_key", WindowClass)
```

Handles singleton behavior - focuses if already open, creates new if not.

### Thread-Safe UI Updates

```python
self.log_queue = queue.Queue()
self.logger = setup_logging(self.log_queue)
self.monitor_log_queue()  # Poll queue in main thread
```

### MongoDB Query Pattern

```python
db = get_database()
collection = db.processos
processo = collection.find_one({"numero_processo": process_number})
```

### Playwright Navigation

```python
page.goto(url)
page.wait_for_load_state("networkidle")
page.fill("#selector", "value")
page.click("#button")
```
