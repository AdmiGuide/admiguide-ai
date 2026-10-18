# AdmiGuide AI

Microservice d'intelligence artificielle d'**AdmiGuide**, une application d'orientation administrative qui aide les usagers à identifier les démarches correspondant à leur situation et à comprendre les précisions nécessaires avant d'obtenir une orientation.

Développé avec **FastAPI**, ce service analyse des demandes formulées en langage naturel, interroge un référentiel de sources administratives officielles avec une architecture **RAG** (*Retrieval-Augmented Generation*) et s'appuie sur les modèles proposés par **Groq**. Il assure également la **transcription vocale** des situations dictées depuis l'interface web.

Le microservice **n'effectue pas les démarches à la place de l'usager**. Il propose une orientation indicative, soumise aux conditions et vérifications des administrations compétentes. Le référentiel Django fournit ensuite les étapes, pièces, services, coûts et délais affichés dans l'application.

## Fonctionnalités principales

- Compréhension de demandes rédigées en français courant, y compris avec des formulations imprécises ou des fautes d'orthographe.
- Identification du domaine administratif et reformulation d'une requête de recherche documentaire avec un LLM.
- Recherche sémantique dans **ChromaDB** à partir de sources officielles indexées localement.
- Sélection de passages issus de **sources distinctes** afin de diversifier le contexte fourni au modèle.
- Analyse des informations déjà données et génération de questions complémentaires si nécessaire.
- Identification d'une démarche uniquement parmi les codes autorisés par le backend Django.
- Retour de réponses structurées et validées, ou d'un message explicatif lorsque l'orientation n'est pas possible.
- Préparation d'enregistrements audio avec **FFmpeg** et transcription en français via **Whisper Large V3 Turbo** sur Groq.
- Ingestion et mise à jour des documents administratifs dans la base vectorielle.

## Périmètre actuellement pris en charge

La branche actuelle couvre les **démarches sénégalaises** des trois domaines suivants. Les parcours documentés concernent prioritairement les situations prévues pour le MVP, notamment à Dakar.

| Domaine | Code de démarche | Description |
| --- | --- | --- |
| Passeport | `DEMANDE_PASSEPORT_ORDINAIRE` | Première demande de passeport sénégalais |
| Passeport | `RENOUVELLEMENT_PASSEPORT` | Renouvellement d'un passeport sénégalais |
| Passeport | `PASSEPORT_PERDU_OU_VOLE` | Passeport sénégalais perdu ou volé |
| Pension | `REVERSION_PENSION_CAPITAL_DECES_ACTIVITE` | Décès d'un fonctionnaire en activité |
| Pension | `REVERSION_PENSION_APRES_RETRAITE` | Décès d'un fonctionnaire à la retraite |
| Foncier | `REGULARISATION_BAIL` | Régularisation d'un terrain par voie de bail |
| Foncier | `ACQUISITION_MUTATION_TITRE_FONCIER` | Acquisition ou mutation d'un bien sous titre foncier |
| Foncier | `TRANSFORMATION_BAIL_EN_TITRE_FONCIER` | Transformation d'un bail en titre foncier |
| Foncier | `TRANSFORMATION_AUTORISATION_OCCUPATION_EN_TITRE_FONCIER` | Orientation relative à une autorisation d'occupation |

L'existence d'un code dans ce service ne suffit pas à rendre une démarche utilisable : **Django doit également l'autoriser et disposer de l'entrée correspondante dans son référentiel**. Les questions posées permettent de distinguer les situations sans présumer des droits de l'usager.

Les demandes relatives à d'autres domaines sont actuellement considérées comme hors du périmètre actif de ce microservice. Le présent README décrit le **code de cette branche**, et non l'ensemble des fonctionnalités envisagées pour les prochaines versions d'AdmiGuide.

## Technologies

