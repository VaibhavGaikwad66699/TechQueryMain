from pathlib import Path
from unittest.mock import Mock
import os

import pytest
from app.models.document import Document, DocumentChunk
from app.models.subject import UserSubject
from app.models.user import User, UserPreference
from app.services import ingestion_jobs
from app.services.storage_service import storage_service


def account(client, name):
    response = client.post('/api/v1/auth/register', json={
        'email': name + '@example.com', 'username': name, 'password': 'Password123!'})
    data = response.json()
    return {'Authorization': 'Bearer ' + data['access_token']}, data['user']['id']


def subject(client, headers, name='Biology'):
    assert client.post('/api/v1/subjects', headers=headers, json={'name': name}).status_code == 201


def book(db, user_id, name, filename, *, shared=False):
    doc = Document(title=filename, filename=filename, original_filename=filename, subject=name,
        uploaded_by=user_id, is_default=shared, status='partial', total_chunks=1)
    db.add(doc)
    db.flush()
    db.add(DocumentChunk(document_id=doc.id, chunk_index=0, page_number=1,
        content='Mitochondria release energy through cellular respiration.', embedding_json='[1,0]'))
    (storage_service.base_dir / filename).write_bytes(b'%PDF-original-' + filename.encode())
    db.commit()
    return doc


def remove(client, headers, name='Biology'):
    return client.delete('/api/v1/subjects', headers=headers, params={'name': name})


def test_subject_deletion_removes_only_owners_books_and_resets_preference(client, db_session):
    alice, alice_id = account(client, 'alice')
    bob, bob_id = account(client, 'bob')
    for headers in (alice, bob):
        subject(client, headers)
    subject(client, alice, 'Chemistry')
    own = [book(db_session, alice_id, 'Biology', 'alice1.pdf'), book(db_session, alice_id, 'Biology', 'alice2.pdf')]
    other = book(db_session, bob_id, 'Biology', 'bob.pdf')
    unrelated = book(db_session, alice_id, 'Chemistry', 'chemistry.pdf')
    defaults = [book(db_session, None, name, name.replace('+', 'p') + '.pdf', shared=True) for name in ['C', 'C++', 'Java', 'Python']]
    untouched = {doc.id: (storage_service.base_dir / doc.filename).read_bytes() for doc in [other, unrelated, *defaults]}
    assert client.put('/api/v1/users/preferences', headers=alice, json={'preferred_subject': 'Biology'}).status_code == 200
    conv = client.post('/api/v1/conversations', headers=alice, json={'subject': 'Biology'}).json()
    reply = client.post(f"/api/v1/conversations/{conv['id']}/messages", headers=alice, json={'question': 'How do mitochondria release energy?'}).json()
    assert reply['sources']
    deleted_ids = {doc.id for doc in own}
    response = remove(client, alice, 'biology')
    assert response.status_code == 200 and response.json()['documents_deleted'] == 2
    assert response.json()['storage_cleanup_pending'] is False
    assert db_session.query(DocumentChunk).filter(DocumentChunk.document_id.in_(deleted_ids)).count() == 0
    assert db_session.query(Document).filter(Document.id.in_(deleted_ids)).count() == 0
    for filename in ['alice1.pdf', 'alice2.pdf']:
        assert not (storage_service.base_dir / filename).exists()
    assert not list(storage_service.base_dir.glob('.subject-delete-*'))
    for doc_id, original in untouched.items():
        assert (storage_service.base_dir / db_session.get(Document, doc_id).filename).read_bytes() == original
    assert 'Biology' not in client.get('/api/v1/subjects', headers=alice).json()
    assert 'Biology' in client.get('/api/v1/subjects', headers=bob).json()
    assert client.get('/api/v1/users/preferences', headers=alice).json()['preferred_subject'] == 'All'
    assert client.get('/api/v1/users/preferences', headers=bob).json()['preferred_subject'] == 'All'
    assert client.get(f"/api/v1/conversations/{conv['id']}", headers=alice).json()['messages']  # History is preserved.
    assert client.post('/api/v1/query', headers=alice, json={'subject': 'Biology', 'question': 'Explain mitochondria.'}).status_code == 422
    for ident in deleted_ids:
        assert client.get(f'/api/v1/documents/{ident}/download', headers=alice).status_code == 404


def test_empty_subject_deletion_and_encoded_names(client, db_session):
    headers, _ = account(client, 'owner')
    name = 'Art / Design & Theory'
    subject(client, headers, name)
    response = remove(client, headers, name)
    assert response.status_code == 200 and response.json()['documents_deleted'] == 0
    assert name not in client.get('/api/v1/subjects', headers=headers).json()
    assert remove(client, headers, name).status_code == 404


