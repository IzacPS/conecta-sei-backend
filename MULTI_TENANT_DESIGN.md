# Multi-Tenant SEI System Design

## Overview

O sistema precisa suportar múltiplas instituições, cada uma com sua própria instância do SEI,
potencialmente em versões diferentes. O usuário deve poder solicitar scraping de qualquer
instituição configurada.

## Problema

1. **Múltiplas Instituições**: Usuário pode precisar extrair dados de várias instituições diferentes
   - Exemplo: TRF1, TRF2, Ministério da Justiça, etc.
   - Cada instituição tem sua própria URL do SEI
   - Cada instituição pode estar em versão diferente do SEI

2. **Detecção de Versão**: Sistema precisa identificar automaticamente qual scraper usar
   - Não podemos assumir que todas instituições usam mesma versão
   - Versão pode mudar quando instituição atualiza sistema

3. **Configuração por Instituição**: Cada instituição tem suas próprias credenciais e configurações
   - URLs diferentes
   - Credenciais diferentes
   - Possíveis customizações específicas

## Solução Proposta

### 1. Modelo de Dados - Instituição/Tenant

```python
# database/models.py

class Institution:
    """
    Representa uma instituição com instância própria do SEI.
    """
    id: str  # Identificador único (ex: "trf1", "mj")
    name: str  # Nome amigável (ex: "TRF 1ª Região")
    sei_url: str  # URL base do SEI (ex: "https://sei.trf1.jus.br")
    sei_version: Optional[str]  # Versão detectada (ex: "4.2.0")
    sei_family: Optional[str]  # Família (ex: "v4")
    scraper_version: Optional[str]  # Versão do scraper a usar
    credentials: Dict[str, str]  # Credenciais específicas
    active: bool  # Se está ativo
    last_version_check: datetime  # Última verificação de versão
    custom_settings: Dict[str, Any]  # Configurações específicas

    # Metadados
    created_at: datetime
    updated_at: datetime
```

### 2. Fluxo de Identificação

```
Usuário solicita scraping da instituição "TRF1"
    ↓
API busca configuração da instituição no banco
    ↓
Verifica se já tem scraper_version salvo
    ↓
    ├─ SIM: Usa scraper_version armazenado
    │         ↓
    │     Cria scraper com ScraperFactory.create(version)
    │
    └─ NÃO: Auto-detecção necessária
              ↓
          Navega até sei_url
              ↓
          ScraperFactory.auto_detect(page)
              ↓
          Salva versão detectada no banco
              ↓
          Usa scraper detectado
```

### 3. Endpoints da API

```python
# api/routers/institutions.py

POST   /api/institutions
    - Cadastrar nova instituição
    - Body: {name, sei_url, credentials}
    - Sistema faz auto-detecção inicial

GET    /api/institutions
    - Listar todas instituições cadastradas
    - Retorna: [{id, name, sei_url, sei_version, active}]

GET    /api/institutions/{institution_id}
    - Detalhes de uma instituição
    - Inclui versão do SEI detectada

PUT    /api/institutions/{institution_id}
    - Atualizar configurações
    - Pode forçar re-detecção de versão

DELETE /api/institutions/{institution_id}
    - Remover instituição

POST   /api/institutions/{institution_id}/detect-version
    - Forçar nova detecção de versão
    - Útil quando instituição atualiza SEI

POST   /api/institutions/{institution_id}/test-connection
    - Testar credenciais e conexão
    - Retorna versão detectada

# api/routers/processes.py

GET    /api/institutions/{institution_id}/processes
    - Listar processos de uma instituição

POST   /api/institutions/{institution_id}/processes/extract
    - Iniciar extração de processos
    - Sistema usa scraper correto automaticamente

GET    /api/institutions/{institution_id}/processes/{process_number}
    - Detalhes de um processo específico

POST   /api/institutions/{institution_id}/processes/{process_number}/documents/download
    - Download de documentos de um processo
```

### 4. Serviço de Detecção

```python
# core/institution_service.py

class InstitutionService:
    """
    Gerencia instituições e scrapers apropriados.
    """

    def get_scraper_for_institution(
        self,
        institution_id: str,
        force_detect: bool = False
    ) -> SEIScraperBase:
        """
        Retorna scraper apropriado para a instituição.

        Args:
            institution_id: ID da instituição
            force_detect: Forçar nova detecção mesmo se versão salva

        Returns:
            Instância do scraper correto
        """
        institution = self.repository.get(institution_id)

        if not force_detect and institution.scraper_version:
            # Usar versão salva
            scraper = ScraperFactory.create(institution.scraper_version)
            if scraper:
                return scraper

        # Auto-detectar
        page = self.browser.new_page()
        page.goto(institution.sei_url)

        scraper = ScraperFactory.auto_detect(page)

        if scraper:
            # Salvar versão detectada
            institution.scraper_version = scraper.VERSION
            institution.sei_version = scraper.VERSION
            institution.sei_family = scraper.FAMILY
            institution.last_version_check = datetime.now()
            self.repository.update(institution)

        page.close()
        return scraper

    def validate_institution(self, institution_id: str) -> Dict[str, Any]:
        """
        Valida configuração da instituição.

        Testa:
        - URL acessível
        - Credenciais válidas
        - Versão detectável
        - Scraper disponível
        """
        pass
```

