"""Idempotent local-only source-book import. No provider client is used here."""
from dataclasses import dataclass
import ctypes
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
import uuid

from app.core.config import settings
from app.core.scope import normalize_language
from app.models.document import Document, DocumentChunk
from app.services.pdf_service import pdf_service
from app.services.provider_access import LOCAL_ONLY
from app.services.storage_service import storage_service


def file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def peak_working_set(process_handle=None):
    """Windows peak resident memory for one process, including a completed child."""
    if os.name != 'nt':
        return None
    from ctypes import wintypes
    size = ctypes.c_size_t
    class Counters(ctypes.Structure):
        _fields_ = [('cb', wintypes.DWORD), ('PageFaultCount', wintypes.DWORD),
            ('PeakWorkingSetSize', size), ('WorkingSetSize', size),
            ('QuotaPeakPagedPoolUsage', size), ('QuotaPagedPoolUsage', size),
            ('QuotaPeakNonPagedPoolUsage', size), ('QuotaNonPagedPoolUsage', size),
            ('PagefileUsage', size), ('PeakPagefileUsage', size)]
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    handle = wintypes.HANDLE(int(process_handle)) if process_handle is not None else kernel.GetCurrentProcess()
    memory = ctypes.WinDLL('psapi', use_last_error=True).GetProcessMemoryInfo
    memory.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
    memory.restype = wintypes.BOOL
    counters = Counters()
    counters.cb = ctypes.sizeof(counters)
    return counters.PeakWorkingSetSize if memory(handle, ctypes.byref(counters), counters.cb) else None


def split_physical_pages(text, total_pages):
    pages = text.split('\f')
    if pages and not pages[-1].strip():
        pages.pop()  # Only remove the trailer, preserving blank physical pages.
    if len(pages) != total_pages:
        raise ValueError(f'Extractor page count mismatch: expected {total_pages}, received {len(pages)}')
    return pages


@dataclass
class ExtractedBook:
    pages: list[str]
    extractor: str
    seconds: float
    child_peak_working_set_bytes: int | None = None


def extract_with_pdftotext(path, total_pages, executable=None, timeout_seconds=120):
    binary = executable or shutil.which('pdftotext')
    if not binary:
        raise RuntimeError('Install pdftotext locally or pass --pdftotext. No cloud fallback is used.')
    flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    version = subprocess.run([str(binary), '-v'], capture_output=True, timeout=10, creationflags=flags)
    lines = (version.stderr + version.stdout).decode('utf-8', errors='replace').splitlines()
    label = next((line[:120] for line in lines if 'pdftotext version' in line.casefold()), 'pdftotext (version unavailable)')
    started = time.perf_counter()
    with subprocess.Popen([str(binary), '-enc', 'UTF-8', str(path), '-'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=flags) as child:
        try:
            stdout, stderr = child.communicate(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            child.kill()
            child.communicate()
            raise TimeoutError(f'Local extraction exceeded {timeout_seconds} seconds') from None
        memory = peak_working_set(getattr(child, '_handle', None)) if os.name == 'nt' else None
        if child.returncode != 0:
            raise ValueError(f'Local PDF extractor failed with exit code {child.returncode}')
    pages = split_physical_pages(stdout.decode('utf-8'), total_pages)
    return ExtractedBook(pages, label, round(time.perf_counter() - started, 3), memory)


def import_source_book(db, source, language, *, extractor=extract_with_pdftotext, **extractor_options):
    source = Path(source).resolve(strict=True)
    language = normalize_language(language, allow_all=False)
    if source.suffix.lower() != '.pdf' or source.stat().st_size > settings.MAX_PDF_BYTES:
        raise ValueError('Source must be a PDF within the upload size limit')
    with source.open('rb') as stream:
        if stream.read(5) != b'%PDF-':
            raise ValueError('Source does not have a PDF header')
    digest = file_sha256(source)
    # Compare content, not filenames: Java may already have a generated storage key.
    for existing in db.query(Document).order_by(Document.id).all():
        stored = Path(storage_service.get_file_path(existing.filename))
        if stored.is_file() and stored.stat().st_size == source.stat().st_size and file_sha256(stored) == digest:
            if existing.subject != language:
                raise ValueError('An identical PDF is registered under a different language; review without relabeling it')
            return {'action': 'preserved_existing', 'document_id': existing.id,
                'language': language, 'title': existing.title, 'source_sha256': digest,
                'total_pages': existing.total_pages, 'total_chunks': existing.total_chunks,
                'no_provider_calls': True}
    info = pdf_service.extract_document_info(str(source))
    extracted = extractor(source, info['total_pages'], **extractor_options)
    if len(extracted.pages) != info['total_pages']:
        raise ValueError('Extractor did not preserve every physical page')
    chunks = []
    for page_number, text in enumerate(extracted.pages, 1):
        normalized = re.sub(r'\s+', ' ', text).strip()
        for content in pdf_service._split_text(normalized):
            if len(content.strip()) >= 30:
                chunks.append((page_number, content))
    if not chunks:
        raise ValueError('No readable text found; OCR is not enabled')
    if file_sha256(source) != digest:
        raise ValueError('Source changed during extraction; import cancelled')
    filename = f'{uuid.uuid4().hex}_{source.name}'
    with source.open('rb') as stream:
        storage_service.save_file(stream, filename)
    try:
        if file_sha256(storage_service.get_file_path(filename)) != digest:
            raise ValueError('Copied PDF does not match its source')
        doc = Document(title=f'{language} Notes for Professionals', filename=filename,
            original_filename=source.name, subject=language, file_size=source.stat().st_size,
            total_pages=info['total_pages'], total_chunks=len(chunks), status='partial',
            error_message='Text searchable locally. Google use is awaiting permission; no embeddings have been generated.')
        db.add(doc)
        db.flush()
        for index, (page, content) in enumerate(chunks):
            metadata = {'page': page, 'source_sha256': digest, 'extraction_version': 1,
                'extraction_origin': 'local_pdftotext', 'extractor': extracted.extractor,
                'provider_access': LOCAL_ONLY}
            db.add(DocumentChunk(document_id=doc.id, chunk_index=index, page_number=page,
                content=content, token_count=max(1, len(content.split())), metadata_json=json.dumps(metadata)))
        document_id = doc.id
        db.commit()
    except Exception:
        db.rollback()
        storage_service.delete_file(filename)  # Only the UUID file created by this import.
        raise
    return {'action': 'imported_local_only', 'document_id': document_id, 'language': language,
        'title': f'{language} Notes for Professionals', 'source_sha256': digest, 'total_pages': info['total_pages'],
        'pages_with_text': sum(bool(re.sub(r'\s+', ' ', page).strip()) for page in extracted.pages),
        'total_chunks': len(chunks), 'extractor': extracted.extractor,
        'extraction_seconds': extracted.seconds,
        'extractor_peak_working_set_bytes': extracted.child_peak_working_set_bytes,
        'import_process_peak_working_set_bytes': peak_working_set(),
        'embedded_chunks': 0, 'provider_use_allowed': False, 'no_provider_calls': True}
