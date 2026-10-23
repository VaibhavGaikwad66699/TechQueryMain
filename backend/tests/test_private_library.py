"""Account isolation is enforced before ranking and before provider submission."""
import hashlib
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from app.core.config import settings
from app.core.scope import SUPPORTED_LANGUAGES
from app.models.document import Document, DocumentChunk
from app.models.user import User
from app.services.embedding_service import embedding_service
from app.services.rag_service import rag_service
from app.schemas.rag import SourceReference
from seed_sample_docs import make_simple_pdf


def account(client, name):
    result = client.post('/api/v1/auth/register', json={
        'email': name + '@example.com', 'username': name, 'password': 'Password123!'}).json()
    assert result['user']['role'] == 'user'
    return {'Authorization': 'Bearer ' + result['access_token']}, result['user']['id']


def defaults(db):
    books = []
    for language in SUPPORTED_LANGUAGES:
        doc = Document(title=language + ' Default', filename=language + '.pdf', original_filename='book.pdf',
            subject=language, is_default=True, status='partial', total_chunks=1)
        db.add(doc)
        db.flush()
        db.add(DocumentChunk(document_id=doc.id, chunk_index=0, page_number=1,
            content='Interfaces describe a contract for implementing classes in programming.'))
        books.append(doc)
    db.commit()
    return books


def upload(client, headers, tmp_path, subject, text):
    path = tmp_path / 'reference.pdf'
    make_simple_pdf([[text]], path)
    response = client.post('/api/v1/documents/upload', headers=headers,
        files={'file': ('reference.pdf', path.read_bytes(), 'application/pdf')},
        data={'subject': subject, 'auto_process': 'true', 'is_default': 'true', 'uploaded_by': '999'})
    assert response.status_code == 201, response.text
    assert response.json()['processing_scheduled'] is True
    return response.json()['document']['id'], path.read_bytes()


def test_registration_includes_four_defaults_without_copying_books(client, db_session):
    shared = defaults(db_session)
    expected = {doc.id for doc in shared}
    first, _ = account(client, 'first')
    second, _ = account(client, 'second')
    for headers in ({}, first, second):
        docs = client.get('/api/v1/documents', headers=headers).json()
        assert {doc['id'] for doc in docs} == expected
        assert all(doc['is_default'] and not doc['can_modify'] for doc in docs)
    assert db_session.query(Document).count() == 4
    assert db_session.query(DocumentChunk).count() == 4
    for doc in shared:
        assert client.delete(f'/api/v1/documents/{doc.id}', headers=first).status_code == 403


def test_same_named_personal_subjects_and_pdfs_never_cross_accounts(client, db_session, tmp_path, monkeypatch):
    shared = defaults(db_session)
    alice, alice_id = account(client, 'alice')
    bob, bob_id = account(client, 'bob')
    admin, admin_id = account(client, 'admin')
    db_session.get(User, admin_id).role = 'admin'
    db_session.commit()
    for headers in (alice, bob):
        assert client.post('/api/v1/subjects', headers=headers, json={'name': ' Biology '}).status_code == 201
        assert client.post('/api/v1/subjects', headers=headers, json={'name': 'biology'}).status_code == 409
    assert 'Biology' not in client.get('/api/v1/subjects').json()
    assert 'Biology' not in client.get('/api/v1/subjects', headers=admin).json()
    alice_doc, alice_pdf = upload(client, alice, tmp_path, 'biology',
        'Mitochondria release energy through cellular respiration. ALICE_PRIVATE_MARKER.')
    bob_doc, _ = upload(client, bob, tmp_path, 'Biology',
        'Mitochondria release energy through cellular respiration. BOB_PRIVATE_MARKER.')
    assert db_session.get(Document, alice_doc).uploaded_by == alice_id
    assert db_session.get(Document, bob_doc).uploaded_by == bob_id
    assert db_session.get(Document, alice_doc).is_default is False
    assert db_session.get(Document, bob_doc).is_default is False
    for headers, own, foreign in ((alice, alice_doc, bob_doc), (bob, bob_doc, alice_doc)):
        docs = client.get('/api/v1/documents', headers=headers).json()
        assert {doc['id'] for doc in docs} == {own, *(doc.id for doc in shared)}
        for suffix in ('', '/download'):
            assert client.get(f'/api/v1/documents/{foreign}{suffix}', headers=headers).status_code == 404
        assert client.post(f'/api/v1/documents/{foreign}/process', headers=headers).status_code == 404
        assert client.delete(f'/api/v1/documents/{foreign}', headers=headers).status_code == 404
        for subject in ('All', 'Biology'):
            response = client.post('/api/v1/query', headers=headers, json={
                'question': 'How do mitochondria release energy through cellular respiration?', 'subject': subject}).json()
            assert {source['document_id'] for source in response['sources']} == {own}
            assert response['response_mode'] == 'source_excerpts'
    for headers in ({}, admin):
        assert len(client.get('/api/v1/documents', headers=headers).json()) == 4
        assert client.get(f'/api/v1/documents/{alice_doc}/download', headers=headers).status_code == 404
        assert client.post('/api/v1/query', headers=headers,
            json={'question': 'Explain cellular respiration', 'subject': 'Biology'}).status_code == 422
        assert client.get('/api/v1/health', headers=headers).json()['database']['total_documents'] == 4
    download = client.get(f'/api/v1/documents/{alice_doc}/download', headers=alice)
    assert download.content == alice_pdf and download.headers['cache-control'] == 'private, no-store'

    # Generation independently rejects a forged source from another user's book.
    chunk = db_session.get(Document, bob_doc).chunks[0]
    forged = SourceReference(document_id=bob_doc, document_title='forged', page_number=1,
        chunk_index=0, similarity_score=1, snippet=chunk.content)
    provider = Mock(side_effect=AssertionError('Private text must not leave its owner scope'))
    monkeypatch.setattr('google.genai.Client', provider)
    assert rag_service.generate_answer_result('Explain cellular respiration', [forged], db_session, {},
        user_id=alice_id, subject='Biology').abstained
    provider.assert_not_called()


