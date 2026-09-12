# Permet de réutiliser la même instance du modèle.
from functools import lru_cache

# Modèle utilisé pour transformer les textes en vecteurs.
from sentence_transformers import SentenceTransformer

# Configuration générale de l'application.
from app.core.config import settings


# Service chargé de créer les embeddings.
class EmbeddingService:
    def __init__(self):
        # Charge le modèle d'embeddings.
        self.model = SentenceTransformer(
            settings.embedding_model_name
        )

    # Transforme une demande utilisateur en vecteur.
    def encode_query(self, texte: str) -> list[float]:
        return self._encode(f"query: {texte}")

    # Transforme un contenu administratif en vecteur.
    def encode_passage(self, texte: str) -> list[float]:
        return self._encode(f"passage: {texte}")

    # Méthode commune utilisée pour créer un vecteur normalisé.
    def _encode(self, texte: str) -> list[float]:
        vecteur = self.model.encode(
            texte,
            normalize_embeddings=True,
        )

        return vecteur.tolist()


# Évite de recharger le modèle à chaque appel.
@lru_cache
def get_embedding_service() -> EmbeddingService:
    return EmbeddingService()