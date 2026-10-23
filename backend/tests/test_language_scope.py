"""Scope is enforced for every caller, beyond the language dropdown."""
from unittest.mock import Mock

import pytest
from app.core.scope import question_outside_scope
from app.models.conversation import Conversation
from app.models.document import Document, DocumentChunk
from app.models.user import UserPreference
from app.services.index_service import process_document
from app.services.rag_service import rag_service
from app.services.storage_service import storage_service


def login(client):
    result = client.post('/api/v1/auth/register', json={
        'email': 'anyone@example.com', 'username': 'AnyCoder', 'password': 'Password123!'}).json()
    return {'Authorization': 'Bearer ' + result['access_token']}, result['user']['id']


def book(db, language, content='Pointers refer to memory addresses. Arrays store contiguous elements.'):
    doc = Document(is_default=True, title=language + ' Book', filename=language + '.pdf',
        original_filename='book.pdf', subject=language, status='partial', total_chunks=1)
    db.add(doc)
    db.flush()
    db.add(DocumentChunk(document_id=doc.id, chunk_index=0, page_number=7, content=content))
    db.commit()
    return doc


@pytest.mark.parametrize('language', ['C', 'C++', 'Java', 'Python'])
def test_each_language_is_searchable_for_guests_and_accounts(client, db_session, language):
    doc = book(db_session, language)
    headers, _ = login(client)
    for auth in ({}, headers):
        response = client.post('/api/v1/query', headers=auth,
            json={'question': 'How do pointers refer to memory addresses?', 'subject': language})
        assert response.status_code == 200
        assert response.json()['response_mode'] == 'source_excerpts'
        assert {source['document_id'] for source in response.json()['sources']} == {doc.id}


def test_all_filter_excludes_retained_books_and_specific_filter_isolates_languages(client, db_session):
    c = book(db_session, 'C')
    java = book(db_session, 'Java')
    old = book(db_session, 'Operating Systems')
    question = 'How do pointers refer to memory addresses?'
    assert {s.document_id for s in rag_service.retrieve_relevant_chunks(db_session, question)} == {c.id, java.id}
    assert {s.document_id for s in rag_service.retrieve_relevant_chunks(db_session, question, 'C')} == {c.id}
    assert rag_service.retrieve_relevant_chunks(db_session, question, 'Operating Systems') == []
    docs = client.get('/api/v1/documents').json()
    assert old.id not in {doc['id'] for doc in docs}
    assert client.get(f'/api/v1/documents/{old.id}').status_code == 404
    assert client.get('/api/v1/health').json()['database']['in_scope_documents'] == 2
    assert db_session.get(Document, old.id).chunks[0].content.startswith('Pointers')


@pytest.mark.parametrize('subject', ['DBMS', 'Operating Systems', 'JavaScript', 'General', 'SQL'])
def test_unsupported_subject_cannot_enter_query_preferences_or_conversations(client, subject):
    headers, _ = login(client)
    for auth in ({}, headers):
        assert client.post('/api/v1/query', headers=auth,
            json={'question': 'What are interfaces?', 'subject': subject}).status_code == 422
    assert client.get('/api/v1/documents', params={'subject': subject}).status_code == 422
    assert client.post('/api/v1/conversations', headers=headers, json={'subject': subject}).status_code == 422
    assert client.put('/api/v1/users/preferences', headers=headers,
        json={'preferred_subject': subject}).status_code == 422
    conv = client.post('/api/v1/conversations', headers=headers, json={}).json()
    assert client.post(f"/api/v1/conversations/{conv['id']}/messages", headers=headers,
        json={'question': 'What are interfaces?', 'subject': subject}).status_code == 422


@pytest.mark.parametrize('subject', ['All', 'DBMS', 'JavaScript', '', None])
def test_upload_requires_a_specific_supported_language_before_writing(client, subject):
    headers, _ = login(client)
    stored_before = set(storage_service.base_dir.iterdir())
    data = {'auto_process': 'false'}
    if subject is not None:
        data['subject'] = subject
    response = client.post('/api/v1/documents/upload', headers=headers,
        files={'file': ('sample.pdf', b'%PDF-1.4\nfixture', 'application/pdf')}, data=data)
    assert response.status_code == 422
    assert client.get('/api/v1/documents').json() == []
    assert set(storage_service.base_dir.iterdir()) == stored_before


@pytest.mark.parametrize(('value', 'canonical'), [(' c ', 'C'), ('cpp', 'C++'), ('C++', 'C++'), ('JAVA', 'Java'), ('python', 'Python')])
def test_upload_canonicalizes_language_labels(client, value, canonical):
    headers, _ = login(client)
    response = client.post('/api/v1/documents/upload', headers=headers,
        files={'file': ('sample.pdf', b'%PDF-1.4\nfixture', 'application/pdf')},
        data={'subject': value, 'auto_process': 'false'})
    assert response.status_code == 201
    assert response.json()['document']['subject'] == canonical
    assert response.json()['document']['in_scope'] is True


