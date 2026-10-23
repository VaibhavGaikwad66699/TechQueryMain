"""Remove an owner's subject without touching shared or other owners' books."""

from fastapi import HTTPException
from app.models.document import Document
from app.models.subject import UserSubject
from app.models.user import UserPreference
from app.services import ingestion_jobs


def delete_subject(db, user_id, name):
    subject = db.query(UserSubject).filter_by(user_id=user_id, name_key=name.casefold()).first()
    if subject is None:
        raise HTTPException(status_code=404, detail='Personal subject not found. Default subjects cannot be deleted.')
    documents = db.query(Document).filter_by(uploaded_by=user_id, subject=subject.name, is_default=False).all()
    if any(doc.status == 'processing' or ingestion_jobs.is_active(doc.id) for doc in documents):
        raise HTTPException(status_code=409, detail='Wait for this subject’s books to finish processing before deleting it.')

    from app.services.deletion_service import delete_books

    def mutate():
        pref = db.query(UserPreference).filter_by(user_id=user_id, preferred_subject=subject.name).first()
        if pref:
            pref.preferred_subject = 'All'
        db.delete(subject)
    cleanup_pending = delete_books(db, documents, mutate)
    return {'message': ('Subject and books removed from your library. Private file cleanup will retry on restart.'
        if cleanup_pending else 'Personal subject, its source books and their search data were deleted.'),
        'deleted_subject': name, 'documents_deleted': len(documents), 'storage_cleanup_pending': cleanup_pending}
