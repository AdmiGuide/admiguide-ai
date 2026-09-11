from fastapi import APIRouter

# Modèle utilisé pour valider les situations reçues.
from app.schemas.orientation import OrientationRequest

# Regroupe les routes générales de l'API.
router = APIRouter()


# Vérifie que l'API répond correctement.
@router.get("/")
def root():
    return {
        "message": "AdmiGuide AI fonctionne correctement."
    }


# Vérifie l'état du service.
@router.get("/health")
def health_check():
    return {
        "status": "ok"
    }

# Reçoit et valide une situation avant son analyse par le service IA.
@router.post("/analyze")
def analyze_situation(data: OrientationRequest):
    return {
        "message": "Situation reçue et validée.",
        "situation": data.situation,
    }