"""Offline release bundles. Defaults are rebuilt from an allowlist, never a DB scrub."""
from contextlib import contextmanager, closing
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import sqlite3
import tempfile

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from app import models
from app.database.session import Base
from app.database.library_migration import DEFAULT_BOOKS
from app.models.document import Document, DocumentChunk
from app.services.embedding_service import embedding_service, read_metadata
from app.services.extraction_service import file_digest
from app.services.runtime_guard import data_guard

PRIVATE_TABLES = ('users', 'user_preferences', 'conversations', 'messages', 'user_subjects')


def snapshot(database, destination):
    with closing(sqlite3.connect(Path(database).resolve().as_uri() + '?mode=ro', uri=True)) as source:
        with closing(sqlite3.connect(destination)) as target:
            source.backup(target)


@contextmanager
def new_bundle(destination, forbidden=()):
    destination = Path(destination).resolve()
    if destination.exists() or any(destination == Path(root).resolve() or destination.is_relative_to(Path(root).resolve()) for root in forbidden):
        raise ValueError('Use a new output directory outside the live data and storage directories')
    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.release-', dir=destination.parent))
    try:
        yield stage
        # Destination must remain new: never merge with or replace live data.
        if destination.exists():
            raise ValueError('Output already exists')
        os.rename(stage, destination)
    finally:
        if stage.exists():
            if stage.is_symlink() or stage.resolve().parent != destination.parent or not stage.name.startswith('.release-'):
                raise ValueError('Unsafe temporary cleanup path')
            shutil.rmtree(stage)


def inventory(root):
    files = {}
    for path in sorted(Path(root).rglob('*')):
        if path.is_symlink() or (hasattr(path, 'is_junction') and path.is_junction()):
            raise ValueError('Symlinks and junctions are not accepted in data bundles')
        if path.is_file() and path != Path(root) / 'manifest.json':
            files[path.relative_to(root).as_posix()] = {'bytes': path.stat().st_size, 'sha256': file_digest(path)}
    return files


def database_summary(database):
    with closing(sqlite3.connect(Path(database).resolve().as_uri() + '?mode=ro', uri=True)) as db:
        if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok' or db.execute('PRAGMA foreign_key_check').fetchall():
            raise ValueError('Database integrity or foreign-key check failed')
        tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        required = {*PRIVATE_TABLES, 'documents', 'document_chunks', 'extraction_checkpoints', 'extraction_pages'}
        if not required <= tables:
            raise ValueError('Data bundle schema is incomplete')
        result = {table: db.execute('SELECT count(*) FROM ' + table).fetchone()[0] for table in sorted(required)}
        result['stored_embeddings'] = db.execute("SELECT count(*) FROM document_chunks WHERE embedding_json IS NOT NULL AND embedding_json != ''").fetchone()[0]
        return result


