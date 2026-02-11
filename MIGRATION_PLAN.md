# MongoDB → PostgreSQL Migration Plan

**AutomaSEI v2.0 - Sprint 4.1**
**Data:** 2025-12-16
**Objetivo:** Migrar dados do MongoDB para PostgreSQL + ParadeDB mantendo 100% dos dados

---

## 📋 Resumo Executivo

Este documento descreve o plano completo de migração dos dados do AutomaSEI v1.0.10 (MongoDB) para v2.0 (PostgreSQL + ParadeDB).

**Estratégia:**
- Migração **não destrutiva** (MongoDB permanece intacto)
- Validação completa de dados migrados
- Rollback automático em caso de erro
- Backup antes da migração
- Dry-run mode para testes

---

## 🗂️ Estrutura de Dados

### MongoDB (Legacy)

**Database:** `sei_database`

**Collections:**
1. **processos** - Processos do SEI
2. **configuracoes** - Configurações do sistema
3. **documentos_historico** (opcional) - Histórico de downloads

### PostgreSQL (v2.0)

**Database:** `automasei_v2`

**Tables:**
1. **institutions** - Instituições (NOVO)
2. **processes** - Processos migrados
3. **document_history** - Histórico de documentos
4. **system_configuration** - Configurações migradas

---

## 🔄 Mapeamento de Dados

### Collection: `processos` → Table: `processes`

| Campo MongoDB | Tipo | Campo PostgreSQL | Transformação |
|---------------|------|------------------|---------------|
| `numero_processo` | String | `numero_processo` | Direto |
| `links` | Object | `links` (JSONB) | Direto |
| `documentos` | Object | `documentos` (JSONB) | Direto |
| `tipo_acesso_atual` | String | `tipo_acesso_atual` | Direto |
| `melhor_link_atual` | String | `melhor_link_atual` | Direto |
| `categoria` | String | `categoria` | Direto |
| `status_categoria` | String | `status_categoria` | Direto |
| `unidade` | String | `unidade` | Direto |
| `Autoridade` | String | `autoridade` | Direto (lowercase na tabela) |
| `sem_link_validos` | Boolean | `sem_link_validos` | Direto |
| `apelido` | String | `apelido` | Direto |
| `ultima_atualizacao` | String | `ultima_atualizacao` | Direto |
| - | - | `id` | **GERAR UUID** |
| - | - | `institution_id` | **DEFINIR DEFAULT** |
| - | - | `created_at` | **CALCULAR** de `ultima_atualizacao` |
| - | - | `updated_at` | **CALCULAR** de `ultima_atualizacao` |
| - | - | `metadata` | {} (vazio por padrão) |

**Novos campos obrigatórios:**
- `id`: Gerar UUID único para cada processo
- `institution_id`: Atribuir instituição padrão (criar "legacy" se necessário)
- `created_at`: Derivar de `ultima_atualizacao` ou usar data atual
- `updated_at`: Derivar de `ultima_atualizacao` ou usar data atual

### Collection: `configuracoes` → Table: `system_configuration`

| Campo MongoDB | Tipo | Campo PostgreSQL | Transformação |
|---------------|------|------------------|---------------|
| `tipo` | String | `key` | Direto |
| `{rest}` | Object | `value` (JSONB) | Todo o documento exceto `tipo` |
| - | - | `description` | Vazio |
| - | - | `created_at` | Data atual |
| - | - | `updated_at` | Data atual |
| - | - | `updated_by` | "migration_script" |

**Exemplos:**

MongoDB:
```json
{
  "tipo": "credenciais_acesso",
  "email": "user@example.com",
  "senha": "encrypted"
}
```

PostgreSQL:
```sql
key = 'credenciais_acesso'
value = '{"email": "user@example.com", "senha": "encrypted"}'
description = ''
```

### Collection: `documentos_historico` → Table: `document_history`

**NOTA:** Esta collection pode não existir no MongoDB legacy (feature nova v2.0).

Se existir:

