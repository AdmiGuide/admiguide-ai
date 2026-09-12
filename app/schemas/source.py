# Outils Pydantic pour définir et valider une source administrative.
from pydantic import BaseModel, Field


# Représente une source administrative complète avant son découpage.
class AdministrativeSource(BaseModel):
    # Identifiant stable permettant de reconnaître la source.
    source_id: str

    # Contenu textuel complet récupéré depuis la source officielle.
    texte: str = Field(
        ...,
        min_length=20,
    )

    # Code de la démarche concernée par cette source.
    demarche_code: str

    # Pays dans lequel l'information administrative s'applique.
    pays_application: str

    # Administration ou zone concernée par l'information.
    juridiction: str

    # Titre de la source officielle.
    source_titre: str

    # Adresse de la source officielle.
    source_url: str

    # Type de source : page web, document, API, etc.
    source_type: str