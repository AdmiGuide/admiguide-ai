# Service chargé de transformer le fichier en sources administratives.
from app.services.source_parser_service import parse_sources_file

# Service chargé d'indexer les sources dans ChromaDB.
from app.services.ingestion_service import get_ingestion_service


# Fichier contenant les sources liées au domaine passeport.
SOURCE_FILE = "data/sources/passeport.txt"


def main():
    # Transforme les différents blocs du fichier en sources administratives.
    sources = parse_sources_file(
        file_path=SOURCE_FILE,
        domaine="PASSEPORT",
    )

    ingestion = get_ingestion_service()
    total_chunks = 0

    # Indexe chaque source séparément afin de conserver sa traçabilité.
    for source in sources:
        nombre_chunks = ingestion.ingest_source(source)
        total_chunks += nombre_chunks

        print(
            f"{source.source_id} : "
            f"{nombre_chunks} chunk(s)"
        )

    # Affiche un résumé de l'ingestion.
    print(
        f"\n{len(sources)} source(s) indexée(s), "
        f"{total_chunks} chunk(s) au total."
    )


# Lance le script uniquement lorsqu'il est exécuté directement.
if __name__ == "__main__":
    main()