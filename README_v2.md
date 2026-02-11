# AutomaSEI v2.0 - Development Guide

> **Branch**: `refactor/v2` | **Status**: In Progress (Sprints 1.1-1.2 Complete)

---

## 🎯 Quick Start

### Para Desenvolvedores
1. **Entender arquitetura**: Leia [ARCHITECTURE_SUMMARY.md](ARCHITECTURE_SUMMARY.md)
2. **Criar novo scraper**: Siga [scrapers/INHERITANCE_GUIDE.md](scrapers/INHERITANCE_GUIDE.md)
3. **Acompanhar progresso**: Veja [REFACTOR_PROGRESS.md](REFACTOR_PROGRESS.md)

### Para Product/Stakeholders
1. **Visão geral**: [ARCHITECTURE_SUMMARY.md](ARCHITECTURE_SUMMARY.md)
2. **Multi-tenant**: [MULTI_TENANT_DESIGN.md](MULTI_TENANT_DESIGN.md)
3. **Onboarding**: [INSTITUTION_ONBOARDING.md](INSTITUTION_ONBOARDING.md)

---

## 📚 Documentação Completa

### Arquitetura e Design
| Documento | Descrição |
|-----------|-----------|
| [ARCHITECTURE_SUMMARY.md](ARCHITECTURE_SUMMARY.md) | Resumo executivo de todas decisões arquiteturais |
| [MULTI_TENANT_DESIGN.md](MULTI_TENANT_DESIGN.md) | Sistema multi-instituição (N instituições, N versões SEI) |
| [INSTITUTION_ONBOARDING.md](INSTITUTION_ONBOARDING.md) | Processo completo de adicionar nova instituição |

### Desenvolvimento
| Documento | Descrição |
|-----------|-----------|
| [scrapers/INHERITANCE_GUIDE.md](scrapers/INHERITANCE_GUIDE.md) | Como criar scrapers com herança OOP |
| [REFACTOR_PROGRESS.md](REFACTOR_PROGRESS.md) | Timeline 10 semanas, tracking de sprints |
| [SESSION_SUMMARY.md](SESSION_SUMMARY.md) | Resumo da sessão atual (Sprints 1.1-1.2) |

### Código Legado (v1.0)
| Documento | Descrição |
|-----------|-----------|
| [CLAUDE.md](CLAUDE.md) | Documentação desktop app (Python + tkinter) |

---

## 🏗️ Estrutura do Projeto v2.0

```
AutomaSEI/
├── api/                        # FastAPI REST API (Sprint 3.x)
│   ├── routers/               # Endpoints
│   ├── models/                # Pydantic models
│   └── schemas/               # Request/response schemas
│
├── core/                       # Business logic (Sprint 2.x)
│   ├── process_extractor.py  # Merged stages 2+3, multithreaded
│   ├── notification_system.py # Detecta novos processos/docs
│   └── document_downloader.py # Download + upload SharePoint
│
├── scrapers/                   # ✅ Plugin system (Sprint 1.2 DONE)
│   ├── base.py                # SEIScraperBase (interface)
│   ├── registry.py            # ScraperRegistry (singleton)
│   ├── factory.py             # ScraperFactory (auto-detect)
│   │
│   ├── sei_v2/                # Família v2 (legacy)
│   │   └── base.py           # ✅ SEIv2Base
│   │
│   ├── sei_v3/                # Família v3
│   │   └── base.py           # ✅ SEIv3Base
│   │
│   ├── sei_v4/                # Família v4 (atual)
│   │   ├── base.py           # ✅ SEIv4Base
│   │   └── v4_2_0/           # 🔄 Sprint 1.3 (next)
│   │       ├── scraper.py    # SEIv4_2_0 plugin
│   │       └── selectors.py  # CSS selectors
│   │
│   └── sei_v5/                # Família v5 (futuro)
│       └── base.py           # ✅ SEIv5Base
│
├── database/                   # Repository pattern (Sprint 1.5)
│   ├── models.py              # DTOs (Institution, Process, etc)
│   ├── base.py                # Repository interfaces
│   ├── mongodb/               # Adapter atual
│   └── postgres/              # Adapter futuro (ParadeDB)
│
├── config/                     # Configuration
├── utils/                      # Utilities
├── tests/                      # ✅ Unit tests
│   └── test_scraper_registry.py
│
├── requirements-new.txt        # ✅ v2.0 dependencies
└── [docs]                      # ✅ Comprehensive documentation
```

