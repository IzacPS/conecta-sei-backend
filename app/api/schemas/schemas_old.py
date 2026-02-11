"""
ConectaSEI v2.0 - Pydantic Schemas

Schemas para validação de dados da API.
Usa Pydantic para validação automática, serialização e documentação.

IMPORTANTE: Schemas refletem EXATAMENTE os campos do legacy code.
Baseado em:
- database/models_sqlalchemy.py (Process, Institution)
- database/models.py (ProcessData dataclass)
- get_process_docs_update.py (estrutura de documentos)

Categorias:
- Institution schemas (criação, atualização, resposta)
- Process schemas (filtros, resposta, estatísticas)
- Document schemas (estrutura do legacy)
- Pagination schemas (lista paginada)
- Common schemas (mensagens, erros)

Uso:
    from api.schemas import InstitutionCreate, ProcessResponse
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime


# ==================== Common Schemas ====================

class MessageResponse(BaseModel):
    """Resposta padrão para operações bem-sucedidas."""
    message: str = Field(..., description="Mensagem de sucesso")
    details: Optional[Dict[str, Any]] = Field(None, description="Detalhes adicionais")
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class ErrorResponse(BaseModel):
    """Resposta padrão para erros."""
    error: str = Field(..., description="Tipo de erro")
    message: str = Field(..., description="Mensagem de erro")
    details: Optional[Dict[str, Any]] = Field(None, description="Detalhes do erro")
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class PaginationMeta(BaseModel):
    """Metadados de paginação."""
    total: int = Field(..., description="Total de itens", ge=0)
    page: int = Field(..., description="Página atual", ge=1)
    per_page: int = Field(..., description="Itens por página", ge=1, le=100)
    total_pages: int = Field(..., description="Total de páginas", ge=0)
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


# ==================== Institution Schemas ====================

class InstitutionBase(BaseModel):
    """Campos base de instituição."""
    name: str = Field(..., min_length=1, max_length=255, description="Nome da instituição")
    url: str = Field(..., description="URL do sistema SEI")
    scraper_version: str = Field(..., description="Versão do scraper (v1, v2, etc.)")
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class InstitutionCreate(InstitutionBase):
    """Schema para criação de instituição."""
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Metadados adicionais (JSON)"
    )
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class InstitutionUpdate(BaseModel):
    """Schema para atualização de instituição."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    url: Optional[str] = None
    scraper_version: Optional[str] = None
    is_active: Optional[bool] = None
    metadata: Optional[Dict[str, Any]] = None
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class InstitutionResponse(InstitutionBase):
    """Schema de resposta de instituição."""
    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="ID único da instituição")
    is_active: bool = Field(..., description="Se a instituição está ativa")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Metadados")
    created_at: datetime = Field(..., description="Data de criação")
    updated_at: Optional[datetime] = Field(None, description="Data de atualização")


class InstitutionListResponse(BaseModel):
    """Schema de resposta para lista de instituições."""
    items: List[InstitutionResponse] = Field(..., description="Lista de instituições")
    meta: PaginationMeta = Field(..., description="Metadados de paginação")
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class InstitutionStatsResponse(BaseModel):
    """Estatísticas de uma instituição."""
    institution_id: str
    total_processes: int = Field(..., ge=0)
    by_access_type: Dict[str, int] = Field(default_factory=dict)
    by_category: Dict[str, int] = Field(default_factory=dict)
    pending_categorization: int = Field(..., ge=0)
    invalid_links: int = Field(..., ge=0)
    total_documents: int = Field(..., ge=0)
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


# ==================== Process Schemas ====================