| Composant | Technologie |
| --- | --- |
| API HTTP | Python 3.12 (image Docker), FastAPI, Uvicorn |
| Validation | Pydantic, Pydantic Settings |
| Appels externes | HTTPX |
| Base vectorielle | ChromaDB, collection `administrative_sources` |
| Embeddings | Sentence Transformers — `intfloat/multilingual-e5-small` |
| LLM d'analyse | `openai/gpt-oss-120b` via l'API Groq |
| Reconnaissance vocale | `whisper-large-v3-turbo` via l'API Groq |
| Préparation audio | FFmpeg |
| Conteneurisation | Docker, image `python:3.12-slim` |

Les fichiers `requirements.txt` et `requirements-docker.txt` contiennent respectivement les dépendances de l'environnement Python local et celles retenues pour l'image Docker.

## Architecture et fonctionnement

```text
Utilisateur (Angular)
        |
        v
Backend Django REST Framework
        |
        | POST /analyze
        v
AdmiGuide AI (FastAPI)
        |
        +--> Préparation de la demande (Groq)
        |      - identification du domaine
        |      - formulation de la requête RAG
        |
        +--> Embeddings (multilingual-e5-small)
        |          |
        |          v
        |      ChromaDB (sources officielles)
        |          |
        |          v
        |      Passages pertinents de sources distinctes
        |
        +--> Prompt métier + contexte RAG (Groq)
        |          |
        |          v
        |      Validation JSON / Pydantic / codes autorisés
        |
        v
Django : enregistrement et enrichissement de l'orientation
        |
        v
Angular : résultat, sources, étapes et suivi
```

### Déroulement d'une analyse

1. Django transmet la description de la situation, les codes de démarches autorisés et, si elles existent, les réponses aux questions précédentes.
2. Le service `preparation_demande_service.py` utilise Groq pour identifier un domaine (`PASSEPORT`, `PENSION`, `FONCIER`, `HORS_COUVERTURE` ou `INDETERMINE`) et proposer une requête documentaire sans déterminer la démarche finale.
3. Pour un domaine couvert, le service limite les codes candidats à ceux transmis par Django.
4. Le service RAG recherche les documents pertinents dans ChromaDB. Il demande huit passages candidats par défaut à ChromaDB, puis retient **jusqu'à trois sources distinctes** selon les résultats disponibles.
5. Le service de prompts associe la demande, les réponses précédentes, les extraits officiels et les règles spécifiques au domaine.
6. Groq produit la proposition d'orientation au format JSON, que Python contrôle avant de la retourner.

L'identification du domaine et la génération finale sont **deux appels distincts au LLM** lors du parcours normal. Les limites de requêtes et de tokens de Groq peuvent donc avoir un effet sur la disponibilité du service.

### Statuts retournés

| Statut | Signification |
| --- | --- |
| `ORIENTATION` | Une démarche autorisée a été identifiée ; le résultat contient son code, un résumé et un éventuel avertissement. |
| `PRECISIONS_REQUISES` | Une ou plusieurs informations sont nécessaires ; le résultat contient les questions à poser. |
| `SOURCES_INSUFFISANTES` | Le service ne peut pas proposer une orientation suffisamment fiable ou adaptée au périmètre pris en charge ; une explication est fournie. |

Le dernier statut peut aussi correspondre à un cas **non couvert ou nécessitant une vérification**, et pas uniquement à l'absence de documents dans ChromaDB.

## Structure du projet

