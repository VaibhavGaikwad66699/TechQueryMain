"""Fault injection uses isolated storage/database; never calls an AI provider."""
import asyncio
import io
import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import Mock

import pytest
from fastapi import HTTPException
from starlette.formparsers import MultiPartParser
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.config import settings, BASE_DIR
from app.models.document import Document, ExtractionCheckpoint, ExtractionPage
from app.services import ingestion_jobs, deletion_service
from app.services.extraction_service import file_digest
from app.services.file_locks import document_lock, file_lock, LockBusy
from app.services.index_service import process_document, index_coverage
from app.services.pdf_service import pdf_service, bounded_output
from app.services.storage_service import storage_service, StorageError
from app.services.upload_limits import UploadBodyLimit
from tests.test_indexing import create_book
from tests.test_document_workflow import account, upload, pdf_bytes


def interrupt_after_first(monkeypatch):
    original = pdf_service.iter_pages
    def interrupted(*args, **kwargs):
        yield next(original(*args, **kwargs))
        raise TimeoutError('simulated interruption')
    monkeypatch.setattr(pdf_service, 'iter_pages', interrupted)


def test_page_checkpoint_resumes_without_replacing_published_text(db_session, monkeypatch):
    doc = create_book(db_session)
    process_document(db_session, doc.id, max_chunks=0)
    before = [(c.id, c.content, c.embedding_json) for c in doc.chunks]
    # A forced fresh extraction can fail without destroying the published snapshot.
    for chunk in doc.chunks:
        chunk.metadata_json = '{}'
    db_session.commit()
    with monkeypatch.context() as patch:
        interrupt_after_first(patch)
        with pytest.raises(TimeoutError):
            process_document(db_session, doc.id, max_chunks=0)
    assert doc.status == 'pending'
    assert [(c.id, c.content, c.embedding_json) for c in doc.chunks] == before
    checkpoint = db_session.get(ExtractionCheckpoint, doc.id)
    assert checkpoint.last_page == 1 and not checkpoint.complete
    original = pdf_service.iter_pages
    calls = []
    def resumed(path, total, start, extractor):
        calls.append((start, extractor))
        yield from original(path, total, start, extractor)
    monkeypatch.setattr(pdf_service, 'iter_pages', resumed)
    process_document(db_session, doc.id, max_chunks=0)
    assert calls == [(2, checkpoint.extractor)]
    assert [(c.id, c.content, c.embedding_json) for c in doc.chunks] == before
    assert checkpoint.complete and checkpoint.last_page == 3
    assert db_session.query(ExtractionPage).count() == 0


def test_background_interruption_is_visible_and_resumable(client, tmp_path, monkeypatch):
    headers, _ = account(client, 'owner')
    with monkeypatch.context() as patch:
        interrupt_after_first(patch)
        response = upload(client, headers, pdf_bytes(tmp_path), process=True)
    ident = response.json()['document']['id']
    detail = client.get(f'/api/v1/documents/{ident}', headers=headers).json()
    assert detail['status'] == 'pending' and detail['processing_active'] is False
    assert detail['indexing']['extraction']['saved_pages'] == 1
    assert 'page 1 of 2' in detail['error_message']
    assert client.post(f'/api/v1/documents/{ident}/process', headers=headers).status_code == 202
    assert client.get(f'/api/v1/documents/{ident}', headers=headers).json()['status'] == 'partial'


def test_stale_job_recovery_respects_live_os_lock(db_session, monkeypatch):
    doc = create_book(db_session)
    doc.status = 'processing'
    db_session.commit()
    monkeypatch.setattr(ingestion_jobs, '_active', set())
    provider = Mock(side_effect=AssertionError('Recovery must not call Gemini'))
    monkeypatch.setattr('app.services.embedding_service.embedding_service.generate_embeddings_batch', provider)
    with document_lock(doc.id):
        assert ingestion_jobs.recover_interrupted(db_session) == 0
        assert doc.status == 'processing'
    assert ingestion_jobs.recover_interrupted(db_session) == 1
    assert doc.status == 'pending'
    provider.assert_not_called()


def test_changed_pdf_discards_only_unpublished_checkpoint(db_session, monkeypatch):
    doc = create_book(db_session)
    with monkeypatch.context() as patch:
        interrupt_after_first(patch)
        with pytest.raises(TimeoutError):
            process_document(db_session, doc.id, max_chunks=0)
    from seed_sample_docs import make_simple_pdf
    make_simple_pdf([['Replacement text explains deterministic resource management and cleanup.']], storage_service.base_dir / doc.filename)
    process_document(db_session, doc.id, max_chunks=0)
    assert len(doc.chunks) == 1 and 'Replacement' in doc.chunks[0].content
    assert doc.extraction_checkpoint.last_page == 1


