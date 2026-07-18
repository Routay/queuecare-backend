import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from main import app
from core.database import get_db
from models.schema import Base

SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)

def test_read_main():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Bienvenue sur l'API de QueueCare SN !"}

def test_create_ticket():
    response = client.post(
        "/queue/ticket",
        json={"department": "Consultation Générale"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "ticketNumber" in data
    assert data["department"] == "Consultation Générale"
    assert data["status"] == "waiting"

def test_get_queue():
    response = client.get("/queue/Consultation Générale")
    assert response.status_code == 200
    data = response.json()
    assert data["department"] == "Consultation Générale"
    assert "patients" in data
    assert len(data["patients"]) > 0

def test_book_appointment():
    # First create an availability
    avail_res = client.post(
        "/appointments/availabilities",
        json={
            "doctorId": "doc-001",
            "date": "2027-01-01",
            "startTime": "09:00",
            "endTime": "09:30"
        }
    )
    assert avail_res.status_code == 200
    avail_id = avail_res.json()["data"]["id"]

    # Now book the appointment
    app_res = client.post(
        "/appointments/",
        json={
            "availabilityId": avail_id,
            "patientName": "Jean Dupont",
            "patientPhone": "771234567",
            "reason": "Consultation routine"
        }
    )
    assert app_res.status_code == 200
    assert app_res.json()["data"]["patientName"] == "Jean Dupont"
    assert app_res.json()["data"]["status"] == "pending"

def test_update_appointment_status():
    apps = client.get("/appointments/")
    app_id = apps.json()["data"][0]["id"]

    res = client.put(
        f"/appointments/{app_id}/status",
        json={"status": "confirmed"}
    )
    assert res.status_code == 200
    
    # Verify
    apps = client.get("/appointments/")
    assert apps.json()["data"][0]["status"] == "confirmed"

# Cleanup database after tests
@pytest.fixture(scope="session", autouse=True)
def cleanup():
    yield
    import os
    if os.path.exists("./test.db"):
        os.remove("./test.db")
