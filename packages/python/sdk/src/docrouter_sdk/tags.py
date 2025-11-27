from typing import Dict, Any
from .models.tag import (
    TagConfig,
    Tag,
    ListTagsResponse
)

class TagsAPI:
    def __init__(self, client):
        self.client = client
    
    def create(self, organization_id: str, tag_config: Dict[str, Any]) -> Tag:
        """
        Create a tag
        
        Args:
            organization_id: The organization ID
            tag_config: The tag configuration
            
        Returns:
            Created Tag
        """
        data = self.client.request(
            "POST",
            f"/v0/orgs/{organization_id}/tags",
            json=tag_config
        )
        return Tag(**data)
    
    def list(self, organization_id: str, skip: int = 0, limit: int = 10) -> ListTagsResponse:
        """
        List tags
        
        Args:
            organization_id: The organization ID
            skip: Number of tags to skip
            limit: Maximum number of tags to return
            
        Returns:
            ListTagsResponse with tags, total count, and skip
        """
        params = {"skip": skip, "limit": limit}
        
        data = self.client.request(
            "GET",
            f"/v0/orgs/{organization_id}/tags",
            params=params
        )
        return ListTagsResponse(**data)
    
    def update(self, organization_id: str, tag_id: str, tag_config: Dict[str, Any]) -> Tag:
        """
        Update a tag
        
        Args:
            organization_id: The organization ID
            tag_id: The tag ID
            tag_config: The updated tag configuration
            
        Returns:
            Updated Tag
        """
        data = self.client.request(
            "PUT",
            f"/v0/orgs/{organization_id}/tags/{tag_id}",
            json=tag_config
        )
        return Tag(**data)
    
    def delete(self, organization_id: str, tag_id: str) -> Dict[str, str]:
        """
        Delete a tag
        
        Args:
            organization_id: The organization ID
            tag_id: The tag ID
            
        Returns:
            Dict with status message
        """
        return self.client.request(
            "DELETE",
            f"/v0/orgs/{organization_id}/tags/{tag_id}"
        )
