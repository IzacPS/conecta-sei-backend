# AutomaSEI v2.0 - Architecture Summary

## Quick Reference

Este documento resume as decisões arquiteturais principais do projeto.

---

## 1. Sistema de Plugins (Plugin System)

**Problema**: SEI tem múltiplas versões com diferentes CSS selectors e comportamentos

**Solução**: Arquitetura OOP com herança em 3 níveis

```
SEIScraperBase (abstract)
    ↓
SEIv4Base (família v4)
    ↓
SEIv4_2_0 (versão específica)
```

**Implementação**:
- `scrapers/base.py` - Interface abstrata com todos os métodos
- `scrapers/registry.py` - Registro centralizado de plugins (Singleton)
- `scrapers/factory.py` - Criação de scrapers com auto-detecção

**Benefícios**:
- Adicionar nova versão: criar classe herdando da família
- Override apenas o que muda
- Auto-detecção de versão
- Fallback strategies

**Status**: ✅ Implementado (Sprint 1.2)

---

## 2. Multi-Tenant Architecture

**Problema**: Usuários precisam acessar SEI de múltiplas instituições, cada uma com versão diferente

**Solução**: Modelo de Instituição + Auto-detecção por instituição

```
Institution (Tenant)
├── id: "trf1"
├── name: "TRF 1ª Região"
├── sei_url: "https://sei.trf1.jus.br"
├── sei_version: "4.2.0" (auto-detected)
├── scraper_version: "4.2.0"
└── credentials: {...}
```

**Fluxo**:
```
1. User: "Extrair processos do TRF1"
2. API busca Institution(id="trf1")
3. System usa scraper_version (setado manualmente pelo dev)
4. ScraperFactory.create(version)
5. Executa extração com scraper correto
```

**Endpoints**:
- `POST /api/institutions` - Cadastrar instituição (dev informa versão manualmente)
- `GET /api/institutions` - Listar instituições
- `POST /api/institutions/{id}/processes/extract` - Extrair processos
- `PUT /api/institutions/{id}` - Atualizar versão (quando SEI atualiza)

**Benefícios**:
- Suporta múltiplas instituições simultaneamente
- Versão manual mais confiável que auto-detecção
- Cache de scraper por instituição
- Fácil adicionar novas instituições

**Status**: 📋 Planejado (Sprint 3.1)

Detalhes: [MULTI_TENANT_DESIGN.md](MULTI_TENANT_DESIGN.md)

---

## 3. Pipeline de Extração (3 Módulos)

**Arquitetura Original**: 4 stages sequenciais (get_process_update → get_process_links_status → get_process_docs_update → get_docs_download)

**Problema**: Stages 2 e 3 abrem mesma página 2x (desperdício de 50% do tempo)

**Nova Arquitetura**: 3 módulos com Stages 2+3 merged

### Módulo 1: Extractor (Merged)
```python
# Stage 1: Discovery (sequential)
process_list = scraper.extract_process_list(page)

# Stage 2+3: Process worker (parallel)
with ThreadPoolExecutor(max_workers=5) as executor:
    for process in process_list:
        executor.submit(process_worker, process)

def process_worker(process_number):
    page.goto(link)  # Abre UMA vez
    access_type = scraper.validate_link(page, link)
    authority = scraper.extract_authority(page)
    documents = scraper.extract_documents(page)
    # 50% mais rápido
```

### Módulo 2: Notifications
- Detecta novos processos
- Detecta novos documentos
- Envia emails

### Módulo 3: Downloader
- Download de documentos
- Upload para SharePoint
- Modo individual (usuário seleciona arquivos)

**Benefícios**:
- 50% menos navegações
- Multithreading (5-10x mais rápido)
- Lógica mais clara

**Status**: 📋 Planejado (Sprint 2.1-2.3)

---

## 4. Database Abstraction Layer

**Problema**: Atualmente usa MongoDB direto, mas vai migrar para PostgreSQL + ParadeDB

**Solução**: Repository Pattern

```python
# Interface
class ProcessRepository(ABC):
    def get_all(self) -> List[Process]: pass
    def get_by_number(self, num: str) -> Process: pass
    def bulk_upsert(self, processes: List[Process]): pass

# Implementações
class MongoProcessRepository(ProcessRepository):
    # Atual - MongoDB

class PostgresProcessRepository(ProcessRepository):
    # Futuro - PostgreSQL
```

**Benefícios**:
- Core code não depende do banco
- Migração transparente (trocar adapter)
- Testável (mock repository)

