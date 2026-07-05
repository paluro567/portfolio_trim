"""Shared CLI wiring: settings -> logging -> engine -> session factory."""

from sqlalchemy.orm import Session, sessionmaker

from mip.core.config import get_settings
from mip.core.db import create_db_engine, create_session_factory
from mip.core.logging import configure_logging


def open_session_factory() -> sessionmaker[Session]:
    settings = get_settings()
    configure_logging(settings.log_format)
    return create_session_factory(create_db_engine(settings))
