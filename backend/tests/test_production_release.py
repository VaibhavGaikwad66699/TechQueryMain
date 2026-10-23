import asyncio
import json
from pathlib import Path
import secrets
import sqlite3

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.config import Settings, settings
from app.database.session import Base
from app.models.document import Document, DocumentChunk
from app.models.user import User, UserPreference
from app.services import release_service as release
from app.services.file_locks import LockBusy
from app.services.runtime_guard import data_guard
from app.services.production_http import ProductionRateLimit
from app.services.embedding_service import embedding_service
from prepare_production import prepare
from manage_admin import promote


def production(tmp_path, **changes):
    values = dict(ENVIRONMENT='production', SECRET_KEY=secrets.token_urlsafe(64),
        SECRET_KEY_FILE='', GEMINI_API_KEY_FILE='', PUBLIC_ORIGIN='https://study.techquery.app',
        BACKEND_CORS_ORIGINS=['https://study.techquery.app'], TRUSTED_HOSTS=['study.techquery.app'],
        DATABASE_URL='sqlite:///' + (tmp_path / 'techquery.db').as_posix(), DOCUMENTS_DIR=str(tmp_path / 'documents'),
        SERVE_FRONTEND=True, MAX_INGESTION_JOBS=1)
    return Settings(_env_file=None, **(values | changes))


@pytest.mark.parametrize('changes', [
    {'SECRET_KEY': 'techquery-super-secret-local-jwt-key-change-in-production-32bytes'},
    {'SECRET_KEY': 'a' * 64}, {'PUBLIC_ORIGIN': 'http://study.techquery.app'},
    {'PUBLIC_ORIGIN': 'https://study.techquery.app/'}, {'BACKEND_CORS_ORIGINS': ['*']},
    {'TRUSTED_HOSTS': ['*']}, {'SERVE_FRONTEND': False}, {'DATABASE_URL': 'sqlite:///:memory:'},
    {'MAX_INGESTION_JOBS': 2}, {'PUBLIC_ORIGIN': 'https://replace.invalid'},
])
def test_production_rejects_unsafe_configuration(tmp_path, changes):
    with pytest.raises(ValidationError):
        production(tmp_path, **changes)


def test_secret_files_and_no_secret_in_validation_errors(tmp_path):
    secret = secrets.token_urlsafe(64)
    path = tmp_path / 'secret'
    path.write_text(secret)
    assert production(tmp_path, SECRET_KEY='ignored', SECRET_KEY_FILE=str(path)).SECRET_KEY == secret
    with pytest.raises(ValidationError) as error:
        production(tmp_path, SECRET_KEY_FILE=str(tmp_path / 'missing'))
    assert secret not in str(error.value)


def test_environment_generator_never_overwrites_or_prints_secrets(tmp_path):
    destination = tmp_path / 'production'
    result = prepare(destination)
    assert not result['domain_configured']
    assert len((destination / 'secrets/jwt_secret').read_text().strip()) >= 64
    assert 'SECRET_KEY=' not in (destination / 'production.env').read_text()
    with pytest.raises(ValueError):
        prepare(destination)


@pytest.fixture
def source_library(tmp_path, monkeypatch):
    database = tmp_path / 'source/live.db'
    documents = tmp_path / 'source/documents'
    documents.mkdir(parents=True)
    engine = create_engine('sqlite:///' + database.as_posix())
    Base.metadata.create_all(engine)
    defaults = {}
    with Session(engine) as db:
        user = User(email='private@example.com', username='Private', hashed_password='private-password-hash')
        db.add(user); db.flush()
        db.add(UserPreference(user_id=user.id))
        for index, subject in enumerate(('C', 'C++', 'Java', 'Python'), start=1):
            original = subject.replace('+', 'p') + '.pdf'
            stored = 'private-local-name-' + original
            (documents / stored).write_bytes(b'%PDF-fake-test-only-' + subject.encode())
            digest = release.file_digest(documents / stored)
            defaults[subject] = (original, digest)
            doc = Document(id=index, title='Local title', filename=stored, original_filename=original,
                subject=subject, is_default=True, uploaded_by=user.id, status='partial', total_pages=1, total_chunks=1)
            db.add(doc); db.flush()
            content = 'A reference paragraph explains resource ownership and cleanup.'
            meta = {'page': 1, 'source_sha256': digest, 'extraction_version': 0, 'extraction_origin': 'legacy_snapshot',
                'private_email': user.email, 'provider_access': 'google_approved', 'provider_authorization': {
                    'source_sha256': digest, 'provider': 'Google Gemini', 'purposes': ['embeddings', 'answer_generation'],
                    'authorization_reference': 'private conversation with ' + user.email}, 'embedding': embedding_service.provenance(content)}
            db.add(DocumentChunk(document_id=doc.id, chunk_index=0, page_number=1, content=content,
                embedding_json=json.dumps([1.] + [0.] * (settings.EMBEDDING_DIMENSIONS - 1)), metadata_json=json.dumps(meta)))
        private = Document(title='Private Book', filename='private.pdf', original_filename='private.pdf', subject='Java', uploaded_by=user.id)
        db.add(private)
        (documents / 'private.pdf').write_bytes(b'private book')
        db.commit()
    monkeypatch.setattr(release, 'DEFAULT_BOOKS', defaults)
    yield database, documents
    engine.dispose()


