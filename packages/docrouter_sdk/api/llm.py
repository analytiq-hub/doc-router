from typing import Dict, List, Optional, Any
from ..models.llm import (
    LLMModel,
    ListLLMModelsResponse,
    LLMRunResponse,
    LLMResult,
    UpdateLLMResultRequest
)

class LLMAPI:
    def __init__(self, client):
        self.client = client
    
    def list_models(self) -> ListLLMModelsResponse:
        """
        List available LLM models
        
        Returns:
            ListLLMModelsResponse with available models
        """
        data = self.client.request(
            "GET",
            "/v0/account/llm_models"
        )
        return ListLLMModelsResponse(**data)
    
    def run(self, organization_id: str, document_id: str, prompt_id: str = "default", force: bool = False) -> LLMRunResponse:
        """
        Run LLM analysis on a document
        
        Args:
            organization_id: The organization ID
            document_id: The document ID
            prompt_id: The prompt ID to use
            force: Whether to force a new run even if results exist
            
        Returns:
            LLMRunResponse with status and result
        """
        params = {
            "prompt_id": prompt_id,
            "force": force
        }
        
        data = self.client.request(
            "POST",
            f"/v0/orgs/{organization_id}/llm/run/{document_id}",
            params=params
        )
        return LLMRunResponse(**data)
    
    def get_result(self, organization_id: str, document_id: str, prompt_id: str = "default") -> LLMResult:
        """
        Get LLM results for a document
        
        Args:
            organization_id: The organization ID
            document_id: The document ID
            prompt_id: The prompt ID to retrieve
            
        Returns:
            LLMResult with analysis results
        """
        params = {"prompt_id": prompt_id}
        
        data = self.client.request(
            "GET",
            f"/v0/orgs/{organization_id}/llm/result/{document_id}",
            params=params
        )
        return LLMResult(**data)
    
    def update_result(self, organization_id: str, document_id: str, updated_llm_result: Dict[str, Any], prompt_id: str = "default", is_verified: bool = False) -> LLMResult:
        """
        Update LLM results for a document
        
        Args:
            organization_id: The organization ID
            document_id: The document ID
            updated_llm_result: The updated LLM result
            prompt_id: The prompt ID to update
            is_verified: Whether the result is verified
            
        Returns:
            Updated LLMResult
        """
        params = {"prompt_id": prompt_id}
        update_data = {
            "updated_llm_result": updated_llm_result,
            "is_verified": is_verified
        }
        
        data = self.client.request(
            "PUT",
            f"/v0/orgs/{organization_id}/llm/result/{document_id}",
            params=params,
            json=update_data
        )
        return LLMResult(**data)
    
    def delete_result(self, organization_id: str, document_id: str, prompt_id: str) -> Dict[str, str]:
        """
        Delete LLM results for a document
        
        Args:
            organization_id: The organization ID
            document_id: The document ID
            prompt_id: The prompt ID to delete
            
        Returns:
            Dict with status message
        """
        params = {"prompt_id": prompt_id}
        
        return self.client.request(
            "DELETE",
            f"/v0/orgs/{organization_id}/llm/result/{document_id}",
            params=params
        )
