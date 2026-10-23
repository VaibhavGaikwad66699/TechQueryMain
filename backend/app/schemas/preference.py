from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict
from app.core.scope import SubjectName

ExplanationLevel = Literal["Beginner", "Intermediate", "Advanced"]
AnswerStyle = Literal["Concise", "Detailed"]

class UserPreferenceBase(BaseModel):
    explanation_level: ExplanationLevel = "Intermediate"
    answer_style: AnswerStyle = "Detailed"
    include_examples: bool = True
    preferred_subject: SubjectName = "All"

class UserPreferenceUpdate(BaseModel):
    explanation_level: Optional[ExplanationLevel] = None
    answer_style: Optional[AnswerStyle] = None
    include_examples: Optional[bool] = None
    preferred_subject: Optional[SubjectName] = None

class UserPreferenceResponse(UserPreferenceBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    updated_at: datetime