class ProcessBase(BaseModel):
    """Campos base de processo."""
    numero_processo: str = Field(
        ...,
        description="Número do processo (formato: 12345.001234/2024-56)",
        alias="process_number"  # API usa process_number, mas DB é numero_processo
    )
    institution_id: str = Field(..., description="ID da instituição")
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class ProcessCreate(ProcessBase):
    """Schema para criação de processo."""
    links: Optional[Dict[str, Any]] = Field(default_factory=dict)
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class ProcessUpdate(BaseModel):
    """
    Schema para atualização de processo.

    Campos refletem exatamente o legacy:
    - tipo_acesso_atual: "integral" | "parcial" | "error"
    - categoria: "restrito" | outro (string livre no legacy)
    - status_categoria: "pendente" | "categorizado"
    - autoridade: campo com "A" maiúsculo (legacy: "Autoridade")
    """
    tipo_acesso_atual: Optional[str] = Field(None, description="Tipo de acesso: integral/parcial/error")
    categoria: Optional[str] = Field(None, description="Categoria do processo")
    status_categoria: Optional[str] = Field(None, description="Status: pendente/categorizado")
    melhor_link_atual: Optional[str] = Field(None, description="ID do melhor link")
    unidade: Optional[str] = Field(None, description="Unidade administrativa")
    autoridade: Optional[str] = Field(None, description="Autoridade do processo", alias="Autoridade")
    sem_link_validos: Optional[bool] = Field(None, description="Se processo não tem links válidos")
    apelido: Optional[str] = Field(None, description="Apelido/nickname do processo")
    links: Optional[Dict[str, Any]] = Field(None, description="Dicionário de links")
    documentos: Optional[Dict[str, Any]] = Field(None, description="Dicionário de documentos")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Metadados adicionais")
    ultima_atualizacao: Optional[str] = Field(None, description="Data da última atualização (ISO string)")
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class ProcessResponse(ProcessBase):
    """
    Schema de resposta de processo.

    IMPORTANTE: Campos refletem EXATAMENTE o modelo do legacy.
    Ver database/models_sqlalchemy.py:Process
    """
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str = Field(..., description="ID único do processo (UUID)")
    links: Dict[str, Any] = Field(default_factory=dict, description="Links de acesso ao processo")
    documentos: Dict[str, Any] = Field(default_factory=dict, description="Documentos do processo")

    # Current state fields
    tipo_acesso_atual: Optional[str] = Field(None, description="Tipo de acesso: integral/parcial")
    melhor_link_atual: Optional[str] = Field(None, description="ID do melhor link válido")

    # Categorization
    categoria: Optional[str] = Field(None, description="Categoria do processo (ex: restrito)")
    status_categoria: Optional[str] = Field(None, description="Status: pendente/categorizado")

    # Additional fields
    unidade: Optional[str] = Field(None, description="Unidade administrativa")
    autoridade: Optional[str] = Field(None, description="Autoridade do processo", alias="Autoridade")
    sem_link_validos: bool = Field(False, description="Se não possui links válidos")
    apelido: Optional[str] = Field(None, description="Apelido/nickname do processo")

    # Timestamps
    ultima_atualizacao: Optional[str] = Field(None, description="Última atualização (ISO string do legacy)")
    created_at: datetime = Field(..., description="Data de criação")
    updated_at: Optional[datetime] = Field(None, description="Data de atualização")

    # JSONB metadata
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Metadados adicionais")


class ProcessListResponse(BaseModel):
    """Schema de resposta para lista de processos."""
    items: List[ProcessResponse] = Field(..., description="Lista de processos")
    meta: PaginationMeta = Field(..., description="Metadados de paginação")
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class ProcessFilterParams(BaseModel):
    """Parâmetros de filtro para processos."""
    institution_id: Optional[str] = Field(None, description="Filtrar por instituição")
    tipo_acesso: Optional[str] = Field(None, description="Filtrar por tipo de acesso")
    categoria: Optional[str] = Field(None, description="Filtrar por categoria")
    status_categoria: Optional[str] = Field(None, description="Filtrar por status")
    sem_link_validos: Optional[bool] = Field(None, description="Filtrar processos sem links válidos")
    search: Optional[str] = Field(None, description="Busca full-text (número, unidade, autoridade)")
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


# ==================== Document Schemas ====================

class DocumentInfo(BaseModel):
    """
    Informações de um documento (estrutura do legacy).

    Baseado em get_process_docs_update.py:166-172
    """
    tipo: str = Field(..., description="Tipo do documento (ex: Despacho, Petição)")
    data: str = Field(..., description="Data do documento (formato: dd/mm/yyyy)")
    status: str = Field(
        default="nao_baixado",
        description="Status: nao_baixado/baixado/erro"
    )
    ultima_verificacao: Optional[str] = Field(
        None,
        description="Data da última verificação (formato: dd/mm/yyyy HH:MM:SS)"
    )
    signatario: Optional[str] = Field(
        default="Autoridade Competente",
        description="Signatário do documento"
    )
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class DocumentDownloadRequest(BaseModel):
    """Request para download de documentos."""
    process_id: str = Field(..., description="ID do processo")
    document_numbers: Optional[List[str]] = Field(
        None,
        description="Números específicos de documentos (None = todos)"
    )
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class DocumentDownloadResponse(BaseModel):
    """Resposta de download de documentos."""
    task_id: str = Field(..., description="ID da task em background")
    status: str = Field(..., description="Status inicial (pending)")
    message: str = Field(..., description="Mensagem")
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


# ==================== Search Schemas ====================

class SearchQuery(BaseModel):
    """Query de busca full-text."""
    query: str = Field(..., min_length=1, description="Texto de busca")
    institution_id: Optional[str] = Field(None, description="Filtrar por instituição")
    limit: int = Field(10, ge=1, le=100, description="Limite de resultados")
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class SearchResult(BaseModel):
    """Resultado de busca."""
    process_id: str
    numero_processo: str = Field(..., alias="process_number")
    institution_id: str
    score: float = Field(..., description="Score BM25 de relevância")
    highlight: Optional[str] = Field(None, description="Trecho destacado")
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class SearchResponse(BaseModel):
    """Resposta de busca."""
    results: List[SearchResult] = Field(..., description="Resultados ordenados por relevância")
    total: int = Field(..., ge=0, description="Total de resultados encontrados")
    query: str = Field(..., description="Query executada")
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


# ==================== Scraper Schemas ====================

class ScraperInfo(BaseModel):
    """Informações de um scraper."""
    version: str = Field(..., description="Versão do scraper")
    name: str = Field(..., description="Nome do scraper")
    description: Optional[str] = Field(None, description="Descrição")
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class ScraperListResponse(BaseModel):
    """Lista de scrapers disponíveis."""
    scrapers: List[ScraperInfo] = Field(..., description="Scrapers disponíveis")
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
