import os
from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.config.settings import settings

# Automatically create the SQLite directory if it doesn't exist
db_path = settings.sqlite_db_path
if db_path:
    db_dir = os.path.dirname(db_path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

# Create engine
# connect_args={"check_same_thread": False} is required for SQLite in multithreaded/async contexts
engine = create_engine(
    settings.DATABASE_URL,
    connect_args=(
        {"check_same_thread": False}
        if settings.DATABASE_URL.startswith("sqlite")
        else {}
    ),
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@contextmanager
def get_db_ctx():
    """Context manager for database sessions, ideal for background tasks or scheduler."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_db():
    """Generator for FastAPI Dependency Injection."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
