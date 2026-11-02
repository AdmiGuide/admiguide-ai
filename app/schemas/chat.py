
from typing import Literal

# Pydantic permet de définir et de valider
# les données échangées avec l'API FastAPI.
from pydantic import BaseModel, Field


# ==========================================================
# MESSAGE DE CONVERSATION
# ==========================================================

class ChatMessage(BaseModel):
    """
    Représente un message échangé entre
    l'utilisateur et le chatbot.
    """

    # Identifie l'auteur du message.
    # Seuls l'utilisateur et l'assistant sont autorisés.
    role: Literal["user", "assistant"]

    # Contenu textuel du message.
    # Sa longueur est limitée à 1500 caractères.
    content: str = Field(
        min_length=1,
        max_length=1500,
    )


# ==========================================================
# SERVICE ADMINISTRATIF COMPÉTENT
# ==========================================================

class ChatServiceCompetent(BaseModel):
    """
    Contient les informations d'un service administratif
    associé à la démarche de l'utilisateur.
    """

    # Nom du service chargé de la démarche.
    nom: str

    # Administration à laquelle appartient le service.
    administration: str = ""

    # Adresse du service, lorsqu'elle est disponible.
    adresse: str = ""

    # Coordonnées de contact du service.
    contact: str = ""


# ==========================================================
# REQUÊTE ENVOYÉE AU CHATBOT
# ==========================================================

class ChatRequest(BaseModel):
    """
    Définit les informations transmises au chatbot
    pour produire une réponse adaptée au contexte.
    """

    # Question posée par l'utilisateur.
    question: str = Field(
        min_length=2,
        max_length=600,
    )

    # Page depuis laquelle le chatbot est appelé.
    # Le comportement dépend de cette page.
    page: Literal[
        "PRECISIONS",
        "RESULTAT",
        "SUIVI",
    ]

    # Description initiale de la situation administrative.
    situation: str = Field(
        min_length=1,
        max_length=1500,
    )

    # Domaine administratif concerné.
    # Peut être inconnu pendant les précisions.
    domaine: Literal[
        "PASSEPORT",
        "PENSION",
        "FONCIER",
    ] | None = None

    # Nom de la démarche recommandée.
    # Disponible après une orientation réussie.
    demarche: str | None = None

    # Étapes déjà présentées dans l'orientation.
    # Permet au chatbot d'expliquer une étape existante.
    etapes: list[str] = Field(
        default_factory=list,
        max_length=30,
    )

    # Pièces déjà indiquées dans l'orientation.
    # Permet d'expliquer leur signification ou leur utilité.
    pieces_a_preparer: list[str] = Field(
        default_factory=list,
        max_length=50,
    )

    # Question complémentaire actuellement affichée.
    # Permet d'expliquer son vocabulaire dans le contexte.
    question_precision: str | None = None

    # Terme juridique complexe sélectionné par l'usager.
    terme_juridique: str | None = None

    # Services administratifs liés à la démarche.
    # Utilisés notamment pour répondre aux questions
    # concernant leur localisation.
    services_competents: list[
        ChatServiceCompetent
    ] = Field(
        default_factory=list,
        max_length=10,
    )

    # Derniers messages de la conversation.
    # Permet de comprendre les questions de suivi.
    # Limité à six messages pour maîtriser le contexte.
    historique: list[ChatMessage] = Field(
        default_factory=list,
        max_length=6,
    )


# ==========================================================
# SOURCE ADMINISTRATIVE
# ==========================================================

class ChatSource(BaseModel):
    """
    Représente une source officielle utilisée
    pour justifier une réponse du chatbot.
    """

    # Titre de la source administrative.
    titre: str

    # Adresse permettant de consulter la source.
    url: str


# ==========================================================
# RÉPONSE DU CHATBOT
# ==========================================================

class ChatResponse(BaseModel):
    """
    Définit la réponse renvoyée par le chatbot
    à l'application AdmiGuide.
    """

    # Explication générée pour l'utilisateur.
    reponse: str

    # Sources officielles appuyant l'explication.
    # La liste peut être vide si aucune source
    # pertinente et vérifiable n'est disponible.
    sources: list[ChatSource] = Field(
        default_factory=list,
    )
