from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from core.database import get_db
from models.schema import User
import uuid

router = APIRouter()


class LoginRequest(BaseModel):
    username: str
    password: str


# Tokens actifs en mémoire (simplifié — en prod, utiliser JWT)
active_tokens: dict = {}


@router.post("/login")
async def login(request: LoginRequest, db: Session = Depends(get_db)):
    """Authentifie un médecin ou agent médical.
    
    Retourne un token de session et les informations du profil.
    """
    user = db.query(User).filter(User.username == request.username, User.password == request.password).first()
    
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Identifiants incorrects. Vérifiez votre nom d'utilisateur et mot de passe."
        )
    
    user_data = {
        "id": user.id,
        "username": user.username,
        "fullName": user.fullName,
        "role": user.role,
        "department": user.department,
        "avatar": user.avatar,
        "hospital_id": user.hospital_id
    }
    
    # Générer un token de session simple
    token = str(uuid.uuid4())
    active_tokens[token] = user_data
    
    return {
        "token": token,
        "user": user_data
    }


@router.post("/logout")
async def logout(token: str = ""):
    """Déconnexion — invalide le token de session."""
    if token in active_tokens:
        del active_tokens[token]
    return {"message": "Déconnexion réussie."}


@router.get("/me")
async def get_current_user(token: str = ""):
    """Retourne le profil de l'utilisateur connecté."""
    if token not in active_tokens:
        raise HTTPException(status_code=401, detail="Token invalide ou expiré.")
    return active_tokens[token]


class UserCreate(BaseModel):
    username: str
    password: str
    fullName: str
    role: str
    department: str
    avatar: str
    hospital_id: str | None = None

@router.post("/register")
async def register_user(request: UserCreate, db: Session = Depends(get_db)):
    """Créer un nouvel utilisateur (Agent, Médecin, etc.)."""
    existing_user = db.query(User).filter(User.username == request.username).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Ce nom d'utilisateur est déjà pris.")
    
    # Generate unique ID based on role
    prefix = "doc-" if "Médecin" in request.role or request.role in ["Cardiologue", "Pédiatre", "Ophtalmologue"] else "agent-"
    new_id = f"{prefix}{str(uuid.uuid4())[:6]}"
    
    new_user = User(
        id=new_id,
        username=request.username,
        password=request.password,
        fullName=request.fullName,
        role=request.role,
        department=request.department,
        avatar=request.avatar,
        hospital_id=request.hospital_id
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    return {
        "message": "Utilisateur créé avec succès.",
        "user": {
            "id": new_user.id,
            "username": new_user.username,
            "fullName": new_user.fullName,
            "role": new_user.role,
            "department": new_user.department,
            "hospital_id": new_user.hospital_id
        }
    }

@router.get("/users")
async def get_users(hospital_id: str | None = None, role: str | None = None, db: Session = Depends(get_db)):
    """Retourne la liste des utilisateurs, optionnellement filtrée par hôpital ou rôle."""
    query = db.query(User)
    if hospital_id:
        query = query.filter(User.hospital_id == hospital_id)
    if role:
        query = query.filter(User.role == role)
        
    users = query.all()
    return {
        "data": [
            {
                "id": u.id,
                "username": u.username,
                "fullName": u.fullName,
                "role": u.role,
                "department": u.department,
                "avatar": u.avatar,
                "hospital_id": u.hospital_id
            } for u in users
        ]
    }

class UserUpdate(BaseModel):
    username: str | None = None
    password: str | None = None
    fullName: str | None = None
    role: str | None = None
    department: str | None = None
    avatar: str | None = None
    hospital_id: str | None = None

@router.put("/users/{user_id}")
async def update_user(user_id: str, request: UserUpdate, db: Session = Depends(get_db)):
    """Modifier les informations d'un utilisateur."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable.")
    
    # Check if username is being changed and is unique
    if request.username is not None and request.username != user.username:
        existing = db.query(User).filter(User.username == request.username).first()
        if existing:
            raise HTTPException(status_code=400, detail="Ce nom d'utilisateur est déjà pris.")
        user.username = request.username
    
    if request.password is not None:
        user.password = request.password
    if request.fullName is not None:
        user.fullName = request.fullName
        user.avatar = request.fullName[:2].upper()
    if request.role is not None:
        user.role = request.role
    if request.department is not None:
        user.department = request.department
    if request.hospital_id is not None:
        user.hospital_id = request.hospital_id
    
    db.commit()
    db.refresh(user)
    return {
        "message": "Utilisateur mis à jour avec succès.",
        "user": {
            "id": user.id,
            "username": user.username,
            "fullName": user.fullName,
            "role": user.role,
            "department": user.department,
            "avatar": user.avatar,
            "hospital_id": user.hospital_id
        }
    }

@router.delete("/users/{user_id}")
async def delete_user(user_id: str, db: Session = Depends(get_db)):
    """Supprimer un utilisateur."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable.")
    
    db.delete(user)
    db.commit()
    return {"message": f"Utilisateur {user.fullName} supprimé avec succès."}

