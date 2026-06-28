from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from models.mock_db import db

router = APIRouter()

class MedicinePrescription(BaseModel):
    name: str
    quantity: int
    dosage: str

class PrescriptionRequest(BaseModel):
    ticketId: str
    doctorName: str
    notes: str
    medicines: List[MedicinePrescription]

@router.post("/prescribe")
async def create_prescription(request: PrescriptionRequest):
    """Créer une nouvelle ordonnance."""
    prescription = db.create_prescription(
        request.ticketId, 
        request.doctorName, 
        request.notes, 
        [m.dict() for m in request.medicines]
    )
    return prescription

@router.get("/prescriptions")
async def get_prescriptions(status: Optional[str] = None):
    """Récupérer les ordonnances (filtrées par statut)."""
    return db.get_prescriptions(status)

@router.get("/prescriptions/patient/{ticket_id}")
async def get_patient_prescriptions(ticket_id: str):
    """Récupérer les ordonnances d'un patient."""
    return db.get_patient_prescriptions(ticket_id)

class DeliverRequest(BaseModel):
    pharmacyId: int
    pharmacistName: str

@router.post("/prescriptions/{prescription_id}/deliver")
async def deliver_prescription(prescription_id: str, request: DeliverRequest):
    """Délivrer une ordonnance (déduit le stock)."""
    success = db.deliver_prescription(prescription_id, request.pharmacyId, request.pharmacistName)
    if not success:
        raise HTTPException(status_code=400, detail="Impossible de délivrer l'ordonnance. Peut-être déjà servie ou stock insuffisant.")
    return {"message": "Ordonnance délivrée avec succès."}

@router.get("/availability")
async def check_availability():
    """Vérifier la disponibilité des médicaments (sans quantités)."""
    return db.check_availability()
