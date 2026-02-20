"""Shared test fixtures. Every test gets a fresh in-memory SQLite database."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from rangefinder.models import Base


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
