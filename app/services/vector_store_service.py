# Permet de réutiliser la même instance du service.
from functools import lru_cache

# Bibliothèque utilisée comme base de données vectorielle.
import chromadb

# Configuration générale de l'application.
from app.core.config import settings

# Service chargé de créer les embeddings.
from app.services.embedding_service import get_embedding_service

# Structure utilisée pour valider les documents avant leur indexation.
from app.schemas.document import AdministrativeDocument

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

        # Ajoute ou met à jour un document administratif dans ChromaDB.
    def upsert_document(
        self,
        document: AdministrativeDocument,
    ) -> None:
        # Transforme le contenu administratif en vecteur.
        vecteur = self.embedding_service.encode_passage(
            document.texte
        )

        # Informations permettant d'identifier la démarche et la source.
        metadata = {
            "demarche_code": document.demarche_code,
            "pays_application": document.pays_application,
            "juridiction": document.juridiction,
            "source_titre": document.source_titre,
            "source_url": document.source_url,
            "source_type": document.source_type,
        }

        # Enregistre le texte, son vecteur et ses métadonnées.
        self.collection.upsert(
            ids=[document.document_id],
            documents=[document.texte],
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

    # Supprime un document de ChromaDB à partir de son identifiant.
    def delete_document(self, document_id: str) -> None:
        self.collection.delete(
            ids=[document_id]
        )

# Évite de recréer le client ChromaDB à chaque appel.
@lru_cache
def get_vector_store_service() -> VectorStoreService:
    return VectorStoreService()