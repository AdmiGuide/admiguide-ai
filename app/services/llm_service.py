# Permet de réutiliser la même instance du service.
from functools import lru_cache

# Client HTTP asynchrone utilisé pour contacter Groq.
import httpx

# Configuration centralisée de l'application.
from app.core.config import settings


class LLMService:
    """Service chargé de communiquer avec le modèle génératif."""

    def __init__(self):
        # Vérifie que la clé Groq est présente.
        if not settings.groq_api_key:
            raise ValueError(
                "GROQ_API_KEY est manquante dans le fichier .env."
            )

        # Vérifie que le modèle est configuré.
        if not settings.llm_model_name:
            raise ValueError(
                "LLM_MODEL_NAME est manquant dans le fichier .env."
            )

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        """Envoie une demande à Groq et retourne la réponse du modèle."""

        payload = {
            "model": settings.llm_model_name,
            "temperature": 0,
            "messages": [
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": user_prompt,
                },
            ],
        }

        headers = {
            "Authorization": (
                f"Bearer {settings.groq_api_key}"
            ),
            "Content-Type": "application/json",
        }

        # Envoie la requête à Groq.
        async with httpx.AsyncClient(
            timeout=60.0,
        ) as client:
            response = await client.post(
                f"{settings.groq_base_url}/chat/completions",
                headers=headers,
                json=payload,
            )

        # Signale clairement une erreur de l'API.
        if response.status_code >= 400:
            print(
                "Erreur Groq :",
                response.status_code,
                response.text[:1000],
            )

            raise RuntimeError(
                f"Erreur Groq : HTTP {response.status_code}"
            )

        data = response.json()

        # Vérifie que la réponse contient bien du texte.
        try:
            contenu = data[
                "choices"
            ][0]["message"]["content"]

        except (
            KeyError,
            IndexError,
            TypeError,
        ) as exc:
            raise RuntimeError(
                "Groq a retourné une réponse sans contenu généré."
            ) from exc

        return contenu.strip()


@lru_cache
def get_llm_service() -> LLMService:
    """Retourne une instance réutilisable du service LLM."""
    return LLMService()