def test_legacy_preferences_and_conversations_stay_readable_without_relabeling_data(client, db_session):
    headers, user_id = login(client)
    pref = db_session.query(UserPreference).filter_by(user_id=user_id).one()
    pref.preferred_subject = 'DBMS'
    conv = Conversation(user_id=user_id, title='Old discussion', subject='Operating Systems')
    db_session.add(conv)
    db_session.commit()
    assert client.get('/api/v1/users/preferences', headers=headers).json()['preferred_subject'] == 'All'
    assert client.get(f'/api/v1/conversations/{conv.id}', headers=headers).json()['subject'] == 'Operating Systems'
    book(db_session, 'C')
    reply = client.post(f'/api/v1/conversations/{conv.id}/messages', headers=headers,
        json={'question': 'How do pointers refer to memory addresses?'}).json()
    assert reply['sources'][0]['document_title'] == 'C Book'
    db_session.refresh(pref)
    assert pref.preferred_subject == 'DBMS'  # compatibility is read-time only


def test_conversation_without_query_language_inherits_its_supported_language(client, db_session):
    headers, _ = login(client)
    c = book(db_session, 'C')
    book(db_session, 'Java')
    conv = client.post('/api/v1/conversations', headers=headers, json={'subject': 'C'}).json()
    response = client.post(f"/api/v1/conversations/{conv['id']}/messages", headers=headers,
        json={'question': 'How do pointers refer to memory addresses?'}).json()
    assert {source['document_id'] for source in response['sources']} == {c.id}


def test_aliases_work_for_json_and_url_filters(client, db_session):
    headers, _ = login(client)
    doc = book(db_session, 'C++')
    assert client.get('/api/v1/documents', params={'subject': 'cpp'}).json()[0]['id'] == doc.id
    assert client.put('/api/v1/users/preferences', headers=headers,
        json={'preferred_subject': 'python'}).json()['preferred_subject'] == 'Python'
    assert client.post('/api/v1/conversations', headers=headers,
        json={'subject': 'JAVA'}).json()['subject'] == 'Java'
    assert client.post('/api/v1/query', json={
        'question': 'How do pointers refer to memory addresses?', 'subject': 'cpp'}).json()['sources'][0]['document_id'] == doc.id


def test_generation_cannot_use_retained_outside_scope_evidence(db_session, monkeypatch):
    from app.schemas.rag import SourceReference
    doc = book(db_session, 'DBMS')
    provider = Mock(side_effect=AssertionError('Must not send retained out-of-scope passages'))
    monkeypatch.setattr('google.genai.Client', provider)
    source = SourceReference(document_id=doc.id, document_title=doc.title, page_number=7,
        chunk_index=0, similarity_score=1, snippet=doc.chunks[0].content)
    result = rag_service.generate_answer_result('How do pointers work?', [source], db_session, {})
    assert result.abstained and not result.context_used
    provider.assert_not_called()


@pytest.mark.parametrize('question', [
    'Explain JavaScript interfaces.', 'How do C# arrays work?', 'Write a Rust pointer example.',
    'Teach me programming in Go.', 'What are SQL joins?', 'Explain ACID properties in DBMS.',
])
def test_explicit_unsupported_questions_abstain_for_every_caller_without_provider(client, db_session, monkeypatch, question):
    book(db_session, 'Java', content=question)
    provider = Mock(side_effect=AssertionError('Scope rejection must not call Google'))
    monkeypatch.setattr('google.genai.Client', provider)
    headers, _ = login(client)
    for auth in ({}, headers):
        data = client.post('/api/v1/query', headers=auth, json={'question': question}).json()
        assert data['abstained'] is True and data['sources'] == []
        assert data['suggested_questions'] == []
        assert 'C, C++, Java, and Python' in data['answer']
    provider.assert_not_called()


@pytest.mark.parametrize('question', [
    'How do C++ constructors work?', 'How do I go back through a list in Python?',
    'How do Java threads work on operating systems?', 'Use SQL through Python sqlite3.',
    'How do pointers work?', 'Explain memory allocation in C.',
])
def test_related_programming_questions_remain_eligible(question):
    assert not question_outside_scope(question)


def test_retained_outside_scope_book_cannot_be_processed_via_api_or_cli(client, db_session):
    headers, _ = login(client)  # first account is admin in the local app
    doc = book(db_session, 'DBMS')
    chunk_id = doc.chunks[0].id
    assert client.post(f'/api/v1/documents/{doc.id}/process', headers=headers).status_code == 404
    with pytest.raises(ValueError, match=r'Only C, C\+\+, Java, and Python'):
        process_document(db_session, doc.id)
    db_session.refresh(doc)
    assert doc.status == 'partial' and doc.chunks[0].id == chunk_id
