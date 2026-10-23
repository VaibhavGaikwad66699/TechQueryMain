from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.scope import LANGUAGE_FILTERS, SUPPORTED_LANGUAGES
from app.database.session import get_db
from app.api.deps import get_optional_current_user
from app.services.library_access import visible_documents
from app.models.document import Document, DocumentChunk
from app.services.embedding_service import embedding_service
from app.services.index_service import index_coverage

router = APIRouter(tags=["Health & Status"])

@router.get("/ready")
def readiness(db: Session = Depends(get_db)):
    """Cheap local readiness check; does not call providers or scan vector data."""
    from fastapi import HTTPException
    try:
        db.execute(text("SELECT 1 FROM documents LIMIT 1"))
    except Exception:
        raise HTTPException(status_code=503, detail="Database is not ready")
    return {"status": "ready"}

SUPPORTED_SUBJECTS = list(LANGUAGE_FILTERS)

@router.get("/health")
def health_check(db: Session = Depends(get_db), user=Depends(get_optional_current_user)):
    """Health check endpoint validating database connectivity and Gemini configuration."""
    db_ok = False
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False

    docs = db.query(Document).filter(visible_documents(user.id if user else None)).all() if db_ok else []
    doc_count = len(docs)
    coverage = [index_coverage(doc) for doc in docs]
    chunk_count = sum(c['total_chunks'] for c in coverage)
    gemini_configured = embedding_service.is_configured()

    return {
        "status": "online",
        "app_name": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "supported_languages": list(SUPPORTED_LANGUAGES),
        "limits": {"max_pdf_bytes": settings.MAX_PDF_BYTES, "max_question_characters": 4000},
        "database": {
            "status": "connected" if db_ok else "error",
            "type": "SQLite",
            "total_documents": doc_count,
            "in_scope_documents": len(docs),
            "total_indexed_chunks": chunk_count,
            "total_embedded_chunks": sum(c["embedded_chunks"] for c in coverage),
            "semantic_ready_documents": sum(c["semantic_ready"] for c in coverage),
            "unverified_embeddings": sum(c["unverified_embeddings"] for c in coverage),
        },
        "gemini": {
            "configured": gemini_configured,
            "model": settings.GEMINI_MODEL,
            "embedding_model": settings.EMBEDDING_MODEL,
            "availability": "not_checked",
            "instructions": "Set GEMINI_API_KEY in backend/.env to enable live AI responses." if not gemini_configured else "Key configured; provider availability is not checked by this endpoint."
        }
    }
