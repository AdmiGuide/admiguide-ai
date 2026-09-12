# Découpe un texte en morceaux adaptés à l'indexation.
def chunk_text(
    texte: str,
    max_chars: int = 1000,
) -> list[str]:
    # Sépare le texte en paragraphes et supprime les paragraphes vides.
    paragraphes = [
        paragraphe.strip()
        for paragraphe in texte.split("\n\n")
        if paragraphe.strip()
    ]

    chunks = []
    chunk_actuel = ""

    for paragraphe in paragraphes:
        # Essaie d'ajouter le paragraphe au chunk en cours.
        candidat = f"{chunk_actuel}\n\n{paragraphe}".strip()

        if len(candidat) <= max_chars:
            chunk_actuel = candidat
            continue

        # Sauvegarde le chunk actuel lorsqu'il est suffisamment rempli.
        if chunk_actuel:
            chunks.append(chunk_actuel)

        # Si le paragraphe tient seul, il devient le nouveau chunk.
        if len(paragraphe) <= max_chars:
            chunk_actuel = paragraphe
            continue

        # Découpe aussi les paragraphes exceptionnellement trop longs.
        mots = paragraphe.split()
        chunk_actuel = ""

        for mot in mots:
            candidat = f"{chunk_actuel} {mot}".strip()

            if len(candidat) > max_chars and chunk_actuel:
                chunks.append(chunk_actuel)
                chunk_actuel = mot
            else:
                chunk_actuel = candidat

    # Ajoute le dernier morceau restant.
    if chunk_actuel:
        chunks.append(chunk_actuel)

    return chunks