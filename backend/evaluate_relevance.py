"""Read-only cross-book relevance checks, with original-page and manual-review evidence."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import time

import pypdf
from app.core.config import settings
from app.database.session import SessionLocal
from app.models.document import Document, DocumentChunk
from app.services.pdf_verification import fresh_pdftotext_page, normalized_passage_in_page
from app.services.rag_service import rag_service, source_key
from app.services.storage_service import storage_service


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', type=Path, default=Path(__file__).parent / 'evaluation/relevance_release.json')
    parser.add_argument('--mode', choices=['lexical', 'auto'], default='lexical')
    parser.add_argument('--generate', action='store_true')
    parser.add_argument('--case-id', action='append', default=[])
    parser.add_argument('--pdftotext')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--max-provider-failures', type=int, default=3)
    args = parser.parse_args()
    configured_key = settings.GEMINI_API_KEY
    cases = json.loads(args.dataset.read_text(encoding='utf-8'))['cases']
    output = {'checked_at': datetime.now(timezone.utc).isoformat(), 'mode': args.mode,
        'generation_model': settings.GEMINI_MODEL, 'embedding_model': settings.EMBEDDING_MODEL,
        'generation_timeout_ms': settings.GENERATION_TIMEOUT_MS,
        'generation_max_attempts': settings.GENERATION_MAX_ATTEMPTS,
        'index_modified': False, 'cases': [],
        'limitation': 'Small smoke set. A generated answer with valid citations is not a correctness pass. Review expected facts, actual answer and cited page text.'}
    failures, readers, pages = 0, {}, {}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with SessionLocal() as db:
        books = {doc.id: doc for doc in db.query(Document).filter_by(is_default=True).all()}
        for case in cases:
            if args.case_id and case['id'] not in args.case_id:
                continue
            started = time.perf_counter()
            settings.GEMINI_API_KEY = configured_key if args.mode == 'auto' else ''
            sources = rag_service.retrieve_relevant_chunks(db, case['question'], case['subject'])
            result = {**case, 'retrieved_sources': [source.model_dump() for source in sources]}
            if args.generate and failures < args.max_provider_failures:
                settings.GEMINI_API_KEY = configured_key
                answer = rag_service.generate_answer_result(case['question'], sources, db,
                    case.get('preferences', {'answer_style': 'Concise', 'explanation_level': 'Beginner', 'include_examples': False}), subject=case['subject'])
                result.update(answer.model_dump())
                if case['supported_expected']:
                    failures = failures + 1 if answer.response_mode == 'source_excerpts' else 0
                if answer.cited_source_keys:
                    sources = [source for source in sources if source_key(source) in answer.cited_source_keys]
            elif args.generate:
                result['generation_skipped'] = 'Stopped after consecutive provider fallbacks.'
            checks = []
            for source in sources:
                doc = books.get(source.document_id)
                chunk = db.query(DocumentChunk).filter_by(document_id=source.document_id, chunk_index=source.chunk_index).first()
                valid = bool(doc and chunk and doc.id == source.document_id and source.page_number == chunk.page_number
                    and doc.subject == case.get('expected_source_subject', doc.subject if case['subject'] == 'All' else case['subject'])
                    and 1 <= source.page_number <= doc.total_pages)
                method, text = None, ''
                if valid:
                    page_key = (doc.id, source.page_number)
                    if page_key not in pages:
                        path = storage_service.get_file_path(doc.filename)
                        pages[page_key] = {}
                        if args.pdftotext:
                            pages[page_key]['fresh_pdftotext_exact_normalized'] = fresh_pdftotext_page(path, source.page_number, args.pdftotext)
                    variants = pages[page_key]
                    if not any(normalized_passage_in_page(chunk.content, value) for value in variants.values()):
                        if 'pypdf_exact_normalized' not in variants:
                            if doc.id not in readers:
                                readers[doc.id] = pypdf.PdfReader(storage_service.get_file_path(doc.filename))
                            variants['pypdf_exact_normalized'] = readers[doc.id].pages[source.page_number - 1].extract_text() or ''
                    # Match each chunk independently; different chunks on the
                    # same physical page can require different reading orders.
                    method, text = next(((name, value) for name, value in variants.items()
                        if normalized_passage_in_page(chunk.content, value)), (None, ''))
                checks.append({'document_id': source.document_id, 'chunk_index': source.chunk_index,
                    'physical_page': source.page_number, 'metadata_valid': valid,
                    'original_page_verified': bool(valid and normalized_passage_in_page(chunk.content, text)), 'method': method})
            result.update(sources=[source.model_dump() for source in sources], page_checks=checks,
                elapsed_seconds=round(time.perf_counter() - started, 3))
            output['cases'].append(result)
            args.output.write_text(json.dumps(output, indent=2), encoding='utf-8')
            print(json.dumps({'id': case['id'], 'mode': result.get('response_mode', 'retrieval_only'),
                'pages': [source.page_number for source in sources], 'page_checks_passed': all(check['original_page_verified'] for check in checks)}, ensure_ascii=True), flush=True)
    settings.GEMINI_API_KEY = configured_key
    output['total'] = len(output['cases'])
    output['generated'] = sum(case.get('response_mode') == 'generated' for case in output['cases'])
    output['abstained'] = sum(case.get('abstained', False) for case in output['cases'])
    output['provider_fallbacks'] = sum(case.get('response_mode') == 'source_excerpts' for case in output['cases'])
    args.output.write_text(json.dumps(output, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
