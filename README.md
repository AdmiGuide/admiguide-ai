# AdmiGuide AI

Microservice d'intelligence artificielle de **AdmiGuide**, une application web d'orientation administrative destinée à accompagner les usagers dans l'identification des démarches administratives sénégalaises.

Ce projet analyse la situation décrite par l'utilisateur à partir de sources administratives officielles et communique avec le backend principal Django d'AdmiGuide.

## Fonctionnalités principales

- Analyse d'une situation administrative en langage naturel
- Recherche d'informations dans des sources administratives officielles
- Architecture RAG pour enrichir les réponses du modèle de langage
- Génération de questions complémentaires lorsque des informations sont manquantes
- Identification de la démarche administrative adaptée
- Détection des cas où les sources disponibles sont insuffisantes
- Filtrage des sources selon le pays d'application
- Ingestion automatique des fichiers de sources dans la base vectorielle

## Technologies utilisées

- Python
- FastAPI
- ChromaDB
- Embeddings
- Modèle de langage
- Architecture RAG
- Pydantic
- Uvicorn

## Architecture

Le microservice reçoit les situations envoyées par le backend Django, recherche les informations pertinentes dans la base vectorielle puis utilise le modèle de langage pour produire une orientation structurée.

```text
Django Backend
      |
      v
FastAPI - /analyze
      |
      v
Recherche RAG
      |
      v
ChromaDB
      |
      v
Modèle de langage
      |
      v
Réponse structurée
```

Le service peut retourner trois types de résultats :

- `ORIENTATION` : une démarche administrative a été identifiée ;
- `PRECISIONS_REQUISES` : des informations supplémentaires sont nécessaires ;
- `SOURCES_INSUFFISANTES` : les sources disponibles ne permettent pas de fournir une orientation fiable.

## Structure principale

```text
admiguide-ai/
|
|-- app/
|   |-- schemas/
|   `-- services/
|
|-- data/
|   `-- sources/
|       |-- passeport/
|       |-- retour_definitif/
|       |-- etat_civil/
|       `-- pension/
|
|-- scripts/
|   `-- ingest_sources.py
|
|-- requirements.txt
|-- .env.example
`-- README.md
```

## Installation

### 1. Cloner le projet

```bash
git clone https://github.com/AdmiGuide/admiguide-ai.git
cd admiguide-ai
```

### 2. Créer un environnement virtuel

```bash
python -m venv venv
```

Sous Windows PowerShell :

```powershell
.\venv\Scripts\Activate.ps1
```

### 3. Installer les dépendances

```bash
pip install -r requirements.txt
```

## Configuration

Créer un fichier `.env` à la racine du projet à partir de `.env.example` puis renseigner les variables nécessaires au fonctionnement du modèle de langage et des différents services utilisés par l'application.

Le fichier `.env` ne doit pas être ajouté au dépôt Git.

## Ingestion des sources

Les sources administratives sont organisées par domaine dans :

```text
data/sources/
```

Pour les indexer dans la base vectorielle :

```bash
python -m scripts.ingest_sources
```

Le script détecte automatiquement les fichiers `.txt` présents dans les sous-dossiers et les ajoute à ChromaDB.

## Lancement du serveur

```bash
uvicorn app.main:app --reload --port 8001
```

Le service est alors disponible à l'adresse :

```text
http://127.0.0.1:8001/
```

La documentation interactive FastAPI est disponible sur :

```text
http://127.0.0.1:8001/docs
```

## Endpoint principal

### Analyse d'une situation

```text
POST /analyze
```

Exemple de requête :

```json
{
  "situation": "J'ai perdu mon passeport sénégalais au Sénégal et je voudrais savoir comment le remplacer.",
  "pays_application": "SN",
  "demarche_codes": [
    "REMPLACEMENT_PASSEPORT_PERDU"
  ],
  "reponses": []
}
```

Exemple de réponse :

```json
{
  "statut": "ORIENTATION",
  "demarche_code": "REMPLACEMENT_PASSEPORT_PERDU",
  "resume": "L'utilisateur a perdu son passeport sénégalais au Sénégal et souhaite savoir comment le remplacer.",
  "avertissement": ""
}
```

## Scénarios couverts par le MVP

Le service prend actuellement en charge les situations suivantes :

- remplacement d'un passeport sénégalais perdu ;
- retour définitif au Sénégal avec des effets personnels ;
- transcription d'une naissance survenue à l'étranger ;
- réversion de pension et capital-décès d'un fonctionnaire décédé en activité.

## Projet associé

Ce microservice fonctionne avec le backend métier principal :

```text
admiguide-backend
```

Le backend Django envoie les situations à AdmiGuide AI puis enregistre les questions complémentaires ou l'orientation retournée.

## Développeuse

**Dado Watt**