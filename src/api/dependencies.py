from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from src.infrastructure.config.settings import Settings, get_settings
from src.infrastructure.db.session import get_db_session

# Reusable dependency types for endpoints:
# def route(db: DbSession, settings: SettingsDep): ...
DbSession = Annotated[Session, Depends(get_db_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
