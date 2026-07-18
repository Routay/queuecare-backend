from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api import queue_router, pharmacy_router, auth_router, consultation_router, appointment_router
from core.database import engine
from models import schema

schema.Base.metadata.create_all(bind=engine)

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

@app.get("/")
async def root():
    return {"message": "Bienvenue sur l'API de QueueCare SN !"}
