"""Reviewed source exclusions and private-reference recall with real boundaries."""
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.models.document import Document, DocumentChunk
from app.models.subject import UserSubject
from app.models.user import User
from app.services.embedding_service import embedding_service
from app.services.rag_service import rag_service
from app.services.source_quality import JAVA_BOOK_SHA256, PYTHON_BOOK_SHA256, SOURCE_CAUTION, TUPLE_CAUTION, reviewed_passage

FAULTY = ('toUpperCase and toLowerCase convert case. '
    'These methods both return the converted strings as new String instances: '
    'the original String objects are not modified because String is immutable in Java.')


def java_evidence(db):
    doc = Document(is_default=True, title='Java Reference', filename='java.pdf',
        original_filename='JavaNotesForProfessionals.pdf', subject='Java', status='partial')
    db.add(doc)
    db.flush()
    chunk = DocumentChunk(document_id=doc.id, chunk_index=0, page_number=77,
        content=FAULTY, metadata_json=json.dumps({'source_sha256': JAVA_BOOK_SHA256}))
    db.add(chunk)
    db.commit()
    source = rag_service._source(chunk, doc.title, 1, 'lexical')
    return doc, chunk, source


def test_exclusion_preserves_saved_text_and_labels_offline_excerpts(db_session):
    doc, chunk, source = java_evidence(db_session)
    text, note = reviewed_passage(chunk, doc)
    assert 'new String instances' not in text
    assert 'String is immutable' in text and note == SOURCE_CAUTION
    result = rag_service.generate_answer_result('Do Java case methods modify the original String?', [source], db_session, {})
    assert result.response_mode == 'source_excerpts' and SOURCE_CAUTION in result.answer
    assert chunk.content == FAULTY


@pytest.mark.parametrize('change', ['private', 'fingerprint', 'page', 'language'])
def test_review_does_not_rewrite_other_sources(db_session, change):
    doc, chunk, _ = java_evidence(db_session)
    if change == 'private': doc.is_default = False
    if change == 'fingerprint': chunk.metadata_json = '{}'
    if change == 'page': chunk.page_number = 78
    if change == 'language': doc.subject = 'Python'
    assert reviewed_passage(chunk, doc) == (FAULTY, None)


@pytest.mark.parametrize('claim,expected', [
    ('The original String remains unchanged.', 'generated'),
    ('Both methods return new String instances.', 'source_excerpts'),
    ('Every case-conversion operation allocates a new object.', 'source_excerpts'),
])
def test_bad_allocation_claim_cannot_reenter_via_generation(db_session, monkeypatch, claim, expected):
    _, chunk, source = java_evidence(db_session)
    generate = Mock(return_value=SimpleNamespace(text=json.dumps({'abstained': False,
        'claims': [{'text': claim, 'source_ids': ['S1']}]})))
    client = SimpleNamespace(models=SimpleNamespace(generate_content=generate), close=Mock())
    monkeypatch.setattr(embedding_service, 'is_configured', lambda: True)
    monkeypatch.setattr('google.genai.Client', lambda **kwargs: client)
    result = rag_service.generate_answer_result('Does Java case conversion change the original String?', [source], db_session, {})
    assert result.response_mode == expected
    payload = json.loads(generate.call_args.kwargs['contents'])
    assert 'new String instances' not in payload['evidence'][0]['text']
    assert 'editorial_exclusion' in payload['evidence'][0]
    assert SOURCE_CAUTION in result.answer and chunk.content == FAULTY
    client.close.assert_called_once()