```text
admiguide-ai/
├── app/
│   ├── api/
│   │   └── routes.py                 # Endpoints FastAPI
│   ├── core/
│   │   └── config.py                 # Configuration et variables d'environnement
│   ├── schemas/                      # Modèles Pydantic
│   ├── services/
│   │   ├── preparation_demande_service.py
│   │   ├── orientation_service.py
│   │   ├── prompt_service.py
│   │   ├── retrieval_service.py
│   │   ├── vector_store_service.py
│   │   ├── embedding_service.py
│   │   ├── source_parser_service.py
│   │   ├── chunking_service.py
│   │   ├── ingestion_service.py
│   │   ├── llm_service.py
│   │   ├── response_parser_service.py
│   │   ├── audio_cleaning_service.py
│   │   └── transcription_service.py
│   └── main.py
├── data/
│   ├── sources/                      # Documents administratifs suivis par Git
│   │   ├── passeport/
│   │   ├── pension/
│   │   └── foncier/
│   └── chroma/                       # Base vectorielle locale générée (non versionnée)
├── scripts/
│   ├── ingest_sources.py
│   ├── test_mvp_full_flow.py
│   ├── test_identification_domaine.py
│   ├── test_orientation_llm.py
│   ├── test_requete_rag_ia.py
│   └── test_sources_passeport.py
├── .env.example
├── requirements.txt
├── requirements-docker.txt
├── Dockerfile
└── README.md
```

## Installation locale

### 1. Récupérer le dépôt

```bash
git clone https://github.com/AdmiGuide/admiguide-ai.git
cd admiguide-ai
```

### 2. Créer un environnement virtuel

```bash
python -m venv venv
```

**Windows PowerShell :**

```powershell
.\venv\Scripts\Activate.ps1
```

**Linux / macOS :**

```bash
source venv/bin/activate
```

### 3. Installer les dépendances

```bash
python -m pip install -r requirements.txt
```

**FFmpeg doit également être installé et accessible dans le `PATH`** pour utiliser `/transcribe`. L'image Docker installe FFmpeg automatiquement.

Le modèle d'embeddings peut être téléchargé lors de sa première utilisation. Une connexion réseau peut donc être nécessaire au premier chargement.

### 4. Configurer les variables d'environnement

Créer le fichier `.env` à la racine du projet à partir de `.env.example` :

```env
GROQ_API_KEY=votre_cle_api_groq
LLM_MODEL_NAME=openai/gpt-oss-120b
TRANSCRIPTION_MODEL_NAME=whisper-large-v3-turbo
```

- `GROQ_API_KEY` : clé pour les appels d'analyse et de transcription à Groq.
- `LLM_MODEL_NAME` : modèle génératif utilisé pour préparer et analyser les demandes.
- `TRANSCRIPTION_MODEL_NAME` : modèle de transcription audio.

Les paramètres supplémentaires définis par défaut dans `app/core/config.py` comprennent `EMBEDDING_MODEL_NAME`, `CHROMA_PATH`, `CHROMA_COLLECTION_NAME` et `GROQ_BASE_URL`.

**Ne pas versionner `.env` :** il est exclu par `.gitignore`. Ne jamais publier une vraie clé API dans le README ou dans les commits.

## Sources administratives et indexation RAG

Les fichiers de `data/sources/` regroupent des extraits de sources officielles, structurés en blocs commençant par `=== SOURCE ===`. Chaque bloc contient notamment un identifiant, un titre, une URL, un type, une date de vérification, un pays d'application et un contenu.

Dans la branche examinée, les sources suivies par Git comprennent les trois fichiers suivants :

```text
data/sources/passeport/passeport.txt
data/sources/pension/pensions_deces.txt
data/sources/foncier/regularisation_fonciere.txt
```

Ils décrivent respectivement les procédures relatives au passeport, les pensions après décès et les démarches foncières, dont la transformation de droits d'occupation en titre foncier. **Ce corpus est organisé manuellement : il n'y a pas de recherche automatique sur le Web pendant une orientation.**

### Indexer les sources

Depuis la racine du projet et avec le venv activé :

```bash
python -m scripts.ingest_sources
```

Le script :

1. Parcourt les fichiers `.txt` de `data/sources/`.
2. Lit les blocs de sources et leurs métadonnées.
3. Découpe les textes en passages (environ 1 000 caractères maximum par défaut).
4. Génère des embeddings avec `intfloat/multilingual-e5-small`.
5. Enregistre ou met à jour les documents dans ChromaDB.

