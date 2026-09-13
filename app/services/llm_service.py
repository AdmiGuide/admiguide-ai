# Permet de réutiliser la même instance du service.
from functools import lru_cache

# Client HTTP asynchrone utilisé pour contacter OpenRouter.
import httpx

# Configuration centralisée de l'application.
from app.core.config import settings


class LLMService:
    """Service chargé de communiquer avec le modèle génératif."""

    def __init__(self):
        # Vérifie que la configuration indispensable est présente.
        if not settings.openrouter_api_key:
            raise ValueError(
                "OPENROUTER_API_KEY est manquante dans le fichier .env."
            )

        if not settings.llm_model_name:
            raise ValueError(
                "LLM_MODEL_NAME est manquant dans le fichier .env."
            )

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        """Envoie une demande au modèle et retourne sa réponse."""

        # Données envoyées à OpenRouter.
        payload = {
            "model": settings.llm_model_name,
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

        # Authentifie la requête auprès d'OpenRouter.
        headers = {
            "Authorization": (
                f"Bearer {settings.openrouter_api_key}"
            ),
            "Content-Type": "application/json",
        }

        # Envoie la requête avec un délai maximal de 30 secondes.
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{settings.openrouter_base_url}/chat/completions",
                headers=headers,
                json=payload,
            )

        # Ne masque pas une erreur provenant du fournisseur.
        if response.status_code >= 400:
            raise RuntimeError(
                f"Erreur OpenRouter : HTTP {response.status_code}"
            )

        data = response.json()

        # Vérifie que la réponse possède la structure attendue.
        try:
            contenu = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            raise RuntimeError(
                "La réponse reçue depuis OpenRouter est invalide."
            )

        return contenu.strip()


@lru_cache
def get_llm_service() -> LLMService:
    """Retourne une instance réutilisable du service LLM."""
    return LLMService()