from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class DocumentUpload(BaseModel):
    name: str
    content: str = Field(
        ..., 
        description="Base64 encoded file content. Can be either:\n"
                   "1. Plain base64: 'JVBERi0xLjQK...'\n"
                   "2. Data URL: 'data:application/pdf;base64,JVBERi0xLjQK...'"
    )
    tag_ids: List[str] = []
    metadata: Optional[Dict[str, str]] = {}

class DocumentsUpload(BaseModel):
    documents: List[DocumentUpload]

class DocumentMetadata(BaseModel):
    id: str
    document_name: str
    upload_date: datetime
    uploaded_by: str
    state: str
    tag_ids: List[str] = []
    metadata: Optional[Dict[str, str]] = {}

class DocumentResponse(BaseModel):
    id: str
    pdf_id: str
    document_name: str
    upload_date: datetime
    uploaded_by: str
    state: str
    tag_ids: List[str] = []
    type: Optional[str] = None
    metadata: Optional[Dict[str, str]] = {}
    content: str

class DocumentUpdate(BaseModel):
    document_name: Optional[str] = None
    tag_ids: List[str] = []
    metadata: Optional[Dict[str, str]] = {}

class ListDocumentsResponse(BaseModel):
    documents: List[DocumentMetadata]
    total_count: int
    skip: int