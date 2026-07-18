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
        "avatar": user.avatar
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
