# Outil Pydantic utilisé pour définir la structure d'un document.
from pydantic import BaseModel, Field


# Représente un morceau de contenu prêt à être indexé dans ChromaDB.
class AdministrativeDocument(BaseModel):
    # Identifiant unique du chunk dans ChromaDB.
    document_id: str

    # Identifiant de la source complète.
    source_id: str

    # Texte utilisé pour la recherche sémantique.
    texte: str = Field(
        ...,
        min_length=20,
    )

    # Domaine administratif auquel appartient le contenu.
    domaine: str

    # Titre de la source.
    source_titre: str

    # Adresse officielle de la source.
    source_url: str

    # Type de source.
    source_type: str

    # Date à laquelle la source a été vérifiée.
    date_verification: str