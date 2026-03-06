"""Shared test fixtures. Every test gets a fresh in-memory SQLite database."""

import pytest
from sqlalchemy.orm import Session

from drift.database import get_engine
from drift.models import Base


@pytest.fixture()
def db():
    engine = get_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