La base est stockée par défaut dans **`data/chroma/`**, qui n'est pas suivie par Git. L'indexation doit être effectuée dans chaque nouvel environnement utilisant une base vide, ou après modification des sources.

La recherche actuelle filtre les métadonnées sur **`pays_application = SN`** et, lorsqu'il est connu, sur le domaine administratif. Ce filtrage est réalisé côté recherche vectorielle : `pays_application` **n'est pas un champ du JSON reçu par `/analyze`**.

## Démarrer le microservice

```bash
uvicorn app.main:app --reload --port 8001
```

- API : <http://127.0.0.1:8001/>
- Vérification de santé : <http://127.0.0.1:8001/health>
- Swagger UI : <http://127.0.0.1:8001/docs>

En fonctionnement normal, le frontend Angular échange avec le backend Django, qui appelle à son tour AdmiGuide AI. Angular ne consomme pas directement `/analyze` ni `/transcribe`.

## Endpoints HTTP

| Méthode | Endpoint | Rôle |
| --- | --- | --- |
| `GET` | `/` | Message de disponibilité du service |
| `GET` | `/health` | Réponse `{"status": "ok"}` |
| `POST` | `/analyze` | Analyse d'une situation administrative |
| `POST` | `/transcribe` | Transcription d'un enregistrement audio |

### `POST /analyze`

Le corps attendu comporte :

- `situation` : description libre, de **20 à 1 500 caractères** ;
- `demarche_codes` : liste non vide de codes autorisés ;
- `reponses` : liste facultative de réponses précédentes. Chaque réponse contient `texte_question` et `contenu`.

**Exemple de requête :**

```json
{
  "situation": "J'ai perdu mon passeport sénégalais à Dakar et je voudrais savoir comment en obtenir un nouveau.",
  "demarche_codes": [
    "DEMANDE_PASSEPORT_ORDINAIRE",
    "RENOUVELLEMENT_PASSEPORT",
    "PASSEPORT_PERDU_OU_VOLE"
  ],
  "reponses": []
}
```

**Exemple de réponse d'orientation (illustratif) :**

```json
{
  "statut": "ORIENTATION",
  "demarche_code": "PASSEPORT_PERDU_OU_VOLE",
  "resume": "L'utilisateur a perdu son passeport sénégalais à Dakar et souhaite le remplacer.",
  "avertissement": ""
}
```

**Exemple de réponse demandant une précision (illustratif) :**

```json
{
  "statut": "PRECISIONS_REQUISES",
  "questions": [
    {
      "texte": "S'agit-il d'un passeport sénégalais ?",
      "type_question": "CHOIX_UNIQUE",
      "options": ["Oui", "Non", "Je ne sais pas"]
    }
  ]
}
```

**Exemple de réponse sans orientation fiable (illustratif) :**

```json
{
  "statut": "SOURCES_INSUFFISANTES",
  "message": "AdmiGuide ne couvre pas encore ce type de demande administrative."
}
```

Ces exemples décrivent les formats de l'API. Les réponses effectives dépendent des informations transmises, des sources indexées et du modèle. Une question déjà résolue dans la description ne doit normalement pas être reposée.

### `POST /transcribe`

L'endpoint accepte un formulaire **`multipart/form-data`** contenant un fichier sous le nom **`audio`**.

```powershell
curl.exe -X POST "http://127.0.0.1:8001/transcribe" -F "audio=@enregistrement.webm"
```

Le fichier doit avoir un type MIME `audio/*`, être non vide et ne pas dépasser **10 Mo** (limite contrôlée par cette route). Les principales étapes du traitement sont :

1. Enregistrement temporaire du fichier reçu.
2. Préparation avec FFmpeg : traitement des silences prolongés, conversion en **mono**, **16 kHz**, format **WAV**.
3. Envoi à l'API de transcription Groq, avec reconnaissance en français.
4. Retour du texte transcrit, puis suppression des fichiers temporaires.

**Réponse attendue :**

