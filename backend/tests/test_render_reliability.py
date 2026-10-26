import json
from pathlib import Path
from unittest.mock import Mock
from types import SimpleNamespace

import pytest
from sqlalchemy.orm import raiseload
from app.core.config import settings
from app.models.document import Document, DocumentChunk
from app.services.embedding_service import embedding_service
from app.services.index_service import index_coverage
from app.services.provider_access import provider_use_allowed
from app.services.rag_service import rag_service


def test_coverage_and_permissions_do_not_load_chunk_relationship(db_session):
    doc = Document(title='Test', filename='test.pdf', original_filename='test.pdf',
        subject='Java', is_default=True, status='partial', total_pages=1, total_chunks=1)
    db_session.add(doc); db_session.flush()
    content = 'Interfaces define contracts.'
    db_session.add(DocumentChunk(document_id=doc.id, chunk_index=0, page_number=1, content=content,
        embedding_json=json.dumps([1.] + [0.] * (settings.EMBEDDING_DIMENSIONS - 1)),
        metadata_json=json.dumps({'embedding': embedding_service.provenance(content)})))
    db_session.commit(); db_session.expire_all()
    doc = db_session.query(Document).options(raiseload(Document.chunks)).one()
    assert index_coverage(doc)['embedded_chunks'] == 1
    assert provider_use_allowed(doc)
    assert 'chunks' not in doc.__dict__


def general_provider(monkeypatch, text='A database index helps locate rows efficiently.'):
    monkeypatch.setattr(settings, 'ALLOW_GENERAL_ANSWERS', True)
    monkeypatch.setattr(embedding_service, 'is_configured', lambda: True)
    call = Mock(return_value=SimpleNamespace(text=text))
    client = SimpleNamespace(models=SimpleNamespace(generate_content=call), close=Mock())
    monkeypatch.setattr('google.genai.Client', lambda **kwargs: client)
    return call, client


@pytest.mark.parametrize('question', ['Explain SQL indexes.', 'What is the orbital period of Neptune?',
    'Explain C++26 reflection.', 'Explain Rust borrowing.'])
def test_unsupported_query_uses_labelled_general_answer(client, monkeypatch, question):
    call, provider = general_provider(monkeypatch)
    result = client.post('/api/v1/query', json={'question': question}).json()
    assert result['response_mode'] == 'general_ai' and not result['abstained']
    assert not result['context_used'] and result['sources'] == [] and result['retrieval_mode'] == 'none'
    assert result['answer'].startswith('General AI answer')
    assert json.loads(call.call_args.kwargs['contents']) == {'question': question}
    provider.close.assert_called_once()


def test_general_answer_preserves_history_without_sources(client, monkeypatch):
    account = client.post('/api/v1/auth/register', json={'email':'general@example.com',
        'username':'General', 'password':'Password123!'}).json()
    headers = {'Authorization':'Bearer '+account['access_token']}
    conv = client.post('/api/v1/conversations', headers=headers, json={}).json()
    call, _ = general_provider(monkeypatch)
    reply = client.post(f"/api/v1/conversations/{conv['id']}/messages", headers=headers,
        json={'question':'Explain SQL indexes.'})
    assert reply.status_code == 200 and reply.json()['response_mode'] == 'general_ai'
    history = client.get(f"/api/v1/conversations/{conv['id']}", headers=headers).json()['messages'][-1]
    assert history['response_mode'] == 'general_ai' and history['sources'] is None
    assert history['content'].startswith('General AI answer')


@pytest.mark.parametrize('failure', [RuntimeError('quota unavailable'), '', 'Invented [Book, PDF p. 1]'])
def test_general_failure_never_fabricates_a_book_answer(client, monkeypatch, failure):
    call, _ = general_provider(monkeypatch, text=failure if isinstance(failure,str) else '')
    if isinstance(failure, Exception): call.side_effect = failure
    result = client.post('/api/v1/query', json={'question':'Explain SQL indexes.'}).json()
    assert result['abstained'] and result['sources'] == [] and not result['context_used']
    assert 'general AI answer is unavailable' in result['answer']
    assert call.call_count == 1


