from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from core.database import get_db
from models.schema import Availability, Appointment

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

class AppointmentReschedule(BaseModel):
    newAvailabilityId: str

# ══════════════════════════════════════
#  Disponibilités (Médecins)
# ══════════════════════════════════════
@router.post("/availabilities")
def create_availability(avail: AvailabilityCreate, db: Session = Depends(get_db)):
    new_avail = Availability(
        doctorId=avail.doctorId,
        date=avail.date,
        startTime=avail.startTime,
        endTime=avail.endTime
    )
    db.add(new_avail)
    db.commit()
    db.refresh(new_avail)
    return {"message": "Disponibilité ajoutée avec succès", "data": new_avail}

@router.get("/availabilities")
def get_availabilities(doctorId: Optional[str] = None, date: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(Availability)
    if doctorId:
        query = query.filter(Availability.doctorId == doctorId)
    if date:
        query = query.filter(Availability.date == date)
    avails = query.all()
    return {"data": avails}

@router.delete("/availabilities/{avail_id}")
def delete_availability(avail_id: str, db: Session = Depends(get_db)):
    avail = db.query(Availability).filter(Availability.id == avail_id).first()
    if not avail:
        raise HTTPException(status_code=404, detail="Disponibilité introuvable")
    if avail.isBooked:
        raise HTTPException(status_code=400, detail="Impossible de supprimer un créneau déjà réservé")
        
    db.delete(avail)
    db.commit()
    return {"message": "Créneau supprimé avec succès"}

# ══════════════════════════════════════
#  Rendez-vous (Patients & Médecins)
# ══════════════════════════════════════
@router.post("/")
def book_appointment(req: AppointmentRequest, db: Session = Depends(get_db)):
    avail = db.query(Availability).filter(Availability.id == req.availabilityId).first()
    if not avail or avail.isBooked:
        raise HTTPException(status_code=400, detail="Disponibilité invalide ou déjà réservée")
        
    avail.isBooked = True
    
    appointment = Appointment(
        availabilityId=req.availabilityId,
        doctorId=avail.doctorId,
        patientName=req.patientName,
        patientPhone=req.patientPhone,
        date=avail.date,
        startTime=avail.startTime,
        endTime=avail.endTime,
        reason=req.reason
    )
    db.add(appointment)
    db.commit()
    db.refresh(appointment)
    
    return {"message": "Demande de rendez-vous envoyée", "data": appointment}

@router.get("/")
def get_appointments(doctorId: Optional[str] = None, patientPhone: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(Appointment)
    if doctorId:
        query = query.filter(Appointment.doctorId == doctorId)
    if patientPhone:
        query = query.filter(Appointment.patientPhone == patientPhone)
    apps = query.all()
    return {"data": apps}

@router.put("/{appointment_id}/status")
def update_appointment_status(appointment_id: str, update: AppointmentStatusUpdate, db: Session = Depends(get_db)):
    if update.status not in ["pending", "confirmed", "cancelled", "completed"]:
        raise HTTPException(status_code=400, detail="Statut invalide")
        
    app = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Rendez-vous introuvable")
        
    app.status = update.status
    if update.status == "cancelled":
        avail = db.query(Availability).filter(Availability.id == app.availabilityId).first()
        if avail:
            avail.isBooked = False
            
    db.commit()
    return {"message": f"Statut mis à jour en {update.status}"}

@router.put("/{appointment_id}/reschedule")
def reschedule_appointment(appointment_id: str, req: AppointmentReschedule, db: Session = Depends(get_db)):
    # 1. Trouver le rendez-vous
    app = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Rendez-vous introuvable")

    # 2. Trouver la nouvelle disponibilité
    new_avail = db.query(Availability).filter(Availability.id == req.newAvailabilityId).first()
    if not new_avail or new_avail.isBooked:
        raise HTTPException(status_code=400, detail="Nouvelle disponibilité invalide ou déjà réservée")

    # 3. Libérer l'ancienne disponibilité
    old_avail = db.query(Availability).filter(Availability.id == app.availabilityId).first()
    if old_avail:
        old_avail.isBooked = False

    # 4. Réserver la nouvelle
    new_avail.isBooked = True

    # 5. Mettre à jour le rendez-vous
    app.availabilityId = new_avail.id
    app.date = new_avail.date
    app.startTime = new_avail.startTime
    app.endTime = new_avail.endTime
    
    # On peut le repasser en pending s'il était annulé, ou le laisser dans son statut actuel
    if app.status == 'cancelled':
        app.status = 'pending'

    db.commit()
    return {"message": "Rendez-vous reporté avec succès"}
