import sqlite3
import math
import os
from contextlib import contextmanager
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
from src.config import SQL_DIR, _get_config_val, BASE_DIR

def get_engine_url():
    """Dynamically get and normalize current DATABASE_URL."""
    url = _get_config_val("DATABASE_URL", f"sqlite:///{BASE_DIR / 'urbanpulse.db'}")
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return url

def create_app_engine():
    """Create a configured SQLAlchemy engine for either SQLite or PostgreSQL."""
    url = get_engine_url()
    kwargs = {"pool_pre_ping": True}
    
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    else:
        # Production Cloud PostgreSQL Pool configuration
        kwargs["pool_size"] = 10
        kwargs["max_overflow"] = 20
        kwargs["pool_recycle"] = 1800
        kwargs["connect_args"] = {
            "sslmode": "require",
            "connect_timeout": 15
        }
    return create_engine(url, **kwargs)

engine = create_app_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def _add_sqlite_custom_functions(dbapi_con, con_record):
    """Register custom math functions for SQLite connection if needed."""
    if isinstance(dbapi_con, sqlite3.Connection):
        try:
            dbapi_con.create_function("sqrt", 1, math.sqrt)
            dbapi_con.create_function("pow", 2, math.pow)
            dbapi_con.execute("PRAGMA journal_mode=WAL;")
            dbapi_con.execute("PRAGMA synchronous=NORMAL;")
        except Exception:
            pass

from sqlalchemy import event
event.listen(engine, "connect", _add_sqlite_custom_functions)

@contextmanager
def get_db_session():
    """Provide a transactional database session scope."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

def init_db():
    """Execute schema and views to ensure all tables & analytical views exist."""
    try:
        is_pg = engine.dialect.name == "postgresql"
        schema_file = "schema_postgres.sql" if is_pg else "schema.sql"
        schema_path = SQL_DIR / schema_file
        views_path = SQL_DIR / "views.sql"

        with engine.connect() as conn:
            if schema_path.exists():
                with open(schema_path, "r", encoding="utf-8") as f:
                    schema_sql = f.read()
                    for statement in schema_sql.split(";"):
                        stmt = statement.strip()
                        if stmt:
                            try:
                                conn.execute(text(stmt))
                            except Exception as e:
                                pass
                    conn.commit()

            if views_path.exists():
                with open(views_path, "r", encoding="utf-8") as f:
                    views_sql = f.read()
                    for statement in views_sql.split(";"):
                        stmt = statement.strip()
                        if stmt:
                            try:
                                conn.execute(text(stmt))
                            except Exception as e:
                                pass
                    conn.commit()
        print(f"[Database] Schema & Analytical Views verified on {engine.dialect.name.upper()}.")
    except Exception as err:
        print(f"[Database Init Warning] {err}")

if __name__ == "__main__":
    init_db()


