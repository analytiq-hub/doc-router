from datetime import datetime
from typing import Dict, List, Optional, Literal
from pydantic import BaseModel

class LLMModel(BaseModel):
    id: str
    name: str
    provider: str
    description: str
    max_tokens: int
    cost_per_1m_input_tokens: float
    cost_per_1m_output_tokens: float

class ListLLMModelsResponse(BaseModel):
    models: List[LLMModel]

class LLMRunResponse(BaseModel):
    status: str
    result: dict

class LLMResult(BaseModel):
    prompt_id: str
    document_id: str
    llm_result: dict
    updated_llm_result: dict
    is_edited: bool
    is_verified: bool
    created_at: datetime
    updated_at: datetime

class UpdateLLMResultRequest(BaseModel):
    updated_llm_result: dict
    is_verified: bool = False
