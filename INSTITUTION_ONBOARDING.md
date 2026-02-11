# Institution Onboarding Process

## Overview

Este documento descreve o processo de onboarding quando um usuário solicita suporte a uma nova instituição SEI.

---

## Fluxo Completo

```
┌─────────────────────────────────────────────────────────────┐
│ 1. SOLICITAÇÃO DO USUÁRIO                                   │
└─────────────────────────────────────────────────────────────┘
                          ↓
    Usuário: "Preciso acessar o SEI do TRF3"
    Fornece: URL + credenciais de teste (opcional)
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. ANÁLISE MANUAL DA VERSÃO (Dev Team)                      │
└─────────────────────────────────────────────────────────────┘
                          ↓
    Dev team acessa a URL fornecida
    Analisa código fonte, testa seletores, identifica versão manualmente
                          ↓
            ┌─────────────┴─────────────┐
            │                           │
    ┌───────▼────────┐         ┌───────▼────────┐
    │ VERSÃO         │         │ VERSÃO         │
    │ CONHECIDA      │         │ DESCONHECIDA   │
    │ (ex: 4.2.0)    │         │ (ex: 5.1.0)    │
    └───────┬────────┘         └───────┬────────┘
            │                           │
┌───────────▼────────────┐   ┌─────────▼──────────────────┐
│ 3A. SCRAPER EXISTE     │   │ 3B. IMPLEMENTAÇÃO          │
│                        │   │     NECESSÁRIA             │
└───────────┬────────────┘   └─────────┬──────────────────┘
            │                           │
            │                ┌──────────▼──────────┐
            │                │ Dev Team cria novo  │
            │                │ scraper (Sprint)    │
            │                └──────────┬──────────┘
            │                           │
            └──────────┬────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────────┐
│ 4. CADASTRO DA INSTITUIÇÃO                                  │
└─────────────────────────────────────────────────────────────┘
                          ↓
    POST /api/institutions
    {
        "name": "TRF 3ª Região",
        "sei_url": "https://sei.trf3.jus.br",
        "credentials": {...}
    }
    Sistema automaticamente:
    - Detecta versão
    - Valida credenciais
    - Testa scraper
    - Salva configuração
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 5. DISPONIBILIZAÇÃO PARA O USUÁRIO                          │
└─────────────────────────────────────────────────────────────┘
                          ↓
    Usuário pode agora:
    - Extrair processos: POST /institutions/trf3/processes/extract
    - Listar processos: GET /institutions/trf3/processes
    - Download docs: POST /institutions/trf3/processes/{num}/documents/download
```

---

## Detalhamento por Etapa

### 1. Solicitação do Usuário

**Canais**:
- Email/ticket de suporte
- Formulário na aplicação
- API endpoint dedicado (futuro)

**Informações necessárias**:
```json
{
  "institution_name": "TRF 3ª Região",
  "sei_url": "https://sei.trf3.jus.br",
  "test_credentials": {
    "email": "teste@example.com",
    "password": "senha_teste"
  },
  "contact": {
    "name": "João Silva",
    "email": "joao@trf3.jus.br"
  },
  "priority": "normal" | "urgent"
}
```

---

### 2. Análise da Versão (MANUAL por enquanto)

**Processo atual**: Dev team executa análise manualmente

**Script de detecção** (executado manualmente pelo dev team):

```python
# scripts/detect_institution_version.py

async def analyze_institution(sei_url: str, credentials: dict = None):
    """
    Analisa uma instituição e determina se temos scraper compatível.

    Returns:
        {
            "sei_url": str,
            "detected_version": str | None,
            "scraper_available": bool,
            "scraper_version": str | None,
            "compatibility": "full" | "partial" | "none",
            "recommendation": str
        }
    """
    browser = await init_browser()
    page = await browser.new_page()

    try:
        # 1. Acessa URL
        await page.goto(sei_url)

        # 2. Tenta auto-detecção
        # Dev team manually tests scrapers
        scraper = test_scraper_compatibility(page, "4.2.0")

        if scraper:
            # Versão conhecida - scraper exists
            return {
                "sei_url": sei_url,
                "detected_version": scraper.VERSION,
                "scraper_available": True,
                "scraper_version": scraper.VERSION,
                "compatibility": "full",
                "recommendation": "Can be registered immediately"
            }
        else:
            # Versão desconhecida - tentar identificar manualmente
            version_info = await manual_version_detection(page)

            return {
                "sei_url": sei_url,
                "detected_version": version_info.get("version"),
                "scraper_available": False,
                "scraper_version": None,
                "compatibility": "none",
                "recommendation": f"New scraper needed for version {version_info.get('version')}"
            }
    finally:
        await browser.close()
```