### 5. Cache de Scrapers

```python
# core/scraper_cache.py

class ScraperCache:
    """
    Cache de scrapers por instituição para evitar re-detecção constante.
    """
    _cache: Dict[str, SEIScraperBase] = {}

    def get_or_create(
        self,
        institution_id: str,
        institution_service: InstitutionService
    ) -> SEIScraperBase:
        """
        Retorna scraper do cache ou cria novo.
        """
        if institution_id not in self._cache:
            self._cache[institution_id] = \
                institution_service.get_scraper_for_institution(institution_id)

        return self._cache[institution_id]

    def invalidate(self, institution_id: str):
        """
        Invalida cache para forçar nova detecção.
        """
        if institution_id in self._cache:
            del self._cache[institution_id]
```

### 6. Uso na Prática

```python
# Exemplo de uso no endpoint de extração

@router.post("/institutions/{institution_id}/processes/extract")
async def extract_processes(
    institution_id: str,
    background_tasks: BackgroundTasks
):
    # 1. Buscar instituição
    institution = institution_repo.get(institution_id)
    if not institution:
        raise HTTPException(404, "Institution not found")

    # 2. Obter scraper correto
    scraper = scraper_cache.get_or_create(
        institution_id,
        institution_service
    )

    # 3. Executar extração em background
    background_tasks.add_task(
        process_extractor.extract_all,
        institution=institution,
        scraper=scraper
    )

    return {
        "status": "started",
        "institution": institution.name,
        "sei_version": scraper.VERSION
    }
```

## Benefícios

1. **Transparente para o usuário**: Sistema identifica versão automaticamente
2. **Suporte multi-tenant**: Cada instituição independente
3. **Caching**: Evita re-detecção desnecessária
4. **Flexível**: Fácil adicionar novas instituições
5. **Manutenível**: Quando instituição atualiza SEI, basta forçar re-detecção

## Considerações de Implementação

### Fase de Implementação

- **Sprint 2.2-2.3**: Criar modelos de Institution
- **Sprint 3.1**: Implementar endpoints de instituições
- **Sprint 3.2**: Integrar com sistema de extração
- **Sprint 4.1**: Adicionar cache e otimizações

### Perguntas a Resolver

1. **Credenciais compartilhadas?**
   - Cada instituição tem credenciais próprias? ✓ (mais provável)
   - Ou um usuário pode ter múltiplas credenciais por instituição?

2. **Versionamento automático?**
   - Verificar versão a cada X horas/dias automaticamente?
   - Ou apenas quando usuário força?

3. **Fallback behavior?**
   - Se versão detectada não tem scraper, usar versão anterior da mesma família?
   - Ou retornar erro?

4. **Multi-usuário?**
   - Uma instituição compartilhada por vários usuários?
   - Ou cada usuário tem suas próprias instituições?

## Migration Path

### Código Atual → Multi-Tenant

1. Sistema atual assume 1 instituição (configuração global)
2. Migration:
   - Criar instituição "default" com configurações atuais
   - Migrar processos existentes para institution_id="default"
   - Adicionar campo `institution_id` em todos processos

### Backward Compatibility

Durante transição, manter suporte a código legado:
```python
# Se institution_id não informado, usar "default"
institution_id = institution_id or "default"
```

## Processo de Onboarding

Para detalhes sobre como adicionar novas instituições (processo completo desde solicitação do usuário até disponibilização), veja: **[INSTITUTION_ONBOARDING.md](INSTITUTION_ONBOARDING.md)**

Resumo do fluxo:
1. Usuário solicita instituição (fornece URL)
2. Sistema analisa versão automaticamente
3. Se scraper existe → cadastro imediato
4. Se scraper não existe → dev team implementa (1-7 dias)
5. Instituição disponível para uso

## Próximos Passos

- [x] Adicionar ao REFACTOR_PROGRESS.md
- [x] Documentar processo de onboarding
- [ ] Criar Sprint específico para multi-tenant
- [ ] Decidir perguntas em aberto com stakeholders
- [ ] Implementar modelo Institution
- [ ] Criar endpoints básicos
