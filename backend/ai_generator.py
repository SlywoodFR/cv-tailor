"""Génération de CV/lettre via un LLM (Anthropic, OpenAI ou Google Gemini), en
remplacement du moteur mécanique par mots-clés de
cv_generator.py/letter_generator.py.

Un seul appel modèle fait à la fois la sélection du contenu pertinent (par
rapport à l'offre) ET sa rédaction -- y compris sa traduction si l'offre est
dans une langue différente de celle du profil. Aucune donnée n'est inventée :
le modèle ne peut que réordonner/sélectionner/traduire les données fournies.

Nécessite une clé API configurée côté serveur (ANTHROPIC_API_KEY, OPENAI_API_KEY
et/ou GEMINI_API_KEY, voir .env.example) -- sans clé, l'appelant doit rester sur
le moteur mécanique (voir ai_status()).
"""
import hashlib
import json
import os
from datetime import datetime
from types import SimpleNamespace
from typing import Optional

from pydantic import BaseModel, ConfigDict

try:
    import anthropic
except ImportError:
    anthropic = None

try:
    import openai
except ImportError:
    openai = None

try:
    from google import genai
    from google.genai import errors as genai_errors
except ImportError:
    genai = None
    genai_errors = None


AI_MODELS = {"anthropic": "claude-sonnet-5", "openai": "gpt-4o", "gemini": "gemini-2.5-flash"}


def ai_status() -> dict:
    return {
        "anthropic": bool(os.environ.get("ANTHROPIC_API_KEY")),
        "openai": bool(os.environ.get("OPENAI_API_KEY")),
        "gemini": bool(os.environ.get("GEMINI_API_KEY")),
    }


# ---------- Schémas de réponse attendus du modèle ----------
class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AILabels(_Strict):
    experiences: str
    education: str
    skills: str
    projects: str
    languages: str
    certifications: str
    contact: str
    current: str  # mot localisé pour "en cours" / "present"


class AISkillItem(_Strict):
    name: str
    level: str
    matched: bool


class AISkillCategory(_Strict):
    category: str
    items: list[AISkillItem]


class AIExperience(_Strict):
    company: str  # jamais traduit
    role: str
    location: str
    start_date: Optional[str]  # "YYYY-MM-DD" ou null
    end_date: Optional[str]
    bullets: list[str]
    matched: bool


class AIEducation(_Strict):
    school: str  # jamais traduit
    degree: str
    field: str
    start_date: Optional[str]
    end_date: Optional[str]
    description: str


class AIProject(_Strict):
    name: str  # jamais traduit
    description: str
    link: str


class AILanguage(_Strict):
    name: str
    level: str


class AICertification(_Strict):
    name: str  # jamais traduit (nom officiel de la certification)
    issuer: str  # jamais traduit
    obtained_date: Optional[str]
    link: str


class AICVResponse(_Strict):
    lang_code: str
    labels: AILabels
    summary: str
    skills_by_category: list[AISkillCategory]
    experiences: list[AIExperience]
    educations: list[AIEducation]
    projects: list[AIProject]
    languages: list[AILanguage]
    certifications: list[AICertification]


class AILetterResponse(_Strict):
    lang_code: str
    subject_line: str
    salutation: str
    paragraphs: list[str]
    closing: str


# ---------- Prompts ----------
_SYSTEM_COMMON = """You are a resume-and-cover-letter assistant. You will receive the \
candidate's raw structured profile data as JSON, followed by the text of a job offer \
(may be empty).

Rules, always:
- Detect the language the job offer is written in. If the offer is empty or its \
language is not clearly identifiable, keep the candidate's original language.
- If the offer's language differs from the candidate's data, translate ALL free text \
(summary, bullets, descriptions, category names, section labels, letter prose) into \
the offer's language. NEVER translate proper nouns: company names, school names, \
project names, the candidate's own name.
- Never invent: every company, school, skill, project, and date you output must come \
from the supplied data, verbatim for names/dates. You may reorder, condense, select, \
or translate -- never fabricate new experience, skills, education, or qualifications.
- If there is no job offer text: keep the original order and language, make no \
relevance judgments, only lightly polish phrasing if needed.
- Reply ONLY with the structured JSON response -- no extra commentary."""

