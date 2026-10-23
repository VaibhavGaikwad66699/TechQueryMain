"""Isolated pypdf fallback. The parent enforces output and wall-clock limits."""
import argparse
import json
import pypdf


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('path')
    parser.add_argument('--info', action='store_true')
    parser.add_argument('--first', type=int, default=1)
    parser.add_argument('--last', type=int, default=1)
    args = parser.parse_args()
    reader = pypdf.PdfReader(args.path)
    if reader.is_encrypted and not reader.decrypt(''):
        raise ValueError('Password-protected PDF')
    if args.info:
        metadata = reader.metadata or {}
        result = {'total_pages': len(reader.pages), 'title': str(metadata.get('/Title') or '').strip(),
            'author': str(metadata.get('/Author') or ''), 'subject': str(metadata.get('/Subject') or '')}
    else:
        result = [reader.pages[index].extract_text() or '' for index in range(args.first - 1, args.last)]
    print(json.dumps(result, ensure_ascii=True))


if __name__ == '__main__':
    main()
