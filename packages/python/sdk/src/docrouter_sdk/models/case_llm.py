from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class CaseLlmRunStartResponse(BaseModel):
    message: str
    queue_message_id: str


class CaseLlmRunSummary(BaseModel):
    run_id: str
    prompt_revid: str
    prompt_version: int
    document_ids: List[str] = Field(default_factory=list)
    llm_result: Optional[Dict[str, Any]] = None
    created_at: datetime
    status: str
    run: Optional[Dict[str, Any]] = None


class CaseLlmResultsResponse(BaseModel):
    prompt_id: str
    latest_prompt_revid: str
    stale: bool
    stale_reasons: List[str] = Field(default_factory=list)
    current_document_ids: List[str] = Field(default_factory=list)
    case_run: Optional[CaseLlmRunSummary] = None
