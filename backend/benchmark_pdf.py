"""Bounded extraction timing in a child process; no database writes or provider calls.

Synthetic results are not a guarantee for arbitrary PDFs. A real-file sample does
not establish the runtime or memory of full-book extraction. Outputs stay local.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def child(path, pages):
    import pypdf
    from app.services.pdf_service import pdf_service
    started = time.perf_counter()
    reader = pypdf.PdfReader(str(path))
    total = len(reader.pages)
    if pages:
        import re
        chunks = 0
        for number in pages:
            text = re.sub(r'\s+', ' ', reader.pages[number - 1].extract_text() or '').strip()
            chunks += sum(len(c.strip()) >= 30 for c in pdf_service._split_text(text))
        extracted_pages = len(pages)
    else:
        del reader
        chunks = len(pdf_service.extract_and_chunk(str(path)))
        extracted_pages = total
    print(json.dumps({'result':'passed', 'total_pdf_pages':total,
        'extracted_pages':extracted_pages, 'chunks':chunks,
        'extraction_seconds':round(time.perf_counter()-started,3),
        'peak_memory_bytes':None, 'memory_note':'Peak memory was not measured.'}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--child', type=Path)
    parser.add_argument('--sample-pages', help='Comma-separated physical pages for child mode')
    parser.add_argument('--real-pdf', type=Path)
    parser.add_argument('--output', type=Path, required=False)
    parser.add_argument('--timeout-seconds', type=int, default=60)
    args = parser.parse_args()
    if args.timeout_seconds < 1:
        parser.error('timeout-seconds must be positive')
    if args.child:
        child(args.child, [int(p) for p in args.sample_pages.split(',')] if args.sample_pages else None)
        return
    from seed_sample_docs import make_simple_pdf
    root = Path(__file__).resolve().parent.parent
    work = root / '.local/performance' / str(time.time_ns())
    work.mkdir(parents=True)
    synthetic = work / 'self-authored-500-pages.pdf'
    make_simple_pdf([
        [f'Page {page}: A Java interface defines a contract that implementing classes must satisfy. '
         'A class can implement multiple interfaces using the implements keyword. '
         'An interface describes behavior, and an implementing class supplies method bodies.'] * 6
        for page in range(1,501)
    ], synthetic)
    cases = [('synthetic_500_pages', synthetic, None)]
    if args.real_pdf:
        cases.append(('real_java_sample_only', args.real_pdf.resolve(), '77,253,404,484'))
    report = {'scope':'Extraction only, no database writes or Gemini requests', 'cases':[],
        'limitations':'Synthetic 500-page PDF and optional four-page real sample. Full 982-page extraction and peak memory remain unverified.'}
    env = dict(os.environ, GEMINI_API_KEY='', PYTHONPATH=os.pathsep.join([
        str(root/'backend'),str(root/'backend/.venv/Lib/site-packages')]))
    for label,path,pages in cases:
        command = [sys._base_executable,str(Path(__file__).resolve()),'--child',str(path)]
        if pages:
            command += ['--sample-pages',pages]
        try:
            run = subprocess.run(command,capture_output=True,text=True,env=env,
                timeout=args.timeout_seconds,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
            result = json.loads(run.stdout) if run.returncode==0 else {'result':'failed','exit_code':run.returncode}
        except subprocess.TimeoutExpired:
            result = {'result':'timed_out','timeout_seconds':args.timeout_seconds}
        result.update(case=label,file_bytes=path.stat().st_size)
        report['cases'].append(result)
        print(json.dumps(result),flush=True)
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    return 0 if all(case['result']=='passed' for case in report['cases']) else 1


if __name__ == '__main__':
    raise SystemExit(main())
