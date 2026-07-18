from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from core.database import get_db
from models.schema import PaymentReceipt

router = APIRouter()

class PaymentRequest(BaseModel):
    patientName: str
    patientPhone: str
    type: str # 'ticket' or 'appointment'
    amount: int
    operator: str # 'Wave' or 'Orange Money'

@router.post("/")
def create_payment(req: PaymentRequest, db: Session = Depends(get_db)):
    """Generate a payment receipt."""
    receipt = PaymentReceipt(
        patientName=req.patientName,
        patientPhone=req.patientPhone,
        type=req.type,
        amount=req.amount,
        operator=req.operator,
        status="paid"
    )
    db.add(receipt)
    db.commit()
    db.refresh(receipt)
    return {"message": "Paiement validé avec succès", "data": receipt}
