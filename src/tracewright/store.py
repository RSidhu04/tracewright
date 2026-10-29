import json
import os
from pathlib import Path
from datetime import datetime, timezone
from sqlalchemy import (create_engine, MetaData, Table, Column, String, Integer,
                        Text, ForeignKey, select, text, event)
from sqlalchemy.exc import IntegrityError
from alembic import command
from alembic.config import Config
from .records import RunRecord
from .redaction import redact

metadata = MetaData()
runs = Table('tw_runs', metadata,
    Column('id', String(36), primary_key=True),
    Column('created_at', String(40), nullable=False),
    Column('suite_hash', String(64), nullable=False, index=True),
    Column('payload', Text, nullable=False))
baselines = Table('tw_baselines', metadata,
    Column('name', String(80), primary_key=True),
    Column('version', Integer, primary_key=True),
    Column('run_id', String(36), ForeignKey('tw_runs.id'), nullable=False),
    Column('created_at', String(40), nullable=False),
    Column('note', Text, nullable=False))


def database_url(path=None):
    value = str(path or os.getenv('TRACEWRIGHT_DATABASE_URL') or os.getenv('TRACEWRIGHT_DB', 'tracewright.db'))
    if '://' not in value:
        Path(value).parent.mkdir(parents=True, exist_ok=True)
        return 'sqlite:///' + str(Path(value).resolve())
    if value.startswith('postgresql://'):
        value = value.replace('postgresql://', 'postgresql+psycopg://', 1)
    return value


class Conflict(ValueError):
    pass


class Store:
    def __init__(self, path=None, *, migrate=None, secrets=()):
        self.engine = create_engine(database_url(path), pool_pre_ping=True)
        self.secrets = secrets
        if self.engine.dialect.name == 'sqlite':
            @event.listens_for(self.engine, 'connect')
            def sqlite_setup(connection, record):
                connection.execute('PRAGMA foreign_keys=ON')
                connection.execute('PRAGMA busy_timeout=5000')
        # Local SQLite bootstraps automatically; PostgreSQL migration is explicit.
        if migrate is True or (migrate is None and self.engine.dialect.name == 'sqlite'):
            self.migrate()

    def migrate(self):
        config = Config()
        config.set_main_option('script_location', str(Path(__file__).parent / 'migrations'))
        with self.engine.begin() as connection:
            config.attributes['connection'] = connection
            command.upgrade(config, 'head')

    def ready(self):
        with self.engine.connect() as conn:
            conn.execute(select(runs.c.id).limit(1))
            conn.execute(select(baselines.c.name).limit(1))
        return True

    def save(self, run):
        validated = RunRecord.model_validate(run).model_dump(mode='json')
        safe = redact(validated, self.secrets)
        # Revalidate after masking, so secrets in identity fields fail closed.
        safe = RunRecord.model_validate(safe).model_dump(mode='json')
        payload = json.dumps(safe, sort_keys=True, allow_nan=False)
        if len(payload.encode()) > 2_000_000:
            raise ValueError('run exceeds 2 MB limit')
        try:
            with self.engine.begin() as conn:
                conn.execute(runs.insert().values(id=safe['id'], created_at=safe['created_at'],
                    suite_hash=safe['suite_hash'], payload=payload))
        except IntegrityError:
            if self.get(safe['id']) == safe:
                return False  # Idempotent retry of identical redacted content.
            raise Conflict('run ID already exists with different content') from None
        return True

    def get(self, run_id):
        with self.engine.connect() as conn:
            row = conn.execute(select(runs.c.payload).where(runs.c.id == str(run_id))).first()
        if row is None:
            raise KeyError(run_id)
        return json.loads(row[0])

    def list(self, limit=100, offset=0):
        with self.engine.connect() as conn:
            values = conn.execute(select(runs).order_by(runs.c.created_at.desc(), runs.c.id).limit(limit).offset(offset)).mappings().all()
        result = []
        for row in values:
            run = json.loads(row['payload'])
            result.append({k: run[k] for k in ('id', 'created_at', 'suite_name', 'suite_version', 'revision', 'source')} |
                {'pass_rate': sum(x['passed'] for x in run['results']) / len(run['results']),
                 'trials': len(run['results'])})
        return result

    def promote(self, name, version, run_id, note=''):
        # Caller supplies explicit version: concurrent conflicting promotions fail.
        run = self.get(str(run_id))
        value = dict(name=name, version=version, run_id=run['id'],
                     created_at=datetime.now(timezone.utc).isoformat(), note=redact(note, self.secrets))
        try:
            with self.engine.begin() as conn:
                conn.execute(baselines.insert().values(**value))
        except IntegrityError:
            raise Conflict('baseline version already exists') from None
        return value

    def baseline(self, name, version):
        with self.engine.connect() as conn:
            row = conn.execute(select(baselines).where(baselines.c.name == name, baselines.c.version == version)).mappings().first()
        if row is None:
            raise KeyError(name)
        return dict(row)

    def list_baselines(self, limit=100, offset=0):
        with self.engine.connect() as conn:
            return [dict(row) for row in conn.execute(select(baselines).order_by(baselines.c.created_at.desc()).limit(limit).offset(offset)).mappings()]
