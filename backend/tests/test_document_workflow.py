from fastapi import BackgroundTasks
import io
import pytest

from app.core.config import settings
from app.models.document import Document
from app.services import ingestion_jobs
from app.services.storage_service import storage_service, StorageError
from seed_sample_docs import make_simple_pdf


def account(client, name):
    response = client.post('/api/v1/auth/register', json={
        'email': f'{name}@example.com', 'username': name, 'password': 'Password123!'})
    assert response.status_code == 201
    return {'Authorization': 'Bearer ' + response.json()['access_token']}, response.json()['user']


def pdf_bytes(tmp_path):
    source = tmp_path / 'source.pdf'
    make_simple_pdf([
        ['A Java interface defines a contract that implementing classes must satisfy.'],
        ['Virtual memory allows a program to use more memory than physical RAM.'],
    ], source)
    return source.read_bytes()


def upload(client, headers, data, process=False):
    return client.post('/api/v1/documents/upload', headers=headers,
        files={'file': ('sample.pdf', data, 'application/pdf')},
        data={'subject': 'Java', 'auto_process': str(process).lower()})


def test_background_upload_process_download_and_resume(client, db_session, tmp_path):
    headers, _ = account(client, 'owner')
    content = pdf_bytes(tmp_path)
    response = upload(client, headers, content, process=True)
    assert response.status_code == 201
    assert response.json()['processing_scheduled'] is True
    doc = response.json()['document']
    assert doc['status'] == 'pending'  # accepted response is built before worker runs
    assert doc['processing_active'] is True
    detail = client.get(f"/api/v1/documents/{doc['id']}", headers=headers).json()
    assert detail['status'] == 'partial'
    assert detail['total_pages'] == 2 and detail['total_chunks'] == 2
    assert detail['processing_active'] is False and detail['can_modify'] is True
    original_ids = [c.id for c in db_session.get(Document, doc['id']).chunks]
    download = client.get(f"/api/v1/documents/{doc['id']}/download", headers=headers)
    assert download.status_code == 200 and download.content == content
    assert download.headers['content-disposition'].startswith('inline;')
    assert client.post(f"/api/v1/documents/{doc['id']}/process", headers=headers).status_code == 202
    db_session.expire_all()
    assert [c.id for c in db_session.get(Document, doc['id']).chunks] == original_ids


def test_other_user_cannot_access_a_private_book(client, db_session, tmp_path):
    admin, _ = account(client, 'administrator')
    owner, _ = account(client, 'owner')
    other, _ = account(client, 'other')
    response = upload(client, owner, pdf_bytes(tmp_path))
    doc = response.json()['document']
    url = f"/api/v1/documents/{doc['id']}"
    assert client.get(url).status_code == 404
    assert client.get(url, headers=owner).json()['can_modify'] is True
    assert client.get(url, headers=other).status_code == 404
    from app.models.user import User
    administrator = db_session.query(User).filter_by(email='administrator@example.com').one()
    administrator.role = 'admin'
    db_session.commit()
    assert client.get(url, headers=admin).status_code == 404
    assert client.post(url + '/process', headers=other).status_code == 404
    assert client.delete(url, headers=other).status_code == 404
    assert client.delete(url).status_code == 401
    assert client.get(url + '/download').status_code == 404
    assert client.delete(url, headers=owner).status_code == 200
    assert client.get(url).status_code == 404


def test_pdf_head_and_ranges_share_download_authorization(client, db_session, tmp_path):
    owner, _ = account(client, 'head-owner')
    other, _ = account(client, 'head-other')
    content = pdf_bytes(tmp_path)
    doc = upload(client, owner, content).json()['document']
    path = f"/api/v1/documents/{doc['id']}/download"
    head = client.head(path, headers=owner)
    assert head.status_code == 200 and head.content == b''
    assert int(head.headers['content-length']) == len(content)
    assert head.headers['content-type'] == 'application/pdf'
    assert head.headers['cache-control'] == 'private, no-store'
    assert 'authorization' in head.headers['vary'].lower()
    assert client.head(path).status_code == client.head(path, headers=other).status_code == 404
    partial = client.get(path, headers=owner | {'Range': 'bytes=0-9'})
    assert partial.status_code == 206 and partial.content == content[:10]
    assert partial.headers['content-range'] == f'bytes 0-9/{len(content)}'


