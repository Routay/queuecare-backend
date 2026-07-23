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
            "deliveredBy": p.deliveredBy,
            "pharmacy_id": p.pharmacy_id,
            "deliveryMethod": p.deliveryMethod,
            "deliveryAddress": p.deliveryAddress,
            "orderedAt": p.orderedAt
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


# ══════════════════════════════════════
#  Endpoints Pharmacie — Workflow de délivrance
# ══════════════════════════════════════

@router.get("/prescriptions/pharmacy/{pharmacy_id}")
async def get_pharmacy_prescriptions(
    pharmacy_id: int,
    status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Retourne toutes les ordonnances adressées à une pharmacie.
    Filtre optionnel par statut : 'pending', 'delivered', 'cancelled'.
    """
    query = db.query(Prescription)
    
    if status:
        query = query.filter(Prescription.status == status)
        if status == 'ordered':
            query = query.filter(Prescription.pharmacy_id == pharmacy_id)
            
    prescriptions = query.all()
    
    # Enrichir chaque ordonnance avec la disponibilité des médicaments en stock
    results = []
    for p in prescriptions:
        medicines_detail = []
        all_available = True
        
        for med in p.medicines:
            stock = db.query(Medicine).filter(
                Medicine.pharmacy_id == pharmacy_id,
                Medicine.name == med.name
            ).first()
            
            available = stock is not None and stock.inStock and stock.quantity >= med.quantity
            if not available:
                all_available = False
            
            medicines_detail.append({
                "name": med.name,
                "quantity": med.quantity,
                "dosage": med.dosage,
                "inStock": available,
                "stockQuantity": stock.quantity if stock else 0
            })
        
        results.append({
            "id": p.id,
            "ticketId": p.ticketId,
            "doctorName": p.doctorName,
            "date": p.date,
            "notes": p.notes,
            "status": p.status,
            "deliveredAt": p.deliveredAt,
            "deliveredBy": p.deliveredBy,
            "medicines": medicines_detail,
            "allMedicinesAvailable": all_available
        })
    
    return {
        "pharmacyId": pharmacy_id,
        "total": len(results),
        "pending": sum(1 for r in results if r["status"] == "pending"),
        "delivered": sum(1 for r in results if r["status"] == "delivered"),
        "data": results
    }


class StatusUpdate(BaseModel):
    status: str  # 'pending', 'delivered', 'cancelled'
    note: Optional[str] = None


@router.put("/prescriptions/{prescription_id}/status")
async def update_prescription_status(
    prescription_id: str,
    request: StatusUpdate,
    db: Session = Depends(get_db)
):
    """Mettre à jour le statut d'une ordonnance (confirmée, annulée, etc.)."""
    if request.status not in ["pending", "delivered", "cancelled", "confirmed"]:
        raise HTTPException(status_code=400, detail="Statut invalide.")
    
    prescription = db.query(Prescription).filter(Prescription.id == prescription_id).first()
    if not prescription:
        raise HTTPException(status_code=404, detail="Ordonnance introuvable.")
    
    if prescription.status == "delivered" and request.status != "cancelled":
        raise HTTPException(status_code=400, detail="Une ordonnance déjà délivrée ne peut pas être modifiée.")
    
    prescription.status = request.status
    if request.status == "delivered":
        prescription.deliveredAt = datetime.now().isoformat()
    
    db.commit()
    return {
        "message": f"Ordonnance mise à jour : statut '{request.status}'.",
        "prescriptionId": prescription_id,
        "newStatus": request.status
    }

# ══════════════════════════════════════
#  Endpoints Patient — Commandes
# ══════════════════════════════════════

@router.get("/prescriptions/{prescription_id}/pharmacies")
async def get_capable_pharmacies(prescription_id: str, db: Session = Depends(get_db)):
    """Retourne la liste des pharmacies capables de fournir cette ordonnance, avec leurs stocks et coordonnées."""
    prescription = db.query(Prescription).filter(Prescription.id == prescription_id).first()
    if not prescription:
        raise HTTPException(status_code=404, detail="Ordonnance introuvable.")
    
    all_pharmacies = db.query(Pharmacy).all()
    capable_pharmacies = []

    for pharmacy in all_pharmacies:
        all_available = True
        medicines_detail = []
        for med in prescription.medicines:
            stock = db.query(Medicine).filter(
                Medicine.pharmacy_id == pharmacy.id,
                Medicine.name == med.name
            ).first()
            
            available = stock is not None and stock.inStock and stock.quantity >= med.quantity
            if not available:
                all_available = False
            
            medicines_detail.append({
                "name": med.name,
                "requested": med.quantity,
                "inStock": available,
                "stockQuantity": stock.quantity if stock else 0
            })
            
        if all_available:
            capable_pharmacies.append({
                "pharmacy": {
                    "id": pharmacy.id,
                    "name": pharmacy.name,
                    "address": pharmacy.address,
                    "latitude": pharmacy.latitude,
                    "longitude": pharmacy.longitude
                },
                "medicines_detail": medicines_detail
            })
            
    return capable_pharmacies

class OrderRequest(BaseModel):
    pharmacyId: int
    deliveryMethod: str  # 'pickup' or 'delivery'
    deliveryAddress: Optional[str] = None

@router.post("/prescriptions/{prescription_id}/order")
async def place_order(prescription_id: str, request: OrderRequest, db: Session = Depends(get_db)):
    """Passe commande pour une ordonnance vers une pharmacie spécifique."""
    prescription = db.query(Prescription).filter(Prescription.id == prescription_id).first()
    if not prescription:
        raise HTTPException(status_code=404, detail="Ordonnance introuvable.")
    
    pharmacy = db.query(Pharmacy).filter(Pharmacy.id == request.pharmacyId).first()
    if not pharmacy:
        raise HTTPException(status_code=404, detail="Pharmacie introuvable.")
        
    if prescription.status != "pending":
        raise HTTPException(status_code=400, detail=f"Impossible de commander. Statut actuel: {prescription.status}")
        
    prescription.pharmacy_id = request.pharmacyId
    prescription.deliveryMethod = request.deliveryMethod
    prescription.deliveryAddress = request.deliveryAddress
    prescription.orderedAt = datetime.now().isoformat()
    prescription.status = "ordered"
    
    db.commit()
    return {"message": "Commande passée avec succès", "prescriptionId": prescription.id}
