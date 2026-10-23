"""Preview or import the source library locally, without embedding/generation calls."""
import argparse
import json
from pathlib import Path
import sys
import time

from app.core.config import PROJECT_ROOT, settings
from app.database.session import SessionLocal
from app.models.user import User  # Register related SQLAlchemy mappings.
from app.services.source_book_service import import_source_book, file_sha256

SOURCE_BOOKS = {
    'C': ('C', 'CNotesForProfessionals.pdf'),
    'C++': ('C++', 'CPlusPlusNotesForProfessionals.pdf'),
    'Java': ('JAVA', 'JavaNotesForProfessionals.pdf'),
    'Python': ('PYTHON', 'PythonNotesForProfessionals.pdf'),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, default=PROJECT_ROOT / 'source_book')
    parser.add_argument('--languages', nargs='+', choices=list(SOURCE_BOOKS), default=['C', 'C++', 'Python'])
    parser.add_argument('--apply', action='store_true', help='Without this flag only source paths/fingerprints are inspected')
    parser.add_argument('--pdftotext', help='Local executable path, if not on PATH')
    parser.add_argument('--timeout-seconds', type=int, default=120)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if not 1 <= args.timeout_seconds <= 600:
        parser.error('timeout-seconds must be 1..600')
    # An offline process-level override; the on-disk key/configuration is unchanged.
    settings.GEMINI_API_KEY = ''
    result = {'mode': 'apply_local_only' if args.apply else 'preview', 'books': [], 'no_provider_calls': True}
    started = time.perf_counter()
    for language in args.languages:
        folder, filename = SOURCE_BOOKS[language]
        source = args.source_root / folder / filename
        if args.apply:
            with SessionLocal() as db:
                book = import_source_book(db, source, language,
                    executable=args.pdftotext, timeout_seconds=args.timeout_seconds)
        else:
            book = {'language': language, 'source': str(source.resolve()),
                'file_bytes': source.stat().st_size, 'source_sha256': file_sha256(source)}
        result['books'].append(book)
        print(json.dumps(book), flush=True)
        result['elapsed_seconds'] = round(time.perf_counter() - started, 3)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    return 0


if __name__ == '__main__':
    sys.exit(main())
