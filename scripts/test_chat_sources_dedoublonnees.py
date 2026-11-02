"""Tests unitaires de l'affichage des sources, sans requête Groq ni HTTP."""
import unittest

from app.services.chat_service import ChatService


class TestsSourcesAffichees(unittest.TestCase):
    def test_doublons_url_www_slash_et_tracking(self):
        sources = [
            {"titre": "Contact DGID", "url": "https://www.dgid.sn/contact"},
            {"titre": "Contact répété", "url": "https://dgid.sn/contact/?utm_source=chatbot"},
            {"titre": "DGID", "url": "https://www.dgid.sn/"},
        ]
        resultat = ChatService.selectionner_sources_publiques(sources)
        self.assertEqual(len(resultat), 1)
        self.assertEqual(resultat[0]["titre"], "Contact DGID")

    def test_contact_prioritaire_et_deux_sources_maximum(self):
        sources = [
            {"titre": "DGID", "url": "https://www.dgid.sn/"},
            {"titre": "Centre fiscal", "url": "https://www.dgid.sn/services/pikine"},
            {"titre": "Page de contact officielle", "url": "https://www.dgid.sn/contact"},
            {"titre": "Page de contact officielle", "url": "https://www.dgid.sn/contact/faq"},
        ]
        resultat = ChatService.selectionner_sources_publiques(sources)
        self.assertLessEqual(len(resultat), 2)
        self.assertEqual(resultat[0]["url"], "https://www.dgid.sn/contact")
        self.assertEqual(len({s["titre"] for s in resultat}), len(resultat))

    def test_sources_externes_refusees(self):
        sources = [
            {"titre": "Imitation DGID", "url": "https://dgid.sn.example.com/contact"},
            {"titre": "Réseau local", "url": "http://127.0.0.1/contact"},
            {"titre": "DGID officiel", "url": "https://www.dgid.sn/contact"},
        ]
        resultat = ChatService.selectionner_sources_publiques(sources)
        self.assertEqual(len(resultat), 1)
        self.assertEqual(resultat[0]["titre"], "DGID officiel")

    def test_source_unique_et_extrait_non_expose(self):
        sources = [{"titre": "Bureau des Domaines de Pikine",
                    "url": "https://www.dgid.sn/pikine", "extrait": "Texte privé"}]
        resultat = ChatService.selectionner_sources_publiques(sources)
        self.assertEqual(resultat, [{"titre": "Bureau des Domaines de Pikine",
                                    "url": "https://www.dgid.sn/pikine"}])


if __name__ == "__main__":
    unittest.main()