def test_custom_subject_conversation_generation_and_saved_preferences(client, db_session, tmp_path, monkeypatch):
    alice, _ = account(client, 'alice')
    bob, _ = account(client, 'bob')
    assert client.post('/api/v1/subjects', headers=alice, json={'name': 'Operating Systems'}).status_code == 201
    doc_id, _ = upload(client, alice, tmp_path, 'Operating Systems',
        'Paging divides virtual memory into fixed-size pages. A page table maps pages to physical frames.')
    preferences = {'preferred_subject': 'Operating Systems', 'explanation_level': 'Beginner',
        'answer_style': 'Concise', 'include_examples': False}
    assert client.put('/api/v1/users/preferences', headers=alice, json=preferences).status_code == 200
    assert client.get('/api/v1/users/preferences', headers=alice).json()['preferred_subject'] == 'Operating Systems'
    assert client.put('/api/v1/users/preferences', headers=bob, json=preferences).status_code == 422
    assert client.post('/api/v1/conversations', headers=bob, json={'subject': 'Operating Systems'}).status_code == 422
    preferred_conversation = client.post('/api/v1/conversations', headers=alice, json={}).json()
    assert preferred_conversation['subject'] == 'Operating Systems'

    generate = Mock(return_value=SimpleNamespace(text=json.dumps({'abstained': False, 'claims': [
        {'text': 'Paging divides virtual memory into fixed-size pages.', 'source_ids': ['S1']}]})))
    provider = SimpleNamespace(models=SimpleNamespace(generate_content=generate), close=lambda: None)
    monkeypatch.setattr(embedding_service, 'is_configured', lambda: True)
    monkeypatch.setattr('google.genai.Client', lambda **kwargs: provider)
    # No subject override: direct queries use this account's saved preference.
    direct = client.post('/api/v1/query', headers=alice, json={'question': 'Explain paging and virtual memory.'}).json()
    assert direct['response_mode'] == 'generated'
    assert {source['document_id'] for source in direct['sources']} == {doc_id}
    assert direct['preferences_applied'] == {key: value for key, value in preferences.items() if key != 'preferred_subject'}
    instruction = generate.call_args.kwargs['config']['system_instruction']
    assert '"explanation_level": "Beginner"' in instruction and '"include_examples": false' in instruction
    conv = client.post('/api/v1/conversations', headers=alice, json={'subject': 'Operating Systems'}).json()
    reply = client.post(f"/api/v1/conversations/{conv['id']}/messages", headers=alice,
        json={'question': 'Explain paging and virtual memory.'}).json()
    assert reply['response_mode'] == 'generated' and reply['preferences_applied']['answer_style'] == 'Concise'
    assert client.get(f"/api/v1/conversations/{conv['id']}", headers=bob).status_code == 404
    assert client.get('/api/v1/conversations', headers=bob).json() == []
    assert client.get('/api/v1/users/preferences', headers=bob).json()['preferred_subject'] == 'All'


@pytest.mark.parametrize('name', ['', '  ', 'x' * 101, 'Bad\nSubject'])
def test_subject_names_are_bounded(client, name):
    headers, _ = account(client, 'owner')
    assert client.post('/api/v1/subjects', headers=headers, json={'name': name}).status_code == 422


def test_reserved_subjects_and_guest_creation_rejected(client):
    headers, _ = account(client, 'owner')
    for name in ['All', 'JAVA', 'cpp', 'python', 'C']:
        assert client.post('/api/v1/subjects', headers=headers, json={'name': name}).status_code == 409
    assert client.post('/api/v1/subjects', json={'name': 'Biology'}).status_code == 401


def test_semantic_and_hybrid_candidates_are_filtered_before_provider_calls(client, db_session, tmp_path, monkeypatch):
    alice, alice_id = account(client, 'alice')
    bob, _ = account(client, 'bob')
    alice_doc, _ = upload(client, alice, tmp_path, 'Java', 'Interfaces specify a contract for implementing classes. ALICE.')
    bob_doc, _ = upload(client, bob, tmp_path, 'Java', 'Interfaces specify a contract for implementing classes. BOB.')
    vector = [1.0] + [0.0] * (settings.EMBEDDING_DIMENSIONS - 1)
    bob_chunk = db_session.get(Document, bob_doc).chunks[0]
    bob_chunk.embedding_json = json.dumps(vector)
    bob_chunk.metadata_json = json.dumps({'embedding': embedding_service.provenance(bob_chunk.content)})
    db_session.commit()
    monkeypatch.setattr(embedding_service, 'is_configured', lambda: True)
    embed = Mock(return_value=vector)
    monkeypatch.setattr(embedding_service, 'generate_embedding', embed)
    sources = rag_service.retrieve_relevant_chunks(db_session, 'Explain interfaces contract.', 'Java', user_id=alice_id)
    assert {source.document_id for source in sources} == {alice_doc}
    embed.assert_not_called()  # Bob's compatible vector cannot trigger Alice's semantic search.
    chunk = db_session.get(Document, alice_doc).chunks[0]
    chunk.embedding_json = json.dumps(vector)
    chunk.metadata_json = json.dumps({'embedding': embedding_service.provenance(chunk.content)})
    db_session.commit()
    sources = rag_service.retrieve_relevant_chunks(db_session, 'Explain interfaces contract.', 'Java', user_id=alice_id)
    assert {source.document_id for source in sources} == {alice_doc}
    assert sources[0].retrieval_method == 'semantic'
