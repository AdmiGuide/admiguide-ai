import asyncio

import re

# Permet de réutiliser la même instance du service.
from functools import lru_cache

# Client HTTP asynchrone utilisé pour contacter Groq.
import httpx

# Configuration centralisée de l'application.
from app.core.config import settings
from app.services.web_source_service import url_officielle


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

    @staticmethod
    def _collecter_sources_web(message: dict, sources_web: list[dict]) -> None:
        """Conserve les extraits réellement renvoyés par browser_search.

        IMPORTANT : l'URL n'a pas besoin de figurer dans le texte généré par
        Groq. Sinon une page officielle pertinente peut être ignorée alors
        que le moteur l'a bien trouvée. Une page sans extrait ne constitue
        jamais à elle seule une preuve d'adresse.
        """
        deja_vus = {s.get("url"): s for s in sources_web if s.get("url")}
        for outil in message.get("executed_tools", []) or []:
            if not isinstance(outil, dict):
                continue
            pages = list(outil.get("browser_results") or [])
            recherche = outil.get("search_results") or {}
            if isinstance(recherche, dict):
                pages.extend(recherche.get("results") or [])
            for page in pages:
                if not isinstance(page, dict):
                    continue
                url = page.get("url")
                if not url_officielle(url):
                    continue
                # L'extrait provient du moteur de recherche, pas de l'IA.
                # Ne jamais dériver une preuve du seul message rédigé.
                extrait = next(
                    (valeur for cle in ("content", "snippet", "description", "summary")
                     if isinstance((valeur := page.get(cle)), str) and valeur.strip()),
                    "",
                )
                if url in deja_vus:
                    # browser_results et search_results peuvent contenir
                    # la même URL : garder l'extrait le plus exploitable.
                    existante = deja_vus[url]
                    if len(extrait) > len(existante.get("extrait") or ""):
                        existante["extrait"] = extrait[:10000]
                    continue
                source = {
                    "titre": str(page.get("title") or "Source institutionnelle")[:180],
                    "url": url,
                    "extrait": extrait[:10000],
                }
                sources_web.append(source)
                deja_vus[url] = source
                if len(deja_vus) >= 12:
                    return

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        model_name: str | None = None,
        utiliser_recherche_web: bool = False,
        sources_web: list[dict] | None = None,
    ) -> str:
        """
        Envoie une demande à Groq.
        En cas d'erreur 429, attend le délai conseillé
        puis effectue une seule nouvelle tentative.
        """

        # Sélectionne le modèle demandé par le service.

        # Par défaut, utilise GPT-OSS 120B pour l'orientation.
        modele_selectionne = (
            model_name or settings.llm_model_name
        )

        # Prépare les données à envoyer à Groq.
        payload = {
            "model": modele_selectionne,
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

        # Active la recherche Internet uniquement

        # lorsque le service appelant en a besoin.
        if utiliser_recherche_web:
            payload["tools"] = [
                {"type": "browser_search"}
            ]
            payload["tool_choice"] = "required"
            payload["reasoning_effort"] = "low"

            # Limite la longueur des réponses de recherche

            # afin de limiter la consommation de tokens.
            payload["max_completion_tokens"] = 1200
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

            # La recherche Internet peut prendre plus de temps

            # qu'une simple génération de texte.
            delai = 90.0 if utiliser_recherche_web else 20.0
            async with httpx.AsyncClient(
                timeout=delai,
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

        # Conserve les extraits des pages officielles renvoyés par browser_search.
        # Le moteur peut trouver une page sans que le modèle cite son URL.
        # Un lien sans extrait ne constitue pas une preuve d'adresse.
        if utiliser_recherche_web and sources_web is not None:
            self._collecter_sources_web(data["choices"][0]["message"], sources_web)

        return contenu.strip()


@lru_cache


def get_llm_service() -> LLMService:
    """Retourne une instance réutilisable du service LLM."""
    return LLMService()
