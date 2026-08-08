"""Import de données depuis la Member Data Portability API de LinkedIn (Member Snapshot
API), réservée aux membres UE/EEE/Suisse dans le cadre du DMA. Nécessite un access token
généré par l'utilisateur via le portail développeur LinkedIn (OAuth Token Generator Tool,
scope `r_dma_portability_self_serve`) — voir le README pour la procédure complète.

Doc officielle : https://learn.microsoft.com/en-us/linkedin/dma/member-data-portability/
"""
import json
import urllib.error
import urllib.request

from linkedin_import import map_education, map_experience, map_language, map_profile, map_skill

API_BASE = "https://api.linkedin.com"
LINKEDIN_VERSION = "202312"
MAX_PAGES_PER_DOMAIN = 20


class _NoSnapshotData(Exception):
    """LinkedIn n'a pas (encore) de données pour ce domaine : après consentement, le
    "snapshot" se génère de façon asynchrone côté LinkedIn et peut ne pas être prêt
    immédiatement. Ce n'est pas une erreur d'authentification.
    """


def _api_get(url: str, access_token: str) -> dict:
    if not url.startswith("http"):
        url = f"{API_BASE}{url}"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Linkedin-Version": LINKEDIN_VERSION,
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "ignore")
        if e.code == 404 and "no data found" in body.lower():
            raise _NoSnapshotData(body) from e
        raise RuntimeError(f"LinkedIn a répondu {e.code} : {body[:300]}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Impossible de joindre l'API LinkedIn : {e.reason}") from e


def _fetch_domain_rows(domain: str, access_token: str) -> list[dict]:
    rows: list[dict] = []
    url = f"/rest/memberSnapshotData?q=criteria&domain={domain}"
    for _ in range(MAX_PAGES_PER_DOMAIN):
        try:
            data = _api_get(url, access_token)
        except _NoSnapshotData:
            break
        for element in data.get("elements", []):
            snapshot_data = element.get("snapshotData")
            if isinstance(snapshot_data, list):
                rows.extend(r for r in snapshot_data if isinstance(r, dict))
            elif isinstance(snapshot_data, dict):
                rows.append(snapshot_data)

        next_link = next(
            (l.get("href") for l in data.get("paging", {}).get("links", []) if l.get("rel") == "next"),
            None,
        )
        if not next_link:
            break
        url = next_link
    return rows


def fetch_linkedin_snapshot(access_token: str) -> dict:
    """Interroge la Member Snapshot API pour les domaines pertinents et retourne
    les données dans le même format que `linkedin_import.parse_linkedin_export`.
    """
    result = {"profile": {}, "experiences": [], "educations": [], "skills": [], "languages": []}

    profile_rows = _fetch_domain_rows("PROFILE", access_token)
    if profile_rows:
        result["profile"] = map_profile(profile_rows[0])

    for row in _fetch_domain_rows("POSITIONS", access_token):
        exp = map_experience(row)
        if exp:
            result["experiences"].append(exp)

    for row in _fetch_domain_rows("EDUCATION", access_token):
        edu = map_education(row)
        if edu:
            result["educations"].append(edu)

    for row in _fetch_domain_rows("SKILLS", access_token):
        sk = map_skill(row)
        if sk:
            result["skills"].append(sk)

    for row in _fetch_domain_rows("LANGUAGES", access_token):
        lang = map_language(row)
        if lang:
            result["languages"].append(lang)

    if not any(result.values()):
        raise RuntimeError(
            "LinkedIn n'a encore aucune donnée disponible pour ce token. Après le "
            "consentement, la génération du \"snapshot\" côté LinkedIn peut prendre de "
            "quelques minutes à plusieurs heures. Réessaie plus tard avec le même token "
            "(pas besoin d'en régénérer un tout de suite, il reste valable 60 jours)."
        )

    return result
