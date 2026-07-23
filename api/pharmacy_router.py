from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from core.database import get_db
from models.schema import Pharmacy, Medicine, Transaction

router = APIRouter()

class StockUpdate(BaseModel):
    name: str
    quantity: int
    threshold: int = 10
    category: str = "Général"
    expirationDate: str = "2099-12-31"

class TransactionLog(BaseModel):
    medicine: str
    type: str
    quantity: int
    user: str

class PharmacyCreate(BaseModel):
    name: str
    address: str
    latitude: float = 0.0
    longitude: float = 0.0

@router.post("/")
async def create_pharmacy(request: PharmacyCreate, db: Session = Depends(get_db)):
    """Créer une nouvelle pharmacie."""
    new_pharmacy = Pharmacy(
        name=request.name,
        address=request.address,
        latitude=request.latitude,
        longitude=request.longitude
    )
    db.add(new_pharmacy)
    db.commit()
    db.refresh(new_pharmacy)
    return {
        "message": "Pharmacie créée avec succès.",
        "data": {
            "id": new_pharmacy.id,
            "name": new_pharmacy.name,
            "address": new_pharmacy.address
        }
    }

@router.delete("/{pharmacy_id}")
async def delete_pharmacy(pharmacy_id: int, db: Session = Depends(get_db)):
    """Supprimer une pharmacie."""
    pharmacy = db.query(Pharmacy).filter(Pharmacy.id == pharmacy_id).first()
    if not pharmacy:
        raise HTTPException(status_code=404, detail="Pharmacie introuvable.")
    
    db.delete(pharmacy)
    db.commit()
    return {"message": "Pharmacie supprimée avec succès."}

@router.get("/")
async def get_pharmacies(db: Session = Depends(get_db)):
    pharmacies = db.query(Pharmacy).all()
    # Eagerly load stock and transactions or just return the ORM object if FastAPI Pydantic allows it
    # We will manually construct the dict to match previous behavior
    result = []
    for p in pharmacies:
        result.append({
            "id": p.id,
            "name": p.name,
            "address": p.address,
            "latitude": p.latitude,
            "longitude": p.longitude,
            "stock": [
                {
                    "name": m.name,
                    "inStock": m.inStock,
                    "quantity": m.quantity,
                    "threshold": m.threshold,
                    "category": m.category,
                    "expirationDate": m.expirationDate
                } for m in p.stock
            ],
            "transactions": [
                {
                    "id": t.id,
                    "date": t.date,
                    "medicine": t.medicine,
                    "type": t.type,
                    "quantity": t.quantity,
                    "user": t.user
                } for t in p.transactions
            ]
        })
    return result

@router.put("/{pharmacy_id}/stock")
async def update_pharmacy_stock(pharmacy_id: int, request: StockUpdate, db: Session = Depends(get_db)):
    pharmacy = db.query(Pharmacy).filter(Pharmacy.id == pharmacy_id).first()
    if not pharmacy:
        raise HTTPException(status_code=404, detail="Pharmacy not found")
        
    medicine = db.query(Medicine).filter(Medicine.pharmacy_id == pharmacy_id, Medicine.name == request.name).first()
    if medicine:
        medicine.quantity = request.quantity
        medicine.inStock = request.quantity > 0
        medicine.threshold = request.threshold
        medicine.category = request.category
        medicine.expirationDate = request.expirationDate
    else:
        new_med = Medicine(
            pharmacy_id=pharmacy_id,
            name=request.name,
            inStock=request.quantity > 0,
            quantity=request.quantity,
            threshold=request.threshold,
            category=request.category,
            expirationDate=request.expirationDate
        )
        db.add(new_med)
        
    db.commit()
    return {"message": "Stock updated successfully"}

@router.delete("/{pharmacy_id}/stock/{medicine_name}")
async def delete_pharmacy_stock(pharmacy_id: int, medicine_name: str, db: Session = Depends(get_db)):
    medicine = db.query(Medicine).filter(Medicine.pharmacy_id == pharmacy_id, Medicine.name == medicine_name).first()
    if not medicine:
        raise HTTPException(status_code=404, detail="Pharmacy or medicine not found")
        
    db.delete(medicine)
    db.commit()
    return {"message": "Medicine removed successfully"}

@router.post("/{pharmacy_id}/transactions")
async def log_transaction(pharmacy_id: int, request: TransactionLog, db: Session = Depends(get_db)):
    pharmacy = db.query(Pharmacy).filter(Pharmacy.id == pharmacy_id).first()
    if not pharmacy:
        raise HTTPException(status_code=404, detail="Pharmacy not found")
        
    import datetime
    transaction = Transaction(
        pharmacy_id=pharmacy_id,
        date=datetime.datetime.now().isoformat(),
        medicine=request.medicine,
        type=request.type,
        quantity=request.quantity,
        user=request.user
    )
    db.add(transaction)
    db.commit()
    return {"message": "Transaction logged successfully"}
