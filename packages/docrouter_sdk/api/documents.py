import base64
from typing import List, Optional, Dict, Any
from ..models.document import (
    DocumentUpload,
    DocumentsUpload,
    DocumentMetadata,
    DocumentResponse,
    DocumentUpdate,
    ListDocumentsResponse
)

class DocumentsAPI:
    def __init__(self, client):
        self.client = client
    
    def upload(self, organization_id: str, documents: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """
        Upload one or more documents
        
        Args:
            organization_id: The organization ID
            documents: List of documents to upload, each with:
                - name: Document filename
                - content: Base64 encoded content (can be data URL or plain base64)
                - tag_ids: Optional list of tag IDs
            
        Returns:
            Dict with uploaded_documents list containing document metadata
        """
        # Convert to expected format
        docs_upload = {"documents": documents}
        return self.client.request(
            "POST",
            f"/v0/orgs/{organization_id}/documents",
            json=docs_upload
        )
    
    def list(self, organization_id: str, skip: int = 0, limit: int = 10, tag_ids: List[str] = None) -> ListDocumentsResponse:
        """
        List documents
        
        Args:
            organization_id: The organization ID
            skip: Number of documents to skip
            limit: Maximum number of documents to return
            tag_ids: Optional list of tag IDs to filter by
            
        Returns:
            ListDocumentsResponse containing documents, total count, and skip
        """
        params = {"skip": skip, "limit": limit}
        if tag_ids:
            params["tag_ids"] = ",".join(tag_ids)
            
        data = self.client.request(
            "GET",
            f"/v0/orgs/{organization_id}/documents",
            params=params
        )
        return ListDocumentsResponse(**data)
    
    def get(self, organization_id: str, document_id: str) -> DocumentResponse:
        """
        Get a document
        
        Args:
            organization_id: The organization ID
            document_id: The document ID
            
        Returns:
            DocumentResponse containing document metadata and content
        """
        data = self.client.request(
            "GET",
            f"/v0/orgs/{organization_id}/documents/{document_id}"
        )
        return DocumentResponse(**data)
    
    def update(self, organization_id: str, document_id: str, document_name: Optional[str] = None, tag_ids: List[str] = None) -> Dict[str, str]:
        """
        Update a document
        
        Args:
            organization_id: The organization ID
            document_id: The document ID
            document_name: Optional new name for the document
            tag_ids: Optional list of tag IDs
            
        Returns:
            Dict with status message
        """
        update_data = {}
        if document_name is not None:
            update_data["document_name"] = document_name
        if tag_ids is not None:
            update_data["tag_ids"] = tag_ids
            
        return self.client.request(
            "PUT",
            f"/v0/orgs/{organization_id}/documents/{document_id}",
            json=update_data
        )
    
    def delete(self, organization_id: str, document_id: str) -> Dict[str, str]:
        """
        Delete a document
        
        Args:
            organization_id: The organization ID
            document_id: The document ID
            
        Returns:
            Dict with status message
        """
        return self.client.request(
            "DELETE",
            f"/v0/orgs/{organization_id}/documents/{document_id}"
        )
