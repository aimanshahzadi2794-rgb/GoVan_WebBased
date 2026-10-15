from .conftest import register_and_login


def test_existing_sqlite_schema_gets_nullable_organization_columns(monkeypatch, tmp_path):
    from sqlalchemy import create_engine, inspect, text

    from app import database

    legacy_engine = create_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    with legacy_engine.begin() as connection:
        connection.execute(text("CREATE TABLE organizations (id INTEGER PRIMARY KEY)"))
        connection.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY)"))
        connection.execute(text("CREATE TABLE vehicles (id INTEGER PRIMARY KEY)"))
        connection.execute(text("CREATE TABLE routes (id INTEGER PRIMARY KEY)"))
        connection.execute(text("CREATE TABLE trips (id INTEGER PRIMARY KEY)"))
        connection.execute(text("CREATE TABLE stops (id INTEGER PRIMARY KEY)"))
        connection.execute(text("CREATE TABLE bookings (id INTEGER PRIMARY KEY)"))

    monkeypatch.setattr(database, "engine", legacy_engine)
    monkeypatch.setattr(database, "DATABASE_URL", "sqlite:///legacy.db")
    database.ensure_sqlite_schema()

    inspector = inspect(legacy_engine)
    for table in ("users", "vehicles", "routes"):
        columns = {column["name"]: column for column in inspector.get_columns(table)}
        assert columns["organization_id"]["nullable"] is True
        indexes = {index["name"] for index in inspector.get_indexes(table)}
        assert f"ix_{table}_organization_id" in indexes
    booking_columns = {
        column["name"]: column for column in inspector.get_columns("bookings")
    }
    assert booking_columns["boarding_stop_id"]["nullable"] is True
    assert booking_columns["dropoff_stop_id"]["nullable"] is True
    legacy_engine.dispose()


def test_admin_can_manage_organizations_and_assign_entities(client):
    admin = register_and_login(client, "organizations-admin@example.com", role="admin")
    created = client.post("/organizations/", json={
        "name": "Central School",
        "type": "school",
        "contact_email": "office@central.example",
    }, headers=admin)
    assert created.status_code == 201
    organization = created.json()
    organization_id = organization["id"]
    assert organization["type"] == "school"

    edited = client.patch(f"/organizations/{organization_id}", json={
        "name": "Central Academy",
        "type": "university",
    }, headers=admin)
    assert edited.status_code == 200
    assert edited.json()["name"] == "Central Academy"
    assert edited.json()["type"] == "university"

    user = client.post("/users/", json={
        "name": "Org Driver",
        "email": "org-driver@example.com",
        "password": "Passw0rd!",
        "role": "driver",
        "organization_id": organization_id,
    }, headers=admin)
    assert user.status_code == 201
    assert user.json()["organization_id"] == organization_id

    vehicle = client.post("/vehicles/", json={
        "plate_number": "ORG-101",
        "model": "Van",
        "organization_id": organization_id,
    }, headers=admin)
    assert vehicle.status_code == 201
    assert vehicle.json()["organization_id"] == organization_id

    route = client.post("/routes/", json={
        "name": "Organization route",
        "organization_id": organization_id,
    }, headers=admin)
    assert route.status_code == 201
    assert route.json()["organization_id"] == organization_id

    listed = client.get("/organizations/", headers=admin)
    assert listed.status_code == 200
    assert any(item["id"] == organization_id for item in listed.json())

    deleted = client.delete(f"/organizations/{organization_id}", headers=admin)
    assert deleted.status_code == 204
    assert client.get("/users/", headers=admin).json()[0]["organization_id"] is None
    assert client.get("/vehicles/", headers=admin).json()[0]["organization_id"] is None
    assert client.get("/routes/", headers=admin).json()[0]["organization_id"] is None


def test_organization_endpoints_require_admin(client):
    passenger = register_and_login(client, "organizations-passenger@example.com")
    admin = register_and_login(client, "organizations-permission-admin@example.com", role="admin")
    created = client.post("/organizations/", json={
        "name": "Permission Test Organization",
        "type": "company",
    }, headers=admin)
    organization_id = created.json()["id"]

    assert client.get("/organizations/", headers=passenger).status_code == 403
    assert client.post("/organizations/", json={
        "name": "Unauthorized Org",
        "type": "company",
    }, headers=passenger).status_code == 403
    assert client.patch(f"/organizations/{organization_id}", json={
        "name": "Unauthorized Edit",
    }, headers=passenger).status_code == 403
    assert client.delete(
        f"/organizations/{organization_id}", headers=passenger
    ).status_code == 403


def test_organization_assignment_rejects_unknown_ids(client):
    admin = register_and_login(client, "organizations-invalid-admin@example.com", role="admin")
    response = client.post("/vehicles/", json={
        "plate_number": "ORG-404",
        "model": "Van",
        "organization_id": 404,
    }, headers=admin)
    assert response.status_code == 404
