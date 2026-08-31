import sqlite3
import math
from contextlib import contextmanager
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
from src.config import DATABASE_URL, SQL_DIR

# Normalize connection string for SQLAlchemy (postgres:// -> postgresql://)
engine_url = DATABASE_URL
if engine_url.startswith("postgres://"):
    engine_url = engine_url.replace("postgres://", "postgresql://", 1)

# Initialize SQLAlchemy Engine with connection pooling
engine_kwargs = {"pool_pre_ping": True}
if engine_url.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    # Production Cloud PostgreSQL Pool configuration
    engine_kwargs["pool_size"] = 10
    engine_kwargs["max_overflow"] = 20
    engine_kwargs["pool_recycle"] = 1800

engine = create_engine(engine_url, **engine_kwargs)

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
    is_pg = engine.dialect.name == "postgresql"
    schema_file = "schema_postgres.sql" if is_pg else "schema.sql"
    schema_path = SQL_DIR / schema_file
    views_path = SQL_DIR / "views.sql"

    with engine.connect() as conn:
        if schema_path.exists():
            with open(schema_path, "r", encoding="utf-8") as f:
                schema_sql = f.read()
                # Split and execute individual statements
                for statement in schema_sql.split(";"):
                    stmt = statement.strip()
                    if stmt:
                        try:
                            conn.execute(text(stmt))
                        except Exception as e:
                            print(f"[DB Init Notice] Schema execution: {e}")
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
                            print(f"[DB Init Notice] View execution: {e}")
                conn.commit()
    print(f"[Database] Schema & Analytical Views initialized successfully on {engine.dialect.name.upper()}.")

if __name__ == "__main__":
    init_db()

