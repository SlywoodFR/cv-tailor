"""Moteur de génération de CV adapté à une offre d'emploi.

Logique :
1. Extraire des mots-clés de l'offre (texte libre collé par l'utilisateur).
2. Scorer chaque compétence / expérience / projet en fonction du nombre de
   mots-clés qu'il partage avec l'offre (via ses tags + son texte).
3. Construire un contexte de rendu où :
   - les compétences sont triées par pertinence dans chaque catégorie
   - les expériences restent en ordre chronologique (attendu sur un CV) mais
     leurs bullets sont réordonnées pour mettre en avant celles qui matchent
   - les projets sont filtrés aux plus pertinents (si une offre est fournie)
Sans offre fournie, le CV est simplement généré "tel quel" (ordre chronologique
/ alphabétique par défaut).
"""
import re
from collections import Counter

STOPWORDS = set("""
le la les un une des de du au aux et ou en dans pour par sur avec sans sous
vous nous ils elles il elle je tu on est sont sera seront a ont être avoir
notre votre leur leurs ce cet cette ces qui que quoi dont où mais donc car
plus moins très tres bien tout tous toute toutes autre autres ainsi comme
the a an of to in for on at by with and or is are be will your our their
we you they this that these those from as an will have has had not
poste role role mission missions entreprise societe société profil
recherche recherchons cherche cherchons candidat candidature h f
""".split())

WORD_RE = re.compile(r"[a-zàâäéèêëïîôöùûüçA-ZÀÂÄÉÈÊËÏÎÔÖÙÛÜÇ0-9+#\.\-]{2,}")

# Titres de section par défaut (mode mécanique, toujours en français). Le mode IA
# (ai_generator.py) fournit sa propre traduction sous la même forme.
DEFAULT_CV_LABELS = {
    "experiences": "Expériences",
    "education": "Formation",
    "skills": "Compétences",
    "projects": "Projets",
    "languages": "Langues",
    "contact": "Contact",
    "current": "en cours",
    "lang_code": "fr",
}


def extract_keywords(text: str) -> Counter:
    if not text:
        return Counter()
    words = [w.lower().strip(".-") for w in WORD_RE.findall(text)]
    words = [w for w in words if w not in STOPWORDS and len(w) > 1]
    return Counter(words)


def _tags_set(tags_str: str) -> set:
    return {t.strip().lower() for t in (tags_str or "").split(",") if t.strip()}


def score_against_keywords(text: str, tags: str, keywords: Counter) -> int:
    score = 0
    tag_set = _tags_set(tags)
    for tag in tag_set:
        if tag in keywords:
            score += keywords[tag] + 2  # un tag explicite pèse plus qu'un mot trouvé au hasard
    if text:
        text_words = extract_keywords(text)
        for word, count in text_words.items():
            if word in keywords:
                score += min(count, keywords[word])
    return score


def build_cv_context(profile, experiences, educations, skills, projects, languages, offer_text: str = ""):
    keywords = extract_keywords(offer_text)
    has_offer = bool(keywords)

    # --- Compétences : triées par pertinence puis regroupées par catégorie
    scored_skills = []
    for s in skills:
        score = score_against_keywords(s.name, s.name, keywords) if has_offer else 0
        scored_skills.append((score, s))
    scored_skills.sort(key=lambda x: (-x[0], x[1].name.lower()))

    skills_by_category = {}
    for score, s in scored_skills:
        cat = s.category or "Autres"
        skills_by_category.setdefault(cat, []).append({
            "name": s.name,
            "level": s.level,
            "matched": score > 0,
        })

    # --- Expériences : ordre chronologique (plus récent d'abord), bullets réordonnées
    def exp_sort_key(e):
        return e.end_date or e.start_date or __import__("datetime").date.min

    sorted_experiences = sorted(experiences, key=exp_sort_key, reverse=True)
    exp_context = []
    for e in sorted_experiences:
        bullets = [b.strip("- ").strip() for b in (e.description or "").split("\n") if b.strip()]
        if has_offer:
            bullets = sorted(
                bullets,
                key=lambda b: -score_against_keywords(b, "", keywords)
            )
        exp_score = score_against_keywords(e.description, e.tags, keywords) if has_offer else 0
        exp_context.append({
            "company": e.company,
            "role": e.role,
            "location": e.location,
            "start_date": e.start_date,
            "end_date": e.end_date,
            "bullets": bullets,
            "matched": exp_score > 0,
        })

    # --- Projets : si une offre est fournie, on garde les plus pertinents (max 4)
    scored_projects = []
    for p in projects:
        score = score_against_keywords(p.description, p.tags, keywords) if has_offer else 0
        scored_projects.append((score, p))
    scored_projects.sort(key=lambda x: -x[0])
    if has_offer:
        kept_projects = [p for score, p in scored_projects if score > 0][:4]
        if not kept_projects:  # rien ne matche -> on garde quand même les projets existants
            kept_projects = [p for _, p in scored_projects][:4]
    else:
        kept_projects = [p for _, p in scored_projects]

    projects_context = [{
        "name": p.name,
        "description": p.description,
        "link": p.link,
        "tags": _tags_set(p.tags),
    } for p in kept_projects]

    # --- Formations : ordre chronologique
    sorted_educations = sorted(
        educations,
        key=lambda e: e.end_date or e.start_date or __import__("datetime").date.min,
        reverse=True,
    )

    return {
        "profile": profile,
        "labels": DEFAULT_CV_LABELS,
        "summary": profile.summary,
        "skills_by_category": skills_by_category,
        "experiences": exp_context,
        "educations": sorted_educations,
        "projects": projects_context,
        "languages": languages,
        "has_offer": has_offer,
        "matched_keyword_count": sum(1 for _, s in scored_skills if s and score_against_keywords(s.name, s.name, keywords) > 0) if has_offer else 0,
    }