def test_blank_physical_pages_keep_citations_and_pypdf_fallback(db_session, monkeypatch):
    doc = create_book(db_session)
    from seed_sample_docs import make_simple_pdf
    make_simple_pdf([['The first chapter describes safe memory ownership in modern C++.'], [],
        ['The third chapter describes deterministic destruction at the end of scope.']], storage_service.base_dir / doc.filename)
    monkeypatch.setattr(pdf_service, 'extractor', lambda: 'pypdf')
    process_document(db_session, doc.id, max_chunks=0)
    assert doc.total_pages == 3
    assert [c.page_number for c in doc.chunks] == [1, 3]
    assert index_coverage(doc)['extraction']['saved_pages'] == 3


@pytest.mark.parametrize('mode', ['timeout', 'output'])
def test_parser_subprocess_limits(monkeypatch, mode):
    monkeypatch.setattr(settings, 'PDF_EXTRACT_TIMEOUT_SECONDS', .1 if mode == 'timeout' else 5)
    monkeypatch.setattr(settings, 'PDF_MAX_BATCH_OUTPUT_BYTES', 1024)
    code = 'import time; time.sleep(10)' if mode == 'timeout' else 'import sys; sys.stdout.write("x" * 4096)'
    with pytest.raises(TimeoutError if mode == 'timeout' else ValueError):
        bounded_output([sys.executable, '-c', code])


def test_page_and_text_limits_preserve_saved_state(db_session, monkeypatch):
    doc = create_book(db_session)
    with monkeypatch.context() as patch:
        patch.setattr(settings, 'PDF_MAX_PAGES', 2)
        with pytest.raises(ValueError, match='page limit'):
            process_document(db_session, doc.id, max_chunks=0)
    assert not doc.chunks
    monkeypatch.setattr(settings, 'PDF_MAX_TEXT_BYTES', 90)
    with pytest.raises(ValueError, match='size limit'):
        process_document(db_session, doc.id, max_chunks=0)
    assert doc.extraction_checkpoint.last_page == 1
    assert not doc.chunks


def test_partial_upload_cleanup_skips_active_writer(monkeypatch):
    directory = storage_service.base_dir / '.upload-parts'
    directory.mkdir()
    active, stale = directory / 'active.part', directory / 'stale.part'
    active.write_bytes(b'partial'); stale.write_bytes(b'partial')
    with file_lock(active.with_suffix('.lock')):
        storage_service.recover_upload_parts()
        assert active.exists() and not stale.exists()
    storage_service.recover_upload_parts()
    assert not active.exists()
    monkeypatch.setattr(settings, 'MAX_PDF_BYTES', 4)
    with pytest.raises(StorageError):
        storage_service.save_file(io.BytesIO(b'too large'), 'large.pdf')
    assert not list(directory.glob('*.part'))
    assert not (storage_service.base_dir / 'large.pdf').exists()


def test_chunked_upload_limit_closes_spooled_files(monkeypatch):
    monkeypatch.setattr(settings, 'MAX_PDF_BYTES', 1024)
    import starlette.formparsers as parsers
    actual = parsers.SpooledTemporaryFile
    opened = []
    def tracked(*args, **kwargs):
        stream = actual(*args, **kwargs); opened.append(stream); return stream
    monkeypatch.setattr(parsers, 'SpooledTemporaryFile', tracked)
    async def app(scope, receive, send):
        from starlette.exceptions import HTTPException as StarletteHTTPException
        try:
            await Request(scope, receive).form()
            response = JSONResponse({'unexpected': True})
        except StarletteHTTPException:
            response = JSONResponse({'detail': 'too large'}, status_code=400)
        except parsers.MultiPartException:
            response = JSONResponse({'detail': 'too large'}, status_code=400)
        await response(scope, receive, send)
    scope = {'type': 'http', 'method': 'POST', 'path': '/api/v1/documents/upload',
        'headers': [(b'content-type', b'multipart/form-data; boundary=test')], 'query_string': b''}
    prefix = b'--test\r\nContent-Disposition: form-data; name="file"; filename="large.pdf"\r\nContent-Type: application/pdf\r\n\r\n'
    chunks = [prefix, b'x' * (1024 * 1024), b'x' * 2048, b'unread ending']
    consumed, messages = [], []
    async def receive():
        consumed.append(1)
        return {'type': 'http.request', 'body': chunks[len(consumed)-1], 'more_body': True}
    async def send(message):
        messages.append(message)
    asyncio.run(UploadBodyLimit(app)(scope, receive, send))
    assert messages[0]['status'] == 413
    assert len(consumed) == 3 and opened and all(stream.closed for stream in opened)


