"""
GoVan MVP backend -- modular monolith entrypoint.

Each domain module lives in its own router (app/routers/*), matching the
module boundaries from the SRS and the architecture diagram. This file
only wires them together; it holds no business logic of its own.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os

from .database import Base, engine, ensure_sqlite_schema
from .routers import auth, vehicles, drivers, routes, trips, bookings, alerts, maintenance, users, organizations, reports, guardian, audit
from .routers import geocode, demo
from .routers import notifications
Base.metadata.create_all(bind=engine)
ensure_sqlite_schema()

app = FastAPI(
    title="GoVan MVP API",
    description="Modular-monolith backend for the GoVan fleet coordination MVP.",
    version="0.1.0",
)

_default_origins = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174"
allowed_origins = [
    origin.strip()
    for origin in os.getenv("GOVAN_CORS_ORIGINS", _default_origins).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(vehicles.router)
app.include_router(drivers.router)
app.include_router(routes.router)
app.include_router(trips.router)
app.include_router(bookings.router)
app.include_router(alerts.router)
app.include_router(notifications.router)
app.include_router(maintenance.router)
app.include_router(geocode.router)
app.include_router(demo.router)
app.include_router(users.router)
app.include_router(organizations.router)
app.include_router(reports.router)
app.include_router(guardian.router)
app.include_router(audit.router)

@app.get("/health", tags=["health"])
def health():
    return {"status": "ok"}
