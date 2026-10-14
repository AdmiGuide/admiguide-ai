"""
Tests de non-régression du parcours d'orientation AdmiGuide.

Ce script vérifie les domaines actuellement couverts par le MVP :

- PASSEPORT
  - première demande ;
  - renouvellement ;
  - perte ou vol ;
  - intention trop vague ;
  - pays émetteur du passeport non précisé.

- PENSIONS / DÉCÈS
  - fonctionnaire décédé en activité ;
  - fonctionnaire décédé après la retraite ;
  - situation du défunt à préciser ;
  - parcours après une réponse "Je ne sais pas".

- FONCIER
  - régularisation par voie de bail ;
  - acquisition d'un bien sous titre foncier ;
  - transformation d'un bail en titre foncier ;
  - intention foncière à préciser ;
  - transformation nécessitant des précisions.

À lancer depuis la racine de admiguide-ai :

    python -m scripts.test_mvp_full_flow
"""

import asyncio
import json
import os
import sys
from pathlib import Path


# ==========================================================
# CONFIGURATION DU PROJET
# ==========================================================

ROOT_DIR = Path(__file__).resolve().parents[1]

os.chdir(ROOT_DIR)

sys.path.insert(
    0,
    str(ROOT_DIR),
)


from app.services.orientation_service import (
    get_orientation_service,
)


# ==========================================================
# CODES DU MVP
# ==========================================================

MVP_DEMARCHE_CODES = [
    # Passeport.
    "DEMANDE_PASSEPORT_ORDINAIRE",
    "RENOUVELLEMENT_PASSEPORT",
    "PASSEPORT_PERDU_OU_VOLE",

    # Pensions / décès.
    "REVERSION_PENSION_CAPITAL_DECES_ACTIVITE",
    "REVERSION_PENSION_APRES_RETRAITE",

    # Foncier.
    "REGULARISATION_BAIL",
    "ACQUISITION_MUTATION_TITRE_FONCIER",
    "TRANSFORMATION_BAIL_EN_TITRE_FONCIER",
]


# Pause entre deux tests afin de limiter
# les erreurs 429 liées au quota Groq.
DELAI_ENTRE_TESTS = 20

# Si Groq refuse temporairement une requête,
# le test est retenté avant d'être considéré
# comme une véritable erreur.
NOMBRE_MAX_TENTATIVES = 3

DELAI_AVANT_NOUVELLE_TENTATIVE = 25


# ==========================================================
# CAS DE TEST
# ==========================================================