| Campo MongoDB | Tipo | Campo PostgreSQL | Transformação |
|---------------|------|------------------|---------------|
| `processo_numero` | String | `process_id` | **RESOLVER UUID** via `numero_processo` |
| `documento_numero` | String | `document_number` | Direto |
| `tipo_operacao` | String | `action` | Direto |
| `resultado` | String | `new_status` | Direto |
| `timestamp_inicio` | DateTime | `timestamp` | Direto |
| `{metadata}` | Object | `details` (JSONB) | Todos os outros campos |
| - | - | `id` | **GERAR UUID** |

---

## 🏗️ Estratégia de Migração

### Fase 1: Preparação (Pre-Migration)

1. **Criar instituição padrão** ("legacy")
   - `id`: "legacy"
   - `name`: "Legacy Institution (SEI)"
   - `sei_url`: Carregar de `configuracoes.url_sistema`
   - `scraper_version`: "v1.0.10"
   - `sei_family`: "v1"
   - `active`: True

2. **Backup do MongoDB**
   - Criar dump completo antes da migração
   - Salvar em `backups/mongodb_dump_{timestamp}.json`

3. **Verificar PostgreSQL vazio**
   - Garantir que tabelas estão vazias (ou fazer TRUNCATE CASCADE)
   - Ou criar novo database se preferível

### Fase 2: Migração de Configurações

1. Carregar `configuracoes` do MongoDB
2. Para cada documento:
   - Criar registro em `system_configuration`
   - `key` = campo `tipo`
   - `value` = documento completo (exceto `tipo`)

3. **Configurações críticas:**
   - `url_sistema` → usado para criar instituição "legacy"
   - `credenciais_acesso` → migrado para `system_configuration`
   - `email_notifications` → migrado para `system_configuration`

### Fase 3: Migração de Processos

1. Carregar todos os processos do MongoDB (`db.processos.find({})`)

2. Para cada processo:
   - Gerar UUID único
   - Atribuir `institution_id = "legacy"`
   - Mapear todos os campos conforme tabela acima
   - Converter `Autoridade` → `autoridade` (lowercase)
   - Calcular `created_at` e `updated_at` de `ultima_atualizacao`

3. **Validações:**
   - `numero_processo` é único
   - `links` e `documentos` são JSONB válidos
   - Campos obrigatórios preenchidos

4. **Tratamento de erros:**
   - Log de processos com erros
   - Continuar migração (não abortar)
   - Criar relatório de erros ao final

### Fase 4: Validação Pós-Migração

1. **Contagem de registros:**
   - MongoDB `processos.count()` == PostgreSQL `SELECT COUNT(*) FROM processes`
   - MongoDB `configuracoes.count()` == PostgreSQL `SELECT COUNT(*) FROM system_configuration`

2. **Amostragem aleatória:**
   - Selecionar 10 processos aleatórios
   - Comparar dados campo a campo

3. **Integridade referencial:**
   - Todos os processos têm `institution_id = "legacy"`
   - Instituição "legacy" existe

4. **Relatório de validação:**
   - Total de registros migrados
   - Total de erros
   - Processos com dados faltando
   - Tempo de migração

---

## 🔧 Implementação

### Script: `migrate_mongodb_to_postgres.py`

**Argumentos:**

```bash
python migrate_mongodb_to_postgres.py [OPTIONS]

Opções:
  --dry-run          Simula migração sem escrever no PostgreSQL
  --skip-backup      Pula criação de backup do MongoDB
  --clear-postgres   Limpa tabelas PostgreSQL antes de migrar
  --validate-only    Apenas valida dados sem migrar
  --batch-size N     Migra em lotes de N processos (padrão: 100)
  --verbose          Log detalhado
```

**Estrutura:**

