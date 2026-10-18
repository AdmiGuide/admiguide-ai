"""Test isolé de l'identification des domaines d'AdmiGuide avec Groq.

À copier dans admiguide-ai/scripts/test_identification_domaine.py.
Depuis la racine du projet :
    python -m scripts.test_identification_domaine
    python -m scripts.test_identification_domaine --all

Ne modifie aucun fichier de production et n'utilise pas ChromaDB.
"""

import argparse
import asyncio
import json

from app.services.llm_service import get_llm_service


SYSTEM_PROMPT = """Tu identifies le domaine d'une demande adressée à AdmiGuide.
Comprends le sens de la phrase, même en français familier ou avec des fautes.
Choisis UNE valeur parmi : PASSEPORT, PENSION, FONCIER,
HORS_COUVERTURE, INDETERMINE.
- PASSEPORT : demander, refaire, renouveler ou remplacer un passeport.
- PENSION : pension ou sommes liées au décès d'un fonctionnaire.
- FONCIER : terrain, maison, achat ou papiers de propriété.
- HORS_COUVERTURE : autre domaine clairement identifiable.
- INDETERMINE : demande trop vague pour identifier un domaine.
Le domaine n'est PAS une démarche administrative et n'autorise pas
à fournir une orientation. N'invente aucune information manquante.
Réponds uniquement avec un objet JSON : {"domaine": "VALEUR"}.
"""

CAS = [
    (
        "Mon passport est expiré, j'aimerais savoir comment faire pour le renouveller.",
        "PASSEPORT",
    ),
    (
        "J'ai perdu mon passeport et je veux en avoir un nouveau.",
        "PASSEPORT",
    ),
    (
        "Mon père était fonctionnaire et il est décédé. Je voudrais savoir quoi faire.",
        "PENSION",
    ),
    (
        "J'occupe un terrain et je veux avoir des papiers à mon nom.",
        "FONCIER",
    ),
    (
        "Je souhaite ouvrir un restaurant à Dakar.",
        "HORS_COUVERTURE",
    ),
    (
        "J'ai besoin de faire des papiers.",
        "INDETERMINE",
    ),
]

VALIDES = {
    "PASSEPORT", "PENSION", "FONCIER", "HORS_COUVERTURE", "INDETERMINE"
}


async def tester(tous: bool = False) -> None:
    llm = get_llm_service()
    selection = CAS if tous else CAS[:2]
    reussis = 0

    for numero, (situation, attendu) in enumerate(selection, start=1):
        print(f"\nTEST {numero} — {situation}", flush=True)
        try:
            brut = await llm.generate(
                system_prompt=SYSTEM_PROMPT,
                user_prompt=f"Situation de l'usager : {situation}",
            )
            objet = json.loads(brut)
            obtenu = objet.get("domaine") if isinstance(objet, dict) else None
            if obtenu not in VALIDES:
                raise ValueError(f"Domaine ou format inattendu : {brut[:200]}")
        except (RuntimeError, ValueError, json.JSONDecodeError) as exc:
            print(f"ERREUR : {exc}", flush=True)
            continue

        succes = obtenu == attendu
        reussis += int(succes)
        print(f"Attendu : {attendu}", flush=True)
        print(f"Obtenu  : {obtenu}", flush=True)
        print("OK" if succes else "ÉCHEC", flush=True)

    print(f"\nBilan : {reussis}/{len(selection)} réussis", flush=True)
    print("Ce test valide uniquement la classification du domaine, pas l'orientation.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--all", action="store_true", help="Teste les six phrases au lieu des deux premières."
    )
    args = parser.parse_args()
    asyncio.run(tester(tous=args.all))
