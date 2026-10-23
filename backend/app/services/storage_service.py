import os
import uuid
from abc import ABC, abstractmethod
from pathlib import Path
from typing import BinaryIO
from app.core.config import settings

class StorageError(Exception):
    """A storage operation failed; do not expose local paths to API clients."""

class StorageService(ABC):
    """
    Abstract Storage Service interface.
    Allows easy switching between local disk storage and cloud storage (e.g. S3) in future phases.
    """

    @abstractmethod
    def save_file(self, file_obj: BinaryIO, filename: str) -> str:
        """Save a file and return its storage key/path."""
        pass

    @abstractmethod
    def get_file_path(self, filename: str) -> str:
        """Return the accessible local path of the file."""
        pass

    @abstractmethod
    def delete_file(self, filename: str) -> bool:
        """Delete a file from storage."""
        pass

    @abstractmethod
    def file_exists(self, filename: str) -> bool:
        """Check if file exists in storage."""
        pass

class LocalStorageService(StorageService):
    """
    Local filesystem implementation of StorageService.
    Stores PDFs in the data/documents directory.
    """

    def __init__(self, base_dir: str = None):
        self.base_dir = Path(base_dir or settings.sync_documents_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save_file(self, file_obj: BinaryIO, filename: str) -> str:
        destination = Path(self.get_file_path(filename))
        from app.services.file_locks import file_lock
        directory = self.base_dir / '.upload-parts'
        directory.mkdir(exist_ok=True)
        temporary = directory / (uuid.uuid4().hex + '.part')
        try:
            with file_lock(temporary.with_suffix('.lock')):
                try:
                    size = 0
                    with temporary.open('xb') as buffer:
                        while block := file_obj.read(1024 * 1024):
                            size += len(block)
                            if size > settings.MAX_PDF_BYTES:
                                raise StorageError('PDF exceeds the configured upload limit')
                            buffer.write(block)
                        buffer.flush()
                        os.fsync(buffer.fileno())
                    # Atomic publication without overwriting an existing name.
                    os.link(temporary, destination)
                finally:
                    temporary.unlink(missing_ok=True)
        except Exception as exc:
            raise StorageError('Could not save PDF') from exc
        return str(destination)

    def recover_upload_parts(self):
        from app.services.file_locks import file_lock, LockBusy
        directory = self.base_dir / '.upload-parts'
        if not directory.is_dir() or directory.is_symlink():
            return
        for part in directory.glob('*.part'):
            try:
                with file_lock(part.with_suffix('.lock')):
                    part.unlink(missing_ok=True)
            except (LockBusy, OSError):
                continue  # Never remove a part owned by another active process.

    def get_file_path(self, filename: str) -> str:
        if not filename or filename in (".", "..") or "/" in filename or "\\" in filename or "\x00" in filename or ":" in filename:
            raise ValueError("Invalid storage filename")
        path = self.base_dir / filename
        return str(path)

    def delete_file(self, filename: str) -> bool:
        path = Path(self.get_file_path(filename))
        try:
            path.unlink()
            return True
        except FileNotFoundError:
            return False
        except OSError as exc:
            raise StorageError('Could not delete PDF') from exc

    def file_exists(self, filename: str) -> bool:
        path = Path(self.get_file_path(filename))
        return path.is_file()

# Singleton instance
storage_service = LocalStorageService()