```python
class DataMigration:
    def __init__(self, dry_run=False, batch_size=100):
        self.dry_run = dry_run
        self.batch_size = batch_size
        self.stats = {
            "total_processes": 0,
            "migrated_processes": 0,
            "total_configs": 0,
            "migrated_configs": 0,
            "errors": [],
        }

    def run(self):
        """Executa migração completa."""
        self.backup_mongodb()
        self.create_legacy_institution()
        self.migrate_configurations()
        self.migrate_processes()
        self.validate_migration()
        self.generate_report()

    def backup_mongodb(self):
        """Cria backup JSON de todas as collections."""
        pass

    def create_legacy_institution(self):
        """Cria instituição 'legacy' para processos antigos."""
        pass

    def migrate_configurations(self):
        """Migra collection 'configuracoes' → 'system_configuration'."""
        pass

    def migrate_processes(self):
        """Migra collection 'processos' → 'processes'."""
        pass

    def validate_migration(self):
        """Valida integridade dos dados migrados."""
        pass

    def generate_report(self):
        """Gera relatório de migração."""
        pass
```

---

## 📊 Validação de Dados

### Checklist de Validação

**Configurações:**
- [ ] Todas as configurações migradas (contagem correta)
- [ ] `url_sistema` presente
- [ ] `credenciais_acesso` presente
- [ ] Formato JSONB válido

**Processos:**
- [ ] Contagem igual (MongoDB == PostgreSQL)
- [ ] Todos têm UUID único
- [ ] Todos têm `institution_id = "legacy"`
- [ ] `numero_processo` é único (constraint OK)
- [ ] Campos JSONB válidos (`links`, `documentos`)
- [ ] Nenhum campo obrigatório NULL

**Instituição Legacy:**
- [ ] ID = "legacy"
- [ ] `sei_url` correto (de `configuracoes.url_sistema`)
- [ ] Todos os processos referenciam esta instituição

### Queries de Validação

```sql
-- Contar processos
SELECT COUNT(*) FROM processes;

-- Verificar institution_id
SELECT institution_id, COUNT(*)
FROM processes
GROUP BY institution_id;

-- Verificar processos sem instituição (deveria ser 0)
SELECT COUNT(*)
FROM processes
WHERE institution_id IS NULL;

-- Verificar duplicatas de numero_processo (deveria ser 0)
SELECT numero_processo, COUNT(*)
FROM processes
GROUP BY numero_processo
HAVING COUNT(*) > 1;

-- Amostra de dados
SELECT id, numero_processo, institution_id, categoria, tipo_acesso_atual
FROM processes
LIMIT 10;

-- Verificar JSONB válido
SELECT id, numero_processo
FROM processes
WHERE links IS NULL OR documentos IS NULL;

-- Configurações
SELECT key, updated_by, created_at
FROM system_configuration
ORDER BY key;
```

---

## 🚨 Rollback Plan

Se a migração falhar:

1. **PostgreSQL:** DROP DATABASE ou TRUNCATE CASCADE
2. **MongoDB:** Permanece intacto (não foi modificado)
3. **Restaurar estado:** PostgreSQL vazio, MongoDB inalterado
4. **Análise:** Revisar logs de erro e corrigir script

**Backup criado automaticamente em:**
- `backups/mongodb_dump_{timestamp}.json`

---

## ⚠️ Riscos e Mitigações

### Risco 1: Perda de Dados

**Mitigação:**
- Backup completo antes da migração
- Validação pós-migração obrigatória
- MongoDB não é modificado (apenas leitura)

### Risco 2: Dados Inconsistentes

**Mitigação:**
- Validação campo a campo
- Amostragem aleatória
- Relatório de erros detalhado

### Risco 3: Falha no Meio da Migração

**Mitigação:**
- Migração em lotes (batch_size)
- Transações PostgreSQL (commit por lote)
- Log de progresso

### Risco 4: institution_id Incorreto

**Mitigação:**
- Criar instituição "legacy" ANTES de migrar processos
- Validar FK antes de commit

### Risco 5: JSONB Inválido

**Mitigação:**
- Validar estrutura JSONB antes de inserir
- Try/catch em cada inserção
- Log de processos com JSONB inválido

---

## 📝 Exemplo de Migração

