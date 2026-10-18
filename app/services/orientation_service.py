import re

# Permet de réutiliser la même instance du service.
from functools import lru_cache

# Service IA chargé de comprendre la demande avant la recherche RAG.
from app.services.preparation_demande_service import (
    get_preparation_demande_service,
)

# Schémas de réponse de l'API.
from app.schemas.orientation import (
    OrientationResponse,
    PrecisionsRequisesResponse,
    QuestionComplementaireResponse,
    SourcesInsuffisantesResponse,
)

# Services RAG et LLM.
from app.services.llm_service import get_llm_service
from app.services.prompt_service import (
    build_system_prompt,
    build_user_prompt,
)
from app.services.response_parser_service import parse_llm_response
from app.services.retrieval_service import get_retrieval_service


# ==========================================================
# DOMAINES DU MVP
# ==========================================================

DOMAINES_CODES = {
    "PASSEPORT": {
        "DEMANDE_PASSEPORT_ORDINAIRE",
        "RENOUVELLEMENT_PASSEPORT",
        "PASSEPORT_PERDU_OU_VOLE",
    },
    "PENSION": {
        "REVERSION_PENSION_CAPITAL_DECES_ACTIVITE",
        "REVERSION_PENSION_APRES_RETRAITE",
    },
    "FONCIER": {
        "REGULARISATION_BAIL",
        "ACQUISITION_MUTATION_TITRE_FONCIER",
        "TRANSFORMATION_BAIL_EN_TITRE_FONCIER",
        "TRANSFORMATION_AUTORISATION_OCCUPATION_EN_TITRE_FONCIER",
    },
}


# ==========================================================
# INDICES POUR IDENTIFIER LE DOMAINE
# ==========================================================

INDICES_DOMAINES = {
    "PASSEPORT": [
        r"\bpasseports?\b",
        r"\btitre de voyage\b",
    ],

    "PENSION": [
        r"\bdécès\b",
        r"\bdeces\b",
        r"\bdécéd(?:é|ée|és|ées)\b",
        r"\bdéfunt(?:e|s|es)?\b",
        r"\bfonctionnaires?\b",
        r"\bpensions?\b",
        r"\bréversions?\b",
        r"\bretrait(?:e|é|ée|és|ées)\b",
    ],

    "FONCIER": [
        r"\bterrains?\b",
        r"\bparcelles?\b",
        r"\bbail\b",
        r"\bbaux\b",
        r"\bfonciers?\b",
        r"\bmaisons?\b",
        r"\bimmobili(?:er|ère|ers|ères)\b",
        r"\bcadastre\b",
        r"\bpropriét(?:é|aire|aires)\b",
    ],
}


# ==========================================================
# QUESTION DE DOMAINE
# ==========================================================

QUESTION_DOMAINE = (
    "Votre demande concerne principalement quel sujet ?"
)

OPTIONS_DOMAINES = [
    "Un terrain, une maison ou un bien immobilier",
    "Un passeport",
    "Le décès d'un fonctionnaire ou une pension",
    "Je ne sais pas",
]

REPONSES_DOMAINES = {
    OPTIONS_DOMAINES[0]: "FONCIER",
    OPTIONS_DOMAINES[1]: "PASSEPORT",
    OPTIONS_DOMAINES[2]: "PENSION",
}


# ==========================================================
# QUESTIONS FONCIÈRES CONNUES
# ==========================================================

QUESTION_PROPRIETAIRE_TERRAIN = (
    "Savez-vous à qui appartient le terrain que vous occupez ?"
)

QUESTION_DOCUMENT_VENDEUR = (
    "Quel document le vendeur vous a-t-il présenté "
    "pour prouver ses droits sur ce bien ?"
)

QUESTION_PROPRIETAIRE_BIEN = (
    "Le bien appartient-il actuellement à un particulier ?"
)

QUESTION_USAGE_TERRAIN = (
    "Le terrain concerné est-il destiné à l'habitation ?"
)

QUESTION_AMENAGEMENTS = (
    "Les constructions ou aménagements prévus "
    "dans votre bail ont-ils été réalisés ?"
)

# ==========================================================
# QUESTIONS PASSEPORT CONNUES
# ==========================================================

QUESTION_PASSEPORT_SENEGALAIS = (
    "S'agit-il d'un passeport sénégalais ?"
)

