from typing import Dict, List
from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        # Association d'un identifiant de ticket à une liste de WebSockets
        self.active_connections: Dict[str, List[WebSocket]] = {}
        # Connexions globales (pour les portails médicaux)
        self.dashboard_connections: List[WebSocket] = []

    # --- Connexions Patients ---
    async def connect(self, websocket: WebSocket, ticket_id: str):
        await websocket.accept()
        if ticket_id not in self.active_connections:
            self.active_connections[ticket_id] = []
        self.active_connections[ticket_id].append(websocket)
        print(f"✅ Client connecté au ticket {ticket_id}")

    def disconnect(self, websocket: WebSocket, ticket_id: str):
        if ticket_id in self.active_connections:
            if websocket in self.active_connections[ticket_id]:
                self.active_connections[ticket_id].remove(websocket)
            if len(self.active_connections[ticket_id]) == 0:
                del self.active_connections[ticket_id]
        print(f"❌ Client déconnecté du ticket {ticket_id}")

    async def send_personal_message(self, message: dict, ticket_id: str):
        """Envoie un message JSON à tous les clients connectés pour un ticket donné."""
        if ticket_id in self.active_connections:
            disconnected = []
            for connection in self.active_connections[ticket_id]:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    print(f"⚠️ Erreur d'envoi WebSocket pour {ticket_id}: {e}")
                    disconnected.append(connection)
            # Nettoyer les connexions mortes
            for conn in disconnected:
                self.active_connections[ticket_id].remove(conn)
            if ticket_id in self.active_connections and len(self.active_connections[ticket_id]) == 0:
                del self.active_connections[ticket_id]

    # --- Connexions Dashboard ---
    async def connect_dashboard(self, websocket: WebSocket):
        await websocket.accept()
        self.dashboard_connections.append(websocket)
        print("✅ Portail médical connecté au WebSocket global")

    def disconnect_dashboard(self, websocket: WebSocket):
        if websocket in self.dashboard_connections:
            self.dashboard_connections.remove(websocket)
        print("❌ Portail médical déconnecté du WebSocket global")

    async def broadcast_to_dashboard(self, message: dict):
        """Envoie un message JSON à tous les portails connectés."""
        disconnected = []
        for connection in self.dashboard_connections:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)
        for conn in disconnected:
            self.dashboard_connections.remove(conn)

    def get_connected_count(self) -> int:
        """Retourne le nombre total de connexions actives."""
        return sum(len(conns) for conns in self.active_connections.values()) + len(self.dashboard_connections)


manager = ConnectionManager()