_SYSTEM_CV = _SYSTEM_COMMON + """

For this CV task specifically:
- Mark each skill and each experience "matched": true if it is clearly relevant to \
the offer's stated requirements, else false. If there is no offer text, mark \
everything "matched": false.
- Within each skill category, order items with matched ones first.
- You may reorder each experience's bullets (the "description" field, one bullet per \
line) to foreground relevant ones, but must keep every bullet from the input -- do \
not drop or merge bullets.
- You may omit low-relevance projects, keeping at most 4, but never omit or invent an \
experience or education entry -- every one supplied must appear in the output, \
unmodified in substance.
- Dates: reproduce start_date/end_date exactly as given (ISO YYYY-MM-DD, or null).
- "labels": translate the section headers (experiences, education, skills, projects, \
languages, certifications, contact) and the "current/ongoing" word into the target \
language, or keep them in French if no translation is happening.
- Certifications: keep every one supplied (never omit or invent), reproduce \
"obtained_date" exactly as given. Never translate "name" or "issuer" -- certification \
titles and issuing organizations are official/branded terms, like company or school \
names."""

_SYSTEM_LETTER = _SYSTEM_COMMON + """

For this cover-letter task specifically:
- Write 3 to 5 short paragraphs of cover-letter prose in the target language, \
addressed to the employer, referencing the offer and the candidate's most relevant \
experience/skills from the supplied data (again: no invented facts).
- Write your own culturally-appropriate salutation, subject line, and closing for \
that language (e.g. "Dear Hiring Manager," / "Sincerely," in English; "Madame, \
Monsieur," / "Cordialement," in French) -- do not reuse a fixed template."""


def _parse_date(value: Optional[str]):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _serialize_cv_data(profile, experiences, educations, skills, projects, languages, certifications) -> dict:
    return {
        "profile": {"full_name": profile.full_name, "summary": profile.summary},
        "experiences": [
            {
                "company": e.company,
                "role": e.role,
                "location": e.location,
                "start_date": e.start_date.isoformat() if e.start_date else None,
                "end_date": e.end_date.isoformat() if e.end_date else None,
                "description": e.description,
            }
            for e in experiences
        ],
        "educations": [
            {
                "school": ed.school,
                "degree": ed.degree,
                "field": ed.field,
                "start_date": ed.start_date.isoformat() if ed.start_date else None,
                "end_date": ed.end_date.isoformat() if ed.end_date else None,
                "description": ed.description,
            }
            for ed in educations
        ],
        "skills": [{"name": s.name, "category": s.category, "level": s.level} for s in skills],
        "projects": [{"name": p.name, "description": p.description, "link": p.link} for p in projects],
        "languages": [{"name": l.name, "level": l.level} for l in languages],
        "certifications": [
            {
                "name": c.name,
                "issuer": c.issuer,
                "obtained_date": c.obtained_date.isoformat() if c.obtained_date else None,
                "link": c.link,
            }
            for c in certifications
        ],
    }


def _serialize_letter_data(profile, experiences, skills) -> dict:
    return {
        "profile": {"full_name": profile.full_name, "summary": profile.summary},
        "experiences": [
            {
                "company": e.company,
                "role": e.role,
                "location": e.location,
                "start_date": e.start_date.isoformat() if e.start_date else None,
                "end_date": e.end_date.isoformat() if e.end_date else None,
                "description": e.description,
            }
            for e in experiences
        ],
        "skills": [{"name": s.name, "category": s.category, "level": s.level} for s in skills],
    }


