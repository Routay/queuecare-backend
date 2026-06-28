from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from models.mock_db import db

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

@router.get("/")
async def get_pharmacies():
    return db.pharmacies

@router.put("/{pharmacy_id}/stock")
async def update_pharmacy_stock(pharmacy_id: int, request: StockUpdate):
    success = db.update_stock(
        pharmacy_id, 
        request.name, 
        request.quantity, 
        request.threshold, 
        request.category, 
        request.expirationDate
    )
    if not success:
        raise HTTPException(status_code=404, detail="Pharmacy not found")
    return {"message": "Stock updated successfully"}

@router.delete("/{pharmacy_id}/stock/{medicine_name}")
async def delete_pharmacy_stock(pharmacy_id: int, medicine_name: str):
    success = db.remove_stock(pharmacy_id, medicine_name)
    if not success:
        raise HTTPException(status_code=404, detail="Pharmacy or medicine not found")
    return {"message": "Medicine removed successfully"}

@router.post("/{pharmacy_id}/transactions")
async def log_transaction(pharmacy_id: int, request: TransactionLog):
    success = db.log_transaction(pharmacy_id, request.medicine, request.type, request.quantity, request.user)
    if not success:
        raise HTTPException(status_code=404, detail="Pharmacy not found")
    return {"message": "Transaction logged successfully"}
