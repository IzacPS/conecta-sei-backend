# ParadeDB Knowledge Base

**Last Updated:** 2025-12-15
**ParadeDB Version:** v2 API
**Project:** AutomaSEI v2.0 PostgreSQL Migration

---

## What is ParadeDB?

ParadeDB is a PostgreSQL extension that adds **Elasticsearch-like full-text search** capabilities to PostgreSQL. It uses a custom index type called **BM25** that provides:

- **Full-text search** with relevance scoring
- **JSON/JSONB indexing** with automatic sub-field detection
- **ORM-friendly syntax** (v2 API improvements)
- **Token-based matching** (not substring matching)

---

## Core Concepts

### BM25 Index

ParadeDB uses a **covering index** called BM25, which means multiple columns can be included in a single index.

**Key Rules:**
- Only **ONE BM25 index per table**
- Must specify a `key_field` (unique identifier, usually PRIMARY KEY)
- The `key_field` must be the **first column** in the column list
- Index all columns you want to filter, sort, or aggregate on

**Example:**
```sql
CREATE INDEX search_idx ON processos
USING bm25 (id, numero_processo, autoridade, categoria, metadata, documentos)
WITH (key_field='id');
```

### Tokenization

At **index time**, text is broken into discrete units called **tokens** using a tokenizer.
At **query time**, the query engine looks for token matches.

**Default:** Unicode tokenizer (splits by Unicode segmentation standard)

**Example:**
- Input: `"Sleek running shoes"`
- Tokens: `sleek`, `running`, `shoes`

**Available tokenizers:**
- `unicode` (default)
- `icu` (multi-language support)
- `whitespace`
- `ngram`
- Custom with token filters (stemming, lowercasing, etc.)

---

## Query Operators

ParadeDB introduces custom SQL operators for search:

| Operator | Name                | Meaning                                          | Example                               |
|----------|---------------------|--------------------------------------------------|---------------------------------------|
| `\|\|\|` | Match Disjunction   | Find documents with ANY of the tokens (OR)       | `description \|\|\| 'running shoes'`  |
| `&&&`    | Match Conjunction   | Find documents with ALL of the tokens (AND)      | `description &&& 'running shoes'`     |
| `###`    | Phrase              | Find documents with tokens in exact order        | `description ### 'running shoes'`     |
| `@@@`    | Query Builder       | Advanced queries (regex, fuzzy, range, etc.)     | `description @@@ pdb.regex('key.*')` |

### Match Disjunction (`|||`)

Returns documents containing **one or more** query tokens.

```sql
SELECT numero_processo, autoridade
FROM processos
WHERE autoridade ||| 'João Silva';
-- Returns: "João Silva", "Maria João", "Silva Santos"
```

### Match Conjunction (`&&&`)

Returns documents containing **all** query tokens.

```sql
SELECT numero_processo, autoridade
FROM processos
WHERE autoridade &&& 'João Silva';
-- Returns: Only "João Silva" (must have both tokens)
```

### Phrase (`###`)

Returns documents where tokens appear in **exact order and position**.

```sql
SELECT numero_processo, autoridade
FROM processos
WHERE autoridade ### 'João Silva';
-- Returns: "João Silva", NOT "Silva João"
```

**Slop:** Allow flexibility in token position
```sql
WHERE autoridade ### 'Silva João'::pdb.slop(2)
-- Allows transposition (slop of 2)
```

---

## JSON/JSONB Indexing

**CRITICAL for AutomaSEI:** ParadeDB **automatically indexes all sub-fields** of JSON/JSONB columns!

### Automatic Sub-Field Indexing

```sql
CREATE INDEX search_idx ON processos
USING bm25 (id, metadata)
WITH (key_field='id');
```

If `metadata` is:
```json
{
  "color": "Silver",
  "location": "United States"
}
```

ParadeDB automatically indexes:
- `metadata.color` as text
- `metadata.location` as text

### Querying JSON Sub-Fields

```sql
-- Search within JSON
SELECT * FROM processos
WHERE metadata ||| 'United States';

-- Configure tokenizer for entire JSON
CREATE INDEX search_idx ON processos
USING bm25 (id, (metadata::pdb.ngram(2,3)))
WITH (key_field='id');

-- Index individual JSON sub-fields with different tokenizers
CREATE INDEX search_idx ON processos
USING bm25 (id, ((metadata->>'location')::pdb.ngram(2,3)))
WITH (key_field='id');
```

---

## BM25 Scoring & Relevance

BM25 scores measure **relevance** for a given query. Higher scores = higher relevance.

### Usage

```sql
SELECT numero_processo, pdb.score(id)
FROM processos
WHERE numero_processo ||| '12345'
ORDER BY pdb.score(id) DESC
LIMIT 10;
```

### Highlighting

```sql
SELECT numero_processo, pdb.snippet(numero_processo), pdb.score(id)
FROM processos
WHERE numero_processo ||| '12345'
ORDER BY pdb.score(id) DESC;
```

**Output:**
```
numero_processo          | snippet                        | score
-------------------------|--------------------------------|-------
12345.001234/2024-56     | <b>12345</b>.001234/2024-56   | 8.234
```

---

## Advanced Features

### Top N Optimization

ParadeDB is **highly optimized** for `ORDER BY ... LIMIT` queries:

```sql
SELECT numero_processo, autoridade
FROM processos
WHERE numero_processo ||| '12345'
ORDER BY created_at DESC
LIMIT 20;
```

### Faceted Queries

Combine Top N results with aggregate values in a **single query**:

