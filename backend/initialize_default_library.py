"""Run after copying/importing the four approved PDFs and their index to a new host."""
from app import models  # register tables
from app.database.session import Base, engine, SessionLocal
from app.database.library_migration import upgrade_library, publish_default_books


if __name__ == '__main__':
    Base.metadata.create_all(engine)
    upgrade_library(engine)
    with SessionLocal() as db:
        print({'shared_default_document_ids': publish_default_books(db)})
