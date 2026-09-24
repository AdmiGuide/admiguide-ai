# Image Python légère pour le microservice IA.
FROM python:3.12-slim

# Dossier de travail de l'application.
WORKDIR /app

# Installe PyTorch en version CPU uniquement.
RUN pip install \
    --no-cache-dir \
    --timeout 120 \
    --retries 5 \
    torch==2.14.0+cpu \
    --index-url https://download.pytorch.org/whl/cpu

# Copie les dépendances nécessaires à Docker.
COPY requirements-docker.txt .

# Installe les dépendances du microservice IA.
RUN pip install \
    --no-cache-dir \
    --timeout 120 \
    --retries 5 \
    -r requirements-docker.txt

# Copie le microservice dans le conteneur.
COPY . .

# Port utilisé par FastAPI.
EXPOSE 8001

# Lance l'API FastAPI.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]