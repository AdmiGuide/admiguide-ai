from fastapi import FastAPI

# Importe les routes définies dans le dossier api.
from app.api.routes import router

# Importe la configuration générale de l'application.
from app.core.config import settings


# Création de l'application FastAPI.
app = FastAPI(
    title=settings.app_name,
    description="Service intelligent d'orientation administrative d'AdmiGuide.",
    version=settings.app_version,
)


# Ajoute les routes définies dans routes.py à l'application.
app.include_router(router)