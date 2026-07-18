from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from core.database import get_db
from models.schema import Hospital

router = APIRouter()

@router.get("/")
def get_hospitals(db: Session = Depends(get_db)):
    """Retrieve all hospitals."""
    hospitals = db.query(Hospital).all()
    return {"data": hospitals}
