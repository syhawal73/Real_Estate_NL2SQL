"""
seed.py — Seed PostgreSQL with city_centers.csv and properties.csv.

Designed to run inside a Docker container connected to the postgres service.
Uses ON CONFLICT ... DO UPDATE (upsert) so it is safe to re-run.

Standard-library CSV parsing only (no pandas/numpy) to keep the seed image
small and its build fast.

Usage (inside container):
    python seed.py

Environment variables (set by docker-compose):
    DATABASE_URL  — postgresql://user:pass@host:port/dbname
"""

import csv
import os
import sys
import time

import psycopg2
from psycopg2.extras import execute_values

SEED_DIR = os.path.dirname(os.path.abspath(__file__))
CITIES_CSV = os.path.join(SEED_DIR, "city_centers.csv")
PROPERTIES_CSV = os.path.join(SEED_DIR, "properties.csv")

MAX_RETRIES = 15
RETRY_DELAY = 3  # seconds


def _read_rows(path: str) -> list[dict]:
    """Read a CSV into a list of dicts, stripping whitespace from header names.

    Uses csv.reader (not DictReader) so header stripping is unambiguous.
    Quoted fields containing commas (e.g. descriptions) are handled by the
    csv module.
    """
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.reader(fh)
        header = [h.strip() for h in next(reader)]
        return [dict(zip(header, raw)) for raw in reader if raw]


def wait_for_db(dsn: str):
    """Block until PostgreSQL accepts connections (with retries)."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            conn = psycopg2.connect(dsn)
            conn.close()
            print(f"  ✔ PostgreSQL is reachable (attempt {attempt})")
            return
        except psycopg2.OperationalError:
            print(f"  Waiting for PostgreSQL... (attempt {attempt}/{MAX_RETRIES})")
            time.sleep(RETRY_DELAY)
    print("  ✖ Could not connect to PostgreSQL after retries.", file=sys.stderr)
    sys.exit(1)


def ensure_base_schema(cur):
    """Create the property-domain tables needed before the first seed run.

    The backend also declares these tables with SQLAlchemy and will verify them
    idempotently on startup. The seed container must create them first because
    the backend intentionally waits for the seed container to complete.
    """
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS properties (
            id INTEGER PRIMARY KEY,
            title VARCHAR NOT NULL,
            city VARCHAR NOT NULL,
            neighbourhood VARCHAR NOT NULL,
            intent VARCHAR NOT NULL,
            price INTEGER NOT NULL,
            bedrooms INTEGER NOT NULL,
            bathrooms INTEGER NOT NULL,
            size_sqm INTEGER NOT NULL,
            property_type VARCHAR NOT NULL,
            distance_from_city_km DOUBLE PRECISION NOT NULL,
            description TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS ix_properties_city_intent ON properties (city, intent);
        CREATE INDEX IF NOT EXISTS ix_properties_city ON properties (city);
        CREATE INDEX IF NOT EXISTS ix_properties_intent ON properties (intent);
        CREATE INDEX IF NOT EXISTS ix_properties_property_type ON properties (property_type);

        CREATE TABLE IF NOT EXISTS city_centers (
            city VARCHAR PRIMARY KEY,
            latitude DOUBLE PRECISION NOT NULL,
            longitude DOUBLE PRECISION NOT NULL
        );
        """
    )


def load_city_centers(cur, path: str) -> int:
    rows = [
        (d["city"], float(d["latitude"]), float(d["longitude"]))
        for d in _read_rows(path)
    ]
    execute_values(
        cur,
        """
        INSERT INTO city_centers (city, latitude, longitude)
        VALUES %s
        ON CONFLICT (city) DO UPDATE
            SET latitude  = EXCLUDED.latitude,
                longitude = EXCLUDED.longitude
        """,
        rows,
    )
    return len(rows)


def load_properties(cur, path: str) -> int:
    rows = []
    for d in _read_rows(path):
        rows.append((
            int(d["id"]),
            d["title"],
            d["city"],
            d["neighbourhood"],
            d["intent"],
            int(float(d["price"])),
            int(float(d["bedrooms"])),
            int(float(d["bathrooms"])),
            int(float(d["size_sqm"])),
            d["property_type"],
            float(d["distance_from_city_km"]),
            d.get("description") or "",
        ))

    execute_values(
        cur,
        """
        INSERT INTO properties (
            id, title, city, neighbourhood, intent,
            price, bedrooms, bathrooms, size_sqm,
            property_type, distance_from_city_km, description
        )
        VALUES %s
        ON CONFLICT (id) DO UPDATE
            SET title                   = EXCLUDED.title,
                city                    = EXCLUDED.city,
                neighbourhood           = EXCLUDED.neighbourhood,
                intent                  = EXCLUDED.intent,
                price                   = EXCLUDED.price,
                bedrooms                = EXCLUDED.bedrooms,
                bathrooms               = EXCLUDED.bathrooms,
                size_sqm                = EXCLUDED.size_sqm,
                property_type           = EXCLUDED.property_type,
                distance_from_city_km   = EXCLUDED.distance_from_city_km,
                description             = EXCLUDED.description
        """,
        rows,
    )
    return len(rows)


def main():
    dsn = os.environ.get(
        "DATABASE_URL",
        "postgresql://ai_property_demo_user:ai_property_password_2026@postgres:5432/ai_property_demo",
    )

    # psycopg2 needs postgresql:// not postgresql+asyncpg://
    dsn = dsn.replace("postgresql+asyncpg://", "postgresql://")

    print("━━━ Database Seeder ━━━")
    wait_for_db(dsn)

    conn = psycopg2.connect(dsn)
    conn.autocommit = False

    try:
        with conn.cursor() as cur:
            ensure_base_schema(cur)
            cur.execute("SELECT COUNT(*) FROM properties")
            count = cur.fetchone()[0]
            if count > 0:
                print(f"  ℹ Database already has {count} properties — re-upserting...")

            print(f"  Loading city centers from {CITIES_CSV}")
            n_cities = load_city_centers(cur, CITIES_CSV)
            print(f"    → {n_cities} cities upserted")

            print(f"  Loading properties from {PROPERTIES_CSV}")
            n_props = load_properties(cur, PROPERTIES_CSV)
            print(f"    → {n_props} properties upserted")

        conn.commit()
        print("  ✔ Seed complete — all changes committed!")

    except Exception as exc:
        conn.rollback()
        print(f"  ✖ Seed failed: {exc}", file=sys.stderr)
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
