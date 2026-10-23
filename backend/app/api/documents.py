"""Four shared defaults plus owner-private PDFs, bounded uploads and local jobs."""
import os
import re
import uuid
from typing import Annotated, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from app.api.deps import get_current_user, get_optional_current_user
from app.core.config import settings
from app.core.scope import SubjectName
from app.database.session import get_db
from app.models.document import Document
from app.models.user import User
from app.schemas.document import DocumentProcessResponse, DocumentResponse, DocumentUploadResponse
from app.services.storage_service import storage_service, StorageError
from app.services import ingestion_jobs
from app.services.provider_access import provider_use_allowed
from app.services.library_access import get_visible_document, visible_documents, resolve_subject
from app.services.library_mutations import library_mutation

router = APIRouter(prefix='/documents', tags=['Document Management'])


def can_modify(document, user):
    return bool(user and ((document.is_default and user.role == 'admin') or (not document.is_default and document.uploaded_by == user.id)))


def document_response(document, user):
    return DocumentResponse.model_validate(document).model_copy(update={
        'can_modify': can_modify(document, user),
        'processing_active': ingestion_jobs.is_active(document.id) or document.status == 'processing',
        'in_scope': True,
    })


def require_modify(document, user):
    if not can_modify(document, user):
        raise HTTPException(status_code=403, detail='You can manage your own books. Default books are maintained by an administrator.')


@router.get('', response_model=List[DocumentResponse])
def list_documents(subject: Optional[SubjectName] = None, db: Session = Depends(get_db),
                   current_user: Optional[User] = Depends(get_optional_current_user)):
    query = db.query(Document).filter(visible_documents(current_user.id if current_user else None))
    if subject:
        subject = resolve_subject(db, subject, current_user.id if current_user else None)
        if subject != 'All':
            query = query.filter(Document.subject == subject)
    documents = query.order_by(Document.created_at.desc()).all()
    ingestion_jobs.recover_interrupted(db, documents)
    return [document_response(doc, current_user) for doc in documents]


@router.get('/{document_id}', response_model=DocumentResponse)
def get_document(document_id: int, db: Session = Depends(get_db),
                 current_user: Optional[User] = Depends(get_optional_current_user)):
    doc = get_visible_document(db, document_id, current_user.id if current_user else None)
    ingestion_jobs.recover_interrupted(db, [doc])
    return document_response(doc, current_user)


@router.post('/upload', response_model=DocumentUploadResponse, status_code=status.HTTP_201_CREATED)
@library_mutation
def upload_document(background_tasks: BackgroundTasks, subject: Annotated[SubjectName, Form()],
    file: UploadFile = File(...), title: Optional[str] = Form(None, max_length=255),
    auto_process: bool = Form(True), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    subject = resolve_subject(db, subject, current_user.id, allow_all=False)
    if not file.filename or not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail='Only PDF files are supported.')
    file.file.seek(0, os.SEEK_END)
    file_size = file.file.tell()
    file.file.seek(0)
    if file_size > settings.MAX_PDF_BYTES:
        raise HTTPException(status_code=413, detail='PDF exceeds the configured upload size limit.')
    if file_size == 0 or file.file.read(5) != b'%PDF-':
        raise HTTPException(status_code=400, detail='The file does not have a valid PDF header.')
    file.file.seek(0)
    original = file.filename.replace('\\', '/').rsplit('/', 1)[-1][:255]
    safe_name = re.sub(r'[^A-Za-z0-9._-]+', '_', original)[:190]
    filename = f'{uuid.uuid4().hex}_{safe_name}'
    try:
        storage_service.save_file(file.file, filename)
    except (OSError, StorageError):
        raise HTTPException(status_code=503, detail='Could not save the PDF. Please retry.')
    doc = Document(title=(title.strip() if title and title.strip() else original.rsplit('.', 1)[0])[:255],
        filename=filename, original_filename=original, file_size=file_size,
        subject=subject, status='pending', uploaded_by=current_user.id)
    try:
        db.add(doc)
        db.commit()
        db.refresh(doc)
    except Exception:
        db.rollback()
        try:
            storage_service.delete_file(filename)
        except (OSError, StorageError):
            pass
        raise HTTPException(status_code=503, detail='Could not register the uploaded PDF. Please retry.')
    scheduled = False
    message = 'PDF uploaded. Select Process to extract and index it.'
    if auto_process:
        try:
            ingestion_jobs.schedule(db, doc, background_tasks)
            scheduled = True
            message = 'PDF uploaded and scheduled for processing. Refresh its status to follow progress.'
        except ingestion_jobs.QueueFull:
            message = 'PDF uploaded. Another PDF is processing; retry processing shortly.'
    return {'message': message, 'document': document_response(doc, current_user), 'processing_scheduled': scheduled}


@router.post('/{document_id}/process', response_model=DocumentProcessResponse, status_code=202)
@library_mutation
def process_document(document_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db),
                     current_user: User = Depends(get_current_user)):
    doc = get_visible_document(db, document_id, current_user.id if current_user else None)
    require_modify(doc, current_user)
    resolve_subject(db, doc.subject, current_user.id, allow_all=False)
    if not provider_use_allowed(doc):
        raise HTTPException(status_code=422, detail='This book is searchable locally. Permission is required before sending its text to Google.')
    try:
        ingestion_jobs.schedule(db, doc, background_tasks)
    except ingestion_jobs.JobConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ingestion_jobs.QueueFull as exc:
        raise HTTPException(status_code=503, detail=str(exc), headers={'Retry-After': '5'})
    return {'message': 'Processing scheduled. Refresh the document status to follow progress.',
        'document_id': doc.id, 'chunks_created': 0, 'pages_processed': 0, 'status': doc.status, 'indexing': doc.indexing}


@router.delete('/{document_id}', status_code=200)
@library_mutation
def delete_document(document_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    doc = get_visible_document(db, document_id, current_user.id if current_user else None)
    require_modify(doc, current_user)
    if doc.is_default:
        raise HTTPException(status_code=409, detail='Default books are included for every account and cannot be deleted here.')
    if ingestion_jobs.is_active(doc.id) or doc.status == 'processing':
        raise HTTPException(status_code=409, detail='Wait for document processing to finish before deleting it.')
    from app.services.deletion_service import delete_books
    pending = delete_books(db, [doc])
    return {'message': ('Book removed from your library. Private file cleanup will retry on restart.' if pending
        else 'Document and all associated chunks were successfully deleted.'), 'storage_cleanup_pending': pending}


@router.head('/{document_id}/download', include_in_schema=False)
@router.get('/{document_id}/download')
def download_document(document_id: int, db: Session = Depends(get_db),
                      current_user: Optional[User] = Depends(get_optional_current_user)):
    doc = get_visible_document(db, document_id, current_user.id if current_user else None)
    try:
        if not storage_service.file_exists(doc.filename):
            raise HTTPException(status_code=404, detail='Physical file missing from storage.')
        path = storage_service.get_file_path(doc.filename)
    except (OSError, StorageError):
        raise HTTPException(status_code=503, detail='PDF storage is temporarily unavailable.')
    return FileResponse(path=path, filename=doc.original_filename, media_type='application/pdf', content_disposition_type='inline', headers={'Cache-Control': 'private, no-store', 'Vary': 'Authorization'})