def test_default_dataset_keeps_vectors_and_excludes_private_data(source_library, tmp_path):
    database, documents = source_library
    destination = tmp_path / 'defaults'
    result = release.export_defaults(database, documents, destination)
    assert result['kind'] == 'default-library' and result['index_complete']
    assert result['summary']['users'] == result['summary']['user_preferences'] == 0
    assert result['summary']['documents'] == 4 and result['summary']['stored_embeddings'] == 4
    assert not (destination / 'documents/private.pdf').exists()
    with sqlite3.connect(destination / 'techquery.db') as db:
        assert not db.execute('SELECT id FROM documents WHERE uploaded_by IS NOT NULL').fetchall()
        for raw, in db.execute('SELECT metadata_json FROM document_chunks'):
            assert 'private@example.com' not in raw and 'private_email' not in raw
        ids = db.execute('SELECT id,embedding_json,content FROM document_chunks').fetchall()
    with sqlite3.connect(database) as db:
        assert ids == db.execute('SELECT id,embedding_json,content FROM document_chunks').fetchall()
    restored = tmp_path / 'restored'
    release.restore_bundle(destination, restored)
    assert release.verify_bundle(restored)['summary'] == result['summary']


def test_private_backup_restore_keeps_all_tables_and_staged_files(source_library, tmp_path):
    database, documents = source_library
    recovery = documents / '.subject-delete-interrupted'
    recovery.mkdir()
    (recovery / 'journal.json').write_text('{"version":1,"entries":[]}')
    (recovery / 'staged.pdf').write_bytes(b'preserve staged PDF')
    # A filename matching the root manifest must still be inventoried in storage.
    (documents / 'manifest.json').write_text('private storage file')
    backup = tmp_path / 'backup'
    manifest = release.backup_data(database, documents, backup)
    assert manifest['summary']['users'] == 1 and manifest['summary']['documents'] == 5
    restored = tmp_path / 'restored'
    release.restore_bundle(backup, restored)
    assert (restored / 'documents/.subject-delete-interrupted/staged.pdf').read_bytes() == b'preserve staged PDF'
    assert (restored / 'documents/manifest.json').read_text() == 'private storage file'
    with sqlite3.connect(database) as before, sqlite3.connect(restored / 'techquery.db') as after:
        for name in ('users', 'user_preferences', 'documents', 'document_chunks'):
            assert before.execute('SELECT * FROM ' + name).fetchall() == after.execute('SELECT * FROM ' + name).fetchall()


@pytest.mark.parametrize('mutation', ['pdf', 'extra', 'path', 'symlink'])
def test_bundle_verification_rejects_tamper(source_library, tmp_path, mutation):
    database, documents = source_library
    output = tmp_path / 'backup'
    release.backup_data(database, documents, output)
    if mutation == 'pdf':
        (output / 'documents/private.pdf').write_bytes(b'tampered')
    elif mutation == 'extra':
        (output / 'documents/extra.pdf').write_bytes(b'unknown')
    elif mutation == 'path':
        path = output / 'manifest.json'
        manifest = json.loads(path.read_text()); manifest['files']['../escape.pdf'] = {}
        path.write_text(json.dumps(manifest))
    else:
        # Windows installations may lack symlink permission.
        try:
            (output / 'documents/link.pdf').symlink_to(documents / 'private.pdf')
        except OSError:
            pytest.skip('OS does not permit creating symlinks')
    with pytest.raises(ValueError):
        release.verify_bundle(output)
    assert not (tmp_path / 'escaped').exists()


def test_maintenance_refuses_live_lock_and_existing_destination(source_library, tmp_path):
    database, documents = source_library
    with data_guard(database):
        with pytest.raises(LockBusy):
            release.backup_data(database, documents, tmp_path / 'busy')
    assert not (tmp_path / 'busy').exists()
    existing = tmp_path / 'keep'
    existing.mkdir(); (existing / 'keep.txt').write_text('original')
    with pytest.raises(ValueError):
        release.backup_data(database, documents, existing)
    assert (existing / 'keep.txt').read_text() == 'original'


def test_restore_refuses_existing_target(source_library, tmp_path):
    database, documents = source_library
    bundle = tmp_path / 'backup'
    release.backup_data(database, documents, bundle)
    with pytest.raises(ValueError):
        release.restore_bundle(bundle, database.parent)
    assert database.exists()


