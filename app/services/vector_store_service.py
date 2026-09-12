# Permet de réutiliser la même instance du service.
from functools import lru_cache

# Bibliothèque utilisée comme base de données vectorielle.
import chromadb

# Configuration générale de l'application.
from app.core.config import settings

# Service chargé de créer les embeddings.
from app.services.embedding_service import get_embedding_service


# Service chargé du stockage et de la recherche vectorielle.
class VectorStoreService:
    def __init__(self):
        # Réutilise le service d'embeddings déjà chargé en mémoire.
        self.embedding_service = get_embedding_service()

        # Crée ou ouvre la base ChromaDB locale.
        self.client = chromadb.PersistentClient(
            path=settings.chroma_path
        )

        # Crée ou récupère la collection des contenus administratifs.
        self.collection = self.client.get_or_create_collection(
            name=settings.chroma_collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    # Ajoute ou met à jour un contenu administratif dans ChromaDB.
    def upsert_document(
        self,
        document_id: str,
        texte: str,
        metadata: dict[str, str | int | float | bool],
    ) -> None:
        vecteur = self.embedding_service.encode_passage(texte)

        self.collection.upsert(
            ids=[document_id],
            documents=[texte],
            embeddings=[vecteur],
            metadatas=[metadata],
        )

    # Recherche les contenus les plus proches de la demande utilisateur.
    def search(self, texte: str, limit: int = 3) -> dict:
        vecteur = self.embedding_service.encode_query(texte)

        return self.collection.query(
            query_embeddings=[vecteur],
            n_results=limit,
            include=["documents", "metadatas", "distances"],
        )


# Évite de recréer le client ChromaDB à chaque appel.
@lru_cache
def get_vector_store_service() -> VectorStoreService:
    return VectorStoreService()