# ---------- Appels fournisseurs ----------
def _call_anthropic(system_prompt: str, user_content: str, schema_model) -> str:
    if anthropic is None:
        raise RuntimeError("Le paquet Python 'anthropic' n'est pas installé sur le serveur.")
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("Clé API Anthropic non configurée sur le serveur.")
    client = anthropic.Anthropic(api_key=api_key, timeout=90.0)
    try:
        response = client.messages.create(
            model=AI_MODELS["anthropic"],
            max_tokens=8000,
            system=system_prompt,
            messages=[{"role": "user", "content": user_content}],
            output_config={
                "format": {"type": "json_schema", "schema": schema_model.model_json_schema()},
            },
        )
    except anthropic.APIConnectionError as e:
        raise RuntimeError("Impossible de contacter l'API Anthropic (problème réseau).") from e
    except anthropic.APIStatusError as e:
        raise RuntimeError(f"Erreur API Anthropic ({e.status_code}) : {e.message}") from e
    if response.stop_reason == "refusal":
        raise RuntimeError("La génération IA a été refusée par les filtres de sécurité du modèle.")
    return next((block.text for block in response.content if block.type == "text"), "")


def _call_openai(system_prompt: str, user_content: str, schema_model) -> str:
    if openai is None:
        raise RuntimeError("Le paquet Python 'openai' n'est pas installé sur le serveur.")
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Clé API OpenAI non configurée sur le serveur.")
    client = openai.OpenAI(api_key=api_key, timeout=90.0)
    try:
        response = client.chat.completions.create(
            model=AI_MODELS["openai"],
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": schema_model.__name__,
                    "schema": schema_model.model_json_schema(),
                    "strict": True,
                },
            },
        )
    except openai.APIConnectionError as e:
        raise RuntimeError("Impossible de contacter l'API OpenAI (problème réseau).") from e
    except openai.APIStatusError as e:
        raise RuntimeError(f"Erreur API OpenAI ({e.status_code}) : {e.message}") from e
    choice = response.choices[0]
    if choice.finish_reason == "content_filter":
        raise RuntimeError("La génération IA a été refusée par les filtres de sécurité du modèle.")
    return choice.message.content or ""


def _gemini_schema(schema_model) -> dict:
    """Le sous-ensemble de schéma accepté par Gemini n'a pas d'"additionalProperties"
    (rejeté avec une erreur 400 "Unknown name") -- on part du JSON Schema Pydantic,
    on résout les $ref/$defs (au cas où le SDK installé ne les supporte pas encore)
    et on retire les clés que Gemini ne reconnaît pas."""
    raw = schema_model.model_json_schema()
    defs = raw.pop("$defs", {})

    def resolve(node):
        if isinstance(node, dict):
            if "$ref" in node:
                return resolve(defs[node["$ref"].rsplit("/", 1)[-1]])
            return {
                key: resolve(value)
                for key, value in node.items()
                if key not in ("additionalProperties", "title")
            }
        if isinstance(node, list):
            return [resolve(item) for item in node]
        return node

    return resolve(raw)


def _call_gemini(system_prompt: str, user_content: str, schema_model) -> str:
    if genai is None:
        raise RuntimeError("Le paquet Python 'google-genai' n'est pas installé sur le serveur.")
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("Clé API Gemini non configurée sur le serveur.")
    client = genai.Client(api_key=api_key, http_options={"timeout": 90_000})  # ms
    try:
        response = client.models.generate_content(
            model=AI_MODELS["gemini"],
            contents=user_content,
            config={
                "system_instruction": system_prompt,
                "response_mime_type": "application/json",
                "response_schema": _gemini_schema(schema_model),
            },
        )
    except genai_errors.APIError as e:
        raise RuntimeError(f"Erreur API Gemini ({e.code}) : {e.message}") from e
    return response.text or ""


# Cache mémoire (process-local) des réponses déjà générées : évite de rappeler le
# LLM quand "Aperçu" est suivi de "Télécharger en PDF/.docx" pour la même offre --
# la clé inclut tout ce qui détermine la sortie (fournisseur + prompt + données
# sérialisées de la requête), donc tout changement réel (édition du profil, offre
# différente, fournisseur différent) invalide automatiquement le cache.
_response_cache: dict[str, BaseModel] = {}
_CACHE_MAX_ENTRIES = 64


