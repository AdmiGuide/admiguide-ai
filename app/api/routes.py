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
    Reçoit l'enregistrement vocal envoyé par le frontend.

    À cette étape, l'endpoint réalise les traitements suivants :

    1. vérifie que le fichier reçu est bien un fichier audio ;
    2. vérifie que le fichier n'est pas vide ;
    3. enregistre temporairement l'audio original ;
    4. crée un emplacement pour la version nettoyée ;
    5. appelle FFmpeg via le service clean_audio() ;
    6. supprime les fichiers temporaires après traitement.

    Le nettoyage permet notamment :
    - d'atténuer certains bruits de fond ;
    - de supprimer les silences prolongés ;
    - de convertir l'audio en mono ;
    - de convertir sa fréquence en 16 kHz.

    La transcription de la voix en texte sera ajoutée
    dans une prochaine étape.
    """

    # ======================================================
    # 1. VÉRIFICATION DU TYPE DE FICHIER
    # ======================================================

    # Le navigateur peut produire différents formats audio
    # selon la plateforme : WebM, MP3, etc.
    #
    # On accepte donc tout fichier dont le type MIME
    # commence par "audio/".
    if (
        not audio.content_type
        or not audio.content_type.startswith("audio/")
    ):
        raise HTTPException(
            status_code=400,
            detail="Le fichier envoyé doit être un fichier audio.",
        )


    # ======================================================
    # 2. LECTURE DE L'AUDIO
    # ======================================================

    # Récupère en mémoire les octets du fichier
    # envoyé par Angular ou Swagger.
    audio_content = await audio.read()


    # Informations temporaires utiles pendant nos tests.
    # Nous les supprimerons lorsque la fonctionnalité
    # de saisie vocale sera complètement validée.
    print("\n========== AUDIO REÇU ==========")
    print("Nom :", audio.filename)
    print("Type :", audio.content_type)
    print("Taille :", len(audio_content))
    print(
        "Premiers octets :",
        audio_content[:16].hex(),
    )
    print("================================\n")


    # Un fichier sans contenu ne doit pas être envoyé
    # à FFmpeg.
    if not audio_content:
        raise HTTPException(
            status_code=400,
            detail="Le fichier audio est vide.",
        )


    # ======================================================
    # 3. RÉCUPÉRATION DE L'EXTENSION
    # ======================================================

    # Exemple :
    #
    # perte_passport.mp3 -> .mp3
    # audio.webm         -> .webm
    #
    # Si aucun nom n'est fourni, WebM est utilisé
    # par défaut car MediaRecorder produit actuellement
    # ce format dans notre frontend.
    suffix = Path(
        audio.filename or "audio.webm"
    ).suffix or ".webm"


    # Chemin du fichier audio original temporaire.
    temporary_path: Path | None = None

    # Chemin du futur fichier WAV nettoyé.
    cleaned_path: Path | None = None


    try:

        # ==================================================
        # 4. ENREGISTREMENT TEMPORAIRE DE L'AUDIO ORIGINAL
        # ==================================================

        # NamedTemporaryFile crée un véritable fichier
        # temporaire sur le disque.
        #
        # delete=False est utilisé car FFmpeg devra
        # accéder au fichier après la fermeture du bloc.
        with tempfile.NamedTemporaryFile(
            suffix=suffix,
            delete=False,
        ) as temporary_file:

            # Écrit dans le fichier temporaire
            # exactement les données audio reçues.
            temporary_file.write(
                audio_content
            )

            # Conserve le chemin du fichier.
            temporary_path = Path(
                temporary_file.name
            )

        # IMPORTANT :
        #
        # Nous sommes maintenant sortis du "with".
        # temporary_file est donc fermé.
        #
        # Sous Windows, cette étape est importante :
        # FFmpeg peut maintenant ouvrir correctement
        # le fichier temporaire.


        # ==================================================
        # 5. PRÉPARATION DU FICHIER AUDIO NETTOYÉ
        # ==================================================

        # Crée un emplacement temporaire avec
        # l'extension .wav.
        #
        # FFmpeg écrira ensuite le résultat nettoyé
        # dans ce fichier.
        with tempfile.NamedTemporaryFile(
            suffix=".wav",
            delete=False,
        ) as cleaned_file:

            cleaned_path = Path(
                cleaned_file.name
            )

        # Ici aussi, le fichier est fermé avant
        # son utilisation par FFmpeg.


        # ==================================================
        # 6. NETTOYAGE AVEC FFMPEG
        # ==================================================

        try:

            clean_audio(
                input_path=temporary_path,
                output_path=cleaned_path,
            )

        except AudioCleaningError as exc:

            # L'utilisateur ne reçoit pas les détails
            # techniques internes de FFmpeg.
            #
            # Pendant le développement, les détails sont
            # affichés dans le terminal par notre service
            # audio_cleaning_service.py.
            raise HTTPException(
                status_code=500,
                detail=(
                    "Impossible de nettoyer "
                    "l'enregistrement audio."
                ),
            ) from exc


        # ==================================================
        # 7. RÉSULTAT DU TEST
        # ==================================================

        # Pour le moment, aucune transcription n'est encore
        # effectuée.
        #
        # On retourne simplement les tailles des fichiers
        # pour vérifier que FFmpeg a bien généré
        # une nouvelle version de l'audio.
        return {
            "message": (
                "Audio reçu et nettoyé correctement."
            ),
            "filename": audio.filename,
            "content_type": audio.content_type,
            "original_size_bytes": len(
                audio_content
            ),
            "cleaned_size_bytes": (
                cleaned_path.stat().st_size
            ),
        }


    finally:

        # ==================================================
        # 8. NETTOYAGE DES FICHIERS TEMPORAIRES
        # ==================================================

        # Supprime l'enregistrement original.
        if (
            temporary_path is not None
            and temporary_path.exists()
        ):
            temporary_path.unlink()


        # Supprime également la version WAV nettoyée.
        if (
            cleaned_path is not None
            and cleaned_path.exists()
        ):
            cleaned_path.unlink()


        # Ferme le fichier UploadFile géré par FastAPI.
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