# cv-tailor

Application locale pour centraliser des infos perso (profil, expériences, formations,
compétences, projets, langues) dans une base SQLite, les modifier à tout moment via une
interface web, et générer un CV automatiquement adapté à une offre d'emploi collée en texte.

Le générateur repère les mots-clés de l'offre, met en avant les compétences correspondantes,
réordonne les puces d'expérience pour faire remonter les plus pertinentes, et sélectionne
les projets les plus proches de l'offre. Sans offre collée, il génère un CV générique.

## Installation

Nécessite Python 3.10+.

```bash
cd cv-tailor
pip install -r requirements.txt
```

## Lancer l'application

```bash
cd backend
uvicorn main:app --reload
```

Puis ouvrir http://127.0.0.1:8000 dans un navigateur.

La base de données (`data/cvtailor.db`) est créée automatiquement au premier lancement.

## Utilisation

0. En haut de la barre latérale, choisir un profil dans le menu déroulant ou en créer un
   nouveau avec **+ Profil** (un par personne, ex. deux prénoms différents). Chaque profil a
   ses propres expériences, formations, compétences, projets et langues, isolés des autres.
1. Onglet **Profil** : renseigner les coordonnées et le résumé.
2. Onglets **Expériences / Formations / Compétences / Projets / Langues** : ajouter les entrées
   (pour les compétences et projets, renseigner des mots-clés pertinents — c'est ce sur quoi
   se base le matching avec les offres).
3. Onglet **Générer un CV** : coller le texte d'une offre d'emploi, cliquer sur "Aperçu" pour
   voir le rendu, puis "Télécharger en .docx" pour récupérer un fichier Word éditable
   (exportable en PDF depuis Word via "Enregistrer sous").

## Structure du projet

```
cv-tailor/
  backend/
    main.py            -> app FastAPI, routes API + génération de CV
    models.py           -> modèles de données (SQLModel)
    database.py          -> connexion SQLite
    crud_factory.py       -> routes CRUD génériques
    cv_generator.py        -> extraction de mots-clés + scoring de pertinence
    docx_generator.py       -> génération du CV au format Word
    templates/cv_template.html -> gabarit HTML du CV
  frontend/
    index.html / app.js / style.css -> interface web (aucune dépendance externe)
  data/
    cvtailor.db  -> base SQLite (créée automatiquement)
```

## Pistes d'évolution

- Export PDF direct (actuellement HTML + DOCX, à convertir en PDF via le navigateur ou Word)
- Plusieurs modèles de mise en page de CV
- Historique des CV générés par offre
- Lettre de motivation générée sur le même principe

## Développement

Projet conçu et développé avec l'assistance de [Claude Code](https://claude.com/claude-code)
(Anthropic) : définition de l'architecture, implémentation du backend/frontend, ajout du
support multi-profils et revue du code se sont faits en collaboration avec l'outil, avec
relecture et validation de chaque étape.
