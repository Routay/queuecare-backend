from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api import queue_router, pharmacy_router, auth_router, consultation_router, appointment_router, hospital_router, payment_router
from core.database import engine
from models import schema

from core.database import SessionLocal

schema.Base.metadata.create_all(bind=engine)

def seed_database():
    db = SessionLocal()
    try:
        # Seed Hospitals
        if db.query(schema.Hospital).count() == 0:
            hospitals = [
                schema.Hospital(id="hosp-fann", name="Fann", address="Avenue Cheikh Anta Diop, Dakar"),
                schema.Hospital(id="hosp-dalal", name="Dalal Jamm", address="Guédiawaye, Dakar"),
                schema.Hospital(id="hosp-principal", name="Principal", address="Avenue Nelson Mandela, Dakar"),
                schema.Hospital(id="hosp-abass", name="Abass Ndao", address="Avenue Cheikh Anta Diop, Dakar")
            ]
            db.add_all(hospitals)
            db.commit()

        # Seed Users
        if db.query(schema.User).count() == 0:
            users_to_add = [
                # Médecins
                schema.User(id="doc-001", username="dr.diallo", password="queuecare2026", fullName="Dr. Mamadou Diallo", role="Médecin Chef", department="Consultation Générale", avatar="MD", hospital_id="hosp-fann"),
                schema.User(id="doc-002", username="dr.ndiaye", password="queuecare2026", fullName="Dr. Fatou Ndiaye", role="Pédiatre", department="Pédiatrie", avatar="FN", hospital_id="hosp-dalal"),
                schema.User(id="doc-003", username="dr.fall", password="queuecare2026", fullName="Dr. Ousmane Fall", role="Cardiologue", department="Cardiologie", avatar="OF", hospital_id="hosp-principal"),
                schema.User(id="doc-004", username="dr.sow", password="queuecare2026", fullName="Dr. Awa Sow", role="Ophtalmologue", department="Ophtalmologie", avatar="AS", hospital_id="hosp-abass"),
                
                # Agents
                schema.User(id="agent-001", username="agent1", password="agent123", fullName="Agent Fann", role="Agent Médical", department="Tous", avatar="A1", hospital_id="hosp-fann"),
                schema.User(id="agent-002", username="agent2", password="agent123", fullName="Agent Dalal Jamm", role="Agent Médical", department="Tous", avatar="A2", hospital_id="hosp-dalal"),
                schema.User(id="agent-003", username="agent3", password="agent123", fullName="Agent Principal", role="Agent Médical", department="Tous", avatar="A3", hospital_id="hosp-principal"),
                schema.User(id="agent-005", username="agent5", password="agent123", fullName="Agent Abass Ndao", role="Agent Médical", department="Tous", avatar="A5", hospital_id="hosp-abass"),

                # Pharmacien
                schema.User(id="pharm-001", username="pharm.guigon", password="pharmacie2026", fullName="Pharmacie Guigon", role="Pharmacien", department="Pharmacie", avatar="PH")
            ]
            db.add_all(users_to_add)
            
        # Seed Pharmacies
        if db.query(schema.Pharmacy).count() == 0:
            pharm1 = schema.Pharmacy(id=1, name="Pharmacie Guigon", address="Avenue Georges Pompidou, Dakar", latitude=14.6672, longitude=-17.4336)
            pharm2 = schema.Pharmacy(id=2, name="Hôpital Principal de Dakar", address="Avenue Nelson Mandela", latitude=14.6601, longitude=-17.4352)
            db.add_all([pharm1, pharm2])
            db.commit() # commit pour obtenir les IDs
            
            medicines = [
                schema.Medicine(pharmacy_id=1, name="Paracétamol 500mg", inStock=True, quantity=150, threshold=50, category="Analgésiques", expirationDate="2027-12-31"),
                schema.Medicine(pharmacy_id=1, name="Amoxicilline 1g", inStock=True, quantity=12, threshold=20, category="Antibiotiques", expirationDate="2026-08-15"),
                schema.Medicine(pharmacy_id=1, name="Artemether/Lumefantrine", inStock=False, quantity=0, threshold=10, category="Antipaludiques", expirationDate="2026-10-01"),
                schema.Medicine(pharmacy_id=2, name="Paracétamol 500mg", inStock=True, quantity=500, threshold=100, category="Analgésiques", expirationDate="2028-01-01"),
                schema.Medicine(pharmacy_id=2, name="Insuline Glargine", inStock=True, quantity=45, threshold=15, category="Antidiabétiques", expirationDate="2026-05-20")
            ]
            db.add_all(medicines)
            
        db.commit()
    finally:
        db.close()

seed_database()
app = FastAPI(title="QueueCare SN - Backend API")

# Configuration CORS pour permettre à l'application mobile et web de communiquer avec l'API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # En production, spécifier les domaines exacts
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inclusion des routes
app.include_router(auth_router.router, prefix="/auth", tags=["Authentification"])
app.include_router(queue_router.router, prefix="/queue", tags=["Queue"])
app.include_router(pharmacy_router.router, prefix="/pharmacies", tags=["Pharmacies"])
app.include_router(consultation_router.router, prefix="/consultations", tags=["Consultations"])
app.include_router(appointment_router.router, prefix="/appointments", tags=["Rendez-vous"])
app.include_router(hospital_router.router, prefix="/hospitals", tags=["Hôpitaux"])
app.include_router(payment_router.router, prefix="/payments", tags=["Paiements"])

@app.get("/")
async def root():
    return {"message": "Bienvenue sur l'API de QueueCare SN !"}
