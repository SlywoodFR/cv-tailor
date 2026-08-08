"""Modèles de données pour cv-tailor.

Un seul profil (l'utilisateur) avec des listes d'expériences, formations,
compétences, projets et langues rattachées.
"""
from datetime import date
from typing import Optional, List

from sqlmodel import SQLModel, Field, Relationship


class Profile(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    full_name: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    linkedin: str = ""
    github: str = ""
    website: str = ""
    summary: str = ""  # accroche / résumé en tête de CV

    experiences: List["Experience"] = Relationship(back_populates="profile")
    educations: List["Education"] = Relationship(back_populates="profile")
    skills: List["Skill"] = Relationship(back_populates="profile")
    projects: List["Project"] = Relationship(back_populates="profile")
    languages: List["Language"] = Relationship(back_populates="profile")


class Experience(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    profile_id: Optional[int] = Field(default=None, foreign_key="profile.id")
    company: str = ""
    role: str = ""
    location: str = ""
    start_date: Optional[date] = None
    end_date: Optional[date] = None  # None = en cours
    # bullets séparés par des retours à la ligne
    description: str = ""
    # mots-clés séparés par des virgules, utilisés pour le matching
    tags: str = ""

    profile: Optional[Profile] = Relationship(back_populates="experiences")


class Education(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    profile_id: Optional[int] = Field(default=None, foreign_key="profile.id")
    school: str = ""
    degree: str = ""
    field: str = ""
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    description: str = ""

    profile: Optional[Profile] = Relationship(back_populates="educations")


class Skill(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    profile_id: Optional[int] = Field(default=None, foreign_key="profile.id")
    name: str = ""
    category: str = ""  # ex: "Langages", "Frameworks", "Outils", "Soft skills"
    level: str = ""  # ex: "Débutant", "Intermédiaire", "Avancé"

    profile: Optional[Profile] = Relationship(back_populates="skills")


class Project(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    profile_id: Optional[int] = Field(default=None, foreign_key="profile.id")
    name: str = ""
    description: str = ""
    tags: str = ""
    link: str = ""

    profile: Optional[Profile] = Relationship(back_populates="projects")


class Language(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    profile_id: Optional[int] = Field(default=None, foreign_key="profile.id")
    name: str = ""
    level: str = ""  # ex: "Natif", "Courant", "B2"

    profile: Optional[Profile] = Relationship(back_populates="languages")
