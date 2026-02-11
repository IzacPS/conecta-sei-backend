"""
Repository Pattern Base Classes

Provides database abstraction layer for ConectaSEI v2.0.

The Repository Pattern provides several benefits:
1. Decouples business logic from database implementation
2. Makes testing easier (can mock repositories)
3. Allows switching databases in the future
4. Centralizes database queries and logic

Architecture:
- BaseRepository: Generic CRUD operations for any model
- Specialized repositories: Domain-specific queries (InstitutionRepository, ProcessRepository)
"""

from abc import ABC
from typing import Any, Dict, Generic, List, Optional, Protocol, Sequence, Type, TypeVar
from sqlalchemy.orm import Session
from sqlalchemy import RowMapping, text
from app.database.models.model_base import SqlAlchemyModel



ModelType = TypeVar("ModelType", bound=SqlAlchemyModel)

class RepositoryContext(Protocol[ModelType]):
    session: Session
    model: Type[ModelType]

class BaseRepository(Generic[ModelType], ABC):
    """
    Abstract base repository with common CRUD operations.

    Type Parameters:
        ModelType: The SQLAlchemy model class (Institution, Process, etc.)

    Example:
        class InstitutionRepository(BaseRepository[Institution]):
            def __init__(self, session: Session):
                super().__init__(session, Institution)
    """

    def __init__(self, session: Session, model: type[ModelType]):
        """
        Initialize repository.

        Args:
            session: SQLAlchemy session
            model: The SQLAlchemy model class
        """
        self.session = session
        self.model = model

    def get_by_id(self, id: Any) -> Optional[ModelType]:
        """
        Retrieve a single record by ID.

        Args:
            id: Primary key value

        Returns:
            Model instance or None if not found
        """
        return self.session.query(self.model).filter(self.model.id == id).first()

    def get_all(self, skip: int = 0, limit: int = 100) -> List[ModelType]:
        """
        Retrieve all records with pagination.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of model instances
        """
        return self.session.query(self.model).offset(skip).limit(limit).all()

    def create(self, **kwargs) -> ModelType:
        """
        Create a new record.

        Args:
            **kwargs: Column values for the new record

        Returns:
            Created model instance
        """
        instance = self.model(**kwargs)
        self.session.add(instance)
        self.session.commit()
        self.session.refresh(instance)
        return instance

    def update(self, id: Any, **kwargs) -> Optional[ModelType]:
        """
        Update an existing record.

        Args:
            id: Primary key value
            **kwargs: Column values to update

        Returns:
            Updated model instance or None if not found
        """
        instance = self.get_by_id(id)
        if instance is None:
            return None

        for key, value in kwargs.items():
            if hasattr(instance, key):
                setattr(instance, key, value)

        self.session.commit()
        self.session.refresh(instance)
        return instance

    def delete(self, id: Any) -> bool:
        """
        Delete a record by ID.

        Args:
            id: Primary key value

        Returns:
            True if deleted, False if not found
        """
        instance = self.get_by_id(id)
        if instance is None:
            return False

        self.session.delete(instance)
        self.session.commit()
        return True

    def count(self) -> int:
        """
        Count total records.

        Returns:
            Total number of records
        """
        return self.session.query(self.model).count()

    def exists(self, id: Any) -> bool:
        """
        Check if a record exists.

        Args:
            id: Primary key value

        Returns:
            True if exists, False otherwise
        """
        return self.session.query(self.model.id).filter(self.model.id == id).first() is not None


