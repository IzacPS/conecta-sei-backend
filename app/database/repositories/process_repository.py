"""
Process Repository

Provides database operations for Process model with ParadeDB search capabilities.
"""

from typing import Dict, List, Optional, Any, Sequence
from sqlalchemy.orm import Session
from sqlalchemy import RowMapping, text, and_, or_

from app.database.models.process import Process
from app.database.repositories.repository import BaseRepository, ParadeDBSearchMixin


class ProcessRepository(BaseRepository[Process], ParadeDBSearchMixin):
    """
    Repository for Process model.

    Provides:
    - CRUD operations
    - Full-text search on numero_processo and autoridade
    - JSONB search on links and documentos
    - Complex filtering (categoria, status, tipo_acesso)
    - Bulk operations

    Example:
        session = Session()
        repo = ProcessRepository(session)

        # Create process
        process = repo.create(
            numero_processo="12345.001234/2024-56",
            institution_id="trf1",
            links={"ABC123": {"tipo_acesso": "integral", "valido": True}},
            categoria="restrito"
        )

        # Search by process number
        results = repo.search_by_numero("12345")

        # Get processes by category
        restricted = repo.get_by_categoria("restrito")
    """

    def __init__(self, session: Session):
        super().__init__(session, Process)

    def get_by_numero_processo(self, numero_processo: str) -> Optional[Process]:
        """
        Get process by exact numero_processo.

        Args:
            numero_processo: Exact process number

        Returns:
            Process or None
        """
        return (
            self.session.query(Process)
            .filter(Process.numero_processo == numero_processo)
            .first()
        )

    def search_by_numero(
        self, query: str, limit: int = 100
    ) -> Sequence[RowMapping]:
        """
        Search processes by numero_processo with full-text search.

        Args:
            query: Search query (e.g., "12345")
            limit: Maximum results

        Returns:
            List of matching processes sorted by relevance

        Example:
            # Search for processes containing "12345"
            results = repo.search_by_numero("12345")
        """
        return self.search_with_score(
            field="numero_processo",
            query=query,
            key_field="id",
            operator="|||",
            limit=limit
        )

    def search_by_autoridade(
        self, query: str, limit: int = 100
    ) -> Sequence[RowMapping]:
        """
        Search processes by autoridade (authority name).

        Args:
            query: Search query (e.g., "João Silva")
            limit: Maximum results

        Returns:
            List of matching processes

        Example:
            results = repo.search_by_autoridade("João Silva")
        """
        return self.search_with_score(
            field="autoridade",
            query=query,
            key_field="id",
            operator="|||",
            limit=limit
        )

    def get_by_institution(
        self, institution_id: str, skip: int = 0, limit: int = 100
    ) -> List[Process]:
        """
        Get all processes for a specific institution.

        Args:
            institution_id: Institution ID
            skip: Records to skip
            limit: Maximum results

        Returns:
            List of processes
        """
        return (
            self.session.query(Process)
            .filter(Process.institution_id == institution_id)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_categoria(
        self, categoria: str, skip: int = 0, limit: int = 100
    ) -> List[Process]:
        """
        Get processes by category.

        Args:
            categoria: Category (e.g., "restrito", "público")
            skip: Records to skip
            limit: Maximum results

        Returns:
            List of processes
        """
        return (
            self.session.query(Process)
            .filter(Process.categoria == categoria)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_status_categoria(
        self, status: str, skip: int = 0, limit: int = 100
    ) -> List[Process]:
        """
        Get processes by categorization status.

        Args:
            status: Status (e.g., "pendente", "categorizado")
            skip: Records to skip
            limit: Maximum results

        Returns:
            List of processes
        """
        return (
            self.session.query(Process)
            .filter(Process.status_categoria == status)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_tipo_acesso(
        self, tipo: str, skip: int = 0, limit: int = 100
    ) -> List[Process]:
        """
        Get processes by access type.

        Args:
            tipo: Access type ("integral", "parcial", "error")
            skip: Records to skip
            limit: Maximum results

        Returns:
            List of processes
        """
        return (
            self.session.query(Process)
            .filter(Process.tipo_acesso_atual == tipo)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_pending_categorization(
        self, institution_id: Optional[str] = None, limit: int = 100
    ) -> List[Process]:
        """
        Get processes pending categorization.

        Args:
            institution_id: Optional filter by institution
            limit: Maximum results

        Returns:
            List of processes pending categorization
        """
        query = self.session.query(Process).filter(
            Process.status_categoria == "pendente"
        )

        if institution_id:
            query = query.filter(Process.institution_id == institution_id)

        return query.limit(limit).all()

    def get_with_invalid_links(
        self, institution_id: Optional[str] = None, limit: int = 100
    ) -> List[Process]:
        """
        Get processes with invalid links.

        Args:
            institution_id: Optional filter by institution
            limit: Maximum results

        Returns:
            List of processes with invalid links
        """
        query = self.session.query(Process).filter(
            Process.sem_link_validos == True
        )

        if institution_id:
            query = query.filter(Process.institution_id == institution_id)

        return query.limit(limit).all()

    def search_documents(
        self, query: str, limit: int = 100
    ) -> Sequence[RowMapping]:
        """
        Search within documentos JSONB field.

        ParadeDB auto-indexes all JSONB sub-fields, so this searches
        document tipo, numero, assinantes, etc.

        Args:
            query: Search query (e.g., "Despacho", "João Silva")
            limit: Maximum results

        Returns:
            List of processes with matching documents

        Example:
            # Find processes with documents signed by João Silva
            results = repo.search_documents("João Silva")

            # Find processes with Despacho documents
            results = repo.search_documents("Despacho")
        """
        return self.search_json_field(
            json_column="documentos",
            query=query,
            operator="|||",
            limit=limit
        )

    def update_links(
        self, process_id: str, links: Dict[str, Dict[str, Any]]
    ) -> Optional[Process]:
        """
        Update process links JSONB field.

        Args:
            process_id: Process ID
            links: New links dict

        Returns:
            Updated process or None
        """
        return self.update(process_id, links=links)

    def update_documentos(
        self, process_id: str, documentos: Dict[str, Dict[str, Any]]
    ) -> Optional[Process]:
        """
        Update process documentos JSONB field.

        Args:
            process_id: Process ID
            documentos: New documentos dict

        Returns:
            Updated process or None
        """
        return self.update(process_id, documentos=documentos)

    def update_current_state(
        self,
        process_id: str,
        tipo_acesso: Optional[str] = None,
        melhor_link: Optional[str] = None,
    ) -> Optional[Process]:
        """
        Update process current state (tipo_acesso_atual, melhor_link_atual).

        Args:
            process_id: Process ID
            tipo_acesso: New access type
            melhor_link: New best link

        Returns:
            Updated process or None
        """
        updates = {}
        if tipo_acesso is not None:
            updates["tipo_acesso_atual"] = tipo_acesso
        if melhor_link is not None:
            updates["melhor_link_atual"] = melhor_link

        return self.update(process_id, **updates) if updates else None

    def categorize_process(
        self, process_id: str, categoria: str, status: str = "categorizado"
    ) -> Optional[Process]:
        """
        Categorize a process.

        Args:
            process_id: Process ID
            categoria: Category (e.g., "restrito", "público")
            status: Status (default: "categorizado")

        Returns:
            Updated process or None
        """
        return self.update(
            process_id,
            categoria=categoria,
            status_categoria=status
        )

    def get_statistics_by_institution(self, institution_id: str) -> dict:
        """
        Get process statistics for an institution.

        Args:
            institution_id: Institution ID

        Returns:
            Dict with statistics
        """
        total = (
            self.session.query(Process)
            .filter(Process.institution_id == institution_id)
            .count()
        )

        by_categoria = {}
        categorias = (
            self.session.query(Process.categoria)
            .filter(Process.institution_id == institution_id)
            .distinct()
            .all()
        )
        for (cat,) in categorias:
            if cat:
                count = (
                    self.session.query(Process)
                    .filter(
                        and_(
                            Process.institution_id == institution_id,
                            Process.categoria == cat
                        )
                    )
                    .count()
                )
                by_categoria[cat] = count

        by_tipo_acesso = {}
        tipos = (
            self.session.query(Process.tipo_acesso_atual)
            .filter(Process.institution_id == institution_id)
            .distinct()
            .all()
        )
        for (tipo,) in tipos:
            if tipo:
                count = (
                    self.session.query(Process)
                    .filter(
                        and_(
                            Process.institution_id == institution_id,
                            Process.tipo_acesso_atual == tipo
                        )
                    )
                    .count()
                )
                by_tipo_acesso[tipo] = count

        pending = (
            self.session.query(Process)
            .filter(
                and_(
                    Process.institution_id == institution_id,
                    Process.status_categoria == "pendente"
                )
            )
            .count()
        )

        invalid_links = (
            self.session.query(Process)
            .filter(
                and_(
                    Process.institution_id == institution_id,
                    Process.sem_link_validos == True
                )
            )
            .count()
        )

        return {
            "total": total,
            "by_categoria": by_categoria,
            "by_tipo_acesso": by_tipo_acesso,
            "pending_categorization": pending,
            "with_invalid_links": invalid_links,
        }

    def bulk_update_categoria(
        self, process_ids: List[str], categoria: str, status: str = "categorizado"
    ) -> int:
        """
        Bulk update categoria for multiple processes.

        Args:
            process_ids: List of process IDs
            categoria: Category
            status: Status

        Returns:
            Number of processes updated
        """
        result = (
            self.session.query(Process)
            .filter(Process.id.in_(process_ids))
            .update(
                {
                    Process.categoria: categoria,
                    Process.status_categoria: status
                },
                synchronize_session=False
            )
        )
        self.session.commit()
        return result
