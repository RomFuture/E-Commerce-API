from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.infrastructure.config.settings import get_settings
from src.infrastructure.debug_log import log, redact_db_url

settings = get_settings()

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, class_=Session)


def get_db_session():
    """Yield one SQLAlchemy session per request."""
    # region agent log
    log(
        run_id="pre-fix",
        hypothesis_id="H_cfg",
        location="src/infrastructure/db/session.py:get_db_session",
        message="Creating DB session",
        data={"database_url": redact_db_url(settings.database_url)},
    )
    # endregion
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

