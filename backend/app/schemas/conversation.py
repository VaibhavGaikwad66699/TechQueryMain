from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.rag import SourceReference
from app.core.scope import SubjectName

class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    conversation_id: int
    role: str
    content: str
    sources: Optional[List[SourceReference]] = None
    created_at: datetime
    response_mode: Optional[str] = None
    abstained: Optional[bool] = None
    retrieval_mode: Optional[str] = None
    suggested_questions: List[str] = Field(default_factory=list)

class ConversationBase(BaseModel):
    title: str = "New Programming Discussion"
    subject: SubjectName = "All"

class ConversationCreate(BaseModel):
    title: Optional[str] = None
    subject: Optional[SubjectName] = None

class ConversationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    title: str
    subject: str
    created_at: datetime
    updated_at: datetime

class ConversationDetailResponse(ConversationResponse):
    messages: List[MessageResponse] = []
