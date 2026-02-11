"""
Search Router - ParadeDB BM25 full-text search with advanced features.
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import UserInfo, get_current_user
from app.database.models.institution import Institution
from app.database.models.process import Process
from app.database.session import get_db

logger = logging.getLogger(__name__)

router = APIRouter()


class SearchResultItem(BaseModel):
    id: int
    process_number: str
    institution_id: int
    institution_name: Optional[str] = None
    authority: Optional[str] = None
    category: Optional[str] = None
    access_type: Optional[str] = None
    nickname: Optional[str] = None
    unit: Optional[str] = None
    score: float = 0.0
    highlight: Optional[str] = None


class AdvancedSearchResponse(BaseModel):
    results: List[SearchResultItem]
    total: int
    query: str
    filters_applied: dict


class AutocompleteResponse(BaseModel):
    suggestions: List[dict]


@router.post("/search/advanced")
async def advanced_search(
    data: dict,
    user: UserInfo = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Advanced full-text search using ParadeDB BM25."""
    query_text = data.get("query", "").strip()
    institution_id = data.get("institution_id")
    access_type = data.get("access_type")
    category = data.get("category")
    category_status = data.get("category_status")
    limit = min(data.get("limit", 20), 100)
    offset = data.get("offset", 0)
    filters_applied = {}

    if not query_text:
        raise HTTPException(status_code=400, detail="query is required")

    try:
        sql = text("""
            SELECT
                p.id,
                p.process_number,
                p.institution_id,
                i.name as institution_name,
                p.authority,
                p.category,
                p.access_type,
                p.nickname,
                p.unit,
                paradedb.score(p.id) as score,
                paradedb.snippet(p.process_number) as highlight
            FROM processes p
            JOIN institutions i ON p.institution_id = i.id
            WHERE i.user_id = :user_id
              AND p.process_number ||| :query
              AND (:institution_id IS NULL OR p.institution_id = :institution_id)
              AND (:access_type IS NULL OR p.access_type = :access_type)
              AND (:category IS NULL OR p.category = :category)
              AND (:category_status IS NULL OR p.category_status = :category_status)
            ORDER BY score DESC
            LIMIT :limit OFFSET :offset
        """)
        result = await db.execute(sql, {
            "user_id": user.db_id,
            "query": query_text,
            "institution_id": institution_id,
            "access_type": access_type,
            "category": category,
            "category_status": category_status,
            "limit": limit,
            "offset": offset,
        })
        results = result.fetchall()
        items = [
            SearchResultItem(
                id=r.id,
                process_number=r.process_number,
                institution_id=r.institution_id,
                institution_name=r.institution_name,
                authority=r.authority,
                category=r.category,
                access_type=r.access_type,
                nickname=r.nickname,
                unit=r.unit,
                score=float(r.score) if r.score else 0.0,
                highlight=r.highlight,
            ).model_dump()
            for r in results
        ]
        if institution_id:
            filters_applied["institution_id"] = institution_id
        if access_type:
            filters_applied["access_type"] = access_type
        if category:
            filters_applied["category"] = category
        return AdvancedSearchResponse(
            results=items,
            total=len(items),
            query=query_text,
            filters_applied=filters_applied,
        ).model_dump()
    except Exception as e:
        logger.warning(f"ParadeDB search failed, falling back to LIKE: {e}")
        search_term = f"%{query_text}%"
        q = (
            select(Process)
            .join(Institution)
            .where(Institution.user_id == user.db_id)
            .where(
                or_(
                    Process.process_number.ilike(search_term),
                    Process.authority.ilike(search_term),
                    Process.nickname.ilike(search_term),
                    Process.unit.ilike(search_term),
                )
            )
        )
        if institution_id:
            q = q.where(Process.institution_id == institution_id)
        if access_type:
            q = q.where(Process.access_type == access_type)
        if category:
            q = q.where(Process.category == category)
        q = q.offset(offset).limit(limit)
        res = await db.execute(q)
        items_raw = res.scalars().unique().all()
        items = [
            SearchResultItem(
                id=p.id,
                process_number=p.process_number,
                institution_id=p.institution_id,
                authority=p.authority,
                category=p.category,
                access_type=p.access_type,
                nickname=p.nickname,
                unit=p.unit,
                score=0.0,
            ).model_dump()
            for p in items_raw
        ]
        return AdvancedSearchResponse(
            results=items,
            total=len(items),
            query=query_text,
            filters_applied=filters_applied,
        ).model_dump()


@router.get("/search/autocomplete")
async def autocomplete(
    q: str = Query(..., min_length=2, max_length=100),
    user: UserInfo = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Autocomplete suggestions for search."""
    search_term = f"%{q}%"
    stmt = (
        select(Process)
        .join(Institution)
        .where(
            Institution.user_id == user.db_id,
            or_(
                Process.process_number.ilike(search_term),
                Process.nickname.ilike(search_term),
                Process.authority.ilike(search_term),
            )
        )
        .limit(10)
    )
    result = await db.execute(stmt)
    processes = result.scalars().unique().all()
    suggestions = []
    for p in processes:
        if p.process_number and q.lower() in p.process_number.lower():
            suggestions.append({
                "type": "process_number",
                "value": p.process_number,
                "label": p.process_number,
                "process_id": p.id,
            })
        if p.nickname and q.lower() in p.nickname.lower():
            suggestions.append({
                "type": "nickname",
                "value": p.nickname,
                "label": f"{p.nickname} ({p.process_number})",
                "process_id": p.id,
            })
    return AutocompleteResponse(suggestions=suggestions[:10]).model_dump()
