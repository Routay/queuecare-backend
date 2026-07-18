from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from typing import Optional
from models.mock_db import db
from core.websocket_manager import manager
import asyncio

router = APIRouter()

class TicketRequest(BaseModel):
    department: str = "Consultation Générale"


class CallNextRequest(BaseModel):
    doctorName: str = "Médecin"


@router.post("/ticket")
async def create_ticket(request: TicketRequest):
    """Créer un nouveau ticket pour un patient dans un département donné."""
    ticket = db.add_ticket(request.department)
    
    # Notifier les portails médicaux du changement
    await manager.broadcast_to_dashboard({"type": "queue_update", "department": request.department})
    
    return ticket


@router.get("/{department}")
async def get_queue(department: str):
    """Retourne la liste des patients en attente pour un service donné.
    Utilisé par le portail médical pour afficher la file d'attente."""
    queue = db.get_queue(department)
    return {
        "department": department,
        "patients": queue,
        "total": len(queue)
    }


@router.get("/departments/list")
async def get_departments():
    """Retourne la liste de tous les départements disponibles."""
    departments = []
    for dept_name, queue in db.queues.items():
        waiting = [t for t in queue if t["status"] == "waiting"]
        departments.append({
            "name": dept_name,
            "waitingCount": len(waiting)
        })
    return departments


@router.post("/{department}/next")
async def call_next_patient(department: str, doctorName: str = "Médecin"):
    """Appelle le patient suivant dans la file d'attente.
    
    Actions :
    1. Marque le premier patient 'waiting' comme 'completed'.
    2. Sauvegarde le patient dans l'historique.
    3. Recalcule les positions de tous les patients restants.
    4. Envoie une notification WebSocket à chaque patient concerné.
    """
    result = db.call_next_patient(department, doctorName)
    
    if "error" in result:
        return {"status": "empty", "message": result["error"]}
    
    called_ticket_id = result["called_ticket"]
    
    # Envoyer la notification "C'est votre tour !" au patient appelé
    await manager.send_personal_message({
        "type": "queue_update",
        "position": 0,
        "estimatedWaitTime": 0,
        "message": "C'est votre tour !"
    }, called_ticket_id)
    
    # Recalculer et notifier TOUS les patients restants dans cette file
    remaining_patients = db.get_queue(department)
    for index, patient in enumerate(remaining_patients):
        new_position = index + 1
        await manager.send_personal_message({
            "type": "queue_update",
            "position": new_position,
            "estimatedWaitTime": new_position * 15
        }, patient["id"])
    
    # Notifier les portails médicaux du changement
    await manager.broadcast_to_dashboard({"type": "queue_update", "department": department})
    
    return {
        "status": "called",
        "calledTicketId": called_ticket_id,
        "remainingPatients": len(remaining_patients),
        "historyEntry": result.get("history_entry")
    }


# ══════════════════════════════════════
#  Historique des patients traités
# ══════════════════════════════════════

@router.get("/history/all")
async def get_all_history():
    """Retourne l'historique complet de tous les patients traités."""
    return db.get_history()


@router.get("/history/{department}")
async def get_department_history(department: str):
    """Retourne l'historique des patients traités pour un département donné."""
    return db.get_history(department)

@router.get("/history/patient/{ticket_id}")
async def get_patient_record(ticket_id: str):
    """Retourne le dossier médical (historique + ordonnances) pour un ticket donné."""
    history_entry = None
    for dept_history in db.history.values():
        for entry in dept_history:
            if entry["id"] == ticket_id:
                history_entry = entry
                break
        if history_entry:
            break
            
    prescriptions = db.get_patient_prescriptions(ticket_id)
    
    return {
        "ticketId": ticket_id,
        "visitInfo": history_entry,
        "prescriptions": prescriptions
    }


# ══════════════════════════════════════
#  Statistiques en temps réel
# ══════════════════════════════════════

@router.get("/statistics/overview")
async def get_statistics():
    """Retourne les statistiques globales de l'écosystème QueueCare."""
    return db.get_statistics()


# ══════════════════════════════════════
#  WebSocket temps réel
# ══════════════════════════════════════

@router.websocket("/ws/dashboard")
async def websocket_dashboard(websocket: WebSocket):
    """Endpoint WebSocket global pour le portail médical.
    
    Permet de recevoir des notifications en temps réel lors d'un 
    changement dans n'importe quelle file d'attente.
    """
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
    """Endpoint WebSocket pour le suivi en temps réel de la position d'un patient.
    
    Le serveur maintient la connexion ouverte et envoie des mises à jour
    lorsque le médecin appelle le patient suivant via POST /queue/{dept}/next.
    """
    await manager.connect(websocket, ticket_id)
    try:
        # Envoyer la position initiale dès la connexion
        found_department = None
        for dept, queue in db.queues.items():
            for t in queue:
                if t["id"] == ticket_id and t["status"] == "waiting":
                    found_department = dept
                    break
            if found_department:
                break
        
        if found_department:
            current_position = db.get_position(found_department, ticket_id)
            await manager.send_personal_message({
                "type": "queue_update",
                "position": current_position,
                "estimatedWaitTime": current_position * 15
            }, ticket_id)
        
        # Garder la connexion ouverte — les mises à jour arrivent
        # via call_next_patient() quand le médecin appuie sur le bouton
        while True:
            # Recevoir les messages du client (heartbeat / keep-alive)
            data = await websocket.receive_text()
            # On peut traiter les messages du client si nécessaire
            if data == "ping":
                await websocket.send_json({"type": "pong"})
    
    except WebSocketDisconnect:
        manager.disconnect(websocket, ticket_id)
