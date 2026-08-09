import io
import os
import zipfile
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()  # confort en dev local (uvicorn --reload) ; no-op en Docker, où
                # docker-compose injecte déjà de vraies variables d'environnement

from fastapi import FastAPI, Depends, Body, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from jinja2 import Environment, FileSystemLoader
from sqlmodel import Session, select

try:
    from weasyprint import HTML  # nécessite Pango/cairo, voir README
except (ImportError, OSError):
    HTML = None

from database import init_db, get_session, engine
from models import Profile, Experience, Education, Skill, Project, Language, GeneratedCV
from crud_factory import make_crud_router
from cv_generator import build_cv_context
from letter_generator import build_letter_context
from docx_generator import build_docx, build_letter_docx, build_letter_docx_ai
from linkedin_import import parse_linkedin_export
from linkedin_api_import import fetch_linkedin_snapshot
from ai_generator import ai_status, generate_cv_context_ai, generate_letter_context_ai

CV_TEMPLATES = {
    "classique": "cv_template.html",
    "moderne": "cv_template_moderne.html",
    "compact": "cv_template_compact.html",
}


def _cv_template_file(payload: dict) -> str:
    return CV_TEMPLATES.get(payload.get("template"), CV_TEMPLATES["classique"])

BASE_DIR = os.path.dirname(__file__)
FRONTEND_DIR = os.path.join(os.path.dirname(BASE_DIR), "frontend")

app = FastAPI(title="cv-tailor")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)

jinja_env = Environment(loader=FileSystemLoader(os.path.join(BASE_DIR, "templates")))


@app.on_event("startup")
def on_startup():
    init_db()
    # s'assure qu'il existe toujours au moins un profil
    with Session(engine) as session:
        if not session.exec(select(Profile)).first():
            session.add(Profile(full_name="Profil 1"))
            session.commit()


# ---------- Profils (multi-utilisateurs) ----------
@app.get("/api/profiles", response_model=list[Profile])
def list_profiles(session: Session = Depends(get_session)):
    return session.exec(select(Profile)).all()


@app.post("/api/profiles", response_model=Profile)
def create_profile(payload: dict = Body(default={}), session: Session = Depends(get_session)):
    payload.pop("id", None)
    profile = Profile.model_validate(payload)
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return profile


@app.get("/api/profile/{profile_id}", response_model=Profile)
def get_profile(profile_id: int, session: Session = Depends(get_session)):
    db_item = session.get(Profile, profile_id)
    if not db_item:
        raise HTTPException(status_code=404, detail="Profil introuvable")
    return db_item


@app.put("/api/profile/{profile_id}", response_model=Profile)
def update_profile(profile_id: int, payload: dict = Body(...), session: Session = Depends(get_session)):
    db_item = session.get(Profile, profile_id)
    if not db_item:
        raise HTTPException(status_code=404, detail="Profil introuvable")
    payload.pop("id", None)
    validated = Profile.model_validate({**db_item.model_dump(), **payload})
    for key, value in validated.model_dump(exclude={"id"}).items():
        setattr(db_item, key, value)
    session.add(db_item)
    session.commit()
    session.refresh(db_item)
    return db_item


