from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, model_validator

class DocumentBase(BaseModel):
    title: str
    subject: str = "All"  # Keep legacy subjects readable; new uploads are validated separately.

class DocumentResponse(DocumentBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    original_filename: str
    file_size: int
    total_pages: int
    total_chunks: int
    status: str
    error_message: Optional[str] = None
    uploaded_by: Optional[int] = None
    created_at: datetime
    indexing: dict
    is_default: bool = False
    can_modify: bool = False
    processing_active: bool = False
    in_scope: bool = True

    @model_validator(mode="after")
    def correct_legacy_status(self):
        if self.status == "ready" and not self.indexing["semantic_ready"]:
            self.status = "partial"
        return self

class DocumentChunkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    document_id: int
    chunk_index: int
    page_number: int
    content: str
    token_count: int

class DocumentUploadResponse(BaseModel):
    message: str
    document: DocumentResponse
    processing_scheduled: bool = False

class DocumentProcessResponse(BaseModel):
    message: str
    document_id: int
    chunks_created: int
    pages_processed: int
    status: str
    indexing: dict
