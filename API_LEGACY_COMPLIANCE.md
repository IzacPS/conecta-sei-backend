# API Legacy Compliance

**Princípio Fundamental:** Toda a API v2.0 DEVE estar em **conformidade total com o código legacy** (v1.0.10).

**Data:** 2025-12-16 (Sprint 3.1)

---

## 1. Objetivo da Refatoração

**AutomaSEI v2.0 é uma REFATORAÇÃO, não uma reescrita.**

### O que isso significa:

✅ **FAZER:**
- Migrar código legacy para arquitetura moderna (FastAPI + PostgreSQL)
- Manter **100% compatibilidade** com estrutura de dados do legacy
- Preservar **todos os campos** exatamente como estão no legacy
- Manter **mesma lógica de negócio** do legacy
- Melhorar organização, performance e manutenibilidade

❌ **NÃO FAZER:**
- Adicionar features novas que não existem no legacy
- Remover campos do legacy
- Renomear campos sem alias (quebra compatibilidade)
- Mudar lógica de negócio
- "Melhorar" estruturas de dados (manter as originais)

---

## 2. Fontes de Verdade (Legacy Code)

Ao criar schemas, routers ou core logic, **sempre consultar**:

### Estrutura de Dados:

1. **MongoDB Schema (implícito)**
   - Examinar queries em `connect_mongo.py` e `get_*.py`
   - Estrutura real dos documentos no banco

2. **Modelos Python:**
   - `database/models.py` - ProcessData dataclass (legacy)
   - `database/models_sqlalchemy.py` - Process, Institution (novo, mas baseado no legacy)

3. **Scrapers (lógica de extração):**
   - `get_process_update.py` - Stage 1 (descoberta de processos)
   - `get_process_links_status.py` - Stage 2 (validação de links)
   - `get_process_docs_update.py` - Stage 3 (extração de documentos)
   - `get_docs_download.py` - Stage 4 (download de documentos)

### Lógica de Negócio:

1. **Utils:**
   - `utils.py` (legacy) / `utils/*.py` (refatorado)
   - Funções como `should_process_documents()`, `login_to_sei()`, etc.

2. **Email/Notificações:**
   - `email_api_ms.py` (legacy)
   - `utils/email_service.py` (migrado)
   - Consultar `LEGACY_NOTIFICATION_FLOW.md`

3. **UI:**
   - `ui_*.py` - Lógica de interface
   - Indica comportamento esperado pelo usuário

---

## 3. Mapeamento de Campos - Processo

### Campos do Legacy → API Schema

**Fonte:** `database/models_sqlalchemy.py:Process` (linha 150-199)

| Campo Legacy | Tipo | API Schema | Descrição | Obrigatório |
|--------------|------|------------|-----------|-------------|
| `id` | String(36) | `id` | UUID do processo | Sim |
| `institution_id` | String(50) | `institution_id` | FK para instituição | Sim |
| `numero_processo` | String(50) | `numero_processo` (alias: `process_number`) | Número único do processo | Sim |
| `links` | JSONB | `links: Dict[str, Any]` | Links de acesso | Sim (default {}) |
| `documentos` | JSONB | `documentos: Dict[str, Any]` | Documentos do processo | Sim (default {}) |
| `tipo_acesso_atual` | String(20) | `tipo_acesso_atual` | "integral", "parcial", "error" | Não |
| `melhor_link_atual` | String(255) | `melhor_link_atual` | ID do melhor link | Não |
| `categoria` | String(50) | `categoria` | Ex: "restrito", "publico" | Não |
| `status_categoria` | String(50) | `status_categoria` | "pendente", "categorizado" | Não |
| `unidade` | String(255) | `unidade` | Unidade administrativa | Não |
| `autoridade` | String(255) | `autoridade` (alias: `Autoridade`) | Autoridade (com A maiúsculo no legacy!) | Não |
| `sem_link_validos` | Boolean | `sem_link_validos` | Flag de links inválidos | Sim (default False) |
| `apelido` | String(255) | `apelido` | Nickname do processo | Não |
| `ultima_atualizacao` | String(50) | `ultima_atualizacao` | ISO string (legacy format) | Não |
| `created_at` | DateTime(TZ) | `created_at` | Data de criação | Sim |
| `updated_at` | DateTime(TZ) | `updated_at` | Data de atualização | Não |
| `metadata` | JSONB | `metadata: Dict[str, Any]` | Metadados extras | Sim (default {}) |

