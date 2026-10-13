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

    def _select_relevant_codes(
    self,
    contenus: list[dict],
    demarche_codes: list[str],
) -> list[str]:
        """
        Sélectionne les démarches susceptibles de correspondre
        aux sources retrouvées par le RAG.

        Si aucun domaine connu n'est identifié, tous les codes
        autorisés sont conservés par sécurité.
        """

        source_ids = {
            contenu["source_id"]
            for contenu in contenus
        }

        codes_pertinents = set()

        # Passeport.

        # Dès qu'une source passeport est retrouvée,
        # on conserve les trois démarches possibles.
        # Le LLM déterminera ensuite l'intention exacte
        # de l'utilisateur ou demandera une précision.
        if any(
            source_id.startswith("PASSEPORT_")
            for source_id in source_ids
        ):
            codes_pertinents.update({
                "DEMANDE_PASSEPORT_ORDINAIRE",
                "RENOUVELLEMENT_PASSEPORT",
                "PASSEPORT_PERDU_OU_VOLE",
            })

        # Pension / décès.
        if any(
            source_id.startswith("DECES_")
            for source_id in source_ids
        ):
            codes_pertinents.update({
                "REVERSION_PENSION_CAPITAL_DECES_ACTIVITE",
                "REVERSION_PENSION_APRES_RETRAITE",
            })

        # Foncier.
        if any(
            source_id.startswith((
                "REGULARISATION_",
                "ACQUISITION_",
                "ETAT_DROITS_REELS_",
            ))
            for source_id in source_ids
        ):
            codes_pertinents.update({
                "REGULARISATION_BAIL",
                "ACQUISITION_MUTATION_TITRE_FONCIER",
            })

        # Si aucun domaine n'a été reconnu,
        # on conserve tous les codes autorisés.
        if not codes_pertinents:
            return demarche_codes

        # Conserve uniquement les codes réellement autorisés
        # par Django et respecte leur ordre d'origine.
        return [
            code
            for code in demarche_codes
            if code in codes_pertinents
        ]

    async def analyze(
        self,
        situation: str,
        demarche_codes: list[str],
        reponses: list[dict] | None = None,
    ):
        """Analyse une situation et retourne un résultat métier validé."""

        # Recherche une seule fois les passages officiels pertinents.
        contenus = self.retrieval.retrieve(
            texte=situation,
        )

        # Construit le contexte à partir des résultats déjà récupérés.
        contexte = (
            self.retrieval.build_context_from_results(
                contenus
            )
        )

        # Garde uniquement les démarches correspondant
        # aux domaines retrouvés dans les sources.
        codes_pertinents = self._select_relevant_codes(
            contenus=contenus,
            demarche_codes=demarche_codes,
        )

        # Prépare les instructions du modèle.
        system_prompt = build_system_prompt(
            demarche_codes=codes_pertinents,
        )

        user_prompt = build_user_prompt(
            situation=situation,
            contexte=contexte,
            demarche_codes=codes_pertinents,
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
            demarche_codes=codes_pertinents,
        )


@lru_cache
def get_orientation_service() -> OrientationService:
    """Retourne une instance réutilisable du service."""

    return OrientationService()