TESTS = [

    # ------------------------------------------------------
    # PASSEPORT
    # ------------------------------------------------------

    {
        "nom": "Passeport - Première demande",
        "situation": (
            "Je vis à Dakar et je souhaite demander "
            "un passeport sénégalais pour la première fois."
        ),
        "reponses": [],
        "statut_attendu": "ORIENTATION",
        "code_attendu": "DEMANDE_PASSEPORT_ORDINAIRE",
    },

    {
        "nom": "Passeport - Renouvellement",
        "situation": (
            "Mon passeport sénégalais est expiré "
            "et je souhaite le renouveler à Dakar."
        ),
        "reponses": [],
        "statut_attendu": "ORIENTATION",
        "code_attendu": "RENOUVELLEMENT_PASSEPORT",
    },

    {
        "nom": "Passeport - Perte",
        "situation": (
            "J'ai perdu mon passeport sénégalais "
            "à Dakar et je souhaite le refaire."
        ),
        "reponses": [],
        "statut_attendu": "ORIENTATION",
        "code_attendu": "PASSEPORT_PERDU_OU_VOLE",
    },

    {
        "nom": "Passeport - Intention à préciser",
        "situation": (
            "Je réside à Dakar et je souhaite faire "
            "des démarches pour mon passeport sénégalais."
        ),
        "reponses": [],
        "statut_attendu": "PRECISIONS_REQUISES",
        "question_attendue": (
            "Quelle est votre situation concernant "
            "votre passeport sénégalais ?"
        ),
        "options_attendues": [
            (
                "Je souhaite demander un passeport "
                "pour la première fois"
            ),
            "Je souhaite renouveler mon passeport",
            "J'ai perdu ou on m'a volé mon passeport",
            "Autre situation",
        ],
    },

    {
        "nom": "Passeport - Pays émetteur inconnu",
        "situation": (
            "J'ai perdu mon passeport "
            "et je vis à Dakar."
        ),
        "reponses": [],
        "statut_attendu": "PRECISIONS_REQUISES",
        "question_attendue": (
            "S'agit-il d'un passeport sénégalais ?"
        ),
        "options_attendues": [
            "Oui",
            "Non",
            "Je ne sais pas",
        ],
    },


    # ------------------------------------------------------
    # PENSIONS / DÉCÈS
    # ------------------------------------------------------

    {
        "nom": "Décès - Fonctionnaire en activité",
        "situation": (
            "Un membre de ma famille est décédé. "
            "Il était fonctionnaire en activité "
            "au moment de son décès."
        ),
        "reponses": [],
        "statut_attendu": "ORIENTATION",
        "code_attendu": (
            "REVERSION_PENSION_CAPITAL_DECES_ACTIVITE"
        ),
    },

    {
        "nom": "Décès - Fonctionnaire à la retraite",
        "situation": (
            "Un membre de ma famille est décédé. "
            "Il était fonctionnaire à la retraite "
            "au moment de son décès."
        ),
        "reponses": [],
        "statut_attendu": "ORIENTATION",
        "code_attendu": (
            "REVERSION_PENSION_APRES_RETRAITE"
        ),
    },

    {
        "nom": "Décès - Situation à préciser",
        "situation": (
            "Un membre de ma famille est décédé "
            "et je souhaite connaître les démarches "
            "pour les ayants droit."
        ),
        "reponses": [],
        "statut_attendu": "PRECISIONS_REQUISES",
        "question_attendue": (
            "Au moment de son décès, quelle était "
            "la situation de la personne ?"
        ),
        "options_attendues": [
            "Elle était fonctionnaire en activité",
            "Elle était fonctionnaire à la retraite",
            "Elle n'était pas fonctionnaire",
            "Je ne sais pas",
        ],
    },

    {
        "nom": "Décès - Je ne sais pas",
        "situation": (
            "Un membre de ma famille est décédé "
            "et je souhaite connaître les démarches "
            "pour les ayants droit."
        ),
        "reponses": [
            {
                "texte_question": (
                    "Au moment de son décès, quelle était "
                    "la situation de la personne ?"
                ),
                "contenu": "Je ne sais pas",
            }
        ],
        "statut_attendu": "PRECISIONS_REQUISES",
        "question_attendue": (
            "Au moment de son décès, la personne "
            "percevait-elle déjà une pension de retraite ?"
        ),
        "options_attendues": [
            "Oui",
            "Non",
            "Je ne sais pas",
        ],
    },


    # ------------------------------------------------------
    # FONCIER
    # ------------------------------------------------------

    {
        "nom": "Foncier - Régularisation par bail",
        "situation": (
            "J'occupe un terrain qui dépend du domaine "
            "privé de l'État et je souhaite obtenir "
            "un bail pour régulariser ma situation."
        ),
        "reponses": [],
        "statut_attendu": "ORIENTATION",
        "code_attendu": "REGULARISATION_BAIL",
    },

    {
        "nom": "Foncier - Acquisition sous titre foncier",
        "situation": (
            "Je souhaite acheter un terrain appartenant "
            "à un particulier. Le terrain possède déjà "
            "un titre foncier et je souhaite que le bien "
            "soit inscrit à mon nom après l'achat."
        ),
        "reponses": [],
        "statut_attendu": "ORIENTATION",
        "code_attendu": (
            "ACQUISITION_MUTATION_TITRE_FONCIER"
        ),
    },

    {
        "nom": "Foncier - Transformation bail en titre foncier",
        "situation": (
            "J'ai un bail sur un terrain à usage d'habitation "
            "à Dakar. La mise en valeur prévue dans le bail "
            "a été réalisée et je souhaite transformer "
            "ce bail en titre foncier."
        ),
        "reponses": [],
        "statut_attendu": "ORIENTATION",
        "code_attendu": (
            "TRANSFORMATION_BAIL_EN_TITRE_FONCIER"
        ),
    },

    {
        "nom": "Foncier - Intention à préciser",
        "situation": (
            "J'ai un terrain au Sénégal "
            "et je souhaite régulariser ma situation."
        ),
        "reponses": [],
        "statut_attendu": "PRECISIONS_REQUISES",
        "question_attendue": (
            "Que souhaitez-vous faire concernant "
            "ce terrain ou ce bien ?"
        ),
        "options_attendues": [
            "Obtenir un bail pour un terrain",
            (
                "Acheter un bien qui possède déjà "
                "un titre foncier"
            ),
            "Transformer un bail en titre foncier",
            "Autre situation",
            "Je ne sais pas",
        ],
    },

    {
        "nom": "Foncier - Transformation bail à préciser",
        "situation": (
            "J'ai déjà un bail sur mon terrain "
            "et je souhaite le transformer "
            "en titre foncier."
        ),
        "reponses": [],
        "statut_attendu": "PRECISIONS_REQUISES",
        "question_attendue": (
            "Le terrain concerné est-il destiné "
            "à l'habitation ?"
        ),
        "options_attendues": [
            "Oui",
            "Non",
            "Je ne sais pas",
        ],
    },
]


