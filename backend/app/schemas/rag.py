from typing import List, Optional
from pydantic import BaseModel, Field, field_validator
from typing import Literal
from app.schemas.preference import ExplanationLevel, AnswerStyle
from app.core.scope import SubjectName

class SourceReference(BaseModel):
    document_id: int
    document_title: str
    page_number: int
    chunk_index: int
    similarity_score: float
    snippet: str
    retrieval_method: Literal["semantic", "lexical", "hybrid"] = "lexical"

class QueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    conversation_id: Optional[int] = None
    subject: Optional[SubjectName] = None
    explanation_level: Optional[ExplanationLevel] = None
    answer_style: Optional[AnswerStyle] = None
    include_examples: Optional[bool] = None

    @field_validator("question")
    @classmethod
    def nonempty_question(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("Question must not be blank")
        return value

class QueryResponse(BaseModel):
    answer: str
    sources: List[SourceReference]
    context_used: bool
    conversation_id: Optional[int] = None
    message_id: Optional[int] = None
    preferences_applied: dict
    suggested_questions: List[str] = Field(default_factory=list)
    response_mode: Literal["generated", "source_excerpts", "abstained", "general_ai"] = "source_excerpts"
    retrieval_mode: Literal["semantic", "lexical", "hybrid", "none"] = "none"
    abstained: bool = False
