"""
Tests complets de l'API QueueCare SN
═══════════════════════════════════════════
Couverture : Auth, Hôpitaux, File d'attente, Rendez-vous,
             Pharmacies, Consultations, Paiements
"""
import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from main import app
from core.database import get_db
from models.schema import Base

# ══════════════════════════════════════
#  Configuration de la base de test
# ══════════════════════════════════════
TEST_DB_PATH = "./test_queuecare.db"
SQLALCHEMY_DATABASE_URL = f"sqlite:///{TEST_DB_PATH}"

# Supprimer l'ancienne BD de test
if os.path.exists(TEST_DB_PATH):
    try:
        os.remove(TEST_DB_PATH)
    except PermissionError:
        pass

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


# ══════════════════════════════════════
#  Fixtures & Constantes
# ══════════════════════════════════════
HOSPITAL_NAME = "Hôpital Test Intégration"
HOSPITAL_ADDR = "123 Avenue des Tests, Dakar"
TEST_DEPARTMENT = "Consultation Générale"

# Variables partagées entre tests (remplies par les tests de création)
shared = {
    "hospital_id": None,
    "ticket_id": None,
    "ticket_number": None,
    "availability_id": None,
    "appointment_id": None,
    "prescription_id": None,
    "payment_id": None,
    "pharmacy_id": 1,
}


# ══════════════════════════════════════
#  1. Tests Racine
# ══════════════════════════════════════
class TestRoot:
    def test_root_endpoint(self):
        """GET / retourne le message d'accueil."""
        response = client.get("/")
        assert response.status_code == 200
        assert response.json() == {"message": "Bienvenue sur l'API de QueueCare SN !"}


# ══════════════════════════════════════
#  2. Tests Authentification
# ══════════════════════════════════════
class TestAuthentification:
    def test_login_identifiants_invalides(self):
        """Login avec de mauvais identifiants → 401."""
        response = client.post(
            "/auth/login",
            json={"username": "hacker", "password": "wrongpass"}
        )
        assert response.status_code == 401

    def test_login_champs_manquants(self):
        """Login sans mot de passe → 422 (validation Pydantic)."""
        response = client.post("/auth/login", json={"username": "test"})
        assert response.status_code == 422

    def test_me_sans_token(self):
        """GET /auth/me sans token → 401."""
        response = client.get("/auth/me?token=invalid-token-xxx")
        assert response.status_code == 401

    def test_logout(self):
        """POST /auth/logout est toujours 200."""
        response = client.post("/auth/logout?token=fake-token")
        assert response.status_code == 200
        assert "message" in response.json()


