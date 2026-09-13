# Structure utilisée pour valider chaque source administrative.
from app.schemas.source import AdministrativeSource


# Lit un fichier contenant plusieurs sources et les transforme en objets Python.
def parse_sources_file(
    file_path: str,
    domaine: str,
) -> list[AdministrativeSource]:
    # Lit tout le contenu du fichier texte.
    with open(file_path, "r", encoding="utf-8") as fichier:
        contenu = fichier.read()

    # Chaque bloc commence par la balise === SOURCE ===.
    blocs = contenu.split("=== SOURCE ===")

    sources = []

    for bloc in blocs:
        bloc = bloc.strip()

        # Ignore la partie vide située avant la première source.
        if not bloc:
            continue

        # Sépare les métadonnées du contenu administratif.
        if "CONTENU:" not in bloc:
            raise ValueError(
                "Une source ne contient pas la section CONTENU."
            )

        entete, texte = bloc.split("CONTENU:", 1)

        metadata = {}

        # Lit les lignes comme ID:, TITRE:, URL:, etc.
        for ligne in entete.splitlines():
            ligne = ligne.strip()

            if not ligne:
                continue

            cle, separateur, valeur = ligne.partition(":")

            if separateur:
                metadata[cle.strip()] = valeur.strip()

        # Vérifie que les informations indispensables sont présentes.
        champs_obligatoires = [
            "ID",
            "TITRE",
            "URL",
            "TYPE",
            "DATE_VERIFICATION",
            "PAYS_APPLICATION",
        ]

        for champ in champs_obligatoires:
            if not metadata.get(champ):
                raise ValueError(
                    f"Le champ {champ} manque dans une source."
                )

        # Transforme le bloc en AdministrativeSource validée par Pydantic.
        source = AdministrativeSource(
            source_id=metadata["ID"],
            texte=texte.strip(),
            domaine=domaine,
            pays_application=metadata["PAYS_APPLICATION"],
            source_titre=metadata["TITRE"],
            source_url=metadata["URL"],
            source_type=metadata["TYPE"],
            date_verification=metadata["DATE_VERIFICATION"],
        )

        sources.append(source)

    return sources