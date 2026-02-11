# MongoDB → PostgreSQL/ParadeDB Migration Log

**Data de Início:** 2025-12-15 (Sprint 2.2)
**Status:** Em Andamento

---

## Visão Geral

Este documento rastreia a migração gradual de MongoDB para PostgreSQL + ParadeDB no AutomaSEI v2.0.

**Estratégia:**
1. ✅ Sprint 1.5: Criar infraestrutura PostgreSQL + repositories
2. 🔄 Sprint 2.2+: Migrar módulos gradualmente
3. ⏳ Sprints futuros: Substituir código legado
4. ⏳ Final: Remover MongoDB completamente

---

## Módulos Migrados

### ✅ utils/credentials.py (Sprint 2.2)

**Status:** MIGRADO para PostgreSQL
**Data:** 2025-12-15

**Mudanças:**
- `load_credentials_from_mongodb()` → `load_credentials_from_database()` (PostgreSQL)
- `save_credentials()` agora usa SystemConfiguration table
- Credenciais armazenadas em JSONB metadata field
- Arquivo local continua como fallback/cache

**Tabela Usada:**
- `system_configuration` com `key` = "url_sistema" e "credenciais_acesso", `value` (JSONB)

**Código:**
```python
# ANTES (MongoDB)
db = get_database()
config_collection = db.configuracoes
credentials = config_collection.find_one({"tipo": "credenciais_acesso"})

# DEPOIS (PostgreSQL)
from app.database.session import get_session
from app.database.models.system_configuration import SystemConfiguration

with get_session() as session:
    cred = session.query(SystemConfiguration).filter_by(key="credenciais_acesso").first()
    email = cred.value.get("email") if cred and isinstance(cred.value, dict) else ""
```

**Benefícios:**
- ✅ Queries SQL ao invés de MongoDB
- ✅ JSONB para dados flexíveis (como MongoDB)
- ✅ Transações ACID
- ✅ ParadeDB full-text search disponível (futuro)

---

## Módulos Pendentes de Migração

### ⏳ utils/database.py

**Status:** NÃO INICIADO
**Prioridade:** BAIXA
**Razão:** Contém funções legadas (`load_process_data()`, `save_process_data()`) que serão gradualmente substituídas por repositories

**Plano:**
- Manter MongoDB por enquanto (código legado funciona)
- Novos módulos usam ProcessRepository diretamente
- Migrar quando código legado for removido (Sprint 6.2)

### ⏳ email_api_ms.py → utils/email_service.py

**Status:** MIGRAÇÃO PENDENTE
**Prioridade:** MÉDIA

**Funções que usam MongoDB:**
- `get_process_nickname()` - Busca apelido do processo
- `get_recipients()` - Busca emails de notificação via `mongo_config.py`

**Plano de Migração (Sprint 2.2):**
- Migrar `get_process_nickname()` para usar ProcessRepository
- Migrar `get_recipients()` para usar SystemConfiguration
- Adicionar JSONB field `notification_emails` em SystemConfiguration

---

## Dependências MongoDB Restantes

### 📦 Código Legado (NÃO TOCAR até Sprint 6.2)

Estes arquivos continuam usando MongoDB:
- `get_process_update.py` - Stage 1 legado
- `get_process_links_status.py` - Stage 2 legado
- `get_process_docs_update.py` - Stage 3 legado
- `get_docs_download.py` - Stage 4 legado
- `ui_*.py` - Todos os módulos de UI legados
- `main.py` - Aplicação desktop legada

**Status:** OFF-LIMITS (não modificar, será removido no Sprint 6.2)

### 📦 Módulos de Configuração

- `connect_mongo.py` - Mantém conexão MongoDB ativa
- `mongo_config.py` - Funções de configuração MongoDB

**Plano:** Remover após migração completa (Sprint 6.2+)

---

## Checklist de Migração para Cada Módulo

Ao migrar um módulo de MongoDB para PostgreSQL:

- [ ] Identificar todas as queries MongoDB
- [ ] Criar model SQLAlchemy se necessário
- [ ] Criar repository se necessário
- [ ] Substituir `get_database()` por `get_session()`
- [ ] Substituir `.find()` / `.find_one()` por `.query()` / `.filter_by()`
- [ ] Substituir `.update_one()` / `.insert_one()` por SQLAlchemy ORM
- [ ] Usar JSONB para campos flexíveis (equivalente a MongoDB documents)
- [ ] Atualizar imports (remover `connect_mongo`, adicionar `database.session`)
- [ ] Atualizar docstrings
- [ ] Criar testes
- [ ] Atualizar este documento

---

## Queries MongoDB → PostgreSQL

### Find One

```python
# MongoDB
db = get_database()
collection = db.processos
processo = collection.find_one({"numero_processo": "123"})

# PostgreSQL
from app.database.session import get_session
from app.database.models.process import Process

with get_session() as session:
    processo = session.query(Process).filter_by(
        process_number="123"
    ).first()
```

### Find All

```python
# MongoDB
processos = collection.find({"categoria": "restrito"})

# PostgreSQL
processos = session.query(Process).filter_by(
    categoria="restrito"
).all()
```

### Update

```python
# MongoDB
collection.update_one(
    {"numero_processo": "123"},
    {"$set": {"categoria": "publico"}}
)

# PostgreSQL
processo = session.query(Process).filter_by(process_number="123").first()
processo.categoria = "publico"
# commit automático no context manager
```

### Insert

```python
# MongoDB
collection.insert_one({
    "numero_processo": "123",
    "categoria": "restrito"
})

# PostgreSQL
novo_processo = Process(
    process_number="123",
    categoria="restrito"
)
session.add(novo_processo)
```

### JSONB (equivalente a documentos MongoDB)

```python
# MongoDB
collection.update_one(
    {"numero_processo": "123"},
    {"$set": {"documentos": {"DOC001": {"tipo": "OFÍCIO"}}}}
)

# PostgreSQL (usando JSONB)
processo.documentos = {"DOC001": {"tipo": "OFÍCIO"}}
# ParadeDB auto-indexa: documentos.DOC001.tipo
```

---

## Notas Importantes

1. **JSONB vs MongoDB Documents**: JSONB do PostgreSQL é equivalente a documentos MongoDB, mas com queries SQL
2. **ParadeDB Indexing**: JSONB fields são automaticamente indexados com BM25 para full-text search
3. **Transações**: PostgreSQL garante ACID, MongoDB não
4. **Performance**: ParadeDB BM25 é mais rápido que MongoDB text search
5. **Schemas**: PostgreSQL tem schemas definidos (models), MongoDB é schema-less

---

## Próximos Passos (Sprint 2.2)

1. ✅ Migrar `utils/credentials.py`
2. ⏳ Migrar `utils/email_service.py` (get_process_nickname, get_recipients)
3. ⏳ Manter `utils/database.py` usando MongoDB (legado)
4. ⏳ Novos módulos (process_extractor, etc.) usam repositories diretamente

---

## Timeline de Remoção do MongoDB

| Sprint | Ação | Status |
|--------|------|--------|
| 1.5 | Criar PostgreSQL + repositories | ✅ Completo |
| 2.2 | Migrar credentials.py | ✅ Completo |
| 2.2 | Migrar email_service.py | ⏳ Pendente |
| 2.3+ | Novos módulos usam apenas PostgreSQL | 🔄 Em andamento |
| 6.2 | Remover código legado (MongoDB) | ⏳ Futuro |
| 7.1 | Validar remoção completa de MongoDB | ⏳ Futuro |

---

**Última Atualização:** 2025-12-15 (Sprint 2.2)
