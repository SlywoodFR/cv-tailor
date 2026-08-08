import io
import os
import zipfile
from datetime import datetime

from fastapi import FastAPI, Depends, Body, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from jinja2 import Environment, FileSystemLoader
from sqlmodel import Session, select

from database import init_db, get_session, engine
from models import Profile, Experience, Education, Skill, Project, Language
from crud_factory import make_crud_router
from cv_generator import build_cv_context
from docx_generator import build_docx
from linkedin_import import parse_linkedin_export
from linkedin_api_import import fetch_linkedin_snapshot

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


# ---------- CRUD génériques (filtrés par profile_id) ----------
app.include_router(make_crud_router(Experience, "/api/experiences", "Expériences"))
app.include_router(make_crud_router(Education, "/api/educations", "Formations"))
app.include_router(make_crud_router(Skill, "/api/skills", "Compétences"))
app.include_router(make_crud_router(Project, "/api/projects", "Projets"))
app.include_router(make_crud_router(Language, "/api/languages", "Langues"))


# ---------- Import LinkedIn ----------
def _apply_linkedin_import(session: Session, profile: Profile, profile_id: int, data: dict) -> dict:
    profile_updated = False
    for key, value in data["profile"].items():
        if not getattr(profile, key, ""):
            setattr(profile, key, value)
            profile_updated = True
    if profile_updated:
        session.add(profile)

    counts = {"experiences": 0, "educations": 0, "skills": 0, "languages": 0}
    for exp in data["experiences"]:
        session.add(Experience(profile_id=profile_id, **exp))
        counts["experiences"] += 1
    for edu in data["educations"]:
        session.add(Education(profile_id=profile_id, **edu))
        counts["educations"] += 1
    for sk in data["skills"]:
        session.add(Skill(profile_id=profile_id, **sk))
        counts["skills"] += 1
    for lang in data["languages"]:
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


@app.post("/api/generate-cv/html", response_class=HTMLResponse)
def generate_cv_html(payload: dict = Body(default={}), session: Session = Depends(get_session)):
    offer_text = payload.get("offer_text", "")
    profile_id = int(payload.get("profile_id", 1))
    context = build_cv_context(*_gather(session, profile_id), offer_text=offer_text)
    template = jinja_env.get_template("cv_template.html")
    return template.render(**context)


@app.post("/api/generate-cv/docx")
def generate_cv_docx(payload: dict = Body(default={}), session: Session = Depends(get_session)):
    offer_text = payload.get("offer_text", "")
    profile_id = int(payload.get("profile_id", 1))
    context = build_cv_context(*_gather(session, profile_id), offer_text=offer_text)
    doc = build_docx(context)
    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    filename = f"CV_{context['profile'].full_name.replace(' ', '_') or 'export'}.docx"
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------- Frontend statique ----------
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
