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
        limit: int = 3,
        domaine: str | None = None,
    ) -> list[dict]:
        """
        Recherche les passages pertinents dans ChromaDB.

        Lorsque le domaine est connu, la recherche est limitée
        à ce domaine. Les résultats sont ensuite sélectionnés
        pour éviter plusieurs passages d'une même source.
        """

        # Récupère plusieurs morceaux afin de pouvoir
        # sélectionner des sources administratives différentes.
        resultat = self.vector_store.search(
            texte=texte,
            limit=max(8, limit),
            domaine=domaine,
        )

        # Récupère les textes, les métadonnées et les distances.
        documents = resultat["documents"][0]
        metadatas = resultat["metadatas"][0]
        distances = resultat["distances"][0]

        contenus = []
        sources_vues = set()

        # Parcourt les morceaux dans leur ordre de pertinence.
        for document, metadata, distance in zip(
            documents,
            metadatas,
            distances,
        ):
            source_id = metadata["source_id"]

            # Ignore les passages provenant d'une source
            # déjà sélectionnée.
            if source_id in sources_vues:
                continue

            sources_vues.add(source_id)

            # Prépare les informations nécessaires au contexte RAG.
            contenus.append(
                {
                    "texte": document,
                    "source_id": source_id,
                    "source_titre": metadata["source_titre"],
                    "source_url": metadata["source_url"],
                    "domaine": metadata["domaine"],
                    "distance": distance,
                }
            )

            # Arrête la sélection lorsque la limite est atteinte.
            if len(contenus) >= limit:
                break

        return contenus

    # Transforme les résultats en contexte lisible pour le LLM.
    def build_context_from_results(
        self,
        contenus: list[dict],
    ) -> str:
        blocs = []

        # Prépare un bloc lisible pour chaque contenu retrouvé.
        for index, contenu in enumerate(
            contenus,
            start=1,
        ):
            bloc = (
                f"SOURCE {index}\n"
                f"ID : {contenu['source_id']}\n"
                f"Titre : {contenu['source_titre']}\n"
                f"URL : {contenu['source_url']}\n"
                f"Contenu :\n{contenu['texte']}"
            )

            blocs.append(bloc)

        # Sépare clairement les différentes sources.
        return "\n\n---\n\n".join(blocs)

    # Recherche les contenus puis construit le contexte.
    def build_context(
        self,
        texte: str,
        limit: int = 3,
    ) -> str:
        contenus = self.retrieve(
            texte=texte,
            limit=limit,
        )

        return self.build_context_from_results(
            contenus
        )


# Réutilise la même instance pendant l'exécution de l'application.
@lru_cache
def get_retrieval_service() -> RetrievalService:
    return RetrievalService()