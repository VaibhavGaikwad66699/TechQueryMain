"""Nonblocking, process-owned local locks; the OS releases them after a crash."""
from contextlib import contextmanager
from pathlib import Path
import os


class LockBusy(Exception):
    pass


@contextmanager
def file_lock(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open('a+b')
    acquired = False
    try:
        if os.fstat(handle.fileno()).st_size == 0:
            handle.write(b'0')
            handle.flush()
        handle.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise LockBusy('Operation already active') from exc
        acquired = True
        yield
    finally:
        if acquired:
            handle.seek(0)
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()
    # Never unlink lock files: another process may already have opened that inode.


def document_lock(document_id):
    from app.services.storage_service import storage_service
    return file_lock(storage_service.base_dir / '.processing-locks' / f'{int(document_id)}.lock')
