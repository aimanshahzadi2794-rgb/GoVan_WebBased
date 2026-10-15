"""
Database engine + session setup.

Uses SQLite for the MVP so the project runs with zero external
infrastructure. Swapping to Postgres later is a one-line change to
DATABASE_URL since we only use SQLAlchemy's ORM layer (no SQLite-specific
SQL anywhere in the app).
"""
import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Anchor the SQLite file to this file's own directory (backend/), not the
# current working directory. Without this, running `uvicorn app.main:app`
# from a different folder each time silently creates a brand new, empty
# database -- which looks exactly like "my data disappeared".
BACKEND_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = BACKEND_DIR / "govan.db"

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DEFAULT_DB_PATH}")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def ensure_sqlite_schema():
    """Add MVP demo columns to an existing SQLite DB without requiring Alembic."""
    if not DATABASE_URL.startswith("sqlite"):
        return

    with engine.begin() as conn:
        user_columns = {
            row[1] for row in conn.exec_driver_sql("PRAGMA table_info(users)").fetchall()
        }
        if "is_active" not in user_columns:
            conn.exec_driver_sql("ALTER TABLE users ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT 1")
        user_additions = {
            "license_number": "license_number VARCHAR",
            "phone": "phone VARCHAR",
            "license_expiry": "license_expiry DATE",
            "organization_id": "organization_id INTEGER REFERENCES organizations(id) ON DELETE SET NULL",
        }
        for column_name, ddl in user_additions.items():
            if column_name not in user_columns:
                conn.exec_driver_sql(f"ALTER TABLE users ADD COLUMN {ddl}")
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_users_organization_id ON users(organization_id)"
        )

        vehicle_columns = {
            row[1] for row in conn.exec_driver_sql("PRAGMA table_info(vehicles)").fetchall()
        }
        additions = {
            "vehicle_type": "vehicle_type VARCHAR NOT NULL DEFAULT 'van'",
            "fuel_type": "fuel_type VARCHAR NOT NULL DEFAULT 'petrol'",
            "ownership_type": "ownership_type VARCHAR NOT NULL DEFAULT 'internal'",
            "odometer_km": "odometer_km INTEGER NOT NULL DEFAULT 0",
            "insurance_expiry": "insurance_expiry DATE",
            "fitness_expiry": "fitness_expiry DATE",
            "permit_expiry": "permit_expiry DATE",
            "next_service_due": "next_service_due DATE",
            "organization_id": "organization_id INTEGER REFERENCES organizations(id) ON DELETE SET NULL",
        }
        for column_name, ddl in additions.items():
            if column_name not in vehicle_columns:
                conn.exec_driver_sql(f"ALTER TABLE vehicles ADD COLUMN {ddl}")
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_vehicles_organization_id ON vehicles(organization_id)"
        )

        route_columns = {
            row[1] for row in conn.exec_driver_sql("PRAGMA table_info(routes)").fetchall()
        }
        route_additions = {
            "days_of_week": "days_of_week JSON NOT NULL DEFAULT '[]'",
            "valid_from": "valid_from DATE",
            "valid_to": "valid_to DATE",
            "organization_id": "organization_id INTEGER REFERENCES organizations(id) ON DELETE SET NULL",
        }
        for column_name, ddl in route_additions.items():
            if column_name not in route_columns:
                conn.exec_driver_sql(f"ALTER TABLE routes ADD COLUMN {ddl}")
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_routes_organization_id ON routes(organization_id)"
        )

        trip_columns = {
            row[1] for row in conn.exec_driver_sql("PRAGMA table_info(trips)").fetchall()
        }
        if "created_at" not in trip_columns:
            conn.exec_driver_sql("ALTER TABLE trips ADD COLUMN created_at DATETIME")

        booking_columns = {
            row[1] for row in conn.exec_driver_sql("PRAGMA table_info(bookings)").fetchall()
        }
        if "boarding_stop_id" not in booking_columns:
            conn.exec_driver_sql(
                "ALTER TABLE bookings ADD COLUMN boarding_stop_id INTEGER REFERENCES stops(id) ON DELETE SET NULL"
            )
        if "dropoff_stop_id" not in booking_columns:
            conn.exec_driver_sql(
                "ALTER TABLE bookings ADD COLUMN dropoff_stop_id INTEGER REFERENCES stops(id) ON DELETE SET NULL"
            )


def get_db():
    """FastAPI dependency: yields a session, always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
