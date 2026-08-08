"""Génère un brouillon de lettre de motivation à partir du profil et,
si fournie, d'une offre d'emploi -- réutilise le même moteur de mots-clés
que le CV (cv_generator.py). Pas d'IA générative : un gabarit de phrases
rempli avec les données les plus pertinentes, à relire avant envoi.
"""
import datetime as _dt

from cv_generator import extract_keywords, score_against_keywords


def _first_line(text: str, max_len: int = 100) -> str:
    for line in (text or "").splitlines():
        line = line.strip()
        if line:
            return line[:max_len]
    return ""


def build_letter_context(profile, experiences, skills, offer_text: str = "") -> dict:
    keywords = extract_keywords(offer_text)
    has_offer = bool(keywords)

    if has_offer:
        scored = [
            (score_against_keywords(e.description, e.tags, keywords), e) for e in experiences
        ]
        top_experiences = [e for score, e in sorted(scored, key=lambda x: -x[0]) if score > 0][:2]
        if not top_experiences:  # rien ne matche -> les plus récentes quand même
            top_experiences = sorted(
                experiences, key=lambda e: e.end_date or e.start_date or _dt.date.min, reverse=True
            )[:2]
    else:
        top_experiences = sorted(
            experiences, key=lambda e: e.end_date or e.start_date or _dt.date.min, reverse=True
        )[:2]

    if has_offer:
        scored_skills = [(score_against_keywords(s.name, s.name, keywords), s) for s in skills]
        top_skills = [s.name for score, s in sorted(scored_skills, key=lambda x: -x[0]) if score > 0][:6]
    else:
        top_skills = [s.name for s in skills][:6]

    return {
        "profile": profile,
        "summary": profile.summary,
        "job_title": _first_line(offer_text) if has_offer else "",
        "has_offer": has_offer,
        "top_experiences": top_experiences,
        "top_skills": top_skills,
    }
