# Outils Pydantic pour définir et valider une source administrative.
from pydantic import BaseModel, Field


# Représente une source administrative complète avant son découpage.
class AdministrativeSource(BaseModel):
    # Identifiant stable permettant de reconnaître la source.
    source_id: str

    # Contenu textuel complet de la source.
    texte: str = Field(
        ...,
        min_length=20,
    )

    # Domaine administratif auquel appartient la source.
    domaine: str

    # Titre permettant d'identifier la source.
    source_titre: str

    # Adresse officielle de la source.
    source_url: str

    # Type de source : page web, document, API, etc.
    source_type: str

    # Date à laquelle la source a été vérifiée.
    date_verification: str