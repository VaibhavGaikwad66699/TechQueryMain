"""Generate ignored deployment settings/secrets; never print secret values."""
import argparse
import json
import os
from pathlib import Path
import secrets
from urllib.parse import urlsplit
from app.core.config import settings


def prepare(destination, origin=None):
    destination = Path(destination).resolve()
    if destination.exists():
        raise ValueError('Use a new output directory; existing settings and secrets are never overwritten')
    if origin:
        url = urlsplit(origin)
        if url.scheme != 'https' or not url.hostname or url.netloc != url.hostname or url.path or url.query or url.fragment:
            raise ValueError('Use an HTTPS origin with a plain hostname and no trailing slash')
    else:
        origin = 'https://replace-with-your-domain.invalid'
    hostname = urlsplit(origin).hostname
    destination.mkdir(parents=True, mode=0o700)
    secret_dir = destination / 'secrets'
    secret_dir.mkdir(mode=0o700)
    for name, value in [('jwt_secret', secrets.token_urlsafe(64)), ('gemini_api_key', settings.GEMINI_API_KEY.strip())]:
        path = secret_dir / name
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
            stream.write(value + '\n')
    content = '\n'.join([
        '# PRIVATE deployment settings. Set the real domain before use.',
        'ENVIRONMENT=production', 'PUBLIC_ORIGIN=' + origin,
        'SITE_ADDRESS=' + hostname,
        'BACKEND_CORS_ORIGINS=' + json.dumps([origin]),
        'TRUSTED_HOSTS=' + json.dumps([hostname, 'localhost', '127.0.0.1']),
        'SERVE_FRONTEND=true', 'FRONTEND_DIST=/app/frontend/dist',
        'DATABASE_URL=sqlite:////data/live/techquery.db', 'DOCUMENTS_DIR=/data/live/documents',
        'SECRET_KEY_FILE=/run/secrets/jwt_secret', 'GEMINI_API_KEY_FILE=/run/secrets/gemini_api_key',
        'MAX_PDF_BYTES=52428800', 'MAX_INGESTION_JOBS=1',
        'GEMINI_MODEL=' + settings.GEMINI_MODEL, 'EMBEDDING_MODEL=' + settings.EMBEDDING_MODEL,
        'EMBEDDING_DIMENSIONS=' + str(settings.EMBEDDING_DIMENSIONS),
        'INDEX_MAX_CHUNKS_PER_REQUEST=16',
        'RATE_LIMIT_REQUESTS_PER_MINUTE=120', 'RATE_LIMIT_AUTH_PER_MINUTE=10',
        'RATE_LIMIT_QUERIES_PER_MINUTE=12', 'RATE_LIMIT_UPLOADS_PER_MINUTE=4', '',
    ])
    descriptor = os.open(destination / 'production.env', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
        stream.write(content)
    return {'settings_created': True, 'new_jwt_secret': True,
        'gemini_key_copied_locally': bool(settings.GEMINI_API_KEY.strip()), 'domain_configured': not hostname.endswith('.invalid')}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--origin')
    args = parser.parse_args()
    print(json.dumps(prepare(args.output, args.origin)))
