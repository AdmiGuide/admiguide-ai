"""Lecture prudente des pages institutionnelles trouvées par Groq.

Ce service ne fait aucune recherche générale sur Internet : il ouvre seulement
les URL institutionnelles déjà retournées par browser_search.
"""

from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import httpx


# Domaines publics autorisés : pas d'URL arbitraire fournie par le modèle.
DOMAINES_AUTORISES = (
    "dgid.sn",
    "senegalservices.sn",
    "gouv.sn",
)

TAILLE_MAX_PAGE = 1_000_000  # 1 Mo au maximum, même si Content-Length manque.
TAILLE_MAX_TEXTE = 60_000
NOMBRE_MAX_SOURCES = 2
NOMBRE_MAX_REQUETES = 4


def url_officielle(url: str) -> bool:
    """Vérifie le protocole, le domaine et le port d'une URL publique."""
    if not isinstance(url, str) or not (0 < len(url) <= 2000):
        return False
    try:
        parsed = urlparse(url)
        nom = (parsed.hostname or "").rstrip(".").lower()
        return (
            parsed.scheme == "https"
            and bool(nom)
            and parsed.port in (None, 443)
            and parsed.username is None
            and parsed.password is None
            and all(c not in url for c in ("\r", "\n", "\t", "\\"))
            and any(
                nom == domaine or nom.endswith("." + domaine)
                for domaine in DOMAINES_AUTORISES
            )
        )
    except ValueError:
        return False


class LecteurHTML(HTMLParser):
    """Récupère le texte visible et les liens de contact d'une page HTML."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parties: list[str] = []
        self.liens_contact: list[str] = []
        self.ignores = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]):
        if tag in {"script", "style", "noscript", "svg", "template"}:
            self.ignores += 1
        if tag == "a" and not self.ignores:
            attribs = dict(attrs)
            chemin = attribs.get("href") or ""
            # Ne consulte que des liens annoncés comme pages de contact.
            if any(terme in chemin.lower() for terme in ("contact", "mentions-legales")):
                self.liens_contact.append(chemin)

    def handle_endtag(self, tag: str):
        if tag in {"script", "style", "noscript", "svg", "template"}:
            self.ignores = max(self.ignores - 1, 0)

    def handle_data(self, data: str):
        if not self.ignores:
            texte = " ".join(data.split())
            if texte:
                self.parties.append(texte)


def extraire_texte(html: str) -> tuple[str, list[str]]:
    lecteur = LecteurHTML()
    lecteur.feed(html)
    # Séparer les éléments évite de confondre des adresses éloignées.
    return "\n".join(lecteur.parties)[:TAILLE_MAX_TEXTE], lecteur.liens_contact


async def _lire_page(
    client: httpx.AsyncClient,
    url: str,
) -> tuple[str, str, list[str]] | None:
    """Lit une page HTTPS autorisée, sans suivre de redirection externe."""
    if not url_officielle(url):
        return None

    # Deux redirections maximum, uniquement dans la même famille officielle.
    # Ne jamais laisser httpx suivre automatiquement un lien externe.
    famille = next(
        d for d in DOMAINES_AUTORISES
        if (urlparse(url).hostname or "").rstrip(".").lower() == d
        or (urlparse(url).hostname or "").rstrip(".").lower().endswith("." + d)
    )
    try:
        courant = url
        for _ in range(3):
            async with client.stream("GET", courant, follow_redirects=False) as response:
                if response.status_code in (301, 302, 303, 307, 308):
                    destination = urljoin(courant, response.headers.get("location", ""))
                    if not url_officielle(destination) or destination == courant:
                        return None
                    hostname = (urlparse(destination).hostname or "").lower()
                    if hostname != famille and not hostname.endswith("." + famille):
                        return None
                    courant = destination
                    continue
                if response.status_code != 200:
                    return None
                type_contenu = response.headers.get("content-type", "").lower()
                if not (
                    type_contenu.startswith("text/html")
                    or type_contenu.startswith("text/plain")
                ):
                    return None
                morceaux = bytearray()
                async for morceau in response.aiter_bytes():
                    if len(morceaux) + len(morceau) > TAILLE_MAX_PAGE:
                        return None
                    morceaux.extend(morceau)
                contenu = morceaux.decode(response.encoding or "utf-8", errors="replace")
                if type_contenu.startswith("text/html"):
                    texte, liens = extraire_texte(contenu)
                else:
                    texte = contenu[:TAILLE_MAX_TEXTE]
                    liens = []
                return texte, str(response.url), liens
        return None
    except (httpx.HTTPError, UnicodeError, ValueError):
        return None


async def enrichir_sources_officielles(
    sources: list[dict],
    *,
    client: httpx.AsyncClient | None = None,
) -> None:
    """Complète en place les extraits vides et consulte une page de contact.

    Ne renvoie aucune page non autorisée. Les URL fournies par Groq sont des
    données non fiables. Au maximum 4 requêtes GET pour éviter les appels longs.
    """
    if not sources:
        return

    proprietaire = client is None
    if proprietaire:
        client = httpx.AsyncClient(
            timeout=httpx.Timeout(8.0, connect=4.0),
            follow_redirects=False,
            trust_env=False,
            headers={"User-Agent": "AdmiGuide/1.0 (consultation sources institutionnelles)"},
        )

    try:
        vus: set[str] = set()
        requetes = 0
        for source in list(sources[:NOMBRE_MAX_SOURCES]):
            if requetes >= NOMBRE_MAX_REQUETES:
                break
            original = source.get("url", "")
            if not url_officielle(original) or original in vus:
                continue
            # Une source avec extrait exploitable n'a pas besoin d'être rechargée.
            if (source.get("extrait") or "").strip():
                continue
            vus.add(original)
            requetes += 1
            page = await _lire_page(client, original)
            if page is None:
                continue
            texte, url_finale, liens = page
            source["extrait"] = texte

            # Cherche en priorité une page de contact reliée à la page trouvée.
            # En dernier recours pour un accueil sans lien lisible, essaie /contact.
            if not liens and urlparse(url_finale).path in ("", "/"):
                liens = ["/contact"]
            for lien in liens:
                if requetes >= NOMBRE_MAX_REQUETES:
                    break
                cible = urljoin(url_finale, lien)
                if cible in vus or not url_officielle(cible):
                    continue
                # Un lien de contact d'un autre organisme ne prouve pas
                # l'adresse de l'organisme recherché.
                origine = (urlparse(original).hostname or "").lower()
                destination = (urlparse(cible).hostname or "").lower()
                famille = next(
                    domaine for domaine in DOMAINES_AUTORISES
                    if origine == domaine or origine.endswith("." + domaine)
                )
                if destination != famille and not destination.endswith("." + famille):
                    continue
                vus.add(cible)
                requetes += 1
                contact = await _lire_page(client, cible)
                if contact is None:
                    continue
                contact_texte, url_contact, _ = contact
                if contact_texte:
                    sources.append({
                        "titre": "Page de contact officielle",
                        "url": url_contact,
                        "extrait": contact_texte,
                    })
                    break
    finally:
        if proprietaire:
            await client.aclose()
