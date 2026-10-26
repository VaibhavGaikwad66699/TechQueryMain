"""Initialize a fresh deployment from the seed; never replace existing data."""
import argparse
from pathlib import Path
from sqlalchemy.engine import make_url
from app.core.config import settings
from app.services.release_service import restore_bundle


def initialize(seed):
    url = make_url(settings.sync_database_url)
    database = Path(url.database).resolve()
    documents = Path(settings.sync_documents_dir).resolve()
    if database.is_file():
        print('[Startup] Existing database preserved; skipping seed restore.', flush=True)
        return
    if database.name != 'techquery.db' or documents != database.parent / 'documents':
        raise ValueError('Fresh seed requires techquery.db and documents/ in the same configured data directory')
    restore_bundle(Path(seed), database.parent)
    print('[Startup] Verified four-book seed restored; no embeddings generated.', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed', default='/app/seed')
    args = parser.parse_args()
    try:
        initialize(args.seed)
    except (ValueError, OSError, KeyError) as error:
        parser.exit(2, f'[Startup] Seed initialization refused ({type(error).__name__}). Check data paths, seed inventory and directory permissions. Existing data was not replaced.\n')
