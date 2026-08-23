import os
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite:///./test_society.db"
os.environ["SECRET_KEY"] = "test-secret"
os.environ["SEED_DEMO"] = "true"
from fastapi.testclient import TestClient
from app.main import Base, engine, app, init, SessionLocal, User, Role, pwd

client = TestClient(app)

def setup_module():
    Path("test_society.db").unlink(missing_ok=True)
    Base.metadata.create_all(engine)
    init()
    with SessionLocal() as session:
        if not session.query(User).filter_by(email="admin@demo.example.com").first():
            session.add(User(name="Admin", email="admin@demo.example.com", password_hash=pwd.hash("Admin123!"), role=Role.admin))
            session.commit()

def test_resident_complaint_lifecycle():
    resident = client.post("/auth/register", json={"name":"Test Resident","email":"test@example.com","password":"Password123!"})
    assert resident.status_code == 201
    headers = {"Authorization": f"Bearer {resident.json()['access_token']}"}
    created = client.post("/complaints", headers=headers, json={"category":"Plumbing","title":"Leaking pipe","description":"The kitchen pipe has been leaking since this morning."})
    assert created.status_code == 201
    assert created.json()["history"][0]["new_status"] == "Open"

def test_admin_can_update_status():
    login = client.post("/auth/login", json={"email":"admin@demo.example.com","password":"Admin123!"})
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    complaint = client.get("/complaints", headers=headers).json()[0]
    updated = client.patch(f"/complaints/{complaint['id']}", headers=headers, json={"status":"Resolved","priority":"High","note":"Repaired."})
    assert updated.status_code == 200
    assert updated.json()["status"] == "Resolved"