# ==========================================================
# VÉRIFICATION D'UN RÉSULTAT
# ==========================================================

def verifier_resultat(
    test: dict,
    data: dict,
) -> tuple[bool, dict]:

    statut_recu = data.get(
        "statut"
    )

    statut_attendu = test[
        "statut_attendu"
    ]

    details = {
        "statut_recu": statut_recu,
        "statut_attendu": statut_attendu,
    }


    # ------------------------------------------------------
    # ORIENTATION
    # ------------------------------------------------------

    if statut_attendu == "ORIENTATION":

        code_recu = data.get(
            "demarche_code"
        )

        code_attendu = test[
            "code_attendu"
        ]

        details[
            "demarche_code_recu"
        ] = code_recu

        details[
            "demarche_code_attendu"
        ] = code_attendu

        ok = (
            statut_recu == "ORIENTATION"
            and code_recu == code_attendu
        )

        return ok, details


    # ------------------------------------------------------
    # PRECISIONS_REQUISES
    # ------------------------------------------------------

    if (
        statut_attendu
        == "PRECISIONS_REQUISES"
    ):

        questions = data.get(
            "questions",
            [],
        )

        question_attendue = test[
            "question_attendue"
        ]

        options_attendues = test.get(
            "options_attendues"
        )

        question_trouvee = None

        for question in questions:

            if (
                question.get("texte")
                == question_attendue
            ):
                question_trouvee = question
                break

        details[
            "question_attendue"
        ] = question_attendue

        details[
            "questions_recues"
        ] = [
            question.get("texte")
            for question in questions
        ]

        if question_trouvee:

            details[
                "options_recues"
            ] = question_trouvee.get(
                "options",
                [],
            )

        ok = (
            statut_recu
            == "PRECISIONS_REQUISES"
            and question_trouvee
            is not None
        )

        # Vérifie également les options lorsque
        # le test en attend explicitement.
        if (
            ok
            and options_attendues
            is not None
        ):

            ok = (
                question_trouvee.get(
                    "options",
                    [],
                )
                == options_attendues
            )

        return ok, details


    # ------------------------------------------------------
    # SOURCES_INSUFFISANTES
    # ------------------------------------------------------

    if (
        statut_attendu
        == "SOURCES_INSUFFISANTES"
    ):

        details[
            "message_recu"
        ] = data.get(
            "message"
        )

        ok = (
            statut_recu
            == "SOURCES_INSUFFISANTES"
        )

        return ok, details


    return False, details


# ==========================================================
# APPEL IA AVEC NOUVELLE TENTATIVE
# ==========================================================