def test_model_abstention_uses_general_answer_without_retrieved_context(client, db_session, monkeypatch):
    doc = Document(title='Private facts', filename='test.pdf', original_filename='test.pdf', subject='Java',
        is_default=True, status='partial', total_pages=1, total_chunks=1)
    db_session.add(doc); db_session.flush()
    db_session.add(DocumentChunk(document_id=doc.id, chunk_index=0, page_number=1,
        content='Interfaces specify a contract that implementing classes must satisfy.'))
    db_session.commit()
    call, _ = general_provider(monkeypatch)
    call.side_effect = [SimpleNamespace(text=json.dumps({'abstained':True,'claims':[]})),
        SimpleNamespace(text='Here is a general explanation.')]
    result = client.post('/api/v1/query', json={'question':'What contract do interfaces specify?', 'subject':'Java'}).json()
    assert result['response_mode'] == 'general_ai' and result['sources'] == []
    assert 'evidence' not in json.loads(call.call_args.kwargs['contents'])


def test_general_answer_cannot_forward_another_owners_reference(db_session, monkeypatch):
    from app.models.user import User
    from app.schemas.rag import SourceReference
    alice = User(email='alice@example.com', username='Alice', hashed_password='not-used')
    bob = User(email='bob@example.com', username='Bob', hashed_password='not-used')
    db_session.add_all([alice,bob]); db_session.flush()
    doc = Document(title='BOB PRIVATE', filename='secret.pdf', original_filename='secret.pdf',
        subject='Java', uploaded_by=bob.id, is_default=False, status='partial')
    db_session.add(doc); db_session.flush()
    db_session.add(DocumentChunk(document_id=doc.id, chunk_index=0, page_number=1, content='BOB SECRET CONTENT'))
    db_session.commit()
    call, _ = general_provider(monkeypatch)
    source = SourceReference(document_id=doc.id,document_title=doc.title,page_number=1,
        chunk_index=0,similarity_score=1,snippet='BOB SECRET CONTENT')
    result = rag_service.generate_answer_result('Explain resource ownership.',[source],db_session,{},user_id=alice.id)
    assert result.response_mode == 'general_ai' and not result.context_used
    request = json.dumps(call.call_args.kwargs)
    assert 'BOB' not in request and 'secret.pdf' not in request


def test_registration_rolls_back_account_if_preferences_fail(client, db_session):
    from sqlalchemy import event
    from sqlalchemy.exc import IntegrityError
    from app.models.user import User, UserPreference
    def fail(*args):
        raise IntegrityError('synthetic preference failure', {}, Exception('disposable test'))
    event.listen(UserPreference, 'before_insert', fail)
    try:
        response = client.post('/api/v1/auth/register',json={'email':'atomic@example.com',
            'username':'Atomic','password':'Password123!'})
        assert response.status_code == 400
        assert db_session.query(User).filter_by(email='atomic@example.com').count() == 0
    finally:
        event.remove(UserPreference,'before_insert',fail)


def test_bootstrap_preserves_existing_database(tmp_path, monkeypatch):
    import bootstrap_runtime as boot
    database = tmp_path/'techquery.db'; database.write_bytes(b'existing account data')
    monkeypatch.setattr(settings, 'DATABASE_URL', 'sqlite:///'+database.as_posix())
    monkeypatch.setattr(settings, 'DOCUMENTS_DIR', str(tmp_path/'documents'))
    restore = Mock(side_effect=AssertionError('Never restore over an existing database'))
    monkeypatch.setattr(boot, 'restore_bundle', restore)
    boot.initialize(tmp_path/'absent-seed')
    assert database.read_bytes() == b'existing account data'
    restore.assert_not_called()


def test_bootstrap_uses_configured_directory_and_rejects_mismatched_storage(tmp_path, monkeypatch):
    import bootstrap_runtime as boot
    database = tmp_path/'nested/techquery.db'
    monkeypatch.setattr(settings,'DATABASE_URL','sqlite:///'+database.as_posix())
    monkeypatch.setattr(settings,'DOCUMENTS_DIR',str(database.parent/'documents'))
    restore = Mock(); monkeypatch.setattr(boot,'restore_bundle',restore)
    boot.initialize(tmp_path/'seed')
    restore.assert_called_once_with(tmp_path/'seed',database.parent)
    monkeypatch.setattr(settings,'DOCUMENTS_DIR',str(tmp_path/'elsewhere'))
    with pytest.raises(ValueError, match='same configured data directory'):
        boot.initialize(tmp_path/'seed')
