from datetime import datetime
from typing import List, Optional, Dict
from pydantic import BaseModel


class DocumentInputSpec(BaseModel):
    """
    Document input matching rule for a single alias.
    """
    metadata_match: Dict[str, str] = {}


class IncludeConfig(BaseModel):
    """
    Controls which parts of each document are included in the generated LLM context.
    """
    ocr_text: bool = True
    metadata: bool = False
    pdf: bool = True


class PromptConfig(BaseModel):
    name: str
    content: str
    schema_id: Optional[str] = None
    schema_version: Optional[int] = None
    tag_ids: List[str] = []
    model: str = "gpt-4o-mini"
    kb_id: Optional[str] = None  # Optional knowledge base ID for RAG
    # Grouped peer prompt fields (see docs/plan-prompt-group-by.md)
    metadata_group_by: List[str] = []
    document_inputs: Dict[str, DocumentInputSpec] = {}
    include: IncludeConfig = IncludeConfig()


class Prompt(PromptConfig):
    prompt_revid: str
    prompt_id: str
    prompt_version: int
    created_at: datetime
    created_by: str

class ListPromptsResponse(BaseModel):
    prompts: List[Prompt]
    total_count: int
    skip: int
