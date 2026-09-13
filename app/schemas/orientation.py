# Outils Pydantic pour définir et valider les données reçues par l'API.
from pydantic import BaseModel, Field, field_validator

# Literal permet de limiter un champ à des valeurs précises.
from typing import Literal


# Représente une réponse donnée à une question complémentaire.
class ReponseComplementaireInput(BaseModel):
    texte_question: str = Field(
        ...,
        min_length=3,
        max_length=500,
    )

    contenu: str = Field(
        ...,
        min_length=1,
        max_length=1000,
    )


# Données envoyées au service IA pour analyser une situation.
class OrientationRequest(BaseModel):
    """Données nécessaires pour analyser une situation administrative."""

    # Situation décrite librement par l'utilisateur.
    situation: str = Field(
        ...,
        min_length=20,
        max_length=2000,
        description="Situation administrative décrite par l'utilisateur.",
    )

    # Pays dans lequel la démarche doit être effectuée, s'il est connu.
    pays_application: str | None = Field(
        default=None,
        min_length=2,
        max_length=100,
    )

    # Codes de démarches que Django autorise pour cette analyse.
    demarche_codes: list[str] = Field(
        ...,
        min_length=1,
    )

    # Réponses déjà fournies aux éventuelles questions complémentaires.
    reponses: list[ReponseComplementaireInput] = Field(
        default_factory=list
    )

    @field_validator("situation", mode="before")
    @classmethod
    def nettoyer_situation(cls, valeur: str) -> str:
        """Supprime les espaces inutiles autour de la situation."""

        return valeur.strip()



# Représente une question nécessaire pour mieux comprendre la situation.
class QuestionComplementaireResponse(BaseModel):
    texte: str
    type_question: Literal["TEXTE", "CHOIX_UNIQUE"]

    # Une question texte n'a pas d'options.
    # Une question à choix unique peut en contenir plusieurs.
    options: list[str] = Field(default_factory=list)


# Réponse lorsque certaines informations manquent encore.
class PrecisionsRequisesResponse(BaseModel):
    statut: Literal["PRECISIONS_REQUISES"] = "PRECISIONS_REQUISES"
    questions: list[QuestionComplementaireResponse]


# Réponse lorsque la démarche administrative a été identifiée.
class OrientationResponse(BaseModel):
    statut: Literal["ORIENTATION"] = "ORIENTATION"
    demarche_code: str
    resume: str
    avertissement: str = ""


# Réponse lorsque les sources ne permettent pas une orientation fiable.
class SourcesInsuffisantesResponse(BaseModel):
    statut: Literal["SOURCES_INSUFFISANTES"] = "SOURCES_INSUFFISANTES"
    message: str