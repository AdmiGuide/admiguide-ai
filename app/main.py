from fastapi import FastAPI

# Création de l'application FastAPI principale
app = FastAPI(
    title="AdmiGuide AI",
    description="Microservice IA chargé de l'orientation administrative.",
    version="1.0.0",
)


# Route simple permettant de vérifier que l'API fonctionne
@app.get("/")
def root():
    return {
        "message": "AdmiGuide AI fonctionne correctement."
    }


# Route permettant de vérifier l'état du microservice
@app.get("/health")
def health_check():
    return {
        "status": "ok"
    }