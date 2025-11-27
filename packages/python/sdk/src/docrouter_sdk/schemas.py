from typing import Dict, Any
from .models.schema import (
    SchemaProperty,
    SchemaResponseFormat,
    SchemaConfig,
    Schema,
    ListSchemasResponse
)

class SchemasAPI:
    def __init__(self, client):
        self.client = client
    
    def create(self, organization_id: str, schema_config: Dict[str, Any]) -> Schema:
        """
        Create a schema
        
        Args:
            organization_id: The organization ID
            schema_config: The schema configuration
            
        Returns:
            Created Schema
        """
        data = self.client.request(
            "POST",
            f"/v0/orgs/{organization_id}/schemas",
            json=schema_config
        )
        return Schema(**data)
    
    def list(self, organization_id: str, skip: int = 0, limit: int = 10) -> ListSchemasResponse:
        """
        List schemas
        
        Args:
            organization_id: The organization ID
            skip: Number of schemas to skip
            limit: Maximum number of schemas to return
            
        Returns:
            ListSchemasResponse with schemas, total count, and skip
        """
        params = {"skip": skip, "limit": limit}
        
        data = self.client.request(
            "GET",
            f"/v0/orgs/{organization_id}/schemas",
            params=params
        )
        return ListSchemasResponse(**data)
    
    def get(self, organization_id: str, schema_revid: str) -> Schema:
        """
        Get a schema
        
        Args:
            organization_id: The organization ID
            schema_revid: The schema revision ID
            
        Returns:
            Schema details
        """
        data = self.client.request(
            "GET",
            f"/v0/orgs/{organization_id}/schemas/{schema_revid}"
        )
        return Schema(**data)
    
    def update(self, organization_id: str, schema_id: str, schema_config: Dict[str, Any]) -> Schema:
        """
        Update a schema
        
        Args:
            organization_id: The organization ID
            schema_id: The schema ID
            schema_config: The updated schema configuration
            
        Returns:
            Updated Schema
        """
        data = self.client.request(
            "PUT",
            f"/v0/orgs/{organization_id}/schemas/{schema_id}",
            json=schema_config
        )
        return Schema(**data)
    
    def delete(self, organization_id: str, schema_id: str) -> Dict[str, str]:
        """
        Delete a schema
        
        Args:
            organization_id: The organization ID
            schema_id: The schema ID
            
        Returns:
            Dict with status message
        """
        return self.client.request(
            "DELETE",
            f"/v0/orgs/{organization_id}/schemas/{schema_id}"
        )
    
    def validate(self, organization_id: str, schema_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate data against a schema
        
        Args:
            organization_id: The organization ID
            schema_id: The schema ID
            data: The data to validate
            
        Returns:
            Validation result
        """
        return self.client.request(
            "POST",
            f"/v0/orgs/{organization_id}/schemas/{schema_id}/validate",
            json=data
        )