def test_restore_supports_existing_empty_directory(source_library, tmp_path):
    database, documents = source_library
    bundle = tmp_path / 'backup'
    release.backup_data(database, documents, bundle)
    target = tmp_path / 'fresh_empty_target'
    target.mkdir()
    manifest = release.restore_bundle(bundle, target)
    assert manifest['kind'] == 'full-backup'
    assert (target / 'techquery.db').is_file()
    assert (target / 'documents').is_dir()
    assert release.verify_bundle(target)['summary'] == manifest['summary']


def test_restore_supports_existing_directory_with_lost_and_found(source_library, tmp_path):
    database, documents = source_library
    bundle = tmp_path / 'backup'
    release.backup_data(database, documents, bundle)
    target = tmp_path / 'persistent_mount_target'
    target.mkdir()
    (target / 'lost+found').mkdir()
    manifest = release.restore_bundle(bundle, target)
    assert manifest['kind'] == 'full-backup'
    assert (target / 'lost+found').is_dir()
    assert (target / 'techquery.db').is_file()
    assert release.verify_bundle(target)['summary'] == manifest['summary']


def test_restore_cleans_up_stale_stage_from_interrupted_run(source_library, tmp_path):
    database, documents = source_library
    bundle = tmp_path / 'backup'
    release.backup_data(database, documents, bundle)
    target = tmp_path / 'interrupted_target'
    target.mkdir()
    stale = target / '.restore-stage-prior'
    stale.mkdir()
    (stale / 'partial.tmp').write_text('stale data')
    manifest = release.restore_bundle(bundle, target)
    assert not stale.exists()
    assert (target / 'techquery.db').is_file()
    assert release.verify_bundle(target)['summary'] == manifest['summary']


def test_restore_refuses_directory_with_existing_user_files(source_library, tmp_path):
    database, documents = source_library
    bundle = tmp_path / 'backup'
    release.backup_data(database, documents, bundle)
    target = tmp_path / 'populated_target'
    target.mkdir()
    (target / 'user_data.txt').write_text('preserve this')
    with pytest.raises(ValueError) as exc:
        release.restore_bundle(bundle, target)
    assert 'not empty' in str(exc.value)
    assert (target / 'user_data.txt').read_text() == 'preserve this'
    assert not (target / 'techquery.db').exists()


def test_manage_release_restore_reports_detailed_error(source_library, tmp_path):
    import subprocess, sys
    database, documents = source_library
    bundle = tmp_path / 'backup'
    release.backup_data(database, documents, bundle)
    target = tmp_path / 'non_empty_cli_target'
    target.mkdir()
    (target / 'existing.db').write_text('existing')
    script = Path(__file__).resolve().parent.parent / 'manage_release.py'
    res = subprocess.run([sys.executable, str(script), 'restore', '--bundle', str(bundle), '--target', str(target)],
                         capture_output=True, text=True)
    assert res.returncode == 2
    assert '[manage_release:restore] Maintenance refused (ValueError):' in res.stderr
    assert 'not empty' in res.stderr
    assert 'no existing destination was replaced' in res.stderr



def test_rate_limits_bound_clients_and_ignore_spoofed_forwarded_header(monkeypatch):
    monkeypatch.setattr(settings, 'ENVIRONMENT', 'production')
    monkeypatch.setattr(settings, 'RATE_LIMIT_AUTH_PER_MINUTE', 1)
    monkeypatch.setattr(settings, 'RATE_LIMIT_MAX_CLIENTS', 4)
    calls = []
    async def app(scope, receive, send):
        calls.append(1)
        await send({'type': 'http.response.start', 'status': 200, 'headers': []})
        await send({'type': 'http.response.body', 'body': b'ok'})
    limiter = ProductionRateLimit(app)
    async def request(host, path='/api/v1/auth/login', forwarded='fake'):
        messages = []
        async def send(message): messages.append(message)
        async def receive(): return {'type': 'http.request', 'body': b''}
        await limiter({'type': 'http', 'path': path, 'method': 'POST', 'client': (host, 1000),
            'headers': [(b'x-forwarded-for', forwarded.encode())]}, receive, send)
        return messages[0]['status']
    assert asyncio.run(request('ip-one')) == 200
    assert asyncio.run(request('ip-one', forwarded='another')) == 429
    assert asyncio.run(request('ip-two')) == 200
    assert asyncio.run(request('ip-three')) == 429
    assert len(limiter.clients) <= 4
    assert asyncio.run(request('ip-three', '/api/v1/ready')) == 200


def test_admin_promotion_requires_existing_active_account(db_session):
    with pytest.raises(ValueError):
        promote(db_session, 'absent@example.com')
    user = User(email='operator@example.com', username='Operator', hashed_password='test-hash', is_active=False)
    db_session.add(user); db_session.commit()
    with pytest.raises(ValueError):
        promote(db_session, user.email)
    assert user.role == 'user'
    user.is_active = True; db_session.commit()
    promote(db_session, ' OPERATOR@EXAMPLE.COM ')
    assert user.role == 'admin' and db_session.query(User).count() == 1
