from typing import Dict, List, Optional, Any
from .models.prompt import (
    PromptConfig,
    Prompt,
    ListPromptsResponse
)

class PromptsAPI:
    def __init__(self, client):
        self.client = client
    
    def create(self, organization_id: str, prompt_config: Dict[str, Any]) -> Prompt:
        """
        Create a prompt
        
        Args:
            organization_id: The organization ID
            prompt_config: The prompt configuration
            
        Returns:
            Created Prompt
        """
        data = self.client.request(
            "POST",
            f"/v0/orgs/{organization_id}/prompts",
            json=prompt_config
        )
        return Prompt(**data)
    
    def list(self, organization_id: str, skip: int = 0, limit: int = 10, document_id: Optional[str] = None, tag_ids: List[str] = None) -> ListPromptsResponse:
        """
        List prompts
        
        Args:
            organization_id: The organization ID
            skip: Number of prompts to skip
            limit: Maximum number of prompts to return
            document_id: Optional document ID to filter by
            tag_ids: Optional list of tag IDs to filter by
            
        Returns:
            ListPromptsResponse with prompts, total count, and skip
        """
        params = {"skip": skip, "limit": limit}
        if document_id:
            params["document_id"] = document_id
        if tag_ids:
            params["tag_ids"] = ",".join(tag_ids)
            
        data = self.client.request(
            "GET",
            f"/v0/orgs/{organization_id}/prompts",
            params=params
        )
        return ListPromptsResponse(**data)
    
    def get(self, organization_id: str, prompt_revid: str) -> Prompt:
        """
        Get a prompt

        Args:
            organization_id: The organization ID
            prompt_revid: The prompt revision ID

        Returns:
            Prompt details
        """
        data = self.client.request(
            "GET",
            f"/v0/orgs/{organization_id}/prompts/{prompt_revid}"
        )
        return Prompt(**data)
    
    def update(self, organization_id: str, prompt_id: str, prompt_config: Dict[str, Any]) -> Prompt:
        """
        Update a prompt
        
        Args:
            organization_id: The organization ID
            prompt_id: The prompt ID
            prompt_config: The updated prompt configuration
            
        Returns:
            Updated Prompt
        """
        data = self.client.request(
            "PUT",
            f"/v0/orgs/{organization_id}/prompts/{prompt_id}",
            json=prompt_config
        )
        return Prompt(**data)
    
    def delete(self, organization_id: str, prompt_id: str) -> Dict[str, str]:
        """
        Delete a prompt
        
        Args:
            organization_id: The organization ID
            prompt_id: The prompt ID
            
        Returns:
            Dict with status message
        """
        return self.client.request(
            "DELETE",
            f"/v0/orgs/{organization_id}/prompts/{prompt_id}"
        )
