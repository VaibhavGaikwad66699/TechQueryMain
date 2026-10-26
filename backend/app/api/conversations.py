import json
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.api.deps import get_current_user
from app.database.session import get_db
from app.models.conversation import Conversation, Message
from app.models.user import User, UserPreference
from app.schemas.conversation import ConversationCreate, ConversationDetailResponse, ConversationResponse, MessageResponse
from app.schemas.rag import QueryRequest, QueryResponse, SourceReference
from app.services.rag_service import rag_service
from app.services.library_access import resolve_subject, subject_names

router = APIRouter(prefix="/conversations", tags=["Conversations & Chat"])

@router.get("", response_model=List[ConversationResponse])
def list_conversations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieve all conversations for the authenticated user, ordered by most recently updated."""
    return db.query(Conversation)\
        .filter(Conversation.user_id == current_user.id)\
        .order_by(Conversation.updated_at.desc())\
        .all()

@router.post("", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
def create_conversation(
    conv_in: ConversationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new technical discussion thread."""
    pref = db.query(UserPreference).filter_by(user_id=current_user.id).first()
    preferred = pref.preferred_subject if pref and pref.preferred_subject in subject_names(db, current_user.id) else 'All'
    subject = resolve_subject(db, conv_in.subject or preferred, current_user.id)
    conv = Conversation(
        user_id=current_user.id,
        title=conv_in.title or "New Discussion",
        subject=subject
    )
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv

@router.get("/{conversation_id}", response_model=ConversationDetailResponse)
def get_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get full conversation details including messages and source citations."""
    conv = db.query(Conversation)\
        .filter(Conversation.id == conversation_id, Conversation.user_id == current_user.id)\
        .first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Format messages and parse sources_json
    formatted_messages = []
    for msg in conv.messages:
        sources = None
        try:
            metadata = json.loads(msg.preferences_json or "{}")
        except (TypeError, ValueError):
            metadata = {}
        if not isinstance(metadata, dict):
            metadata = {}
        if msg.sources_json:
            try:
                sources_data = json.loads(msg.sources_json)
                sources = [SourceReference(**s) for s in sources_data]
            except Exception:
                sources = None

        formatted_messages.append(MessageResponse(
            id=msg.id,
            conversation_id=msg.conversation_id,
            role=msg.role,
            content=msg.content,
            sources=sources,
            created_at=msg.created_at,
            response_mode=metadata.get("response_mode"),
            abstained=metadata.get("abstained"),
            retrieval_mode=metadata.get("retrieval_mode"),
            suggested_questions=metadata.get("suggested_questions", []) if not metadata.get("abstained") else [],
        ))

    return ConversationDetailResponse(
        id=conv.id,
        user_id=conv.user_id,
        title=conv.title,
        subject=conv.subject,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        messages=formatted_messages
    )

@router.delete("/{conversation_id}", status_code=status.HTTP_200_OK)
def delete_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a conversation and all its messages."""
    conv = db.query(Conversation)\
        .filter(Conversation.id == conversation_id, Conversation.user_id == current_user.id)\
        .first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    db.delete(conv)
    db.commit()
    return {"message": "Conversation deleted successfully"}

@router.post("/{conversation_id}/messages", response_model=QueryResponse)
def send_message_in_conversation(
    conversation_id: int,
    query_in: QueryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Send a question in a conversation:
    1. Saves the user's message.
    2. Runs RAG retrieval over textbooks.
    3. Calls Gemini with user preferences.
    4. Saves the assistant's message with sources.
    5. Updates conversation title if it's the first message.
    """
    conv = db.query(Conversation)\
        .filter(Conversation.id == conversation_id, Conversation.user_id == current_user.id)\
        .first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    subject_to_use = resolve_subject(db, query_in.subject or (conv.subject if conv.subject in subject_names(db, current_user.id) else 'All'), current_user.id)

    # Get user's saved preferences
    user_pref = db.query(UserPreference).filter(UserPreference.user_id == current_user.id).first()
    pref_dict = {
        "explanation_level": query_in.explanation_level or (user_pref.explanation_level if user_pref else "Intermediate"),
        "answer_style": query_in.answer_style or (user_pref.answer_style if user_pref else "Detailed"),
        "include_examples": query_in.include_examples if query_in.include_examples is not None else (user_pref.include_examples if user_pref else True),
    }

    # Record user message
    user_msg = Message(
        conversation_id=conv.id,
        role="user",
        content=query_in.question.strip()
    )
    db.add(user_msg)
    db.commit()

    # Update conversation title if default
    if conv.title == "New Discussion" or conv.title == "New Technical Discussion":
        words = query_in.question.strip().split()
        short_title = " ".join(words[:6])
        if len(short_title) > 40:
            short_title = short_title[:37] + "..."
        conv.title = short_title.capitalize()

    # RAG Retrieval
    sources = rag_service.retrieve_relevant_chunks(
        db=db,
        query=query_in.question,
        subject=subject_to_use,
        top_k=5, user_id=current_user.id
    )

    # Gemini Generation
    result = rag_service.generate_answer_result(
        question=query_in.question,
        sources=sources,
        db=db,
        preferences=pref_dict, user_id=current_user.id, subject=subject_to_use
    )
    if result.cited_source_keys:
        sources = [s for s in sources if f"{s.document_id}:{s.chunk_index}" in result.cited_source_keys]
    if not result.context_used:
        sources = []
    retrieval_mode = ("hybrid" if len({s.retrieval_method for s in sources}) > 1 else sources[0].retrieval_method) if sources else "none"
    suggestions = rag_service.suggested_questions(query_in.question, subject_to_use) if not result.abstained else []

    # Serialize sources
    sources_data = [s.model_dump() for s in sources]
    sources_json = json.dumps(sources_data) if sources_data else None

    # Record assistant message
    asst_msg = Message(
        conversation_id=conv.id,
        role="assistant",
        content=result.answer,
        sources_json=sources_json,
        preferences_json=json.dumps({**pref_dict, "response_mode": result.response_mode, "abstained": result.abstained, "retrieval_mode": retrieval_mode, "suggested_questions": suggestions})
    )
    db.add(asst_msg)
    db.commit()
    db.refresh(asst_msg)

    return QueryResponse(
        answer=result.answer,
        sources=sources,
        context_used=result.context_used,
        response_mode=result.response_mode,
        abstained=result.abstained,
        retrieval_mode=retrieval_mode,
        conversation_id=conv.id,
        message_id=asst_msg.id,
        preferences_applied=pref_dict,
        suggested_questions=suggestions
    )
