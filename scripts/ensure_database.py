#!/usr/bin/env python3
"""
Ensure target Postgres database exists.
Safe to run multiple times.
"""

import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
import psycopg2
from psycopg2 import sql

# ======================================================
# Load environment variables
# ======================================================
ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(dotenv_path=ENV_PATH, override=True)

# ======================================================
# Retry configuration
# ======================================================
RETRIES = int(os.getenv("ENSURE_DB_RETRIES", "3"))
RETRY_DELAY = float(os.getenv("ENSURE_DB_RETRY_DELAY", "2"))


def getenv_any(*names, default=None):
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return default


def ensure_database():
    target_db = getenv_any("DB_NAME", "POSTGRES_DATABASE", default="ny_taxi")
    maintenance_db = getenv_any("DB_MAINTENANCE_DB", default="postgres")

    conn_params = {
        "host": getenv_any("DB_HOST", "POSTGRES_HOST"),
        "port": getenv_any("DB_PORT", "POSTGRES_PORT", default="5432"),
        "user": getenv_any("DB_USER", "POSTGRES_USER"),
        "password": getenv_any("DB_PASSWORD", "POSTGRES_PASSWORD"),
        "dbname": maintenance_db,
        "sslmode": "require",
    }

    missing = [k for k, v in conn_params.items() if not v and k != "port"]
    if missing:
        print(
            f"❌ Missing required environment variables: {missing}",
            file=sys.stderr,
        )
        return 1

    for attempt in range(1, RETRIES + 1):
        try:
            with psycopg2.connect(**conn_params) as conn:
                conn.autocommit = True
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT 1 FROM pg_database WHERE datname = %s",
                        (target_db,),
                    )
                    if cur.fetchone():
                        print(f"✅ Database '{target_db}' already exists")
                    else:
                        cur.execute(
                            sql.SQL("CREATE DATABASE {}").format(
                                sql.Identifier(target_db)
                            )
                        )
                        print(f"✅ Database '{target_db}' created successfully")
            return 0

        except Exception as exc:
            if attempt == RETRIES:
                print(
                    f"❌ Failed to ensure database exists: {exc}",
                    file=sys.stderr,
                )
                return 1
            time.sleep(RETRY_DELAY)


if __name__ == "__main__":
    sys.exit(ensure_database())

