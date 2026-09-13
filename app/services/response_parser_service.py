# Permet de lire une chaîne JSON reçue du modèle.
import json

# Schémas déjà utilisés par l'API AdmiGuide.
from app.schemas.orientation import (
    OrientationResponse,
    PrecisionsRequisesResponse,
    SourcesInsuffisantesResponse,
)


def parse_llm_response(
    reponse: str,
    demarche_codes: list[str],
):
    """Valide et transforme la réponse JSON du modèle."""

    # Transforme le JSON en dictionnaire Python.
    try:
        data = json.loads(reponse)
    except json.JSONDecodeError as exc:
        raise ValueError(
            "Le modèle n'a pas retourné un JSON valide."
        ) from exc

    statut = data.get("statut")

    if statut == "ORIENTATION":
        resultat = OrientationResponse.model_validate(data)

        # Refuse un code de démarche qui n'était pas autorisé.
        if resultat.demarche_code not in demarche_codes:
            raise ValueError(
                "Le modèle a retourné un code de démarche non autorisé."
            )

        return resultat

    if statut == "PRECISIONS_REQUISES":
        return PrecisionsRequisesResponse.model_validate(data)

    if statut == "SOURCES_INSUFFISANTES":
        return SourcesInsuffisantesResponse.model_validate(data)

    raise ValueError(
        "Le modèle a retourné un statut inconnu."
    )