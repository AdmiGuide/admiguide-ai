"""Teste l'identification d'une démarche par Groq + RAG, sans règles déterministes.

À copier dans admiguide-ai/scripts/test_orientation_llm.py.
Depuis le dossier racine avec le venv activé :
    python -m scripts.test_orientation_llm

N'appelle pas Django, n'écrit ni en base ni dans les sources, et ne modifie
aucun fichier de production. Deux appels Groq sont effectués au maximum.
"""

import asyncio

from app.services.llm_service import get_llm_service
from app.services.retrieval_service import get_retrieval_service
from app.services.prompt_service import build_system_prompt, build_user_prompt
from app.services.response_parser_service import parse_llm_response


CODES_PASSEPORT = [
    "DEMANDE_PASSEPORT_ORDINAIRE",
    "RENOUVELLEMENT_PASSEPORT",
    "PASSEPORT_PERDU_OU_VOLE",
]

SITUATION = (
    "J'ai perdu mon passeport à Dakar et je veux savoir "
    "comment en avoir un nouveau."
)
QUESTION_NATIONALITE = "S'agit-il d'un passeport sénégalais ?"


async def analyser(llm, system_prompt, situation, contexte, reponses):
    """Demande à Groq de produire un statut, en utilisant les sources RAG."""
    prompt = build_user_prompt(
        situation=situation,
        contexte=contexte,
        demarche_codes=CODES_PASSEPORT,
        reponses=reponses,
    )
    texte = await llm.generate(system_prompt=system_prompt, user_prompt=prompt)
    return parse_llm_response(texte, demarche_codes=CODES_PASSEPORT)


def afficher(resultat):
    print("Statut reçu :", resultat.statut)
    if resultat.statut == "ORIENTATION":
        print("Démarche :", resultat.demarche_code)
    elif resultat.statut == "PRECISIONS_REQUISES":
        for question in resultat.questions:
            print("Question :", question.texte)
            print("Options  :", ", ".join(question.options))
    else:
        print("Message :", resultat.message)


async def main():
    print("TEST ISOLÉ — IA + sources RAG, sans décisions métiers Python")
    print("Situation :", SITUATION, flush=True)

    # Étape précédente déjà validée : domaine PASSEPORT connu.
    # Ce test vérifie uniquement les décisions d'orientation de Groq.
    retrieval = get_retrieval_service()
    contenus = retrieval.retrieve(texte=SITUATION, domaine="PASSEPORT")

    if not contenus:
        print("ARRÊT : aucune source PASSEPORT indexée dans ChromaDB.")
        print("Vérifie l'ingestion locale des sources avant de continuer.")
        return

    print("\nSources retrouvées :")
    for source in contenus:
        print("-", source["source_id"], "—", source["source_titre"])

    contexte = retrieval.build_context_from_results(contenus)
    system_prompt = build_system_prompt(CODES_PASSEPORT)
    llm = get_llm_service()

    # 1. Information manquante : type de passeport.
    print("\nÉTAPE 1 — Sans réponse complémentaire", flush=True)
    premier = await analyser(llm, system_prompt, SITUATION, contexte, [])
    afficher(premier)
    if premier.statut != "PRECISIONS_REQUISES":
        print("ÉCHEC : on attend une précision sur le passeport sénégalais.")
        return

    questions = [q.texte for q in premier.questions]
    if QUESTION_NATIONALITE not in questions:
        print("ÉCHEC : la question attendue sur le pays émetteur est absente.")
        return

    print("OK : demande de nationalité du passeport détectée.")

    # 2. L'usager a confirmé : c'est un passeport sénégalais.
    # Le motif perte figure DÉJÀ dans sa situation.
    print("\nÉTAPE 2 — Après réponse « Oui »", flush=True)
    reponses = [{
        "texte_question": QUESTION_NATIONALITE,
        "contenu": "Oui",
    }]
    second = await analyser(llm, system_prompt, SITUATION, contexte, reponses)
    afficher(second)

    succes = (
        second.statut == "ORIENTATION"
        and second.demarche_code == "PASSEPORT_PERDU_OU_VOLE"
    )
    print("\nBILAN :", "SUCCÈS" if succes else "À CORRIGER")
    if succes:
        print("L'IA a reconnu la perte sans reposer la question du motif.")
    else:
        print("Le comportement reçu doit être examiné avant toute modification.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as exc:
        print(f"\nERREUR pendant le test : {type(exc).__name__} : {exc}")
        raise SystemExit(1) from exc
