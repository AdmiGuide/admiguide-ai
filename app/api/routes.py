from pathlib import Path
import tempfile

# Outils FastAPI pour créer les routes,
# recevoir les fichiers et gérer les erreurs HTTP.
from fastapi import (
    APIRouter,
    File,
    HTTPException,
    UploadFile,
)
from app.services.transcription_service import (
    TranscriptionError,
    transcribe_audio as transcribe_audio_file,
)

# Service chargé de nettoyer les enregistrements vocaux.
from app.services.audio_cleaning_service import (
    AudioCleaningError,
    clean_audio,
)

# Schémas d'entrée et de sortie de l'analyse.
from app.schemas.orientation import (
    OrientationRequest,
    OrientationResponse,
    PrecisionsRequisesResponse,
    SourcesInsuffisantesResponse,
)

# Service principal chargé d'orchestrer l'analyse.
from app.services.orientation_service import (
    get_orientation_service,
)


router = APIRouter()


# ==========================================================
# ACCUEIL
# ==========================================================

@router.get("/")
def home():
    """Vérifie simplement que le service AdmiGuide AI fonctionne."""

    return {
        "message": "AdmiGuide AI fonctionne correctement."
    }


# ==========================================================
# HEALTH CHECK
# ==========================================================

@router.get("/health")
def health():
    """Endpoint utilisé pour vérifier l'état du service."""

    return {
        "status": "ok"
    }


# ==========================================================
# SAISIE VOCALE
# ==========================================================

@router.post("/transcribe")
async def transcribe_audio(
    audio: UploadFile = File(...),
):
    """
    Reçoit un enregistrement vocal, le nettoie avec FFmpeg,
    puis retourne sa transcription en texte.

    Les fichiers temporaires sont supprimés après traitement.
    """

    # Vérifie que le fichier reçu est bien un fichier audio.
    if (
        not audio.content_type
        or not audio.content_type.startswith("audio/")
    ):
        raise HTTPException(
            status_code=400,
            detail="Le fichier envoyé doit être un fichier audio.",
        )

    audio_content = await audio.read()

    if not audio_content:
        raise HTTPException(
            status_code=400,
            detail="Le fichier audio est vide.",
        )

    # Limite aussi la taille côté microservice IA.
    max_size = 10 * 1024 * 1024

    if len(audio_content) > max_size:
        raise HTTPException(
            status_code=400,
            detail="Le fichier audio est trop volumineux.",
        )

    # Conserve l'extension du fichier original.
    suffix = Path(
        audio.filename or "audio.webm"
    ).suffix or ".webm"

    temporary_path: Path | None = None
    cleaned_path: Path | None = None

    try:

        # Enregistre temporairement l'audio original.
        with tempfile.NamedTemporaryFile(
            suffix=suffix,
            delete=False,
        ) as temporary_file:

            temporary_file.write(audio_content)
            temporary_path = Path(
                temporary_file.name
            )

        # Prépare le fichier WAV produit par FFmpeg.
        with tempfile.NamedTemporaryFile(
            suffix=".wav",
            delete=False,
        ) as cleaned_file:

            cleaned_path = Path(
                cleaned_file.name
            )

        try:
            clean_audio(
                input_path=temporary_path,
                output_path=cleaned_path,
            )

        except AudioCleaningError as exc:
            raise HTTPException(
                status_code=500,
                detail=(
                    "Impossible de nettoyer "
                    "l'enregistrement audio."
                ),
            ) from exc

        try:
            transcription = await transcribe_audio_file(
                audio_path=cleaned_path,
            )

        except TranscriptionError as exc:
            raise HTTPException(
                status_code=503,
                detail=(
                    "Le service de transcription "
                    "est temporairement indisponible."
                ),
            ) from exc

        return {
            "message": "Audio transcrit correctement.",
            "transcription": transcription,
        }

    finally:

        # Les fichiers vocaux ne sont pas conservés.
        if (
            temporary_path is not None
            and temporary_path.exists()
        ):
            temporary_path.unlink()

        if (
            cleaned_path is not None
            and cleaned_path.exists()
        ):
            cleaned_path.unlink()

        await audio.close()


# ==========================================================
# ANALYSE DE LA SITUATION ADMINISTRATIVE
# ==========================================================

@router.post(
    "/analyze",
    response_model=(
        OrientationResponse
        | PrecisionsRequisesResponse
        | SourcesInsuffisantesResponse
    ),
)
async def analyze(
    request: OrientationRequest,
):
    """Analyse une situation administrative."""

    orientation_service = (
        get_orientation_service()
    )

    # Convertit les réponses Pydantic
    # en dictionnaires simples.
    reponses = [
        reponse.model_dump()
        for reponse in request.reponses
    ]

    try:

        # Lance toute la chaîne :
        # RAG + LLM + validation.
        return await orientation_service.analyze(
            situation=request.situation,
            demarche_codes=request.demarche_codes,
            reponses=reponses,
        )

    except RuntimeError as exc:

        # Une indisponibilité du fournisseur IA
        # est considérée comme temporaire.
        raise HTTPException(
            status_code=503,
            detail=(
                "Le service d'analyse est "
                "temporairement indisponible."
            ),
        ) from exc

    except ValueError as exc:

        # Une réponse IA invalide ne doit jamais
        # être transmise telle quelle au frontend.
        raise HTTPException(
            status_code=502,
            detail=(
                "Le service d'analyse a retourné "
                "une réponse invalide."
            ),
        ) from exc