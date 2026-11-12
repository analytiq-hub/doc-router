from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class CaseCreate(BaseModel):
    name: str = Field(min_length=1)
    tag_ids: List[str] = Field(default_factory=list)
    metadata: Dict[str, str] = Field(default_factory=dict)


class CaseUpdate(BaseModel):
    name: Optional[str] = None
    tag_ids: Optional[List[str]] = None
    metadata: Optional[Dict[str, str]] = None


class CaseOut(BaseModel):
    case_id: str
    name: str
    tag_ids: List[str] = Field(default_factory=list)
    metadata: Dict[str, str] = Field(default_factory=dict)
    document_count: int
    created_by: str
    created_at: datetime
    updated_at: datetime


class ListCasesResponse(BaseModel):
    cases: List[CaseOut]
    total_count: int
    skip: int
