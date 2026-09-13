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
        # Ajoute le contexte de la source au texte utilisé pour l'embedding.
        texte_embedding = (
            f"Domaine : {document.domaine}\n"
            f"Source : {document.source_titre}\n"
            f"{document.texte}"
        )

        # Transforme le contenu enrichi en vecteur.
        vecteur = self.embedding_service.encode_passage(
            texte_embedding
        )

        # Informations permettant d'identifier le contenu et sa source.
        metadata = {
            "source_id": document.source_id,
            "domaine": document.domaine,
            "source_titre": document.source_titre,
            "source_url": document.source_url,
            "source_type": document.source_type,
            "date_verification": document.date_verification,
            "pays_application": document.pays_application,
        }

        # Enregistre le texte, son vecteur et ses métadonnées.
        self.collection.upsert(
            ids=[document.document_id],
            documents=[document.texte],
            embeddings=[vecteur],
            metadatas=[metadata],
        )

    # Ajoute ou met à jour plusieurs documents en une seule opération.
    def upsert_documents(
        self,
        documents: list[AdministrativeDocument],
    ) -> None:
        # Ne fait rien si la liste est vide.
        if not documents:
            return

        # Ajoute le contexte de chaque source avant de créer les embeddings.
        vecteurs = [
            self.embedding_service.encode_passage(
                f"Domaine : {document.domaine}\n"
                f"Source : {document.source_titre}\n"
                f"{document.texte}"
            )
            for document in documents
        ]

        # Prépare les métadonnées de chaque document.
        metadatas = [
            {
                "source_id": document.source_id,
                "domaine": document.domaine,
                "source_titre": document.source_titre,
                "source_url": document.source_url,
                "source_type": document.source_type,
                "date_verification": document.date_verification,
                "pays_application": document.pays_application,
            }
            for document in documents
        ]

        # Enregistre tous les documents dans ChromaDB.
        self.collection.upsert(
            ids=[document.document_id for document in documents],
            documents=[document.texte for document in documents],
            embeddings=vecteurs,
            metadatas=metadatas,
        )

    # Retourne les identifiants des chunks déjà enregistrés pour une source.
    def get_source_document_ids(
        self,
        source_id: str,
    ) -> list[str]:
        resultat = self.collection.get(
            where={"source_id": source_id}
        )

        return resultat["ids"]

    # Recherche les contenus les plus proches de la demande utilisateur.
    def search(
        self,
        texte: str,
        limit: int = 3,
        pays_application: str | None = None,
    ) -> dict:
        # Transforme la demande utilisateur en vecteur.
        vecteur = self.embedding_service.encode_query(texte)

        # Prépare le filtre géographique des sources.
        filtre = None

        if pays_application:
            if pays_application == "SN":
                # Une démarche effectuée au Sénégal utilise les sources sénégalaises.
                filtre = {
                    "pays_application": "SN"
                }

            elif pays_application == "ETRANGER":
                # Recherche explicitement les sources applicables à l'étranger.
                filtre = {
                    "pays_application": "ETRANGER"
                }

            else:
                # À l'étranger, accepte une source propre au pays
                # ou une source consulaire valable à l'étranger en général.
                filtre = {
                    "$or": [
                        {"pays_application": pays_application},
                        {"pays_application": "ETRANGER"},
                    ]
                }

        return self.collection.query(
            query_embeddings=[vecteur],
            n_results=limit,
            where=filtre,
            include=["documents", "metadatas", "distances"],
        )

    # Supprime plusieurs documents à partir de leurs identifiants.
    def delete_documents(
        self,
        document_ids: list[str],
    ) -> None:
        if document_ids:
            self.collection.delete(
                ids=document_ids
            )

    # Supprime un document de ChromaDB à partir de son identifiant.
    def delete_document(self, document_id: str) -> None:
        self.collection.delete(
            ids=[document_id]
        )

    # Supprime tous les morceaux appartenant à une même source.
    def delete_source(self, source_id: str) -> None:
        self.collection.delete(
            where={"source_id": source_id}
        )

# Évite de recréer le client ChromaDB à chaque appel.
@lru_cache
def get_vector_store_service() -> VectorStoreService:
    return VectorStoreService()