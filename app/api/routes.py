# Outils FastAPI pour créer les routes et gérer les erreurs HTTP.
from fastapi import APIRouter, HTTPException

# Schémas d'entrée et de sortie de l'analyse.
from app.schemas.orientation import (
    OrientationRequest,
    OrientationResponse,
    PrecisionsRequisesResponse,
    SourcesInsuffisantesResponse,
)

# Service principal chargé d'orchestrer l'analyse.
from app.services.orientation_service import get_orientation_service


router = APIRouter()


@router.get("/")
def home():
    """Vérifie simplement que le service AdmiGuide AI fonctionne."""

    return {
        "message": "AdmiGuide AI fonctionne correctement."
    }


@router.get("/health")
def health():
    """Endpoint utilisé pour vérifier l'état du service."""

    return {
        "status": "ok"
    }


@router.post(
    "/analyze",
    response_model=(
        OrientationResponse
        | PrecisionsRequisesResponse
        | SourcesInsuffisantesResponse
    ),
)
async def analyze(request: OrientationRequest):
    """Analyse une situation administrative."""

    orientation_service = get_orientation_service()

    # Convertit les réponses Pydantic en dictionnaires simples.
    reponses = [
        reponse.model_dump()
        for reponse in request.reponses
    ]

    try:
        # Lance toute la chaîne RAG + LLM + validation.
        return await orientation_service.analyze(
            situation=request.situation,
            pays_application=request.pays_application,
            demarche_codes=request.demarche_codes,
            pays_residence=request.pays_residence,
            reponses=reponses,
        )

    except RuntimeError as exc:
        # Une indisponibilité du fournisseur IA est une erreur temporaire.
        raise HTTPException(
            status_code=503,
            detail="Le service d'analyse est temporairement indisponible.",
        ) from exc

    except ValueError as exc:
        # Une réponse IA invalide ne doit jamais être transmise au client.
        raise HTTPException(
            status_code=502,
            detail="Le service d'analyse a retourné une réponse invalide.",
        ) from exc