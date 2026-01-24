from datetime import datetime
from typing import Dict, List, Optional, Literal
from pydantic import BaseModel

class LLMChatModel(BaseModel):
    litellm_model: str
    litellm_provider: str
    max_input_tokens: int
    max_output_tokens: int
    input_cost_per_token: float
    output_cost_per_token: float

class LLMEmbeddingModel(BaseModel):
    litellm_model: str
    litellm_provider: str
    max_input_tokens: int
    dimensions: int
    input_cost_per_token: float
    input_cost_per_token_batches: float

class ListLLMModelsResponse(BaseModel):
    chat_models: List[LLMChatModel]
    embedding_models: List[LLMEmbeddingModel]

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