#### ⚠️ Atenção Especial:

1. **`Autoridade` vs `autoridade`:**
   - Legacy usa `"Autoridade"` (maiúsculo) em alguns lugares
   - SQLAlchemy usa `autoridade` (minúsculo)
   - API Schema: usar **alias** para aceitar ambos

2. **`numero_processo` vs `process_number`:**
   - DB/Legacy: `numero_processo`
   - API (user-friendly): `process_number` como alias
   - Internamente sempre `numero_processo`

3. **Valores de Enums (NÃO são enums reais no legacy!):**
   - `tipo_acesso_atual`: string livre, mas geralmente "integral"/"parcial"/"error"
   - `categoria`: string livre, mas geralmente "restrito" ou outros
   - `status_categoria`: string livre, mas geralmente "pendente"/"categorizado"
   - **Na API: usar `str`, não Enum** (legacy não valida)

---

## 4. Estrutura de Documentos (JSONB)

### Campo `links` (JSONB)

**Fonte:** `get_process_links_status.py:89-107`

```python
{
    "ABC123": {
        "status": "Ativo",  # ou "Inativo"
        "tipo_acesso": "integral",  # ou "parcial" ou "error"
        "ultima_verificacao": "2024-01-15 14:30:00",  # formato: YYYY-MM-DD HH:MM:SS
        "historico": [
            {
                "data": "2024-01-15 14:30:00",
                "status": "Ativo",
                "tipo_acesso": "integral"
            }
        ]
    }
}
```

### Campo `documentos` (JSONB)

**Fonte:** `get_process_docs_update.py:166-172`

```python
{
    "12345678": {
        "tipo": "Despacho",  # tipo do documento
        "data": "15/01/2024",  # formato dd/mm/yyyy
        "status": "nao_baixado",  # ou "baixado" ou "erro"
        "ultima_verificacao": "15/01/2024 14:30:00",  # formato dd/mm/yyyy HH:MM:SS
        "signatario": "João Silva"  # ou "Autoridade Competente" (default)
    }
}
```

### Campo `metadata` (JSONB)

Campos extras não estruturados. No legacy, usado para:
- Dados de migração
- Flags temporárias
- Informações específicas de instituição

---

## 5. Estrutura de Instituições

### Campos do Legacy → API Schema

**Fonte:** `database/models_sqlalchemy.py:Institution` (linha 95-125)

| Campo Legacy | Tipo | API Schema | Descrição | Obrigatório |
|--------------|------|------------|-----------|-------------|
| `id` | String(50) | `id` | ID único (user-defined) | Sim |
| `name` | String(255) | `name` | Nome da instituição | Sim |
| `url` | String(500) | `url` | URL do sistema SEI | Sim |
| `scraper_version` | String(50) | `scraper_version` | Versão do scraper (v1, v2) | Sim |
| `is_active` | Boolean | `is_active` | Se instituição está ativa | Sim (default True) |
| `metadata` | JSONB | `metadata: Dict[str, Any]` | Metadados extras | Sim (default {}) |
| `created_at` | DateTime(TZ) | `created_at` | Data de criação | Sim |
| `updated_at` | DateTime(TZ) | `updated_at` | Data de atualização | Não |

---

## 6. Regras de Validação (do Legacy)

### Número de Processo

**Fonte:** Observado em `get_process_update.py` e diversos arquivos

**Formato:** `12345.001234/2024-56`

**Regex:** `^\d{5}\.\d{6}/\d{4}-\d{2}$`

**Componentes:**
- 5 dígitos
- ponto
- 6 dígitos
- barra
- 4 dígitos (ano)
- hífen
- 2 dígitos

### Número de Documento

**Fonte:** `get_process_docs_update.py:154`

**Formato:** `12345678` (8 dígitos)

**Regex:** `^\d{8}$`

### Tipo de Acesso

**Fonte:** `get_process_links_status.py:26-34`

**Valores possíveis:**
- `"integral"` - Acesso completo ao processo
- `"parcial"` - Acesso parcial (requer categorização)
- `"error"` - Erro ao acessar

**Detecção:** Baseada em texto do SEI:
- "Acesso Externo com Acompanhamento Integral" → `"integral"`
- "Acesso Externo com Disponibilização Parcial" → `"parcial"`

### Status de Categoria

