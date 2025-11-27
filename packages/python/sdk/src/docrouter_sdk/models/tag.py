from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel

class TagConfig(BaseModel):
    name: str
    color: Optional[str] = None
    description: Optional[str] = None

class Tag(TagConfig):
    id: str
    created_at: datetime
    created_by: str

class ListTagsResponse(BaseModel):
    tags: List[Tag]
    total_count: int
    skip: int
