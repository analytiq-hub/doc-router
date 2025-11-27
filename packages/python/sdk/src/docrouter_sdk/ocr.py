from typing import Optional, Dict, Any

class OCRAPI:
    """API client for OCR (Optical Character Recognition) operations"""
    
    def __init__(self, client):
        """
        Initialize the OCR API client
        
        Args:
            client: The parent DocRouterClient instance
        """
        self.client = client
    
    def get_blocks(self, organization_id: str, document_id: str) -> Dict[str, Any]:
        """
        Get OCR blocks for a document
        
        Args:
            organization_id: The organization ID
            document_id: The document ID
            
        Returns:
            Dict containing OCR block data with position and text information
        """
        return self.client.request(
            "GET",
            f"/v0/orgs/{organization_id}/ocr/download/blocks/{document_id}"
        )
    
    def get_text(self, organization_id: str, document_id: str, page_num: Optional[int] = None) -> str:
        """
        Get OCR text for a document
        
        Args:
            organization_id: The organization ID
            document_id: The document ID
            page_num: Optional page number (1-based). If not provided, returns text for all pages.
            
        Returns:
            OCR text as string
        """
        params = {}
        if page_num is not None:
            params["page_num"] = page_num
            
        return self.client.request(
            "GET",
            f"/v0/orgs/{organization_id}/ocr/download/text/{document_id}",
            params=params
        )
    
    def get_metadata(self, organization_id: str, document_id: str) -> Dict[str, Any]:
        """
        Get OCR metadata for a document
        
        Args:
            organization_id: The organization ID
            document_id: The document ID
            
        Returns:
            Dict with metadata including n_pages and ocr_date
        """
        return self.client.request(
            "GET",
            f"/v0/orgs/{organization_id}/ocr/download/metadata/{document_id}"
        )