class ParadeDBSearchMixin:
    """
    Mixin for ParadeDB full-text search operations.

    Provides methods for BM25 search queries using ParadeDB operators.
    Must be used with BaseRepository.

    Example:
        class ProcessRepository(BaseRepository[Process], ParadeDBSearchMixin):
            pass
    """

    def search(
        self: RepositoryContext[ModelType],
        field: str,
        query: str,
        operator: str = "|||",
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[RowMapping]:
        """
        Perform full-text search using ParadeDB operators.

        Args:
            field: Column name to search
            query: Search query string
            operator: ParadeDB operator (|||, &&&, ###, @@@)
            limit: Maximum results to return
            offset: Number of results to skip

        Returns:
            List of matching records

        Example:
            # Match disjunction (OR)
            results = repo.search("numero_processo", "12345 6789", operator="|||")

            # Match conjunction (AND)
            results = repo.search("autoridade", "João Silva", operator="&&&")

            # Phrase search
            results = repo.search("autoridade", "João Silva", operator="###")
        """
        sql = text(f"""
            SELECT * FROM {self.model.__tablename__}
            WHERE {field} {operator} :query
            LIMIT :limit OFFSET :offset
        """)

        result = self.session.execute(
            sql,
            {"query": query, "limit": limit, "offset": offset}
        )
        return result.mappings().all()

    def search_with_score(
        self: RepositoryContext[ModelType],
        field: str,
        query: str,
        key_field: str = "id",
        operator: str = "|||",
        limit: int = 100,
    ) -> Sequence[RowMapping]:
        """
        Perform search with BM25 relevance scoring.

        Args:
            field: Column name to search
            query: Search query string
            key_field: Key field name (for scoring)
            operator: ParadeDB operator
            limit: Maximum results to return

        Returns:
            List of tuples (record, score) sorted by relevance

        Example:
            results = repo.search_with_score("numero_processo", "12345")
            for record, score in results:
                print(f"{record.numero_processo}: {score}")
        """
        sql = text(f"""
            SELECT *, pdb.score({key_field}) as score
            FROM {self.model.__tablename__}
            WHERE {field} {operator} :query
            ORDER BY score DESC
            LIMIT :limit
        """)

        result = self.session.execute(
            sql,
            {"query": query, "limit": limit}
        )
        return result.mappings().all()

    def search_json_field(
        self: RepositoryContext[ModelType],
        json_column: str,
        query: str,
        operator: str = "|||",
        limit: int = 100,
    ) -> Sequence[RowMapping]:
        """
        Search within JSONB column using ParadeDB.

        ParadeDB automatically indexes all sub-fields of JSONB columns.

        Args:
            json_column: JSONB column name (e.g., "metadata", "documentos")
            query: Search query
            operator: ParadeDB operator
            limit: Maximum results

        Returns:
            List of matching records

        Example:
            # Search within metadata JSONB
            results = repo.search_json_field("metadata", "São Paulo")

            # Search within documentos JSONB
            results = repo.search_json_field("documentos", "Despacho")
        """
        sql = text(f"""
            SELECT * FROM {self.model.__tablename__}
            WHERE {json_column} {operator} :query
            LIMIT :limit
        """)

        result = self.session.execute(
            sql,
            {"query": query, "limit": limit}
        )
        return result.mappings().all()

    def advanced_search(
        self: RepositoryContext[ModelType],
        filters: Dict[str, Any],
        search_fields: Optional[Dict[str, str]] = None,
        order_by: str = "created_at",
        order_dir: str = "DESC",
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[RowMapping]:
        """
        Perform advanced search combining filters and full-text search.

        Args:
            filters: Dict of {column: value} for exact match filters
            search_fields: Dict of {column: query} for full-text search
            order_by: Column to order by
            order_dir: ASC or DESC
            limit: Maximum results
            offset: Results to skip

        Returns:
            List of matching records

        Example:
            results = repo.advanced_search(
                filters={"categoria": "restrito", "active": True},
                search_fields={"numero_processo": "12345"},
                order_by="created_at",
                order_dir="DESC",
                limit=20
            )
        """
        # Build WHERE clause
        where_clauses = []
        
        params: Dict[str, Any] = {
            "limit": limit,
            "offset": offset,
        }

        # Add exact match filters
        for column, value in filters.items():
            where_clauses.append(f"{column} = :{column}")
            params[column] = value

        # Add full-text search fields
        if search_fields:
            for column, query in search_fields.items():
                param_name = f"search_{column}"
                where_clauses.append(f"{column} ||| :{param_name}")
                params[param_name] = query

        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

        sql = text(f"""
            SELECT * FROM {self.model.__tablename__}
            WHERE {where_sql}
            ORDER BY {order_by} {order_dir}
            LIMIT :limit OFFSET :offset
        """)

        result = self.session.execute(sql, params)
        return result.mappings().all()
