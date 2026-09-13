# Permet de réutiliser la même instance du service.
from functools import lru_cache

# Structure représentant un chunk prêt pour ChromaDB.
from app.schemas.document import AdministrativeDocument

# Structure représentant une source administrative complète.
from app.schemas.source import AdministrativeSource

# Fonction utilisée pour découper le contenu en petits morceaux.
from app.services.chunking_service import chunk_text

# Service utilisé pour communiquer avec ChromaDB.
from app.services.vector_store_service import get_vector_store_service


# Service chargé de préparer et d'indexer les sources administratives.
class IngestionService:
    def __init__(self):
        # Réutilise le service ChromaDB déjà initialisé.
        self.vector_store = get_vector_store_service()

    # Découpe puis indexe une source administrative complète.
    def ingest_source(
        self,
        source: AdministrativeSource,
    ) -> int:
        # Découpe le texte en morceaux adaptés à la recherche.
        chunks = chunk_text(source.texte)

        # Récupère les anciens chunks éventuellement liés à cette source.
        anciens_ids = self.vector_store.get_source_document_ids(
            source.source_id
        )

        documents = []

        # Transforme chaque chunk en document prêt pour ChromaDB.
        for index, chunk in enumerate(chunks, start=1):
            document = AdministrativeDocument(
                document_id=f"{source.source_id}-chunk-{index}",
                source_id=source.source_id,
                texte=chunk,
                domaine=source.domaine,
                source_titre=source.source_titre,
                source_url=source.source_url,
                source_type=source.source_type,
                date_verification=source.date_verification,
                pays_application=source.pays_application,
            )

            documents.append(document)

        # Enregistre les nouveaux chunks.
        self.vector_store.upsert_documents(documents)

        # Identifiants correspondant à la nouvelle version de la source.
        nouveaux_ids = {
            document.document_id
            for document in documents
        }

        # Identifie les anciens chunks qui ne sont plus nécessaires.
        ids_obsoletes = [
            document_id
            for document_id in anciens_ids
            if document_id not in nouveaux_ids
        ]

        # Supprime uniquement les anciens chunks devenus obsolètes.
        self.vector_store.delete_documents(ids_obsoletes)

        # Retourne le nombre de chunks créés.
        return len(documents)


# Réutilise la même instance du service pendant l'exécution.
@lru_cache
def get_ingestion_service() -> IngestionService:
    return IngestionService()