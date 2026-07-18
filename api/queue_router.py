from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import func
from core.database import get_db, SessionLocal
from core.websocket_manager import manager
from models.schema import QueueTicket, HistoryEntry, Prescription
from datetime import datetime

router = APIRouter()

class TicketRequest(BaseModel):
    department: str = "Consultation Générale"
    hospital_id: str

class CallNextRequest(BaseModel):
    doctorName: str = "Médecin"
    hospital_id: str

@router.post("/ticket")
async def create_ticket(request: TicketRequest, db: Session = Depends(get_db)):
    """Créer un nouveau ticket pour un patient dans un hôpital et département donnés."""
    total_tickets = db.query(QueueTicket).count() + db.query(HistoryEntry).count()
    ticket_number = f"A-{total_tickets + 100}"
    
    waiting_count = db.query(QueueTicket).filter(
        QueueTicket.department == request.department, 
        QueueTicket.hospital_id == request.hospital_id,
        QueueTicket.status == "waiting"
    ).count()
    position = waiting_count + 1
    
    ticket = QueueTicket(
        ticketNumber=ticket_number,
        department=request.department,
        position=position,
        estimatedWaitTime=position * 15,
        timestamp=datetime.now().isoformat(),
        status="waiting",
        hospital_id=request.hospital_id
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    
    await manager.broadcast_to_dashboard({"type": "queue_update", "department": request.department, "hospital_id": request.hospital_id})
    
    return {
        "id": ticket.id,
        "ticketNumber": ticket.ticketNumber,
        "department": ticket.department,
        "hospital_id": ticket.hospital_id,
        "position": ticket.position,
        "estimatedWaitTime": ticket.estimatedWaitTime,
        "timestamp": ticket.timestamp,
        "status": ticket.status
    }

@router.get("/{hospital_id}/{department}")
async def get_queue(hospital_id: str, department: str, db: Session = Depends(get_db)):
    """Retourne la liste des patients en attente pour un hôpital et service donné."""
    queue = db.query(QueueTicket).filter(
        QueueTicket.hospital_id == hospital_id,
        QueueTicket.department == department, 
        QueueTicket.status == "waiting"
    ).order_by(QueueTicket.timestamp).all()
    patients = [{
        "id": t.id,
        "ticketNumber": t.ticketNumber,
        "position": t.position,
        "estimatedWaitTime": t.estimatedWaitTime,
        "timestamp": t.timestamp,
        "status": t.status
    } for t in queue]
    
    return {
        "department": department,
        "patients": patients,
        "total": len(patients)
    }

@router.get("/{hospital_id}/departments/list")
async def get_departments(hospital_id: str, db: Session = Depends(get_db)):
    """Retourne la liste des départements d'un hôpital et le nombre d'attente."""
    deps = db.query(QueueTicket.department).filter(QueueTicket.hospital_id == hospital_id).distinct().all()
    departments = []
    for (dept_name,) in deps:
        waiting = db.query(QueueTicket).filter(
            QueueTicket.hospital_id == hospital_id,
            QueueTicket.department == dept_name, 
            QueueTicket.status == "waiting"
        ).count()
        departments.append({
            "name": dept_name,
            "waitingCount": waiting
        })
    return departments

@router.post("/{hospital_id}/{department}/next")
async def call_next_patient(hospital_id: str, department: str, request: CallNextRequest, db: Session = Depends(get_db)):
    """Appelle le patient suivant dans la file d'attente d'un hôpital."""
    first_ticket = db.query(QueueTicket).filter(
        QueueTicket.hospital_id == hospital_id,
        QueueTicket.department == department, 
        QueueTicket.status == "waiting"
    ).order_by(QueueTicket.timestamp).first()
    
    if not first_ticket:
        return {"status": "empty", "message": "Aucun patient en attente."}
        
    first_ticket.status = "completed"
    called_time = datetime.now()
    
    try:
        arrival_time = datetime.fromisoformat(first_ticket.timestamp)
        wait_minutes = int((called_time - arrival_time).total_seconds() / 60)
    except:
        wait_minutes = 0
        
    history = HistoryEntry(
        id=first_ticket.id,
        ticketNumber=first_ticket.ticketNumber,
        department=department,
        arrivalTime=first_ticket.timestamp,
        calledTime=called_time.isoformat(),
        waitMinutes=wait_minutes,
        treatedBy=request.doctorName,
        status="treated",
        hospital_id=hospital_id
    )
    db.add(history)
    db.commit()
    
    remaining_patients = db.query(QueueTicket).filter(
        QueueTicket.hospital_id == hospital_id,
        QueueTicket.department == department, 
        QueueTicket.status == "waiting"
    ).order_by(QueueTicket.timestamp).all()
    
    for index, patient in enumerate(remaining_patients):
        patient.position = index + 1
        patient.estimatedWaitTime = patient.position * 15
        await manager.send_personal_message({
            "type": "queue_update",
            "position": patient.position,
            "estimatedWaitTime": patient.estimatedWaitTime
        }, patient.id)
        
    db.commit()

    await manager.send_personal_message({
        "type": "queue_update",
        "position": 0,
        "estimatedWaitTime": 0,
        "message": "C'est votre tour !"
    }, first_ticket.id)
    
    await manager.broadcast_to_dashboard({"type": "queue_update", "department": department, "hospital_id": hospital_id})
    
    return {
        "status": "called",
        "calledTicketId": first_ticket.id,
        "remainingPatients": len(remaining_patients),
        "historyEntry": {
            "id": history.id,
            "ticketNumber": history.ticketNumber,
            "department": history.department,
            "calledTime": history.calledTime,
            "waitMinutes": history.waitMinutes,
            "treatedBy": history.treatedBy
        }
    }

# ══════════════════════════════════════
#  Historique
# ══════════════════════════════════════
@router.get("/history/all/{hospital_id}")
async def get_all_history(hospital_id: str, db: Session = Depends(get_db)):
    history = db.query(HistoryEntry).filter(HistoryEntry.hospital_id == hospital_id).order_by(HistoryEntry.calledTime.desc()).all()
    return [{"id": h.id, "ticketNumber": h.ticketNumber, "department": h.department, "calledTime": h.calledTime, "waitMinutes": h.waitMinutes, "treatedBy": h.treatedBy} for h in history]

@router.get("/history/{hospital_id}/{department}")
async def get_department_history(hospital_id: str, department: str, db: Session = Depends(get_db)):
    history = db.query(HistoryEntry).filter(
        HistoryEntry.hospital_id == hospital_id,
        HistoryEntry.department == department
    ).order_by(HistoryEntry.calledTime.desc()).all()
    return [{"id": h.id, "ticketNumber": h.ticketNumber, "department": h.department, "calledTime": h.calledTime, "waitMinutes": h.waitMinutes, "treatedBy": h.treatedBy} for h in history]

@router.get("/history/patient/{ticket_id}")
async def get_patient_record(ticket_id: str, db: Session = Depends(get_db)):
    history_entry = db.query(HistoryEntry).filter(HistoryEntry.id == ticket_id).first()
    prescriptions = db.query(Prescription).filter(Prescription.ticketId == ticket_id).all()
    
    return {
        "ticketId": ticket_id,
        "visitInfo": {
            "id": history_entry.id,
            "ticketNumber": history_entry.ticketNumber,
            "department": history_entry.department,
            "calledTime": history_entry.calledTime,
            "waitMinutes": history_entry.waitMinutes,
            "treatedBy": history_entry.treatedBy
        } if history_entry else None,
        "prescriptions": [{
            "id": p.id,
            "date": p.date,
            "doctorName": p.doctorName,
            "status": p.status
        } for p in prescriptions]
    }

# ══════════════════════════════════════
#  Statistiques
# ══════════════════════════════════════
@router.get("/statistics/overview")
async def get_statistics(hospital_id: Optional[str] = None, db: Session = Depends(get_db)):
    q_waiting = db.query(QueueTicket).filter(QueueTicket.status == "waiting")
    q_treated = db.query(HistoryEntry)
    
    if hospital_id:
        q_waiting = q_waiting.filter(QueueTicket.hospital_id == hospital_id)
        q_treated = q_treated.filter(HistoryEntry.hospital_id == hospital_id)
        
    total_waiting = q_waiting.count()
    total_treated = q_treated.count()
    
    total_wait_time = q_treated.with_entities(func.sum(HistoryEntry.waitMinutes)).scalar() or 0
    avg_wait = round(total_wait_time / total_treated, 1) if total_treated > 0 else 0
    
    deps = q_waiting.with_entities(QueueTicket.department).distinct().all()
    dept_stats = []
    
    for (dept_name,) in deps:
        waiting = q_waiting.filter(QueueTicket.department == dept_name).count()
        treated = q_treated.filter(HistoryEntry.department == dept_name).count()
        dept_stats.append({
            "name": dept_name,
            "waiting": waiting,
            "treated": treated,
            "total": waiting + treated
        })
        
    busiest = max(dept_stats, key=lambda d: d["total"]) if dept_stats else None
    
    return {
        "totalTicketsCreated": q_waiting.count() + q_treated.count(), # Approx
        "totalPatientsTreated": total_treated,
        "totalWaiting": total_waiting,
        "averageWaitMinutes": avg_wait,
        "busiestDepartment": busiest["name"] if busiest and busiest["total"] > 0 else "—",
        "departmentStats": dept_stats,
        "timestamp": datetime.now().isoformat()
    }

# ══════════════════════════════════════
#  WebSocket
# ══════════════════════════════════════
@router.websocket("/ws/dashboard")
async def websocket_dashboard(websocket: WebSocket):
    await manager.connect_dashboard(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        manager.disconnect_dashboard(websocket)

@router.websocket("/ws/{ticket_id}")
async def websocket_endpoint(websocket: WebSocket, ticket_id: str):
    await manager.connect(websocket, ticket_id)
    try:
        db = SessionLocal()
        ticket = db.query(QueueTicket).filter(QueueTicket.id == ticket_id, QueueTicket.status == "waiting").first()
        if ticket:
            await manager.send_personal_message({
                "type": "queue_update",
                "position": ticket.position,
                "estimatedWaitTime": ticket.estimatedWaitTime
            }, ticket_id)
        db.close()
        
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_json({"type": "pong"})
    
    except WebSocketDisconnect:
        manager.disconnect(websocket, ticket_id)