**Legenda**:
- ✅ Completo
- 🔄 Em progresso
- 📋 Pendente

---

## 🚀 Sistema de Plugins (Core Feature)

### Arquitetura de Herança

```
SEIScraperBase (interface abstrata)
    ↓
SEIv4Base (família v4 - comportamento comum)
    ↓
SEIv4_2_0 (versão específica - override apenas mudanças)
```

### Como Criar Novo Scraper

**Exemplo**: Adicionar suporte para SEI v4.3.0

```python
# scrapers/sei_v4/v4_3_0/scraper.py

from scrapers.sei_v4.base import SEIv4Base
from scrapers import register_scraper

@register_scraper()
class SEIv4_3_0(SEIv4Base):
    VERSION = "4.3.0"
    VERSION_RANGE = ">=4.3.0 <4.4.0"

    # Override APENAS o que mudou
    def get_login_selectors(self):
        selectors = super().get_login_selectors()
        selectors["submit"] = "#btnEntrar"  # mudou em v4.3
        return selectors

    # Resto herda de SEIv4Base (90%+ do código)
```

**Resultado**: ~5-50 linhas ao invés de ~1000 linhas

Detalhes: [scrapers/INHERITANCE_GUIDE.md](scrapers/INHERITANCE_GUIDE.md)

---

## 🏢 Multi-Tenant Architecture

Sistema suporta **múltiplas instituições** simultaneamente, cada uma com:
- URL própria do SEI
- Versão própria (auto-detectada)
- Credenciais próprias
- Scraper apropriado (selecionado automaticamente)

### Exemplo de Uso

```python
# Usuário solicita extração do TRF1
POST /api/institutions/trf1/processes/extract

# Sistema automaticamente:
# 1. Busca Institution(id="trf1")
# 2. Verifica scraper_version (ex: "4.2.0")
# 3. ScraperFactory.create("4.2.0")
# 4. Executa extração com scraper correto
```

### Onboarding de Instituições

**Versão conhecida**: ✅ Cadastro imediato (< 5 min)
**Versão nova**: ⏳ Implementação necessária (1-7 dias)

Detalhes: [INSTITUTION_ONBOARDING.md](INSTITUTION_ONBOARDING.md)

---

## 📊 Progresso Atual

### Sprints Concluídos ✅

- [x] **Sprint 1.1**: Setup inicial (branch, estrutura, requirements)
- [x] **Sprint 1.2**: Plugin system base (SEIScraperBase, Registry, Factory)

### Próximo Sprint 🔄

- [ ] **Sprint 1.3**: Implementar SEIv4_2_0 (migrar código atual)

### Timeline

| Fase | Duração | Status |
|------|---------|--------|
| **Phase 1**: Foundation | 10-14 dias | 🔄 In Progress (40% done) |
| **Phase 2**: Core Logic | 14-18 dias | 📋 Pending |
| **Phase 3**: REST API | 18-24 dias | 📋 Pending |
| **Phase 4**: Scheduler | 24-28 dias | 📋 Pending |
| **Phase 5**: Docker | 28-32 dias | 📋 Pending |
| **Phase 6**: Migration | 32-36 dias | 📋 Pending |
| **Phase 7**: Deploy | 36-40 dias | 📋 Pending |

Detalhes: [REFACTOR_PROGRESS.md](REFACTOR_PROGRESS.md)

---

## 🛠️ Tech Stack

