import logging
import time

from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.config import settings


logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def wait_for_database(max_attempts: int = 30, delay_seconds: float = 1.0) -> None:
    last_error: Exception | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            if attempt > 1:
                logger.info("Database became available on attempt %s.", attempt)
            return
        except OperationalError as exc:
            last_error = exc
            logger.warning(
                "Database not ready yet (attempt %s/%s): %s",
                attempt,
                max_attempts,
                exc,
            )
            if attempt < max_attempts:
                time.sleep(delay_seconds)

    if last_error is not None:
        raise last_error


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
