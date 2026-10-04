"""
Test ciblé du domaine PENSIONS_DECES.

Ce script vérifie :
- le cas d'un fonctionnaire décédé en activité ;
- le cas d'un fonctionnaire décédé après la retraite ;
- le cas où la situation au moment du décès doit être précisée.

À lancer :
    python -m scripts.test_mvp_full_flow
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


# Codes de démarches autorisés pour le domaine PENSIONS_DECES.
MVP_DEMARCHE_CODES = [
    "REVERSION_PENSION_CAPITAL_DECES_ACTIVITE",
    "REVERSION_PENSION_APRES_RETRAITE",
]


TESTS = [
    {
        "nom": "Décès fonctionnaire en activité",
        "situation": (
            "Mon mari était fonctionnaire et travaillait encore "
            "dans l'administration au moment de son décès. "
            "Je souhaite savoir quelle démarche effectuer."
        ),
        "reponses": [],
        "statut_attendu": "ORIENTATION",
        "code_attendu": (
            "REVERSION_PENSION_CAPITAL_DECES_ACTIVITE"
        ),
    },
    {
        "nom": "Décès fonctionnaire après la retraite",
        "situation": (
            "Mon père était un ancien fonctionnaire déjà à la retraite "
            "lorsqu'il est décédé. Je souhaite savoir quelle démarche "
            "effectuer concernant sa pension."
        ),
        "reponses": [],
        "statut_attendu": "ORIENTATION",
        "code_attendu": "REVERSION_PENSION_APRES_RETRAITE",
    },
    {
        "nom": "Décès fonctionnaire - situation à préciser",
        "situation": (
            "Mon père était fonctionnaire et il est décédé. "
            "Je souhaite savoir quelle démarche effectuer "
            "concernant sa pension."
        ),
        "reponses": [],
        "statut_attendu": "PRECISIONS_REQUISES",
        "question_attendue": (
            "Au moment de son décès, la personne travaillait-elle "
            "encore comme fonctionnaire ou avait-elle déjà pris "
            "sa retraite ?"
        ),
    },
]


async def main() -> None:
    service = get_orientation_service()
    resultats = []

    print("\nTEST DU DOMAINE PENSIONS_DECES\n")

    for index, test in enumerate(TESTS):
        try:
            resultat = await service.analyze(
                situation=test["situation"],
                demarche_codes=MVP_DEMARCHE_CODES,
                reponses=test["reponses"],
            )

            data = resultat.model_dump()

            statut_recu = data.get("statut")
            statut_attendu = test["statut_attendu"]

            # -------------------------------------------------
            # Cas ORIENTATION
            # -------------------------------------------------
            if statut_attendu == "ORIENTATION":
                code_recu = data.get("demarche_code")
                code_attendu = test["code_attendu"]

                ok = (
                    statut_recu == "ORIENTATION"
                    and code_recu == code_attendu
                )

                item = {
                    "nom": test["nom"],
                    "statut_recu": statut_recu,
                    "statut_attendu": statut_attendu,
                    "demarche_code_recu": code_recu,
                    "demarche_code_attendu": code_attendu,
                    "verdict": "OK" if ok else "A_VERIFIER",
                    "resultat_complet": data,
                }

            # -------------------------------------------------
            # Cas PRECISIONS_REQUISES
            # -------------------------------------------------
            else:
                questions = data.get("questions", [])

                textes_questions = [
                    question.get("texte", "")
                    for question in questions
                ]

                question_attendue = test["question_attendue"]

                ok = (
                    statut_recu == "PRECISIONS_REQUISES"
                    and question_attendue in textes_questions
                )

                item = {
                    "nom": test["nom"],
                    "statut_recu": statut_recu,
                    "statut_attendu": statut_attendu,
                    "question_attendue": question_attendue,
                    "questions_recues": textes_questions,
                    "verdict": "OK" if ok else "A_VERIFIER",
                    "resultat_complet": data,
                }

        except Exception as exc:
            item = {
                "nom": test["nom"],
                "statut_recu": None,
                "statut_attendu": test["statut_attendu"],
                "verdict": "ERREUR",
                "erreur": f"{type(exc).__name__}: {exc}",
            }

        resultats.append(item)

        print("=" * 70)
        print(test["nom"].upper())
        print("=" * 70)

        print("Statut reçu :", item.get("statut_recu"))
        print("Statut attendu :", item.get("statut_attendu"))

        if test["statut_attendu"] == "ORIENTATION":
            print(
                "Code reçu :",
                item.get("demarche_code_recu"),
            )
            print(
                "Code attendu :",
                item.get("demarche_code_attendu"),
            )
        else:
            print(
                "Questions reçues :",
                item.get("questions_recues"),
            )
            print(
                "Question attendue :",
                item.get("question_attendue"),
            )

        print("Verdict :", item["verdict"])

        # Pause plus longue pour limiter les erreurs HTTP 429 de Groq.
        if index < len(TESTS) - 1:
            await asyncio.sleep(15)

    fichier = (
        ROOT_DIR
        / "scripts"
        / "test_mvp_full_flow_results.json"
    )

    fichier.write_text(
        json.dumps(
            resultats,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print("\nRésultats détaillés :")
    print("scripts/test_mvp_full_flow_results.json")


if __name__ == "__main__":
    asyncio.run(main())