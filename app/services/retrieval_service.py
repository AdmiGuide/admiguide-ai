# Permet de réutiliser la même instance du service.
from functools import lru_cache

# Service utilisé pour effectuer les recherches dans ChromaDB.
from app.services.vector_store_service import get_vector_store_service


# Service chargé de récupérer et préparer les informations utiles au LLM.
class RetrievalService:
    def __init__(self):
        # Réutilise le service ChromaDB déjà initialisé.
        self.vector_store = get_vector_store_service()

    # Recherche les contenus pertinents pour une situation utilisateur.
    def retrieve(
        self,
        texte: str,
        pays_application: str | None = None,
        limit: int = 3,
    ) -> list[dict]:
        resultat = self.vector_store.search(
            texte=texte,
            limit=limit,
            pays_application=pays_application,
        )

        documents = resultat["documents"][0]
        metadatas = resultat["metadatas"][0]
        distances = resultat["distances"][0]

        contenus = []

        # Regroupe chaque texte avec sa source et sa distance.
        for document, metadata, distance in zip(
            documents,
            metadatas,
            distances,
        ):
            contenus.append(
                {
                    "texte": document,
                    "source_id": metadata["source_id"],
                    "source_titre": metadata["source_titre"],
                    "source_url": metadata["source_url"],
                    "distance": distance,
                }
            )

        return contenus

    # Transforme les résultats en contexte lisible pour le LLM.
    def build_context(
        self,
        texte: str,
        pays_application: str | None = None,
        limit: int = 3,
    ) -> str:
        contenus = self.retrieve(
            texte=texte,
            pays_application=pays_application,
            limit=limit,
        )

        blocs = []

        # Prépare un bloc lisible pour chaque contenu retrouvé.
        for index, contenu in enumerate(contenus, start=1):
            bloc = (
                f"SOURCE {index}\n"
                f"Titre : {contenu['source_titre']}\n"
                f"URL : {contenu['source_url']}\n"
                f"Contenu :\n{contenu['texte']}"
            )

            blocs.append(bloc)

        # Sépare clairement les différentes sources.
        return "\n\n---\n\n".join(blocs)


# Réutilise la même instance pendant l'exécution de l'application.
@lru_cache
def get_retrieval_service() -> RetrievalService:
    return RetrievalService()