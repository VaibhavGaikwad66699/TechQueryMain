"""One visibility boundary for listings, PDF access, retrieval and generation."""
from fastapi import HTTPException
from sqlalchemy import and_, or_
from app.core.scope import SUPPORTED_LANGUAGES, normalize_subject
from app.models.document import Document
from app.models.subject import UserSubject


def visible_documents(user_id=None):
    shared = and_(Document.is_default.is_(True), Document.subject.in_(SUPPORTED_LANGUAGES))
    return or_(shared, and_(Document.is_default.is_(False), Document.uploaded_by == user_id)) if user_id else shared


def subject_names(db, user_id=None):
    own = db.query(UserSubject).filter_by(user_id=user_id).order_by(UserSubject.name).all() if user_id else []
    return ['All', *SUPPORTED_LANGUAGES, *(subject.name for subject in own)]


def resolve_subject(db, value, user_id=None, *, allow_all=True):
    name = normalize_subject(value)
    if name in SUPPORTED_LANGUAGES or (allow_all and name == 'All'):
        return name
    if name != 'All' and user_id:
        own = db.query(UserSubject).filter_by(user_id=user_id, name_key=name.casefold()).first()
        if own:
            return own.name
    raise HTTPException(status_code=422, detail='Choose a default subject or add this subject to your own account first.')


def searchable_documents(db, user_id=None):
    return db.query(Document).filter(visible_documents(user_id), Document.subject.in_(subject_names(db, user_id)[1:]))


def get_visible_document(db, document_id, user_id=None):
    doc = db.query(Document).filter(Document.id == document_id, visible_documents(user_id)).first()
    if doc is None:
        raise HTTPException(status_code=404, detail='Document not found')
    return doc
