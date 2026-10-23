from unittest.mock import Mock
import json

import pytest
from app.models.document import Document, DocumentChunk
from app.services.embedding_service import embedding_service
from app.services.index_service import process_document, index_coverage
from app.services.provider_access import provider_use_allowed, authorize_provider_use
from app.services.source_book_service import ExtractedBook, import_source_book, split_physical_pages, file_sha256
from app.services.storage_service import storage_service
from seed_sample_docs import make_simple_pdf


PAGES = [
    'C pointers store memory addresses and use the indirection operator to access an object.',
    'C arrays store contiguous elements. Array indexes begin at zero and must stay within bounds.',
]


def source_pdf(tmp_path):
    folder = tmp_path / 'source'
    folder.mkdir(exist_ok=True)
    path = folder / 'book.pdf'
    make_simple_pdf([[text] for text in PAGES], path)
    return path


def local_extractor(*args, **kwargs):
    return ExtractedBook(list(PAGES), 'test local extractor', 0.01)


def test_import_is_local_only_idempotent_and_preserves_source(db_session, tmp_path, monkeypatch):
    source = source_pdf(tmp_path)
    digest = file_sha256(source)
    forbidden = Mock(side_effect=AssertionError('No Google calls during local import'))
    monkeypatch.setattr('google.genai.Client', forbidden)
    monkeypatch.setattr(embedding_service, 'generate_embeddings_batch', forbidden)
    result = import_source_book(db_session, source, 'C', extractor=local_extractor)
    doc = db_session.get(Document, result['document_id'])
    assert doc.status == 'partial' and doc.total_pages == 2 and doc.total_chunks == 2
    assert [chunk.page_number for chunk in doc.chunks] == [1, 2]
    assert all(chunk.embedding_json is None for chunk in doc.chunks)
    assert not provider_use_allowed(doc)
    assert index_coverage(doc)['provider_use_allowed'] is False
    assert file_sha256(source) == file_sha256(storage_service.get_file_path(doc.filename)) == digest
    ids = [chunk.id for chunk in doc.chunks]
    repeat = import_source_book(db_session, source, 'C', extractor=forbidden)
    assert repeat['action'] == 'preserved_existing' and repeat['document_id'] == doc.id
    assert [chunk.id for chunk in doc.chunks] == ids
    assert db_session.query(Document).count() == 1
    forbidden.assert_not_called()


def test_import_failure_leaves_no_record_or_storage_copy(db_session, tmp_path):
    source = source_pdf(tmp_path)
    def failed(*args, **kwargs):
        raise TimeoutError('bounded extraction failed')
    with pytest.raises(TimeoutError):
        import_source_book(db_session, source, 'C', extractor=failed)
    assert db_session.query(Document).count() == 0
    assert not list(storage_service.base_dir.glob('*_book.pdf'))
    assert source.is_file()


def test_database_failure_removes_only_new_copy(db_session, tmp_path, monkeypatch):
    source = source_pdf(tmp_path)
    preserved = storage_service.base_dir / 'preserved.pdf'
    preserved.write_bytes(b'original bytes')
    with monkeypatch.context() as patch:
        patch.setattr(db_session, 'commit', Mock(side_effect=RuntimeError('database unavailable')))
        with pytest.raises(RuntimeError, match='database unavailable'):
            import_source_book(db_session, source, 'C', extractor=local_extractor)
    assert db_session.query(Document).count() == 0
    assert preserved.read_bytes() == b'original bytes' and source.is_file()
    assert not list(storage_service.base_dir.glob('*_book.pdf'))


def test_import_detects_source_changes_before_copy(db_session, tmp_path):
    source = source_pdf(tmp_path)
    def changing(path, *args, **kwargs):
        path.write_bytes(path.read_bytes() + b'changed')
        return local_extractor()
    with pytest.raises(ValueError, match='Source changed'):
        import_source_book(db_session, source, 'C', extractor=changing)
    assert db_session.query(Document).count() == 0
    assert not list(storage_service.base_dir.glob('*_book.pdf'))


@pytest.mark.parametrize('pages', [[], ['only one page'], ['', '']])
def test_incomplete_or_empty_extraction_is_not_registered(db_session, tmp_path, pages):
    with pytest.raises(ValueError):
        import_source_book(db_session, source_pdf(tmp_path), 'C',
            extractor=lambda *args, **kwargs: ExtractedBook(pages, 'fixture', 0))
    assert db_session.query(Document).count() == 0


def test_blank_physical_pages_keep_their_positions():
    assert split_physical_pages('one\f\ftwo\f', 3) == ['one', '', 'two']
    with pytest.raises(ValueError, match='page count mismatch'):
        split_physical_pages('one\ftwo\f', 3)


def test_wrong_language_duplicate_is_preserved_without_relabeling(db_session, tmp_path):
    source = source_pdf(tmp_path)
    result = import_source_book(db_session, source, 'C', extractor=local_extractor)
    with pytest.raises(ValueError, match='different language'):
        import_source_book(db_session, source, 'Python', extractor=local_extractor)
    assert db_session.get(Document, result['document_id']).subject == 'C'