@app.delete("/api/profile/{profile_id}")
def delete_profile(profile_id: int, session: Session = Depends(get_session)):
    profile = session.get(Profile, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profil introuvable")
    for model in (Experience, Education, Skill, Project, Language, GeneratedCV):
        for row in session.exec(select(model).where(model.profile_id == profile_id)).all():
            session.delete(row)
    session.delete(profile)
    session.commit()
    return {"ok": True}


# ---------- CRUD génériques (filtrés par profile_id) ----------
app.include_router(make_crud_router(Experience, "/api/experiences", "Expériences"))
app.include_router(make_crud_router(Education, "/api/educations", "Formations"))
app.include_router(make_crud_router(Skill, "/api/skills", "Compétences"))
app.include_router(make_crud_router(Project, "/api/projects", "Projets"))
app.include_router(make_crud_router(Language, "/api/languages", "Langues"))


# ---------- Historique des offres (léger : texte + date, pas de snapshot fichier) ----------
@app.get("/api/cv-history/", response_model=list[GeneratedCV])
def list_cv_history(profile_id: int, session: Session = Depends(get_session)):
    return session.exec(
        select(GeneratedCV)
        .where(GeneratedCV.profile_id == profile_id)
        .order_by(GeneratedCV.created_at.desc())
    ).all()


@app.delete("/api/cv-history/{entry_id}")
def delete_cv_history(entry_id: int, session: Session = Depends(get_session)):
    entry = session.get(GeneratedCV, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Entrée introuvable")
    session.delete(entry)
    session.commit()
    return {"ok": True}


def _log_cv_history(session: Session, profile_id: int, offer_text: str, template: str):
    offer_text = (offer_text or "").strip()
    if not offer_text:
        return
    existing = session.exec(
        select(GeneratedCV).where(
            GeneratedCV.profile_id == profile_id, GeneratedCV.offer_text == offer_text
        )
    ).first()
    if existing:
        existing.created_at = datetime.utcnow()
        existing.template = template
        session.add(existing)
    else:
        first_line = next((l.strip() for l in offer_text.splitlines() if l.strip()), offer_text)
        session.add(GeneratedCV(
            profile_id=profile_id, offer_text=offer_text, offer_title=first_line[:100], template=template,
        ))
    session.commit()


# ---------- Import LinkedIn ----------
def _norm(value: str) -> str:
    return (value or "").strip().lower()


def _apply_linkedin_import(session: Session, profile: Profile, profile_id: int, data: dict) -> dict:
    profile_updated = False
    for key, value in data["profile"].items():
        if not getattr(profile, key, ""):
            setattr(profile, key, value)
            profile_updated = True
    if profile_updated:
        session.add(profile)

    existing_experiences = {
        (_norm(e.company), _norm(e.role))
        for e in session.exec(select(Experience).where(Experience.profile_id == profile_id)).all()
    }
    existing_educations = {
        (_norm(e.school), _norm(e.degree))
        for e in session.exec(select(Education).where(Education.profile_id == profile_id)).all()
    }
    existing_skills = {
        _norm(s.name)
        for s in session.exec(select(Skill).where(Skill.profile_id == profile_id)).all()
    }
    existing_languages = {
        _norm(l.name)
        for l in session.exec(select(Language).where(Language.profile_id == profile_id)).all()
    }

    counts = {"experiences": 0, "educations": 0, "skills": 0, "languages": 0, "duplicates_skipped": 0}

    for exp in data["experiences"]:
        key = (_norm(exp["company"]), _norm(exp["role"]))
        if key in existing_experiences:
            counts["duplicates_skipped"] += 1
            continue
        existing_experiences.add(key)
        session.add(Experience(profile_id=profile_id, **exp))
        counts["experiences"] += 1

    for edu in data["educations"]:
        key = (_norm(edu["school"]), _norm(edu["degree"]))
        if key in existing_educations:
            counts["duplicates_skipped"] += 1
            continue
        existing_educations.add(key)
        session.add(Education(profile_id=profile_id, **edu))
        counts["educations"] += 1

    for sk in data["skills"]:
        key = _norm(sk["name"])
        if key in existing_skills:
            counts["duplicates_skipped"] += 1
            continue
        existing_skills.add(key)
        session.add(Skill(profile_id=profile_id, **sk))
        counts["skills"] += 1

    for lang in data["languages"]:
        key = _norm(lang["name"])
        if key in existing_languages:
            counts["duplicates_skipped"] += 1
            continue
        existing_languages.add(key)
        session.add(Language(profile_id=profile_id, **lang))
        counts["languages"] += 1

    session.commit()
    counts["profile_updated"] = profile_updated
    return counts


@app.post("/api/import/linkedin")
async def import_linkedin(
    profile_id: int, file: UploadFile = File(...), session: Session = Depends(get_session)
):
    profile = session.get(Profile, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profil introuvable")

    content = await file.read()
    try:
        data = parse_linkedin_export(content)
    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="Le fichier fourni n'est pas un .zip valide")

    return _apply_linkedin_import(session, profile, profile_id, data)


@app.post("/api/import/linkedin-api")
def import_linkedin_api(
    profile_id: int, payload: dict = Body(...), session: Session = Depends(get_session)
):
    access_token = (payload.get("access_token") or "").strip()
    if not access_token:
        raise HTTPException(status_code=400, detail="Access token manquant")

    profile = session.get(Profile, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profil introuvable")

    try:
        data = fetch_linkedin_snapshot(access_token)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))

    return _apply_linkedin_import(session, profile, profile_id, data)


# ---------- Mode IA ----------
@app.get("/api/ai/status")
def get_ai_status():
    return ai_status()


# ---------- Génération de CV ----------
def _gather(session: Session, profile_id: int):
    profile = session.get(Profile, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profil introuvable")
    experiences = session.exec(select(Experience).where(Experience.profile_id == profile_id)).all()
    educations = session.exec(select(Education).where(Education.profile_id == profile_id)).all()
    skills = session.exec(select(Skill).where(Skill.profile_id == profile_id)).all()
    projects = session.exec(select(Project).where(Project.profile_id == profile_id)).all()
    languages = session.exec(select(Language).where(Language.profile_id == profile_id)).all()
    return profile, experiences, educations, skills, projects, languages


def _build_cv_context(session: Session, profile_id: int, offer_text: str, ai_provider):
    ai_provider = (ai_provider or "").strip()
    if ai_provider:
        try:
            return generate_cv_context_ai(ai_provider, *_gather(session, profile_id), offer_text=offer_text)
        except RuntimeError as e:
            raise HTTPException(status_code=502, detail=str(e))
    return build_cv_context(*_gather(session, profile_id), offer_text=offer_text)


@app.post("/api/generate-cv/html", response_class=HTMLResponse)
def generate_cv_html(payload: dict = Body(default={}), session: Session = Depends(get_session)):
    offer_text = payload.get("offer_text", "")
    profile_id = int(payload.get("profile_id", 1))
    context = _build_cv_context(session, profile_id, offer_text, payload.get("ai_provider"))
    template = jinja_env.get_template(_cv_template_file(payload))
    return template.render(**context)


@app.post("/api/generate-cv/pdf")
def generate_cv_pdf(payload: dict = Body(default={}), session: Session = Depends(get_session)):
    if HTML is None:
        raise HTTPException(
            status_code=503,
            detail="Export PDF indisponible : bibliothèques système manquantes (voir README).",
        )
    offer_text = payload.get("offer_text", "")
    profile_id = int(payload.get("profile_id", 1))
    template_key = payload.get("template", "classique")
    context = _build_cv_context(session, profile_id, offer_text, payload.get("ai_provider"))
    template = jinja_env.get_template(_cv_template_file(payload))
    html = template.render(**context)
    buf = io.BytesIO()
    HTML(string=html).write_pdf(buf)
    buf.seek(0)
    _log_cv_history(session, profile_id, offer_text, template_key)
    filename = f"CV_{context['profile'].full_name.replace(' ', '_') or 'export'}.pdf"
    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.post("/api/generate-cv/docx")
def generate_cv_docx(payload: dict = Body(default={}), session: Session = Depends(get_session)):
    offer_text = payload.get("offer_text", "")
    profile_id = int(payload.get("profile_id", 1))
    context = _build_cv_context(session, profile_id, offer_text, payload.get("ai_provider"))
    doc = build_docx(context)
    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    _log_cv_history(session, profile_id, offer_text, "classique")
    filename = f"CV_{context['profile'].full_name.replace(' ', '_') or 'export'}.docx"
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------- Génération de lettre de motivation (gabarit mécanique, ou IA si ai_provider) ----------
def _gather_letter(session: Session, profile_id: int):
    profile = session.get(Profile, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profil introuvable")
    experiences = session.exec(select(Experience).where(Experience.profile_id == profile_id)).all()
    skills = session.exec(select(Skill).where(Skill.profile_id == profile_id)).all()
    return profile, experiences, skills


def _build_letter_context(session: Session, profile_id: int, offer_text: str, ai_provider):
    ai_provider = (ai_provider or "").strip()
    if ai_provider:
        try:
            return generate_letter_context_ai(
                ai_provider, *_gather_letter(session, profile_id), offer_text=offer_text
            )
        except RuntimeError as e:
            raise HTTPException(status_code=502, detail=str(e))
    return build_letter_context(*_gather_letter(session, profile_id), offer_text=offer_text)


@app.post("/api/generate-letter/html", response_class=HTMLResponse)
def generate_letter_html(payload: dict = Body(default={}), session: Session = Depends(get_session)):
    offer_text = payload.get("offer_text", "")
    profile_id = int(payload.get("profile_id", 1))
    ai_provider = (payload.get("ai_provider") or "").strip()
    context = _build_letter_context(session, profile_id, offer_text, ai_provider)
    context["today"] = datetime.now().strftime("%d/%m/%Y")
    template = jinja_env.get_template("letter_template_ai.html" if ai_provider else "letter_template.html")
    return template.render(**context)


@app.post("/api/generate-letter/pdf")
def generate_letter_pdf(payload: dict = Body(default={}), session: Session = Depends(get_session)):
    if HTML is None:
        raise HTTPException(
            status_code=503,
            detail="Export PDF indisponible : bibliothèques système manquantes (voir README).",
        )
    offer_text = payload.get("offer_text", "")
    profile_id = int(payload.get("profile_id", 1))
    ai_provider = (payload.get("ai_provider") or "").strip()
    context = _build_letter_context(session, profile_id, offer_text, ai_provider)
    context["today"] = datetime.now().strftime("%d/%m/%Y")
    template = jinja_env.get_template("letter_template_ai.html" if ai_provider else "letter_template.html")
    html = template.render(**context)
    buf = io.BytesIO()
    HTML(string=html).write_pdf(buf)
    buf.seek(0)
    filename = f"Lettre_{context['profile'].full_name.replace(' ', '_') or 'export'}.pdf"
    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.post("/api/generate-letter/docx")
def generate_letter_docx_route(payload: dict = Body(default={}), session: Session = Depends(get_session)):
    offer_text = payload.get("offer_text", "")
    profile_id = int(payload.get("profile_id", 1))
    ai_provider = (payload.get("ai_provider") or "").strip()
    context = _build_letter_context(session, profile_id, offer_text, ai_provider)
    context["today"] = datetime.now().strftime("%d/%m/%Y")
    doc = build_letter_docx_ai(context) if ai_provider else build_letter_docx(context)
    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    filename = f"Lettre_{context['profile'].full_name.replace(' ', '_') or 'export'}.docx"
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------- Frontend statique ----------
class NoCacheStaticFiles(StaticFiles):
    """Évite que le navigateur mette en cache l'ancien app.js/style.css entre deux
    mises à jour de l'app -- sans ça, un simple rechargement de page peut continuer
    à servir une version obsolète du frontend."""

    def file_response(self, *args, **kwargs):
        response = super().file_response(*args, **kwargs)
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        return response


app.mount("/", NoCacheStaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
