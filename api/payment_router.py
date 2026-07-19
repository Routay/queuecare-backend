from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from core.database import get_db
from models.schema import PaymentReceipt
from datetime import datetime

router = APIRouter()


class PaymentRequest(BaseModel):
    patientName: str
    patientPhone: str
    type: str          # 'ticket' ou 'appointment'
    amount: int
    operator: str      # 'Wave' ou 'Orange Money'


# ──────────────────────────────────────────
#  POST /payments/ — Créer un reçu
# ──────────────────────────────────────────
@router.post("/")
def create_payment(req: PaymentRequest, db: Session = Depends(get_db)):
    """Enregistre un paiement et génère un reçu numérique."""
    if req.amount <= 0:
        raise HTTPException(status_code=400, detail="Le montant doit être supérieur à 0 FCFA.")
    if req.operator not in ["Wave", "Orange Money"]:
        raise HTTPException(status_code=400, detail="Opérateur invalide. Utilisez 'Wave' ou 'Orange Money'.")
    if req.type not in ["ticket", "appointment"]:
        raise HTTPException(status_code=400, detail="Type invalide. Utilisez 'ticket' ou 'appointment'.")

    receipt = PaymentReceipt(
        patientName=req.patientName,
        patientPhone=req.patientPhone,
        type=req.type,
        amount=req.amount,
        operator=req.operator,
        date=datetime.now().isoformat(),
        status="paid"
    )
    db.add(receipt)
    db.commit()
    db.refresh(receipt)

    return {
        "message": f"Paiement de {req.amount} FCFA validé via {req.operator}.",
        "data": {
            "id": receipt.id,
            "patientName": receipt.patientName,
            "patientPhone": receipt.patientPhone,
            "type": receipt.type,
            "amount": receipt.amount,
            "operator": receipt.operator,
            "date": receipt.date,
            "status": receipt.status
        }
    }


# ──────────────────────────────────────────
#  GET /payments/ — Tous les paiements (admin)
# ──────────────────────────────────────────
@router.get("/")
def get_all_payments(db: Session = Depends(get_db)):
    """Retourne tous les reçus de paiement (réservé à l'administrateur)."""
    receipts = db.query(PaymentReceipt).order_by(PaymentReceipt.date.desc()).all()
    return {
        "total": len(receipts),
        "data": [
            {
                "id": r.id,
                "patientName": r.patientName,
                "patientPhone": r.patientPhone,
                "type": r.type,
                "amount": r.amount,
                "operator": r.operator,
                "date": r.date,
                "status": r.status
            }
            for r in receipts
        ]
    }


# ──────────────────────────────────────────
#  GET /payments/history/{phone} — Historique patient
# ──────────────────────────────────────────
@router.get("/history/{patient_phone}")
def get_patient_payment_history(patient_phone: str, db: Session = Depends(get_db)):
    """Retourne l'historique de paiements d'un patient via son numéro de téléphone."""
    receipts = db.query(PaymentReceipt).filter(
        PaymentReceipt.patientPhone == patient_phone
    ).order_by(PaymentReceipt.date.desc()).all()

    total_spent = sum(r.amount for r in receipts)

    return {
        "patientPhone": patient_phone,
        "totalTransactions": len(receipts),
        "totalSpentFCFA": total_spent,
        "data": [
            {
                "id": r.id,
                "patientName": r.patientName,
                "type": r.type,
                "amount": r.amount,
                "operator": r.operator,
                "date": r.date,
                "status": r.status
            }
            for r in receipts
        ]
    }


# ──────────────────────────────────────────
#  GET /payments/{payment_id} — Détail reçu
# ──────────────────────────────────────────
@router.get("/{payment_id}")
def get_payment_receipt(payment_id: str, db: Session = Depends(get_db)):
    """Retourne le détail d'un reçu de paiement par son identifiant."""
    receipt = db.query(PaymentReceipt).filter(PaymentReceipt.id == payment_id).first()
    if not receipt:
        raise HTTPException(status_code=404, detail="Reçu de paiement introuvable.")
    return {
        "data": {
            "id": receipt.id,
            "patientName": receipt.patientName,
            "patientPhone": receipt.patientPhone,
            "type": receipt.type,
            "amount": receipt.amount,
            "operator": receipt.operator,
            "date": receipt.date,
            "status": receipt.status
        }
    }
