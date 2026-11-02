"""Tests offline du suivi de localisation : sans requête Groq ni Internet.

Exécution : python -m unittest discover -s scripts -p 'test_chat_suivi_localite.py' -v
"""
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from app.services.chat_service import ChatService


def message(role, content):
    return SimpleNamespace(
        role=role, content=content,
        model_dump=lambda: {"role": role, "content": content},
    )


def demande(question, historique=None):
    return SimpleNamespace(
        question=question,
        situation='Je souhaite régulariser un terrain au Sénégal.',
        page='RESULTAT',
        domaine='FONCIER',
        demarche='Régularisation par voie de bail',
        terme_juridique=None,
        etapes=[],
        pieces_a_preparer=[],
        question_precision=None,
        historique=historique or [],
        services_competents=[SimpleNamespace(
            nom='Bureau des Domaines territorialement compétent',
            administration='Direction générale des Impôts et des Domaines',
            model_dump=lambda: {
                'nom': 'Bureau des Domaines territorialement compétent',
                'administration': 'Direction générale des Impôts et des Domaines',
            },
        )],
    )


def conversation(question='Mon terrain se trouve à Pikine.'):
    return demande(question, [
        message('user', 'Où se trouve le bureau des Domaines compétent pour mon terrain ?'),
        message('assistant',
                "Je n'ai pas pu confirmer l'adresse du bureau administratif compétent. "
                "Pouvez-vous préciser la localité concernée par votre démarche ?"),
    ])


class TestsSuiviLocalite(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.chat = ChatService.__new__(ChatService)
        self.chat.retrieval = Mock()
        self.chat.retrieval.retrieve.return_value = []
        self.chat.retrieval.build_context_from_results.return_value = ''
        self.chat.llm = Mock()
        self.chat.llm.generate = AsyncMock(return_value='')

    async def test_reponse_pikine_relance_recherche_ciblee(self):
        d = conversation()
        ancien, lieu = self.chat.reconnaitre_suivi_localisation(d)
        self.assertEqual(lieu, 'Pikine')
        self.assertIn('bureau des Domaines', ancien)

        async def simuler_groq(**kwargs):
            self.assertTrue(kwargs['utiliser_recherche_web'])
            self.assertIn('Bureau des Domaines', kwargs['user_prompt'])
            self.assertIn('Pikine', kwargs['user_prompt'])
            self.assertNotIn('Je souhaite régulariser', kwargs['user_prompt'])
            # Réponse volontairement dangereuse, comme observé en pratique.
            return 'Liste des étapes : 1. Mutation foncière 2. Acte notarié.'

        self.chat.llm.generate = AsyncMock(side_effect=simuler_groq)
        reponse = await self.chat.repondre(d)
        self.assertIn('Pour Pikine', reponse.reponse)
        self.assertIn("pas pu confirmer", reponse.reponse)
        self.assertNotIn('Mutation foncière', reponse.reponse)
        self.assertNotIn('acte notarié', reponse.reponse.lower())
        self.assertNotIn('préciser la localité', reponse.reponse)
        self.chat.retrieval.retrieve.assert_not_called()
        self.chat.llm.generate.assert_awaited_once()

    async def test_une_preuve_du_bureau_peut_etre_retenue(self):
        d = conversation('Pikine')

        async def simuler_groq(**kwargs):
            kwargs['sources_web'].append({
                'titre': 'DGID — annuaire institutionnel',
                'url': 'https://www.dgid.sn/centres',
                'extrait': 'Bureau des Domaines de Pikine — quartier Golf à Pikine',
            })
            return 'Texte généré, sans valeur de preuve'

        self.chat.llm.generate = AsyncMock(side_effect=simuler_groq)
        reponse = await self.chat.repondre(d)
        self.assertIn('Bureau des Domaines de Pikine', reponse.reponse)
        self.assertIn('quartier Golf', reponse.reponse)
        self.assertEqual(len(reponse.sources), 1)

    async def test_csf_ne_prouve_pas_adresse_bureau_domaines(self):
        d = conversation('À Pikine')

        async def simuler_groq(**kwargs):
            kwargs['sources_web'].append({
                'titre': 'DGID — centres fiscaux',
                'url': 'https://www.dgid.sn/centres',
                'extrait': 'Centre des services fiscaux de Pikine : quartier Golf',
            })
            return 'Bureau des Domaines de Pikine, adresse certaine.'

        self.chat.llm.generate = AsyncMock(side_effect=simuler_groq)
        reponse = await self.chat.repondre(d)
        self.assertIn('pas pu confirmer', reponse.reponse)
        self.assertNotIn('adresse certaine', reponse.reponse)

    async def test_ne_pas_reprendre_historique_sans_question_de_localite(self):
        d = demande('Mon terrain se trouve à Pikine.', [
            message('user', 'Quels documents préparer ?'),
            message('assistant', 'Je peux aider à comprendre votre démarche.'),
        ])
        self.assertIsNone(self.chat.reconnaitre_suivi_localisation(d))
        self.chat.llm.generate = AsyncMock(return_value='Il faut confirmer le type de demande.')
        await self.chat.repondre(d)
        self.assertFalse(self.chat.llm.generate.await_args.kwargs.get('utiliser_recherche_web'))

    async def test_si_localite_deja_dans_question_ne_pas_redemander(self):
        d = demande('Où se trouve le bureau des Domaines pour mon terrain à Pikine ?')
        self.chat.llm.generate = AsyncMock(return_value='Liste de démarches non pertinente')
        reponse = await self.chat.repondre(d)
        self.assertIn('Pour Pikine', reponse.reponse)
        self.assertNotIn('préciser la localité', reponse.reponse)
        self.assertNotIn('Liste de démarches', reponse.reponse)

    async def test_localite_deja_presente_dans_situation(self):
        """Le chatbot réutilise Pikine sans redemander la localité."""

        d = demande(
            "Où se trouve le Bureau des Domaines compétent pour mon terrain ?"
        )
        d.situation = (
            "J'occupe un terrain situé à Pikine, au Sénégal. "
            "Je dispose d'une autorisation d'occupation."
        )

        async def simuler_groq(**kwargs):
            self.assertTrue(kwargs["utiliser_recherche_web"])
            self.assertIn("Bureau des Domaines", kwargs["user_prompt"])
            self.assertIn("Pikine", kwargs["user_prompt"])

            # Ne transmet pas la situation personnelle complète.
            self.assertNotIn("J'occupe un terrain", kwargs["user_prompt"])

            return "Adresse non vérifiée."

        self.chat.llm.generate = AsyncMock(side_effect=simuler_groq)

        reponse = await self.chat.repondre(d)

        self.assertIn("Pour Pikine", reponse.reponse)
        self.assertIn("pas pu confirmer", reponse.reponse)
        self.assertNotIn("préciser la localité", reponse.reponse)

        self.chat.llm.generate.assert_awaited_once()

    async def test_hors_sujet_preserve(self):
        reponse = await self.chat.repondre(conversation('C’est quoi la scalabilité ?'))
        self.assertIn('démarche administrative', reponse.reponse)
        self.chat.llm.generate.assert_not_awaited()


if __name__ == '__main__':
    unittest.main()
