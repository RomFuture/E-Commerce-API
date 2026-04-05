import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.api.main import create_app
from src.infrastructure.config.settings import get_settings
from src.infrastructure.db.base import Base
from src.infrastructure.db.session import get_db_session


@pytest.fixture
def db_session():
    """
    Integration DB session for tests.

    Default: in-memory SQLite (fast, no external deps).
    If `TEST_DATABASE_URL` is set: use that database (recommended: Postgres in Docker).
    """
    settings = get_settings()
    test_db_url = getattr(settings, "test_database_url", None)  # backward-safe if not defined
    # Prefer explicit env var to avoid surprises.
    # Example:
    #   TEST_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5434/ecommerce_test
    import os

    test_db_url = os.getenv("TEST_DATABASE_URL") or test_db_url

    if test_db_url:
        engine = create_engine(test_db_url, pool_pre_ping=True)
    else:
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

    # Ensure schema exists for the chosen DB.
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        try:
            session.close()
        finally:
            # Clean up tables between test runs.
            try:
                Base.metadata.drop_all(engine)
            except SQLAlchemyError:
                # If DB is unavailable at teardown, surface original test failure.
                pass


@pytest.fixture
def app(db_session, monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "test-secret-key-at-least-32-characters-long")
    monkeypatch.setenv("ADMIN_EMAIL", "admin@test.com")
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_valid_fake_for_pytest")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test_fake_for_pytest")
    get_settings.cache_clear()
    application = create_app()

    def override_db():
        yield db_session

    application.dependency_overrides[get_db_session] = override_db
    yield application
    application.dependency_overrides.clear()
    get_settings.cache_clear()


@pytest.fixture
def client(app):
    with TestClient(app) as test_client:
        yield test_client
