"""
Test final du passage PRECISIONS_REQUISES -> ORIENTATION.

Ce script teste uniquement le deuxième tour des 4 démarches MVP,
car le premier tour a déjà été validé.

À placer dans :
    admiguide-ai/scripts/test_mvp_full_flow.py

À lancer :
    python scripts/test_mvp_full_flow.py
"""

import asyncio
import json
import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
os.chdir(ROOT_DIR)
sys.path.insert(0, str(ROOT_DIR))

from app.services.orientation_service import get_orientation_service


MVP_DEMARCHE_CODES = [
    "REMPLACEMENT_PASSEPORT_PERDU",
    "RETOUR_EFFETS_PERSONNELS",
    "NAISSANCE_ETRANGER",
    "DECES_FONCTIONNAIRE",
]


TESTS = [
    {
        "nom": "Passeport perdu",
        "situation": (
            "J’ai perdu mon passeport sénégalais. "
            "Je voudrais savoir par où commencer pour le remplacer."
        ),
        "pays_application": "SN",
        "reponses": [
            {
                "texte_question": "Avez-vous déjà déclaré la perte ?",
                "contenu": "Oui, j’ai une déclaration",
            }
        ],
        "code_attendu": "REMPLACEMENT_PASSEPORT_PERDU",
    },
    {
        "nom": "Retour définitif",
        "situation": (
            "Je suis ressortissante sénégalaise, je vis à l’étranger "
            "et je prépare mon retour définitif au Sénégal."
        ),
        "pays_application": "SN",
        "reponses": [
            {
                "texte_question": "Qu’avez-vous prévu de ramener ?",
                "contenu": "Des effets personnels / biens mobiliers",
            }
        ],
        "code_attendu": "RETOUR_EFFETS_PERSONNELS",
    },
    {
        "nom": "Naissance à l'étranger",
        "situation": (
            "Mon enfant, de nationalité sénégalaise, est né en France. "
            "Je souhaite faire transcrire sa naissance auprès "
            "des autorités sénégalaises."
        ),
        "pays_application": "ETRANGER",
        "reponses": [
            {
                "texte_question": "Disposez-vous de l’acte de naissance local ?",
                "contenu": "Oui, je l’ai reçu",
            }
        ],
        "code_attendu": "NAISSANCE_ETRANGER",
    },
    {
        "nom": "Décès fonctionnaire",
        "situation": (
            "Un membre de ma famille, fonctionnaire en activité, "
            "est décédé. Je souhaite connaître les démarches "
            "pour les ayants droit."
        ),
        "pays_application": "SN",
        "reponses": [
            {
                "texte_question": "Quel est votre lien avec la personne décédée ?",
                "contenu": "Conjoint ou conjointe",
            }
        ],
        "code_attendu": "DECES_FONCTIONNAIRE",
    },
]


async def main() -> None:
    service = get_orientation_service()
    resultats = []

    print("\nTEST FINAL DES 4 PARCOURS MVP\n")

    for index, test in enumerate(TESTS):
        try:
            resultat = await service.analyze(
                situation=test["situation"],
                pays_application=test["pays_application"],
                demarche_codes=MVP_DEMARCHE_CODES,
                reponses=test["reponses"],
            )

            data = resultat.model_dump()

            statut = data.get("statut")
            code_recu = data.get("demarche_code")

            ok = (
                statut == "ORIENTATION"
                and code_recu == test["code_attendu"]
            )

            item = {
                "nom": test["nom"],
                "statut_recu": statut,
                "demarche_code_recu": code_recu,
                "demarche_code_attendu": test["code_attendu"],
                "verdict": "OK" if ok else "A_VERIFIER",
                "resultat_complet": data,
            }

        except Exception as exc:
            item = {
                "nom": test["nom"],
                "statut_recu": None,
                "demarche_code_recu": None,
                "demarche_code_attendu": test["code_attendu"],
                "verdict": "ERREUR",
                "erreur": f"{type(exc).__name__}: {exc}",
            }

        resultats.append(item)

        print("=" * 70)
        print(test["nom"].upper())
        print("=" * 70)
        print("Statut :", item["statut_recu"])
        print("Code reçu :", item["demarche_code_recu"])
        print("Code attendu :", item["demarche_code_attendu"])
        print("Verdict :", item["verdict"])

        if index < len(TESTS) - 1:
            await asyncio.sleep(5)

    fichier = ROOT_DIR / "scripts" / "test_mvp_full_flow_results.json"
    fichier.write_text(
        json.dumps(resultats, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("\nRésultats détaillés :")
    print("scripts/test_mvp_full_flow_results.json")


if __name__ == "__main__":
    asyncio.run(main())
