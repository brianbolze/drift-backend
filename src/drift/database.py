"""Database engine and session configuration.

Reads DATABASE_URL from environment / .env file.
Default: sqlite:///data/drift.db (relative to project root).
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Load .env from project root
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(_PROJECT_ROOT / ".env")

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{_PROJECT_ROOT / 'data' / 'drift.db'}")


def get_engine(url: str = DATABASE_URL):
    # Ensure the data/ directory exists for SQLite
    if url.startswith("sqlite:///"):
        db_path = Path(url.replace("sqlite:///", ""))
        if not db_path.is_absolute():
            db_path = _PROJECT_ROOT / db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(url, echo=False)


def get_session_factory(url: str = DATABASE_URL):
    engine = get_engine(url)
    return sessionmaker(bind=engine)
