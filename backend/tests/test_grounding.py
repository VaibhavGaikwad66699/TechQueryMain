import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from app.models.document import Document, DocumentChunk
from app.services.embedding_service import embedding_service
from app.services.rag_service import rag_service


def evidence(db):
    doc = Document(is_default=True, title='Source Book', filename='source.pdf', original_filename='source.pdf', subject='Java', status='partial')
    db.add(doc)
    db.flush()
    db.add(DocumentChunk(document_id=doc.id, chunk_index=0, page_number=42,
        content='Interfaces specify a contract that implementing classes must satisfy.'))
    db.commit()
    return rag_service.retrieve_relevant_chunks(db, 'What contract do interfaces specify?', 'Java')


def fake_provider(monkeypatch, payload):
    mock = Mock(return_value=SimpleNamespace(text=json.dumps(payload)))
    client = SimpleNamespace(models=SimpleNamespace(generate_content=mock), close=lambda: None)
    monkeypatch.setattr(embedding_service, 'is_configured', lambda: True)
    monkeypatch.setattr('google.genai.Client', lambda **kwargs: client)
    return mock


def test_no_evidence_abstains_without_provider_call(db_session, monkeypatch):
    mock = Mock(side_effect=AssertionError('Must not call provider'))
    monkeypatch.setattr('google.genai.Client', mock)
    result = rag_service.generate_answer_result('Unanswerable?', [], db_session, {})
    assert result.abstained and not result.context_used
    mock.assert_not_called()


def test_citations_use_database_page_and_only_allow_known_ids(db_session, monkeypatch):
    sources = evidence(db_session)
    fake_provider(monkeypatch, {'abstained': False, 'claims': [{'text': 'Interfaces specify a contract.', 'source_ids': ['S1']}]})
    result = rag_service.generate_answer_result('What contract?', sources, db_session, {})
    assert result.response_mode == 'generated'
    assert '[Source Book, PDF p. 42]' in result.answer
    fake_provider(monkeypatch, {'abstained': False, 'claims': [{'text': 'Invented', 'source_ids': ['S999']}]})
    result = rag_service.generate_answer_result('What contract?', sources, db_session, {})
    assert result.response_mode == 'source_excerpts'
    assert 'Invented' not in result.answer


def test_provider_abstention_and_outage_are_distinct(db_session, monkeypatch):
    sources = evidence(db_session)
    mock = fake_provider(monkeypatch, {'abstained': True, 'claims': []})
    result = rag_service.generate_answer_result('Unsupported question', sources, db_session, {})
    assert result.abstained and result.response_mode == 'abstained'
    mock.side_effect = RuntimeError('outage')
    result = rag_service.generate_answer_result('What contract?', sources, db_session, {})
    assert result.response_mode == 'source_excerpts' and not result.abstained
    assert 'generated explanation is unavailable' in result.answer


def test_lexical_search_avoids_toc_substrings_and_unrelated_questions(db_session):
    sources = evidence(db_session)
    assert sources[0].page_number == 42
    assert not rag_service.retrieve_relevant_chunks(db_session, 'What is a face?', 'Java')
    assert not rag_service.retrieve_relevant_chunks(db_session, 'What is the orbital period of Neptune?', 'Java')


@pytest.mark.parametrize('question', ['', '  ', 'x' * 4001])
def test_question_validation(client, question):
    assert client.post('/api/v1/query', json={'question': question}).status_code == 422


def test_api_discloses_fallback_and_incomplete_index(client, db_session):
    evidence(db_session)
    response = client.post('/api/v1/query', json={'question': 'What contract do interfaces specify?', 'subject': 'Java'})
    data = response.json()
    assert data['response_mode'] == 'source_excerpts'
    assert data['retrieval_mode'] == 'lexical'
    assert not data['abstained']
    docs = client.get('/api/v1/documents').json()
    assert docs[0]['status'] == 'partial'
    assert docs[0]['indexing']['embedded_chunks'] == 0
    assert client.get('/api/v1/health').json()['gemini']['availability'] == 'not_checked'


def test_unknown_legacy_vectors_do_not_exclude_unembedded_book(db_session, monkeypatch):
    sources = evidence(db_session)
    monkeypatch.setattr(embedding_service, 'is_configured', lambda: True)
    mock = Mock(side_effect=AssertionError('No compatible vectors; no query call needed'))
    monkeypatch.setattr(embedding_service, 'generate_embedding', mock)
    found = rag_service.retrieve_relevant_chunks(db_session, 'What contract do interfaces specify?', 'Java')
    assert found and found[0].retrieval_method == 'lexical'
    mock.assert_not_called()


def test_complete_index_uses_compatible_semantic_vectors(db_session, monkeypatch):
    evidence(db_session)
    from app.core.config import settings
    chunk = db_session.query(DocumentChunk).first()
    vector = [1.0] + [0.0] * (settings.EMBEDDING_DIMENSIONS - 1)
    chunk.embedding_json = json.dumps(vector)
    chunk.metadata_json = json.dumps({'embedding': embedding_service.provenance(chunk.content)})
    db_session.commit()
    monkeypatch.setattr(embedding_service, 'is_configured', lambda: True)
    monkeypatch.setattr(embedding_service, 'generate_embedding', lambda text: vector)
    found = rag_service.retrieve_relevant_chunks(db_session, 'What contract do interfaces specify?', 'Java')
    assert found[0].retrieval_method == 'semantic'
    assert found[0].page_number == 42


def test_conversation_preserves_response_mode(client):
    account = client.post('/api/v1/auth/register', json={'email': 'mode@example.com', 'username': 'ModeTest', 'password': 'Password123!'})
    headers = {'Authorization': 'Bearer ' + account.json()['access_token']}
    conv = client.post('/api/v1/conversations', json={'title': 'Modes'}, headers=headers).json()
    reply = client.post(f"/api/v1/conversations/{conv['id']}/messages", json={'question': 'What is an interface?'}, headers=headers)
    assert reply.json()['response_mode'] == 'abstained'
    history = client.get(f"/api/v1/conversations/{conv['id']}", headers=headers).json()
    assert history['messages'][1]['response_mode'] == 'abstained'
    assert history['messages'][1]['abstained'] is True


def test_generation_retries_a_transient_read_failure(db_session, monkeypatch):
    import httpx
    sources = evidence(db_session)
    payload = {'abstained': False, 'claims': [{'text': 'Interfaces specify a contract.', 'source_ids': ['S1']}]}
    mock = fake_provider(monkeypatch, payload)
    mock.side_effect = [httpx.ReadError('temporary disconnect'), SimpleNamespace(text=json.dumps(payload))]
    monkeypatch.setattr('app.services.rag_service.time.sleep', lambda seconds: None)
    result = rag_service.generate_answer_result('What contract?', sources, db_session, {})
    assert result.response_mode == 'generated'
    assert mock.call_count == 2
