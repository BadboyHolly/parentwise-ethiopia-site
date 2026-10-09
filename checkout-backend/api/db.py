import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def get_database_url() -> str:
    value = os.environ.get('DATABASE_URL', '')
    if not value:
        raise RuntimeError('DATABASE_URL is required; API cannot operate without persistent storage')
    # psycopg SQLAlchemy driver; other compatible URLs used only in disposable local tests.
    if value.startswith('postgres://'):
        value = 'postgresql+psycopg://' + value[len('postgres://'):]
    elif value.startswith('postgresql://'):
        value = 'postgresql+psycopg://' + value[len('postgresql://'):]
    if not (value.startswith('postgresql+psycopg://') or (os.environ.get('PYTEST_CURRENT_TEST') and value.startswith('sqlite:///'))):
        raise RuntimeError('Production API requires PostgreSQL')
    return value


def make_sessionmaker(url: str):
    connect_args = {'check_same_thread': False} if url.startswith('sqlite:') else {'connect_timeout': 5}
    opts = {'pool_size': 5} if not url.startswith('sqlite:') else {}
    engine = create_engine(url, pool_pre_ping=True, connect_args=connect_args, **opts)
    return engine, sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)