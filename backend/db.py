"""SQLite engine, sessions, and startup initialization."""

from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import text
from sqlmodel import Session, SQLModel, create_engine

from config import DATABASE_URL

# SQLite needs check_same_thread=False; Postgres/Others omit it.
_engine_kwargs: dict = {}
if DATABASE_URL.startswith("sqlite"):
    _engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, **_engine_kwargs)


def _migrate_sqlite_connected_repo_columns() -> None:
    """Add columns added after first deploy (SQLite has no ALTER IF NOT EXISTS).

    Table name must match SQLModel defaults (e.g. ConnectedRepo -> connectedrepo).
    """
    from models import ConnectedRepo

    url = str(engine.url)
    if "sqlite" not in url:
        return
    table = ConnectedRepo.__table__.name
    with engine.connect() as conn:
        rows = conn.execute(text(f'PRAGMA table_info("{table}")')).fetchall()
        if not rows:
            return
        colnames = {r[1] for r in rows}
        if "review_dimensions_json" not in colnames:
            conn.execute(
                text(f'ALTER TABLE "{table}" ADD COLUMN review_dimensions_json TEXT')
            )
            conn.commit()


def init_db() -> None:
    # Imported here to register models with SQLModel metadata.
    from models import ConnectedRepo, PRCommentSnapshot, User  # noqa: F401

    SQLModel.metadata.create_all(engine)
    _migrate_sqlite_connected_repo_columns()


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