def test_guests_outsiders_admins_and_default_subjects_are_protected(client, db_session):
    alice, alice_id = account(client, 'alice')
    outsider, outsider_id = account(client, 'outsider')
    db_session.get(User, outsider_id).role = 'admin'
    db_session.commit()
    subject(client, alice)
    doc = book(db_session, alice_id, 'Biology', 'private.pdf')
    assert remove(client, {}, 'Biology').status_code == 401
    assert remove(client, outsider, 'Biology').status_code == 404
    for name in ['All', 'C', 'cpp', 'Java', 'Python']:
        assert remove(client, alice, name).status_code == 404
        assert remove(client, outsider, name).status_code == 404
    assert db_session.get(Document, doc.id) is not None
    assert (storage_service.base_dir / doc.filename).exists()


@pytest.mark.parametrize('busy', ['queued', 'processing'])
def test_busy_subject_rejected_before_removing_any_files(client, db_session, monkeypatch, busy):
    headers, ident = account(client, 'owner')
    subject(client, headers)
    first = book(db_session, ident, 'Biology', 'first.pdf')
    second = book(db_session, ident, 'Biology', 'second.pdf')
    if busy == 'queued':
        monkeypatch.setattr(ingestion_jobs, '_active', {second.id})
    else:
        second.status = 'processing'
        db_session.commit()
    assert remove(client, headers).status_code == 409
    assert all((storage_service.base_dir / doc.filename).exists() for doc in (first, second))
    assert db_session.query(UserSubject).count() == 1


@pytest.mark.parametrize('failure', ['second_file', 'database'])
def test_failed_subject_deletion_restores_all_books_and_preference(client, db_session, monkeypatch, failure):
    headers, ident = account(client, 'owner')
    subject(client, headers)
    books = [book(db_session, ident, 'Biology', 'first.pdf'), book(db_session, ident, 'Biology', 'second.pdf')]
    before = {doc.filename: (storage_service.base_dir / doc.filename).read_bytes() for doc in books}
    preference = db_session.query(UserPreference).filter_by(user_id=ident).one()
    preference.preferred_subject = 'Biology'
    db_session.commit()
    with monkeypatch.context() as patch:
        if failure == 'database':
            patch.setattr(db_session, 'commit', Mock(side_effect=RuntimeError('private db error')))
        else:
            original = os.replace
            calls = 0
            def fail_second(source, target):
                nonlocal calls
                if str(source).endswith('.pdf'):
                    calls += 1
                if calls == 2:
                    raise OSError('private storage path')
                return original(source, target)
            patch.setattr('app.services.deletion_service.os.replace', fail_second)
        response = remove(client, headers)
    assert response.status_code == 503
    assert 'private db error' not in response.text and 'private storage path' not in response.text
    assert db_session.query(Document).count() == 2 and db_session.query(DocumentChunk).count() == 2
    assert db_session.query(UserSubject).count() == 1
    assert db_session.query(UserPreference).filter_by(user_id=ident).one().preferred_subject == 'Biology'
    for filename, content in before.items():
        assert (storage_service.base_dir / filename).read_bytes() == content


def test_cleanup_failure_is_reported_without_making_deleted_books_searchable(client, db_session, monkeypatch):
    headers, ident = account(client, 'owner')
    subject(client, headers)
    doc = book(db_session, ident, 'Biology', 'private.pdf')
    original = Path.unlink
    def failed(path, *args, **kwargs):
        if path.parent.name.startswith('.subject-delete-'):
            raise OSError('Temporary cleanup failure')
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'unlink', failed)
    response = remove(client, headers)
    assert response.status_code == 200 and response.json()['storage_cleanup_pending'] is True
    assert 'cleanup' in response.json()['message']
    assert db_session.query(DocumentChunk).count() == 0
    assert client.get(f'/api/v1/documents/{doc.id}/download', headers=headers).status_code == 404


def test_delete_one_source_book_keeps_subject_and_preferences(client, db_session):
    headers, ident = account(client, 'owner')
    subject(client, headers)
    doc = book(db_session, ident, 'Biology', 'private.pdf')
    client.put('/api/v1/users/preferences', headers=headers, json={'preferred_subject': 'Biology'})
    assert client.delete(f'/api/v1/documents/{doc.id}', headers=headers).status_code == 200
    assert 'Biology' in client.get('/api/v1/subjects', headers=headers).json()
    assert client.get('/api/v1/users/preferences', headers=headers).json()['preferred_subject'] == 'Biology'
    assert db_session.query(DocumentChunk).count() == 0
