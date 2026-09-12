# Outil Pydantic utilisé pour définir la structure d'un document.
from pydantic import BaseModel, Field


# Représente un contenu administratif prêt à être indexé dans ChromaDB.
class AdministrativeDocument(BaseModel):
    # Identifiant unique du contenu dans ChromaDB.
    document_id: str

    # Texte administratif utilisé pour la recherche sémantique.
    texte: str = Field(
        ...,
        min_length=20,
    )

    # Code stable de la démarche liée au document.
    demarche_code: str

    # Pays dans lequel l'information administrative s'applique.
    pays_application: str

    # Administration ou juridiction concernée.
    juridiction: str

    # Titre de la source officielle.
    source_titre: str

    # Adresse de la source officielle.
    source_url: str

    # Type de source : page web, document, API, etc.
    source_type: str