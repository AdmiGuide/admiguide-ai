"""
Test ciblé du domaine FONCIER.

Ce script vérifie :
- la régularisation par voie de bail ;
- l'acquisition d'un bien déjà sous titre foncier ;
- une situation foncière trop vague ;
- une transformation de bail en titre foncier,
  qui n'est pas couverte par les sources du MVP.

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


# Codes autorisés pour le domaine FONCIER.
MVP_DEMARCHE_CODES = [
    "REGULARISATION_BAIL",
    "ACQUISITION_MUTATION_TITRE_FONCIER",
]


TESTS = [
    {
        "nom": "Régularisation par voie de bail",
        "situation": (
            "J'occupe un terrain qui dépend du domaine privé de l'État "
            "et je souhaite obtenir un bail pour régulariser ma situation."
        ),
        "reponses": [],
        "statut_attendu": "ORIENTATION",
        "code_attendu": "REGULARISATION_BAIL",
    },
    {
        "nom": "Acquisition d'un bien sous titre foncier",
        "situation": (
            "Je souhaite acheter un terrain appartenant à un particulier. "
            "Le terrain possède déjà un titre foncier et je veux que "
            "le bien soit inscrit à mon nom après l'achat."
        ),
        "reponses": [],
        "statut_attendu": "ORIENTATION",
        "code_attendu": (
            "ACQUISITION_MUTATION_TITRE_FONCIER"
        ),
    },
    {
        "nom": "Situation foncière à préciser",
        "situation": (
            "J'ai un terrain au Sénégal et je souhaite "
            "régulariser ma situation."
        ),
        "reponses": [],
        "statut_attendu": "PRECISIONS_REQUISES",
        "question_attendue": (
            "Que souhaitez-vous faire concernant ce terrain ou ce bien ?"
        ),
    },
    {
        "nom": "Transformation bail en titre foncier non couverte",
        "situation": (
            "J'ai déjà un bail sur mon terrain et je souhaite "
            "le transformer en titre foncier."
        ),
        "reponses": [],
        "statut_attendu": "SOURCES_INSUFFISANTES",
    },
]


async def main() -> None:
    service = get_orientation_service()
    resultats = []

    print("\nTEST DU DOMAINE FONCIER\n")

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
                    "verdict": (
                        "OK"
                        if ok
                        else "A_VERIFIER"
                    ),
                    "resultat_complet": data,
                }

            # -------------------------------------------------
            # Cas PRECISIONS_REQUISES
            # -------------------------------------------------
            elif statut_attendu == "PRECISIONS_REQUISES":
                questions = data.get("questions", [])

                textes_questions = [
                    question.get("texte", "")
                    for question in questions
                ]

                question_attendue = test[
                    "question_attendue"
                ]

                ok = (
                    statut_recu
                    == "PRECISIONS_REQUISES"
                    and question_attendue
                    in textes_questions
                )

                item = {
                    "nom": test["nom"],
                    "statut_recu": statut_recu,
                    "statut_attendu": statut_attendu,
                    "question_attendue": (
                        question_attendue
                    ),
                    "questions_recues": (
                        textes_questions
                    ),
                    "verdict": (
                        "OK"
                        if ok
                        else "A_VERIFIER"
                    ),
                    "resultat_complet": data,
                }

            # -------------------------------------------------
            # Cas SOURCES_INSUFFISANTES
            # -------------------------------------------------
            else:
                ok = (
                    statut_recu
                    == "SOURCES_INSUFFISANTES"
                )

                item = {
                    "nom": test["nom"],
                    "statut_recu": statut_recu,
                    "statut_attendu": statut_attendu,
                    "message_recu": data.get(
                        "message"
                    ),
                    "verdict": (
                        "OK"
                        if ok
                        else "A_VERIFIER"
                    ),
                    "resultat_complet": data,
                }

        except Exception as exc:
            item = {
                "nom": test["nom"],
                "statut_recu": None,
                "statut_attendu": (
                    test["statut_attendu"]
                ),
                "verdict": "ERREUR",
                "erreur": (
                    f"{type(exc).__name__}: {exc}"
                ),
            }

        resultats.append(item)

        print("=" * 70)
        print(test["nom"].upper())
        print("=" * 70)

        print(
            "Statut reçu :",
            item.get("statut_recu"),
        )

        print(
            "Statut attendu :",
            item.get("statut_attendu"),
        )

        if test["statut_attendu"] == "ORIENTATION":
            print(
                "Code reçu :",
                item.get(
                    "demarche_code_recu"
                ),
            )

            print(
                "Code attendu :",
                item.get(
                    "demarche_code_attendu"
                ),
            )

        elif (
            test["statut_attendu"]
            == "PRECISIONS_REQUISES"
        ):
            print(
                "Questions reçues :",
                item.get(
                    "questions_recues"
                ),
            )

            print(
                "Question attendue :",
                item.get(
                    "question_attendue"
                ),
            )

        else:
            print(
                "Message reçu :",
                item.get("message_recu"),
            )

        print(
            "Verdict :",
            item["verdict"],
        )

        # Pause pour limiter les erreurs HTTP 429 de Groq.
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
    print(
        "scripts/test_mvp_full_flow_results.json"
    )


if __name__ == "__main__":
    asyncio.run(main())