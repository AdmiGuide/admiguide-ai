"""Régression : un service nommé par l'utilisateur ne doit pas être remplacé
par le service figurant dans l'orientation (tests sans appel API externe).
"""
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from app.services.chat_service import ChatService


def message(role, content):
    return SimpleNamespace(
        role=role,
        content=content,
        model_dump=lambda: {"role": role, "content": content},
    )


def demande(historique=None):
    return SimpleNamespace(
        question="Mon terrain se trouve à Pikine.",
        situation="Je souhaite régulariser mon terrain.",
        page="RESULTAT",
        domaine="FONCIER",
        demarche="Régularisation par voie de bail",
        terme_juridique=None,
        etapes=[],
        pieces_a_preparer=[],
        question_precision=None,
        historique=historique or [
            message("user", "Où se trouve le bureau des Domaines compétent pour mon terrain ?"),
            message("assistant", "Pouvez-vous préciser la localité concernée par votre démarche ?"),
        ],
        services_competents=[SimpleNamespace(
            nom="Conservation de la propriété et des droits fonciers",
            administration="Direction générale des Impôts et des Domaines",
            model_dump=lambda: {
                "nom": "Conservation de la propriété et des droits fonciers",
                "administration": "Direction générale des Impôts et des Domaines",
            },
        )],
    )


class TestPrioriteService(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.chat = ChatService.__new__(ChatService)
        self.chat.retrieval = Mock()
        self.chat.retrieval.retrieve.return_value = []
        self.chat.retrieval.build_context_from_results.return_value = ""
        self.chat.llm = Mock()
        self.chat.llm.generate = AsyncMock(return_value="")

    async def test_demande_explicite_prioritaire_sur_orientation(self):
        d = demande()
        cible = self.chat.cibler_service_web(
            d, "Où se trouve le bureau des Domaines compétent pour mon terrain ?"
        )
        self.assertEqual(cible, ("Bureau des Domaines", "BUREAU"))

        async def faux_generate(**kwargs):
            self.assertIn("Bureau des Domaines à Pikine", kwargs["user_prompt"])
            self.assertNotIn("Conservation de la propriété", kwargs["user_prompt"])
            return "Une liste de démarches hors sujet"

        self.chat.llm.generate = AsyncMock(side_effect=faux_generate)
        resultat = await self.chat.repondre(d)
        self.assertIn("Bureau des Domaines", resultat.reponse)
        self.assertNotIn("Conservation", resultat.reponse)
        self.assertNotIn("liste de démarches", resultat.reponse)
        self.assertNotIn("préciser la localité", resultat.reponse)

    async def test_preuve_conservation_ne_prouve_pas_bureau_domaines(self):
        d = demande()

        async def faux_generate(**kwargs):
            kwargs["sources_web"].append({
                "titre": "Annuaire institutionnel",
                "url": "https://www.dgid.sn/services",
                "extrait": "Conservation de la propriété et des droits fonciers de Pikine, quartier Golf",
            })
            return "Conservation foncière à Pikine"

        self.chat.llm.generate = AsyncMock(side_effect=faux_generate)
        resultat = await self.chat.repondre(d)
        self.assertIn("pas pu confirmer", resultat.reponse)
        self.assertIn("Bureau des Domaines", resultat.reponse)
        self.assertNotIn("Conservation", resultat.reponse)

    async def test_preuve_bureau_domaines_explicitement_identifie(self):
        d = demande()

        async def faux_generate(**kwargs):
            kwargs["sources_web"].append({
                "titre": "Annuaire institutionnel",
                "url": "https://www.dgid.sn/services",
                "extrait": "Bureau des Domaines de Pikine — quartier Golf à Pikine",
            })
            return "Texte libre ignoré"

        self.chat.llm.generate = AsyncMock(side_effect=faux_generate)
        resultat = await self.chat.repondre(d)
        self.assertIn("Bureau des Domaines de Pikine", resultat.reponse)
        self.assertIn("quartier Golf", resultat.reponse)
        self.assertIn("doit être confirmée", resultat.reponse)
        self.assertEqual(len(resultat.sources), 1)


if __name__ == "__main__":
    unittest.main()