# ══════════════════════════════════════
#  3. Tests Hôpitaux
# ══════════════════════════════════════
class TestHopitaux:
    def test_get_hospitals_vide(self):
        """La liste des hôpitaux est accessible (peut être vide)."""
        response = client.get("/hospitals/")
        assert response.status_code == 200
        assert "data" in response.json()

    def test_create_hospital(self):
        """Créer un hôpital de test."""
        response = client.post(
            "/hospitals/",
            json={"name": HOSPITAL_NAME, "address": HOSPITAL_ADDR}
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["name"] == HOSPITAL_NAME
        assert data["address"] == HOSPITAL_ADDR
        assert "id" in data
        shared["hospital_id"] = data["id"]

    def test_create_hospital_doublon(self):
        """Créer un hôpital avec le même nom → 400."""
        response = client.post(
            "/hospitals/",
            json={"name": HOSPITAL_NAME, "address": "Autre adresse"}
        )
        assert response.status_code == 400

    def test_get_hospital_by_id(self):
        """Récupérer un hôpital par ID."""
        response = client.get(f"/hospitals/{shared['hospital_id']}")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["name"] == HOSPITAL_NAME

    def test_get_hospital_introuvable(self):
        """Hôpital inexistant → 404."""
        response = client.get("/hospitals/hosp-inexistant-xyz")
        assert response.status_code == 404

    def test_update_hospital(self):
        """Mettre à jour le nom d'un hôpital."""
        response = client.put(
            f"/hospitals/{shared['hospital_id']}",
            json={"name": "Hôpital Test Modifié"}
        )
        assert response.status_code == 200
        # Remettre le nom original pour les tests suivants
        client.put(
            f"/hospitals/{shared['hospital_id']}",
            json={"name": HOSPITAL_NAME}
        )

    def test_get_hospital_stats(self):
        """Les statistiques d'un hôpital sont accessibles."""
        response = client.get(f"/hospitals/{shared['hospital_id']}/stats")
        assert response.status_code == 200
        data = response.json()
        assert "totalWaiting" in data
        assert "totalTreated" in data
        assert "averageWaitMinutes" in data

    def test_get_hospital_staff(self):
        """Le personnel d'un hôpital est accessible."""
        response = client.get(f"/hospitals/{shared['hospital_id']}/staff")
        assert response.status_code == 200
        assert "data" in response.json()


# ══════════════════════════════════════
#  4. Tests File d'Attente
# ══════════════════════════════════════
class TestFileAttente:
    def test_create_ticket(self):
        """Créer un ticket de file d'attente."""
        response = client.post(
            "/queue/ticket",
            json={"department": TEST_DEPARTMENT, "hospital_id": shared["hospital_id"]}
        )
        assert response.status_code == 200
        data = response.json()
        assert "ticketNumber" in data
        assert data["department"] == TEST_DEPARTMENT
        assert data["status"] == "waiting"
        assert data["position"] == 1
        shared["ticket_id"] = data["id"]
        shared["ticket_number"] = data["ticketNumber"]

    def test_create_second_ticket(self):
        """Le 2e ticket a la position 2."""
        response = client.post(
            "/queue/ticket",
            json={"department": TEST_DEPARTMENT, "hospital_id": shared["hospital_id"]}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["position"] == 2

    def test_get_queue(self):
        """La file d'attente contient les tickets créés."""
        response = client.get(
            f"/queue/{shared['hospital_id']}/{TEST_DEPARTMENT}"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["department"] == TEST_DEPARTMENT
        assert len(data["patients"]) >= 2

    def test_get_departments_list(self):
        """La liste des départements est correcte."""
        response = client.get(f"/queue/{shared['hospital_id']}/departments/list")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        dept_names = [d["name"] for d in data]
        assert TEST_DEPARTMENT in dept_names

    def test_get_statistics(self):
        """Les statistiques globales de la file sont accessibles."""
        response = client.get(
            f"/queue/statistics/overview?hospital_id={shared['hospital_id']}"
        )
        assert response.status_code == 200
        data = response.json()
        assert "totalWaiting" in data
        assert "totalPatientsTreated" in data
        assert "averageWaitMinutes" in data
        assert data["totalWaiting"] >= 2

    def test_call_next_patient(self):
        """Appeler le patient suivant crée une entrée d'historique."""
        response = client.post(
            f"/queue/{shared['hospital_id']}/{TEST_DEPARTMENT}/next",
            json={"doctorName": "Dr. Test", "hospital_id": shared["hospital_id"]}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "called"
        assert "historyEntry" in data
        assert data["historyEntry"]["treatedBy"] == "Dr. Test"

    def test_call_next_recalcule_positions(self):
        """Après l'appel, le patient restant est en position 1."""
        response = client.get(
            f"/queue/{shared['hospital_id']}/{TEST_DEPARTMENT}"
        )
        data = response.json()
        if len(data["patients"]) > 0:
            assert data["patients"][0]["position"] == 1

    def test_get_history(self):
        """L'historique contient le patient appelé."""
        response = client.get(f"/queue/history/all/{shared['hospital_id']}")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert data[0]["treatedBy"] == "Dr. Test"

    def test_get_department_history(self):
        """L'historique par département fonctionne."""
        response = client.get(
            f"/queue/history/{shared['hospital_id']}/{TEST_DEPARTMENT}"
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_call_next_file_vide(self):
        """Appeler quand la file a été vidée → status 'empty' ou 'called'."""
        # Vider la file en appelant tous les patients restants
        for _ in range(5):
            res = client.post(
                f"/queue/{shared['hospital_id']}/{TEST_DEPARTMENT}/next",
                json={"doctorName": "Dr. Test", "hospital_id": shared["hospital_id"]}
            )
            if res.json().get("status") == "empty":
                break
        
        response = client.post(
            f"/queue/{shared['hospital_id']}/{TEST_DEPARTMENT}/next",
            json={"doctorName": "Dr. Test", "hospital_id": shared["hospital_id"]}
        )
        assert response.status_code == 200
        assert response.json()["status"] == "empty"


# ══════════════════════════════════════
#  5. Tests Rendez-vous
# ══════════════════════════════════════
class TestRendezVous:
    def test_create_availability(self):
        """Créer une disponibilité pour un médecin."""
        response = client.post(
            "/appointments/availabilities",
            json={
                "doctorId": "doc-test-001",
                "date": "2027-06-15",
                "startTime": "10:00",
                "endTime": "10:30"
            }
        )
        assert response.status_code == 200
        data = response.json()["data"]
        shared["availability_id"] = data["id"]

    def test_get_availabilities(self):
        """Lister les disponibilités."""
        response = client.get("/appointments/availabilities")
        assert response.status_code == 200
        assert len(response.json()["data"]) >= 1

    def test_get_availabilities_filtre_docteur(self):
        """Filtrer les disponibilités par docteur."""
        response = client.get("/appointments/availabilities?doctorId=doc-test-001")
        assert response.status_code == 200
        data = response.json()["data"]
        assert all(a["doctorId"] == "doc-test-001" for a in data)

    def test_book_appointment(self):
        """Réserver un rendez-vous."""
        response = client.post(
            "/appointments/",
            json={
                "availabilityId": shared["availability_id"],
                "patientName": "Fatou Sow",
                "patientPhone": "771234567",
                "reason": "Visite de contrôle"
            }
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["patientName"] == "Fatou Sow"
        assert data["status"] == "pending"
        shared["appointment_id"] = data["id"]

    def test_double_booking(self):
        """Réserver un créneau déjà pris → 400."""
        response = client.post(
            "/appointments/",
            json={
                "availabilityId": shared["availability_id"],
                "patientName": "Autre Patient",
                "patientPhone": "770000000",
                "reason": "Test"
            }
        )
        assert response.status_code == 400

    def test_get_appointments(self):
        """Lister tous les rendez-vous."""
        response = client.get("/appointments/")
        assert response.status_code == 200
        assert len(response.json()["data"]) >= 1

    def test_confirm_appointment(self):
        """Confirmer un rendez-vous."""
        response = client.put(
            f"/appointments/{shared['appointment_id']}/status",
            json={"status": "confirmed"}
        )
        assert response.status_code == 200

    def test_invalid_status_update(self):
        """Statut invalide → 400."""
        response = client.put(
            f"/appointments/{shared['appointment_id']}/status",
            json={"status": "invalid_status"}
        )
        assert response.status_code == 400

    def test_reschedule_appointment(self):
        """Reporter un rendez-vous vers un nouveau créneau."""
        # Créer un nouveau créneau
        new_avail = client.post(
            "/appointments/availabilities",
            json={
                "doctorId": "doc-test-001",
                "date": "2027-07-20",
                "startTime": "14:00",
                "endTime": "14:30"
            }
        )
        new_avail_id = new_avail.json()["data"]["id"]

        response = client.put(
            f"/appointments/{shared['appointment_id']}/reschedule",
            json={"newAvailabilityId": new_avail_id}
        )
        assert response.status_code == 200

    def test_cancel_appointment(self):
        """Annuler un rendez-vous libère le créneau."""
        response = client.put(
            f"/appointments/{shared['appointment_id']}/status",
            json={"status": "cancelled"}
        )
        assert response.status_code == 200

    def test_delete_availability(self):
        """Supprimer un créneau non réservé."""
        # Créer un créneau temporaire
        avail = client.post(
            "/appointments/availabilities",
            json={
                "doctorId": "doc-test-001",
                "date": "2027-12-01",
                "startTime": "08:00",
                "endTime": "08:30"
            }
        )
        avail_id = avail.json()["data"]["id"]
        response = client.delete(f"/appointments/availabilities/{avail_id}")
        assert response.status_code == 200

    def test_get_doctors(self):
        """Lister les médecins (endpoint accessible)."""
        response = client.get("/appointments/doctors")
        assert response.status_code == 200
        assert "data" in response.json()


# ══════════════════════════════════════
#  6. Tests Pharmacies
# ══════════════════════════════════════
class TestPharmacies:
    def test_setup_pharmacy(self):
        """Seed : créer une pharmacie de test si nécessaire."""
        from models.schema import Pharmacy
        db = TestingSessionLocal()
        existing = db.query(Pharmacy).filter(Pharmacy.id == 1).first()
        if not existing:
            ph = Pharmacy(id=1, name="Pharmacie Test", address="Rue du Test", latitude=14.66, longitude=-17.43)
            db.add(ph)
            db.commit()
        db.close()

    def test_get_pharmacies(self):
        """Lister les pharmacies."""
        response = client.get("/pharmacies/")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_update_stock(self):
        """Ajouter/mettre à jour un médicament dans le stock."""
        response = client.put(
            f"/pharmacies/{shared['pharmacy_id']}/stock",
            json={
                "name": "Paracétamol 500mg",
                "quantity": 200,
                "threshold": 50,
                "category": "Analgésiques",
                "expirationDate": "2028-06-30"
            }
        )
        assert response.status_code == 200

    def test_update_stock_nouveau_medicament(self):
        """Ajouter un nouveau médicament."""
        response = client.put(
            f"/pharmacies/{shared['pharmacy_id']}/stock",
            json={
                "name": "Ibuprofène 400mg",
                "quantity": 100,
                "threshold": 20,
                "category": "Anti-inflammatoires",
                "expirationDate": "2027-12-31"
            }
        )
        assert response.status_code == 200

    def test_log_transaction(self):
        """Enregistrer une transaction de mouvement de stock."""
        response = client.post(
            f"/pharmacies/{shared['pharmacy_id']}/transactions",
            json={
                "medicine": "Paracétamol 500mg",
                "type": "ENTREE",
                "quantity": 50,
                "user": "Pharmacien Test"
            }
        )
        assert response.status_code == 200

    def test_pharmacie_introuvable(self):
        """Mise à jour stock pharmacie inexistante → 404."""
        response = client.put(
            "/pharmacies/9999/stock",
            json={"name": "Test", "quantity": 1}
        )
        assert response.status_code == 404

    def test_delete_medicine(self):
        """Supprimer un médicament du stock."""
        # D'abord ajouter pour pouvoir supprimer
        client.put(
            f"/pharmacies/{shared['pharmacy_id']}/stock",
            json={"name": "Médicament Temporaire", "quantity": 5}
        )
        response = client.delete(
            f"/pharmacies/{shared['pharmacy_id']}/stock/M%C3%A9dicament%20Temporaire"
        )
        assert response.status_code == 200

    def test_delete_medicine_introuvable(self):
        """Supprimer un médicament inexistant → 404."""
        response = client.delete(
            f"/pharmacies/{shared['pharmacy_id']}/stock/MedicamentFantome"
        )
        assert response.status_code == 404


# ══════════════════════════════════════
#  7. Tests Consultations & Ordonnances
# ══════════════════════════════════════
class TestConsultations:
    def test_create_prescription(self):
        """Créer une ordonnance avec des médicaments."""
        response = client.post(
            "/consultations/prescribe",
            json={
                "ticketId": shared.get("ticket_id", "ticket-test-001"),
                "doctorName": "Dr. Test",
                "notes": "Douleurs musculaires légères.",
                "medicines": [
                    {"name": "Paracétamol 500mg", "quantity": 2, "dosage": "1 comprimé 3x/jour"},
                    {"name": "Ibuprofène 400mg", "quantity": 1, "dosage": "1 comprimé 2x/jour"}
                ]
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["doctorName"] == "Dr. Test"
        assert data["status"] == "pending"
        assert len(data["medicines"]) == 2
        shared["prescription_id"] = data["id"]

    def test_get_prescriptions(self):
        """Lister toutes les ordonnances."""
        response = client.get("/consultations/prescriptions")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_get_prescriptions_filtre_status(self):
        """Filtrer les ordonnances par statut."""
        response = client.get("/consultations/prescriptions?status=pending")
        assert response.status_code == 200
        data = response.json()
        assert all(p["status"] == "pending" for p in data)

    def test_get_patient_prescriptions(self):
        """Récupérer les ordonnances d'un patient."""
        ticket_id = shared.get("ticket_id", "ticket-test-001")
        response = client.get(f"/consultations/prescriptions/patient/{ticket_id}")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_check_availability(self):
        """Vérifier la disponibilité des médicaments."""
        response = client.get("/consultations/availability")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_get_pharmacy_prescriptions(self):
        """Récupérer les ordonnances pour une pharmacie."""
        response = client.get(
            f"/consultations/prescriptions/pharmacy/{shared['pharmacy_id']}"
        )
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "pending" in data
        assert "data" in data

    def test_deliver_prescription(self):
        """Délivrer une ordonnance (déduit le stock)."""
        response = client.post(
            f"/consultations/prescriptions/{shared['prescription_id']}/deliver",
            json={
                "pharmacyId": shared["pharmacy_id"],
                "pharmacistName": "Pharmacien Test"
            }
        )
        assert response.status_code == 200

    def test_deliver_already_delivered(self):
        """Délivrer une ordonnance déjà délivrée → 400."""
        response = client.post(
            f"/consultations/prescriptions/{shared['prescription_id']}/deliver",
            json={
                "pharmacyId": shared["pharmacy_id"],
                "pharmacistName": "Pharmacien Test"
            }
        )
        assert response.status_code == 400

    def test_update_prescription_status(self):
        """Mettre à jour le statut d'une ordonnance."""
        # Créer une nouvelle ordonnance pour ce test
        create_res = client.post(
            "/consultations/prescribe",
            json={
                "ticketId": "ticket-status-test",
                "doctorName": "Dr. Status",
                "notes": "Test de statut",
                "medicines": [{"name": "Test Med", "quantity": 1, "dosage": "1x/jour"}]
            }
        )
        new_id = create_res.json()["id"]
        
        response = client.put(
            f"/consultations/prescriptions/{new_id}/status",
            json={"status": "confirmed"}
        )
        assert response.status_code == 200
        assert response.json()["newStatus"] == "confirmed"

    def test_update_prescription_status_invalide(self):
        """Statut invalide → 400."""
        response = client.put(
            f"/consultations/prescriptions/{shared['prescription_id']}/status",
            json={"status": "invalid_status"}
        )
        assert response.status_code == 400


# ══════════════════════════════════════
#  8. Tests Paiements
# ══════════════════════════════════════
class TestPaiements:
    def test_create_payment_wave(self):
        """Créer un paiement via Wave."""
        response = client.post(
            "/payments/",
            json={
                "patientName": "Awa Diallo",
                "patientPhone": "776001234",
                "type": "ticket",
                "amount": 2000,
                "operator": "Wave"
            }
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["patientName"] == "Awa Diallo"
        assert data["status"] == "paid"
        assert data["operator"] == "Wave"
        shared["payment_id"] = data["id"]

    def test_create_payment_orange_money(self):
        """Créer un paiement via Orange Money."""
        response = client.post(
            "/payments/",
            json={
                "patientName": "Moussa Ba",
                "patientPhone": "776001234",
                "type": "appointment",
                "amount": 5000,
                "operator": "Orange Money"
            }
        )
        assert response.status_code == 200
        assert response.json()["data"]["operator"] == "Orange Money"

    def test_payment_montant_negatif(self):
        """Montant négatif → 400."""
        response = client.post(
            "/payments/",
            json={
                "patientName": "Test",
                "patientPhone": "770000000",
                "type": "ticket",
                "amount": -100,
                "operator": "Wave"
            }
        )
        assert response.status_code == 400

    def test_payment_operateur_invalide(self):
        """Opérateur invalide → 400."""
        response = client.post(
            "/payments/",
            json={
                "patientName": "Test",
                "patientPhone": "770000000",
                "type": "ticket",
                "amount": 1000,
                "operator": "Bitcoin"
            }
        )
        assert response.status_code == 400

    def test_payment_type_invalide(self):
        """Type de paiement invalide → 400."""
        response = client.post(
            "/payments/",
            json={
                "patientName": "Test",
                "patientPhone": "770000000",
                "type": "invalid",
                "amount": 1000,
                "operator": "Wave"
            }
        )
        assert response.status_code == 400

    def test_get_all_payments(self):
        """Récupérer tous les paiements."""
        response = client.get("/payments/")
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "data" in data
        assert data["total"] >= 2

    def test_get_payment_history_by_phone(self):
        """Historique de paiements d'un patient par téléphone."""
        response = client.get("/payments/history/776001234")
        assert response.status_code == 200
        data = response.json()
        assert data["patientPhone"] == "776001234"
        assert data["totalTransactions"] >= 2
        assert data["totalSpentFCFA"] >= 7000

    def test_get_payment_receipt(self):
        """Récupérer le détail d'un reçu."""
        response = client.get(f"/payments/{shared['payment_id']}")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["id"] == shared["payment_id"]

    def test_get_payment_receipt_introuvable(self):
        """Reçu inexistant → 404."""
        response = client.get("/payments/receipt-inexistant-xyz")
        assert response.status_code == 404


# ══════════════════════════════════════
#  9. Tests Hôpital — Suppression (en dernier)
# ══════════════════════════════════════
class TestHopitalCleanup:
    def test_delete_hospital(self):
        """Supprimer l'hôpital de test."""
        response = client.delete(f"/hospitals/{shared['hospital_id']}")
        assert response.status_code == 200

    def test_delete_hospital_introuvable(self):
        """Supprimer un hôpital inexistant → 404."""
        response = client.delete("/hospitals/hosp-inexistant-xyz")
        assert response.status_code == 404


# ══════════════════════════════════════
#  Cleanup final
# ══════════════════════════════════════
@pytest.fixture(scope="session", autouse=True)
def cleanup():
    yield
    engine.dispose()
    if os.path.exists(TEST_DB_PATH):
        try:
            os.remove(TEST_DB_PATH)
        except PermissionError:
            pass
