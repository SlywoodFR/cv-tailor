"""Import de données depuis l'export officiel LinkedIn : le fichier .zip téléchargeable
depuis Paramètres et confidentialité > Confidentialité des données > Obtenir une copie
de vos données. Ne dépend d'aucun accès API à LinkedIn (fermé aux tiers depuis 2015) :
on lit simplement les CSV que LinkedIn fournit à ses propres utilisateurs.
"""
import csv
import io
import zipfile
from datetime import date, datetime
from typing import Optional


def _parse_date(value: str) -> Optional[date]:
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


def _read_csv(zf: zipfile.ZipFile, filename: str) -> list[dict]:
    matches = [n for n in zf.namelist() if n.lower().endswith(filename.lower())]
    if not matches:
        return []
    with zf.open(matches[0]) as f:
        text = io.TextIOWrapper(f, encoding="utf-8-sig")
        return list(csv.DictReader(text))


def _get(row: dict, *keys: str) -> str:
    lookup = {k.strip().lower(): v for k, v in row.items() if k}
    for key in keys:
        val = lookup.get(key.strip().lower())
        if val:
            return val.strip()
    return ""


def parse_linkedin_export(zip_bytes: bytes) -> dict:
    """Lit un export LinkedIn (.zip) et retourne les données extraites,
    prêtes à être insérées pour un profil donné.
    """
    zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    result = {"profile": {}, "experiences": [], "educations": [], "skills": [], "languages": []}

    profile_rows = _read_csv(zf, "Profile.csv")
    if profile_rows:
        row = profile_rows[0]
        full_name = f"{_get(row, 'First Name')} {_get(row, 'Last Name')}".strip()
        if full_name:
            result["profile"]["full_name"] = full_name
        location = _get(row, "Geo Location", "Location", "Address")
        if location:
            result["profile"]["location"] = location
        summary = _get(row, "Summary", "Headline")
        if summary:
            result["profile"]["summary"] = summary
        website = _get(row, "Websites")
        if website:
            result["profile"]["website"] = website.split(",")[0].strip()

    for row in _read_csv(zf, "Positions.csv"):
        company = _get(row, "Company Name", "Company")
        role = _get(row, "Title")
        if not (company or role):
            continue
        result["experiences"].append({
            "company": company,
            "role": role,
            "location": _get(row, "Location"),
            "start_date": _parse_date(_get(row, "Started On", "Start Date")),
            "end_date": _parse_date(_get(row, "Finished On", "End Date")),
            "description": _get(row, "Description"),
        })

    for row in _read_csv(zf, "Education.csv"):
        school = _get(row, "School Name", "School")
        if not school:
            continue
        result["educations"].append({
            "school": school,
            "degree": _get(row, "Degree Name", "Degree"),
            "field": _get(row, "Field Of Study"),
            "start_date": _parse_date(_get(row, "Start Date")),
            "end_date": _parse_date(_get(row, "End Date")),
            "description": _get(row, "Notes", "Activities"),
        })

    for row in _read_csv(zf, "Skills.csv"):
        name = _get(row, "Name")
        if name:
            result["skills"].append({"name": name})

    for row in _read_csv(zf, "Languages.csv"):
        name = _get(row, "Name")
        if name:
            result["languages"].append({"name": name, "level": _get(row, "Proficiency")})

    return result
