from types import SimpleNamespace
import subprocess

import pytest
from app.services.pdf_verification import normalized_passage_in_page, fresh_pdftotext_page


def test_page_check_normalizes_ligatures_and_whitespace_without_changing_word_order():
    assert normalized_passage_in_page('The file is free.', 'The ﬁle\n is free.')
    assert not normalized_passage_in_page('alignment description', 'description alignment')
    assert not normalized_passage_in_page('malloc fails', 'malloc succeeds')
    assert not normalized_passage_in_page('', 'Some page')


def test_fresh_extraction_targets_the_exact_physical_page_without_shell(monkeypatch):
    called = []
    def run(command, **kwargs):
        called.append((command, kwargs))
        return SimpleNamespace(returncode=0, stdout=b'Original page\f')
    monkeypatch.setattr(subprocess, 'run', run)
    assert fresh_pdftotext_page('source.pdf', 267, 'pdftotext.exe') == 'Original page\f'
    assert called[0][0] == ['pdftotext.exe', '-f', '267', '-l', '267', '-enc', 'UTF-8', 'source.pdf', '-']
    assert called[0][1]['timeout'] == 30 and not called[0][1].get('shell')
    with pytest.raises(ValueError):
        fresh_pdftotext_page('source.pdf', 0, 'pdftotext.exe')
