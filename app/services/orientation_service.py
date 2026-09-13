# Permet de réutiliser la même instance du service.
from functools import lru_cache

# Services déjà validés pour le RAG et le LLM.
from app.services.llm_service import get_llm_service
from app.services.prompt_service import (
    build_system_prompt,
    build_user_prompt,
)
from app.services.response_parser_service import parse_llm_response
from app.services.retrieval_service import get_retrieval_service


class OrientationService:
    """Orchestre l'analyse d'une situation administrative."""

    def __init__(self):
        # Réutilise les services déjà initialisés.
        self.retrieval = get_retrieval_service()
        self.llm = get_llm_service()

    async def analyze(
        self,
        situation: str,
        pays_application: str | None,
        demarche_codes: list[str],
        reponses: list[dict] | None = None,
    ):
        """Analyse une situation et retourne un résultat métier validé."""

        # Recherche les passages officiels pertinents.
        contexte = self.retrieval.build_context(
            texte=situation,
            pays_application=pays_application,
        )

        # Prépare les instructions du modèle.
        system_prompt = build_system_prompt()

        user_prompt = build_user_prompt(
            situation=situation,
            contexte=contexte,
            demarche_codes=demarche_codes,
            reponses=reponses,
        )

        # Demande au modèle d'analyser la situation.
        reponse_brute = await self.llm.generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )

        # Vérifie la structure et le code de démarche retournés.
        return parse_llm_response(
            reponse_brute,
            demarche_codes=demarche_codes,
        )


@lru_cache
def get_orientation_service() -> OrientationService:
    """Retourne une instance réutilisable du service."""

    return OrientationService()