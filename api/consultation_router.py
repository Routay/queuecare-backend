from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy.orm import Session
from core.database import get_db
from models.schema import Prescription, PrescriptionMedicine, Medicine, Pharmacy
from datetime import datetime

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
async def create_prescription(request: PrescriptionRequest, db: Session = Depends(get_db)):
    """Créer une nouvelle ordonnance."""
    prescription = Prescription(
        ticketId=request.ticketId,
        doctorName=request.doctorName,
        date=datetime.now().isoformat(),
        notes=request.notes,
        status="pending"
    )
    db.add(prescription)
    db.flush()  # Pour obtenir l'ID généré

    for med in request.medicines:
        pm = PrescriptionMedicine(
            prescription_id=prescription.id,
            name=med.name,
            quantity=med.quantity,
            dosage=med.dosage
        )
        db.add(pm)

    db.commit()
    db.refresh(prescription)

    return {
        "id": prescription.id,
        "ticketId": prescription.ticketId,
        "doctorName": prescription.doctorName,
        "date": prescription.date,
        "notes": prescription.notes,
        "medicines": [{"name": m.name, "quantity": m.quantity, "dosage": m.dosage} for m in prescription.medicines],
        "status": prescription.status
    }

@router.get("/prescriptions")
async def get_prescriptions(status: Optional[str] = None, db: Session = Depends(get_db)):
    """Récupérer les ordonnances (filtrées par statut)."""
    query = db.query(Prescription)
    if status:
        query = query.filter(Prescription.status == status)
    prescriptions = query.all()

    return [
        {
            "id": p.id,
            "ticketId": p.ticketId,
            "doctorName": p.doctorName,
            "date": p.date,
            "notes": p.notes,
            "medicines": [{"name": m.name, "quantity": m.quantity, "dosage": m.dosage} for m in p.medicines],
            "status": p.status,
            "deliveredAt": p.deliveredAt,
            "deliveredBy": p.deliveredBy
        } for p in prescriptions
    ]

@router.get("/prescriptions/patient/{ticket_id}")
async def get_patient_prescriptions(ticket_id: str, db: Session = Depends(get_db)):
    """Récupérer les ordonnances d'un patient."""
    prescriptions = db.query(Prescription).filter(Prescription.ticketId == ticket_id).all()
    return [
        {
            "id": p.id,
            "ticketId": p.ticketId,
            "doctorName": p.doctorName,
            "date": p.date,
            "notes": p.notes,
            "medicines": [{"name": m.name, "quantity": m.quantity, "dosage": m.dosage} for m in p.medicines],
            "status": p.status,
            "deliveredAt": p.deliveredAt,
            "deliveredBy": p.deliveredBy
        } for p in prescriptions
    ]

class DeliverRequest(BaseModel):
    pharmacyId: int
    pharmacistName: str

@router.post("/prescriptions/{prescription_id}/deliver")
async def deliver_prescription(prescription_id: str, request: DeliverRequest, db: Session = Depends(get_db)):
    """Délivrer une ordonnance (déduit le stock)."""
    prescription = db.query(Prescription).filter(Prescription.id == prescription_id).first()

    if not prescription or prescription.status == "delivered":
        raise HTTPException(status_code=400, detail="Impossible de délivrer l'ordonnance. Peut-être déjà servie ou introuvable.")

    # Déduire le stock pour chaque médicament
    for med in prescription.medicines:
        medicine = db.query(Medicine).filter(
            Medicine.pharmacy_id == request.pharmacyId,
            Medicine.name == med.name
        ).first()

        if medicine and medicine.quantity >= med.quantity:
            medicine.quantity -= med.quantity
            medicine.inStock = medicine.quantity > 0

    prescription.status = "delivered"
    prescription.deliveredAt = datetime.now().isoformat()
    prescription.deliveredBy = request.pharmacistName

    db.commit()
    return {"message": "Ordonnance délivrée avec succès."}

@router.get("/availability")
async def check_availability(db: Session = Depends(get_db)):
    """Vérifier la disponibilité des médicaments (sans quantités)."""
    medicines = db.query(Medicine).all()
    availability = {}
    for item in medicines:
        name = item.name
        if name not in availability:
            availability[name] = {"name": name, "available": item.inStock, "category": item.category or "Général"}
        else:
            if item.inStock:
                availability[name]["available"] = True
    return list(availability.values())