**Status**: 📋 Planejado (Sprint 1.5)

---

## 5. REST API (FastAPI)

**Transformação**: Desktop App → REST API Backend

**Stack**:
- FastAPI (API framework)
- Uvicorn (ASGI server)
- Pydantic (validation)
- Background Tasks (downloads, extrações)

**Principais Routers**:

```python
# Instituições
POST   /api/institutions
GET    /api/institutions
GET    /api/institutions/{id}
POST   /api/institutions/{id}/detect-version

# Processos (por instituição)
GET    /api/institutions/{id}/processes
POST   /api/institutions/{id}/processes/extract
GET    /api/institutions/{id}/processes/{number}

# Documentos
POST   /api/institutions/{id}/processes/{number}/documents/download

# Scrapers (admin)
GET    /api/scrapers/versions
GET    /api/scrapers/families
```

**Benefícios**:
- Frontend separado (Nuxt 4)
- Integração com outros sistemas
- Escalável (containers)
- Documentação automática (Swagger)

**Status**: 📋 Planejado (Sprint 3.1-3.3)

---

## 6. Background Scheduler

**Stack**: APScheduler

**Jobs**:
```python
# Extraction (por instituição)
extraction_job:
    interval: 30 minutes
    action: extract_all_processes(institution_id)

# Notifications
notification_job:
    interval: 35 minutes
    action: check_and_notify(institution_id)

# Download pending
download_job:
    interval: 1 hour
    action: download_pending_documents(institution_id)
```

**Status**: 📋 Planejado (Sprint 4.1)

---

## 7. Containerization

**Stack**: Docker + Docker Compose

```yaml
services:
  api:
    build: .
    environment:
      - MONGODB_URI=...
      - PLAYWRIGHT_BROWSERS_PATH=...
    volumes:
      - ./downloads:/app/downloads

  mongodb:  # Dev only
    image: mongo:7
```

**Benefícios**:
- Deploy simplificado
- Ambiente consistente
- Playwright já configurado

**Status**: 📋 Planejado (Sprint 5.1)

---

## Migration Strategy

### Fase 1: Setup (Weeks 1-2) ✅ CURRENT
- [x] Plugin system base
- [x] Multi-tenant design
- [ ] Database abstraction
- [ ] SEI v4.2 plugin

### Fase 2: Core Logic (Weeks 3-4)
- [ ] Merged extractor + multithreading
- [ ] Notification system
- [ ] Downloader

### Fase 3: API (Weeks 5-6)
- [ ] FastAPI app
- [ ] Institution endpoints
- [ ] Process endpoints
- [ ] Multi-tenant integration

### Fase 4: Automation (Week 7)
- [ ] Background scheduler

### Fase 5: Production (Weeks 8-10)
- [ ] Docker
- [ ] Testing
- [ ] Deploy

---

## Key Decisions

| Decisão | Rationale |
|---------|-----------|
| **OOP com herança** | Reuso máximo de código, override apenas o que muda |
| **Auto-detecção de versão** | Transparente para usuário, suporta updates automáticos |
| **Multi-tenant** | Suporte a múltiplas instituições essencial para escalabilidade |
| **Merge Stages 2+3** | Elimina 50% das navegações (performance crítica) |
| **Repository Pattern** | Prepara migração MongoDB → PostgreSQL sem reescrever core |
| **FastAPI** | Modern, async, auto-documentation, type-safe |
| **Playwright headless** | Já usado no v1, confiável |

---

## Performance Targets

| Métrica | Atual (v1.0) | Target (v2.0) |
|---------|--------------|---------------|
| Extração 100 processos | ~60 min | ~6-10 min (10x) |
| Navegações por processo | 2x (Stages 2+3) | 1x (merged) |
| Concorrência | Sequential | 5-10 threads |
| Escalabilidade | 1 instituição | N instituições |
| Deploy | Windows .exe | Docker container |

---

## Files Reference

- `REFACTOR_PROGRESS.md` - Timeline detalhado (10 weeks)
- `MULTI_TENANT_DESIGN.md` - Design multi-tenant completo
- `CLAUDE.md` - Documentação do código atual (v1.0)
- `scrapers/` - Sistema de plugins
- `database/` - Abstraction layer (futuro)
- `api/` - REST API (futuro)
- `core/` - Business logic (futuro)

---

**Last Updated**: 2025-12-15 (Sprint 1.2 completed)
