from typing import Dict, List, Any
from datetime import datetime
import uuid

# Base de données en mémoire simulant PostgreSQL / Redis
class MockDB:
    def __init__(self):
        # File d'attente par département
        # ex: {"Médecine Générale": [{"id": "...", "number": "A-123", "status": "waiting"}]}
        self.queues: Dict[str, List[Dict[str, Any]]] = {
            "Consultation Générale": [],
            "Cardiologie": [],
            "Pédiatrie": []
        }
        
        # ══════════════════════════════════════
        #  Historique des patients traités
        # ══════════════════════════════════════
        self.history: Dict[str, List[Dict[str, Any]]] = {
            "Consultation Générale": [],
            "Cardiologie": [],
            "Pédiatrie": []
        }
        
        # ══════════════════════════════════════
        #  Compteurs statistiques
        # ══════════════════════════════════════
        self.stats = {
            "total_tickets_created": 0,
            "total_patients_treated": 0,
            "total_wait_time_minutes": 0,
        }
        
        # ══════════════════════════════════════
        #  Utilisateurs autorisés (médecins/agents)
        # ══════════════════════════════════════
        self.users = [
            {
                "id": "doc-001",
                "username": "dr.diallo",
                "password": "queuecare2026",
                "fullName": "Dr. Mamadou Diallo",
                "role": "Médecin Chef",
                "department": "Consultation Générale",
                "avatar": "MD"
            },
            {
                "id": "doc-002",
                "username": "dr.ndiaye",
                "password": "queuecare2026",
                "fullName": "Dr. Fatou Ndiaye",
                "role": "Pédiatre",
                "department": "Pédiatrie",
                "avatar": "FN"
            },
            {
                "id": "agent-001",
                "username": "agent",
                "password": "agent123",
                "fullName": "Agent d'Accueil",
                "role": "Agent Médical",
                "department": "Tous",
                "avatar": "AG"
            },
            {
                "id": "pharm-001",
                "username": "pharm.guigon",
                "password": "pharmacie2026",
                "fullName": "Pharmacie Guigon",
                "role": "Pharmacien",
                "department": "Pharmacie",
                "avatar": "PH"
            }
        ]
        
        self.pharmacies: List[Dict[str, Any]] = [
            {
                "id": 1,
                "name": "Pharmacie Guigon",
                "address": "Avenue Georges Pompidou, Dakar",
                "latitude": 14.6672,
                "longitude": -17.4336,
                "stock": [
                    {"name": "Paracétamol 500mg", "inStock": True, "quantity": 150, "threshold": 50, "category": "Analgésiques", "expirationDate": "2027-12-31"},
                    {"name": "Amoxicilline 1g", "inStock": True, "quantity": 12, "threshold": 20, "category": "Antibiotiques", "expirationDate": "2026-08-15"},
                    {"name": "Artemether/Lumefantrine", "inStock": False, "quantity": 0, "threshold": 10, "category": "Antipaludiques", "expirationDate": "2026-10-01"}
                ],
                "transactions": []
            },
            {
                "id": 2,
                "name": "Hôpital Principal de Dakar",
                "address": "Avenue Nelson Mandela, Dakar",
                "latitude": 14.6631,
                "longitude": -17.4340,
                "stock": [
                    {"name": "Paracétamol 500mg", "inStock": True, "quantity": 500, "threshold": 100, "category": "Analgésiques", "expirationDate": "2028-01-01"},
                    {"name": "Amoxicilline 1g", "inStock": False, "quantity": 0, "threshold": 50, "category": "Antibiotiques", "expirationDate": "2026-09-01"},
                ],
                "transactions": []
            }
        ]

    # ══════════════════════════════════════
    #  Authentification
    # ══════════════════════════════════════
    def authenticate(self, username: str, password: str) -> Dict[str, Any] | None:
        """Vérifie les identifiants et retourne l'utilisateur ou None."""
        for user in self.users:
            if user["username"] == username and user["password"] == password:
                # Retourner sans le mot de passe
                return {k: v for k, v in user.items() if k != "password"}
        return None

    # ══════════════════════════════════════
    #  Gestion des tickets
    # ══════════════════════════════════════
    def add_ticket(self, department: str) -> Dict[str, Any]:
        if department not in self.queues:
            self.queues[department] = []
            
        queue = self.queues[department]
        ticket_number = f"A-{len(queue) + self.stats['total_tickets_created'] + 100}"
        
        ticket = {
            "id": str(uuid.uuid4()),
            "ticketNumber": ticket_number,
            "department": department,
            "position": len([t for t in queue if t["status"] == "waiting"]) + 1,
            "estimatedWaitTime": (len([t for t in queue if t["status"] == "waiting"]) + 1) * 15,
            "timestamp": datetime.now().isoformat(),
            "status": "waiting"
        }
        
        queue.append(ticket)
        self.stats["total_tickets_created"] += 1
        return ticket

    def get_position(self, department: str, ticket_id: str) -> int:
        queue = self.queues.get(department, [])
        # Position basée sur le nombre de personnes "waiting" devant ce ticket
        waiting_patients = [t for t in queue if t["status"] == "waiting"]
        for index, t in enumerate(waiting_patients):
            if t["id"] == ticket_id:
                return index + 1
        return 0

    def get_queue(self, department: str) -> List[Dict[str, Any]]:
        # Retourne les patients en attente
        queue = self.queues.get(department, [])
        return [t for t in queue if t["status"] == "waiting"]

    def call_next_patient(self, department: str, doctor_name: str = "Médecin") -> Dict[str, Any]:
        queue = self.queues.get(department, [])
        # Trouver le premier patient en attente
        for t in queue:
            if t["status"] == "waiting":
                t["status"] = "completed"
                called_time = datetime.now()
                
                # Calculer le temps d'attente réel en minutes
                try:
                    arrival_time = datetime.fromisoformat(t["timestamp"])
                    wait_minutes = int((called_time - arrival_time).total_seconds() / 60)
                except:
                    wait_minutes = 0
                
                # Sauvegarder dans l'historique
                history_entry = {
                    "id": t["id"],
                    "ticketNumber": t["ticketNumber"],
                    "department": department,
                    "arrivalTime": t["timestamp"],
                    "calledTime": called_time.isoformat(),
                    "waitMinutes": wait_minutes,
                    "treatedBy": doctor_name,
                    "status": "treated"
                }
                
                if department not in self.history:
                    self.history[department] = []
                self.history[department].append(history_entry)
                
                # Mettre à jour les statistiques
                self.stats["total_patients_treated"] += 1
                self.stats["total_wait_time_minutes"] += wait_minutes
                
                return {"called_ticket": t["id"], "history_entry": history_entry}
        return {"error": "Aucun patient en attente."}

    # ══════════════════════════════════════
    #  Historique
    # ══════════════════════════════════════
    def get_history(self, department: str | None = None) -> List[Dict[str, Any]]:
        """Retourne l'historique des patients traités, optionnellement filtré par département."""
        if department:
            return self.history.get(department, [])
        # Retourner tout l'historique, trié par date d'appel (plus récent en premier)
        all_history = []
        for dept_history in self.history.values():
            all_history.extend(dept_history)
        all_history.sort(key=lambda x: x.get("calledTime", ""), reverse=True)
        return all_history

    # ══════════════════════════════════════
    #  Statistiques
    # ══════════════════════════════════════
    def get_statistics(self) -> Dict[str, Any]:
        """Retourne les statistiques globales en temps réel."""
        total_waiting = sum(
            len([t for t in q if t["status"] == "waiting"])
            for q in self.queues.values()
        )
        
        avg_wait = 0
        if self.stats["total_patients_treated"] > 0:
            avg_wait = round(
                self.stats["total_wait_time_minutes"] / self.stats["total_patients_treated"], 1
            )
        
        # Stats par département
        dept_stats = []
        for dept_name in self.queues:
            waiting = len([t for t in self.queues[dept_name] if t["status"] == "waiting"])
            treated = len(self.history.get(dept_name, []))
            dept_stats.append({
                "name": dept_name,
                "waiting": waiting,
                "treated": treated,
                "total": waiting + treated
            })
        
        # Trouver le département le plus chargé
        busiest = max(dept_stats, key=lambda d: d["total"]) if dept_stats else None
        
        return {
            "totalTicketsCreated": self.stats["total_tickets_created"],
            "totalPatientsTreated": self.stats["total_patients_treated"],
            "totalWaiting": total_waiting,
            "averageWaitMinutes": avg_wait,
            "busiestDepartment": busiest["name"] if busiest and busiest["total"] > 0 else "—",
            "departmentStats": dept_stats,
            "timestamp": datetime.now().isoformat()
        }

    # ══════════════════════════════════════
    #  Pharmacie
    # ══════════════════════════════════════
    def update_stock(self, pharmacy_id: int, medicine_name: str, quantity: int, threshold: int = 10, category: str = "Général", expiration_date: str = "2099-12-31", in_stock: bool = None) -> bool:
        for pharmacy in self.pharmacies:
            if pharmacy["id"] == pharmacy_id:
                # Chercher si le médicament existe déjà
                for item in pharmacy["stock"]:
                    if item["name"].lower() == medicine_name.lower():
                        item["quantity"] = quantity
                        item["inStock"] = quantity > 0
                        item["threshold"] = threshold
                        item["category"] = category
                        item["expirationDate"] = expiration_date
                        return True
                
                # S'il n'existe pas, l'ajouter
                pharmacy["stock"].append({
                    "name": medicine_name, 
                    "inStock": quantity > 0,
                    "quantity": quantity,
                    "threshold": threshold,
                    "category": category,
                    "expirationDate": expiration_date
                })
                return True
        return False

    def remove_stock(self, pharmacy_id: int, medicine_name: str) -> bool:
        for pharmacy in self.pharmacies:
            if pharmacy["id"] == pharmacy_id:
                initial_length = len(pharmacy["stock"])
                pharmacy["stock"] = [item for item in pharmacy["stock"] if item["name"].lower() != medicine_name.lower()]
                return len(pharmacy["stock"]) < initial_length
        return False

    def log_transaction(self, pharmacy_id: int, medicine_name: str, type: str, quantity: int, user: str):
        for pharmacy in self.pharmacies:
            if pharmacy["id"] == pharmacy_id:
                transaction = {
                    "id": str(uuid.uuid4()),
                    "date": datetime.now().isoformat(),
                    "medicine": medicine_name,
                    "type": type, # "ENTREE" or "SORTIE"
                    "quantity": quantity,
                    "user": user
                }
                pharmacy["transactions"].append(transaction)
                return True
        return False

# Instance globale
db = MockDB()