def _cache_key(provider: str, system_prompt: str, user_content: str) -> str:
    raw = f"{provider}\n{system_prompt}\n{user_content}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _call_ai_json(provider: str, system_prompt: str, user_content: str, schema_model):
    key = _cache_key(provider, system_prompt, user_content)
    if key in _response_cache:
        return _response_cache[key]

    if provider == "anthropic":
        text = _call_anthropic(system_prompt, user_content, schema_model)
    elif provider == "openai":
        text = _call_openai(system_prompt, user_content, schema_model)
    elif provider == "gemini":
        text = _call_gemini(system_prompt, user_content, schema_model)
    else:
        raise RuntimeError(f"Fournisseur IA inconnu : {provider!r}")
    try:
        parsed = schema_model.model_validate_json(text)
    except Exception as e:
        raise RuntimeError(f"Réponse IA invalide (JSON inattendu) : {e}") from e

    if len(_response_cache) >= _CACHE_MAX_ENTRIES:
        _response_cache.pop(next(iter(_response_cache)))  # évince l'entrée la plus ancienne
    _response_cache[key] = parsed
    return parsed


# ---------- Construction de contexte (même forme que cv_generator/letter_generator) ----------
def generate_cv_context_ai(
    provider: str, profile, experiences, educations, skills, projects, languages, certifications,
    offer_text: str = "",
) -> dict:
    data = _serialize_cv_data(profile, experiences, educations, skills, projects, languages, certifications)
    user_content = json.dumps(data, ensure_ascii=False) + f"\n\nOffer text:\n{offer_text}"
    parsed: AICVResponse = _call_ai_json(provider, _SYSTEM_CV, user_content, AICVResponse)

    skills_by_category = {
        cat.category: [{"name": i.name, "level": i.level, "matched": i.matched} for i in cat.items]
        for cat in parsed.skills_by_category
    }

    experiences_ctx = [
        {
            "company": e.company,
            "role": e.role,
            "location": e.location,
            "start_date": _parse_date(e.start_date),
            "end_date": _parse_date(e.end_date),
            "bullets": e.bullets,
            "matched": e.matched,
        }
        for e in parsed.experiences
    ]

    # SimpleNamespace, pas des dicts : docx_generator.build_docx accède aux
    # formations/langues en attribut brut (ed.school, l.name...), comme le fait
    # déjà le mode mécanique avec les objets ORM Education/Language.
    educations_ctx = [
        SimpleNamespace(
            school=ed.school,
            degree=ed.degree,
            field=ed.field,
            start_date=_parse_date(ed.start_date),
            end_date=_parse_date(ed.end_date),
            description=ed.description,
        )
        for ed in parsed.educations
    ]
    languages_ctx = [SimpleNamespace(name=l.name, level=l.level) for l in parsed.languages]

    certifications_ctx = [
        SimpleNamespace(name=c.name, issuer=c.issuer, obtained_date=_parse_date(c.obtained_date), link=c.link)
        for c in parsed.certifications
    ]

    projects_ctx = [{"name": p.name, "description": p.description, "link": p.link} for p in parsed.projects]

    return {
        "profile": profile,
        "labels": parsed.labels.model_dump(),
        "summary": parsed.summary,
        "skills_by_category": skills_by_category,
        "experiences": experiences_ctx,
        "educations": educations_ctx,
        "projects": projects_ctx,
        "languages": languages_ctx,
        "certifications": certifications_ctx,
        "has_offer": bool((offer_text or "").strip()),
        "matched_keyword_count": 0,
    }


def generate_letter_context_ai(provider: str, profile, experiences, skills, offer_text: str = "") -> dict:
    data = _serialize_letter_data(profile, experiences, skills)
    user_content = json.dumps(data, ensure_ascii=False) + f"\n\nOffer text:\n{offer_text}"
    parsed: AILetterResponse = _call_ai_json(provider, _SYSTEM_LETTER, user_content, AILetterResponse)
    return {
        "profile": profile,
        "lang_code": parsed.lang_code,
        "subject_line": parsed.subject_line,
        "salutation": parsed.salutation,
        "paragraphs": parsed.paragraphs,
        "closing": parsed.closing,
    }