**Endpoint de análise** (futuro - Phase 3+):
```python
# FUTURO: Automação via API
POST /api/admin/institutions/analyze
{
  "sei_url": "https://sei.trf3.jus.br",
  "credentials": {...}  # opcional
}

Response:
{
  "detected_version": "4.2.0",
  "scraper_available": true,
  "can_onboard_immediately": true
}
```

**Processo atual (manual)**:
1. Dev recebe solicitação via email/ticket
2. Dev executa script manualmente
3. Dev analisa resultado e responde usuário

---

### 3A. Scraper Existe (Versão Conhecida)

**Ação**: Cadastro imediato

O usuário ou admin pode cadastrar a instituição via API:

```bash
curl -X POST http://localhost:8000/api/institutions \
  -H "Content-Type: application/json" \
  -d '{
    "name": "TRF 3ª Região",
    "sei_url": "https://sei.trf3.jus.br",
    "credentials": {
      "email": "user@trf3.jus.br",
      "password": "senha"
    }
  }'
```

Sistema automaticamente:
1. Detecta versão (4.2.0)
2. Valida que scraper existe
3. Testa login com credenciais
4. Salva configuração
5. Retorna instituição pronta para uso

**Timeline**: Imediato (< 1 minuto)

---

### 3B. Implementação Necessária (Versão Desconhecida)

**Quando acontece**:
- Nova versão do SEI lançada (ex: 5.0.0)
- Customização específica da instituição
- Família completamente nova

**Process**:

1. **Triagem técnica**:
```python
# Identificar diferenças
python scripts/compare_sei_versions.py \
  --known-version 4.2.0 \
  --new-url https://sei.trf3.jus.br

# Output:
# - CSS selector differences
# - New form fields
# - Changed URL patterns
# - JavaScript changes
```

2. **Estimativa de esforço**:
```
Minor version (4.2 → 4.3):
  - Poucas mudanças
  - Override seletores específicos
  - Estimativa: 1-2 dias

Major version (4.x → 5.x):
  - Mudanças significativas
  - Nova classe base (SEIv5Base)
  - Estimativa: 1 semana

Custom implementation:
  - Análise caso a caso
  - Estimativa: 2-5 dias
```

3. **Implementação**:
```python
# scrapers/sei_v4/v4_3_0/scraper.py

from scrapers.sei_v4.base import SEIv4Base
from scrapers import register_scraper

@register_scraper()
class SEIv4_3_0(SEIv4Base):
    VERSION = "4.3.0"
    VERSION_RANGE = ">=4.3.0 <4.4.0"

    # Override apenas o que mudou
    def get_login_selectors(self) -> Dict[str, str]:
        selectors = super().get_login_selectors()
        selectors["submit"] = "#btnEntrar"  # Mudou
        return selectors

    # Resto herda de SEIv4Base
```

4. **Testes**:
```bash
pytest tests/test_sei_v4_3_0.py -v
python scripts/validate_scraper.py --version 4.3.0 --url https://sei.trf3.jus.br
```

5. **Deploy**:
```bash
git commit -m "Add SEI v4.3.0 scraper support"
docker build -t automasei:latest .
docker-compose up -d
```

**Timeline**: 1-7 dias (dependendo da complexidade)

---

### 4. Cadastro da Instituição

**Interface Admin** (futuro):
```
┌─────────────────────────────────────────────┐
│ Nova Instituição                            │
├─────────────────────────────────────────────┤
│ Nome: [TRF 3ª Região                     ]  │
│ URL:  [https://sei.trf3.jus.br           ]  │
│                                             │
│ Credenciais de Teste:                       │
│ Email:    [teste@trf3.jus.br             ]  │
│ Senha:    [••••••••••                    ]  │
│                                             │
│ [Testar Conexão]                            │
│                                             │
│ ✓ Versão detectada: 4.2.0                   │
│ ✓ Scraper disponível: SEIv4_2_0             │
│ ✓ Login bem-sucedido                        │
│                                             │
│           [Cancelar]  [Cadastrar]           │
└─────────────────────────────────────────────┘
```

