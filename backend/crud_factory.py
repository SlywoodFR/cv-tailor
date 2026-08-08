"""Fabrique de routes CRUD génériques pour éviter de dupliquer le code
pour chaque type d'entrée (Experience, Education, Skill, Project, Language).
"""
from typing import Type
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlmodel import SQLModel, Session, select

from database import get_session


def make_crud_router(model: Type[SQLModel], prefix: str, tag: str) -> APIRouter:
    router = APIRouter(prefix=prefix, tags=[tag])

    # NB: on reçoit le body en dict brut puis on passe par model.model_validate()
    # plutôt que "item: model" directement dans la signature -- avec les modèles
    # SQLModel table=True, FastAPI construit l'objet sans repasser par la
    # validation pydantic (les dates restent des str et cassent l'insertion SQLite).
    @router.get("/", response_model=list[model])
    def list_items(profile_id: int, session: Session = Depends(get_session)):
        return session.exec(select(model).where(model.profile_id == profile_id)).all()

    @router.post("/", response_model=model)
    def create_item(profile_id: int, payload: dict = Body(...), session: Session = Depends(get_session)):
        payload.pop("id", None)
        payload["profile_id"] = profile_id
        item = model.model_validate(payload)
        session.add(item)
        session.commit()
        session.refresh(item)
        return item

    @router.put("/{item_id}", response_model=model)
    def update_item(item_id: int, payload: dict = Body(...), session: Session = Depends(get_session)):
        db_item = session.get(model, item_id)
        if not db_item:
            raise HTTPException(status_code=404, detail=f"{tag} introuvable")
        payload.pop("id", None)
        payload.pop("profile_id", None)  # le profil propriétaire ne change pas via update
        validated = model.model_validate({**db_item.model_dump(), **payload})
        for key, value in validated.model_dump(exclude={"id"}).items():
            setattr(db_item, key, value)
        session.add(db_item)
        session.commit()
        session.refresh(db_item)
        return db_item

    @router.delete("/{item_id}")
    def delete_item(item_id: int, session: Session = Depends(get_session)):
        db_item = session.get(model, item_id)
        if not db_item:
            raise HTTPException(status_code=404, detail=f"{tag} introuvable")
        session.delete(db_item)
        session.commit()
        return {"ok": True}

    return router
