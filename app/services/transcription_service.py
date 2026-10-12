from pathlib import Path

import httpx

from app.core.config import settings


class TranscriptionError(Exception):
    """
    Erreur produite lorsqu'un problème survient
    pendant la transcription d'un fichier audio.
    """


async def transcribe_audio(
    audio_path: Path,
) -> str:
    """
    Envoie un fichier audio nettoyé à Groq
    et retourne sa transcription en français.

    Le fichier reçu ici est normalement le WAV
    produit auparavant par audio_cleaning_service.py.

    Étapes :
    1. vérifier que le fichier existe ;
    2. lire son contenu ;
    3. l'envoyer à l'API Speech-to-Text de Groq ;
    4. utiliser Whisper Large V3 Turbo ;
    5. récupérer uniquement le texte transcrit.
    """

    # Vérifie que la clé API Groq est disponible.
    if not settings.groq_api_key:
        raise TranscriptionError(
            "GROQ_API_KEY est manquante."
        )

    # Vérifie que le fichier existe.
    if not audio_path.exists():
        raise TranscriptionError(
            "Le fichier audio à transcrire est introuvable."
        )

    # Lit le fichier WAV nettoyé.
    audio_content = audio_path.read_bytes()

    if not audio_content:
        raise TranscriptionError(
            "Le fichier audio à transcrire est vide."
        )

    # Données envoyées à l'API Groq.
    data = {
        "model": "whisper-large-v3-turbo",
        "language": "fr",
        "response_format": "json",
        "temperature": "0",
    }

    # Fichier envoyé en multipart/form-data.
    files = {
        "file": (
            audio_path.name,
            audio_content,
            "audio/wav",
        )
    }

    headers = {
        "Authorization": (
            f"Bearer {settings.groq_api_key}"
        ),
    }

    try:
        async with httpx.AsyncClient(
            timeout=60.0,
        ) as client:

            response = await client.post(
                (
                    f"{settings.groq_base_url}"
                    "/audio/transcriptions"
                ),
                headers=headers,
                data=data,
                files=files,
            )

    except httpx.RequestError as exc:
        raise TranscriptionError(
            "Impossible de contacter le service de transcription."
        ) from exc

    # Vérifie que Groq n'a pas retourné d'erreur.
    if response.status_code >= 400:

        print(
            "Erreur transcription Groq :",
            response.status_code,
            response.text[:1000],
        )

        raise TranscriptionError(
            "Groq a refusé la transcription audio."
        )

    result = response.json()

    # La réponse attendue ressemble à :
    #
    # {
    #     "text": "J'ai perdu mon passeport..."
    # }
    transcription = result.get("text")

    if (
        not isinstance(transcription, str)
        or not transcription.strip()
    ):
        raise TranscriptionError(
            "Groq n'a retourné aucune transcription."
        )

    return transcription.strip()