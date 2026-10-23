"""Promote an existing registered account during offline operator maintenance."""
import argparse
from sqlalchemy.engine import make_url
from app.core.config import settings
from app.database.session import SessionLocal
from app.models.user import User
from app.services.runtime_guard import data_guard


def promote(db, email):
    user = db.query(User).filter_by(email=email.strip().lower()).one_or_none()
    if user is None or not user.is_active:
        raise ValueError('An active registered account with this email is required')
    user.role = 'admin'
    db.commit()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--email', required=True)
    args = parser.parse_args()
    with data_guard(make_url(settings.sync_database_url).database), SessionLocal() as db:
        promote(db, args.email)
    print('Existing account promoted. No password or public bootstrap endpoint was created.')
