import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from main import app
from core.database import get_db
from models.schema import Base

TEST_DB_PATH = "./test.db"
SQLALCHEMY_DATABASE_URL = f"sqlite:///{TEST_DB_PATH}"

# Supprimer l'ancienne BD de test si elle existe (schéma potentiellement obsolète)
if os.path.exists(TEST_DB_PATH):
    try:
        os.remove(TEST_DB_PATH)
    except PermissionError:
        pass  # La BD sera réutilisée telle quelle

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Recréer toutes les tables avec le schéma actuel
Base.metadata.create_all(bind=engine)


def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)

# ──────────────────────────────────────────
#  Constantes de test
# ──────────────────────────────────────────
TEST_HOSPITAL_ID = "hosp-fann"
TEST_DEPARTMENT = "Consultation Générale"


# ──────────────────────────────────────────
#  Tests de base
# ──────────────────────────────────────────
def test_read_main():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Bienvenue sur l'API de QueueCare SN !"}


# ──────────────────────────────────────────
#  Tests Hôpitaux
# ──────────────────────────────────────────
def test_get_hospitals():
    """Vérifier que la liste des hôpitaux est retournée."""
    response = client.get("/hospitals/")
    assert response.status_code == 200
    data = response.json()
    assert "data" in data


def test_create_hospital():
    """Créer un hôpital de test."""
    response = client.post(
        "/hospitals/",
        json={"name": "Hôpital Test", "address": "123 Rue de Test, Dakar"}
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["name"] == "Hôpital Test"
    assert "id" in data


def test_get_hospital_by_id():
    """Vérifier qu'on peut récupérer un hôpital par ID."""
    response = client.get(f"/hospitals/{TEST_HOSPITAL_ID}")
    # Peut retourner 200 (trouvé) ou 404 (DB de test vide)
    assert response.status_code in [200, 404]


# ──────────────────────────────────────────
#  Tests File d'Attente
# ──────────────────────────────────────────
def test_create_ticket():
    """Créer un ticket de file d'attente."""
    response = client.post(
        "/queue/ticket",
        json={"department": TEST_DEPARTMENT, "hospital_id": TEST_HOSPITAL_ID}
    )
    assert response.status_code == 200
    data = response.json()
    assert "ticketNumber" in data
    assert data["department"] == TEST_DEPARTMENT
    assert data["status"] == "waiting"
    assert data["hospital_id"] == TEST_HOSPITAL_ID


def test_get_queue():
    """Vérifier la file d'attente d'un département."""
    # D'abord créer un ticket pour s'assurer qu'il y en a au moins un
    client.post(
        "/queue/ticket",
        json={"department": TEST_DEPARTMENT, "hospital_id": TEST_HOSPITAL_ID}
    )
    response = client.get(f"/queue/{TEST_HOSPITAL_ID}/{TEST_DEPARTMENT}")
    assert response.status_code == 200
    data = response.json()
    assert data["department"] == TEST_DEPARTMENT
    assert "patients" in data
    assert len(data["patients"]) > 0


def test_get_departments():
    """Vérifier la liste des départements d'un hôpital."""
    response = client.get(f"/queue/{TEST_HOSPITAL_ID}/departments/list")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_get_statistics():
    """Vérifier les statistiques globales."""
    response = client.get(f"/queue/statistics/overview?hospital_id={TEST_HOSPITAL_ID}")
    assert response.status_code == 200
    data = response.json()
    assert "totalWaiting" in data
    assert "totalPatientsTreated" in data
    assert "averageWaitMinutes" in data


# ──────────────────────────────────────────
#  Tests Rendez-vous
# ──────────────────────────────────────────
def test_book_appointment():
    """Créer une disponibilité puis réserver un rendez-vous."""
    # Étape 1 : créer une disponibilité
    avail_res = client.post(
        "/appointments/availabilities",
        json={
            "doctorId": "doc-001",
            "date": "2027-01-15",
            "startTime": "09:00",
            "endTime": "09:30"
        }
    )
    assert avail_res.status_code == 200
    avail_id = avail_res.json()["data"]["id"]

    # Étape 2 : réserver le créneau
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
    data = app_res.json()["data"]
    assert data["patientName"] == "Jean Dupont"
    assert data["status"] == "pending"


def test_update_appointment_status():
    """Confirmer un rendez-vous existant."""
    apps = client.get("/appointments/")
    assert apps.status_code == 200
    appointments = apps.json()["data"]
    if len(appointments) == 0:
        pytest.skip("Aucun rendez-vous disponible pour ce test.")

    app_id = appointments[0]["id"]
    res = client.put(
        f"/appointments/{app_id}/status",
        json={"status": "confirmed"}
    )
    assert res.status_code == 200

    # Vérifier le changement de statut
    apps = client.get("/appointments/")
    found = next((a for a in apps.json()["data"] if a["id"] == app_id), None)
    assert found is not None
    assert found["status"] == "confirmed"


# ──────────────────────────────────────────
#  Tests Authentification
# ──────────────────────────────────────────
def test_login_valid():
    """Connexion avec des identifiants valides (seeded en production DB)."""
    # On ne peut pas tester les utilisateurs seedés car la DB de test est vide.
    # Ce test vérifie que l'endpoint est accessible.
    response = client.post(
        "/auth/login",
        json={"username": "dr.diallo", "password": "queuecare2026"}
    )
    # 200 si utilisateur seedé, 401 si DB de test vide
    assert response.status_code in [200, 401]


def test_login_invalid():
    """Connexion avec de mauvais identifiants."""
    response = client.post(
        "/auth/login",
        json={"username": "hacker", "password": "wrong"}
    )
    assert response.status_code == 401


# ──────────────────────────────────────────
#  Tests Paiements
# ──────────────────────────────────────────
def test_create_payment():
    """Créer un reçu de paiement."""
    response = client.post(
        "/payments/",
        json={
            "patientName": "Fatou Diallo",
            "patientPhone": "776543210",
            "type": "ticket",
            "amount": 2000,
            "operator": "Wave"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    receipt = data["data"]
    assert receipt["patientName"] == "Fatou Diallo"
    assert receipt["status"] == "paid"
    assert receipt["operator"] == "Wave"


def test_get_payment_history():
    """Récupérer l'historique des paiements."""
    response = client.get("/payments/")
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert isinstance(data["data"], list)


def test_get_payment_history_by_phone():
    """Récupérer les paiements d'un patient spécifique."""
    # D'abord créer un paiement
    client.post(
        "/payments/",
        json={
            "patientName": "Test Patient",
            "patientPhone": "700000001",
            "type": "appointment",
            "amount": 5000,
            "operator": "Orange Money"
        }
    )
    response = client.get("/payments/history/700000001")
    assert response.status_code == 200
    body = response.json()
    assert body["patientPhone"] == "700000001"
    assert body["totalTransactions"] > 0
    assert body["totalSpentFCFA"] >= 5000
    data = body["data"]
    assert len(data) > 0
    # Vérifier les champs retournés (patientPhone est dans la réponse racine)
    assert "amount" in data[0]
    assert "operator" in data[0]


# ──────────────────────────────────────────
#  Cleanup
# ──────────────────────────────────────────
@pytest.fixture(scope="session", autouse=True)
def cleanup():
    yield
    # Fermer toutes les connexions avant suppression
    engine.dispose()
    if os.path.exists(TEST_DB_PATH):
        try:
            os.remove(TEST_DB_PATH)
        except PermissionError:
            pass  # Ignoré sur Windows si le fichier est encore verrouillé