def write_manifest(root, kind, **details):
    manifest = {'format': 1, 'kind': kind, 'created_at': datetime.now(timezone.utc).isoformat(),
        'summary': database_summary(root / 'techquery.db'), **details, 'files': inventory(root)}
    (root / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    verify_bundle(root)
    return manifest


def verify_bundle(root):
    root = Path(root).resolve()
    manifest_path = root / 'manifest.json'
    if manifest_path.is_symlink() or manifest_path.stat().st_size > 8 * 1024 * 1024:
        raise ValueError('Invalid bundle manifest')
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    if not isinstance(manifest, dict) or manifest.get('format') != 1 or manifest.get('kind') not in ('default-library', 'full-backup'):
        raise ValueError('Unknown data bundle format')
    files = manifest.get('files')
    if not isinstance(files, dict) or 'techquery.db' not in files:
        raise ValueError('Missing bundle file inventory')
    for name in files:
        path = PurePosixPath(name)
        if not name or '\\' in name or ':' in name or path.is_absolute() or '..' in path.parts or str(path) != name:
            raise ValueError('Unsafe bundle file path')
        if name != 'techquery.db' and not name.startswith('documents/'):
            raise ValueError('Unexpected bundle member')
    if inventory(root) != files:
        raise ValueError('Bundle file set, size or SHA-256 verification failed')
    summary = database_summary(root / 'techquery.db')
    if summary != manifest.get('summary'):
        raise ValueError('Bundle database counts do not match the manifest')
    if manifest['kind'] == 'default-library':
        if any(summary[table] for table in PRIVATE_TABLES) or summary['documents'] != 4 or summary['extraction_pages'] or summary['extraction_checkpoints']:
            raise ValueError('Default library must contain only four completed text snapshots and no personal data')
        with closing(sqlite3.connect((root / 'techquery.db').as_uri() + '?mode=ro', uri=True)) as db:
            records = db.execute('SELECT subject,filename,original_filename,is_default,uploaded_by,total_chunks,total_pages FROM documents').fetchall()
            books = []
            for subject, filename, original, shared, owner, count, pages in records:
                expected = DEFAULT_BOOKS.get(subject)
                if not expected or filename != expected[0] or original != filename or not shared or owner is not None or file_digest(root / 'documents' / filename) != expected[1]:
                    raise ValueError('Default book identity or source fingerprint mismatch')
                chunks = db.execute('SELECT chunk_index,page_number,metadata_json FROM document_chunks WHERE document_id=(SELECT id FROM documents WHERE subject=?) ORDER BY chunk_index', (subject,)).fetchall()
                if not chunks or len(chunks) != count or [c[0] for c in chunks] != list(range(count)) or any(not 1 <= c[1] <= pages or read_metadata(c[2]).get('source_sha256') != expected[1] for c in chunks):
                    raise ValueError('Default book text snapshot is incomplete or unanchored')
                books.append(subject)
            if set(books) != set(DEFAULT_BOOKS) or set(files) != {'techquery.db', *('documents/' + value[0] for value in DEFAULT_BOOKS.values())}:
                raise ValueError('Unexpected default library books or files')
    return manifest


def safe_metadata(chunk, digest):
    original = read_metadata(chunk.metadata_json)
    if original.get('source_sha256') != digest or original.get('extraction_version') not in (0, 1):
        raise ValueError('Default text is not anchored to its source PDF')
    result = {'page': chunk.page_number, 'source_sha256': digest, 'extraction_version': original['extraction_version']}
    if original.get('extraction_origin') == 'legacy_snapshot':
        result['extraction_origin'] = 'legacy_snapshot'
    if original.get('provider_access') == 'local_only':
        result['provider_access'] = 'local_only'
    elif original.get('provider_access') == 'google_approved':
        approval = original.get('provider_authorization', {})
        if approval.get('source_sha256') != digest or approval.get('provider') != 'Google Gemini' or set(approval.get('purposes', [])) != {'embeddings', 'answer_generation'}:
            raise ValueError('Default source approval is inconsistent')
        result.update(provider_access='google_approved', provider_authorization={
            'provider': 'Google Gemini', 'purposes': ['embeddings', 'answer_generation'], 'source_sha256': digest,
            'authorization_reference': 'Approved source library; local authorization conversation omitted from release dataset.'})
    if chunk.embedding_json:
        if embedding_service.compatible_vector(chunk) is None:
            raise ValueError('Default dataset contains an incompatible embedding; no vectors discarded')
        result['embedding'] = original['embedding']
    return json.dumps(result)


def export_defaults(database, documents, destination):
    database, documents = Path(database).resolve(), Path(documents).resolve()
    with data_guard(database), new_bundle(destination, [database.parent, documents]) as stage:
        snapshot(database, stage / 'source.sqlite3')
        source_engine = create_engine('sqlite:///' + (stage / 'source.sqlite3').as_posix())
        target_engine = create_engine('sqlite:///' + (stage / 'techquery.db').as_posix())
        try:
            Base.metadata.create_all(target_engine)
            (stage / 'documents').mkdir()
            with Session(source_engine) as source, Session(target_engine) as target:
                complete = True
                for subject, (filename, digest) in DEFAULT_BOOKS.items():
                    matches = source.query(Document).filter_by(subject=subject, original_filename=filename, is_default=True).all()
                    if len(matches) != 1 or matches[0].status not in ('partial', 'ready'):
                        raise ValueError('Expected one idle, searchable shared default per language')
                    doc = matches[0]
                    # Storage names must be simple keys; never follow a DB path outside storage.
                    if Path(doc.filename).name != doc.filename or '/' in doc.filename or '\\' in doc.filename or ':' in doc.filename:
                        raise ValueError('Unsafe source PDF storage key')
                    pdf = documents / doc.filename
                    if pdf.is_symlink() or file_digest(pdf) != digest:
                        raise ValueError('Default source PDF fingerprint mismatch')
                    chunks = sorted(doc.chunks, key=lambda c: c.chunk_index)
                    if not chunks or len(chunks) != doc.total_chunks or [c.chunk_index for c in chunks] != list(range(len(chunks))):
                        raise ValueError('Default book chunk sequence is incomplete')
                    compatible = sum(embedding_service.compatible_vector(c) is not None for c in chunks)
                    complete = complete and compatible == len(chunks)
                    target.add(Document(id=doc.id, title=subject + ' Notes for Professionals', filename=filename,
                        original_filename=filename, file_size=pdf.stat().st_size, subject=subject,
                        total_pages=doc.total_pages, total_chunks=len(chunks), status='ready' if compatible == len(chunks) else 'partial',
                        error_message=None if compatible == len(chunks) else 'Text searchable; semantic indexing is incomplete.',
                        uploaded_by=None, is_default=True, created_at=doc.created_at))
                    target.flush()
                    for chunk in chunks:
                        target.add(DocumentChunk(id=chunk.id, document_id=doc.id, chunk_index=chunk.chunk_index,
                            page_number=chunk.page_number, content=chunk.content, token_count=chunk.token_count,
                            embedding_json=chunk.embedding_json, metadata_json=safe_metadata(chunk, digest), created_at=chunk.created_at))
                    shutil.copyfile(pdf, stage / 'documents' / filename)
                target.execute(text('CREATE TABLE library_migrations (name VARCHAR(100) PRIMARY KEY)'))
                target.execute(text("INSERT INTO library_migrations VALUES ('private_library_v1')"))
                target.commit()
        finally:
            source_engine.dispose(); target_engine.dispose()
        (stage / 'source.sqlite3').unlink()
        from app.core.config import settings
        return write_manifest(stage, 'default-library', embedding_model=settings.EMBEDDING_MODEL,
            embedding_dimensions=settings.EMBEDDING_DIMENSIONS, index_complete=complete,
            privacy='No users, password hashes, private subjects, history, private PDFs, local filenames or authorization conversations.')


def backup_data(database, documents, destination):
    database, documents = Path(database).resolve(), Path(documents).resolve()
    with data_guard(database), new_bundle(destination, [database.parent, documents]) as stage:
        snapshot(database, stage / 'techquery.db')
        (stage / 'documents').mkdir()
        for source in documents.rglob('*'):
            if source.is_symlink() or (hasattr(source, 'is_junction') and source.is_junction()):
                raise ValueError('Storage symlinks or junctions require operator review')
            if source.is_file() and source.suffix != '.lock':
                target = stage / 'documents' / source.relative_to(documents)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
        return write_manifest(stage, 'full-backup', privacy='PRIVATE: includes accounts, password hashes, history and private PDFs; protect and encrypt off-host.')


def restore_bundle(bundle, destination):
    bundle, destination = Path(bundle).resolve(), Path(destination).resolve()
    if destination == bundle or destination.is_relative_to(bundle) or bundle.is_relative_to(destination):
        raise ValueError('Restore destination cannot be inside or enclose the bundle directory')
    manifest = verify_bundle(bundle)
    created_dest = False
    if not destination.exists():
        destination.mkdir(parents=True, exist_ok=True)
        created_dest = True
    elif not destination.is_dir():
        raise ValueError(f"Destination '{destination}' is not a directory")
    else:
        # Destination already exists as a directory (e.g. /data in Docker or persistent volume mount).
        # Ensure it does not contain existing data or documents; ignore standard mount artifacts like lost+found.
        entries = [p for p in destination.iterdir() if p.name != 'lost+found']
        stale_stages = [p for p in entries if p.name.startswith('.restore-stage-') and p.is_dir()]
        non_stage_entries = [p for p in entries if not (p.name.startswith('.restore-stage-') and p.is_dir())]
        if non_stage_entries:
            raise ValueError(f"Destination directory '{destination}' is not empty; refusing to replace existing data")
        for stale in stale_stages:
            shutil.rmtree(stale, ignore_errors=True)

    stage = Path(tempfile.mkdtemp(prefix='.restore-stage-', dir=destination))
    try:
        for name in manifest['files']:
            target = stage / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(bundle / name, target)
        shutil.copyfile(bundle / 'manifest.json', stage / 'manifest.json')
        verify_bundle(stage)

        # Staged files verified; publish them into destination
        for item in list(stage.iterdir()):
            target_path = destination / item.name
            shutil.move(str(item), str(target_path))
    except Exception:
        if created_dest:
            try:
                shutil.rmtree(stage, ignore_errors=True)
                destination.rmdir()
            except OSError:
                pass
        raise
    finally:
        if stage.exists():
            shutil.rmtree(stage, ignore_errors=True)

    verify_bundle(destination)
    return manifest

