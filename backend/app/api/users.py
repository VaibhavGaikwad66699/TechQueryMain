from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.api.deps import get_current_user
from app.database.session import get_db
from app.models.user import User, UserPreference
from app.services.library_access import resolve_subject, subject_names
from app.schemas.preference import UserPreferenceResponse, UserPreferenceUpdate
from app.services.library_mutations import library_mutation

router = APIRouter(prefix="/users", tags=["Users & Preferences"])

@router.get("/preferences", response_model=UserPreferenceResponse)
def get_user_preferences(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieve learning preferences for currently logged-in user."""
    pref = db.query(UserPreference).filter(UserPreference.user_id == current_user.id).first()
    if not pref:
        pref = UserPreference(
            user_id=current_user.id,
            explanation_level="Intermediate",
            answer_style="Detailed",
            include_examples=True,
            preferred_subject="All",
        )
        db.add(pref)
        db.commit()
        db.refresh(pref)
    if pref.preferred_subject not in subject_names(db, current_user.id):
        return UserPreferenceResponse.model_validate(pref).model_copy(update={'preferred_subject': 'All'})
    return pref

@router.put("/preferences", response_model=UserPreferenceResponse)
@library_mutation
def update_user_preferences(
    pref_update: UserPreferenceUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update learning preferences (explanation level, answer style, examples)."""
    if pref_update.preferred_subject is not None:
        pref_update.preferred_subject = resolve_subject(db, pref_update.preferred_subject, current_user.id)
    pref = db.query(UserPreference).filter(UserPreference.user_id == current_user.id).first()
    if not pref:
        pref = UserPreference(user_id=current_user.id)
        db.add(pref)

    if pref_update.explanation_level is not None:
        pref.explanation_level = pref_update.explanation_level
    if pref_update.answer_style is not None:
        pref.answer_style = pref_update.answer_style
    if pref_update.include_examples is not None:
        pref.include_examples = pref_update.include_examples
    if pref_update.preferred_subject is not None:
        pref.preferred_subject = pref_update.preferred_subject

    db.commit()
    db.refresh(pref)
    return pref
