from pathlib import Path

# Service chargé de transformer les fichiers en sources administratives.
from app.services.source_parser_service import parse_sources_file

# Service chargé d'indexer les sources dans ChromaDB.
from app.services.ingestion_service import get_ingestion_service


# Dossier principal contenant les sources administratives.
SOURCES_DIR = Path("data/sources")


def get_domaine(file_path: Path) -> str:
    """
    Récupère le domaine à partir du premier sous-dossier.

    Exemple :
    data/sources/passeport/france.txt
    -> PASSEPORT
    """
    chemin_relatif = file_path.relative_to(SOURCES_DIR)

    # Une source doit être rangée dans un dossier de domaine.
    if len(chemin_relatif.parts) < 2:
        raise ValueError(
            f"Le fichier {file_path} doit être placé "
            "dans un sous-dossier de domaine."
        )

    return chemin_relatif.parts[0].upper()


def main():
    ingestion = get_ingestion_service()

    total_sources = 0
    total_chunks = 0

    # Recherche automatiquement tous les fichiers .txt.
    fichiers_sources = sorted(SOURCES_DIR.rglob("*.txt"))

    if not fichiers_sources:
        raise ValueError(
            f"Aucun fichier source trouvé dans {SOURCES_DIR}."
        )

    # Parcourt et indexe chaque fichier.
    for file_path in fichiers_sources:
        domaine = get_domaine(file_path)

        sources = parse_sources_file(
            file_path=str(file_path),
            domaine=domaine,
        )

        total_sources += len(sources)

        # Indexe chaque source séparément pour garder sa traçabilité.
        for source in sources:
            nombre_chunks = ingestion.ingest_source(source)
            total_chunks += nombre_chunks

            print(
                f"{source.source_id} : "
                f"{nombre_chunks} chunk(s)"
            )

    # Affiche le résumé global de l'ingestion.
    print(
        f"\n{total_sources} source(s) indexée(s), "
        f"{total_chunks} chunk(s) au total."
    )


# Lance le script uniquement lorsqu'il est exécuté directement.
if __name__ == "__main__":
    main()