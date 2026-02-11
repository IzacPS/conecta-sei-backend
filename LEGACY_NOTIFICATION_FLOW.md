# Fluxo de Notificações no Legacy

**Documentação do comportamento atual** - AutomaSEI v1.0.10
**Data:** 2025-12-15 (Sprint 2.3)

---

## Resumo Executivo

O sistema legado **NÃO** detecta mudanças automáticas de `status_categoria` ou `categoria`.

As notificações são enviadas **apenas** durante a execução dos scrapers, baseadas em **eventos pontuais**:

1. ✅ **Novos processos** (processo parcial que precisa de categorização)
2. ✅ **Mudança de acesso** (parcial → integral)
3. ✅ **Novos documentos** detectados
4. ❌ **NÃO notifica** mudanças de status_categoria
5. ❌ **NÃO notifica** mudanças de categoria

---

## Funções de Notificação

### 1. `notify_categorization_needed(process_set: List[dict])`

**Arquivo:** [email_api_ms.py:146](email_api_ms.py#L146)

**Quando é chamado:**
- [get_process_links_status.py:294](get_process_links_status.py#L294) - **FINAL da execução**
- Envia email com **TODOS** os processos que têm `status_categoria == "pendente"`

**Formato do email:**
```
Assunto: Processos Necessitam de Categorização

Os seguintes processos necessitam ser categorizados:
- Processo 1 (link)
- Processo 2 (link)
...

Esses processos possuem acesso parcial e requerem análise.
```

**Estrutura dos dados:**
```python
process_set = [
    {"process_number": "12345.001234/2024-56", "link": "ABC123"},
    {"process_number": "67890.005678/2024-78", "link": "DEF456"}
]
```

---

### 2. `notify_new_documents(process_data: Dict[str, Dict])`

**Arquivo:** [email_api_ms.py:160](email_api_ms.py#L160)

**Quando é chamado:**
- [get_process_docs_update.py:468](get_process_docs_update.py#L468) - Quando novos documentos são detectados

**Formato do email:**
```
Assunto: Novos Documentos Encontrados

Processo: Apelido do Processo (12345.001234/2024-56)
Signatários e Documentos Enviados:

* João Silva:
   - Petição 12345678
   - Procuração 87654321

* Maria Santos:
   - Resposta 11223344

Data: 15/12/2025 14:30
```

**Estrutura dos dados:**
```python
process_data_grouped = {
    "12345.001234/2024-56": {
        "apelido": "Processo Importante",
        "documentos_por_signatario": {
            "João Silva": ["Petição 12345678", "Procuração 87654321"],
            "Maria Santos": ["Resposta 11223344"]
        }
    }
}
```

---

### 3. `notify_process_update(message: str, process_id: str)`

**Arquivo:** [utils.py:79](utils.py#L79) (legacy) / [utils/process_utils.py:125](utils/process_utils.py#L125) (novo)

**IMPORTANTE:** Esta função **NÃO envia email**, apenas **loga no console**.

**Quando é chamado:**
- [get_process_links_status.py:115-118](get_process_links_status.py#L115-L118) - Quando processo muda de **parcial → integral**
- [get_process_links_status.py:126-128](get_process_links_status.py#L126-L128) - Quando processo **parcial** precisa de categorização

**Código:**
```python
def notify_process_update(message: str, process_id: str) -> None:
    """
    Notifica atualização de processo via log.

    IMPORTANTE: Esta função NÃO envia email, apenas loga.
    """
    logger = UILogger()
    logger.log(f"[PROCESSO {process_id}] {message}")
```

**Exemplos de logs:**
```
[PROCESSO 12345.001234/2024-56] Processo obteve acesso integral (anterior: parcial) - categorizado como restrito
[PROCESSO 67890.005678/2024-78] Processo com acesso parcial necessita de categorização
```

---

## Fluxo de Notificações por Etapa

### Etapa 2: Verificação de Links ([get_process_links_status.py](get_process_links_status.py))

**Lógica de notificação:**

```python
# Linha 109-118: Processo obtém acesso integral
if access_type == "integral":
    process_data["tipo_acesso_atual"] = "integral"
    process_data["categoria"] = "restrito"
    process_data["status_categoria"] = "categorizado"
    process_data["melhor_link_atual"] = link

    if old_access_type == "parcial":
        # 🔔 NOTIFICA (log apenas)
        notify_process_update(
            "Processo obteve acesso integral (anterior: parcial) - categorizado como restrito",
            process_number
        )

# Linha 119-129: Processo parcial precisa de categorização
elif access_type == "parcial" and process_data.get("tipo_acesso_atual") != "integral":
    process_data["tipo_acesso_atual"] = "parcial"
    process_data["melhor_link_atual"] = link

    if process_data.get("status_categoria") != "categorizado":
        process_data["status_categoria"] = "pendente"

        # 🔔 NOTIFICA (log apenas)
        notify_process_update(
            "Processo com acesso parcial necessita de categorização",
            process_number
        )

        # 📝 ADICIONA À LISTA para envio de email ao final
        processos_para_email.append(process_number)

# Linha 294: Envia email ao FINAL da execução
enviar_categorizacoes_pendentes()
```

**Função `enviar_categorizacoes_pendentes()`:**
```python
def enviar_categorizacoes_pendentes():
    db = get_database()
    collection = db.processos

    # 🔍 BUSCA TODOS os processos com status_categoria == "pendente"
    processos_pendentes = []
    cursor = collection.find({"status_categoria": "pendente"})

    for processo in cursor:
        melhor_link = processo.get("melhor_link_atual")
        if melhor_link:
            processos_pendentes.append({
                "process_number": processo["numero_processo"],
                "link": melhor_link
            })

    # 📧 ENVIA EMAIL com todos os processos pendentes
    if processos_pendentes:
        notify_categorization_needed(processos_pendentes)
```

---

### Etapa 3: Coleta de Documentos ([get_process_docs_update.py](get_process_docs_update.py))

**Lógica de notificação:**

```python
# Linha 458-468: Agrupa novos documentos e envia email
if new_documents_found:
    process_data_grouped = {}

    for processo, info in novos_documentos.items():
        # Agrupar documentos por signatário
        documentos_por_signatario = {}
        for doc_numero, doc_info in info["documentos"].items():
            signatario = doc_info.get("signatario", "Signatário Desconhecido")
            doc_tipo = doc_info.get("tipo_documento", "Documento")

            if signatario not in documentos_por_signatario:
                documentos_por_signatario[signatario] = set()

            documentos_por_signatario[signatario].add(f"{doc_tipo} {doc_numero}")

        process_data_grouped[processo] = {
            "apelido": processo_info.get("apelido", ""),
            "documentos_por_signatario": {
                sig: sorted(list(docs))
                for sig, docs in documentos_por_signatario.items()
            }
        }

    # 📧 ENVIA EMAIL com novos documentos
    notify_new_documents(process_data_grouped)

else:
    # 📧 ENVIA EMAIL informando que não há novos documentos
    subject = "Verificação de Documentos Concluída"
    content = f"<p>Nenhum documento novo encontrado.</p><p>Data: {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}</p>"
    send_email(subject, create_email_template(content))
```

---

## O Que NÃO Existe no Legacy

### ❌ Detecção Automática de Mudanças

O legacy **NÃO** compara estados anterior/atual de processos.

Não existe:
- ❌ Snapshot de processos
- ❌ Comparação de valores de campos
- ❌ Detecção de mudança de `categoria`
- ❌ Detecção de mudança de `status_categoria`
- ❌ Detecção de mudança de `tipo_acesso_atual` (além do caso pontual parcial → integral)

### ❌ Notificações de Mudanças de Status/Categoria

**Cenários que NÃO geram notificação:**

1. **Usuário muda categoria via UI** ([ui_process_manager.py:526](ui_process_manager.py#L526))
   - ✅ Loga no console: `"Categoria alterada de X para Y"`
   - ❌ NÃO envia email

2. **Usuário muda categoria via UI Add Process** ([ui_add_process.py:469](ui_add_process.py#L469))
   - ✅ Loga no queue: `"Categoria alterada de X para Y"`
   - ❌ NÃO envia email

3. **Scraper atualiza status_categoria**
   - Se muda de "não definido" → "pendente": ✅ Log
   - Se muda de "pendente" → "categorizado": ❌ Nada
   - Se muda de "categorizado" → "pendente": ❌ Nada

4. **Scraper atualiza categoria**
   - Se muda de "não definido" → "restrito": ❌ Nada
   - Se muda qualquer outra mudança: ❌ Nada

---

## Resumo de Notificações por Tipo

| Tipo de Notificação | Quando Ocorre | Arquivo | Função |
|---------------------|---------------|---------|--------|
| **Processos Pendentes** | Final da Etapa 2 | get_process_links_status.py:294 | `notify_categorization_needed()` |
| **Acesso Integral** | Durante Etapa 2 | get_process_links_status.py:115 | `notify_process_update()` (log) |
| **Precisa Categorização** | Durante Etapa 2 | get_process_links_status.py:126 | `notify_process_update()` (log) |
| **Novos Documentos** | Final da Etapa 3 | get_process_docs_update.py:468 | `notify_new_documents()` |
| **Verificação Concluída** | Final da Etapa 3 (sem docs) | get_process_docs_update.py:472 | `send_email()` |
| **Mudança de Status** | ❌ NUNCA | - | - |
| **Mudança de Categoria** | ❌ NUNCA | - | - |

---

## Conclusões para Sprint 2.3

### Comportamento Atual (Legacy)

O sistema legado tem notificações **reativas** e **pontuais**:

1. ✅ Notifica processos pendentes ao final da Etapa 2
2. ✅ Notifica novos documentos ao final da Etapa 3
3. ✅ Loga (não envia email) quando acesso muda de parcial → integral
4. ❌ **NÃO** detecta mudanças de status_categoria
5. ❌ **NÃO** detecta mudanças de categoria

### Sprint 2.3 - Manter Compatibilidade

Para Sprint 2.3, devemos:

1. **MANTER** o comportamento atual:
   - `notify_categorization_needed()` ao final da Etapa 2
   - `notify_new_documents()` ao final da Etapa 3
   - `notify_process_update()` como log (não email)

2. **NÃO ADICIONAR** (por enquanto):
   - ❌ Detecção automática de mudanças de status/categoria
   - ❌ Snapshots de processos
   - ❌ Comparação de estados

3. **MIGRAR** para PostgreSQL:
   - Funções de notificação já migradas em `utils/email_service.py`
   - Manter mesma lógica e fluxo

---

**Última Atualização:** 2025-12-15 (Sprint 2.3)
