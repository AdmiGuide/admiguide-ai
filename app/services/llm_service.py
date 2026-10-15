import asyncio
import re

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

    def _get_retry_delay(
        self,
        response: httpx.Response,
    ) -> float:
        """
        Récupère le délai recommandé par Groq
        lorsqu'une limite 429 est atteinte.
        """

        # Essaie d'abord l'en-tête HTTP Retry-After.
        retry_after = response.headers.get("retry-after")

        if retry_after:
            try:
                return float(retry_after)
            except ValueError:
                pass

        # Sinon, cherche le délai dans le message Groq.
        match = re.search(
            r"try again in\s+(\d+(?:\.\d+)?)s",
            response.text,
            flags=re.IGNORECASE,
        )

        if match:
            return float(match.group(1))

        # Valeur de secours.
        return 5.0

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        """
        Envoie une demande à Groq.

        En cas d'erreur 429, attend le délai conseillé
        puis effectue une seule nouvelle tentative.
        """

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

        url = (
            f"{settings.groq_base_url.rstrip('/')}"
            "/chat/completions"
        )

        # Un appel initial + une seule nouvelle tentative.
        max_attempts = 2

        try:
            async with httpx.AsyncClient(
                timeout=20.0,
            ) as client:

                for attempt in range(max_attempts):

                    response = await client.post(
                        url,
                        headers=headers,
                        json=payload,
                    )

                    # ==========================================
                    # GESTION DU RATE LIMIT 429
                    # ==========================================
                    if response.status_code == 429:

                        print(
                            "Limite Groq 429 atteinte.",
                            flush=True,
                        )

                        # Si nous avons déjà réessayé une fois,
                        # on arrête.
                        if attempt == max_attempts - 1:
                            break

                        retry_delay = self._get_retry_delay(
                            response
                        )

                        # On évite une attente trop longue
                        # afin de rester sous le timeout Django.
                        if retry_delay > 15:
                            print(
                                (
                                    "Délai Groq trop long "
                                    f"({retry_delay:.1f}s). "
                                    "Pas de nouvelle tentative."
                                ),
                                flush=True,
                            )
                            break

                        # Petite marge après le délai Groq.
                        retry_delay += 0.5

                        print(
                            (
                                "Nouvelle tentative Groq dans "
                                f"{retry_delay:.1f}s..."
                            ),
                            flush=True,
                        )

                        await asyncio.sleep(
                            retry_delay
                        )

                        continue

                    # Une réponse différente de 429
                    # sort immédiatement de la boucle.
                    break

        except httpx.RequestError as exc:
            # Erreur réseau ou timeout.
            print(
                "Erreur de connexion à Groq :",
                type(exc).__name__,
                str(exc),
                flush=True,
            )

            raise RuntimeError(
                "Impossible de contacter temporairement Groq."
            ) from exc

        # ==============================================
        # AUTRES ERREURS HTTP
        # ==============================================

        if response.status_code >= 400:
            print(
                "Erreur Groq :",
                response.status_code,
                response.text[:1000],
                flush=True,
            )

            raise RuntimeError(
                f"Erreur Groq : HTTP {response.status_code}"
            )

        # ==============================================
        # LECTURE DU JSON
        # ==============================================

        try:
            data = response.json()

        except ValueError as exc:
            raise RuntimeError(
                "Groq a retourné une réponse JSON invalide."
            ) from exc

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

        if (
            not isinstance(contenu, str)
            or not contenu.strip()
        ):
            raise RuntimeError(
                "Groq a retourné une réponse vide."
            )

        return contenu.strip()


@lru_cache
def get_llm_service() -> LLMService:
    """Retourne une instance réutilisable du service LLM."""
    return LLMService()