def staged(db, doc):
    directory = storage_service.base_dir / (deletion_service.PREFIX + 'crash')
    directory.mkdir()
    source = storage_service.base_dir / doc.filename
    deletion_service._write_journal(directory, [{'document_id': doc.id, 'filename': doc.filename, 'sha256': file_digest(source)}])
    os.replace(source, directory / doc.filename)
    return directory


@pytest.mark.parametrize('committed', [False, True])
def test_crashed_deletion_recovery_is_idempotent(db_session, committed):
    doc = create_book(db_session)
    content = (storage_service.base_dir / doc.filename).read_bytes()
    directory = staged(db_session, doc)
    if committed:
        db_session.delete(doc); db_session.commit()
    assert deletion_service.recover_deletions(db_session)['recovered'] == 1
    assert not directory.exists()
    source = storage_service.base_dir / doc.filename
    assert source.exists() is not committed
    if not committed:
        assert source.read_bytes() == content
    assert deletion_service.recover_deletions(db_session)['recovered'] == 0


def test_failed_rollback_restoration_retries_after_storage_recovers(db_session, monkeypatch):
    doc = create_book(db_session)
    content = (storage_service.base_dir / doc.filename).read_bytes()
    replace = os.replace
    def failed_restore(source, target):
        if str(source).endswith('.pdf') and Path(source).parent.name.startswith(deletion_service.PREFIX):
            raise OSError('temporarily locked')
        return replace(source, target)
    with monkeypatch.context() as patch:
        patch.setattr(db_session, 'commit', Mock(side_effect=RuntimeError('database unavailable')))
        patch.setattr(deletion_service.os, 'replace', failed_restore)
        with pytest.raises(HTTPException) as error:
            deletion_service.delete_books(db_session, [doc])
        assert error.value.status_code == 503
    assert db_session.get(Document, doc.id) is not None
    assert list(storage_service.base_dir.glob(deletion_service.PREFIX + '*/journal.json'))
    assert deletion_service.recover_deletions(db_session)['recovered'] == 1
    assert (storage_service.base_dir / doc.filename).read_bytes() == content


def test_cleanup_failure_retries_without_resurrecting_deleted_document(db_session, monkeypatch):
    doc = create_book(db_session)
    process_document(db_session, doc.id, max_chunks=0)
    ident = doc.id
    unlink = Path.unlink
    def failed_cleanup(path, *args, **kwargs):
        if path.name.endswith('.pdf') and path.parent.name.startswith(deletion_service.PREFIX):
            raise OSError('temporarily locked')
        return unlink(path, *args, **kwargs)
    with monkeypatch.context() as patch:
        patch.setattr(Path, 'unlink', failed_cleanup)
        assert deletion_service.delete_books(db_session, [doc]) is True
    assert db_session.get(Document, ident) is None
    assert db_session.query(ExtractionCheckpoint).count() == 0
    assert deletion_service.recover_deletions(db_session)['recovered'] == 1
    assert not (storage_service.base_dir / 'test.pdf').exists()


@pytest.mark.parametrize('tamper', ['fingerprint', 'path', 'default', 'extra_file', 'invalid_json_type'])
def test_recovery_fails_closed_on_unsafe_journal(db_session, tamper):
    doc = create_book(db_session)
    directory = staged(db_session, doc)
    if tamper == 'fingerprint':
        (directory / doc.filename).write_bytes(b'different PDF')
    elif tamper == 'path':
        journal = directory / 'journal.json'
        data = json.loads(journal.read_text()); data['entries'][0]['filename'] = '../escape.pdf'
        journal.write_text(json.dumps(data))
    elif tamper == 'default':
        doc.is_default = True; db_session.commit()
    elif tamper == 'extra_file':
        (directory / 'unknown.txt').write_text('keep this')
    else:
        (directory / 'journal.json').write_text('[]')
    assert deletion_service.recover_deletions(db_session)['pending'] == 1
    assert (directory / 'journal.json').exists() and (directory / 'test.pdf').exists()


