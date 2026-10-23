"""Same-disk staged deletion with an fsynced journal and idempotent recovery."""
from contextlib import ExitStack
import json
import logging
import os
from pathlib import Path
import tempfile

from fastapi import HTTPException
from app.models.document import Document
from app.services.extraction_service import file_digest
from app.services.file_locks import file_lock, document_lock, LockBusy
from app.services.storage_service import storage_service

logger = logging.getLogger(__name__)
PREFIX = '.subject-delete-'


def _write_journal(directory, entries):
    path = directory / 'journal.json'
    temporary = directory / 'journal.tmp'
    with temporary.open('x', encoding='utf-8') as stream:
        json.dump({'version': 1, 'entries': entries}, stream)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def recover_directory(db, directory, locks_held=False):
    """Database existence determines rollback versus post-commit cleanup."""
    directory = Path(directory)
    root = storage_service.base_dir.resolve()
    if directory.is_symlink() or directory.resolve().parent != root or not directory.name.startswith(PREFIX):
        raise ValueError('Invalid deletion recovery directory')
    journal = directory / 'journal.json'
    if not journal.exists():
        # Older, unjournalled staging is never guessed at or discarded.
        if not list(directory.iterdir()):
            directory.rmdir()
            return
        raise ValueError('Unjournalled deletion files require operator review')
    if journal.is_symlink() or journal.stat().st_size > 8 * 1024 * 1024:
        raise ValueError('Invalid deletion recovery journal')
    data = json.loads(journal.read_text(encoding='utf-8'))
    if not isinstance(data, dict) or data.get('version') != 1 or not isinstance(data.get('entries'), list):
        raise ValueError('Unsupported deletion recovery journal')
    if not locks_held:
        with ExitStack() as locks:
            for ident in sorted({int(entry['document_id']) for entry in data['entries']}):
                locks.enter_context(document_lock(ident))
            return recover_directory(db, directory, locks_held=True)
    validated = []
    names = set()
    for entry in data['entries']:
        filename = entry['filename']
        original = Path(storage_service.get_file_path(filename))
        target = directory / filename
        if filename in names or target.is_symlink() or original.is_symlink():
            raise ValueError('Unsafe deletion recovery entry')
        names.add(filename)
        doc = db.get(Document, entry['document_id'])
        retained = doc is not None and doc.filename == filename
        if retained and doc.is_default:
            raise ValueError('Default books cannot be recovered through deletion journals')
        if target.exists() and file_digest(target) != entry['sha256']:
            raise ValueError('Staged PDF fingerprint mismatch')
        if retained and original.exists() and entry['sha256'] and file_digest(original) != entry['sha256']:
            raise ValueError('Recovery would overwrite a different PDF')
        validated.append((retained, original, target))
    if any(path.name not in names | {'journal.json'} for path in directory.iterdir()):
        raise ValueError('Unexpected deletion staging files require operator review')
    # Validate every entry before touching any file in this transaction.
    for retained, original, target in validated:
        if retained and target.exists() and not original.exists():
            os.replace(target, original)
        elif target.exists():
            target.unlink()
    journal.unlink()
    directory.rmdir()


def recover_deletions(db):
    recovered, pending = 0, 0
    try:
        with file_lock(storage_service.base_dir / '.deletion-recovery.lock'):
            for directory in storage_service.base_dir.glob(PREFIX + '*'):
                if not directory.is_dir():
                    continue
                try:
                    recover_directory(db, directory)
                    recovered += 1
                except (OSError, ValueError, KeyError, TypeError):
                    pending += 1
                    logger.warning('Deletion recovery pending; operator review or storage retry required')
    except LockBusy:
        return {'recovered': 0, 'pending': 0, 'active': True}
    return {'recovered': recovered, 'pending': pending, 'active': False}


def delete_books(db, documents, mutate=None):
    from app.services import ingestion_jobs
    if any(doc.is_default for doc in documents):
        raise HTTPException(status_code=409, detail='Included books cannot be deleted.')
    if any(doc.status == 'processing' or ingestion_jobs.is_active(doc.id) for doc in documents):
        raise HTTPException(status_code=409, detail='Wait for document processing to finish before deleting it.')
    directory = None
    try:
        with ExitStack() as stack:
            stack.enter_context(file_lock(storage_service.base_dir / '.deletion-recovery.lock'))
            for doc in sorted(documents, key=lambda item: item.id):
                stack.enter_context(document_lock(doc.id))
            try:
                if documents:
                    directory = Path(tempfile.mkdtemp(prefix=PREFIX, dir=storage_service.base_dir))
                    entries = []
                    for doc in documents:
                        original = Path(storage_service.get_file_path(doc.filename))
                        entries.append({'document_id': doc.id, 'filename': doc.filename,
                            'sha256': file_digest(original) if original.exists() else None})
                    _write_journal(directory, entries)
                    for entry in entries:
                        original = Path(storage_service.get_file_path(entry['filename']))
                        if original.exists():
                            os.replace(original, directory / entry['filename'])
                if mutate:
                    mutate()
                for doc in documents:
                    db.delete(doc)
                db.commit()
            except Exception as error:
                db.rollback()
                if directory:
                    try:
                        recover_directory(db, directory, locks_held=True)
                    except (OSError, ValueError, KeyError, TypeError):
                        logger.warning('Deletion rollback needs durable recovery on next startup')
                raise HTTPException(status_code=503, detail='Deletion could not finish. Saved records are retained; file recovery will retry on restart.') from error
            if directory:
                try:
                    recover_directory(db, directory, locks_held=True)
                except (OSError, ValueError, KeyError, TypeError):
                    logger.warning('Deletion committed; private file cleanup will retry on restart')
                    return True
            return False
    except LockBusy as error:
        raise HTTPException(status_code=409, detail='A library operation is active. Retry shortly.') from error
