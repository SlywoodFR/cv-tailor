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

L'export PDF utilise [WeasyPrint](https://weasyprint.org/), qui dépend de bibliothèques
système (Pango/cairo) en plus du `pip install` ci-dessus. Sur Debian/Ubuntu :

```bash
sudo apt-get install libpango-1.0-0 libpangoft2-1.0-0 libgdk-pixbuf-2.0-0 libcairo2 fonts-dejavu-core
```

Sans ces bibliothèques, tout le reste de l'application fonctionne normalement — seul le bouton
"Télécharger en PDF" échouera (l'export .docx reste disponible dans tous les cas).

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
   voir le rendu, puis "Télécharger en PDF" (prêt à envoyer) ou "Télécharger en .docx" (pour
   retoucher le texte dans Word avant export).

### Importer depuis LinkedIn

LinkedIn ne propose aucune API ouverte permettant de récupérer expériences, formations ou
compétences (fermée aux tiers depuis 2015) — l'import passe donc par l'export officiel des
données que chaque utilisateur peut demander pour son propre compte :

1. Sur linkedin.com : photo de profil (ou "Moi") en haut à droite → **Paramètres et
   confidentialité** → **Confidentialité des données** → **Obtenir une copie de vos données**.
2. Choisir **Télécharger l'ensemble de vos données**, valider. LinkedIn envoie par email (de
   quelques minutes à 24h) un lien vers un fichier `.zip`.
3. Dans l'onglet **Profil**, section "Importer depuis LinkedIn", téléverser ce `.zip`
   directement (inutile de le décompresser).

L'import ajoute au profil actif les expériences, formations, compétences et langues trouvées
(sans supprimer l'existant) et complète les champs de profil encore vides. Les entrées déjà
présentes ne sont pas dupliquées : une expérience est reconnue par entreprise + poste, une
formation par école + diplôme, une compétence ou langue par son nom (comparaison insensible à
la casse) — ré-importer le même export plusieurs fois, ou passer du zip à l'API LinkedIn, ne
crée donc pas de doublons.

#### Alternative : import via l'API LinkedIn (membres UE/EEE/Suisse)

LinkedIn propose depuis 2024 une API de portabilité des données ("Member Data Portability
API"), réservée par obligation réglementaire (DMA) aux membres localisés en UE/EEE ou en
Suisse. Elle évite d'attendre l'email d'export, au prix d'une configuration ponctuelle :

1. Créer une app sur [linkedin.com/developers/apps](https://www.linkedin.com/developers/apps),
   obligatoirement rattachée à la page entreprise
   **"Member Data Portability (Member) Default Company"** fournie par LinkedIn (ne pas créer
   de nouvelle page).
2. Dans l'onglet **Products** de l'app, demander l'accès à
   **"Member Data Portability API (Member)"** (accordé automatiquement après acceptation des
   CGU, pas d'attente de validation).
3. Dans **Docs and tools → OAuth Token Tools**, générer un access token pour cette app avec le
   scope `r_dma_portability_self_serve`, et consentir depuis l'écran LinkedIn qui s'affiche.
4. Coller ce token dans le bloc "Ou importer via l'API LinkedIn" de l'onglet Profil.

Le token n'est jamais stocké côté serveur (il ne sert que le temps de la requête) et expire
au bout de 60 jours — à régénérer manuellement ensuite via le même outil. Chaque personne doit
suivre cette procédure avec son propre compte LinkedIn pour importer son propre profil.

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
    linkedin_import.py      -> lecture de l'export de données LinkedIn (.zip)
    linkedin_api_import.py    -> import via la Member Data Portability API (UE/EEE/Suisse)
    templates/cv_template.html -> gabarit HTML du CV
  frontend/
    index.html / app.js / style.css -> interface web (aucune dépendance externe)
  data/
    cvtailor.db  -> base SQLite (créée automatiquement)
```

## Pistes d'évolution

- Plusieurs modèles de mise en page de CV
- Historique des CV générés par offre
- Lettre de motivation générée sur le même principe

## Développement

Projet conçu et développé avec l'assistance de [Claude Code](https://claude.com/claude-code)
(Anthropic) : définition de l'architecture, implémentation du backend/frontend, ajout du
support multi-profils et revue du code se sont faits en collaboration avec l'outil, avec
relecture et validation de chaque étape.
