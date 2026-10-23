import hashlib
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
import pytest
from app.database.session import Base
from app.database.library_migration import upgrade_library, publish_default_books
from app.models.document import Document
from app.services.storage_service import storage_service


def test_old_database_upgrade_preserves_records_and_only_publishes_once(tmp_path, monkeypatch):
    engine = create_engine('sqlite:///' + str(tmp_path / 'old.sqlite3'))
    # Simulate the previous documents schema, without the new column.
    with engine.begin() as connection:
        connection.execute(text('CREATE TABLE documents (id INTEGER PRIMARY KEY, title VARCHAR(255) NOT NULL, filename VARCHAR(255) NOT NULL, original_filename VARCHAR(255) NOT NULL, file_size INTEGER, subject VARCHAR(100), total_pages INTEGER, total_chunks INTEGER, status VARCHAR(50), error_message TEXT, uploaded_by INTEGER, created_at DATETIME)'))
        for ident, subject in enumerate(['C', 'C++', 'Java', 'Python'], 1):
            connection.execute(text("INSERT INTO documents VALUES (:id, :subject, :file, :file, 8, :subject, 1, 1, 'partial', NULL, NULL, '2026-10-21')"),
                {'id': ident, 'subject': subject, 'file': subject + '.pdf'})
            (storage_service.base_dir / (subject + '.pdf')).write_bytes(subject.encode())
    fingerprints = {subject: (subject + '.pdf', hashlib.sha256(subject.encode()).hexdigest()) for subject in ['C', 'C++', 'Java', 'Python']}
    monkeypatch.setattr('app.database.library_migration.DEFAULT_BOOKS', fingerprints)
    Base.metadata.create_all(engine)
    upgrade_library(engine)
    with Session(engine) as db:
        assert [doc.id for doc in db.query(Document).filter_by(is_default=True).all()] == [1, 2, 3, 4]
        assert [(doc.subject, doc.total_chunks, doc.status) for doc in db.query(Document).all()] == [(s, 1, 'partial') for s in fingerprints]
        db.add(Document(title='Future private upload', filename='new.pdf', original_filename='C.pdf', subject='C', uploaded_by=None))
        db.commit()
        new_id = db.query(Document).filter_by(filename='new.pdf').one().id
    (storage_service.base_dir / 'new.pdf').write_bytes(b'C')
    upgrade_library(engine)
    with Session(engine) as db:
        assert db.get(Document, new_id).is_default is False
        with pytest.raises(ValueError, match='No books published'):
            publish_default_books(db)
        assert db.query(Document).filter_by(is_default=True).count() == 4
    engine.dispose()


def test_missing_default_fails_closed_without_publishing_part_of_library(db_session, monkeypatch):
    monkeypatch.setattr('app.database.library_migration.DEFAULT_BOOKS', {'C': ('missing.pdf', 'no match')})
    with pytest.raises(ValueError, match='No books published'):
        publish_default_books(db_session)
    assert db_session.query(Document).filter_by(is_default=True).count() == 0