@pytest.mark.parametrize('claim,expected', [
    ('Tuples are enclosed in parentheses.', 'source_excerpts'),
    ('Tuples cannot be updated after creation.', 'generated'),
])
def test_simplified_tuple_source_does_not_override_precise_syntax(db_session, monkeypatch, claim, expected):
    original = ("Lists are enclosed in brackets [ ] and their elements and size can be changed, "
        "while tuples are enclosed in parentheses ( ) and cannot be updated. Tuples are immutable. "
        "tuple = (123,'hello') tuple1 = ('world') print(tuple + tuple1) # example")
    doc = Document(is_default=True, title='Python Reference', filename='python.pdf',
        original_filename='PythonNotesForProfessionals.pdf', subject='Python', status='partial')
    db_session.add(doc)
    db_session.flush()
    chunk = DocumentChunk(document_id=doc.id, chunk_index=0, page_number=59, content=original,
        metadata_json=json.dumps({'source_sha256': PYTHON_BOOK_SHA256}))
    db_session.add(chunk)
    db_session.commit()
    text, note = reviewed_passage(chunk, doc)
    assert 'enclosed in parentheses' not in text and "tuple1 = ('world')" not in text
    assert 'Tuples are immutable.' in text and note == TUPLE_CAUTION
    generate = Mock(return_value=SimpleNamespace(text=json.dumps({'abstained': False,
        'claims': [{'text': claim, 'source_ids': ['S1']}]})))
    monkeypatch.setattr(embedding_service, 'is_configured', lambda: True)
    monkeypatch.setattr('google.genai.Client', lambda **kwargs: SimpleNamespace(
        models=SimpleNamespace(generate_content=generate), close=lambda: None))
    result = rag_service.generate_answer_result('Compare lists and tuples in Python.',
        [rag_service._source(chunk, doc.title, 1, 'lexical')], db_session, {}, subject='Python')
    assert result.response_mode == expected and TUPLE_CAUTION in result.answer
    assert chunk.content == original
    doc.is_default = False
    assert reviewed_passage(chunk, doc) == (original, None)


@pytest.mark.parametrize('repairs', [True, False])
def test_tuple_precision_retry_is_bounded_and_never_exposes_rejected_wording(db_session, monkeypatch, repairs):
    doc = Document(is_default=True, title='Tuple Reference', filename='tuple.pdf',
        original_filename='PythonNotesForProfessionals.pdf', subject='Python', status='partial')
    db_session.add(doc)
    db_session.flush()
    chunk = DocumentChunk(document_id=doc.id, chunk_index=0, page_number=187,
        content='A one-value tuple uses a trailing comma. a = 1, and a = (1,) are tuples.')
    db_session.add(chunk)
    db_session.commit()
    def payload(text):
        return SimpleNamespace(text=json.dumps({'abstained': False, 'claims': [{'text': text, 'source_ids': ['S1']}]}))
    bad = payload('A tuple can be created using a trailing comma alone.')
    good = payload('For a one-item tuple, a comma follows the value; parentheses around that value are optional.')
    generate = Mock(side_effect=[bad, good if repairs else bad])
    client = SimpleNamespace(models=SimpleNamespace(generate_content=generate), close=Mock())
    monkeypatch.setattr(embedding_service, 'is_configured', lambda: True)
    monkeypatch.setattr('google.genai.Client', lambda **kwargs: client)
    result = rag_service.generate_answer_result('Explain singleton tuple syntax in Python.',
        [rag_service._source(chunk, doc.title, 1, 'lexical')], db_session, {}, subject='Python')
    assert generate.call_count == 2 and client.close.call_count == 1
    assert 'comma alone' not in result.answer
    assert result.response_mode == ('generated' if repairs else 'source_excerpts')


@pytest.mark.parametrize('question', [
    'What is the acceptance marker in this reference?',
    'Which marker does my reference give?',
    'Tell me about the marker in our reference.',
])
def test_private_paraphrases_retrieve_only_owner_even_with_matching_foreign_text(db_session, question):
    owners = []
    for name in ['alice-quality', 'bob-quality']:
        owner = User(email=name + '@example.com', username=name, hashed_password='unused-test-hash')
        db_session.add(owner)
        db_session.flush()
        db_session.add(UserSubject(user_id=owner.id, name='Acceptance Lab', name_key='acceptance lab'))
        doc = Document(title='Reference', filename=name + '.pdf', original_filename='reference.pdf',
            subject='Acceptance Lab', is_default=False, uploaded_by=owner.id, status='partial')
        db_session.add(doc)
        db_session.flush()
        db_session.add(DocumentChunk(document_id=doc.id, chunk_index=0, page_number=1,
            content='This private acceptance reference has marker ' + name + '.'))
        owners.append((owner, doc))
    db_session.commit()
    for owner, doc in owners:
        for scope in ['Acceptance Lab', 'All']:
            sources = rag_service.retrieve_relevant_chunks(db_session, question, scope, user_id=owner.id)
            assert sources and {source.document_id for source in sources} == {doc.id}
            response = rag_service.generate_answer_result(question, sources, db_session, {}, user_id=owner.id, subject=scope)
            assert response.response_mode == 'source_excerpts'
            foreign = next(other.username for other, _ in owners if other.id != owner.id)
            assert foreign not in response.answer
    assert rag_service.retrieve_relevant_chunks(db_session, question, 'All') == []
