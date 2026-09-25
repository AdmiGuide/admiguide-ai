# Outils Pydantic pour gérer la configuration et lire le fichier .env.
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration générale de l'application."""

    app_name: str = "AdmiGuide AI"
    app_version: str = "0.1.0"

    # Modèle utilisé pour transformer les textes en vecteurs.
    embedding_model_name: str = "intfloat/multilingual-e5-small"

    # Configuration de ChromaDB.
    chroma_path: str = "data/chroma"
    chroma_collection_name: str = "administrative_sources"

    # Clé utilisée pour appeler Groq.
    groq_api_key: str = ""

    # Modèle génératif utilisé par AdmiGuide.
    llm_model_name: str = "openai/gpt-oss-120b"

    # Adresse de base de l'API Groq.
    groq_base_url: str = "https://api.groq.com/openai/v1"

    # Charge automatiquement les variables du fichier .env.
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


# Instance utilisée dans toute l'application.
settings = Settings()