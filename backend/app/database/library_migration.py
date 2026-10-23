"""Additive SQLite upgrade. Only the four fingerprinted originals become shared."""
import hashlib
from pathlib import Path
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session
from app.models.document import Document

DEFAULT_BOOKS = {
    'C': ('CNotesForProfessionals.pdf', '4d9133ac6d74b412f2484aca91c482ca66b8d46ed7f94a317740fa34cebd9b36'),
    'C++': ('CPlusPlusNotesForProfessionals.pdf', '7b53f43eae83ef1260f02f6a492fdda498e71e4dff81b7b9306652d5d4e65918'),
    'Java': ('JavaNotesForProfessionals.pdf', '8751bee1658e8b2a247311eb9179625a4216b62f76d4b21545fb68e495dba706'),
    'Python': ('PythonNotesForProfessionals.pdf', 'f5e2868ad977858fa0fa3eb123282f15a06f6eb4dd2b7c3a883e1dd1e138f61f'),
}


def publish_default_books(db):
    """Operator-only initialization of the four exact books; never an HTTP action."""
    from app.services.storage_service import storage_service
    selected = []
    for subject, (filename, digest) in DEFAULT_BOOKS.items():
        candidates = db.query(Document).filter_by(subject=subject, original_filename=filename).all()
        matching = []
        for doc in candidates:
            path = Path(storage_service.get_file_path(doc.filename))
            if path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == digest:
                matching.append(doc)
        if len(matching) != 1:
            raise ValueError(f'Expected one fingerprint-verified {subject} default book; found {len(matching)}. No books published.')
        selected.append(matching[0])
    for doc in selected:
        doc.is_default = True
    db.commit()
    return [doc.id for doc in selected]


def upgrade_library(engine):
    columns = {column['name'] for column in inspect(engine).get_columns('documents')}
    if 'is_default' not in columns:
        with engine.begin() as connection:
            connection.execute(text('ALTER TABLE documents ADD COLUMN is_default BOOLEAN NOT NULL DEFAULT 0'))
    with engine.begin() as connection:
        connection.execute(text('CREATE INDEX IF NOT EXISTS ix_documents_is_default ON documents (is_default)'))
    # One-time promotion: never auto-publish a future user's upload of the same book.
    with engine.begin() as connection:
        connection.execute(text('CREATE TABLE IF NOT EXISTS library_migrations (name VARCHAR(100) PRIMARY KEY)'))
        done = connection.execute(text("SELECT name FROM library_migrations WHERE name='private_library_v1'")).first()
    if done:
        return
    with Session(engine) as db:
        # All four or none. A later account upload must never trigger promotion.
        try:
            publish_default_books(db)
        except ValueError:
            db.rollback()
        db.execute(text("INSERT INTO library_migrations(name) VALUES ('private_library_v1')"))
        db.commit()