QUESTION_SITUATION_PASSEPORT = (
    "Quelle est votre situation concernant votre passeport sénégalais ?"
)


# ==========================================================
# QUESTIONS PENSION / DÉCÈS CONNUES
# ==========================================================

QUESTION_SITUATION_DECES = (
    "Au moment de son décès, quelle était la situation de la personne ?"
)

QUESTION_PENSION_RETRAITE = (
    "Au moment de son décès, la personne percevait-elle déjà "
    "une pension de retraite ?"
)

QUESTION_FONCTIONNAIRE_ACTIVITE = (
    "Au moment de son décès, la personne travaillait-elle encore "
    "comme fonctionnaire ?"
)


class OrientationService:
    """Orchestre l'analyse d'une situation administrative."""

    def __init__(self):
        # Services de recherche, de préparation et de génération.
        self.retrieval = get_retrieval_service()
        self.llm = get_llm_service()
        self.preparation = get_preparation_demande_service()

    # ======================================================
    # UTILITAIRE : RÉCUPÉRER UNE RÉPONSE
    # ======================================================

    def _get_reponse(
        self,
        reponses: list[dict] | None,
        texte_question: str,
    ) -> str | None:
        """
        Retourne la dernière réponse fournie
        à une question précise.
        """

        for reponse in reversed(reponses or []):
            if (
                reponse.get("texte_question")
                == texte_question
            ):
                return reponse.get("contenu")

        return None

    # ======================================================
    # IDENTIFICATION DU DOMAINE
    # ======================================================

    def _identifier_domaine(
        self,
        situation: str,
        reponses: list[dict] | None = None,
    ) -> str | None:
        """
        Identifie le domaine administratif
        lorsque la situation est suffisamment claire.
        """

        # Priorité à une réponse explicite
        # à la question de domaine.
        for reponse in reversed(reponses or []):
            if (
                reponse.get("texte_question")
                == QUESTION_DOMAINE
            ):
                return REPONSES_DOMAINES.get(
                    reponse.get("contenu")
                )

        texte = situation.casefold()

        domaines_trouves = []

        for domaine, motifs in INDICES_DOMAINES.items():
            if any(
                re.search(motif, texte)
                for motif in motifs
            ):
                domaines_trouves.append(domaine)

        if len(domaines_trouves) == 1:
            return domaines_trouves[0]

        return None

    # ======================================================
    # CODES AUTORISÉS DU DOMAINE
    # ======================================================

    def _select_relevant_codes(
        self,
        domaine: str,
        demarche_codes: list[str],
    ) -> list[str]:
        """
        Conserve uniquement les codes autorisés par Django
        appartenant au domaine identifié.
        """

        codes_domaine = DOMAINES_CODES.get(
            domaine,
            set(),
        )

        return [
            code
            for code in demarche_codes
            if code in codes_domaine
        ]


    def _traiter_reponses_passeport(
        self,
        situation: str,
        reponses: list[dict] | None,
    ):
        """
        Traite directement les réponses passeport
        lorsque la règle métier est déjà connue.
        """

        passeport_senegalais = self._get_reponse(
            reponses,
            QUESTION_PASSEPORT_SENEGALAIS,
        )

        # --------------------------------------------------
        # VÉRIFIER S'IL S'AGIT D'UN PASSEPORT SÉNÉGALAIS
        # --------------------------------------------------

        if passeport_senegalais == "Non":
            return SourcesInsuffisantesResponse(
                statut="SOURCES_INSUFFISANTES",
                message=(
                    "Les démarches de passeport actuellement "
                    "couvertes par AdmiGuide concernent "
                    "le passeport sénégalais."
                ),
            )

        if passeport_senegalais == "Je ne sais pas":
            return SourcesInsuffisantesResponse(
                statut="SOURCES_INSUFFISANTES",
                message=(
                    "Vous ne savez pas encore si le passeport "
                    "concerné est un passeport sénégalais. "
                    "Cette information est nécessaire pour "
                    "identifier la démarche adaptée. "
                    "AdmiGuide pourra vous accompagner pour "
                    "savoir comment vérifier cette information."
                ),
            )

        # --------------------------------------------------
        # PASSEPORT SÉNÉGALAIS CONFIRMÉ
        # --------------------------------------------------

        if passeport_senegalais == "Oui":

            situation_passeport = self._get_reponse(
                reponses,
                QUESTION_SITUATION_PASSEPORT,
            )
            # Laisse le modèle analyser la description
            # si aucune réponse explicite n'a été enregistrée.
            if situation_passeport is None:
                return None

            if (
                situation_passeport
                == "Je souhaite demander un passeport pour la première fois"
            ):
                return OrientationResponse(
                    statut="ORIENTATION",
                    demarche_code="DEMANDE_PASSEPORT_ORDINAIRE",
                    resume=(
                        f"{situation.strip()} "
                        "L'utilisateur confirme qu'il s'agit "
                        "d'un passeport sénégalais et souhaite "
                        "effectuer une première demande."
                    ),
                    avertissement="",
                )

            if (
                situation_passeport
                == "Je souhaite renouveler mon passeport"
            ):
                return OrientationResponse(
                    statut="ORIENTATION",
                    demarche_code="RENOUVELLEMENT_PASSEPORT",
                    resume=(
                        f"{situation.strip()} "
                        "L'utilisateur confirme qu'il s'agit "
                        "d'un passeport sénégalais et souhaite "
                        "le renouveler."
                    ),
                    avertissement="",
                )

            if (
                situation_passeport
                == "J'ai perdu ou on m'a volé mon passeport"
            ):
                return OrientationResponse(
                    statut="ORIENTATION",
                    demarche_code="PASSEPORT_PERDU_OU_VOLE",
                    resume=(
                        f"{situation.strip()} "
                        "L'utilisateur confirme qu'il s'agit "
                        "d'un passeport sénégalais qui a été "
                        "perdu ou volé."
                    ),
                    avertissement="",
                )

            if situation_passeport == "Autre situation":
                return SourcesInsuffisantesResponse(
                    statut="SOURCES_INSUFFISANTES",
                    message=(
                        "La situation décrite ne correspond pas "
                        "aux démarches de passeport actuellement "
                        "couvertes par AdmiGuide."
                    ),
                )

        return None


    def _traiter_reponses_pension(
        self,
        situation: str,
        reponses: list[dict] | None,
    ):
        """
        Traite directement les réponses pension / décès
        lorsque la règle métier est déjà connue.
        """

        situation_deces = self._get_reponse(
            reponses,
            QUESTION_SITUATION_DECES,
        )

        # --------------------------------------------------
        # SITUATION CONNUE AU MOMENT DU DÉCÈS
        # --------------------------------------------------

        if situation_deces == "Elle était fonctionnaire en activité":
            return OrientationResponse(
                statut="ORIENTATION",
                demarche_code=(
                    "REVERSION_PENSION_CAPITAL_DECES_ACTIVITE"
                ),
                resume=(
                    f"{situation.strip()} "
                    "La personne était fonctionnaire en activité "
                    "au moment de son décès."
                ),
                avertissement="",
            )

        if situation_deces == "Elle était fonctionnaire à la retraite":
            return OrientationResponse(
                statut="ORIENTATION",
                demarche_code=(
                    "REVERSION_PENSION_APRES_RETRAITE"
                ),
                resume=(
                    f"{situation.strip()} "
                    "La personne était fonctionnaire à la retraite "
                    "au moment de son décès."
                ),
                avertissement="",
            )

        if situation_deces == "Elle n'était pas fonctionnaire":
            return SourcesInsuffisantesResponse(
                statut="SOURCES_INSUFFISANTES",
                message=(
                    "Les démarches de pension après décès actuellement "
                    "couvertes par AdmiGuide concernent le décès "
                    "d'un fonctionnaire en activité ou à la retraite."
                ),
            )

        # --------------------------------------------------
        # PREMIER "JE NE SAIS PAS"
        # --------------------------------------------------

        if situation_deces == "Je ne sais pas":

            pension_retraite = self._get_reponse(
                reponses,
                QUESTION_PENSION_RETRAITE,
            )

            # Pose une question plus concrète.
            if pension_retraite is None:
                return PrecisionsRequisesResponse(
                    statut="PRECISIONS_REQUISES",
                    questions=[
                        QuestionComplementaireResponse(
                            texte=QUESTION_PENSION_RETRAITE,
                            type_question="CHOIX_UNIQUE",
                            options=[
                                "Oui",
                                "Non",
                                "Je ne sais pas",
                            ],
                        )
                    ],
                )

            if pension_retraite == "Oui":
                return OrientationResponse(
                    statut="ORIENTATION",
                    demarche_code=(
                        "REVERSION_PENSION_APRES_RETRAITE"
                    ),
                    resume=(
                        f"{situation.strip()} "
                        "La personne percevait déjà une pension "
                        "de retraite au moment de son décès."
                    ),
                    avertissement="",
                )

            # --------------------------------------------------
            # ELLE NE PERCEVAIT PAS ENCORE DE PENSION
            # --------------------------------------------------

            if pension_retraite == "Non":

                fonctionnaire_activite = self._get_reponse(
                    reponses,
                    QUESTION_FONCTIONNAIRE_ACTIVITE,
                )

                if fonctionnaire_activite is None:
                    return PrecisionsRequisesResponse(
                        statut="PRECISIONS_REQUISES",
                        questions=[
                            QuestionComplementaireResponse(
                                texte=QUESTION_FONCTIONNAIRE_ACTIVITE,
                                type_question="CHOIX_UNIQUE",
                                options=[
                                    "Oui",
                                    "Non",
                                    "Je ne sais pas",
                                ],
                            )
                        ],
                    )

                if fonctionnaire_activite == "Oui":
                    return OrientationResponse(
                        statut="ORIENTATION",
                        demarche_code=(
                            "REVERSION_PENSION_CAPITAL_DECES_ACTIVITE"
                        ),
                        resume=(
                            f"{situation.strip()} "
                            "La personne travaillait encore comme "
                            "fonctionnaire au moment de son décès."
                        ),
                        avertissement="",
                    )

                if fonctionnaire_activite == "Non":
                    return SourcesInsuffisantesResponse(
                        statut="SOURCES_INSUFFISANTES",
                        message=(
                            "La personne ne percevait pas encore "
                            "de pension de retraite et ne travaillait "
                            "plus comme fonctionnaire au moment de son "
                            "décès. Les démarches actuellement couvertes "
                            "par AdmiGuide ne permettent donc pas "
                            "d'identifier une procédure adaptée."
                        ),
                    )

                if fonctionnaire_activite == "Je ne sais pas":
                    return SourcesInsuffisantesResponse(
                        statut="SOURCES_INSUFFISANTES",
                        message=(
                            "Vous ne savez pas encore si la personne "
                            "travaillait comme fonctionnaire au moment "
                            "de son décès. Cette information est "
                            "nécessaire pour identifier la démarche "
                            "adaptée. AdmiGuide pourra vous accompagner "
                            "pour savoir comment vérifier cette "
                            "information."
                        ),
                    )

            if pension_retraite == "Je ne sais pas":
                return SourcesInsuffisantesResponse(
                    statut="SOURCES_INSUFFISANTES",
                    message=(
                        "Vous ne savez pas encore si la personne "
                        "percevait une pension de retraite au moment "
                        "de son décès. Cette information est nécessaire "
                        "pour identifier la démarche adaptée. "
                        "AdmiGuide pourra vous accompagner pour savoir "
                        "comment la vérifier."
                    ),
                )

        return None
    
    # ======================================================
    # RÈGLES DÉTERMINISTES : FONCIER
    # ======================================================

    def _traiter_reponses_foncieres(
        self,
        situation: str,
        reponses: list[dict] | None,
    ):
        """
        Traite directement les réponses foncières
        lorsque la règle métier est déjà connue.

        Cela évite un nouvel appel Groq inutile.
        """

        # --------------------------------------------------
        # 1. RÉGULARISATION PAR VOIE DE BAIL
        # --------------------------------------------------

        proprietaire_terrain = self._get_reponse(
            reponses,
            QUESTION_PROPRIETAIRE_TERRAIN,
        )

        if proprietaire_terrain == "À l'État":
            return OrientationResponse(
                statut="ORIENTATION",
                demarche_code="REGULARISATION_BAIL",
                resume=(
                    f"{situation.strip()} "
                    "L'utilisateur indique que le terrain "
                    "appartient à l'État."
                ),
                avertissement=(
                    "Cette orientation est indicative. "
                    "Le Bureau des Domaines compétent devra "
                    "confirmer que le terrain relève du domaine "
                    "privé de l'État et qu'il peut faire "
                    "l'objet d'un bail."
                ),
            )

        if proprietaire_terrain == "À un particulier":
            return SourcesInsuffisantesResponse(
                statut="SOURCES_INSUFFISANTES",
                message=(
                    "Le terrain appartient à un particulier. "
                    "La régularisation par voie de bail "
                    "actuellement couverte par AdmiGuide "
                    "concerne les terrains relevant du domaine "
                    "privé de l'État."
                ),
            )

        if proprietaire_terrain == "Je ne sais pas":
            return SourcesInsuffisantesResponse(
                statut="SOURCES_INSUFFISANTES",
                message=(
                    "Vous ne savez pas encore à qui appartient "
                    "le terrain que vous occupez. Cette information "
                    "est nécessaire pour identifier la démarche "
                    "adaptée. AdmiGuide pourra vous accompagner "
                    "pour savoir comment vérifier la situation "
                    "juridique du terrain."
                ),
            )

        # --------------------------------------------------
        # 2. ACQUISITION / MUTATION TITRE FONCIER
        # --------------------------------------------------

        document_vendeur = self._get_reponse(
            reponses,
            QUESTION_DOCUMENT_VENDEUR,
        )

        if document_vendeur == "Un titre foncier":

            proprietaire_bien = self._get_reponse(
                reponses,
                QUESTION_PROPRIETAIRE_BIEN,
            )

            # Le titre existe mais il manque encore
            # une information.
            if proprietaire_bien is None:
                return PrecisionsRequisesResponse(
                    statut="PRECISIONS_REQUISES",
                    questions=[
                        QuestionComplementaireResponse(
                            texte=QUESTION_PROPRIETAIRE_BIEN,
                            type_question="CHOIX_UNIQUE",
                            options=[
                                "Oui",
                                "Non",
                                "Je ne sais pas",
                            ],
                        )
                    ],
                )

            if proprietaire_bien == "Oui":
                return OrientationResponse(
                    statut="ORIENTATION",
                    demarche_code=(
                        "ACQUISITION_MUTATION_TITRE_FONCIER"
                    ),
                    resume=(
                        f"{situation.strip()} "
                        "Le vendeur a présenté un titre foncier "
                        "et le bien appartient actuellement "
                        "à un particulier."
                    ),
                    avertissement="",
                )

            if proprietaire_bien == "Non":
                return SourcesInsuffisantesResponse(
                    statut="SOURCES_INSUFFISANTES",
                    message=(
                        "Le bien ne correspond pas au parcours "
                        "d'acquisition d'un titre foncier "
                        "appartenant à un particulier actuellement "
                        "couvert par AdmiGuide."
                    ),
                )

            if proprietaire_bien == "Je ne sais pas":
                return SourcesInsuffisantesResponse(
                    statut="SOURCES_INSUFFISANTES",
                    message=(
                        "Il faut d'abord vérifier qui est le "
                        "propriétaire actuellement inscrit pour "
                        "ce bien avant de poursuivre l'orientation."
                    ),
                )

        if document_vendeur == "Un bail":
            return SourcesInsuffisantesResponse(
                statut="SOURCES_INSUFFISANTES",
                message=(
                    "Le vendeur vous a présenté un bail. "
                    "La cession d'un bien ou d'un droit détenu "
                    "sous bail correspond à une procédure "
                    "différente qui n'est pas encore couverte "
                    "par les démarches disponibles dans AdmiGuide."
                ),
            )

        if (
            document_vendeur
            == "Un autre document d'occupation ou d'attribution"
        ):
            return SourcesInsuffisantesResponse(
                statut="SOURCES_INSUFFISANTES",
                message=(
                    "Le vendeur vous a présenté un autre document "
                    "d'occupation ou d'attribution. La procédure "
                    "à suivre dépend de la nature exacte de ce "
                    "document et n'est pas encore couverte par "
                    "les démarches disponibles dans AdmiGuide."
                ),
            )

        if document_vendeur in {
            "Aucun document ne m'a été présenté",
            "Je ne sais pas",
        }:
            return SourcesInsuffisantesResponse(
                statut="SOURCES_INSUFFISANTES",
                message=(
                    "Avant de vous orienter vers une procédure "
                    "d'achat, il faut identifier le droit existant "
                    "sur le bien. Demandez au vendeur le document "
                    "foncier correspondant : titre foncier, bail "
                    "ou autre titre d'occupation. Si le bien possède "
                    "un titre foncier, AdmiGuide pourra ensuite "
                    "vous orienter vers la procédure d'acquisition "
                    "et de mutation."
                ),
            )

        # --------------------------------------------------
        # 3. TRANSFORMATION BAIL → TITRE FONCIER
        # --------------------------------------------------

        usage_terrain = self._get_reponse(
            reponses,
            QUESTION_USAGE_TERRAIN,
        )

        if usage_terrain == "Oui":

            amenagements = self._get_reponse(
                reponses,
                QUESTION_AMENAGEMENTS,
            )

            # Première condition validée :
            # on pose directement la deuxième question
            # sans rappeler Groq.
            if amenagements is None:
                return PrecisionsRequisesResponse(
                    statut="PRECISIONS_REQUISES",
                    questions=[
                        QuestionComplementaireResponse(
                            texte=QUESTION_AMENAGEMENTS,
                            type_question="CHOIX_UNIQUE",
                            options=[
                                "Oui",
                                "Non",
                                "Je ne sais pas",
                            ],
                        )
                    ],
                )

            if amenagements == "Oui":
                return OrientationResponse(
                    statut="ORIENTATION",
                    demarche_code=(
                        "TRANSFORMATION_BAIL_EN_TITRE_FONCIER"
                    ),
                    resume=(
                        f"{situation.strip()} "
                        "Le terrain est destiné à l'habitation "
                        "et les constructions ou aménagements "
                        "prévus dans le bail ont été réalisés."
                    ),
                    avertissement="",
                )

            if amenagements == "Non":
                return SourcesInsuffisantesResponse(
                    statut="SOURCES_INSUFFISANTES",
                    message=(
                        "Les constructions ou aménagements "
                        "prévus dans le bail ne sont pas encore "
                        "réalisés. AdmiGuide ne peut donc pas "
                        "confirmer cette orientation."
                    ),
                )

            if amenagements == "Je ne sais pas":
                return SourcesInsuffisantesResponse(
                    statut="SOURCES_INSUFFISANTES",
                    message=(
                        "Il faut vérifier si les constructions "
                        "ou aménagements prévus dans votre bail "
                        "ont été réalisés avant de confirmer "
                        "cette orientation."
                    ),
                )

        if usage_terrain == "Non":
            return SourcesInsuffisantesResponse(
                statut="SOURCES_INSUFFISANTES",
                message=(
                    "Le terrain n'est pas destiné à l'habitation. "
                    "La procédure de transformation actuellement "
                    "couverte par AdmiGuide ne correspond donc "
                    "pas à cette situation."
                ),
            )

        if usage_terrain == "Je ne sais pas":
            return SourcesInsuffisantesResponse(
                statut="SOURCES_INSUFFISANTES",
                message=(
                    "L'usage prévu du terrain doit être vérifié "
                    "avant de confirmer cette orientation."
                ),
            )

        # Aucune réponse métier déterministe
        # n'est encore disponible.
        return None

    # ======================================================
    # ANALYSE PRINCIPALE
    # ======================================================

    async def analyze(
        self,
        situation: str,
        demarche_codes: list[str],
        reponses: list[dict] | None = None,
    ):
        """Analyse la demande avec l'IA et valide l'orientation obtenue."""

        # --------------------------------------------------
        # 1. IDENTIFIER LE DOMAINE ET PRÉPARER LA RECHERCHE
        # --------------------------------------------------

        # Groq comprend la situation et propose une requête RAG.
        preparation = await self.preparation.preparer(
            situation=situation,
            reponses=reponses,
        )

        domaine = preparation["domaine"]
        requete_rag = preparation["requete_rag"]

        # Une réponse explicite de l'utilisateur à la question
        # de domaine reste prioritaire sur la classification IA.
        reponse_domaine = self._get_reponse(
            reponses,
            QUESTION_DOMAINE,
        )
        domaine_choisi = REPONSES_DOMAINES.get(reponse_domaine)

        if domaine_choisi is not None:
            if domaine_choisi != domaine:
                # Utilise uniquement la description et le choix
                # réellement fournis par l'utilisateur.
                requete_rag = (
                    f"{situation}\n"
                    f"Sujet indiqué par l'utilisateur : {reponse_domaine}"
                )
            domaine = domaine_choisi

        # L'utilisateur demande une démarche hors du MVP.
        if domaine == "HORS_COUVERTURE":
            return SourcesInsuffisantesResponse(
                statut="SOURCES_INSUFFISANTES",
                message=(
                    "AdmiGuide ne couvre pas encore "
                    "ce type de demande administrative."
                ),
            )

        # Une demande trop vague nécessite une seule
        # question de précision sur le sujet.
        if domaine == "INDETERMINE":
            question_deja_posee = any(
                reponse.get("texte_question") == QUESTION_DOMAINE
                for reponse in (reponses or [])
            )

            if question_deja_posee:
                return SourcesInsuffisantesResponse(
                    statut="SOURCES_INSUFFISANTES",
                    message=(
                        "Nous ne disposons pas encore "
                        "d'informations suffisantes pour "
                        "identifier votre demande."
                    ),
                )

            return PrecisionsRequisesResponse(
                statut="PRECISIONS_REQUISES",
                questions=[
                    QuestionComplementaireResponse(
                        texte=QUESTION_DOMAINE,
                        type_question="CHOIX_UNIQUE",
                        options=OPTIONS_DOMAINES,
                    )
                ],
            )

        # --------------------------------------------------
        # 2. LIMITER L'ANALYSE AUX DÉMARCHES AUTORISÉES
        # --------------------------------------------------

        codes_pertinents = self._select_relevant_codes(
            domaine=domaine,
            demarche_codes=demarche_codes,
        )

        if not codes_pertinents:
            return SourcesInsuffisantesResponse(
                statut="SOURCES_INSUFFISANTES",
                message=(
                    "Aucune démarche disponible dans AdmiGuide "
                    "ne correspond actuellement à ce domaine."
                ),
            )

        # --------------------------------------------------
        # 3. RECHERCHER LES SOURCES OFFICIELLES DANS CHROMADB
        # --------------------------------------------------

        # Utilise la requête reformulée par Groq et le domaine
        # identifié pour retrouver les sources pertinentes.
        contenus = self.retrieval.retrieve(
            texte=requete_rag,
            domaine=domaine,
        )

        if not contenus:
            return SourcesInsuffisantesResponse(
                statut="SOURCES_INSUFFISANTES",
                message=(
                    "Nous ne disposons pas encore de sources "
                    "suffisantes pour analyser cette demande."
                ),
            )

        contexte = self.retrieval.build_context_from_results(
            contenus
        )

        # --------------------------------------------------
        # 4. PRÉPARER LA DEMANDE POUR LE MODÈLE
        # --------------------------------------------------

        # Conserve les règles métier adaptées au domaine.
        system_prompt = build_system_prompt(
            demarche_codes=codes_pertinents,
        )

        # Transmet la description initiale, les réponses précédentes
        # et les documents officiels retrouvés par le RAG.
        user_prompt = build_user_prompt(
            situation=situation,
            contexte=contexte,
            demarche_codes=codes_pertinents,
            reponses=reponses,
        )

        # --------------------------------------------------
        # 5. LAISSER L'IA IDENTIFIER LA DÉMARCHE
        # --------------------------------------------------

        reponse_brute = await self.llm.generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )

        # --------------------------------------------------
        # 6. VALIDER LE RÉSULTAT AVANT DE LE RENVOYER
        # --------------------------------------------------

        # Le parseur refuse notamment les codes de démarches
        # qui ne sont pas autorisés par le backend.
        resultat = parse_llm_response(
            reponse_brute,
            demarche_codes=codes_pertinents,
        )

        # Conserve l'avertissement obligatoire pour la
        # régularisation d'un terrain par voie de bail.
        if (
            resultat.statut == "ORIENTATION"
            and resultat.demarche_code == "REGULARISATION_BAIL"
            and not resultat.avertissement.strip()
        ):
            resultat.avertissement = (
                "Cette orientation est indicative. "
                "Le Bureau des Domaines compétent devra confirmer "
                "que le terrain relève du domaine privé de l'État "
                "et qu'il peut faire l'objet d'un bail."
            )

        return resultat


@lru_cache
def get_orientation_service() -> OrientationService:
    """Retourne une instance réutilisable du service."""

    return OrientationService()