"""Recherche d'informations publiques liées à une orientation AdmiGuide.

Composant isolé du dialogue pour permettre de tester les preuves et
les recherches de services sans modifier les règles de conversation.
"""
import asyncio
import re
import unicodedata
from urllib.parse import urlparse

from app.core.config import settings
from app.services.web_source_service import enrichir_sources_officielles, url_officielle
from app.schemas.chat import ChatRequest, ChatResponse


# Répertoires institutionnels officiels vérifiés. On stocke uniquement l'URL,
# jamais une adresse fixe : la réponse dépend de la page consultée.
PAGES_OFFICIELLES_DE_REFERENCE = {
    "direction des pensions": "https://www.budget.gouv.sn/directions-dgb/direction-des-pensions",
}

# Pages institutionnelles complémentaires en cas d'indisponibilité d'un lien.
# Seules les URL sont conservées, aucune adresse n'est codée en dur.
PAGES_OFFICIELLES_ALTERNATIVES = {
    "direction des pensions": (
        "https://budget.sec.gouv.sn/directions-dgb/direction-des-pensions",
        "https://budget.sec.gouv.sn/contacter-la-direction-generale-du-budget",
    ),
}


class ChatWebMixin:
    """Résolution prudente des informations pratiques (pas de nouvelle démarche)."""

    @staticmethod
    def normaliser(texte: str) -> str:
        """Normalise les accents et les majuscules."""
        texte = unicodedata.normalize("NFKD", texte.casefold())
        return "".join(c for c in texte if not unicodedata.combining(c))


    @staticmethod
    def extraire_message(message) -> tuple[str, str]:
        """Lit un message utilisateur/assistant sans en interpréter les consignes."""
        if isinstance(message, dict):
            role = message.get("role", "")
            contenu = message.get("content", "")
        else:
            role = getattr(message, "role", "")
            contenu = getattr(message, "content", "")
        return str(role).lower(), str(contenu or "")


    @classmethod
    def extraire_localite_courte(cls, message: str) -> str | None:
        """Accepte une réponse simple de lieu, sans données personnelles détaillées."""
        mot = r"[A-Za-zÀ-ÖØ-öø-ÿ][A-Za-zÀ-ÖØ-öø-ÿ'’-]*"
        nom = rf"({mot}(?:\s+{mot}){{0,3}})"
        introductions = (
            r"(?:mon|le|notre|ce)\s+terrain\s+(?:se trouve|se situe|est situé|est situe|est)\s+(?:à|au|en|dans la commune de|dans la ville de)\s+",
            r"(?:c['’]est|il est|je suis)\s+(?:à|au|en|dans)\s+",
            r"(?:à|au|en)\s+",
            r"(?=[A-ZÀ-ÖØ-Ý])",  # « Pikine », après une question de localité.
        )
        for introduction in introductions:
            trouve = re.fullmatch(
                introduction + nom + r"\s*[.!?]?\s*",
                message.strip(), flags=re.IGNORECASE,
            )
            if trouve:
                localite = trouve.group(1).strip()
                if len(localite) <= 60:
                    return localite
        return None


    @staticmethod
    def extraire_localite_de_situation(situation: str) -> str | None:
        """Extrait la localité du terrain depuis la situation initiale."""
        motif = (
            r"(?i:\bterrain\s+(?:est\s+)?"
            r"(?:situé|située|se trouve|se situe)\s+"
            r"(?:à|au|en)\s+)"
            r"([A-ZÀ-ÖØ-Ý][a-zà-öø-ÿ'’-]*"
            r"(?:[ -][A-ZÀ-ÖØ-Ý][a-zà-öø-ÿ'’-]*){0,2})"
        )

        correspondance = re.search(motif, situation)
        return correspondance.group(1) if correspondance else None


    @classmethod
    def reconnaitre_suivi_localisation(
        cls, demande: ChatRequest,
    ) -> tuple[str, str] | None:
        """Relie « Mon terrain se trouve à Pikine » à la recherche précédente.

        Exige : une demande antérieure d'adresse/bureau + une question de
        localité posée par l'assistant + une réponse courte de l'utilisateur.
        Ne transmet jamais l'historique au moteur de recherche.
        """
        historique = list(getattr(demande, "historique", []) or [])[-8:]
        if len(historique) < 2:
            return None
        role, derniere_reponse = cls.extraire_message(historique[-1])
        if role != "assistant":
            return None
        texte = cls.normaliser(derniere_reponse)
        if not any(mot in texte for mot in (
            "localite", "commune", "dans quelle ville",
            "ou se situe votre terrain", "ou se trouve votre terrain",
        )):
            return None
        localite = cls.extraire_localite_courte(demande.question)
        if not localite:
            return None

        # La demande immédiatement antérieure doit concerner la localisation
        # d'un bureau, et non une définition ou une nouvelle orientation.
        for ancien in reversed(historique[:-1]):
            ancien_role, ancienne_question = cls.extraire_message(ancien)
            if ancien_role == "user":
                texte_question = cls.normaliser(ancienne_question)
                if not any(expression in texte_question for expression in (
                    "ou se trouve", "ou est situe", "ou se situe",
                    "adresse", "localisation", "ou dois-je me rendre",
                    "quel bureau",
                )):
                    return None
                cible = cls.cibler_service_web(demande, ancienne_question)
                if cible and cible[1] == "BUREAU":
                    return ancienne_question, localite
                return None
        return None


    @classmethod
    def cibler_service_web(
        cls, demande: ChatRequest, question: str | None = None,
    ) -> tuple[str, str] | None:
        """Distingue le siège d'une administration du bureau d'une démarche.

        Retourne (nom public, 'SIEGE' ou 'BUREAU').
        Ne transmet pas la description personnelle au moteur de recherche.
        """
        question = cls.normaliser(
            question if question is not None else demande.question
        )
        bureau_demande = any(mot in question for mot in (
            "bureau ", "service competent", "bureau competent",
            "ou dois-je me rendre pour", "ou deposer",
            "pour mon dossier", "pour mon terrain",
        ))

        # Le service nommé explicitement par l'usager passe avant
        # le service rattaché à l'orientation (par exemple une conservation).
        # On ne déduit pas pour autant sa compétence pour le dossier.
        if re.search(r"\bbureau\s+des\s+domaines\b", question):
            return ("Bureau des Domaines", "BUREAU")

        # Un organisme explicitement cité par l'usager doit rester la cible
        # même si les services de l'orientation sont présentés autrement.
        if not bureau_demande and re.search(r"\bdirection\s+des\s+pensions\b", question):
            return ("Direction des Pensions", "SIEGE")

        # Noms d'administrations explicitement désignés.
        # La DGID est reconnue même lorsqu'elle n'est mentionnée
        # que par son sigle (cas rencontré dans nos tests).
        if not bureau_demande and (
            re.search(r"\bdgid\b", question)
            or "direction generale des impots et des domaines" in question
        ):
            return ("Direction générale des Impôts et des Domaines (DGID)", "SIEGE")

        services = [
            service for service in demande.services_competents
            if service.nom.strip()
        ]

        # Si la question nomme explicitement l'administration,
        # elle prévaut sur le bureau lié à la démarche.
        if not bureau_demande:
            for service in services:
                administration = (service.administration or "").strip()
                if len(administration) >= 8 and cls.normaliser(administration) in question:
                    return (administration, "SIEGE")

        # Une direction expressément nommée est recherchée comme organisme,
        # non comme un bureau territorial générique.
        if not bureau_demande:
            for service in services:
                nom = service.nom.strip()
                if (cls.normaliser(nom).startswith("direction ")
                        and cls.normaliser(nom) in question):
                    return (nom, "SIEGE")

        # Par défaut on conserve le bureau associé à l'orientation.
        if len(services) == 1:
            return (services[0].nom.strip(), "BUREAU")
        return None


    @classmethod
    def trouver_preuve_siege(
        cls, cible: str, sources_web: list[dict],
    ) -> dict | None:
        """Accepte une adresse seulement si la page officielle la relie au service.

        Une page d'annuaire peut contenir les adresses de plusieurs directions :
        une adresse trouvée ailleurs dans cette page ne constitue pas une preuve.
        """
        nom = cls.normaliser(cible).strip()
        dgid = "direction generale des impots et des domaines" in nom
        adresse_ligne = re.compile(
            r"(?i)^(?:adresse\s*:\s*)?(?:\d{1,4}\s*,?\s*)?"
            r"(?:rue|avenue|boulevard|bd|route|place)\s+[^\n\r]{5,115}$"
        )
        sources = sorted(
            sources_web,
            key=lambda s: not any(m in (s.get("url") or "").lower()
                                  for m in ("contact", "mentions-legales")),
        )
        for source in sources:
            url = source.get("url") or ""
            if not url_officielle(url):
                continue
            host = (urlparse(url).hostname or "").lower()
            if dgid and not (host == "dgid.sn" or host.endswith(".dgid.sn")):
                continue
            extrait = source.get("extrait") or ""
            if not extrait or (not dgid and nom not in cls.normaliser(extrait)):
                continue

            # Les résultats browser.open de Groq peuvent numéroter les lignes :
            # "L50: Direction des Pensions", "L51:", "L52: Rue ...".
            # Ces repères techniques ne font pas partie du contenu officiel.
            # Les retirer AVANT l'extraction, sans changer les règles de preuve.
            extrait = re.sub(r"(?m)^[ \t]*L\d{1,6}:[ \t]*", "", extrait)
            lignes = [ligne.strip() for ligne in extrait.splitlines() if ligne.strip()]
            # Une direction explicitement nommée, immédiatement suivie de son
            # adresse dans la page, constitue une preuve de localisation.
            if not dgid:
                for i, ligne in enumerate(lignes[:-1]):
                    if cls.normaliser(ligne).strip(" :-#") != nom:
                        continue
                    for suivant in lignes[i + 1:i + 3]:
                        # Ne jamais prendre l'adresse d'un autre service.
                        if re.match(r"(?i)^(?:direction|bureau|division)\s+(?:de|des|du|d')\b", suivant):
                            break
                        if adresse_ligne.fullmatch(suivant):
                            return {"titre": source.get("titre") or "Source institutionnelle",
                                    "url": url, "adresse": suivant.rstrip(". ")}
                # Un moteur de recherche peut aplatir plusieurs lignes d'une
                # fiche officielle en une seule phrase. On exige alors que
                # l'adresse suive immédiatement le NOM EXACT du service.
                # Ne jamais reprendre une adresse située ailleurs dans la page.
                aplati = re.sub(r"\s+", " ", extrait)
                contenu_normalise = cls.normaliser(aplati)
                for position in re.finditer(r"(?<!\w)" + re.escape(nom) + r"(?!\w)", contenu_normalise):
                    # 120 caractères au plus et uniquement des libellés de
                    # contact entre le nom du service et son adresse.
                    voisinage = aplati[position.end():position.end() + 120]
                    indice_aplati = re.match(
                        r"(?i)^[\s:#*|,;—–-]*"
                        r"(?:(?:contacts?|coordonn[ée]es|adresse)\s*[:—–-]?\s*){0,2}"
                        r"((?:\d{1,4}\s*,?\s*)?"
                        r"(?:rue|avenue|boulevard|bd|route|place)\s+[^.;\n\r]{5,105})",
                        voisinage,
                    )
                    if indice_aplati:
                        adresse = indice_aplati.group(1).strip(" *#,:;—–- ")
                        return {
                            "titre": source.get("titre") or "Source institutionnelle",
                            "url": url,
                            "adresse": adresse,
                        }

                # Dans les annuaires contenant plusieurs services, ne jamais
                # attribuer une adresse trouvée par une recherche globale.
                intitulés = sum(bool(re.match(
                    r"(?i)^(?:direction|bureau|division)\s+(?:de|des|du|d')\b",
                    ligne,
                )) for ligne in lignes)
                if intitulés > 1:
                    continue

            # Compatibilité avec les pages de contact dédiées :
            # « Adresse : Rue ... » ou « Siège » suivi d'une rue.
            indice = re.search(
                r"(?i)\b(?:adresse(?:\s+du\s+si[eè]ge)?|si[eè]ge)\s*:?\s*"
                r"((?:\d{1,4}\s*,?\s*)?(?:rue|avenue|boulevard|route|place)"
                r"\s+[^\n\r.;]{5,110})",
                extrait,
            )
            if indice:
                adresse = " ".join(indice.group(1).split()).strip(" ,")
                return {"titre": source.get("titre") or "Source institutionnelle",
                        "url": url, "adresse": adresse}
        return None


    @staticmethod
    def necessite_recherche_web(question: str) -> bool:
        """
        Détermine si la question nécessite une recherche
        Internet pour obtenir une information pratique.

        Une explication simple peut utiliser le RAG.
        """

        # Normalise le texte pour ignorer les accents
        # et les différences entre majuscules et minuscules.
        texte = unicodedata.normalize(
            "NFKD",
            question.casefold(),
        )

        texte = "".join(
            caractere
            for caractere in texte
            if not unicodedata.combining(caractere)
        )

        # Expressions liées aux informations pratiques
        # qui peuvent nécessiter une vérification en ligne.
        expressions = (
            "ou se trouve",
            "ou est situe",
            "ou se situe",
            "ou dois-je me rendre",
            "comment me rendre",
            "localisation",
            "adresse",
            "coordonnees",
            "telephone",
            "contacter",
            "contact",
            "horaire",
            "heures d'ouverture",
            "site officiel",
            "quel bureau",
            "quel consulat",
            "cout actuel",
            "tarif",
            "frais actuels",
            "delai actuel",
        )

        # Retourne True si la question contient
        # une expression nécessitant une recherche web.
        return any(
            expression in texte
            for expression in expressions
        )


    def preparer_requete_web(
        self, demande: ChatRequest,
        question_recherche: str | None = None,
        localite: str | None = None,
        *,
        forcer: bool = False,
        type_information: str | None = None,
    ) -> str | None:
        """Recherche le service public nommé dans la question, sans
        transmettre la situation personnelle ni l'historique.
        """
        question = (
            question_recherche if question_recherche is not None
            else demande.question
        )
        if not forcer and not self.necessite_recherche_web(question):
            return None

        identification = self.cibler_service_web(demande, question)
        if not identification:
            return None
        nom, type_cible = identification
        texte = self.normaliser(question)

        # Le classificateur peut détecter la même intention sans mots-clés.
        if type_information == "TARIF" or (type_information is None and any(mot in texte for mot in ("cout", "tarif", "frais"))):
            information = "tarif officiel actuel"
        elif type_information == "DELAI":
            information = "délai officiel actuel"
        elif type_information == "HORAIRES" or (type_information is None and any(mot in texte for mot in ("horaire", "heure d'ouverture"))):
            information = "horaires officiels"
        elif type_information == "CONTACT" or (type_information is None and any(mot in texte for mot in ("telephone", "contact", "contacter"))):
            information = "coordonnées officielles"
        else:
            information = "adresse officielle"

        if type_cible == "SIEGE":
            reference = PAGES_OFFICIELLES_DE_REFERENCE.get(self.normaliser(nom))
            piste = (f"Vérifie en priorité la page officielle {reference}. " if reference else "")
            return (
                f"Trouve l'{information} du siège de {nom}. "
                f"{piste}"
                "Consulte prioritairement sa page de contact institutionnelle. "
                "Ne cherche pas le bureau responsable d'une démarche particulière. "
                "Fournis les liens HTTPS exacts des pages utilisées. "
                "N'invente aucune adresse ni aucune compétence territoriale."
            )

        # Recherche une éventuelle localité présente dans la question seule.
        lieu = re.search(
            r"\b(?:à|au|en)\s+"
            r"([A-ZÀ-ÖØ-Ý][A-Za-zÀ-ÖØ-öø-ÿ-]*"
            r"(?:\s+[A-ZÀ-ÖØ-Ý][A-Za-zÀ-ÖØ-öø-ÿ-]*){0,2})",
            question,
        )
        # Une localité donnée en réponse à l'assistant est prioritaire.
        ville = localite or (lieu.group(1) if lieu else None)
        zone = f" à {ville}" if ville else ""
        # N'envoyer que le nom public du service et une localité :
        # jamais le texte libre de la situation personnelle.
        nom_public = (
            "Bureau des Domaines" if "bureau des domaines" in self.normaliser(nom)
            else nom
        )
        return (
            f"Recherche uniquement : {information} du {nom_public}{zone}. "
            "Privilégie les pages institutionnelles et les annuaires publics. "
            "Distingue le Bureau des Domaines, le Centre des services fiscaux "
            "et la Conservation foncière : ce ne sont pas des synonymes. "
            "Ne déduis pas la compétence territoriale de la seule ville. "
            "Ne propose aucune démarche, liste de pièces ni étapes à suivre. "
            "Fournis les URL HTTPS exactes. N'invente aucune information."
        )


    @staticmethod
    def trouver_preuve_localisation(
        demande: ChatRequest,
        sources_web: list[dict],
        localite: str | None = None,
        service_recherche: str | None = None,
    ) -> dict | None:
        """
        Recherche une indication explicite de localisation
        dans les extraits des sources institutionnelles.

        Ne considère pas l'adresse d'un siège comme
        celle d'un bureau administratif particulier.
        """

        # Une désignation explicite par l'usager prévaut sur le service
        # enregistré dans l'orientation, sans prouver la compétence.
        if service_recherche:
            nom_service = service_recherche
        elif len(demande.services_competents) == 1:
            nom_service = demande.services_competents[0].nom
        else:
            return None

        # Normalise les accents et les majuscules.
        def normaliser(texte: str) -> str:
            texte = unicodedata.normalize(
                "NFKD",
                texte.casefold(),
            )
            return "".join(
                c for c in texte
                if not unicodedata.combining(c)
            )

        nom_attendu = normaliser(nom_service)
        # Le libellé générique du référentiel n'est pas un nom de bureau.
        # Exiger un bureau explicitement désigné pour la localité connue.
        if "bureau des domaines" in nom_attendu:
            if not localite:
                return None
            noms_attendus = (
                normaliser(f"Bureau des Domaines de {localite}"),
                normaliser(f"Bureau des Domaines {localite}"),
            )
        elif "territorialement competent" in nom_attendu:
            # Un intitulé générique ne constitue pas une preuve.
            return None
        else:
            noms_attendus = (nom_attendu,)

        # Expressions indiquant une localisation physique.
        indicateurs = (
            "rue ", "avenue ", "boulevard ",
            "route ", "quartier ", "sicap ",
            "place ", "cite ",
        )

        for source in sources_web:
            extrait = source.get("extrait") or ""

            # Examine des lignes courtes, plutôt que
            # de rapprocher des informations éloignées
            # sur une même page.
            for ligne in extrait.splitlines():

                if len(ligne) > 250:
                    continue

                texte = normaliser(ligne)

                # La ligne doit nommer le service précis.
                if not any(nom in texte for nom in noms_attendus):
                    continue

                # Évite de retenir une adresse de siège
                # pour un service administratif distinct.
                if (
                    "siege" in texte
                    and "siege" not in nom_attendu
                ):
                    continue

                # Une indication géographique doit figurer
                # sur la même ligne que le service.
                if any(mot in texte for mot in indicateurs):
                    return {
                        "titre": source.get("titre", ""),
                        "url": source.get("url", ""),
                        "indication": ligne.strip(),
                    }

        return None


    @staticmethod
    def selectionner_sources_publiques(sources_web: list[dict]) -> list[dict]:
        """Évite les doublons et privilégie les pages officielles utiles.

        Les extraits restent disponibles pour les vérifications internes,
        mais ne sont jamais envoyés au frontend. Deux liens maximum.
        """
        from urllib.parse import parse_qsl, urlparse

        candidats = []
        urls_vues = set()
        for indice, source in enumerate(sources_web):
            url = (source.get("url") or "").strip()
            if not url_officielle(url):
                continue

            adresse = urlparse(url)
            hote = (adresse.hostname or "").lower().removeprefix("www.")
            chemin = re.sub(r"/+", "/", adresse.path).rstrip("/").casefold()
            parametres = tuple(sorted(
                (cle, valeur) for cle, valeur in parse_qsl(adresse.query)
                if not cle.lower().startswith("utm_")
                and cle.lower() not in ("fbclid", "gclid")
            ))
            identite = (hote, chemin, parametres)
            if identite in urls_vues:
                continue
            urls_vues.add(identite)

            titre = str(source.get("titre") or "").strip()
            # Les moteurs de recherche renvoient parfois des libellés internes
            # du type « viewing lines [0 - 64] of 64 ». Ils n'ont aucun
            # intérêt pour l'usager et ne sont pas des titres de page.
            if (not titre or re.search(r"(?i)\bviewing\s+lines\s*\[|\blines\s*\[\d+", titre)):
                titre = f"Source officielle — {hote}"
            titre = titre[:130]
            label = ChatWebMixin.normaliser(titre + " " + chemin)
            # Page sur le bureau recherché > page Contact > autre page
            # > page d'accueil, qui apporte peu de précisions.
            score = (
                30 if "bureau des domaines" in label
                else 20 if "contact" in label
                else 10 if chemin
                else 0
            )
            candidats.append((score, indice, titre, url, hote, chemin))

        candidats.sort(key=lambda item: (-item[0], item[1]))
        selection = []
        titres_vus = set()
        sites_documentes = set()
        for _, _, titre, url, hote, chemin in candidats:
            # Une page d'accueil est superflue si nous disposons déjà
            # d'une page plus précise du même organisme.
            if not chemin and hote in sites_documentes:
                continue
            if titre.casefold() in titres_vus:
                continue
            selection.append({"titre": titre, "url": url})
            titres_vus.add(titre.casefold())
            if chemin:
                sites_documentes.add(hote)
            if len(selection) == 2:
                break
        return selection


    async def _verifier_page_officielle(self, nom: str) -> dict | None:
        """Vérifie une fiche institutionnelle sans dépendre d'un serveur unique.

        Plusieurs noms de domaine officiels peuvent être accessibles à des
        vitesses très différentes. Les requêtes indépendantes sont bornées
        en temps et la première preuve valide l'emporte. Aucune adresse n'est
        codée en dur, ni déduite d'un simple texte généré par un LLM.
        """
        cle = self.normaliser(nom)
        principale = PAGES_OFFICIELLES_DE_REFERENCE.get(cle)
        if not principale:
            return None
        urls = tuple(dict.fromkeys(
            (principale,) + PAGES_OFFICIELLES_ALTERNATIVES.get(cle, ())
        ))

        async def consulter(url: str) -> dict | None:
            sources = [{"titre": f"Page institutionnelle : {nom}",
                        "url": url, "extrait": ""}]
            try:
                # Une page indisponible ne doit pas empêcher les autres
                # adresses institutionnelles d'être essayées.
                await asyncio.wait_for(
                    enrichir_sources_officielles(sources), timeout=6.5,
                )
            except (TimeoutError, OSError, ValueError):
                return None
            return self.trouver_preuve_siege(nom, sources)

        # Les pages de référence sont indépendantes : les lancer ensemble
        # évite que le premier serveur lent monopolise le délai total.
        taches = [asyncio.create_task(consulter(url)) for url in urls]
        try:
            try:
                for travail in asyncio.as_completed(taches, timeout=7.0):
                    try:
                        preuve = await travail
                    except Exception:
                        # Une erreur de réseau sur une page ne justifie pas
                        # de rejeter les autres pages officielles.
                        continue
                    if preuve:
                        return preuve
            except TimeoutError:
                return None
            return None
        finally:
            for travail in taches:
                if not travail.done():
                    travail.cancel()
            await asyncio.gather(*taches, return_exceptions=True)


    async def repondre_web(
        self, demande: ChatRequest, question_recherche: str,
        localite: str | None = None, categorie_web: str | None = None,
        forcer: bool = False,
    ) -> ChatResponse:
        """Recherche et vérifie des informations pratiques publiques."""
        # Prépare une recherche contenant uniquement
        # des informations publiques.
        requete_web = self.preparer_requete_web(
            demande, question_recherche=question_recherche,
            localite=localite, forcer=forcer,
            type_information=categorie_web,
        )

        if not requete_web:
            return ChatResponse(
                reponse=(
                    "Pour rechercher cette information, "
                    "pouvez-vous préciser le service "
                    "administratif concerné ?"
                ),
                sources=[],
            )

        # Si le service dispose déjà d'une référence institutionnelle,
        # la consulter avant d'appeler Groq : réponse plus rapide et fondée
        # sur le texte de la page plutôt que sur le résumé du moteur.
        question_norm = self.normaliser(question_recherche)
        demande_adresse = categorie_web == "ADRESSE" or any(
            expression in question_norm for expression in (
                "ou se trouve", "ou est situe", "ou se situe", "adresse",
                "localisation", "ou dois-je me rendre", "quel bureau",
            )
        )
        cible_directe = self.cibler_service_web(demande, question_recherche)
        if demande_adresse and cible_directe and cible_directe[1] == "SIEGE":
            nom_direct = cible_directe[0]
            preuve_directe = await self._verifier_page_officielle(nom_direct)
            if preuve_directe:
                return ChatResponse(
                    reponse=(
                        f"Le siège de {nom_direct} se trouve à l'adresse suivante : "
                        f"{preuve_directe['adresse']}. "
                        "Cela ne signifie pas que ce siège traite votre dossier : "
                        "le bureau territorialement compétent peut être différent."
                    ),
                    sources=[{"titre": preuve_directe["titre"],
                              "url": preuve_directe["url"]}],
                )

        # Prépare la liste des sources web.
        liens_web = []

        # Effectue une seule requête Groq avec
        # l'outil de recherche Internet.
        reponse_web = await self.llm.generate(
            system_prompt=(
                "Tu es le chatbot contextuel d'AdmiGuide. "
                "Recherche uniquement des informations "
                "administratives publiques. "
                "Privilégie les sources officielles. "
                "Fournis les liens HTTPS exacts des pages "
                "consultées pour justifier tes réponses. "

                # Vérification des adresses administratives.
                "Ne présente jamais l'adresse du siège "
                "d'une administration comme celle d'un "
                "bureau particulier sans confirmation "
                "explicite d'une source fiable. "
                "Ne confonds pas le siège d'une administration "
                "avec le bureau territorialement compétent. "

                # Gestion des informations incertaines.
                "Ne conclus jamais qu'un bureau n'existe pas "
                "simplement parce qu'il est absent des "
                "résultats de recherche. "
                "Si la localisation du bureau compétent "
                "reste incertaine, indique-le clairement "
                "et demande une précision utile. "

                # Respect du rôle du chatbot.
                "N'invente aucune information. "
                "Ne crée aucune nouvelle démarche. "
                "Réponds uniquement à l'information pratique demandée : "
                "aucune procédure, liste d'étapes ou pièces à préparer. "
            ),
            user_prompt=requete_web,
            model_name=settings.chat_llm_model_name,
            utiliser_recherche_web=True,
            sources_web=liens_web,
        )

        # Une URL Groq peut ne contenir aucun extrait. Dans ce cas,
        # lire la page institutionnelle et éventuellement sa page de contact.
        # Les URL sont strictement filtrées par web_source_service.
        if any(not (source.get("extrait") or "").strip() for source in liens_web):
            await enrichir_sources_officielles(liens_web)

        # Prépare les sources à afficher à l'utilisateur.
        # Le champ "extrait" reste réservé au contrôle interne.
        sources_publiques = self.selectionner_sources_publiques(liens_web)

        # Normalise la question pour identifier
        # les demandes de localisation.
        texte = unicodedata.normalize(
            "NFKD",
            question_recherche.casefold(),
        )

        texte = "".join(
            caractere
            for caractere in texte
            if not unicodedata.combining(caractere)
        )

        # Vérifie si l'utilisateur recherche une adresse.
        demande_localisation = categorie_web == "ADRESSE" or any(
            expression in texte
            for expression in (
                "ou se trouve",
                "ou est situe",
                "ou se situe",
                "adresse",
                "localisation",
                "ou dois-je me rendre",
                "quel bureau",
            )
        )

        if demande_localisation:
            identification = self.cibler_service_web(demande, question_recherche)
            if identification is None:
                return ChatResponse(
                    reponse="Pouvez-vous préciser l'administration ou le service recherché ?",
                    sources=[],
                )

            nom, type_cible = identification
            if type_cible == "SIEGE":
                # L'adresse ne doit pas provenir uniquement du texte du LLM.
                preuve = self.trouver_preuve_siege(nom, liens_web)
                # Les pages de référence ont déjà été consultées avant Groq.
                # Ne pas prolonger la réponse par une seconde consultation.
                if preuve is None:
                    # Même sans preuve extractible, donner une page précise
                    # à consulter plutôt qu'une page d'accueil sans contexte.
                    reference = PAGES_OFFICIELLES_DE_REFERENCE.get(
                        self.normaliser(nom)
                    )
                    if reference and url_officielle(reference):
                        sources_publiques = [{
                            "titre": f"Fiche officielle — {nom}",
                            "url": reference,
                        }]
                    return ChatResponse(
                        reponse=(
                            "Je n'ai pas pu confirmer l'adresse du siège "
                            "à partir des pages officielles accessibles au chatbot. "
                            "Vous pouvez consulter la fiche institutionnelle "
                            "ci-dessous pour la vérifier directement."
                        ),
                        sources=sources_publiques,
                    )
                return ChatResponse(
                    reponse=(
                        f"Le siège de {nom} se trouve à l'adresse suivante : "
                        f"{preuve['adresse']}. "
                        "Cela ne signifie pas que ce siège traite votre dossier : "
                        "le bureau territorialement compétent peut être différent."
                    ),
                    sources=[{
                        "titre": preuve["titre"],
                        "url": preuve["url"],
                    }],
                )

            # Pour une démarche, ne présente pas l'adresse du siège
            # comme celle du bureau territorialement compétent.
            # Le lieu peut venir du suivi ou être déjà dans la question.
            if not localite:
                lieu = re.search(
                    r"\b(?:à|au|en)\s+"
                    r"([A-ZÀ-ÖØ-Ý][A-Za-zÀ-ÖØ-öø-ÿ-]*"
                    r"(?:\s+[A-ZÀ-ÖØ-Ý][A-Za-zÀ-ÖØ-öø-ÿ-]*){0,2})",
                    question_recherche,
                )
                if lieu:
                    localite = lieu.group(1)

            preuve = self.trouver_preuve_localisation(
                demande, liens_web, localite=localite,
                service_recherche=nom,
            )
            if preuve is None:
                if localite:
                    nom_public = (
                        "Bureau des Domaines"
                        if "bureau des domaines" in self.normaliser(nom)
                        else nom
                    )
                    texte_reponse = (
                        f"Pour {localite}, je n'ai pas pu confirmer "
                        f"l'adresse exacte du {nom_public} "
                        "à partir des sources officielles consultées. "
                        "Un autre service situé dans la même localité "
                        "n'est pas nécessairement le bureau compétent. "
                        "Vous pouvez vérifier auprès de l'administration "
                        "concernée avant de vous déplacer."
                    )
                else:
                    texte_reponse = (
                        "Je n'ai pas pu confirmer l'adresse du bureau "
                        "administratif compétent. Le siège de l'administration "
                        "peut se trouver ailleurs. Pouvez-vous préciser "
                        "la localité concernée par votre démarche ?"
                    )
                return ChatResponse(
                    reponse=texte_reponse,
                    sources=sources_publiques,
                )

            return ChatResponse(
                reponse=(
                    "Une source institutionnelle mentionne : "
                    f"{preuve['indication']}. "
                    "La compétence de ce bureau pour votre dossier "
                    "doit être confirmée."
                ),
                sources=[{
                    "titre": preuve["titre"], "url": preuve["url"],
                }],
            )

        # Sans source institutionnelle, ne présente pas de détail
        # pratique non vérifié comme une information certaine.
        if not sources_publiques:
            return ChatResponse(
                reponse="Je n'ai pas pu vérifier cette information dans une source officielle.",
                sources=[],
            )

        # Pour les autres informations pratiques
        # (horaires, contacts, tarifs), retourne
        # la réponse et ses sources.
        return ChatResponse(
            reponse=reponse_web.strip(),
            sources=sources_publiques,
        )

