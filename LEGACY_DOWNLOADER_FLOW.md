# Legacy Downloader Flow

**Documentação do comportamento do downloader legacy** - AutomaSEI v1.0.10
**Data:** 2025-12-16 (Sprint 3.2)
**Fonte:** [get_docs_download.py](get_docs_download.py)

---

## Resumo Executivo

O downloader legacy tem **3 responsabilidades principais**:

1. ✅ **Download de documentos** do SEI (via Playwright)
2. ✅ **Conversão HTML → PDF** (quando necessário)
3. ✅ **Upload para SharePoint** (destino final)
4. ✅ **Registro de histórico** (MongoDB documentos_historico)
5. ✅ **Limpeza de arquivos temporários**

**Estrutura:**
```
download_document()
    ↓
1. Download do SEI → temp_downloads/
2. Conversão HTML→PDF (se necessário)
3. Upload para SharePoint
4. Registro no histórico
5. Limpeza de arquivos temp
```

---

## 1. Fluxo Principal - `download_new_documents()`

**Arquivo:** [get_docs_download.py:177-257](get_docs_download.py#L177-L257)

### Algoritmo:

```python
def download_new_documents():
    # 1. Carregar processos
    processes = load_process_data()

    # 2. Iniciar browser e login
    browser, page, playwright = init_browser()
    login(page)

    # 3. Para cada processo:
    for process_number, process_data in processes.items():

        # 3.1. Verificações:
        if not process_data.get("novos_documentos"):
            continue  # Sem novos documentos

        if process_data.get("sem_link_validos"):
            del process_data["novos_documentos"]
            continue  # Sem links válidos

        if not should_process_documents(process_data):
            continue  # Acesso restrito

        # 3.2. Navegar para processo
        best_link = process_data["melhor_link_atual"]
        page.goto(f"{base_url}{best_link}")
        page.wait_for_selector("#tblDocumentos")

        # 3.3. Download de cada documento novo
        successful_downloads = []
        for doc_number in process_data["novos_documentos"]:
            doc_info = process_data["documentos"][doc_number]

            # Download + Upload SharePoint
            if download_document(page, doc_number, doc_info, process_number, process_data):
                process_data["documentos"][doc_number]["status"] = "baixado"
                successful_downloads.append(doc_number)

        # 3.4. Atualizar lista de novos documentos
        process_data["novos_documentos"] = [
            doc for doc in new_docs if doc not in successful_downloads
        ]

        if not process_data["novos_documentos"]:
            del process_data["novos_documentos"]

    # 4. Salvar dados
    save_process_data(processes)

    # 5. Cleanup
    browser.close()
    playwright.stop()
```

---

## 2. Download Individual - `download_document()`

**Arquivo:** [get_docs_download.py:77-175](get_docs_download.py#L77-L175)

### Parâmetros:

```python
def download_document(
    page: Page,           # Playwright page
    doc_number: str,      # Ex: "12345678"
    doc_info: dict,       # {"tipo": "Despacho", "data": "15/01/2024", ...}
    process_number: str,  # Ex: "12345.001234/2024-56"
    process_data: Dict    # Dados completos do processo
) -> bool                # True = sucesso (upload SharePoint OK)
```

### Fluxo Detalhado:

#### Fase 1: Preparação

```python
# Criar diretório temporário
temp_dir = get_app_data_dir() / "temp_downloads"
temp_dir.mkdir(parents=True, exist_ok=True)

# Criar registro de histórico
registro_historico = {
    "processo_numero": process_number,
    "documento_numero": doc_number,
    "tipo_documento": doc_info.get("tipo", "Desconhecido"),
    "data_documento": doc_info.get("data", ""),
    "signatario": doc_info.get("signatario", "Não identificado"),
    "timestamp_inicio": datetime.datetime.now(),
    "tipo_operacao": "completo",
    "resultado": "pendente",
    "apelido_processo": process_data.get("apelido", "")
}
```

#### Fase 2: Download do SEI

```python
# Localizar link do documento
doc_link = page.locator(f'a:text("{doc_number}")')
doc_link.wait_for(state="visible", timeout=30000)

# Iniciar download (ALT+Click)
registro_historico["timestamp_download_inicio"] = datetime.datetime.now()

with page.expect_download(timeout=30000) as download_info:
    page.keyboard.down("Alt")
    doc_link.click()
    page.keyboard.up("Alt")

download = download_info.value
suggested_filename = download.suggested_filename

# Processar nome do arquivo
final_filename = process_filename(suggested_filename, doc_number, doc_info)
# Ex: "12345678.pdf" → "Despacho_12345678.pdf"

temp_path = temp_dir / final_filename

# Salvar arquivo
download.save_as(temp_path)

registro_historico["tamanho_arquivo_bytes"] = temp_path.stat().st_size
registro_historico["timestamp_download_fim"] = datetime.datetime.now()
registro_historico["duracao_download_ms"] = ...
registro_historico["nome_arquivo"] = temp_path.name
```

#### Fase 3: Conversão HTML → PDF (se necessário)

```python
def handle_downloaded_file(temp_path: Path, doc_number: str, doc_info: dict, page: Page) -> Path:
    """
    Se arquivo for HTML, converte para PDF usando Playwright.
    """
    if temp_path.suffix.lower() == ".html":
        try:
            pdf_path = temp_path.with_suffix(".pdf")

            # Abrir HTML no browser
            page.goto(f"file:///{temp_path}")
            page.wait_for_load_state("load")

            # Converter para PDF
            page.pdf(path=str(pdf_path), format="A4")

            # Remover HTML original
            temp_path.unlink()

            return pdf_path
        except Exception as e:
            logger.log(f"Erro ao converter: {e}")
            return temp_path  # Retornar HTML mesmo

    return temp_path
```

#### Fase 4: Upload para SharePoint

```python
registro_historico["timestamp_upload_inicio"] = datetime.datetime.now()

upload_success = upload_to_sharepoint(
    final_path,      # Path do arquivo (PDF ou outro)
    process_number,  # Ex: "12345.001234/2024-56"
    process_data     # Dados completos (para apelido, etc.)
)

registro_historico["timestamp_upload_fim"] = datetime.datetime.now()
registro_historico["duracao_upload_ms"] = ...

if upload_success:
    registro_historico["resultado"] = "sucesso"
    return True
else:
    registro_historico["resultado"] = "falha"
    registro_historico["erro"] = "Falha no upload para SharePoint"
    return False
```

#### Fase 5: Cleanup e Histórico

```python
finally:
    # Calcular tempos finais
    registro_historico["timestamp_fim"] = datetime.datetime.now()
    registro_historico["duracao_total_ms"] = ...

    # Salvar histórico no MongoDB
    salvar_historico_documento(registro_historico)

    # Limpar arquivo temporário
    if temp_file and temp_file.exists():
        temp_file.unlink()
```

---

## 3. Estrutura do Histórico

**Collection MongoDB:** `documentos_historico`

**Fonte:** [get_docs_download.py:88-99](get_docs_download.py#L88-L99)

```python
{
    "processo_numero": "12345.001234/2024-56",
    "documento_numero": "12345678",
    "tipo_documento": "Despacho",
    "data_documento": "15/01/2024",
    "signatario": "João Silva",

    # Timestamps
    "timestamp_inicio": datetime,
    "timestamp_download_inicio": datetime,
    "timestamp_download_fim": datetime,
    "timestamp_upload_inicio": datetime,
    "timestamp_upload_fim": datetime,
    "timestamp_fim": datetime,

    # Durações (milissegundos)
    "duracao_download_ms": 1234.56,
    "duracao_upload_ms": 5678.90,
    "duracao_total_ms": 6913.46,

    # Arquivo
    "nome_arquivo": "Despacho_12345678.pdf",
    "tamanho_arquivo_bytes": 123456,

    # Operação
    "tipo_operacao": "completo",  # ou "parcial"
    "resultado": "sucesso",       # ou "falha" ou "pendente"
    "erro": null,                 # ou string de erro

    # Contexto
    "apelido_processo": "Processo Importante"
}
```

---

## 4. Funções Auxiliares

### 4.1. `process_filename()`

**Arquivo:** [get_docs_download.py:41-48](get_docs_download.py#L41-L48)

```python
def process_filename(suggested_filename: str, doc_number: str, doc_info: dict) -> str:
    """
    Renomeia arquivo para incluir tipo do documento.

    Ex:
    - Input: "12345678.pdf"
    - Output: "Despacho_12345678.pdf"
    """
    filename_without_ext = os.path.splitext(suggested_filename)[0]

    # Se nome é apenas o número (8 dígitos)
    if filename_without_ext.isdigit() and len(filename_without_ext) == 8:
        _, ext = os.path.splitext(suggested_filename)

        # Adicionar tipo do documento
        new_filename = f"{doc_info['tipo']}_{filename_without_ext}{ext}"

        # Sanitizar caracteres inválidos
        new_filename = re.sub(r'[<>:"/\\|?*]', "_", new_filename)

        return new_filename

    return suggested_filename
```

### 4.2. `get_temp_download_dir()`

**Arquivo:** [get_docs_download.py:71-74](get_docs_download.py#L71-L74)

```python
def get_temp_download_dir() -> Path:
    """
    Retorna diretório temporário para downloads.

    Path: %LOCALAPPDATA%\SEI_UNO_TRADE\temp_downloads\
    """
    temp_dir = get_app_data_dir() / "temp_downloads"
    temp_dir.mkdir(parents=True, exist_ok=True)
    return temp_dir
```

### 4.3. `handle_dialog()`

**Arquivo:** [get_docs_download.py:37-38](get_docs_download.py#L37-L38)

```python
def handle_dialog(dialog):
    """Dismisses any JavaScript dialogs during download."""
    dialog.dismiss()
```

---

## 5. Verificações e Validações

### 5.1. Antes de Iniciar Download de um Processo

```python
# 1. Tem novos documentos?
if not process_data.get("novos_documentos"):
    continue

# 2. Tem links válidos?
if process_data.get("sem_link_validos", False):
    del process_data["novos_documentos"]
    continue

# 3. Deve processar documentos? (integral ou restrito categorizado)
if not should_process_documents(process_data):
    continue

# 4. Tem melhor link?
best_link = process_data.get("melhor_link_atual")
if not best_link:
    continue
```

### 5.2. Durante Download

```python
# 1. Timeout de 30 segundos
page.set_default_timeout(30000)

# 2. Esperar elemento visível
doc_link.wait_for(state="visible", timeout=30000)

# 3. Esperar tabela de documentos
page.wait_for_selector("#tblDocumentos", timeout=30000)

# 4. Navegação de volta ao processo
current_url = page.url
if current_url != process_url:
    page.go_back()  # ou page.goto(process_url) se falhar
```

---

## 6. Integração com SharePoint

**Arquivo:** `sharepoint_api.py` (referenciado em get_docs_download.py:16)

```python
from sharepoint_api import upload_to_sharepoint

upload_success = upload_to_sharepoint(
    file_path: Path,           # Arquivo local (PDF ou outro)
    process_number: str,       # Número do processo
    process_data: Dict         # Dados completos (para apelido, metadados)
) -> bool                      # True = sucesso, False = falha
```

**Observação:** SharePoint API não foi migrado ainda (Sprint futuro).

---

## 7. Campos do Processo Atualizados

### 7.1. `novos_documentos`

**Tipo:** List[str]
**Descrição:** Lista de números de documentos a serem baixados

```python
# Antes do download
process_data["novos_documentos"] = ["12345678", "87654321"]

# Durante download
process_data["documento_atual"] = "12345678"

# Após download bem-sucedido
process_data["novos_documentos"] = ["87654321"]  # Remove o baixado

# Se todos baixados
del process_data["novos_documentos"]  # Remove campo
```

### 7.2. `documentos[doc_number]["status"]`

```python
# Antes do download
process_data["documentos"]["12345678"]["status"] = "nao_baixado"

# Após download bem-sucedido
process_data["documentos"]["12345678"]["status"] = "baixado"
```

---

## 8. Tratamento de Erros

### 8.1. Erro de Download

```python
try:
    with page.expect_download(timeout=30000) as download_info:
        # ...
except Exception as e:
    registro_historico["resultado"] = "falha"
    registro_historico["erro"] = str(e)
    logger.log(f"Erro ao baixar documento {doc_number}: {str(e)}")
    return False
```

### 8.2. Erro de Conversão HTML→PDF

```python
try:
    page.pdf(path=str(pdf_path), format="A4")
    temp_path.unlink()
    return pdf_path
except Exception as e:
    logger.log(f"Erro ao converter: {str(e)}")
    return temp_path  # Retorna HTML original
```

### 8.3. Erro de Upload SharePoint

```python
if upload_success:
    registro_historico["resultado"] = "sucesso"
    return True
else:
    registro_historico["resultado"] = "falha"
    registro_historico["erro"] = "Falha no upload para SharePoint"
    return False
```

---

## 9. Conclusões para Sprint 3.2

### Comportamento Legacy:

✅ **Download:** Playwright com ALT+Click
✅ **Conversão:** HTML→PDF via page.pdf()
✅ **Upload:** SharePoint (destino final)
✅ **Histórico:** MongoDB documentos_historico
✅ **Limpeza:** Arquivos temp removidos sempre
✅ **Validação:** should_process_documents() antes de baixar

### Sprint 3.2 - Implementar:

1. **core/document_downloader.py**
   - Classe DocumentDownloader (similar a ProcessExtractor)
   - Método download_documents(process_id, doc_numbers=None)
   - Método download_all_pending(institution_id=None)
   - Integração com Playwright (browser reuse)
   - Registro de histórico (PostgreSQL DocumentHistory)

2. **api/routers/documents.py**
   - POST /documents/download (background task)
   - GET /documents/download/{task_id}/status
   - GET /documents/history (histórico de downloads)
   - GET /documents/history/{document_number}

3. **Background Tasks:**
   - FastAPI BackgroundTasks
   - Task ID tracking
   - Status updates (pending → running → completed/failed)

4. **NÃO IMPLEMENTAR (Sprint futuro):**
   - ❌ SharePoint integration (deferred)
   - ❌ File storage (usar temp por enquanto)

---

**Última Atualização:** 2025-12-16 (Sprint 3.2)