**Fonte:** `get_process_links_status.py:109-128`

**Valores possíveis:**
- `"pendente"` - Processo aguardando categorização manual
- `"categorizado"` - Processo já categorizado

**Lógica:**
- Processo `integral`: automaticamente `"categorizado"` + categoria `"restrito"`
- Processo `parcial` **novo**: automaticamente `"pendente"`
- Processo `parcial` **já categorizado**: mantém `"categorizado"`

---

## 7. Lógica de Negócio Crítica

### `should_process_documents()`

**Fonte:** `utils.py:93-115` (legacy) / `utils/process_utils.py:93-115` (refatorado)

**Lógica EXATA do legacy:**

```python
def should_process_documents(process_data: Dict) -> bool:
    """
    Determina se documentos de um processo devem ser extraídos.

    Regras (do legacy):
    1. Se não tem links válidos → False
    2. Se tipo_acesso == "integral" → True (sempre processar)
    3. Se tipo_acesso == "parcial":
        a. Se status_categoria == "pendente" → False
        b. Se categoria == "restrito" → True
        c. Caso contrário → False
    """
    if process_data.get("sem_link_validos"):
        return False

    tipo_acesso = process_data.get("tipo_acesso_atual", "parcial")

    if tipo_acesso == "integral":
        return True

    # Acesso parcial: só processa em casos específicos
    status_categoria = process_data.get("status_categoria")
    categoria = process_data.get("categoria")

    if status_categoria == "pendente":
        return False

    if categoria == "restrito":
        return True

    return False
```

**⚠️ NUNCA mudar esta lógica na API v2.0!**

### Notificações

**Fonte:** `LEGACY_NOTIFICATION_FLOW.md`

**Tipos de notificação (apenas 2 tipos de EMAIL):**

1. **`notify_categorization_needed()`**
   - **Quando:** Final da Stage 2 (get_process_links_status.py:294)
   - **O que:** Email com TODOS os processos com `status_categoria == "pendente"`
   - **Estrutura:**
     ```python
     [
         {"process_number": "12345.001234/2024-56", "link": "ABC123"},
         ...
     ]
     ```

2. **`notify_new_documents()`**
   - **Quando:** Final da Stage 3 (get_process_docs_update.py:468)
   - **O que:** Email com novos documentos detectados
   - **Estrutura:**
     ```python
     {
         "12345.001234/2024-56": {
             "apelido": "Processo Importante",
             "documentos_por_signatario": {
                 "João Silva": ["Petição 12345678", "Procuração 87654321"],
                 "Maria Santos": ["Resposta 11223344"]
             }
         }
     }
     ```

3. **`notify_process_update()` (LOG APENAS, não email)**
   - **Quando:** Durante Stage 2, mudanças de acesso
   - **O que:** Apenas loga no console, **NÃO envia email**

---

## 8. Checklist de Conformidade

Ao criar **qualquer** componente da API v2.0:

### ✅ Schemas (Pydantic)

- [ ] Todos os campos do legacy presentes?
- [ ] Tipos de dados idênticos ao legacy?
- [ ] Aliases configurados onde necessário? (`numero_processo`/`process_number`, `Autoridade`/`autoridade`)
- [ ] Defaults idênticos ao legacy?
- [ ] Validações compatíveis com legacy? (regex, constraints)
- [ ] JSONB fields mapeados como `Dict[str, Any]`?
- [ ] Documentação menciona fonte no legacy?

### ✅ Routers (FastAPI)

- [ ] Endpoints refletem operações do legacy?
- [ ] Parâmetros de query compatíveis?
- [ ] Lógica de negócio **exata** do legacy preservada?
- [ ] Usa repositories (não acessa DB diretamente)?
- [ ] Tratamento de erros similar ao legacy?

### ✅ Core Logic

- [ ] Lógica **IDÊNTICA** ao legacy?
- [ ] Nenhuma "melhoria" de lógica sem consultar legacy?
- [ ] Mantém quirks e edge cases do legacy?
- [ ] Documentado qual arquivo legacy é a fonte?

### ✅ Repositories

- [ ] Queries refletem estrutura do legacy MongoDB?
- [ ] Filtros equivalentes?
- [ ] Ordenação igual ao legacy?

---

## 9. Quando Divergir do Legacy

**Regra geral: NUNCA divergir sem justificativa clara.**

**Exceções permitidas:**