def test_local_book_queries_and_processing_cannot_send_text_to_google(client, db_session, tmp_path, monkeypatch):
    result = import_source_book(db_session, source_pdf(tmp_path), 'C', extractor=local_extractor)
    doc = db_session.get(Document, result['document_id'])
    doc.is_default = True  # Explicit shared fixture; generic operator imports are private/unpublished by default.
    db_session.commit()
    provider = Mock(side_effect=AssertionError('Imported book is not authorized for Google'))
    monkeypatch.setattr(embedding_service, 'is_configured', lambda: True)
    monkeypatch.setattr(embedding_service, 'generate_embeddings_batch', provider)
    monkeypatch.setattr(embedding_service, 'generate_embedding', provider)
    monkeypatch.setattr('google.genai.Client', provider)
    auth = client.post('/api/v1/auth/register', json={
        'email': 'local@example.com', 'username': 'LocalUser', 'password': 'Password123!'}).json()
    headers = {'Authorization': 'Bearer ' + auth['access_token']}
    for login in ({}, headers):
        data = client.post('/api/v1/query', headers=login,
            json={'question': 'How do C pointers store memory addresses?', 'subject': 'C'}).json()
        assert data['response_mode'] == 'source_excerpts' and data['sources']
        assert 'awaiting permission' in data['answer']
    conv = client.post('/api/v1/conversations', headers=headers, json={'subject': 'C'}).json()
    reply = client.post(f"/api/v1/conversations/{conv['id']}/messages", headers=headers,
        json={'question': 'How do C pointers store memory addresses?'}).json()
    assert reply['response_mode'] == 'source_excerpts' and 'awaiting permission' in reply['answer']
    from app.models.user import User
    db_session.get(User, auth['user']['id']).role = 'admin'
    db_session.commit()
    assert client.post(f"/api/v1/documents/{result['document_id']}/process", headers=headers).status_code == 422
    with pytest.raises(ValueError, match='Permission is required'):
        process_document(db_session, result['document_id'], max_chunks=1)
    provider.assert_not_called()


def test_local_permission_flag_survives_offline_reextraction(db_session, tmp_path, monkeypatch):
    result = import_source_book(db_session, source_pdf(tmp_path), 'C', extractor=local_extractor)
    doc = db_session.get(Document, result['document_id'])
    make_simple_pdf([['A changed C chapter describes pointers to objects and checked array indexes.']],
        storage_service.get_file_path(doc.filename))
    monkeypatch.setattr(embedding_service, 'generate_embeddings_batch', Mock(side_effect=AssertionError('No provider')))
    process_document(db_session, doc.id, max_chunks=0)
    assert not provider_use_allowed(doc)
    assert all(json.loads(chunk.metadata_json)['provider_access'] == 'local_only' for chunk in doc.chunks)
    assert db_session.query(DocumentChunk).count() == 1


def test_explicit_approval_keeps_text_ids_and_is_idempotent(db_session, tmp_path):
    result = import_source_book(db_session, source_pdf(tmp_path), 'C', extractor=local_extractor)
    doc = db_session.get(Document, result['document_id'])
    original = [(chunk.id, chunk.content, chunk.page_number, chunk.embedding_json) for chunk in doc.chunks]
    approval = authorize_provider_use(db_session, doc, 'Human approved this fixture for Google')
    assert approval['changed_chunks'] == 2 and provider_use_allowed(doc)
    assert [(chunk.id, chunk.content, chunk.page_number, chunk.embedding_json) for chunk in doc.chunks] == original
    metadata = [chunk.metadata_json for chunk in doc.chunks]
    assert all(json.loads(value)['provider_authorization']['source_sha256'] == result['source_sha256'] for value in metadata)
    assert authorize_provider_use(db_session, doc, 'Repeated reference')['changed_chunks'] == 0
    assert [chunk.metadata_json for chunk in doc.chunks] == metadata


@pytest.mark.parametrize('problem', ['missing_note', 'changed_pdf', 'processing'])
def test_approval_rejects_missing_evidence_and_keeps_local_protection(db_session, tmp_path, problem):
    result = import_source_book(db_session, source_pdf(tmp_path), 'C', extractor=local_extractor)
    doc = db_session.get(Document, result['document_id'])
    metadata = [chunk.metadata_json for chunk in doc.chunks]
    if problem == 'changed_pdf':
        with open(storage_service.get_file_path(doc.filename), 'ab') as stream:
            stream.write(b'changed')
    elif problem == 'processing':
        doc.status = 'processing'
        db_session.commit()
    with pytest.raises(ValueError):
        authorize_provider_use(db_session, doc, '' if problem == 'missing_note' else 'Human approved')
    assert not provider_use_allowed(doc)
    assert [chunk.metadata_json for chunk in doc.chunks] == metadata


def test_approved_book_can_embed_without_reextracting(db_session, tmp_path, monkeypatch):
    from app.core.config import settings
    result = import_source_book(db_session, source_pdf(tmp_path), 'C', extractor=local_extractor)
    doc = db_session.get(Document, result['document_id'])
    authorize_provider_use(db_session, doc, 'Human approved this fixture for Google')
    monkeypatch.setattr(embedding_service, 'is_configured', lambda: True)
    monkeypatch.setattr(embedding_service, 'generate_embeddings_batch', lambda texts: [[1.0] + [0.0] * (settings.EMBEDDING_DIMENSIONS - 1) for text in texts])
    monkeypatch.setattr('app.services.pdf_service.pdf_service.extract_and_chunk', Mock(side_effect=AssertionError('Do not re-extract')))
    process_document(db_session, doc.id, max_chunks=2)
    assert index_coverage(doc)['embedded_chunks'] == 2 and doc.status == 'ready'