```sql
SELECT
    numero_processo, categoria,
    pdb.agg('{"value_count": {"field": "id"}}') OVER ()
FROM processos
WHERE categoria ||| 'restrito'
ORDER BY created_at DESC
LIMIT 20;
```

### Custom Tokenizers in Queries

Override default tokenizer at query time:

```sql
SELECT * FROM processos
WHERE numero_processo ||| '12345'::pdb.whitespace;
```

### Pretokenized Arrays

Pass exact tokens without further processing:

```sql
SELECT * FROM processos
WHERE autoridade &&& ARRAY['João', 'Silva'];
```

---

## Index Creation Best Practices

### Include All Searchable Columns

```sql
CREATE INDEX search_idx ON processos
USING bm25 (
    id,                    -- key_field (must be first)
    numero_processo,       -- searchable text
    autoridade,            -- searchable text
    categoria,             -- filterable
    status_categoria,      -- filterable
    tipo_acesso_atual,     -- filterable
    unidade,               -- searchable text
    created_at,            -- sortable
    updated_at,            -- sortable
    metadata,              -- JSON (auto-indexed sub-fields)
    documentos             -- JSON (auto-indexed sub-fields)
)
WITH (key_field='id');
```

### Token Filters

Apply stemming, lowercasing, etc.:

```sql
CREATE INDEX search_idx ON processos
USING bm25 (
    id,
    (numero_processo::pdb.simple('stemmer=portuguese')),
    (autoridade::pdb.icu)  -- Multi-language support
)
WITH (key_field='id');
```

### Monitor Progress

For long-running index creation:

```sql
SELECT pid, phase, blocks_done, blocks_total
FROM pg_stat_progress_create_index;
```

---

## Integration with SQLAlchemy

### Model Definition

```python
from sqlalchemy import Column, String, TIMESTAMP, JSON, Boolean
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Processo(Base):
    __tablename__ = "processos"

    id = Column(String, primary_key=True)
    numero_processo = Column(String, nullable=False, unique=True, index=True)
    autoridade = Column(String)
    categoria = Column(String)
    status_categoria = Column(String)
    tipo_acesso_atual = Column(String)
    unidade = Column(String)
    sem_link_validos = Column(Boolean, default=False)
    apelido = Column(String)
    institution_id = Column(String, ForeignKey("institutions.id"))

    # JSONB for flexible data
    links = Column(JSONB, default={})
    documentos = Column(JSONB, default={})
    metadata = Column(JSONB, default={})

    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)
```

### Querying with SQLAlchemy

```python
from sqlalchemy import text

# Match disjunction
results = session.execute(
    text("SELECT * FROM processos WHERE numero_processo ||| :query"),
    {"query": "12345"}
).fetchall()

# BM25 scoring
results = session.execute(
    text("""
        SELECT numero_processo, pdb.score(id) as score
        FROM processos
        WHERE numero_processo ||| :query
        ORDER BY score DESC
        LIMIT 10
    """),
    {"query": "12345"}
).fetchall()
```

---

## Important Notes for AutomaSEI

### Use Cases

1. **Process Search:**
   - Search by `numero_processo` with fuzzy matching
   - Filter by `categoria`, `status_categoria`, `tipo_acesso_atual`
   - Sort by BM25 relevance or `created_at`

2. **Authority Search:**
   - Full-text search on `autoridade` field
   - Support for partial names (e.g., "João" returns all João's)

3. **Document Search within Process:**
   - Index `documentos` JSONB column
   - Search document metadata (tipo, numero, assinantes)
   - ParadeDB will auto-index all sub-fields

4. **Flexible Metadata:**
   - `metadata` JSONB for institution-specific custom fields
   - Searchable without schema changes

### Performance Tips

- **Index EVERYTHING** you might search, filter, or sort on
- Use **Top N** queries (`ORDER BY ... LIMIT`) for best performance
- Run `VACUUM` periodically to refresh BM25 scores
- Consider autovacuum for production

### Migration from MongoDB

MongoDB uses substring matching by default. ParadeDB uses **token matching**.

**Example:**
- MongoDB: `{"numero_processo": {"$regex": "12345"}}`
- ParadeDB: `WHERE numero_processo ||| '12345'`

For exact substring matching, use regex:
```sql
WHERE numero_processo @@@ pdb.regex('12345')
```

---

## v2 API Improvements (Current)

ParadeDB v2 focuses on:

1. **Declarative Schema Configuration**
   - No complex JSON strings for tokenizers
   - Clean syntax: `description::pdb.ngram(2,3)`

2. **Transparent Search Operators**
   - `|||`, `&&&`, `###` make intent clear
   - More intuitive than complex function calls

3. **ORM-Friendly Query Builders**
   - Structured column references
   - Compatible with SQLAlchemy, Django ORM, etc.

**Target:** Full v1 coverage by **October 2025**

---

## Resources

- **ParadeDB Docs:** https://docs.paradedb.com
- **GitHub:** https://github.com/paradedb/paradedb
- **Docker Image:** `paradedb/paradedb:latest`
- **PostgreSQL Compatibility:** Full PostgreSQL compatibility (no fork)

---

## Next Steps for AutomaSEI

1. ✅ Create SQLAlchemy models with JSONB columns
2. ✅ Configure Alembic migrations
3. ✅ Create BM25 indexes via migration
4. ✅ Implement Repository Pattern with ParadeDB queries
5. ✅ Test full-text search on `numero_processo` and `autoridade`
6. ✅ Benchmark search performance vs MongoDB
