"""Bounded local background processing; persisted document state survives worker failures.

One API process owns admission. Source-page checkpoints persist; OS locks prevent
recovering a live worker, and interrupted work becomes resumable after restart.
"""
import logging
from threading import Lock

from app.core.config import settings
from app.database.session import SessionLocal
from app.models.document import Document, ExtractionCheckpoint
from app.services.file_locks import document_lock, LockBusy
from app.services.rag_service import rag_service

logger = logging.getLogger(__name__)
_active = set()
_lock = Lock()


class JobConflict(Exception):
    pass


class QueueFull(Exception):
    pass


def is_active(document_id):
    with _lock:
        return document_id in _active


def schedule(db, document, background_tasks):
    recover_interrupted(db, [document])
    with _lock:
        if document.id in _active or document.status == 'processing':
            raise JobConflict('This document is already processing.')
        if len(_active) >= settings.MAX_INGESTION_JOBS:
            raise QueueFull('Another PDF is processing. Retry shortly.')
        _active.add(document.id)
    try:
        document.status = 'pending'
        document.error_message = None
        db.commit()
        background_tasks.add_task(_run, document.id)
    except Exception:
        with _lock:
            _active.discard(document.id)
        raise


def _run(document_id):
    try:
        with SessionLocal() as db:
            try:
                rag_service.process_document(db, document_id)
            except Exception as exc:
                from app.services.index_service import IndexingInProgress
                if isinstance(exc, IndexingInProgress):
                    return  # Another OS-locked worker owns its status/progress.
                db.rollback()
                document = db.get(Document, document_id)
                if document is not None and document.status in ('pending', 'processing') and not document.error_message:
                    checkpoint = db.get(ExtractionCheckpoint, document_id)
                    document.status = 'pending' if checkpoint and not checkpoint.complete else 'error'
                    document.error_message = 'Processing stopped unexpectedly. Retry processing to resume saved work.'
                    db.commit()
                logger.warning('PDF processing stopped: document=%s error=%s code=%s', document_id, type(exc).__name__, getattr(exc, 'code', None))
    finally:
        with _lock:
            _active.discard(document_id)


def recover_interrupted(db, documents=None):
    documents = documents if documents is not None else db.query(Document).filter_by(status='processing').all()
    recovered = 0
    for doc in documents:
        if doc.status != 'processing' or is_active(doc.id):
            continue
        try:
            with document_lock(doc.id):
                db.refresh(doc)
                if doc.status != 'processing':
                    continue
                checkpoint = db.get(ExtractionCheckpoint, doc.id)
                incomplete = checkpoint is not None and not checkpoint.complete
                doc.status = 'pending' if incomplete or not doc.chunks else 'partial'
                doc.error_message = ('Reading was interrupted. Resume from the saved page checkpoint.' if incomplete
                    else 'Processing was interrupted. Resume to continue saved work.')
                db.commit()
                recovered += 1
        except LockBusy:
            continue
    return recovered
