from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class InstitutionBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    sei_url: str = Field(..., max_length=500)
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class InstitutionCreate(InstitutionBase):
    extra_metadata: Dict[str, Any] = Field(default_factory=dict)


class InstitutionUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    sei_url: Optional[str] = None
    is_active: Optional[bool] = None
    extra_metadata: Optional[Dict[str, Any]] = None
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class InstitutionResponse(InstitutionBase):
    id: int
    user_id: Optional[int] = None
    is_active: bool = True
    extra_metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: Optional[datetime] = None


class InstitutionListResponse(BaseModel):
    items: List[InstitutionResponse]
    total: int
