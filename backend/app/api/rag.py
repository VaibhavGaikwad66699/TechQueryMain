from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.api.deps import get_optional_current_user
from app.database.session import get_db
from app.models.user import User, UserPreference
from app.schemas.rag import QueryRequest, QueryResponse
from app.services.rag_service import rag_service
from app.services.library_access import resolve_subject, subject_names

router = APIRouter(prefix="/query", tags=["RAG Query Engine"])

@router.post("", response_model=QueryResponse)
def query_knowledge_base(
    query_in: QueryRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """
    Direct RAG querying endpoint:
    Retrieves top passages and generates grounded answer with user preferences.
    Accessible to logged in users and guests.
    """
    user_pref = None
    if current_user:
        user_pref = db.query(UserPreference).filter(UserPreference.user_id == current_user.id).first()

    pref_dict = {
        "explanation_level": query_in.explanation_level or (user_pref.explanation_level if user_pref else "Intermediate"),
        "answer_style": query_in.answer_style or (user_pref.answer_style if user_pref else "Detailed"),
        "include_examples": query_in.include_examples if query_in.include_examples is not None else (user_pref.include_examples if user_pref else True),
    }

    default_subject = user_pref.preferred_subject if user_pref and user_pref.preferred_subject in subject_names(db, current_user.id) else 'All'
    subject = resolve_subject(db, query_in.subject or default_subject, current_user.id if current_user else None)
    sources = rag_service.retrieve_relevant_chunks(
        db=db,
        query=query_in.question,
        subject=subject,
        top_k=5, user_id=current_user.id if current_user else None
    )

    result = rag_service.generate_answer_result(
        question=query_in.question,
        sources=sources,
        db=db,
        preferences=pref_dict, user_id=current_user.id if current_user else None, subject=subject
    )
    if result.cited_source_keys:
        sources = [s for s in sources if f"{s.document_id}:{s.chunk_index}" in result.cited_source_keys]
    if not result.context_used:
        sources = []

    return QueryResponse(
        answer=result.answer,
        sources=sources,
        context_used=result.context_used,
        response_mode=result.response_mode,
        abstained=result.abstained,
        retrieval_mode=("hybrid" if len({s.retrieval_method for s in sources}) > 1 else sources[0].retrieval_method) if sources else "none",
        preferences_applied=pref_dict,
        suggested_questions=rag_service.suggested_questions(query_in.question, subject) if not result.abstained else []
    )
