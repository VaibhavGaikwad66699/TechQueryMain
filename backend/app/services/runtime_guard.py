"""Offline maintenance and one running API must not share a SQLite data directory."""
from contextlib import nullcontext
from pathlib import Path
from app.services.file_locks import file_lock


def data_guard(database):
    return file_lock(Path(database).resolve().parent / '.server.lock')


def runtime_guard(engine):
    database = engine.url.database
    return data_guard(database) if engine.url.get_backend_name() == 'sqlite' and database not in (None, '', ':memory:') else nullcontext()
