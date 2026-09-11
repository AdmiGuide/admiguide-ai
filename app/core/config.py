# Outils Pydantic pour gérer la configuration et lire le fichier .env.
from pydantic_settings import BaseSettings, SettingsConfigDict

# Configuration générale de l'application.
class Settings(BaseSettings):
    app_name: str = "AdmiGuide AI"
    app_version: str = "0.1.0"

    # Charge automatiquement les variables présentes dans .env.
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


# Instance utilisée dans toute l'application.
settings = Settings()