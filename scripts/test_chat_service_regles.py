"""Tests sans appels Groq pour les protections du chatbot contextuel.

Lancer depuis la racine admiguide-ai :
    python -m unittest discover -s tests -p 'test_chat_service_regles.py' -v
"""
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from app.services.chat_service import ChatService


def demande(question: str):
    return SimpleNamespace(
        question=question,
        situation="Je souhaite régulariser un terrain au Sénégal.",
        page="RESULTAT",
        domaine="FONCIER",
        demarche="Régularisation par voie de bail",
        terme_juridique=None,
        etapes=[],
        pieces_a_preparer=[],
        question_precision=None,
        historique=[],
        services_competents=[SimpleNamespace(
            nom="Bureau des Domaines territorialement compétent",
            administration="Direction générale des Impôts et des Domaines",
            model_dump=lambda: {"nom":"Bureau des Domaines territorialement compétent", "administration":"Direction générale des Impôts et des Domaines"},
        )],
    )


class ChatReglesTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        # Évite d'initialiser ChromaDB et Groq.
        self.chat = ChatService.__new__(ChatService)
        self.chat.retrieval = Mock()
        self.chat.retrieval.retrieve.return_value = []
        self.chat.retrieval.build_context_from_results.return_value = ""
        self.chat.llm = Mock()
        self.chat.llm.generate = AsyncMock(return_value="Un bail est un contrat permettant d'occuper un bien selon certaines conditions.")

    async def test_hors_sujet_sans_appel_ia(self):
        result = await self.chat.repondre(demande("C'est quoi la scalabilité ?"))
        self.assertIn("démarche administrative", result.reponse)
        self.assertEqual(result.sources, [])
        self.chat.llm.generate.assert_not_awaited()

    async def test_definition_administrative_acceptee(self):
        result = await self.chat.repondre(demande("Que signifie un bail ?"))
        self.assertIn("contrat", result.reponse)
        self.chat.llm.generate.assert_awaited_once()

    async def test_recherche_siege_dgid(self):
        d = demande("Où se trouve la Direction générale des Impôts et des Domaines ?")
        self.assertEqual(self.chat.cibler_service_web(d)[1], "SIEGE")
        self.assertIn("siège", self.chat.preparer_requete_web(d))

        async def faux_generate(**kwargs):
            kwargs["sources_web"].append({
                "titre": "DGID - Nous contacter",
                "url": "https://www.dgid.sn/contact",
                "extrait": "Nous contacter\nAdresse\n31, Rue de Thiong x Vincens, Dakar-Plateau\nTéléphone : ...",
            })
            return "Le siège se trouve à Dakar."

        self.chat.llm.generate = AsyncMock(side_effect=faux_generate)
        result = await self.chat.repondre(d)
        self.assertIn("31, Rue de Thiong", result.reponse)
        self.assertEqual(
            (result.sources[0].url if hasattr(result.sources[0], "url") else result.sources[0]["url"]),
            "https://www.dgid.sn/contact",
        )
        self.chat.llm.generate.assert_awaited_once()

    async def test_bureau_non_confondu_avec_siege(self):
        d = demande("Où se trouve le bureau compétent pour mon terrain ?")
        self.assertEqual(self.chat.cibler_service_web(d)[1], "BUREAU")

        async def faux_generate(**kwargs):
            kwargs["sources_web"].append({
                "titre": "DGID - Nous contacter",
                "url": "https://www.dgid.sn/contact",
                "extrait": "Nous contacter\nAdresse\n31, Rue de Thiong x Vincens, Dakar-Plateau\n",
            })
            return "Le siège se trouve à Dakar."

        self.chat.llm.generate = AsyncMock(side_effect=faux_generate)
        result = await self.chat.repondre(d)
        self.assertIn("pas pu confirmer", result.reponse)
        self.assertNotIn("31, Rue", result.reponse)

    async def test_siege_sans_source_non_invente(self):
        d = demande("Où se trouve la DGID ?")
        self.chat.llm.generate = AsyncMock(return_value="31, Rue inventée, Dakar")
        result = await self.chat.repondre(d)
        self.assertNotIn("Rue inventée", result.reponse)
        self.assertIn("pas pu confirmer", result.reponse)


if __name__ == '__main__':
    unittest.main()
