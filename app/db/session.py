from collections.abc import Iterator
from sqlite3 import Connection as SQLiteConnection
from typing import Any

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Base

DATABASE_URL = "sqlite:///./business.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)
SessionFactory = sessionmaker(bind=engine, expire_on_commit=False)


@event.listens_for(Engine, "connect")
def enable_sqlite_foreign_keys(
    dbapi_connection: Any,
    _connection_record: Any,
) -> None:
    """为每个 SQLite 连接启用外键约束检查。 / Enables foreign-key enforcement for every SQLite connection."""

    if isinstance(dbapi_connection, SQLiteConnection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def create_schema() -> None:
    """根据 SQLAlchemy 模型创建尚不存在的数据库表。 / Creates missing database tables from the SQLAlchemy models."""

    Base.metadata.create_all(engine)


def get_db_session() -> Iterator[Session]:
    """为一次请求提供并在结束后关闭数据库会话。 / Provides a database session for one request and closes it afterward."""

    with SessionFactory() as session:
        yield session
