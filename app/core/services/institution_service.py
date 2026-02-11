from typing import Optional
from fastapi import Depends
from fastapi_pagination import Page, Params
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.database.repositories.institution_repository import InstitutionRepository
from app.database.models.institution import Institution


class InstitutionService:
    def __init__(self, session: Session):
        self.repo = InstitutionRepository(session)

    @staticmethod
    def instance(session = Depends(get_db)):
        return InstitutionService(session)

    def list_institutions(
        self,
        params: Params,
        active_only: bool = False,
    ) -> Page[Institution]:
        items, total = self.repo.get_institution_by_status(
            limit=params.size, 
            offset=((params.page - 1) * params.size), 
            active_only=active_only)
        return Page.create(items=items, total=total, params=params)

    def get_institution(self, institution_id: str) -> Optional[Institution]:
        return self.repo.get_by_id(institution_id)

    def create_institution(self, **data) -> Institution:
        return self.repo.create(**data)

    def update_institution(
        self,
        institution_id: str,
        **data,
    ) -> Optional[Institution]:
        return self.repo.update(institution_id, **data)

    def delete_institution(self, institution_id: str) -> bool:
        return self.repo.delete(institution_id)

    def activate_institution(self, institution_id: str) -> Optional[Institution]:
        return self.repo.activate(institution_id)

    def deactivate_institution(self, institution_id: str) -> Optional[Institution]:
        return self.repo.deactivate(institution_id)

    def update_scraper_version(
        self,
        institution_id: str,
        new_version: str,
        sei_family: str,
    ) -> Optional[Institution]:
        return self.repo.update_scraper_version(
            institution_id=institution_id,
            new_version=new_version,
            sei_family=sei_family,
        )

    def search_by_name(
        self,
        query: str,
        limit: int = 100,
    ):
        return self.repo.search_by_name(query=query, limit=limit)

    def search_by_notes(
        self,
        query: str,
        limit: int = 100,
    ):
        return self.repo.search_by_notes(query=query, limit=limit)

    # def get_statistics(self) -> Dict[str, object]:
    #     total = self.repo.count()

    #     active = len(self.repo.get_active_institutions())
    #     inactive = total - active

    #     family_counts: Dict[str, Any] = {}
    #     version_counts: Dict[str, Any] = {}
    #     institutions: list[Institution] = self.repo.get_all()

    #     for institution in self.repo.get_all():
    #         version = institution.scraper_version
    #         version_counts[version] = version_counts.get(version, 0) + 1
    #         family = institution.sei_family
    #         family_counts[family] = family_counts.get(family, 0) + 1

    #     return {
    #         "total": total,
    #         "active": active,
    #         "inactive": inactive,
    #         "by_family": family_counts,
    #         "by_version": version_counts,
    #     }
