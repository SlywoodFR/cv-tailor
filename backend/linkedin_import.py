"""Import de données depuis l'export officiel LinkedIn : le fichier .zip téléchargeable
depuis Paramètres et confidentialité > Confidentialité des données > Obtenir une copie
de vos données. Ne dépend d'aucun accès API à LinkedIn (fermé aux tiers depuis 2015) :
on lit simplement les CSV que LinkedIn fournit à ses propres utilisateurs.

Les fonctions `_map_*` ci-dessous transforment une "row" (dict de type CSV DictReader)
en champs de modèle ; elles sont réutilisées par linkedin_api_import.py, dont les
réponses JSON (Member Snapshot API) utilisent les mêmes noms de champs.
"""
import csv
import io
import zipfile
from datetime import date, datetime
from typing import Optional


def parse_date(value: str) -> Optional[date]:
    value = (value or "").strip()
    if not value:
        return None
    for fmt in ("%b %Y", "%B %Y", "%Y-%m-%d", "%Y-%m", "%m/%Y", "%d %b %Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    if value.isdigit() and len(value) == 4:
        return date(int(value), 1, 1)
    return None


def get(row: dict, *keys: str) -> str:
    lookup = {k.strip().lower(): v for k, v in row.items() if k}
    for key in keys:
        val = lookup.get(key.strip().lower())
        if val:
            return str(val).strip()
    return ""


def map_profile(row: dict) -> dict:
    fields = {}
    full_name = f"{get(row, 'First Name')} {get(row, 'Last Name')}".strip()
    if full_name:
        fields["full_name"] = full_name
    location = get(row, "Geo Location", "Location", "Address")
    if location:
        fields["location"] = location
    summary = get(row, "Summary", "Headline")
    if summary:
        fields["summary"] = summary
    website = get(row, "Websites")
    if website:
        fields["website"] = website.split(",")[0].strip()
    return fields


def map_experience(row: dict) -> Optional[dict]:
    company = get(row, "Company Name", "Company")
    role = get(row, "Title")
    if not (company or role):
        return None
    return {
        "company": company,
        "role": role,
        "location": get(row, "Location"),
        "start_date": parse_date(get(row, "Started On", "Start Date")),
        "end_date": parse_date(get(row, "Finished On", "End Date")),
        "description": get(row, "Description"),
    }


def map_education(row: dict) -> Optional[dict]:
    school = get(row, "School Name", "School")
    if not school:
        return None
    return {
        "school": school,
        "degree": get(row, "Degree Name", "Degree"),
        "field": get(row, "Field Of Study"),
        "start_date": parse_date(get(row, "Start Date")),
        "end_date": parse_date(get(row, "End Date")),
        "description": get(row, "Notes", "Activities"),
    }


def map_skill(row: dict) -> Optional[dict]:
    name = get(row, "Name")
    return {"name": name} if name else None


def map_language(row: dict) -> Optional[dict]:
    name = get(row, "Name")
    if not name:
        return None
    return {"name": name, "level": get(row, "Proficiency")}


def _read_csv(zf: zipfile.ZipFile, filename: str) -> list[dict]:
    matches = [n for n in zf.namelist() if n.lower().endswith(filename.lower())]
    if not matches:
        return []
    with zf.open(matches[0]) as f:
        text = io.TextIOWrapper(f, encoding="utf-8-sig")
        return list(csv.DictReader(text))


def parse_linkedin_export(zip_bytes: bytes) -> dict:
    """Lit un export LinkedIn (.zip) et retourne les données extraites,
    prêtes à être insérées pour un profil donné.
    """
    zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    result = {"profile": {}, "experiences": [], "educations": [], "skills": [], "languages": []}

    profile_rows = _read_csv(zf, "Profile.csv")
    if profile_rows:
        result["profile"] = map_profile(profile_rows[0])

    for row in _read_csv(zf, "Positions.csv"):
        exp = map_experience(row)
        if exp:
            result["experiences"].append(exp)

    for row in _read_csv(zf, "Education.csv"):
        edu = map_education(row)
        if edu:
            result["educations"].append(edu)

    for row in _read_csv(zf, "Skills.csv"):
        sk = map_skill(row)
        if sk:
            result["skills"].append(sk)

    for row in _read_csv(zf, "Languages.csv"):
        lang = map_language(row)
        if lang:
            result["languages"].append(lang)

    return result