def test_deleting_interrupted_pdf_removes_only_its_staging(db_session, monkeypatch):
    doc = create_book(db_session)
    with monkeypatch.context() as patch:
        interrupt_after_first(patch)
        with pytest.raises(TimeoutError):
            process_document(db_session, doc.id, max_chunks=0)
    assert db_session.query(ExtractionPage).count() == 1
    deletion_service.delete_books(db_session, [doc])
    assert db_session.query(ExtractionPage).count() == 0
    assert db_session.query(ExtractionCheckpoint).count() == 0


def test_killed_process_releases_document_lock(db_session):
    doc = create_book(db_session)
    lock_path = storage_service.base_dir / '.processing-locks' / f'{doc.id}.lock'
    code = ('import os,sys; from pathlib import Path; '
        'from app.services.file_locks import file_lock; '
        'lock=file_lock(Path(sys.argv[1])); lock.__enter__(); '
        'os._exit(17)')
    child = subprocess.run([sys.executable, '-c', code, str(lock_path)], cwd=BASE_DIR, timeout=10)
    assert child.returncode == 17
    with document_lock(doc.id):
        with pytest.raises(LockBusy):
            with document_lock(doc.id):
                pass


@pytest.mark.parametrize('committed', [False, True])
def test_process_exit_during_deletion_recovers_from_disk(tmp_path, committed):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from app.database.session import Base
    engine = create_engine('sqlite:///' + (tmp_path / 'crash.sqlite3').as_posix())
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        doc = create_book(db)
        ident = doc.id
        content = (storage_service.base_dir / doc.filename).read_bytes()
    code = '''
import os, sys
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
import app.models
from app.models.document import Document
from app.services.storage_service import storage_service
from app.services.deletion_service import _write_journal
from app.services.extraction_service import file_digest
from app.services.file_locks import document_lock
storage_service.base_dir = Path(sys.argv[2])
with Session(create_engine(sys.argv[1])) as db, document_lock(int(sys.argv[3])):
    doc = db.get(Document, int(sys.argv[3]))
    directory = storage_service.base_dir / '.subject-delete-exited'
    directory.mkdir()
    source = storage_service.base_dir / doc.filename
    _write_journal(directory, [{'document_id': doc.id, 'filename': doc.filename, 'sha256': file_digest(source)}])
    os.replace(source, directory / doc.filename)
    if sys.argv[4] == 'yes':
        db.delete(doc)
        db.commit()
    os._exit(17)
'''
    result = subprocess.run([sys.executable, '-c', code, str(engine.url), str(tmp_path), str(ident),
        'yes' if committed else 'no'], cwd=BASE_DIR, timeout=15)
    assert result.returncode == 17
    with Session(engine) as db:
        assert deletion_service.recover_deletions(db)['recovered'] == 1
        assert (db.get(Document, ident) is None) is committed
        source = storage_service.base_dir / 'test.pdf'
        assert source.exists() is not committed
        if not committed:
            assert source.read_bytes() == content
    engine.dispose()


def test_failed_publication_retains_chunks_and_resumes_without_rereading(db_session, monkeypatch):
    doc = create_book(db_session)
    process_document(db_session, doc.id, max_chunks=0)
    before = [(c.id, c.content, c.embedding_json) for c in doc.chunks]
    for chunk in doc.chunks:
        chunk.metadata_json = '{}'
    db_session.commit()
    commit = db_session.commit
    def failed_publication():
        checkpoint = db_session.get(ExtractionCheckpoint, doc.id)
        if checkpoint and checkpoint in db_session.dirty and checkpoint.complete:
            raise RuntimeError('commit unavailable')
        commit()
    with monkeypatch.context() as patch:
        patch.setattr(db_session, 'commit', failed_publication)
        with pytest.raises(RuntimeError):
            process_document(db_session, doc.id, max_chunks=0)
    assert [(c.id, c.content, c.embedding_json) for c in doc.chunks] == before
    assert not doc.extraction_checkpoint.complete and doc.extraction_checkpoint.last_page == 3
    original = pdf_service.iter_pages
    def no_reread(path, total, start, extractor):
        assert start == total + 1
        yield from original(path, total, start, extractor)
    monkeypatch.setattr(pdf_service, 'iter_pages', no_reread)
    process_document(db_session, doc.id, max_chunks=0)
    assert doc.extraction_checkpoint.complete
