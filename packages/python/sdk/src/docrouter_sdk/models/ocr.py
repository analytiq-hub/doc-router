from pydantic import BaseModel

class GetOCRMetadataResponse(BaseModel):
    n_pages: int
    ocr_date: str