```json
{
  "message": "Audio transcrit correctement.",
  "transcription": "J'ai perdu mon passeport sénégalais. Quelles sont les étapes à suivre ?"
}
```

La **limite d'enregistrement de 120 secondes** est appliquée dans l'interface Angular ; elle ne constitue pas une validation de durée sur cette route FastAPI. En cas d'indisponibilité de Groq, la transcription peut retourner une erreur HTTP `503`.

## Garde-fous et limites

- Les règles du prompt demandent de s'appuyer sur les passages officiels fournis et de ne pas inventer les conditions, documents, coûts, délais ou droits de l'usager.
- La situation initiale et les réponses déjà données sont transmises ensemble pour éviter les questions répétitives.
- Les codes de démarches sont recoupés avec ceux autorisés par Django avant l'analyse ; une orientation avec un code non autorisé est rejetée.
- Les réponses JSON sont décodées puis validées avec **Pydantic**. Les données utilisateur et les sources sont traitées comme des informations à analyser, et non comme des instructions à exécuter.
- Un résultat `SOURCES_INSUFFISANTES` peut signaler une demande hors couverture ou une condition non vérifiée, pas nécessairement une panne de la recherche.
- Les résultats sont indicatifs : les services administratifs restent compétents pour vérifier les justificatifs, la situation juridique et les conditions d'une démarche.

L'API Groq applique des limites de débit et de consommation. Dans `llm_service.py`, une erreur **429** peut entraîner **une seule nouvelle tentative**, uniquement si le délai conseillé ne dépasse pas 15 secondes ; sinon l'appel échoue sans attente prolongée. Les erreurs temporaires d'analyse sont exposées par `/analyze` avec un code HTTP `503`.

## Tests et diagnostics

Les scripts suivants sont présents dans `scripts/` :

```bash
# Classification du domaine (appels Groq)
python -m scripts.test_identification_domaine

# Analyse par Groq avec contexte RAG
python -m scripts.test_orientation_llm

# Diagnostic de reformulation et recherche RAG
python -m scripts.test_requete_rag_ia

# Vérification des sources pour une perte de passeport (sans appel Groq)
python -m scripts.test_sources_passeport
```

Un script historique de tests de parcours complets est également présent : `scripts/test_mvp_full_flow.py`. Ses scénarios et ses codes doivent être vérifiés avant de le considérer comme une validation du périmètre actuel.

Certains diagnostics effectuent des appels payants ou soumis aux quotas Groq ; les lancer avec une clé et un quota disponibles. Les diagnostics RAG nécessitent que les sources aient déjà été indexées.

## Docker

Le dépôt comprend un `Dockerfile` qui :

- utilise `python:3.12-slim` ;
- installe **FFmpeg** et **PyTorch CPU** ;
- installe les dépendances de `requirements-docker.txt` ;
- expose le port **8001** ;
- démarre Uvicorn sur `0.0.0.0:8001`.

Pour construire l'image depuis la racine du dépôt :

```bash
docker build -t admiguide-ai .
```

Exemple de démarrage autonome avec clé Groq provenant du fichier `.env` :

```bash
docker run --rm -p 8001:8001 --env-file .env admiguide-ai
```

**Attention :** `data/chroma/` n'est pas inclus dans l'image par défaut lorsque le dossier est exclu du contexte Docker. Pour utiliser le RAG dans un conteneur autonome, indexer les sources dans l'environnement concerné et conserver la base dans un volume persistant adapté. L'orchestration avec Django et MySQL relève du dépôt de déploiement AdmiGuide.

## Dépôts associés

- [AdmiGuide Frontend](https://github.com/AdmiGuide/admiguide-frontend) — application Angular et saisie vocale côté navigateur.
- [AdmiGuide Backend](https://github.com/AdmiGuide/admiguide-backend) — API Django REST Framework, comptes, référentiel, suivi et signalements.

## Développeuse

**Dado Watt**
