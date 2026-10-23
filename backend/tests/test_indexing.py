import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from app.core.config import Settings, settings
from app.models.document import Document, DocumentChunk
from app.services.embedding_service import EmbeddingService, embedding_service
from app.services.index_service import index_coverage, IndexingInProgress
from app.services.index_service import process_document
from app.services.rag_service import rag_service
from app.services.storage_service import storage_service
from seed_sample_docs import make_simple_pdf


def vector():
    return [1.0] + [0.0] * (settings.EMBEDDING_DIMENSIONS - 1)


def create_book(db):
    path = storage_service.base_dir / 'test.pdf'
    make_simple_pdf([
        ['Interfaces specify a contract that implementing classes must satisfy.'],
        ['Virtual memory allows a program to use more memory than physical RAM.'],
        ['Normalization reduces duplication and prevents update anomalies.'],
    ], path)
    doc = Document(title='Test', filename='test.pdf', original_filename='test.pdf', subject='Java', status='pending')
    db.add(doc)
    db.commit()
    return doc


def test_partial_batch_survives_failure_and_resume(db_session, monkeypatch):
    doc = create_book(db_session)
    monkeypatch.setattr(embedding_service, 'is_configured', lambda: True)
    monkeypatch.setattr(settings, 'EMBEDDING_BATCH_SIZE', 1)
    call = Mock(side_effect=[[vector()], RuntimeError('provider unavailable')])
    monkeypatch.setattr(embedding_service, 'generate_embeddings_batch', call)
    with pytest.raises(RuntimeError):
        rag_service.process_document(db_session, doc.id, max_chunks=3)
    assert doc.status == 'partial'
    assert index_coverage(doc)['embedded_chunks'] == 1
    original_ids = [c.id for c in doc.chunks]
    call = Mock(side_effect=lambda texts: [vector() for _ in texts])
    monkeypatch.setattr(embedding_service, 'generate_embeddings_batch', call)
    rag_service.process_document(db_session, doc.id, max_chunks=3)
    assert doc.status == 'ready'
    assert index_coverage(doc)['embedded_chunks'] == 3
    assert call.call_count == 2  # first successful batch was reused
    assert [c.id for c in doc.chunks] == original_ids
    call.reset_mock()
    rag_service.process_document(db_session, doc.id, max_chunks=3)
    call.assert_not_called()
    assert len(doc.chunks) == 3


def test_text_only_is_partial_and_budget_is_respected(db_session, monkeypatch):
    doc = create_book(db_session)
    rag_service.process_document(db_session, doc.id)
    assert doc.status == 'partial'
    assert index_coverage(doc)['missing_embeddings'] == 3
    monkeypatch.setattr(embedding_service, 'is_configured', lambda: True)
    monkeypatch.setattr(embedding_service, 'generate_embeddings_batch', lambda texts: [vector() for _ in texts])
    rag_service.process_document(db_session, doc.id, max_chunks=1)
    assert doc.status == 'partial'
    assert index_coverage(doc)['embedded_chunks'] == 1


def test_unknown_model_task_dimension_content_are_not_reused():
    chunk = SimpleNamespace(content='Original', embedding_json=json.dumps(vector()), metadata_json='{}')
    assert embedding_service.compatible_vector(chunk) is None
    chunk.metadata_json = json.dumps({'embedding': embedding_service.provenance(chunk.content)})
    assert embedding_service.compatible_vector(chunk) is not None
    chunk.content = 'Changed'
    assert embedding_service.compatible_vector(chunk) is None
    chunk.content = 'Original'
    chunk.embedding_json = '[1,2,3]'
    assert embedding_service.compatible_vector(chunk) is None
    meta = embedding_service.provenance(chunk.content)
    meta['model'] = 'different-model'
    chunk.metadata_json = json.dumps({'embedding': meta})
    assert embedding_service.compatible_vector(chunk) is None


def test_concurrent_processing_is_rejected(db_session):
    doc = create_book(db_session)
    doc.status = 'processing'
    db_session.commit()
    with pytest.raises(IndexingInProgress):
        rag_service.process_document(db_session, doc.id)


def test_extraction_failure_preserves_existing_chunks(db_session, monkeypatch):
    doc = create_book(db_session)
    rag_service.process_document(db_session, doc.id)
    ids = [c.id for c in doc.chunks]
    (storage_service.base_dir / 'test.pdf').write_bytes(b'broken PDF')
    with pytest.raises(Exception):
        rag_service.process_document(db_session, doc.id)
    assert [c.id for c in doc.chunks] == ids
    assert doc.status == 'error'  # keep data for recovery, but do not serve stale citations


