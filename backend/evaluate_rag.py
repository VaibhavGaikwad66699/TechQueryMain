"""Repeatable retrieval/page checks on the actual book. Generation checks do not prove faithfulness."""
import argparse
import json
import re
from pathlib import Path
import pypdf
from app.database.session import SessionLocal
from app.models.document import Document, DocumentChunk
from app.services.embedding_service import embedding_service
from app.services.index_service import index_coverage
from app.services.rag_service import rag_service
from app.services.storage_service import storage_service
from app.core.config import settings
from app.services.pdf_verification import normalized_passage_in_page, fresh_pdftotext_page


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=['lexical', 'auto', 'semantic'], default='lexical')
    parser.add_argument('--generate', action='store_true', help='Makes live generation calls when configured')
    parser.add_argument('--case-id', action='append', default=[])
    parser.add_argument('--output', type=Path)
    parser.add_argument('--scope-pages', help='Optional sampled physical pages; does not measure full-book retrieval')
    parser.add_argument('--pdftotext', help='Optional local executable for a fresh page check when pypdf reading order differs')
    parser.add_argument('--generation-model', help='Temporary generation model override for evaluation only')
    parser.add_argument('--dataset', type=Path, default=Path(__file__).parent / 'evaluation/java_book.json', help='Frozen question/evidence dataset; defaults to the original smoke set')
    args = parser.parse_args()
    if args.generation_model:
        settings.GEMINI_MODEL = args.generation_model
    dataset = json.loads(args.dataset.read_text(encoding='utf-8'))
    output = {'mode': args.mode, 'dataset': args.dataset.name,
        'generation_model': settings.GEMINI_MODEL if args.generate else None,
        'generation_timeout_ms': settings.GENERATION_TIMEOUT_MS if args.generate else None,
        'cases': [], 'limitations': 'Small release smoke set. Citation/page checks do not establish claim faithfulness. Human review of generated answers is required.'}
    with SessionLocal() as db:
        doc = db.query(Document).filter_by(title=dataset['book_title']).first()
        if doc is None:
            parser.error('Source book not found')
        output['coverage'] = index_coverage(doc)
        pdf = pypdf.PdfReader(storage_service.get_file_path(doc.filename))
        page_text, alternate_page_text = {}, {}
        rows = db.query(DocumentChunk, Document.title).join(Document).filter(Document.id == doc.id).order_by(DocumentChunk.id).all()
        if args.scope_pages:
            pages = {int(p) for p in args.scope_pages.split(',')}
            rows = [(c, t) for c, t in rows if c.page_number in pages]
            output['scope'] = {'type': 'sampled_pages', 'pages': sorted(pages), 'chunks': len(rows), 'note': 'Live pipeline smoke test only; not a full-book retrieval result'}
        else:
            output['scope'] = {'type': 'full_book', 'chunks': len(rows)}
        if args.mode == 'semantic' and (not rows or any(embedding_service.compatible_vector(c) is None for c, _ in rows)):
            parser.error('Semantic evaluation requires compatible embeddings for every chunk in the selected scope')
        # Limit the evaluated corpus to this book without altering application data.
        original_rows = rag_service._rows
        rag_service._rows = lambda *unused: rows
        try:
            for case in dataset['cases']:
                if args.case_id and case['id'] not in args.case_id:
                    continue
                sources = (rag_service._fallback_keyword_search(db, case['question'], rows=rows)
                    if args.mode == 'lexical' else rag_service.retrieve_relevant_chunks(db, case['question']))
                supported = bool(case['pages'])
                hit = any(s.page_number in case['pages'] and all(
                    term.lower() in db.query(DocumentChunk).filter_by(document_id=s.document_id, chunk_index=s.chunk_index).one().content.lower()
                    for term in case['evidence_terms']) for s in sources) if supported else not sources
                citation_valid, page_verified = True, True
                verification_methods = []
                for source in sources:
                    chunk = next((c for c, _ in rows if c.document_id == source.document_id and c.chunk_index == source.chunk_index and c.page_number == source.page_number), None)
                    if chunk is None or not 1 <= source.page_number <= len(pdf.pages):
                        citation_valid = False
                        page_verified = False
                        continue
                    if source.page_number not in page_text:
                        page_text[source.page_number] = re.sub(r'\s+', ' ', pdf.pages[source.page_number - 1].extract_text() or '').strip()
                    if normalized_passage_in_page(chunk.content, page_text[source.page_number]):
                        verification_methods.append('pypdf_exact_normalized')
                    elif args.pdftotext:
                        if source.page_number not in alternate_page_text:
                            alternate_page_text[source.page_number] = fresh_pdftotext_page(
                                storage_service.get_file_path(doc.filename), source.page_number, args.pdftotext)
                        if normalized_passage_in_page(chunk.content, alternate_page_text[source.page_number]):
                            verification_methods.append('fresh_pdftotext_exact_normalized')
                        else:
                            page_verified = False
                    else:
                        page_verified = False
                result = {'id': case['id'], 'question': case['question'], 'expected_fact': case['expected_fact'],
                    'retrieval_pass': hit, 'citation_metadata_valid': citation_valid, 'original_pdf_page_verified': page_verified,
                    'page_verification_methods': verification_methods,
                    'pages': [s.page_number for s in sources], 'methods': [s.retrieval_method for s in sources]}
                result['scores'] = [s.similarity_score for s in sources]
                if args.generate:
                    answer = rag_service.generate_answer_result(case['question'], sources, db, {'answer_style': 'Concise', 'explanation_level': 'Intermediate', 'include_examples': False})
                    result.update(answer.model_dump())
                    result['expected_abstention_pass'] = answer.abstained if not supported else not answer.abstained
                    result['generation_pass'] = answer.response_mode == 'generated' if supported else answer.abstained
                output['cases'].append(result)
                print(json.dumps(result, ensure_ascii=True), flush=True)
        finally:
            rag_service._rows = original_rows
    output['retrieval_passed'] = sum(c['retrieval_pass'] for c in output['cases'])
    output['total'] = len(output['cases'])
    if args.generate:
        output['generation_passed'] = sum(c['generation_pass'] for c in output['cases'])
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(output, indent=2, ensure_ascii=True), encoding='utf-8')
    print(json.dumps({'retrieval_passed': output['retrieval_passed'], 'total': output['total']}), flush=True)
    return 0 if output['cases'] and all(c['retrieval_pass'] and c['citation_metadata_valid'] and
        c['original_pdf_page_verified'] and c.get('generation_pass', True) for c in output['cases']) else 1


if __name__ == '__main__':
    raise SystemExit(main())
