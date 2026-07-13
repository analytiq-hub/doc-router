from typing import Dict, Any, Optional
from .models.llm import (
    LLMChatModel,
    LLMEmbeddingModel,
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
            "/v0/account/llm/models"
        )
        return ListLLMModelsResponse(**data)
    
    def run(self, organization_id: str, document_id: str, prompt_revid: str = "default", force: bool = False) -> LLMRunResponse:
        """
        Run LLM analysis on a document
        
        Args:
            organization_id: The organization ID
            document_id: The document ID
            prompt_revid: The prompt revision ID to use
            force: Whether to force a new run even if results exist
            
        Returns:
            LLMRunResponse with status and result
        """
        params = {"prompt_revid": prompt_revid, "force": force}
        
        data = self.client.request(
            "POST",
            f"/v0/orgs/{organization_id}/llm/run/{document_id}",
            params=params
        )
        return LLMRunResponse(**data)
    
    def get_result(
        self,
        organization_id: str,
        document_id: str,
        prompt_id: Optional[str] = None,
        prompt_revid: Optional[str] = None,
        prompt_revid_fallback: bool = False,
        fallback: Optional[bool] = None,
    ) -> LLMResult:
        """
        Get LLM results for a document

        Provide ``prompt_id`` or ``prompt_revid``; if neither is given, the virtual
        default prompt ("default") is used.

        Args:
            organization_id: The organization ID
            document_id: The document ID
            prompt_id: Stable prompt ID. When provided, returns the latest available
                result for this prompt regardless of version (prompt_revid/
                prompt_revid_fallback are ignored). Use this to retrieve results with a
                single stable ID that survives prompt edits.
            prompt_revid: The prompt revision ID to retrieve
            prompt_revid_fallback: If True, return the latest available result for the
                prompt behind the given prompt_revid
            fallback: Deprecated alias for ``prompt_revid_fallback``, retained for
                backward compatibility.

        Returns:
            LLMResult with analysis results
        """
        # Backward-compat: `fallback` was renamed to `prompt_revid_fallback`.
        if fallback is not None:
            prompt_revid_fallback = fallback

        # Preserve historical behavior: with no prompt selector, target the default prompt.
        if prompt_id is None and prompt_revid is None:
            prompt_revid = "default"

        params = {"prompt_revid_fallback": prompt_revid_fallback}
        if prompt_id is not None:
            params["prompt_id"] = prompt_id
        if prompt_revid is not None:
            params["prompt_revid"] = prompt_revid

        data = self.client.request(
            "GET",
            f"/v0/orgs/{organization_id}/llm/result/{document_id}",
            params=params
        )
        return LLMResult(**data)
    
    def update_result(self, organization_id: str, document_id: str, updated_llm_result: Dict[str, Any], prompt_revid: str = "default", is_verified: bool = False) -> LLMResult:
        """
        Update LLM results for a document
        
        Args:
            organization_id: The organization ID
            document_id: The document ID
            updated_llm_result: The updated LLM result
            prompt_revid: The prompt revision ID to update
            is_verified: Whether the result is verified
            
        Returns:
            Updated LLMResult
        """
        params = {"prompt_revid": prompt_revid}
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
    
    def delete_result(self, organization_id: str, document_id: str, prompt_revid: str) -> Dict[str, str]:
        """
        Delete LLM results for a document
        
        Args:
            organization_id: The organization ID
            document_id: The document ID
            prompt_revid: The prompt revision ID to delete
            
        Returns:
            Dict with status message
        """
        params = {"prompt_revid": prompt_revid}
        
        return self.client.request(
            "DELETE",
            f"/v0/orgs/{organization_id}/llm/result/{document_id}",
            params=params
        )
