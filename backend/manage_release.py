"""Offline default dataset export, private backup, verified fresh-directory restore."""
import argparse
import json
import sqlite3
from pathlib import Path
from sqlalchemy.engine import make_url
from app.core.config import settings
from app.services.file_locks import LockBusy
from app.services.release_service import export_defaults, backup_data, verify_bundle, restore_bundle


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ['export-defaults', 'backup']:
        command = commands.add_parser(name)
        command.add_argument('--output', required=True, type=Path)
        command.add_argument('--database', type=Path, default=Path(make_url(settings.sync_database_url).database))
        command.add_argument('--documents', type=Path, default=Path(settings.sync_documents_dir))
    verify = commands.add_parser('verify')
    verify.add_argument('--bundle', required=True, type=Path)
    restore = commands.add_parser('restore')
    restore.add_argument('--bundle', required=True, type=Path)
    restore.add_argument('--target', required=True, type=Path)
    args = parser.parse_args()
    try:
        if args.command in ('backup', 'export-defaults'):
            function = backup_data if args.command == 'backup' else export_defaults
            report = function(args.database, args.documents, args.output)
        elif args.command == 'verify':
            report = verify_bundle(args.bundle)
        else:
            report = restore_bundle(args.bundle, args.target)
    except LockBusy:
        parser.exit(2, 'Stop the API before offline maintenance; its data directory is locked.\n')
    except (ValueError, OSError, KeyError, sqlite3.Error) as error:
        parser.exit(2, f'Maintenance refused ({type(error).__name__}); no existing destination was replaced.\n')
    print(json.dumps({'kind': report['kind'], 'verified': True, 'summary': report['summary']}))


if __name__ == '__main__':
    main()