def test_upload_limits_and_real_pdf_header(client, tmp_path, monkeypatch):
    headers, _ = account(client, 'owner')
    assert upload(client, headers, b'not really a PDF').status_code == 400
    assert upload(client, headers, b'').status_code == 400
    content = pdf_bytes(tmp_path)
    monkeypatch.setattr(settings, 'MAX_PDF_BYTES', len(content) - 1)
    assert upload(client, headers, content).status_code == 413
    assert client.get('/api/v1/documents').json() == []
    assert not list(storage_service.base_dir.glob('*_sample.pdf'))


def test_upload_storage_failure_does_not_create_record(client, tmp_path, monkeypatch):
    headers, _ = account(client, 'owner')
    def unavailable(*args):
        raise StorageError('internal private path')
    monkeypatch.setattr(storage_service, 'save_file', unavailable)
    response = upload(client, headers, pdf_bytes(tmp_path))
    assert response.status_code == 503 and 'internal private' not in response.text
    assert client.get('/api/v1/documents').json() == []


def test_delete_storage_failure_retains_record(client, tmp_path, monkeypatch):
    headers, _ = account(client, 'owner')
    doc = upload(client, headers, pdf_bytes(tmp_path)).json()['document']
    from app.services import deletion_service
    replace = deletion_service.os.replace
    def unavailable(source, target):
        if str(source).endswith('.pdf'):
            raise OSError('internal private path')
        return replace(source, target)
    monkeypatch.setattr(deletion_service.os, 'replace', unavailable)
    response = client.delete(f"/api/v1/documents/{doc['id']}", headers=headers)
    assert response.status_code == 503
    assert client.get(f"/api/v1/documents/{doc['id']}", headers=headers).status_code == 200


def test_failed_background_job_can_be_retried(client, tmp_path, monkeypatch):
    headers, _ = account(client, 'owner')
    content = pdf_bytes(tmp_path)
    def failed(*args, **kwargs):
        raise RuntimeError('parser unavailable')
    with monkeypatch.context() as patch:
        patch.setattr('app.services.pdf_service.pdf_service.extract_document_info', failed)
        response = upload(client, headers, content, process=True)
    doc_id = response.json()['document']['id']
    assert client.get(f'/api/v1/documents/{doc_id}', headers=headers).json()['status'] == 'error'
    assert ingestion_jobs.is_active(doc_id) is False
    assert client.get(f'/api/v1/documents/{doc_id}/download', headers=headers).content == content
    assert client.post(f'/api/v1/documents/{doc_id}/process', headers=headers).status_code == 202
    assert client.get(f'/api/v1/documents/{doc_id}', headers=headers).json()['status'] == 'partial'


def test_busy_jobs_protect_documents_and_report_capacity(client, db_session, tmp_path, monkeypatch):
    monkeypatch.setattr(ingestion_jobs, '_active', set())
    monkeypatch.setattr(settings, 'MAX_INGESTION_JOBS', 1)
    headers, _ = account(client, 'owner')
    content = pdf_bytes(tmp_path)
    first = upload(client, headers, content).json()['document']
    pending_tasks = BackgroundTasks()  # deliberately not executed in this admission test
    ingestion_jobs.schedule(db_session, db_session.get(Document, first['id']), pending_tasks)
    assert client.post(f"/api/v1/documents/{first['id']}/process", headers=headers).status_code == 409
    assert client.delete(f"/api/v1/documents/{first['id']}", headers=headers).status_code == 409
    second = upload(client, headers, content, process=True)
    assert second.status_code == 201 and second.json()['processing_scheduled'] is False
    doc_id = second.json()['document']['id']
    response = client.post(f'/api/v1/documents/{doc_id}/process', headers=headers)
    assert response.status_code == 503 and response.headers['retry-after'] == '5'


@pytest.mark.parametrize('name', ['../escape.pdf', r'..\escape.pdf', 'C:escape.pdf', '..', ''])
def test_storage_rejects_path_escape(name):
    with pytest.raises(ValueError):
        storage_service.get_file_path(name)


def test_failed_write_cleans_partial_file():
    class FailingStream:
        calls = 0
        def read(self, size):
            self.calls += 1
            if self.calls == 1:
                return b'%PDF-partial'
            raise OSError('disk read failed')
    with pytest.raises(StorageError):
        storage_service.save_file(FailingStream(), 'broken.pdf')
    assert not storage_service.file_exists('broken.pdf')


def test_storage_never_overwrites_existing_pdf():
    storage_service.save_file(io.BytesIO(b'original PDF bytes'), 'existing.pdf')
    with pytest.raises(StorageError):
        storage_service.save_file(io.BytesIO(b'replacement'), 'existing.pdf')
    assert (storage_service.base_dir / 'existing.pdf').read_bytes() == b'original PDF bytes'
