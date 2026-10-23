"""Text is saved first, then each embedding batch is committed independently."""
import json
import logging

from app.core.config import settings
from app.models.document import Document, DocumentChunk, ExtractionCheckpoint
from app.services.embedding_service import embedding_service, read_metadata
from app.services.provider_access import provider_use_allowed
from app.services.file_locks import document_lock, LockBusy
from app.services.extraction_service import extract_saved_pages, file_digest

logger = logging.getLogger(__name__)


def index_coverage(doc):
    chunks = doc.chunks
    compatible = sum(embedding_service.compatible_vector(c) is not None for c in chunks)
    stored = sum(bool(c.embedding_json) for c in chunks)
    checkpoint = doc.extraction_checkpoint
    extraction = {'total_pages': checkpoint.total_pages if checkpoint else doc.total_pages,
        'saved_pages': checkpoint.last_page if checkpoint else (doc.total_pages if chunks else 0),
        'complete': checkpoint.complete if checkpoint else bool(chunks),
        'extractor': checkpoint.extractor if checkpoint else None}
    return {"total_chunks": len(chunks), "embedded_chunks": compatible, 'extraction': extraction,
        "missing_embeddings": len(chunks) - compatible, "unverified_embeddings": stored - compatible,
        "legacy_text_chunks": sum(read_metadata(c.metadata_json).get("extraction_origin") == "legacy_snapshot" for c in chunks),
        "embedding_model": settings.EMBEDDING_MODEL, "embedding_dimensions": settings.EMBEDDING_DIMENSIONS,
        "provider_use_allowed": provider_use_allowed(doc),
        "semantic_ready": bool(chunks) and extraction['complete'] and compatible == len(chunks)}


class IndexingInProgress(ValueError):
    pass


def process_document(db, document_id, max_chunks=None, reuse_existing_text=False, page_numbers=None):
    try:
        with document_lock(document_id):
            return _process_document(db, document_id, max_chunks, reuse_existing_text, page_numbers)
    except LockBusy as exc:
        raise IndexingInProgress('This document has an active processing worker.') from exc


