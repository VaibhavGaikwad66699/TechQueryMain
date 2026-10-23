"""Inspect, estimate, and resume indexing without recreating PDFs or database records."""
import argparse
import json
import math
import logging
import time
from app.core.config import settings
from app.core.scope import SUPPORTED_LANGUAGES
from app.database.session import SessionLocal
from app.models.document import Document
from app.services.embedding_service import embedding_service, provider_failure
from app.services.index_service import index_coverage
from app.services.rag_service import rag_service
from app.services.provider_access import provider_use_allowed, authorize_provider_use


def report(doc):
    coverage = index_coverage(doc)
    pending = [c for c in doc.chunks if embedding_service.compatible_vector(c) is None]
    return {"id": doc.id, "title": doc.title, "status": doc.status, **coverage,
        "estimated_input_tokens": sum(math.ceil(len(c.content) / 4) for c in pending),
        "estimate_note": "Character-based approximation, not provider token accounting or a price quote",
        "estimated_batches": math.ceil(len(pending) / settings.EMBEDDING_BATCH_SIZE)}


def main():
    index_logger = logging.getLogger('app.services.index_service')
    index_logger.setLevel(logging.INFO)
    index_logger.addHandler(logging.StreamHandler())
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['report', 'probe', 'resume', 'reconcile', 'recover', 'authorize-provider'])
    parser.add_argument('--document-id', type=int)
    parser.add_argument('--authorization-note', help='Reference to explicit prior human approval; required for authorize-provider')
    parser.add_argument('--max-chunks', type=int, default=16, help='Upper bound on chunks embedded in this invocation')
    parser.add_argument('--batch-size', type=int, default=None)
    parser.add_argument('--reuse-existing-text', action='store_true', help='Explicitly adopt legacy extracted text without reparsing the PDF; recorded as extraction version 0')
    parser.add_argument('--pace-seconds', type=float, default=0, help='Pause between committed batches, allowing lexical queries between batches')
    parser.add_argument('--pages', help='Optional comma-separated physical PDF pages to backfill first')
    args = parser.parse_args()
    if args.max_chunks < 0:
        parser.error('max-chunks must be non-negative')
    if not 0 <= args.pace_seconds <= 60:
        parser.error('pace-seconds must be 0..60')
    pages = {int(p) for p in args.pages.split(',')} if args.pages else None
    if args.batch_size is not None:
        if not 1 <= args.batch_size <= 100:
            parser.error('batch size must be 1..100')
        settings.EMBEDDING_BATCH_SIZE = args.batch_size
    if args.action in ('probe', 'resume', 'recover', 'authorize-provider') and args.document_id is None:
        parser.error('--document-id is required')
    if args.action == 'authorize-provider' and not (args.authorization_note or '').strip():
        parser.error('--authorization-note must identify explicit prior human approval')
    failed = False
    with SessionLocal() as db:
        docs = db.query(Document).order_by(Document.id)
        if args.document_id is not None:
            docs = docs.filter_by(id=args.document_id)
        docs = docs.all()
        if not docs:
            parser.error('No matching documents')
        for doc in docs:
            print(json.dumps({"before": report(doc)}), flush=True)
            if args.action in ('probe', 'resume') and doc.subject not in SUPPORTED_LANGUAGES:
                failed = True
                print(json.dumps({'document_id': doc.id, 'error': 'Outside C, C++, Java, and Python scope; existing data retained.'}), flush=True)
                continue
            if args.action == 'probe' and not provider_use_allowed(doc):
                failed = True
                print(json.dumps({'document_id': doc.id, 'error': 'Google use is awaiting permission; no book text was sent.'}), flush=True)
                continue
            if args.action == 'authorize-provider':
                print(json.dumps({'authorization': authorize_provider_use(db, doc, args.authorization_note)}), flush=True)
            elif args.action == 'probe':
                try:
                    texts = [c.content for c in sorted(doc.chunks, key=lambda c: c.chunk_index)[:args.max_chunks]]
                    vectors = embedding_service.generate_embeddings_batch(texts)
                    print(json.dumps({"probe": "embedding_batch", "chunks": len(vectors), "dimensions": settings.EMBEDDING_DIMENSIONS, "persisted": False}), flush=True)
                except Exception as exc:
                    failed = True
                    print(json.dumps({"probe": "embedding_batch", "error_type": type(exc).__name__, "code": getattr(exc, 'code', None)}), flush=True)
            elif args.action == 'recover':
                if doc.status == 'processing':
                    doc.status = 'partial' if doc.chunks else 'pending'
                    doc.error_message = 'Interrupted indexing unlocked manually; resume to continue.'
                    db.commit()
            elif args.action == 'reconcile':
                coverage = index_coverage(doc)
                if doc.status in ('ready', 'partial') and doc.chunks:
                    doc.status = 'ready' if coverage['semantic_ready'] else 'partial'
                    doc.error_message = None if coverage['semantic_ready'] else f"{coverage['embedded_chunks']}/{coverage['total_chunks']} compatible embeddings. Resume processing to continue."
                    db.commit()
            elif args.action == 'resume':
                try:
                    from app.services.index_service import process_document
                    if not args.pace_seconds:
                        process_document(db, doc.id, max_chunks=args.max_chunks, reuse_existing_text=args.reuse_existing_text, page_numbers=pages)
                    else:
                        remaining = args.max_chunks
                        while remaining > 0:
                            before = index_coverage(doc)['embedded_chunks']
                            process_document(db, doc.id, max_chunks=min(remaining, settings.EMBEDDING_BATCH_SIZE), reuse_existing_text=args.reuse_existing_text, page_numbers=pages)
                            db.expire_all()
                            coverage = index_coverage(doc)
                            saved = coverage['embedded_chunks'] - before
                            remaining -= saved
                            print(json.dumps({'document_id': doc.id, 'saved': coverage['embedded_chunks'], 'total': coverage['total_chunks'], 'status': doc.status}), flush=True)
                            if coverage['semantic_ready'] or saved <= 0 or remaining <= 0:
                                break
                            # End read transactions during the pause so other requests can write.
                            db.commit()
                            time.sleep(args.pace_seconds)
                except Exception as exc:
                    failed = True
                    print(json.dumps(provider_failure(exc)), flush=True)
            if args.action not in ('report', 'probe'):
                db.expire_all()
                print(json.dumps({"after": report(doc)}), flush=True)
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