### MongoDB → PostgreSQL

**MongoDB (processos):**
```json
{
  "numero_processo": "12345.001234/2024-56",
  "links": {
    "ABC123": {
      "tipo_acesso": "integral",
      "valido": true
    }
  },
  "documentos": {
    "12345678": {
      "tipo": "Despacho",
      "data": "15/01/2024"
    }
  },
  "tipo_acesso_atual": "integral",
  "melhor_link_atual": "ABC123",
  "categoria": "restrito",
  "status_categoria": "categorizado",
  "Autoridade": "João Silva",
  "sem_link_validos": false,
  "ultima_atualizacao": "2024-01-15 10:30:00"
}
```

**PostgreSQL (processes):**
```sql
INSERT INTO processes (
  id,
  institution_id,
  numero_processo,
  links,
  documentos,
  tipo_acesso_atual,
  melhor_link_atual,
  categoria,
  status_categoria,
  autoridade,
  sem_link_validos,
  ultima_atualizacao,
  created_at,
  updated_at,
  metadata
) VALUES (
  'uuid-generated',                    -- NOVO
  'legacy',                             -- NOVO
  '12345.001234/2024-56',
  '{"ABC123": {"tipo_acesso": "integral", "valido": true}}'::jsonb,
  '{"12345678": {"tipo": "Despacho", "data": "15/01/2024"}}'::jsonb,
  'integral',
  'ABC123',
  'restrito',
  'categorizado',
  'João Silva',                         -- lowercase (Autoridade → autoridade)
  false,
  '2024-01-15 10:30:00',
  '2024-01-15 10:30:00'::timestamp,    -- NOVO (de ultima_atualizacao)
  '2024-01-15 10:30:00'::timestamp,    -- NOVO (de ultima_atualizacao)
  '{}'::jsonb                           -- NOVO (vazio)
);
```

---

## 🎯 Critérios de Sucesso

A migração é considerada bem-sucedida se:

✅ **100% dos processos migrados** (contagem igual)
✅ **100% das configurações migradas** (contagem igual)
✅ **0 processos com dados NULL obrigatórios**
✅ **0 duplicatas de numero_processo**
✅ **Amostragem validada** (10 processos comparados manualmente)
✅ **Instituição "legacy" criada corretamente**
✅ **Todos os FKs válidos**
✅ **Backup do MongoDB criado**
✅ **Relatório de migração gerado**

---

## 📋 Checklist de Execução

### Antes de Executar:

- [ ] PostgreSQL rodando e acessível
- [ ] MongoDB rodando e acessível
- [ ] Database PostgreSQL criado (`automasei_v2`)
- [ ] Migrations Alembic executadas (tabelas criadas)
- [ ] Espaço em disco suficiente para backup
- [ ] Credenciais de ambos os bancos configuradas

### Durante Execução:

- [ ] Executar com `--dry-run` primeiro
- [ ] Revisar output do dry-run
- [ ] Executar migração real
- [ ] Monitorar logs de erro
- [ ] Aguardar conclusão

### Após Execução:

- [ ] Revisar relatório de migração
- [ ] Executar queries de validação
- [ ] Comparar contagens (MongoDB vs PostgreSQL)
- [ ] Testar API com dados migrados
- [ ] Commit do backup criado
- [ ] Atualizar documentação

---

## 🔍 Próximos Passos

Após migração bem-sucedida:

1. **Sprint 4.2 - Testing**
   - Testes de integração com dados reais
   - Performance testing
   - E2E tests

2. **Deprecar código MongoDB**
   - Mover `utils/database.py` para `legacy/`
   - Atualizar imports em código legacy (`ui_*.py`, `get_*.py`)
   - Marcar funções legacy como deprecated

3. **Production deployment**
   - Deploy gradual
   - Monitoramento
   - Rollback plan ready

---

**FIM DO PLANO DE MIGRAÇÃO**

**Próxima ação:** Implementar `migrate_mongodb_to_postgres.py` conforme este plano.