def _process_document(db, document_id, max_chunks=None, reuse_existing_text=False, page_numbers=None):
    from app.services.storage_service import storage_service
    doc = db.get(Document, document_id)
    if doc is None:
        raise ValueError("Document not found")
    from app.services.library_access import subject_names
    if doc.subject not in subject_names(db, doc.uploaded_by)[1:]:
        raise ValueError("Only C, C++, Java, and Python defaults or subjects belonging to the uploader can be indexed.")
    local_only = not provider_use_allowed(doc)
    limit = settings.INDEX_MAX_CHUNKS_PER_REQUEST if max_chunks is None else max_chunks
    if local_only and limit > 0:
        raise ValueError("This book is available locally. Permission is required before sending its text to Google.")
    acquired = db.query(Document).filter(Document.id == document_id, Document.status != "processing").update(
        {Document.status: "processing", Document.error_message: None}, synchronize_session=False)
    db.commit()
    db.refresh(doc)
    if not acquired:
        raise IndexingInProgress("Already processing; recover an interrupted job explicitly")
    text_ready = False
    try:
        path = storage_service.get_file_path(doc.filename)
        digest = file_digest(path)
        existing = db.query(DocumentChunk).filter_by(document_id=doc.id).order_by(DocumentChunk.chunk_index).all()
        if any(read_metadata(c.metadata_json).get('provider_authorization', {}).get('source_sha256', digest) != digest for c in existing):
            raise ValueError('PDF changed from its approved source fingerprint; import it as a new reference.')
        if reuse_existing_text and existing:
            known_hashes = {read_metadata(c.metadata_json).get("source_sha256") for c in existing} - {None}
            if known_hashes and known_hashes != {digest}:
                raise ValueError("PDF changed since the saved text snapshot; re-extract before embedding")
            if not known_hashes:
                # Explicit migration of legacy stored text. This anchors the snapshot
                # to today's PDF; it does NOT claim a fresh full extraction was verified.
                if doc.total_chunks != len(existing) or len({c.chunk_index for c in existing}) != len(existing) or any(not 1 <= c.page_number <= doc.total_pages for c in existing):
                    raise ValueError("Legacy chunk metadata is inconsistent; re-extraction required")
                for chunk in existing:
                    metadata = read_metadata(chunk.metadata_json)
                    metadata.update(source_sha256=digest, extraction_version=0, extraction_origin="legacy_snapshot")
                    chunk.metadata_json = json.dumps(metadata)
                db.commit()
        checkpoint = db.get(ExtractionCheckpoint, doc.id)
        if not existing or (checkpoint and not checkpoint.complete) or any(read_metadata(c.metadata_json).get("source_sha256") != digest or read_metadata(c.metadata_json).get("extraction_version") not in (0, 1) for c in existing):
            extract_saved_pages(db, doc, path, digest, existing, local_only)
        text_ready = True
        chunks = db.query(DocumentChunk).filter_by(document_id=doc.id).order_by(DocumentChunk.chunk_index).all()
        pending = [c for c in chunks if embedding_service.compatible_vector(c) is None]
        embedded_before = len(chunks) - len(pending)
        if page_numbers:
            pending = [c for c in pending if c.page_number in page_numbers]
        limit = settings.INDEX_MAX_CHUNKS_PER_REQUEST if max_chunks is None else max_chunks
        if limit < 0:
            raise ValueError("max_chunks must be non-negative")
        if pending and embedding_service.is_configured():
            for start in range(0, min(limit, len(pending)), settings.EMBEDDING_BATCH_SIZE):
                batch = pending[start:min(start + settings.EMBEDDING_BATCH_SIZE, limit)]
                vectors = embedding_service.generate_embeddings_batch([c.content for c in batch])
                if len(vectors) != len(batch):
                    raise ValueError("Embedding count does not match chunk count")
                for chunk, vector in zip(batch, vectors):
                    if not embedding_service.valid_vector(vector):
                        raise ValueError("Invalid embedding vector")
                    metadata = read_metadata(chunk.metadata_json)
                    metadata["embedding"] = embedding_service.provenance(chunk.content)
                    chunk.embedding_json = json.dumps(vector)
                    chunk.metadata_json = json.dumps(metadata)
                db.commit()
                logger.info("Saved embedding progress: %s/%s chunks", embedded_before + start + len(batch), len(chunks))
        db.expire(doc, ["chunks"])
        coverage = index_coverage(doc)
        doc.total_chunks = coverage["total_chunks"]
        doc.status = "ready" if coverage["semantic_ready"] else "partial"
        doc.error_message = None if coverage["semantic_ready"] else (
            f"Text searchable; {coverage['embedded_chunks']}/{coverage['total_chunks']} compatible embeddings. "
            + ("Google use is awaiting permission; local passage search is available." if local_only else
                "Resume processing to continue indexing." if embedding_service.is_configured() else "Configure Gemini to enable semantic indexing."))
        db.commit()
        return doc.total_pages, doc.total_chunks
    except Exception as exc:
        db.rollback()
        db.refresh(doc)
        db.expire(doc, ["chunks"])
        doc.total_chunks = len(doc.chunks)
        checkpoint = db.get(ExtractionCheckpoint, doc.id)
        interrupted_text = checkpoint is not None and not checkpoint.complete
        doc.status = 'pending' if interrupted_text else ("partial" if text_ready and doc.chunks else "error")
        if getattr(exc, 'code', None) == 429:
            doc.error_message = 'Embedding quota reached. Saved text remains searchable; retry indexing after the provider quota resets.'
        elif isinstance(exc, ValueError) and str(exc).startswith('No readable text'):
            doc.status = 'error'
            doc.error_message = 'No readable text found. This PDF may need OCR, which is not enabled.'
        elif interrupted_text:
            doc.error_message = f'Reading stopped at page {checkpoint.last_page} of {checkpoint.total_pages}. Resume processing to continue saved work.'
            if isinstance(exc, ValueError) and str(exc) in (
                    'PDF text exceeds the configured extraction size limit.',
                    'PDF text exceeds the per-batch extraction limit.'):
                doc.error_message = str(exc) + ' Saved pages are retained; use a smaller PDF or ask the operator to review the limits.'
        else:
            doc.error_message = f"Indexing stopped ({type(exc).__name__}, code={getattr(exc, 'code', None)}). Saved batches are retained; retry processing to resume."
        db.commit()
        raise
