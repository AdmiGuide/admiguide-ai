# AdmiGuide AI

**AdmiGuide AI** est le microservice d'intelligence artificielle d'[AdmiGuide](https://github.com/orgs/AdmiGuide/repositories), une application d'orientation dans les démarches administratives sénégalaises. Développé avec **FastAPI**, il est appelé par le backend Django ; le frontend Angular ne le contacte pas directement.

## Fonctionnalités

- **Orientation administrative** : analyse une situation en français, recherche des informations dans un référentiel officiel via **RAG**, demande des précisions si nécessaire et identifie une démarche parmi celles autorisées par Django.
- **Chatbot contextuel** : explique les termes, pièces et étapes d'une orientation existante sur les pages *Quelques précisions*, *Votre orientation* et *Suivi de ma démarche*. Il conserve un historique récent, peut rechercher des renseignements pratiques sur des sites institutionnels et ne modifie pas l'orientation.
- **Transcription vocale** : transforme en texte les situations dictées, après préparation de l'audio avec FFmpeg.

Le MVP couvre trois domaines : **passeport sénégalais, pensions après décès et foncier**. AdmiGuide fournit une aide à l'orientation, **pas une décision administrative ni un service de dépôt de dossier**.

## Stack technique

| Composant | Technologie |
| --- | --- |
| API et validation | Python 3.12, FastAPI, Pydantic |
| Orientation / RAG | ChromaDB, Sentence Transformers (`intfloat/multilingual-e5-small`) |
| Modèle d'orientation | `openai/gpt-oss-120b` via Groq |
| Chatbot contextuel | `openai/gpt-oss-20b` via Groq |
| Transcription | `whisper-large-v3-turbo` via Groq, FFmpeg |
| Exécution | Uvicorn, Docker |

### Architecture

```text
Angular (interface utilisateur)
            |
            v
Django REST Framework (comptes, référentiel et accès)
            |
            v
FastAPI — AdmiGuide AI
  |-- /analyze    -> RAG (ChromaDB) + LLM -> orientation
  |-- /chat       -> contexte existant + LLM / recherche web si nécessaire
  `-- /transcribe -> FFmpeg + Whisper -> texte
```

Les documents RAG sont indexés localement dans ChromaDB. **La recherche web du chatbot est distincte du RAG d'orientation** : elle sert à vérifier certaines informations pratiques, notamment la localisation ou les coordonnées d'un service administratif.

## Installation en local

### 1. Prérequis

- **Python 3.12** et Git ;
- **FFmpeg** installé et accessible dans le `PATH` pour la transcription ;
- une **clé API Groq** valide et un accès Internet ;
- le backend [admiguide-backend](https://github.com/AdmiGuide/admiguide-backend) pour utiliser l'application complète.

Le modèle d'embeddings peut être téléchargé lors de la première exécution.

### 2. Cloner et installer

```bash
git clone https://github.com/AdmiGuide/admiguide-ai.git
cd admiguide-ai
python -m venv venv
```

**Windows PowerShell :**

```powershell
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

**Linux / macOS :**

```bash
source venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

### 3. Configurer `.env`

Renseigner au minimum votre clé Groq dans le fichier `.env` créé à la racine :

```dotenv
GROQ_API_KEY=votre_cle_api_groq
LLM_MODEL_NAME=openai/gpt-oss-120b
CHAT_LLM_MODEL_NAME=openai/gpt-oss-20b
TRANSCRIPTION_MODEL_NAME=whisper-large-v3-turbo
```

Les paramètres RAG (`CHROMA_PATH`, `CHROMA_COLLECTION_NAME`, `EMBEDDING_MODEL_NAME`) ont des valeurs par défaut dans `app/core/config.py`. **Ne jamais committer `.env` ni une clé API réelle.**

### 4. Indexer les sources administratives

À la racine du dépôt :

```bash
python -m scripts.ingest_sources
```

Cette commande indexe les documents de `data/sources/` dans ChromaDB (`data/chroma/` par défaut). **Elle est nécessaire lors d'une première installation** ou après mise à jour des sources. La base vectorielle générée n'est pas versionnée.

### 5. Lancer FastAPI

```bash
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
```

- **Santé du service** : http://127.0.0.1:8001/health
- **Documentation interactive (Swagger)** : http://127.0.0.1:8001/docs

Pour un parcours complet, démarrer également MySQL, Django et Angular selon les instructions de leurs dépôts respectifs.

## Endpoints principaux

| Méthode | Route | Description |
| --- | --- | --- |
| `GET` | `/health` | Vérifier que le service répond |
| `POST` | `/analyze` | Analyser une situation à partir des codes de démarches autorisés et des réponses complémentaires |
| `POST` | `/chat` | Répondre à une question contextualisée (`PRECISIONS`, `RESULTAT` ou `SUIVI`) |
| `POST` | `/transcribe` | Transcrire un fichier audio (`multipart/form-data`, champ `audio`, maximum 10 Mio) |

Les schémas d'entrée et de sortie sont décrits dans **`/docs`** et dans `app/schemas/`. Django prépare le contexte du chatbot depuis la situation enregistrée, ses pièces, étapes et services associés ; il contrôle également les droits d'accès.

## Tests

Depuis la racine du dépôt, avec l'environnement virtuel activé :

```bash
# Tests hors ligne du chatbot (19 tests)
python -m unittest discover -s scripts -p "test_chat_*.py" -v

# Vérification des sources institutionnelles (5 tests)
python -m unittest discover -s scripts -p "test_sources_officielles.py" -v
```

**24 tests automatisés validés** lors de la dernière vérification. Ils couvrent notamment les règles du chatbot, la continuité de conversation, la réutilisation de la localité depuis la situation initiale, la distinction entre siège et bureau territorial, ainsi que le filtrage des sources. Ces tests hors ligne ne remplacent pas les essais de bout en bout avec Groq, Django et Angular.

## Docker

```bash
docker build -t admiguide-ai .
docker run --rm -p 8001:8001 --env-file .env admiguide-ai
```

Le conteneur expose le port **8001**. Pour utiliser le RAG dans Docker, **indexer les sources dans le conteneur et conserver `data/chroma/` dans un volume persistant**, ou utiliser l'orchestration Docker Compose du projet. La commande ci-dessus démarre l'API seule : elle ne prépare pas automatiquement la base vectorielle.

## Fiabilité et limites

Le chatbot explique une démarche existante, sans inventer d'étapes, de pièces, d'adresses, de coûts ou de délais. Pour les renseignements pratiques, il privilégie les sources institutionnelles vérifiables et peut signaler qu'une information n'a pas pu être confirmée. Les réponses dépendent du référentiel, des sources disponibles et des quotas Groq.

## Dépôts associés

- [admiguide-frontend](https://github.com/AdmiGuide/admiguide-frontend) — interface Angular.
- [admiguide-backend](https://github.com/AdmiGuide/admiguide-backend) — API Django, authentification, référentiel et suivi.

**Développement :** Dado Watt.
