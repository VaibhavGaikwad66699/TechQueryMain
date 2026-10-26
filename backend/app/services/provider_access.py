"""Imported books stay local until their additional provider use is authorized."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from sqlalchemy.orm import object_session

from app.core.scope import SUPPORTED_LANGUAGES
from app.services.embedding_service import read_metadata

LOCAL_ONLY = "local_only"


def provider_use_allowed(document):
    from app.models.document import DocumentChunk
    session = object_session(document)
    if session is not None:
        rows = session.query(DocumentChunk.metadata_json).filter(DocumentChunk.document_id == document.id).yield_per(64)
        return all(read_metadata(row.metadata_json).get('provider_access') != LOCAL_ONLY for row in rows)
    return all(read_metadata(chunk.metadata_json).get("provider_access") != LOCAL_ONLY
        for chunk in document.chunks)


def authorize_provider_use(db, document, authorization_note):
    """Record a human's prior explicit approval; this CLI helper cannot infer it."""
    from app.services.storage_service import storage_service
    if not authorization_note or not authorization_note.strip():
        raise ValueError('An explicit human authorization reference is required')
    if document.subject not in SUPPORTED_LANGUAGES or not document.chunks:
        raise ValueError('A supported book with extracted text is required')
    if document.status == 'processing':
        raise ValueError('Wait for processing to stop before changing provider access')
    digest = hashlib.sha256(Path(storage_service.get_file_path(document.filename)).read_bytes()).hexdigest()
    records = [(chunk, read_metadata(chunk.metadata_json)) for chunk in document.chunks]
    if any(metadata.get('source_sha256') != digest for _, metadata in records):
        raise ValueError('Source fingerprint mismatch; do not authorize changed or unanchored text')
    pending = [(chunk, metadata) for chunk, metadata in records if metadata.get('provider_access') == LOCAL_ONLY]
    if not pending:
        return {'document_id': document.id, 'changed_chunks': 0, 'already_allowed': True}
    approval = {'provider': 'Google Gemini', 'purposes': ['embeddings', 'answer_generation'],
        'source_sha256': digest, 'authorized_at': datetime.now(timezone.utc).isoformat(),
        'authorization_reference': authorization_note.strip()}
    try:
        for chunk, metadata in pending:
            metadata.update(provider_access='google_approved', provider_authorization=approval)
            chunk.metadata_json = json.dumps(metadata)
        document.error_message = 'Google use approved. Saved text is searchable; resume indexing to build compatible embeddings.'
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {'document_id': document.id, 'changed_chunks': len(pending),
        'source_sha256': digest, 'provider': approval['provider'], 'authorized_at': approval['authorized_at']}
