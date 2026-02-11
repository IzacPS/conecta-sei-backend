"""
Institution Repository

Provides database operations for Institution model with ParadeDB search.
"""

from typing import List, Optional, Sequence, Tuple
from fastapi_pagination import Params
from sqlalchemy.orm import Session
from sqlalchemy import Row, RowMapping, func, text

from app.database.models.institution import Institution
from app.database.repositories.repository import BaseRepository, ParadeDBSearchMixin


class InstitutionRepository(BaseRepository[Institution], ParadeDBSearchMixin):
    """
    Repository for Institution model.

    Provides:
    - CRUD operations (from BaseRepository)
    - Full-text search (from ParadeDBSearchMixin)
    - Domain-specific queries

    Example:
        session = Session()
        repo = InstitutionRepository(session)

        # Create institution
        institution = repo.create(
            id="trf1",
            name="TRF 1ª Região",
            sei_url="https://sei.trf1.jus.br/sei/",
            scraper_version="4.2.0",
            sei_family="v4",
            created_by="admin@example.com"
        )

        # Search by name
        results = repo.search_by_name("TRF")

        # Get active institutions
        active = repo.get_active_institutions()
    """

    def __init__(self, session: Session):
        super().__init__(session, Institution)

    def get_by_scraper_version(self, version: str) -> List[Institution]:
        """
        Get all institutions using a specific scraper version.

        Args:
            version: Scraper version (e.g., "4.2.0")

        Returns:
            List of institutions
        """
        return (
            self.session.query(Institution)
            .filter(Institution.scraper_version == version)
            .all()
        )

    def get_by_sei_family(self, family: str) -> List[Institution]:
        """
        Get all institutions in a SEI family.

        Args:
            family: SEI family (e.g., "v4", "v3")

        Returns:
            List of institutions
        """
        return (
            self.session.query(Institution)
            .filter(Institution.sei_family == family)
            .all()
        )

    def get_institution_by_status(self, offset: int, limit: int, active_only: bool) -> Tuple[List[Institution], int]:
        """
        Get all active institutions.

        Returns:
            List of active institutions
        """

        if active_only:
            query = (
                self.session.query(Institution)
                .filter(Institution.active == True)
                .order_by(Institution.name)
            )
        else:
            query = (
                self.session.query(Institution)
                .order_by(Institution.name)
            )   

        count = query.count()

        items = query.offset(offset).limit(limit).all()

        return items, count

    def search_by_name(self, query: str, limit: int = 100) -> Sequence[RowMapping]:
        """
        Search institutions by name using ParadeDB full-text search.

        Args:
            query: Search query
            limit: Maximum results

        Returns:
            List of matching institutions sorted by relevance

        Example:
            results = repo.search_by_name("TRF Regional")
        """
        return self.search_with_score(
            field="name",
            query=query,
            key_field="id",
            operator="|||",
            limit=limit
        )

    def search_by_notes(self, query: str, limit: int = 100) -> Sequence[RowMapping]:
        """
        Search institutions by notes field.

        Args:
            query: Search query
            limit: Maximum results

        Returns:
            List of matching institutions
        """
        return self.search(
            field="notes",
            query=query,
            operator="|||",
            limit=limit
        )

    def activate(self, institution_id: str) -> Optional[Institution]:
        """
        Activate an institution.

        Args:
            institution_id: Institution ID

        Returns:
            Updated institution or None
        """
        return self.update(institution_id, active=True)

    def deactivate(self, institution_id: str) -> Optional[Institution]:
        """
        Deactivate an institution.

        Args:
            institution_id: Institution ID

        Returns:
            Updated institution or None
        """
        return self.update(institution_id, active=False)

    def update_scraper_version(
        self, institution_id: str, new_version: str, sei_family: str
    ) -> Optional[Institution]:
        """
        Update institution's scraper version (when SEI system updates).

        Args:
            institution_id: Institution ID
            new_version: New scraper version
            sei_family: New SEI family if changed

        Returns:
            Updated institution or None
        """
        return self.update(
            institution_id,
            scraper_version=new_version,
            sei_family=sei_family
        )
    

    def count_all(self) -> int:
        return self.count()

    def count_active(self) -> int:
        return (
            self.session.query(Institution)
            .filter(Institution.active == True)
            .count()
        )

    def count_by_family(self) -> Sequence[Row[tuple[str, int]]]:
        return (
            self.session.query(
                Institution.sei_family,
                func.count(Institution.id)
            )
            .group_by(Institution.sei_family)
            .all()
        )

    def count_by_version(self) -> Sequence[Row[tuple[str, int]]]:
        return (
            self.session.query(
                Institution.scraper_version,
                func.count(Institution.id)
            )
            .group_by(Institution.scraper_version)
            .all()
        )
