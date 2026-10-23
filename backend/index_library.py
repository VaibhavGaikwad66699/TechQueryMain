"""Paced round-robin backfill of an explicitly selected, approved book library."""
import argparse
import json
from pathlib import Path
import time

from app.core.config import settings
from app.core.scope import SUPPORTED_LANGUAGES
from app.database.session import SessionLocal
from app.models.document import Document
from app.services.embedding_service import embedding_service, provider_failure
from app.services.index_service import process_document, index_coverage
from app.services.provider_access import provider_use_allowed


def coverage(ids):
    with SessionLocal() as db:
        return [{'document_id': doc.id, 'language': doc.subject, 'status': doc.status,
            **index_coverage(doc)} for doc in db.query(Document).filter(Document.id.in_(ids)).order_by(Document.id)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--document-ids', nargs='+', type=int, required=True)
    parser.add_argument('--max-new-chunks', type=int, required=True)
    parser.add_argument('--batch-size', type=int, default=16)
    parser.add_argument('--pace-seconds', type=float, default=14)
    parser.add_argument('--priority-pages', type=Path, help='JSON mapping document IDs to physical page lists')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--stop-file', type=Path)
    args = parser.parse_args()
    ids = list(dict.fromkeys(args.document_ids))
    if args.max_new_chunks < 1 or not 1 <= args.batch_size <= 100 or not 0 <= args.pace_seconds <= 60:
        parser.error('Use a positive chunk budget, batch size 1..100, and pace 0..60 seconds')
    settings.EMBEDDING_BATCH_SIZE = args.batch_size
    if not embedding_service.is_configured():
        parser.error('Gemini must be configured')
    with SessionLocal() as db:
        docs = db.query(Document).filter(Document.id.in_(ids)).all()
        if len(docs) != len(ids) or any(doc.subject not in SUPPORTED_LANGUAGES or not doc.chunks or
                not provider_use_allowed(doc) or doc.status == 'processing' for doc in docs):
            parser.error('Every selected book must exist, have saved text, be approved, and have no active processing')
    priorities = json.loads(args.priority_pages.read_text()) if args.priority_pages else {}
    result = {'state': 'running', 'new_embeddings_saved': 0, 'initial': coverage(ids),
        'batch_size': args.batch_size, 'pace_seconds': args.pace_seconds,
        'batches': [], 'billing_changed': False}
    started = time.perf_counter()
    def checkpoint():
        result['current'] = coverage(ids)
        result['elapsed_seconds'] = round(time.perf_counter() - started, 3)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    def batch(ident, pages=None):
        if args.stop_file and args.stop_file.exists():
            result['state'] = 'stopped_by_control_file'
            return False
        with SessionLocal() as db:
            doc = db.get(Document, ident)
            pending = [chunk for chunk in doc.chunks if embedding_service.compatible_vector(chunk) is None
                and (not pages or chunk.page_number in pages)]
            if not pending:
                return None
            before = index_coverage(doc)['embedded_chunks']
            try:
                process_document(db, ident, max_chunks=min(args.batch_size,
                    args.max_new_chunks - result['new_embeddings_saved']),
                    reuse_existing_text=True, page_numbers=pages)
            except Exception as exc:
                db.expire_all()
                saved = index_coverage(doc)['embedded_chunks'] - before
                result['new_embeddings_saved'] += saved
                result['failure'] = {'document_id': ident, **provider_failure(exc)}
                result['state'] = 'quota_reached' if getattr(exc, 'code', None) == 429 else 'provider_or_index_failure'
                print(json.dumps({'state': result['state'], **result['failure']}), flush=True)
                return False
            db.expire_all()
            count = index_coverage(doc)['embedded_chunks']
            saved = count - before
            if saved <= 0:
                result['state'] = 'no_progress'
                return False
            result['new_embeddings_saved'] += saved
            event = {'document_id': ident, 'language': doc.subject, 'saved': saved,
                'embedded': count, 'total': doc.total_chunks,
                'new_embeddings_saved': result['new_embeddings_saved']}
            if pages:
                event['priority_pages'] = sorted(pages)
            result['batches'].append(event)
            print(json.dumps(event), flush=True)
        checkpoint()
        if result['new_embeddings_saved'] < args.max_new_chunks:
            time.sleep(args.pace_seconds)
        return True
    checkpoint()
    for ident in ids:
        pages = {int(page) for page in priorities.get(str(ident), [])}
        if pages:
            while result['new_embeddings_saved'] < args.max_new_chunks:
                progress = batch(ident, pages)
                if progress is False:
                    checkpoint()
                    return 1
                if progress is None:
                    break
    while result['new_embeddings_saved'] < args.max_new_chunks:
        made_progress = False
        for ident in ids:
            if result['new_embeddings_saved'] >= args.max_new_chunks:
                break
            progress = batch(ident)
            if progress is False:
                checkpoint()
                return 1
            made_progress |= progress is True
        if not made_progress:
            result['state'] = 'complete'
            break
    if result['state'] == 'running':
        result['state'] = 'complete' if all(book['semantic_ready'] for book in coverage(ids)) else 'budget_reached'
    checkpoint()
    print(json.dumps({key: result[key] for key in ('state', 'new_embeddings_saved', 'current', 'elapsed_seconds')}), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
