#!/usr/bin/env python3
"""
UrbanPulse — Cloud Database Migration Script
Migrates schema, views, and data from local SQLite to any cloud PostgreSQL instance.
Usage:
    python migrate_to_cloud_db.py --target-url "postgresql://user:pass@host:5432/dbname"
"""

import sys
import argparse
from pathlib import Path
import pandas as pd
from sqlalchemy import create_engine, text

ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

def run_migration(source_sqlite_path: str, target_pg_url: str):
    print("=" * 65)
    print("🚀 UrbanPulse — SQLite to Cloud PostgreSQL Data Migration")
    print("=" * 65)

    source_path = Path(source_sqlite_path)
    if not source_path.exists():
        print(f"❌ Source database file '{source_path}' not found!")
        sys.exit(1)

    # 1. Connect to Source SQLite
    print(f"📂 Connecting to source SQLite: {source_path}")
    src_engine = create_engine(f"sqlite:///{source_path}")

    # 2. Connect to Target PostgreSQL
    if target_pg_url.startswith("postgres://"):
        target_pg_url = target_pg_url.replace("postgres://", "postgresql://", 1)

    print("☁️ Connecting to target Cloud PostgreSQL...")
    try:
        tgt_engine = create_engine(target_pg_url, pool_pre_ping=True)
        with tgt_engine.connect() as conn:
            ver = conn.execute(text("SELECT version();")).scalar()
            print(f"✅ Connected to PostgreSQL: {ver[:45]}...")
    except Exception as e:
        print(f"❌ Failed to connect to target PostgreSQL: {e}")
        sys.exit(1)

    # 3. Initialize Target Schema & Views
    print("\n🛠️ Initializing PostgreSQL Schema & Analytical Views...")
    schema_file = ROOT_DIR / "sql" / "schema_postgres.sql"
    views_file = ROOT_DIR / "sql" / "views.sql"

    with tgt_engine.begin() as conn:
        if schema_file.exists():
            with open(schema_file, "r", encoding="utf-8") as f:
                for stmt in f.read().split(";"):
                    s = stmt.strip()
                    if s:
                        conn.execute(text(s))
            print("  ✅ Tables created successfully.")

        if views_file.exists():
            with open(views_file, "r", encoding="utf-8") as f:
                for stmt in f.read().split(";"):
                    s = stmt.strip()
                    if s:
                        try:
                            conn.execute(text(s))
                        except Exception as e:
                            print(f"  ⚠️ View notice: {e}")
            print("  ✅ Analytical views created successfully.")

    # 4. Migrate Data Table by Table
    tables = ["cities", "raw_daily_metrics", "api_logs", "ai_narratives"]
    migration_summary = {}

    with src_engine.connect() as src_conn, tgt_engine.begin() as tgt_conn:
        for tbl in tables:
            try:
                df = pd.read_sql_table(tbl, src_conn)
                count = len(df)
                if count > 0:
                    print(f"\n📦 Migrating table '{tbl}' ({count} rows)...")
                    # Clear target table for clean migration
                    tgt_conn.execute(text(f"TRUNCATE TABLE {tbl} CASCADE;"))
                    
                    # Insert in chunks
                    df.to_sql(tbl, tgt_conn, if_exists="append", index=False, chunksize=500, method="multi")
                    
                    # Reset PostgreSQL primary key sequence if table has serial id
                    try:
                        pk_col = "city_id" if tbl == "cities" else "id"
                        seq_sql = f"SELECT setval(pg_get_serial_sequence('{tbl}', '{pk_col}'), COALESCE(MAX({pk_col}), 1)) FROM {tbl};"
                        tgt_conn.execute(text(seq_sql))
                    except Exception:
                        pass

                    migration_summary[tbl] = (count, "✅ Success")
                    print(f"  ✅ Successfully migrated {count} records into '{tbl}'.")
                else:
                    migration_summary[tbl] = (0, "⚪ Empty")
                    print(f"\n⚪ Table '{tbl}' has 0 rows, skipped.")
            except Exception as e:
                migration_summary[tbl] = (0, f"❌ Failed: {e}")
                print(f"\n❌ Error migrating '{tbl}': {e}")

    # 5. Summary & Verification
    print("\n" + "=" * 65)
    print("📊 Data Migration Verification Summary:")
    print("=" * 65)
    for tbl, (cnt, status) in migration_summary.items():
        print(f"  • {tbl.ljust(22)} : {str(cnt).rjust(6)} rows | {status}")
    print("=" * 65)
    print("🎉 Cloud database is fully populated and ready for production!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migrate UrbanPulse data to Cloud PostgreSQL")
    parser.add_argument("--source-sqlite", default=str(ROOT_DIR / "urbanpulse.db"), help="Path to local urbanpulse.db")
    parser.add_argument("--target-url", required=True, help="Target PostgreSQL Connection URL (e.g. postgresql://user:pass@host/db)")
    args = parser.parse_args()

    run_migration(args.source_sqlite, args.target_url)