async def analyser_avec_retry(
    service,
    test: dict,
):
    """
    Lance un cas de test.

    Si le fournisseur IA est temporairement indisponible,
    le même test est retenté avant d'être considéré
    comme une erreur définitive.
    """

    derniere_erreur = None

    for tentative in range(
        1,
        NOMBRE_MAX_TENTATIVES + 1,
    ):

        try:

            return await service.analyze(
                situation=test["situation"],
                demarche_codes=MVP_DEMARCHE_CODES,
                reponses=test["reponses"],
            )

        except RuntimeError as exc:

            derniere_erreur = exc

            if (
                tentative
                == NOMBRE_MAX_TENTATIVES
            ):
                raise

            print(
                "\nService IA temporairement indisponible."
            )

            print(
                f"Nouvelle tentative "
                f"{tentative + 1}/"
                f"{NOMBRE_MAX_TENTATIVES} "
                f"dans "
                f"{DELAI_AVANT_NOUVELLE_TENTATIVE} secondes..."
            )

            await asyncio.sleep(
                DELAI_AVANT_NOUVELLE_TENTATIVE
            )

    raise derniere_erreur


# ==========================================================
# EXÉCUTION DES TESTS
# ==========================================================

async def main() -> None:

    service = (
        get_orientation_service()
    )

    resultats = []

    total = len(TESTS)

    print(
        "\nTESTS DE NON-RÉGRESSION ADMIGUIDE"
    )

    print(
        f"{total} cas à exécuter.\n"
    )


    for index, test in enumerate(
        TESTS,
        start=1,
    ):

        print("=" * 72)

        print(
            f"[{index}/{total}] "
            f"{test['nom'].upper()}"
        )

        print("=" * 72)


        try:

            resultat = (
                await analyser_avec_retry(
                    service,
                    test,
                )
            )

            data = (
                resultat.model_dump()
            )

            ok, details = (
                verifier_resultat(
                    test,
                    data,
                )
            )

            item = {
                "nom": test["nom"],
                **details,
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
                    test[
                        "statut_attendu"
                    ]
                ),
                "verdict": "ERREUR",
                "erreur": (
                    f"{type(exc).__name__}: "
                    f"{exc}"
                ),
            }


        resultats.append(
            item
        )


        print(
            "Statut reçu :",
            item.get(
                "statut_recu"
            ),
        )

        print(
            "Statut attendu :",
            item.get(
                "statut_attendu"
            ),
        )


        if (
            test["statut_attendu"]
            == "ORIENTATION"
        ):

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

            if (
                "options_attendues"
                in test
            ):

                print(
                    "Options reçues :",
                    item.get(
                        "options_recues"
                    ),
                )

                print(
                    "Options attendues :",
                    test[
                        "options_attendues"
                    ],
                )


        elif (
            test["statut_attendu"]
            == "SOURCES_INSUFFISANTES"
        ):

            print(
                "Message reçu :",
                item.get(
                    "message_recu"
                ),
            )


        if item.get("erreur"):

            print(
                "Erreur :",
                item["erreur"],
            )


        print(
            "Verdict :",
            item["verdict"],
        )


        # Laisse le quota Groq se libérer
        # avant le prochain test.
        if index < total:

            print(
                f"\nPause de "
                f"{DELAI_ENTRE_TESTS} secondes..."
            )

            await asyncio.sleep(
                DELAI_ENTRE_TESTS
            )


    # ======================================================
    # ENREGISTREMENT DU RAPPORT JSON
    # ======================================================

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


    # ======================================================
    # RÉSUMÉ
    # ======================================================

    nombre_ok = sum(
        1
        for resultat in resultats
        if resultat["verdict"] == "OK"
    )

    nombre_a_verifier = sum(
        1
        for resultat in resultats
        if resultat["verdict"]
        == "A_VERIFIER"
    )

    nombre_erreurs = sum(
        1
        for resultat in resultats
        if resultat["verdict"]
        == "ERREUR"
    )


    print("\n" + "=" * 72)

    print(
        "RÉSUMÉ DES TESTS"
    )

    print("=" * 72)

    print(
        f"OK : {nombre_ok}/{total}"
    )

    print(
        "À vérifier :",
        nombre_a_verifier,
    )

    print(
        "Erreurs :",
        nombre_erreurs,
    )

    print(
        "\nRésultats détaillés :"
    )

    print(
        "scripts/"
        "test_mvp_full_flow_results.json"
    )


if __name__ == "__main__":
    asyncio.run(
        main()
    )