**Dados salvos**:
```json
{
  "id": "trf3",
  "name": "TRF 3ª Região",
  "sei_url": "https://sei.trf3.jus.br",
  "sei_version": "4.2.0",
  "sei_family": "v4",
  "scraper_version": "4.2.0",
  "active": true,
  "created_at": "2024-12-15T10:30:00Z",
  "last_version_check": "2024-12-15T10:30:00Z",
  "metadata": {
    "region": "São Paulo",
    "type": "tribunal_federal"
  }
}
```

---

### 5. Disponibilização para Usuário

**Usuário final pode**:

1. **Ver instituições disponíveis**:
```bash
GET /api/institutions

Response:
[
  {
    "id": "trf3",
    "name": "TRF 3ª Região",
    "sei_version": "4.2.0",
    "active": true
  },
  ...
]
```

2. **Extrair processos**:
```bash
POST /api/institutions/trf3/processes/extract
{
  "credentials": {
    "email": "user@trf3.jus.br",
    "password": "senha"
  }
}
```

3. **Agendar extrações automáticas**:
```bash
POST /api/institutions/trf3/schedule
{
  "extraction": {
    "enabled": true,
    "interval_minutes": 30
  },
  "credentials": {...}
}
```

---

## Workflow para Dev Team

### Quando receber solicitação de nova instituição:

1. **Executar análise**:
```bash
python scripts/detect_institution_version.py \
  --url https://sei.nova-instituicao.jus.br \
  --credentials credentials.json
```

2. **Verificar output**:
```
✓ Detected version: 4.2.0
✓ Scraper available: SEIv4_2_0
✓ Compatibility: full
→ Action: Can register immediately
```

3. **Se scraper existe**:
   - Responder ao usuário: "Pronto para uso"
   - Fornecer instruções de cadastro
   - Timeline: Imediato

4. **Se scraper NÃO existe**:
   - Responder ao usuário: "Requer implementação"
   - Estimar esforço (1-7 dias)
   - Criar issue/sprint para implementação
   - Notificar quando pronto

---

## Métricas de Sucesso

**KPIs para acompanhar**:
- Tempo médio de onboarding (instituição conhecida): < 5 minutos
- Tempo médio de implementação (nova versão): < 3 dias
- Taxa de sucesso de auto-detecção: > 90%
- Número de instituições ativas
- Cobertura de versões SEI

---

## Casos Especiais

### Instituição com customizações

Algumas instituições podem ter SEI customizado. Nesses casos:

1. Criar scraper específico herdando da versão base
2. Override apenas comportamentos customizados

```python
# scrapers/custom/trf3_custom.py

@register_scraper(version="4.2.0-trf3")
class SEI_TRF3_Custom(SEIv4_2_0):
    """Scraper customizado para TRF3 com modificações específicas."""

    VERSION = "4.2.0-trf3"

    def get_login_selectors(self) -> Dict[str, str]:
        # TRF3 tem botão de login diferente
        selectors = super().get_login_selectors()
        selectors["submit"] = "#btnLoginTRF3"
        return selectors
```

### Migração de versão (instituição atualiza SEI)

Quando instituição atualiza o SEI:

```bash
POST /api/institutions/trf3/detect-version

Response:
{
  "previous_version": "4.2.0",
  "detected_version": "4.3.0",
  "scraper_available": true,
  "auto_updated": true,
  "message": "Institution updated to SEI 4.3.0, scraper changed automatically"
}
```

Sistema automaticamente:
- Detecta nova versão
- Troca scraper
- Notifica usuário
- Mantém histórico de versões

---

## Automação Futura

### Self-service onboarding (Fase 3+)

```
┌─────────────────────────────────────────────┐
│ Usuário preenche formulário                 │
│ ↓                                           │
│ Sistema tenta auto-onboarding               │
│ ↓                                           │
│ ┌─────────────┬─────────────┐               │
│ │ SUCESSO     │ FALHA       │               │
│ │ ↓           │ ↓           │               │
│ │ Instituição │ Ticket para │               │
│ │ disponível  │ dev team    │               │
│ │ imediato    │             │               │
│ └─────────────┴─────────────┘               │
└─────────────────────────────────────────────┘
```

### Monitoramento proativo

Sistema periodicamente verifica versões de todas instituições cadastradas:
- Detecta quando instituição atualiza SEI
- Alerta se nova versão não tem scraper
- Auto-atualiza quando possível

---

**Status**: Documentado para implementação futura
**Prioridade**: Alta (Sprint 3.1+)
**Dependências**: Multi-tenant API, Institution Management system
