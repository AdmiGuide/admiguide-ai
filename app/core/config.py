# Outils Pydantic pour gérer la configuration et lire le fichier .env.
from pydantic_settings import BaseSettings, SettingsConfigDict

# Configuration générale de l'application.
class Settings(BaseSettings):
    app_name: str = "AdmiGuide AI"
    app_version: str = "0.1.0"

    # Modèle utilisé pour transformer les textes en vecteurs.
    embedding_model_name: str = "intfloat/multilingual-e5-small"

    # Dossier local dans lequel ChromaDB conserve les données vectorielles.
    chroma_path: str = "data/chroma"

    # Collection contenant les contenus administratifs indexés.
    chroma_collection_name: str = "administrative_sources"
    
    # Charge automatiquement les variables présentes dans .env.
    model_config = SettingsConfigDict(
            env_file=".env",
            env_file_encoding="utf-8",
            extra="ignore",
        )

    # Clé privée utilisée pour appeler OpenRouter.
    openrouter_api_key: str = ""

    # Modèle génératif utilisé par AdmiGuide.
    llm_model_name: str = ""

    # Adresse de base de l'API OpenRouter.
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    
# Instance utilisée dans toute l'application.
settings = Settings()