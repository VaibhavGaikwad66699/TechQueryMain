from typing import List
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.api.deps import get_current_user, get_optional_current_user
from app.core.scope import LANGUAGE_FILTERS, SubjectName
from app.database.session import get_db
from app.models.subject import UserSubject
from app.models.user import User
from app.services.library_access import subject_names
from app.services.library_mutations import library_mutation
from app.services.subject_service import delete_subject

router = APIRouter(prefix='/subjects', tags=['Personal Subjects'])


class SubjectCreate(BaseModel):
    name: SubjectName


@router.get('', response_model=List[str])
def list_subjects(db: Session = Depends(get_db), user=Depends(get_optional_current_user)):
    return subject_names(db, user.id if user else None)


@router.post('', status_code=201)
@library_mutation
def create_subject(data: SubjectCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if data.name in LANGUAGE_FILTERS:
        raise HTTPException(status_code=409, detail='This subject is already included in your default library.')
    subject = UserSubject(user_id=user.id, name=data.name, name_key=data.name.casefold())
    try:
        db.add(subject)
        db.commit()
        db.refresh(subject)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail='You already have a subject with this name.')
    return {'id': subject.id, 'name': subject.name}


@router.delete('')
@library_mutation
def remove_subject(name: SubjectName, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    # A query parameter supports names containing slashes and other path characters.
    return delete_subject(db, user.id, name)
