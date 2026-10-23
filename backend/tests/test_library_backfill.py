"""A provider stop must preserve saved progress and prevent further sends."""
import json
import sys
from types import SimpleNamespace

import index_library


def setup_job(monkeypatch, tmp_path, failure=None):
    docs = {ident: SimpleNamespace(id=ident, subject=language, status='partial',
        chunks=[SimpleNamespace(page_number=1, saved=False), SimpleNamespace(page_number=2, saved=False)])
        for ident, language in [(5, 'C'), (6, 'C++')]}
    class DB:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def query(self, *args): return self
        def filter(self, *args): return self
        def all(self): return list(docs.values())
        def get(self, model, ident): return docs[ident]
        def expire_all(self): pass
    def progress(doc):
        count = sum(chunk.saved for chunk in doc.chunks)
        return {'embedded_chunks': count, 'total_chunks': 2, 'semantic_ready': count == 2}
    calls = []
    def process(db, ident, max_chunks, **kwargs):
        calls.append(ident)
        if failure and len(calls) == 2:
            raise failure
        for chunk in docs[ident].chunks:
            if not chunk.saved and max_chunks > 0:
                chunk.saved = True
                max_chunks -= 1
        docs[ident].total_chunks = 2
    output = tmp_path / 'progress.json'
    monkeypatch.setattr(index_library.settings, 'EMBEDDING_BATCH_SIZE', index_library.settings.EMBEDDING_BATCH_SIZE)
    monkeypatch.setattr(index_library, 'SessionLocal', DB)
    monkeypatch.setattr(index_library, 'provider_use_allowed', lambda doc: True)
    monkeypatch.setattr(index_library, 'index_coverage', progress)
    monkeypatch.setattr(index_library, 'coverage', lambda ids: [dict(document_id=ident, **progress(docs[ident])) for ident in ids])
    monkeypatch.setattr(index_library, 'process_document', process)
    monkeypatch.setattr(index_library.embedding_service, 'is_configured', lambda: True)
    monkeypatch.setattr(index_library.embedding_service, 'compatible_vector', lambda chunk: [1] if chunk.saved else None)
    monkeypatch.setattr(sys, 'argv', ['index_library.py', '--document-ids', '5', '6',
        '--max-new-chunks', '4', '--batch-size', '1', '--pace-seconds', '0', '--output', str(output)])
    return docs, calls, output


def test_round_robin_stops_when_both_books_are_complete(monkeypatch, tmp_path):
    docs, calls, output = setup_job(monkeypatch, tmp_path)
    assert index_library.main() == 0
    assert calls == [5, 6, 5, 6]
    report = json.loads(output.read_text())
    assert report['state'] == 'complete' and report['new_embeddings_saved'] == 4
    assert all(book['semantic_ready'] for book in report['current'])


def test_quota_stops_all_further_calls_and_keeps_first_commit(monkeypatch, tmp_path):
    class Quota(Exception): code = 429
    docs, calls, output = setup_job(monkeypatch, tmp_path, failure=Quota())
    assert index_library.main() == 1
    report = json.loads(output.read_text())
    assert calls == [5, 6]
    assert report['state'] == 'quota_reached' and report['new_embeddings_saved'] == 1
    assert docs[5].chunks[0].saved and not any(chunk.saved for chunk in docs[6].chunks)


def test_stop_file_prevents_any_provider_work(monkeypatch, tmp_path):
    docs, calls, output = setup_job(monkeypatch, tmp_path)
    stop = tmp_path / 'stop'
    stop.touch()
    monkeypatch.setattr(sys, 'argv', sys.argv + ['--stop-file', str(stop)])
    assert index_library.main() == 1 and calls == []
    assert json.loads(output.read_text())['state'] == 'stopped_by_control_file'