def test_retry_only_transient_failures(monkeypatch):
    class Transient(Exception):
        code = 503
    service = EmbeddingService()
    mock = Mock(side_effect=[Transient(), SimpleNamespace(embeddings=[SimpleNamespace(values=vector())])])
    monkeypatch.setattr(service, '_get_client', lambda: SimpleNamespace(models=SimpleNamespace(embed_content=mock)))
    monkeypatch.setattr('app.services.embedding_service.time.sleep', lambda seconds: None)
    assert service.generate_embeddings_batch(['text']) == [vector()]
    assert mock.call_count == 2
    assert mock.call_args.kwargs['config'].task_type == 'RETRIEVAL_DOCUMENT'
    mock.side_effect = None
    mock.return_value = SimpleNamespace(embeddings=[SimpleNamespace(values=vector())])
    service.generate_embedding('question')
    assert mock.call_args.kwargs['config'].task_type == 'RETRIEVAL_QUERY'


@pytest.mark.parametrize('vectors', [[], [[1.0]], [[float('nan')] * 768]])
def test_malformed_embeddings_are_rejected(monkeypatch, vectors):
    service = EmbeddingService()
    mock = Mock(return_value=SimpleNamespace(embeddings=[SimpleNamespace(values=v) for v in vectors]))
    monkeypatch.setattr(service, '_get_client', lambda: SimpleNamespace(models=SimpleNamespace(embed_content=mock)))
    with pytest.raises(ValueError):
        service.generate_embeddings_batch(['text'])
    assert mock.call_count == 1


def test_database_paths_are_honored(tmp_path):
    assert Settings(_env_file=None, DATABASE_URL='sqlite:///:memory:').sync_database_url == 'sqlite:///:memory:'
    url = 'sqlite:///' + (tmp_path / 'separate.db').as_posix()
    assert Settings(_env_file=None, DATABASE_URL=url).sync_database_url == url


def test_changed_pdf_replaces_chunks_without_reusing_stale_vectors(db_session, monkeypatch):
    doc = create_book(db_session)
    monkeypatch.setattr(embedding_service, 'is_configured', lambda: True)
    monkeypatch.setattr(embedding_service, 'generate_embeddings_batch', lambda texts: [vector() for _ in texts])
    rag_service.process_document(db_session, doc.id, max_chunks=3)
    make_simple_pdf([['A replacement chapter discusses resource management and closing streams safely.']], storage_service.base_dir / 'test.pdf')
    rag_service.process_document(db_session, doc.id, max_chunks=0)
    assert len(doc.chunks) == 1
    assert 'replacement' in doc.chunks[0].content
    assert index_coverage(doc)['embedded_chunks'] == 0
    assert doc.status == 'partial'


def test_explicit_legacy_backfill_preserves_text_and_records_origin(db_session, monkeypatch):
    doc = create_book(db_session)
    rag_service.process_document(db_session, doc.id)
    ids = [c.id for c in doc.chunks]
    for chunk in doc.chunks:
        chunk.metadata_json = json.dumps({'page': chunk.page_number})
    db_session.commit()
    monkeypatch.setattr('app.services.pdf_service.pdf_service.extract_and_chunk', Mock(side_effect=AssertionError('Legacy backfill must not re-extract')))
    monkeypatch.setattr(embedding_service, 'is_configured', lambda: True)
    monkeypatch.setattr(embedding_service, 'generate_embeddings_batch', lambda texts: [vector() for _ in texts])
    process_document(db_session, doc.id, max_chunks=3, reuse_existing_text=True)
    assert [c.id for c in doc.chunks] == ids
    assert index_coverage(doc)['legacy_text_chunks'] == 3
    assert doc.status == 'ready'
    (storage_service.base_dir / 'test.pdf').write_bytes(b'different file')
    with pytest.raises(ValueError, match='PDF changed'):
        process_document(db_session, doc.id, max_chunks=3, reuse_existing_text=True)
    assert doc.status == 'error'


def test_targeted_backfill_keeps_full_document_partial(db_session, monkeypatch):
    doc = create_book(db_session)
    rag_service.process_document(db_session, doc.id)
    monkeypatch.setattr(embedding_service, 'is_configured', lambda: True)
    monkeypatch.setattr(embedding_service, 'generate_embeddings_batch', lambda texts: [vector() for _ in texts])
    process_document(db_session, doc.id, max_chunks=10, page_numbers={2})
    assert [c.page_number for c in doc.chunks if embedding_service.compatible_vector(c) is not None] == [2]
    assert index_coverage(doc)['missing_embeddings'] == 2
    assert doc.status == 'partial'


def test_daily_quota_does_not_trigger_futile_retries(monkeypatch):
    class QuotaError(Exception):
        code = 429
        status = 'RESOURCE_EXHAUSTED'
        details = {'error': {'details': [{'@type': 'type.googleapis.com/google.rpc.RetryInfo', 'retryDelay': '38945s'}]}}
    service = EmbeddingService()
    mock = Mock(side_effect=QuotaError())
    monkeypatch.setattr(service, '_get_client', lambda: SimpleNamespace(models=SimpleNamespace(embed_content=mock)))
    with pytest.raises(QuotaError):
        service.generate_embeddings_batch(['text'])
    assert mock.call_count == 1
