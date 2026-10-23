"""Durable page checkpoints; publish complete text in one transaction."""
import hashlib
import json
import re
from pathlib import Path

from app.core.config import settings
from app.models.document import DocumentChunk, ExtractionCheckpoint, ExtractionPage
from app.services.embedding_service import read_metadata
from app.services.pdf_service import pdf_service


def file_digest(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def extract_saved_pages(db, doc, path, digest, existing, local_only):
    checkpoint = db.get(ExtractionCheckpoint, doc.id)
    if checkpoint is None or checkpoint.source_sha256 != digest or checkpoint.complete:
        # Read/validate the new PDF before replacing even its old staging state.
        info = pdf_service.extract_document_info(path)
        if checkpoint is not None:
            db.delete(checkpoint)
            db.flush()
        checkpoint = ExtractionCheckpoint(document_id=doc.id, source_sha256=digest,
            total_pages=info['total_pages'], last_page=0, extractor=pdf_service.extractor(), complete=False, text_bytes=0)
        db.add(checkpoint)
        db.commit()
        db.expire(doc, ['extraction_checkpoint'])
    for number, text in pdf_service.iter_pages(path, checkpoint.total_pages,
            checkpoint.last_page + 1, checkpoint.extractor):
        if number != checkpoint.last_page + 1:
            raise ValueError('PDF extraction checkpoint page order is inconsistent.')
        text = re.sub(r'\s+', ' ', text).strip()
        size = len(text.encode('utf-8'))
        if checkpoint.text_bytes + size > settings.PDF_MAX_TEXT_BYTES:
            raise ValueError('PDF text exceeds the configured extraction size limit.')
        chunks = [chunk for chunk in pdf_service._split_text(text) if len(chunk.strip()) >= 30] if text else []
        db.add(ExtractionPage(document_id=doc.id, page_number=number, chunks_json=json.dumps(chunks)))
        checkpoint.last_page = number
        checkpoint.text_bytes += size
        db.commit()  # Page text and cursor always advance together, including blank pages.
    if checkpoint.last_page != checkpoint.total_pages or file_digest(path) != digest:
        raise ValueError('PDF changed or extraction did not finish; saved text has not been replaced.')
    pages = db.query(ExtractionPage).filter_by(document_id=doc.id).order_by(ExtractionPage.page_number).all()
    if [page.page_number for page in pages] != list(range(1, checkpoint.total_pages + 1)):
        raise ValueError('Saved extraction pages are incomplete.')
    extracted = [(page.page_number, text) for page in pages for text in json.loads(page.chunks_json)]
    if not extracted:
        raise ValueError('No readable text found. Scanned PDFs require OCR, which is not enabled.')
    same = len(existing) == len(extracted) and all(
        (old.chunk_index, old.page_number, old.content) == (index, number, text)
        for index, (old, (number, text)) in enumerate(zip(existing, extracted)))
    if same:
        for chunk in existing:
            metadata = read_metadata(chunk.metadata_json)
            metadata.update(source_sha256=digest, extraction_version=1)
            chunk.metadata_json = json.dumps(metadata)
    else:
        db.query(DocumentChunk).filter_by(document_id=doc.id).delete(synchronize_session='fetch')
        for index, (number, text) in enumerate(extracted):
            metadata = {'page': number, 'source_sha256': digest, 'extraction_version': 1,
                'extractor': checkpoint.extractor}
            if local_only:
                metadata['provider_access'] = 'local_only'
            db.add(DocumentChunk(document_id=doc.id, chunk_index=index, page_number=number,
                content=text, token_count=max(1, len(text.split())), metadata_json=json.dumps(metadata)))
    checkpoint.complete = True
    for page in pages:
        db.delete(page)
    doc.total_pages = checkpoint.total_pages
    doc.total_chunks = len(extracted)
    db.commit()  # Replacement + complete marker + removal of staging is atomic.
    db.expire(doc, ['chunks', 'extraction_checkpoint'])
