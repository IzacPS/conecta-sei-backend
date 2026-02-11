# SEI Scraper Inheritance Guide

## Referência para novas versões

**A implementação do SEI v4.2.0** (`app/scrapers/sei_v4/v4_2_0/`) é a referência para implementar scrapers das demais versões do SEI. O fluxo e a interface são os mesmos em todas as famílias (v2, v3, v4, v5); o que muda entre versões são basicamente:

- **Seletores** (IDs, classes, XPath) — extrair do HTML/PHP do frontend daquela versão
- **Detecção de versão** (`detect_version`) — meta tags, `data-sei-version`, rodapé, etc.
- **Pequenos ajustes** de fluxo (ex.: nome do botão de login, estrutura da tabela de documentos)

Ao adicionar uma nova versão (ex.: v4.3.0, v5.0.0), use o `SEIv4_2_0` e o `selectors.py` do v4.2.0 como modelo: mesma lista de métodos, mesmo padrão de extração; adapte apenas os seletores e a detecção para o HTML da versão alvo. Os testes de scraping podem usar fixtures HTML copiadas/adaptadas das páginas reais (lista de processos, lista de documentos, login).

---

## Hierarquia de Herança

O sistema de scrapers usa herança em 3 níveis para maximizar reuso de código:

```
┌─────────────────────────────────────────────────────────────────┐
│ Nível 1: BASE UNIVERSAL                                         │
│                                                                  │
│ SEIScraperBase (abstract)                                       │
│ - Interface que TODOS os scrapers devem implementar             │
│ - Define métodos obrigatórios (login, extract, etc)             │
│ - NÃO tem implementação concreta                                │
└─────────────────────────────────────────────────────────────────┘
                              ↓
    ┌─────────────┬───────────┴───────────┬─────────────┐
    │             │                       │             │
┌───▼────┐   ┌───▼────┐   ┌──────▼──────┐   ┌────▼────┐
│SEIv2   │   │SEIv3   │   │  SEIv4      │   │ SEIv5   │
│Base    │   │Base    │   │  Base       │   │ Base    │
└───┬────┘   └───┬────┘   └──────┬──────┘   └────┬────┘
    │            │                │               │
┌───────────────────────────────────────────────────────────────┐
│ Nível 2: FAMÍLIA                                              │
│                                                               │
│ SEIv4Base (exemplo)                                          │
│ - Tudo que é COMUM a TODAS versões da família v4            │
│ - Login padrão v4                                            │
│ - Seletores comuns v4                                        │
│ - Lógica de navegação v4                                     │
│ - Detecção de versão v4                                      │
└───────────────────────────────────────────────────────────────┘
                              ↓
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
   ┌────▼────┐           ┌────▼────┐           ┌───▼─────┐
   │SEIv4_0_0│           │SEIv4_2_0│           │SEIv4_5_0│
   └─────────┘           └─────────┘           └─────────┘
┌───────────────────────────────────────────────────────────────┐
│ Nível 3: VERSÃO ESPECÍFICA                                    │
│                                                               │
│ SEIv4_2_0 (exemplo)                                          │
│ - Override APENAS o que mudou na versão 4.2.0                │
│ - Seletores CSS específicos                                  │
│ - Lógica única desta versão                                  │
│ - Herda 90%+ do código de SEIv4Base                         │
└───────────────────────────────────────────────────────────────┘
```

---

## Exemplo Prático

### Cenário: SEI v4.2.0 e v4.3.0

**SEI v4.2.0**:
- Botão login: `#sbmLogin`
- Tabela processos: `#tblProcessos`
- Campo autoridade: `#txtAutoridade`

**SEI v4.3.0** (atualização):
- Botão login: `#btnEntrar` ← **MUDOU**
- Tabela processos: `#tblProcessos` ← igual
- Campo autoridade: `#txtAutoridade` ← igual

### Sem Herança (❌ Ruim)
```python
class SEIv4_2_0:
    def login(self):
        # 100 linhas de código
        click("#sbmLogin")

    def extract_processes():
        # 200 linhas de código

class SEIv4_3_0:
    def login(self):
        # 100 linhas DUPLICADAS
        click("#btnEntrar")  # só isso mudou

    def extract_processes():
        # 200 linhas DUPLICADAS (código idêntico!)
```

