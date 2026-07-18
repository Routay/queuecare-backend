from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from models.mock_db import db

router = APIRouter()

# ══════════════════════════════════════
#  Modèles Pydantic
# ══════════════════════════════════════
class AvailabilityCreate(BaseModel):
    doctorId: str
    date: str
    startTime: str
    endTime: str

class AppointmentRequest(BaseModel):
    availabilityId: str
    patientName: str
    patientPhone: str
    reason: Optional[str] = ""

class AppointmentStatusUpdate(BaseModel):
    status: str

# ══════════════════════════════════════
#  Disponibilités (Médecins)
# ══════════════════════════════════════
@router.post("/availabilities")
def create_availability(avail: AvailabilityCreate):
    new_avail = db.add_availability(avail.doctorId, avail.date, avail.startTime, avail.endTime)
    return {"message": "Disponibilité ajoutée avec succès", "data": new_avail}

@router.get("/availabilities")
def get_availabilities(doctorId: Optional[str] = None, date: Optional[str] = None):
    avails = db.get_availabilities(doctorId, date)
    return {"data": avails}

# ══════════════════════════════════════
#  Rendez-vous (Patients & Médecins)
# ══════════════════════════════════════
@router.post("/")
def book_appointment(req: AppointmentRequest):
    result = db.book_appointment(req.patientName, req.patientPhone, req.availabilityId, req.reason)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return {"message": "Demande de rendez-vous envoyée", "data": result}

@router.get("/")
def get_appointments(doctorId: Optional[str] = None, patientPhone: Optional[str] = None):
    apps = db.get_appointments(doctorId, patientPhone)
    return {"data": apps}

@router.put("/{appointment_id}/status")
def update_appointment_status(appointment_id: str, update: AppointmentStatusUpdate):
    if update.status not in ["pending", "confirmed", "cancelled", "completed"]:
        raise HTTPException(status_code=400, detail="Statut invalide")
        
    success = db.update_appointment_status(appointment_id, update.status)
    if not success:
        raise HTTPException(status_code=404, detail="Rendez-vous introuvable")
    return {"message": f"Statut mis à jour en {update.status}"}
