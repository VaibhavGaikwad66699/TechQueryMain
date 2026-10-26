import os
from pathlib import Path, PurePosixPath
from typing import List, Literal
from urllib.parse import urlsplit
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, model_validator
from sqlalchemy.engine import make_url

# Base directory for the backend (d:\Project\backend)
BASE_DIR = Path(__file__).resolve().parent.parent.parent
# Project root (d:\Project)
PROJECT_ROOT = BASE_DIR.parent

class Settings(BaseSettings):
    ENVIRONMENT: Literal['development', 'production'] = 'development'
    PUBLIC_ORIGIN: str = ''
    SERVE_FRONTEND: bool = False
    FRONTEND_DIST: str = str(PROJECT_ROOT / 'frontend' / 'dist')
    TRUSTED_HOSTS: List[str] = ['localhost', '127.0.0.1', 'testserver']
    SECRET_KEY_FILE: str = ''
    GEMINI_API_KEY_FILE: str = ''
    RATE_LIMIT_REQUESTS_PER_MINUTE: int = Field(default=120, ge=1)
    RATE_LIMIT_AUTH_PER_MINUTE: int = Field(default=10, ge=1)
    RATE_LIMIT_QUERIES_PER_MINUTE: int = Field(default=12, ge=1)
    RATE_LIMIT_UPLOADS_PER_MINUTE: int = Field(default=4, ge=1)
    RATE_LIMIT_MAX_CLIENTS: int = Field(default=4096, ge=1)
    PROJECT_NAME: str = "TechQuery — AI-Based Technical Knowledge Assistant"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"

    # Security
    SECRET_KEY: str = "techquery-super-secret-local-jwt-key-change-in-production-32bytes"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    # Database
    DATABASE_URL: str = f"sqlite:///{str((PROJECT_ROOT / 'data' / 'techquery.db').resolve()).replace('\\', '/')}"

    # Documents Storage
    DOCUMENTS_DIR: str = str((PROJECT_ROOT / "data" / "documents").resolve())
    MAX_PDF_BYTES: int = Field(default=50 * 1024 * 1024, ge=1)
    MAX_INGESTION_JOBS: int = Field(default=1, ge=1, le=8)
    PDFTOTEXT_PATH: str = ''
    PDF_EXTRACT_BATCH_PAGES: int = Field(default=25, ge=1, le=100)
    PDF_EXTRACT_TIMEOUT_SECONDS: int = Field(default=60, ge=1, le=600)
    PDF_MAX_PAGES: int = Field(default=3000, ge=1)
    PDF_MAX_BATCH_OUTPUT_BYTES: int = Field(default=16 * 1024 * 1024, ge=1024)
    PDF_MAX_TEXT_BYTES: int = Field(default=64 * 1024 * 1024, ge=1024)

    @property
    def sync_database_url(self) -> str:
        url = make_url(self.DATABASE_URL)
        if url.get_backend_name() == "sqlite" and url.database not in (None, "", ":memory:"):
            path = Path(url.database)
            if not path.is_absolute():
                return str(url.set(database=(PROJECT_ROOT / path).resolve().as_posix()))
        return self.DATABASE_URL

    @property
    def sync_documents_dir(self) -> str:
        if self.DOCUMENTS_DIR.startswith("."):
            return str((PROJECT_ROOT / self.DOCUMENTS_DIR).resolve())
        return self.DOCUMENTS_DIR

    # Gemini AI Configuration
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-3.5-flash-lite"
    EMBEDDING_MODEL: str = "gemini-embedding-001"
    EMBEDDING_DIMENSIONS: int = Field(default=768, ge=1, le=3072)
    EMBEDDING_BATCH_SIZE: int = Field(default=16, ge=1, le=100)
    INDEX_MAX_CHUNKS_PER_REQUEST: int = Field(default=16, ge=1, le=100)
    PROVIDER_TIMEOUT_MS: int = Field(default=10000, ge=1000, le=60000)
    EMBEDDING_MAX_ATTEMPTS: int = Field(default=3, ge=1, le=5)
    GENERATION_TIMEOUT_MS: int = Field(default=30000, ge=1000, le=60000)
    GENERATION_MAX_ATTEMPTS: int = Field(default=2, ge=1, le=3)
    ALLOW_GENERAL_ANSWERS: bool = True
    RETRIEVAL_MIN_SIMILARITY: float = Field(default=0.65, ge=0, le=1)

    # CORS
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://localhost:8000",
    ]

    @model_validator(mode='after')
    def validate_production(self):
        for name in ('SECRET_KEY', 'GEMINI_API_KEY'):
            filename = getattr(self, name + '_FILE')
            if filename:
                try:
                    value = Path(filename).read_text(encoding='utf-8').strip()
                except OSError:
                    raise ValueError(f'{name}_FILE cannot be read') from None
                setattr(self, name, value)
        if self.ENVIRONMENT != 'production':
            return self
        # Auto-configure Render HTTPS origin, CORS, and trusted hosts when deployed on Render
        render_url = os.environ.get('RENDER_EXTERNAL_URL', '').strip().rstrip('/')
        if render_url and not self.PUBLIC_ORIGIN:
            self.PUBLIC_ORIGIN = render_url
        if self.PUBLIC_ORIGIN:
            origin_parsed = urlsplit(self.PUBLIC_ORIGIN)
            if self.BACKEND_CORS_ORIGINS == [
                "http://localhost:5173",
                "http://127.0.0.1:5173",
                "http://localhost:3000",
                "http://localhost:8000",
            ]:
                self.BACKEND_CORS_ORIGINS = [self.PUBLIC_ORIGIN]
            if origin_parsed.hostname and (
                not self.TRUSTED_HOSTS
                or self.TRUSTED_HOSTS == ['localhost', '127.0.0.1', 'testserver']
            ):
                self.TRUSTED_HOSTS = [origin_parsed.hostname, 'localhost', '127.0.0.1']
        secret = self.SECRET_KEY.strip()
        if len(secret) < 48 or len(set(secret)) < 12 or any(word in secret.lower() for word in ('change', 'replace', 'techquery-super-secret')):
            raise ValueError('Production requires a new random SECRET_KEY of at least 48 characters')
        origin = urlsplit(self.PUBLIC_ORIGIN)
        if (origin.scheme != 'https' or not origin.hostname or origin.username or origin.password
                or origin.path or origin.query or origin.fragment or origin.hostname in ('localhost', '127.0.0.1')
                or origin.hostname.endswith(('.example', '.invalid')) or 'replace' in origin.hostname.lower()):
            raise ValueError('Production PUBLIC_ORIGIN must be the real HTTPS origin without a trailing slash')
        if self.BACKEND_CORS_ORIGINS != [self.PUBLIC_ORIGIN]:
            raise ValueError('Production CORS must contain only PUBLIC_ORIGIN')
        if not self.TRUSTED_HOSTS or '*' in self.TRUSTED_HOSTS or origin.hostname not in self.TRUSTED_HOSTS:
            raise ValueError('Production TRUSTED_HOSTS must explicitly include the public hostname without wildcards')
        if any('*' in host for host in self.TRUSTED_HOSTS):
            raise ValueError('Wildcard production hosts are not supported')
        url = make_url(self.DATABASE_URL)
        if url.get_backend_name() != 'sqlite' or url.database in (None, '', ':memory:') or not (Path(url.database).is_absolute() or PurePosixPath(url.database).is_absolute()):
            raise ValueError('This production release requires an absolute persistent SQLite database path')
        if not (Path(self.DOCUMENTS_DIR).is_absolute() or PurePosixPath(self.DOCUMENTS_DIR).is_absolute()) or self.MAX_INGESTION_JOBS != 1:
            raise ValueError('Production requires absolute document storage and one ingestion job')
        if not self.SERVE_FRONTEND:
            raise ValueError('Production release requires SERVE_FRONTEND=true')
        return self

    model_config = SettingsConfigDict(
        env_file=(str(BASE_DIR / ".env"), str(PROJECT_ROOT / ".env")),
        env_file_encoding="utf-8",
        extra="ignore",
        hide_input_in_errors=True,
    )

settings = Settings()