### Com Herança (✅ Bom)
```python
class SEIv4Base:
    """Tudo que é comum a v4"""

    def get_login_selectors(self):
        return {
            "email": "#txtUsuario",
            "password": "#pwdSenha",
            "submit": "#sbmLogin"  # padrão v4
        }

    def login(self, page, email, password):
        selectors = self.get_login_selectors()
        page.fill(selectors["email"], email)
        page.fill(selectors["password"], password)
        page.click(selectors["submit"])  # usa seletor configurável
        # ... 100 linhas de lógica comum

    def extract_processes(self, page):
        # ... 200 linhas de código comum

class SEIv4_2_0(SEIv4Base):
    VERSION = "4.2.0"
    # NÃO precisa override - usa padrão do Base

class SEIv4_3_0(SEIv4Base):
    VERSION = "4.3.0"

    # Override APENAS o que mudou
    def get_login_selectors(self):
        selectors = super().get_login_selectors()
        selectors["submit"] = "#btnEntrar"  # só isso mudou
        return selectors

    # Herda login() e extract_processes() sem modificar
```

**Resultado**:
- SEIv4_2_0: 0 linhas de código (herda tudo)
- SEIv4_3_0: 5 linhas de código (só override)
- Reuso: 99% do código

---

## Quando Criar Cada Nível

### Criar Nova Família (SEIvXBase)

**Quando**: Nova versão MAJOR do SEI (v3 → v4 → v5)

**Características**:
- UI completamente redesenhada
- Mudanças estruturais significativas
- Novos padrões de navegação
- Nova arquitetura HTML/CSS

**Exemplo**: SEI v4 introduziu Bootstrap, nova estrutura de menus, etc.

```python
class SEIv4Base(SEIScraperBase):
    FAMILY = "v4"

    def get_login_selectors(self):
        # Padrão para TODA família v4
        return {...}

    def login(self, page, email, password):
        # Lógica comum a TODA família v4
        pass
```

---

### Criar Nova Versão (SEIvX_Y_Z)

**Quando**: Nova versão MINOR/PATCH dentro da família

**Características**:
- Pequenas mudanças de CSS/HTML
- Novos campos em formulários
- Ajustes em seletores
- Bug fixes que afetam scraping

**Exemplo**: v4.2.0 → v4.3.0 mudou alguns seletores

```python
class SEIv4_3_0(SEIv4Base):
    VERSION = "4.3.0"

    # Override APENAS o que mudou
    def get_login_selectors(self):
        selectors = super().get_login_selectors()
        selectors["submit"] = "#btnEntrar"  # mudou
        return selectors

    # Resto herda de SEIv4Base
```

---

## Fluxo de Implementação

### Novo Scraper para Versão Conhecida (dentro da família)

```
1. Identificar família (v4)
   ↓
2. Criar classe herdando de SEIv4Base
   ↓
3. Testar código sem override
   ↓
4. Identificar o que não funciona
   ↓
5. Override APENAS métodos quebrados
   ↓
6. Registrar com @register_scraper()
```

### Novo Scraper para Nova Família

```
1. Criar scrapers/sei_vX/base.py
   ↓
2. Herdar de SEIScraperBase
   ↓
3. Implementar comportamento comum da família
   ↓
4. Criar primeira versão específica (vX.Y.Z)
   ↓
5. Testar e validar
   ↓
6. Registrar ambos
```

---

## Exemplo Completo: Adicionando SEI v4.3.0

### Passo 1: Analisar diferenças

```bash
# Compare com versão conhecida
python scripts/compare_versions.py \
  --base-url https://sei-v4.2.example.com \
  --new-url https://sei-v4.3.example.com

# Output:
# Differences found:
# - Login button: #sbmLogin → #btnEntrar
# - Document table: added column 'assinantes'
```

### Passo 2: Criar scraper

```python
# scrapers/sei_v4/v4_3_0/scraper.py

from scrapers.sei_v4.base import SEIv4Base
from scrapers import register_scraper

@register_scraper()
class SEIv4_3_0(SEIv4Base):
    VERSION = "4.3.0"
    VERSION_RANGE = ">=4.3.0 <4.4.0"

    def get_login_selectors(self) -> Dict[str, str]:
        """Override: botão mudou."""
        selectors = super().get_login_selectors()
        selectors["submit"] = "#btnEntrar"
        return selectors

    def get_document_list_selectors(self) -> Dict[str, str]:
        """Override: nova coluna adicionada."""
        selectors = super().get_document_list_selectors()
        selectors["assinantes"] = "td.doc-assinantes"
        return selectors

    # Tudo mais herda de SEIv4Base:
    # - login()
    # - extract_process_list()
    # - validate_link()
    # - extract_authority()
    # - etc.
```

### Passo 3: Criar __init__.py

```python
# scrapers/sei_v4/v4_3_0/__init__.py

from .scraper import SEIv4_3_0

__all__ = ["SEIv4_3_0"]
```