### Backend (v2.0)
```
FastAPI         # REST API framework
Playwright      # Web automation
MongoDB Atlas   # Database (atual)
PostgreSQL      # Database (futuro)
APScheduler     # Background jobs
Docker          # Containerization
```

### Padrões
```
Repository Pattern  # Database abstraction
Factory Pattern     # Scraper creation
Singleton Pattern   # Registry
Strategy Pattern    # Version-specific logic
```

---

## 📈 Performance Targets

| Métrica | v1.0 | v2.0 Target |
|---------|------|-------------|
| Extração 100 processos | 60 min | 6-10 min (10x) |
| Navegações por processo | 2x | 1x (merged stages) |
| Concorrência | Sequential | 5-10 threads |
| Instituições suportadas | 1 | N (multi-tenant) |
| Deploy | Windows .exe | Docker container |

---

## 🧪 Testes

### Executar Testes

```bash
# Todos os testes
pytest tests/ -v

# Testes específicos
pytest tests/test_scraper_registry.py -v

# Com coverage
pytest tests/ --cov=scrapers --cov-report=html
```

### Coverage Atual
- ✅ Registry: 100%
- ✅ Factory: 100%
- 🔄 Scrapers: Pending (Sprint 1.3+)

---

## 📝 Commits Profissionais

Todos os commits seguem padrão profissional:
- ❌ Sem emojis
- ❌ Sem referências a IA
- ✅ Mensagens descritivas
- ✅ Body explicativo quando necessário

**Exemplo**:
```
Implement plugin system base architecture

- Add SEIScraperBase abstract class with complete interface
- Implement ScraperRegistry with singleton pattern
- Add ScraperFactory with auto-detection strategies
- Create comprehensive unit tests
```

---

## 🔗 Links Rápidos

### Git
- **Branch**: `refactor/v2`
- **Main branch**: `main`
- **Commits**: 9 commits (c3f4333...a36e410)

### Estatísticas
- **Arquivos criados**: 32 arquivos
- **Linhas adicionadas**: 6385+ linhas
- **Documentação**: 5 arquivos MD principais
- **Testes**: 14 testes unitários

---

## 💡 Conceitos Chave

### 1. Herança em 3 Níveis
- **Base**: Interface universal (SEIScraperBase)
- **Família**: Comportamento comum (SEIv4Base)
- **Versão**: Override mudanças (SEIv4_2_0)

### 2. Auto-Detecção
- Sistema detecta versão SEI automaticamente
- Seleciona scraper apropriado
- Transparente para usuário

### 3. Multi-Tenant
- N instituições
- Cada uma independente
- Scraper correto por instituição

### 4. Repository Pattern
- Core code não depende do banco
- Fácil trocar MongoDB → PostgreSQL
- Testável (mock repository)

---

## 🎯 Próximos Passos

### Imediato (Sprint 1.3)
1. Criar `scrapers/sei_v4/v4_2_0/scraper.py`
2. Migrar CSS selectors do código atual
3. Migrar lógica de login, extração, documentos
4. Validar vs código legado

### Curto Prazo (Sprint 1.4-1.5)
1. Auto-detector system
2. Database abstraction layer

### Médio Prazo (Phase 2-3)
1. Core business logic (merged extractor)
2. FastAPI REST API
3. Multi-tenant implementation

---

## 📞 Contato e Suporte

Para dúvidas sobre:
- **Arquitetura**: Ver [ARCHITECTURE_SUMMARY.md](ARCHITECTURE_SUMMARY.md)
- **Scrapers**: Ver [scrapers/INHERITANCE_GUIDE.md](scrapers/INHERITANCE_GUIDE.md)
- **Timeline**: Ver [REFACTOR_PROGRESS.md](REFACTOR_PROGRESS.md)
- **Onboarding**: Ver [INSTITUTION_ONBOARDING.md](INSTITUTION_ONBOARDING.md)

---

**Status**: Foundation Complete ✅ | Next: Implement SEIv4_2_0 Plugin 🔄