1. **Otimizações de performance**
   - Ex: Índices adicionais no PostgreSQL
   - Ex: Connection pooling
   - **Condição:** Não muda o comportamento observável

2. **Correção de bugs óbvios**
   - Ex: Memory leak
   - Ex: SQL injection (se existir)
   - **Condição:** Documentar o bug e a correção

3. **Arquitetura interna**
   - Ex: Repository Pattern vs queries diretas
   - Ex: SQLAlchemy vs PyMongo
   - **Condição:** Interface externa idêntica

4. **Features explicitamente solicitadas**
   - Ex: "adicionar campo X para feature Y"
   - **Condição:** Aprovação explícita + documentação

**Em TODOS os casos:**
- Documentar divergência em `API_LEGACY_COMPLIANCE.md`
- Justificar a razão
- Garantir que não quebra compatibilidade

---

## 10. Processo de Desenvolvimento

### Antes de Escrever Código:

1. **Identificar fonte no legacy**
   - Qual arquivo contém a lógica?
   - Qual linha específica?

2. **Ler e entender o legacy**
   - Qual é o comportamento **exato**?
   - Há edge cases? Quirks?

3. **Mapear campos/lógica**
   - Fazer lista de campos 1:1
   - Documentar diferenças (se houver)

### Durante o Desenvolvimento:

4. **Consultar legacy frequentemente**
   - Não confiar na memória
   - Verificar detalhes (tipos, defaults, validações)

5. **Preservar nomenclatura**
   - Usar **exatamente** os mesmos nomes de campos
   - Aliases apenas para API user-friendly

6. **Testar com dados reais**
   - Usar dados do MongoDB legacy
   - Verificar compatibilidade

### Após o Desenvolvimento:

7. **Documentar conformidade**
   - Atualizar este arquivo
   - Referenciar linhas do legacy

8. **Code review focado em conformidade**
   - Outro desenvolvedor verifica legacy
   - Confirma que comportamento é idêntico

---

## 11. Referências Rápidas

### Arquivos Legacy Mais Importantes:

| Arquivo | Propósito | Consultar Para |
|---------|-----------|----------------|
| `database/models_sqlalchemy.py` | Modelos PostgreSQL | Estrutura de dados, tipos, constraints |
| `database/models.py` | ProcessData dataclass | Estrutura original do legacy |
| `get_process_links_status.py` | Stage 2 - Validação de links | Lógica de acesso, categorização |
| `get_process_docs_update.py` | Stage 3 - Extração de docs | Estrutura de documentos, signatários |
| `utils.py` / `utils/*.py` | Utilitários | Funções helper, lógica de negócio |
| `email_api_ms.py` | Notificações | Estrutura de emails, quando enviar |
| `LEGACY_NOTIFICATION_FLOW.md` | Documentação de notificações | Fluxo completo de notificações |

### Documentação de Referência:

- `REFACTOR_PROGRESS.md` - Progresso da refatoração
- `CLAUDE.md` - Visão geral do projeto legacy
- `DATABASE_SETUP.md` - Setup do PostgreSQL
- `MONGODB_TO_POSTGRES_MIGRATION.md` - Guia de migração

---

## 12. Exemplo Completo: Campo `Autoridade`

### No Legacy (MongoDB):

```python
# database/models.py:108
Autoridade: Optional[str] = None  # com A maiúsculo

# get_process_links_status.py:54
process_data["Autoridade"] = parts[2].strip()  # com A maiúsculo
```

### No PostgreSQL:

```python
# database/models_sqlalchemy.py:178
autoridade = Column(String(255))  # minúsculo (convenção SQL)
```

### No API Schema:

```python
# api/schemas.py
class ProcessResponse(BaseModel):
    autoridade: Optional[str] = Field(
        None,
        description="Autoridade do processo",
        alias="Autoridade"  # ← aceita ambos!
    )
```

### Resultado:

✅ API aceita: `{"Autoridade": "João Silva"}` (legacy format)
✅ API aceita: `{"autoridade": "João Silva"}` (novo format)
✅ DB armazena: `autoridade` (coluna lowercase)
✅ API retorna: `autoridade` (por padrão, mas pode retornar `Autoridade` se configurado)

---

**Última Atualização:** 2025-12-16 (Sprint 3.1)

**Responsável:** Claude Sonnet 4.5 (AutomaSEI v2.0 Refactoring)