### Passo 4: Testar

```python
# tests/test_sei_v4_3_0.py

def test_v4_3_0_login():
    scraper = ScraperFactory.create("4.3.0")
    assert scraper.VERSION == "4.3.0"

    # Testa login
    result = scraper.login(page, "test@example.com", "password")
    assert result == True

def test_v4_3_0_extract_processes():
    scraper = ScraperFactory.create("4.3.0")
    processes = scraper.extract_process_list(page)
    assert len(processes) > 0
```

### Passo 5: Validar herança

```python
# Verificar que herda corretamente
scraper = SEIv4_3_0()

# Deve ter métodos de SEIv4Base
assert hasattr(scraper, 'login')
assert hasattr(scraper, 'extract_process_list')

# Deve ter override
assert scraper.get_login_selectors()["submit"] == "#btnEntrar"

# Deve herdar o resto
assert scraper.get_login_selectors()["email"] == "#txtUsuario"  # de SEIv4Base
```

---

## Boas Práticas

### ✅ DO (Faça)

1. **Override apenas o necessário**
```python
class SEIv4_3_0(SEIv4Base):
    # Só override do que mudou
    def get_login_selectors(self):
        selectors = super().get_login_selectors()  # reutiliza base
        selectors["submit"] = "#btnEntrar"  # muda só isso
        return selectors
```

2. **Usar super() para chamar base**
```python
def extract_documents(self, page):
    # Faz processamento adicional
    documents = super().extract_documents(page)
    # Adiciona lógica específica da versão
    for doc in documents:
        doc["new_field"] = self.extract_new_field(page)
    return documents
```

3. **Documentar diferenças**
```python
class SEIv4_3_0(SEIv4Base):
    """
    SEI v4.3.0 Scraper

    Changes from v4.2.0:
    - Login button selector changed (#sbmLogin → #btnEntrar)
    - Added 'assinantes' column in document table
    - New accessibility features (not affecting scraping)
    """
```

### ❌ DON'T (Não faça)

1. **Duplicar código**
```python
# ❌ Ruim
class SEIv4_3_0(SEIv4Base):
    def login(self, page, email, password):
        # Copiar 100 linhas de SEIv4Base.login()
        # só pra mudar 1 linha
        page.fill("#txtUsuario", email)
        page.fill("#pwdSenha", password)
        page.click("#btnEntrar")  # só isso mudou
        # ... resto duplicado
```

2. **Herdar de versão específica**
```python
# ❌ Ruim
class SEIv4_3_0(SEIv4_2_0):  # herda de versão específica
    pass

# ✅ Bom
class SEIv4_3_0(SEIv4Base):  # herda de base da família
    pass
```

3. **Ignorrar super()**
```python
# ❌ Ruim
def get_login_selectors(self):
    return {
        "email": "#txtUsuario",  # duplicado de base
        "password": "#pwdSenha",  # duplicado de base
        "submit": "#btnEntrar"  # único diferente
    }

# ✅ Bom
def get_login_selectors(self):
    selectors = super().get_login_selectors()
    selectors["submit"] = "#btnEntrar"
    return selectors
```

---

## Estrutura de Pastas

```
scrapers/
├── base.py                    # SEIScraperBase
├── registry.py
├── factory.py
│
├── sei_v2/                    # Família v2 (legado)
│   ├── __init__.py
│   ├── base.py               # SEIv2Base
│   └── v2_6_0/
│       ├── __init__.py
│       └── scraper.py        # SEIv2_6_0
│
├── sei_v3/                    # Família v3
│   ├── __init__.py
│   ├── base.py               # SEIv3Base
│   ├── v3_0_0/
│   └── v3_1_5/
│
├── sei_v4/                    # Família v4 (atual)
│   ├── __init__.py
│   ├── base.py               # SEIv4Base
│   ├── v4_0_0/
│   ├── v4_2_0/               # Versão atual do sistema
│   └── v4_3_0/
│
└── sei_v5/                    # Família v5 (futuro)
    ├── __init__.py
    ├── base.py               # SEIv5Base
    └── v5_0_0/
```

---

## Resumo

**Herança em 3 níveis = Reuso máximo de código**

1. **SEIScraperBase**: Interface universal (todos implementam)
2. **SEIvXBase**: Comportamento comum da família (v2, v3, v4, v5)
3. **SEIvX_Y_Z**: Override apenas diferenças da versão específica

**Benefício**: Implementar nova versão pode levar 5-50 linhas ao invés de 1000+ linhas.
