# Image Python légère pour le microservice IA.
FROM python:3.12-slim

# Dossier de travail de l'application.
WORKDIR /app

# Installe les dépendances Python.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copie le microservice dans le conteneur.
COPY . .

# Port utilisé par FastAPI.
EXPOSE 8001

# Lance l'API FastAPI.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]