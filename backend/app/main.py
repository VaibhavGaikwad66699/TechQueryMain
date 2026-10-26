from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from pathlib import Path
from app.api import auth, conversations, documents, health, rag, users, subjects
from app.core.config import settings
from app.database.session import Base, engine

# Create tables upon startup
@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.services.runtime_guard import runtime_guard
    with runtime_guard(engine):
        if settings.SERVE_FRONTEND and not (Path(settings.FRONTEND_DIST) / 'index.html').is_file():
            raise RuntimeError('Frontend production build is missing')
        async with initialized(app):
            yield


@asynccontextmanager
async def initialized(app: FastAPI):
    # Ensure database tables exist
    Base.metadata.create_all(bind=engine)
    from app.database.library_migration import upgrade_library
    upgrade_library(engine)
    from sqlalchemy.orm import Session
    from app.services.storage_service import storage_service
    from app.services.deletion_service import recover_deletions
    from app.services.ingestion_jobs import recover_interrupted
    storage_service.recover_upload_parts()
    with Session(engine) as db:
        recover_deletions(db)
        recover_interrupted(db)
        if settings.ENVIRONMENT == 'production':
            from app.database.library_migration import DEFAULT_BOOKS
            from app.models.document import Document, DocumentChunk
            from app.services.extraction_service import file_digest
            for subject, (name, digest) in DEFAULT_BOOKS.items():
                books = db.query(Document).filter_by(is_default=True, subject=subject, original_filename=name).all()
                if (len(books) != 1 or not db.query(DocumentChunk.id).filter_by(document_id=books[0].id).first()
                        or file_digest(storage_service.get_file_path(books[0].filename)) != digest):
                    raise RuntimeError('Initialize the verified four-book dataset before starting production')
    yield

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="TechQuery — four included programming books and private subjects grounded in your own PDFs.",
    lifespan=lifespan,
    docs_url=None if settings.ENVIRONMENT == 'production' else '/docs',
    redoc_url=None if settings.ENVIRONMENT == 'production' else '/redoc',
    openapi_url=None if settings.ENVIRONMENT == 'production' else '/openapi.json',
)


@app.middleware('http')
async def private_api_responses(request, call_next):
    response = await call_next(request)
    if request.url.path.startswith(settings.API_V1_STR):
        response.headers['Cache-Control'] = 'private, no-store'
        response.headers['Vary'] = ', '.join(filter(None, [response.headers.get('Vary'), 'Authorization']))
    return response

@app.exception_handler(RequestValidationError)
async def safe_validation_error(request, exc):
    errors = [{"loc": list(error["loc"]), "type": error["type"], "msg": error["msg"]} for error in exc.errors()]
    for error in errors:
        if error["loc"] == ["body", "question"] and error["type"] == "string_too_long":
            error["msg"] = "Question cannot exceed 4,000 characters."
    return JSONResponse(status_code=422, content={"detail": errors, "message": errors[0]["msg"] if errors else "Invalid request."})

# CORS Middleware
from app.services.upload_limits import UploadBodyLimit
app.add_middleware(UploadBodyLimit)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
from app.services.production_http import ProductionRateLimit
app.add_middleware(ProductionRateLimit)
if settings.ENVIRONMENT == 'production':
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.TRUSTED_HOSTS)

if settings.SERVE_FRONTEND:
    app.mount('/assets', StaticFiles(directory=Path(settings.FRONTEND_DIST) / 'assets', check_dir=False), name='assets')

# Register routers under /api/v1
app.include_router(health.router, prefix=settings.API_V1_STR)
app.include_router(auth.router, prefix=settings.API_V1_STR)
app.include_router(users.router, prefix=settings.API_V1_STR)
app.include_router(documents.router, prefix=settings.API_V1_STR)
app.include_router(conversations.router, prefix=settings.API_V1_STR)
app.include_router(rag.router, prefix=settings.API_V1_STR)
app.include_router(subjects.router, prefix=settings.API_V1_STR)

@app.get("/")
def root():
    if settings.SERVE_FRONTEND:
        return FileResponse(Path(settings.FRONTEND_DIST) / 'index.html', headers={'Cache-Control': 'no-cache'})
    return {
        "message": "Welcome to TechQuery API",
        "docs_url": "/docs",
        "health_check": f"{settings.API_V1_STR}/health"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
