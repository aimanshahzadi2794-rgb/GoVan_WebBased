from app import models
from app.auth import hash_password
from tests.conftest import TestingSessionLocal, register_and_login


def test_lahore_demo_is_idempotent_and_computes_results(client):
    headers = register_and_login(client, "demo-platform@example.com", role="admin", name="Platform Admin")
    init = client.post("/demo/initialize", headers=headers)
    assert init.status_code == 200, init.text
    assert init.json()["students"] == 30
    assert init.json()["vehicles"] == 3
    assert init.json()["routes"] == 3
    assert client.post("/demo/initialize", headers=headers).json()["students"] == 30

    login = client.post("/auth/login", data={"username": "fleet.manager@demo-govan.com",
                                               "password": "GoVanDemo2026!"})
    assert login.status_code == 200
    manager_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    users = client.get("/users/", headers=manager_headers).json()
    students = [user for user in users if user["role"] == "passenger"]
    assert len(students) == 30

    result = client.post("/demo/compare", headers=manager_headers)
    assert result.status_code == 200, result.text
    assert result.json()["original"]["students"] == 30
    assert result.json()["optimized"]["students"] == 30
    assert not result.json()["constraints_violations"]
    assert client.post("/demo/cluster", headers=manager_headers).json()["passengers_clustered"] == 30
    assert len(client.post("/demo/schedule", headers=manager_headers).json()["scheduled_routes"]) == 3
    routes = client.get("/demo/map", headers=manager_headers).json()["routes"]
    assert len(routes) == 3
    assert all(len(route["geometry"]) >= 2 for route in routes)
    for route in routes:
        for point in route["markers"]:
            assert -90 <= point["lat"] <= 90 and -180 <= point["lng"] <= 180
        assert route["markers"][-1]["label"] == "Riphah International University — QIE Campus"

    assert client.get("/demo/eta", headers=manager_headers).json()["estimates"]
    assert client.post("/demo/traffic/heavy", headers=manager_headers).status_code == 200
    assert client.get("/demo/eta", headers=manager_headers).json()["traffic_scenario"] == "heavy"
    assert client.post("/demo/simulation/control/start", headers=manager_headers).json()["state"] == "running"
    tick = client.post("/demo/simulation/tick", headers=manager_headers).json()
    assert tick["updated"] == 1
    assert tick["vehicles"][0]["routing_source"] in {"osrm", "straight_line", "straight_line_fallback"}
    assert client.post("/demo/simulation/control/pause", headers=manager_headers).json()["state"] == "paused"
    assert client.post("/demo/simulation/tick", headers=manager_headers).json()["updated"] == 0
    assert client.post("/demo/simulation/control/resume", headers=manager_headers).json()["state"] == "running"
    assert client.post("/demo/simulation/control/stop", headers=manager_headers).json()["state"] == "stopped"


def test_demo_controls_are_tenant_scoped_and_reset_is_demo_only(client):
    admin_headers = register_and_login(client, "demo-reset-admin@example.com", role="admin", name="Platform Admin")
    client.post("/demo/initialize", headers=admin_headers).raise_for_status()
    outsider_headers = register_and_login(client, "outsider@example.com", name="Other Tenant User")
    assert client.get("/demo/map", headers=outsider_headers).status_code == 403
    login = client.post("/auth/login", data={"username": "fleet.manager@demo-govan.com",
                                               "password": "GoVanDemo2026!"})
    fleet_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    db = TestingSessionLocal()
    try:
        other = models.Organization(name="Real Operations", type=models.OrganizationType.company)
        db.add(other); db.flush()
        real_user = models.User(name="Real Driver", email="real-driver@example.com",
                                hashed_password=hash_password("Passw0rd!"), role=models.UserRole.driver,
                                organization_id=other.id)
        db.add(real_user); db.commit(); other_id = other.id
    finally:
        db.close()

    reset = client.post("/demo/reset", headers=fleet_headers)
    assert reset.status_code == 200, reset.text
    assert reset.json()["enabled"] is True
    assert reset.json()["students"] == 30
    db = TestingSessionLocal()
    try:
        assert db.get(models.Organization, other_id) is not None
        assert db.query(models.User).filter(models.User.email == "real-driver@example.com").first() is not None
        assert db.query(models.Organization).filter(models.Organization.name == "GoVan Lahore Demo Fleet").first() is not None
    finally:
        db.close()

