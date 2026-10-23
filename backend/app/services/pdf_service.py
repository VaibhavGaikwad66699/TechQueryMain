import re
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Dict, List, Any
import pypdf
from app.core.config import settings, BASE_DIR


def bounded_output(command):
    """Bound parser lifetime/output outside the API process; do not expose stderr."""
    flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    with tempfile.TemporaryFile() as output:
        with subprocess.Popen(command, stdout=output, stderr=subprocess.DEVNULL,
                cwd=str(BASE_DIR), creationflags=flags) as child:
            deadline = time.monotonic() + settings.PDF_EXTRACT_TIMEOUT_SECONDS
            try:
                while child.poll() is None:
                    if time.monotonic() > deadline:
                        raise TimeoutError('PDF reading took too long. Saved pages are retained; retry or use a simpler PDF.')
                    if os.fstat(output.fileno()).st_size > settings.PDF_MAX_BATCH_OUTPUT_BYTES:
                        raise ValueError('PDF text exceeds the per-batch extraction limit.')
                    time.sleep(.05)
                if child.returncode:
                    raise ValueError('Could not read this PDF. It may be damaged or password-protected.')
                output.seek(0)
                data = output.read(settings.PDF_MAX_BATCH_OUTPUT_BYTES + 1)
                if len(data) > settings.PDF_MAX_BATCH_OUTPUT_BYTES:
                    raise ValueError('PDF text exceeds the per-batch extraction limit.')
                return data
            finally:
                if child.poll() is None:
                    child.kill()
                    child.wait()

class PDFChunk:
    def __init__(self, content: str, page_number: int, chunk_index: int, token_count: int, metadata: Dict[str, Any] = None):
        self.content = content
        self.page_number = page_number
        self.chunk_index = chunk_index
        self.token_count = token_count
        self.metadata = metadata or {}

class PDFService:
    """
    Handles PDF text extraction, metadata parsing, and semantic text chunking.
    """

    @staticmethod
    def extract_document_info(file_path: str) -> Dict[str, Any]:
        """Extract metadata and page count from a PDF file."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"PDF file not found at {file_path}")

        result = json.loads(bounded_output([sys.executable, '-m', 'app.services.pdf_worker', str(path.resolve()), '--info']))
        if not 1 <= result['total_pages'] <= settings.PDF_MAX_PAGES:
            raise ValueError('PDF exceeds the configured page limit or has no pages.')
        result['title'] = result['title'] or path.stem
        return result

    @staticmethod
    def extractor():
        binary = settings.PDFTOTEXT_PATH or shutil.which('pdftotext')
        if not binary and os.name == 'nt':
            candidate = Path(os.environ.get('ProgramFiles', 'C:/Program Files')) / 'Git/mingw64/bin/pdftotext.exe'
            binary = str(candidate) if candidate.is_file() else None
        return 'pdftotext' if binary else 'pypdf'

    @staticmethod
    def iter_pages(file_path, total_pages, start_page=1, extractor=None):
        engine = extractor or PDFService.extractor()
        path = str(Path(file_path).resolve())
        for first in range(start_page, total_pages + 1, settings.PDF_EXTRACT_BATCH_PAGES):
            last = min(total_pages, first + settings.PDF_EXTRACT_BATCH_PAGES - 1)
            if engine == 'pdftotext':
                binary = settings.PDFTOTEXT_PATH or shutil.which('pdftotext')
                if not binary and os.name == 'nt':
                    binary = str(Path(os.environ.get('ProgramFiles', 'C:/Program Files')) / 'Git/mingw64/bin/pdftotext.exe')
                raw = bounded_output([str(binary), '-f', str(first), '-l', str(last), '-enc', 'UTF-8', path, '-'])
                pages = raw.decode('utf-8').split('\f')
                if pages and not pages[-1].strip():
                    pages.pop()
            elif engine == 'pypdf':
                pages = json.loads(bounded_output([sys.executable, '-m', 'app.services.pdf_worker', path,
                    '--first', str(first), '--last', str(last)]))
            else:
                raise ValueError('Unsupported saved PDF extractor.')
            if len(pages) != last - first + 1:
                raise ValueError('PDF extractor returned an inconsistent physical page count.')
            for offset, text in enumerate(pages):
                yield first + offset, text

    @staticmethod
    def extract_and_chunk(
        file_path: str,
        chunk_size: int = 800,
        chunk_overlap: int = 150
    ) -> List[PDFChunk]:
        """
        Extract text page-by-page and chunk it while preserving exact page numbers.
        """
        reader = pypdf.PdfReader(file_path)
        all_chunks: List[PDFChunk] = []
        global_chunk_idx = 0

        for page_idx, page in enumerate(reader.pages):
            page_num = page_idx + 1
            page_text = page.extract_text() or ""
            # Clean up excessive whitespace and control characters
            page_text = re.sub(r'\s+', ' ', page_text).strip()
            if not page_text:
                continue

            # Chunk the page text with overlap
            page_chunks = PDFService._split_text(page_text, chunk_size, chunk_overlap)
            for chunk_str in page_chunks:
                if len(chunk_str.strip()) < 30:
                    continue  # skip tiny meaningless fragments
                approx_tokens = max(1, len(chunk_str.split()))
                all_chunks.append(PDFChunk(
                    content=chunk_str,
                    page_number=page_num,
                    chunk_index=global_chunk_idx,
                    token_count=approx_tokens,
                    metadata={"page": page_num}
                ))
                global_chunk_idx += 1

        return all_chunks

    @staticmethod
    def _split_text(text: str, chunk_size: int = 800, chunk_overlap: int = 150) -> List[str]:
        """
        Split text into overlapping chunks, attempting to break at sentence boundaries.
        """
        if len(text) <= chunk_size:
            return [text]

        chunks = []
        start = 0
        text_len = len(text)

        while start < text_len:
            end = start + chunk_size
            if end >= text_len:
                chunks.append(text[start:].strip())
                break

            # Look for sentence boundary (.!?) near the end
            breakpoint = text.rfind('. ', start, end)
            if breakpoint == -1 or breakpoint < start + (chunk_size // 2):
                # Look for newline or space
                breakpoint = text.rfind(' ', start, end)
                if breakpoint == -1 or breakpoint < start + (chunk_size // 2):
                    breakpoint = end

            chunk = text[start:breakpoint + 1].strip()
            if chunk:
                chunks.append(chunk)

            # Advance by chunk_size - chunk_overlap
            start = max(start + 1, breakpoint + 1 - chunk_overlap)

        return chunks

pdf_service = PDFService()
