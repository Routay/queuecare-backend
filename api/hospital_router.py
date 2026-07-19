from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func
from core.database import get_db
from models.schema import Hospital, User, QueueTicket, HistoryEntry
import uuid

router = APIRouter()


class HospitalCreate(BaseModel):
    name: str
    address: str


class HospitalUpdate(BaseModel):
    name: str | None = None
    address: str | None = None


# ──────────────────────────────────────────
#  GET /hospitals/ — Liste tous les hôpitaux
# ──────────────────────────────────────────
@router.get("/")
def get_hospitals(db: Session = Depends(get_db)):
    """Retourne la liste de tous les hôpitaux enregistrés."""
    hospitals = db.query(Hospital).all()
    return {
        "data": [
            {"id": h.id, "name": h.name, "address": h.address}
            for h in hospitals
        ]
    }


# ──────────────────────────────────────────
#  POST /hospitals/ — Créer un hôpital
# ──────────────────────────────────────────
@router.post("/")
def create_hospital(req: HospitalCreate, db: Session = Depends(get_db)):
    """Créer un nouvel hôpital."""
    existing = db.query(Hospital).filter(Hospital.name == req.name).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Un hôpital nommé '{req.name}' existe déjà.")

    hospital = Hospital(
        id=f"hosp-{str(uuid.uuid4())[:8]}",
        name=req.name,
        address=req.address
    )
    db.add(hospital)
    db.commit()
    db.refresh(hospital)
    return {
        "message": "Hôpital créé avec succès.",
        "data": {"id": hospital.id, "name": hospital.name, "address": hospital.address}
    }


# ──────────────────────────────────────────
#  GET /hospitals/{hospital_id} — Détail hôpital
# ──────────────────────────────────────────
@router.get("/{hospital_id}")
def get_hospital(hospital_id: str, db: Session = Depends(get_db)):
    """Retourne les détails d'un hôpital par son identifiant."""
    hospital = db.query(Hospital).filter(Hospital.id == hospital_id).first()
    if not hospital:
        raise HTTPException(status_code=404, detail="Hôpital introuvable.")
    return {
        "data": {"id": hospital.id, "name": hospital.name, "address": hospital.address}
    }


# ──────────────────────────────────────────
#  PUT /hospitals/{hospital_id} — Modifier hôpital
# ──────────────────────────────────────────
@router.put("/{hospital_id}")
def update_hospital(hospital_id: str, req: HospitalUpdate, db: Session = Depends(get_db)):
    """Mettre à jour le nom ou l'adresse d'un hôpital."""
    hospital = db.query(Hospital).filter(Hospital.id == hospital_id).first()
    if not hospital:
        raise HTTPException(status_code=404, detail="Hôpital introuvable.")

    if req.name is not None:
        hospital.name = req.name
    if req.address is not None:
        hospital.address = req.address

    db.commit()
    db.refresh(hospital)
    return {
        "message": "Hôpital mis à jour.",
        "data": {"id": hospital.id, "name": hospital.name, "address": hospital.address}
    }


# ──────────────────────────────────────────
#  DELETE /hospitals/{hospital_id}
# ──────────────────────────────────────────
@router.delete("/{hospital_id}")
def delete_hospital(hospital_id: str, db: Session = Depends(get_db)):
    """Supprimer un hôpital (admin seulement)."""
    hospital = db.query(Hospital).filter(Hospital.id == hospital_id).first()
    if not hospital:
        raise HTTPException(status_code=404, detail="Hôpital introuvable.")

    db.delete(hospital)
    db.commit()
    return {"message": f"Hôpital '{hospital.name}' supprimé avec succès."}


# ──────────────────────────────────────────
#  GET /hospitals/{hospital_id}/stats
# ──────────────────────────────────────────
@router.get("/{hospital_id}/stats")
def get_hospital_stats(hospital_id: str, db: Session = Depends(get_db)):
    """Retourne les statistiques en temps réel pour un hôpital donné."""
    hospital = db.query(Hospital).filter(Hospital.id == hospital_id).first()
    if not hospital:
        raise HTTPException(status_code=404, detail="Hôpital introuvable.")

    total_waiting = db.query(QueueTicket).filter(
        QueueTicket.hospital_id == hospital_id,
        QueueTicket.status == "waiting"
    ).count()

    total_treated = db.query(HistoryEntry).filter(
        HistoryEntry.hospital_id == hospital_id
    ).count()

    avg_wait_result = db.query(func.avg(HistoryEntry.waitMinutes)).filter(
        HistoryEntry.hospital_id == hospital_id
    ).scalar()
    avg_wait = round(float(avg_wait_result), 1) if avg_wait_result else 0.0

    # Département le plus chargé
    busiest_dept = (
        db.query(QueueTicket.department, func.count(QueueTicket.id).label("count"))
        .filter(QueueTicket.hospital_id == hospital_id, QueueTicket.status == "waiting")
        .group_by(QueueTicket.department)
        .order_by(func.count(QueueTicket.id).desc())
        .first()
    )

    # Nombre de médecins rattachés à l'hôpital
    doctor_count = db.query(User).filter(
        User.hospital_id == hospital_id,
        User.role != "Agent Médical",
        User.role != "Pharmacien"
    ).count()

    return {
        "hospitalId": hospital_id,
        "hospitalName": hospital.name,
        "totalWaiting": total_waiting,
        "totalTreated": total_treated,
        "averageWaitMinutes": avg_wait,
        "busiestDepartment": busiest_dept[0] if busiest_dept else "—",
        "doctorCount": doctor_count
    }


# ──────────────────────────────────────────
#  GET /hospitals/{hospital_id}/staff
# ──────────────────────────────────────────
@router.get("/{hospital_id}/staff")
def get_hospital_staff(hospital_id: str, db: Session = Depends(get_db)):
    """Retourne la liste du personnel affecté à un hôpital."""
    hospital = db.query(Hospital).filter(Hospital.id == hospital_id).first()
    if not hospital:
        raise HTTPException(status_code=404, detail="Hôpital introuvable.")

    staff = db.query(User).filter(User.hospital_id == hospital_id).all()
    return {
        "hospitalName": hospital.name,
        "data": [
            {
                "id": u.id,
                "fullName": u.fullName,
                "role": u.role,
                "department": u.department,
                "avatar": u.avatar
            }
            for u in staff
        ]
    }
