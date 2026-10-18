"""Compare deux recherches RAG pour une perte de passeport.

À placer dans le dossier scripts/ du projet admiguide-ai, puis exécuter :
    python -m scripts.test_sources_passeport

Lecture seule : aucun appel Groq, aucune modification de ChromaDB.
"""

from app.services.retrieval_service import get_retrieval_service

SOURCE_ATTENDUE = "PASSEPORT_DAKAR_PERTE_VOL_01"

REQUETES = [
    (
        "Description naturelle (recherche actuelle)",
        "J'ai perdu mon passeport à Dakar et je veux savoir comment en avoir un nouveau.",
    ),
    (
        "Recherche ciblée sur la démarche identifiée",
        "Passeport sénégalais perdu ou volé au Sénégal à Dakar : "
        "déclaration de perte et demande de nouveau passeport.",
    ),
]


def afficher_resultats(titre: str, texte: str) -> None:
    print(f"\n=== {titre} ===")
    print(f"Requête : {texte}")
    try:
        resultats = get_retrieval_service().retrieve(
            texte=texte,
            domaine="PASSEPORT",
            limit=8,
        )
    except Exception as exc:
        print(f"ERREUR : {type(exc).__name__} : {exc}")
        return

    if not resultats:
        print("Aucun document retrouvé dans la collection ChromaDB.")
        return

    rang_attendu = None
    rangs_par_source = {}
    for rang, resultat in enumerate(resultats, start=1):
        identifiant = resultat.get("source_id", "(identifiant absent)")
        rangs_par_source.setdefault(identifiant, []).append(rang)
        if identifiant == SOURCE_ATTENDUE and rang_attendu is None:
            rang_attendu = rang
        distance = resultat.get("distance")
        score = f"distance={distance:.4f}" if isinstance(distance, (int, float)) else "distance=?"
        print(f"{rang:>2}. {identifiant} ({score})")

    doublons = {
        source: rangs for source, rangs in rangs_par_source.items()
        if len(rangs) > 1
    }
    print(f"Sources uniques : {len(rangs_par_source)} sur {len(resultats)} morceaux retrouvés")
    print("Doublons par source : " + (str(doublons) if doublons else "aucun"))
    if rang_attendu:
        print(f"Source spécifique perte/vol retrouvée au rang {rang_attendu}.")
        if rang_attendu > 3:
            print("Attention : elle est absente du top 3 actuellement fourni au modèle.")
    else:
        print(f"ATTENTION : {SOURCE_ATTENDUE} est absente des {len(resultats)} premiers résultats.")


if __name__ == "__main__":
    print("DIAGNOSTIC RAG — PERTE DE PASSEPORT (sans appel Groq)")
    for titre, texte in REQUETES:
        afficher_resultats(titre, texte)
