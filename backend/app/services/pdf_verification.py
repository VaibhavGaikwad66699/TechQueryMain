"""Fresh physical-page text checks, preserving extractor reading-order differences."""
import os
import re
import subprocess
import unicodedata


def normalized_passage_in_page(passage, page_text):
    def normalize(text):
        return re.sub(r'\s+', ' ', unicodedata.normalize('NFKC', text)).strip()
    return bool(normalize(passage)) and normalize(passage) in normalize(page_text)


def fresh_pdftotext_page(path, page_number, executable):
    if page_number < 1:
        raise ValueError('Physical PDF page must be positive')
    run = subprocess.run([str(executable), '-f', str(page_number), '-l', str(page_number),
        '-enc', 'UTF-8', str(path), '-'], capture_output=True, timeout=30,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    if run.returncode != 0:
        raise ValueError(f'Fresh page extraction failed with exit code {run.returncode}')
    return run.stdout.decode('utf-8')
