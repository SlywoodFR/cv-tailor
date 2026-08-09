# cv-tailor

Application locale pour centraliser des infos perso (profil, expériences, formations,
compétences, projets, langues) dans une base SQLite, les modifier à tout moment via une
interface web, et générer un CV (3 mises en page au choix) et une lettre de motivation
automatiquement adaptés à une offre d'emploi collée en texte.

Le générateur repère les mots-clés de l'offre, met en avant les compétences correspondantes,
réordonne les puces d'expérience pour faire remonter les plus pertinentes, et sélectionne
les projets les plus proches de l'offre. Sans offre collée, il génère un CV générique. Les
offres pour lesquelles un CV a été téléchargé sont conservées dans un historique par profil.

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

Optionnel, pour activer le [mode IA](#mode-ia-traduction--rédaction-par-un-llm) : copier
`.env.example` en `.env` et renseigner une ou plusieurs de `ANTHROPIC_API_KEY`,
`OPENAI_API_KEY`, `GEMINI_API_KEY`. Sans ce fichier (ou avec les trois variables vides), l'app
fonctionne normalement en mode mécanique uniquement. `GEMINI_API_KEY` est la plus simple à
obtenir sans frais : une clé gratuite sur [aistudio.google.com](https://aistudio.google.com/)
(aucune carte bancaire requise) donne accès à Gemini Flash avec un quota quotidien généreux.

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
   ses propres expériences, formations, compétences, projets, langues et certifications,
   isolés des autres.
1. Onglet **Profil** : renseigner les coordonnées et le résumé.
2. Onglets **Expériences / Formations / Compétences / Projets / Langues / Certifications** :
   ajouter les entrées (pour les compétences et projets, renseigner des mots-clés pertinents —
   c'est ce sur quoi se base le matching avec les offres).
3. Onglet **Générer un CV** : coller le texte d'une offre d'emploi, choisir une mise en page
   (Classique, Moderne 2 colonnes, ou Compact — uniquement pour l'aperçu et le PDF, le .docx
   garde une seule mise en page) et un mode de génération (Mécanique, ou IA si une clé est
   configurée — voir [Mode IA](#mode-ia-traduction--rédaction-par-un-llm) ci-dessous), cliquer
   sur "Aperçu", puis "Télécharger en PDF" (prêt à envoyer) ou "Télécharger en .docx" (pour
   retoucher le texte dans Word avant export).
   - **Lettre de motivation** : à partir de la même offre collée au-dessus, génère un brouillon
     de lettre (coordonnées, accroche, expériences et compétences qui matchent l'offre, formules
     de politesse). En mode mécanique (par défaut, sans clé IA configurée) : un gabarit rempli
     automatiquement, à relire et personnaliser avant envoi — pas un texte poli prêt à l'emploi.
     En mode IA : une lettre entièrement rédigée par le modèle choisi.
   - **Historique des offres** : chaque CV téléchargé (PDF ou .docx) pour une offre non vide est
     enregistré (texte de l'offre + date, pas de copie du fichier). "Réutiliser" recolle le texte
     de l'offre pour regénérer — avec les données de profil *actuelles*, qui peuvent différer de
     celles utilisées lors du téléchargement d'origine si le profil a changé depuis.

### Mode IA (traduction + rédaction par un LLM)

Par défaut, la génération est 100% mécanique et locale : matching par mots-clés, aucune donnée
n'est envoyée où que ce soit. En configurant au moins une clé API (Anthropic, OpenAI et/ou
Google Gemini — voir [Installation](#installation)), un mode IA optionnel apparaît dans le
sélecteur "Mode" de l'onglet **Générer un CV**, avec une option par fournisseur configuré — un
seul appel au modèle choisi qui sélectionne le contenu pertinent par rapport à l'offre ET le
rédige, dans la langue de l'offre (traduction automatique si l'offre est dans une langue
différente du profil). Sans offre collée, le mode IA se contente de reformuler légèrement, dans
la langue d'origine du profil.

À savoir avant d'activer ce mode :
- **Premier clic sur "Aperçu"/"Télécharger en PDF"/"Télécharger en .docx" déclenche un vrai appel**
  au fournisseur choisi, et peut prendre jusqu'à une minute. Tant que le profil et l'offre collée
  ne changent pas, les clics suivants (ex. "Aperçu" puis "Télécharger en PDF" juste après)
  réutilisent le résultat déjà généré au lieu de rappeler le modèle — un changement (édition du
  profil, texte d'offre différent, autre fournisseur) régénère automatiquement. Payant pour
  Anthropic/OpenAI ; Gemini a un niveau gratuit (voir Installation) mais avec des quotas
  quotidiens limités.
- **Confidentialité** : en mode IA, le profil complet (coordonnées, expériences, formations,
  compétences) et le texte de l'offre quittent le serveur vers le fournisseur choisi. En mode
  mécanique, rien ne sort du serveur. Sur le niveau gratuit de Gemini spécifiquement, les
  conditions de Google autorisent l'utilisation des données envoyées/reçues pour améliorer leurs
  modèles — à garder en tête si le contenu du profil est sensible.
- Le modèle ne peut que sélectionner/réordonner/traduire les données du profil, jamais en
  inventer (aucune expérience, compétence ou diplôme fictif).
- Export PDF et scripts non-latins : les polices installées dans le `Dockerfile`
  (`fonts-dejavu-core`) ne couvrent que les scripts latins/cyrillique/grec. Un CV traduit en
  japonais, arabe, etc. s'affiche correctement en aperçu HTML et en .docx (polices du système
  qui l'ouvre), mais peut afficher des glyphes manquants dans l'export **PDF** généré côté
  serveur (WeasyPrint) — ajouter des polices adaptées (ex. `fonts-noto-cjk`) au `Dockerfile` si
  besoin.

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

## Déploiement en production (Unraid + Cloudflare Tunnel)

L'app n'a **aucune authentification intégrée** : n'importe qui atteignant l'URL peut voir et
modifier toutes les données de tous les profils. En production, l'accès doit donc être verrouillé
en amont par **Cloudflare Access**, pas seulement par l'obscurité de l'URL. Le tunnel Cloudflare
évite en plus d'ouvrir le moindre port sur le NAS ou la box : le conteneur `cv-tailor` n'est
joignable que par `cloudflared`, via le réseau Docker interne.

### 1. Récupérer le projet sur le NAS

En SSH sur Unraid, dans un dossier persistant (ex. `/mnt/user/appdata/`) :

```bash
git clone <url-de-ton-repo-github> cv-tailor
cd cv-tailor
cp .env.example .env
```

### 2. Créer le tunnel Cloudflare

Sur [le dashboard Cloudflare Zero Trust](https://one.dash.cloudflare.com/) :

1. **Networks → Tunnels → Create a tunnel**, type "Cloudflared", nom `cv-tailor`.
2. Choisir l'environnement **Docker** : Cloudflare affiche une commande `docker run ... --token
   eyJ...`. Copier uniquement la valeur après `--token` dans `.env`, sur la ligne
   `CLOUDFLARE_TUNNEL_TOKEN=`.
3. Onglet **Public Hostname** du tunnel : Subdomain (ex. `cv`), Domain = ton domaine, Type
   `HTTP`, URL `cv-tailor:8000` (nom du service Docker Compose, résolu par le réseau Docker
   interne — pas une IP).

### 3. Restreindre l'accès avec Cloudflare Access

Toujours dans Zero Trust : **Access → Applications → Add an application → Self-hosted**.
- Domain : le même hostname que ci-dessus (`cv.tondomaine.com`).
- Policy : Action `Allow`, Include → **Emails** → lister les deux adresses email (la tienne et
  celle de ta copine).

Résultat : quiconque visite `cv.tondomaine.com` doit d'abord prouver qu'il possède l'une de ces
deux adresses (code reçu par email) avant que Cloudflare ne relaie la moindre requête vers
l'app. Ni mot de passe à gérer, ni compte à créer, et ça bloque tout le monde d'autre.

### 4. Désactiver le cache Cloudflare pour ce domaine

cv-tailor est une app dynamique (pas un site statique), et Cloudflare met par défaut en cache
certains fichiers (`.js`, `.css`, `.html`) au niveau de son CDN, **indépendamment** des en-têtes
`Cache-Control` renvoyés par le serveur. Résultat concret déjà rencontré : après une mise à jour
et un `docker compose up -d --build`, le navigateur peut continuer à recevoir l'ancienne version
de l'app pendant un moment (ou indéfiniment sur certains réseaux), sans qu'aucun vidage de cache
navigateur ne change quoi que ce soit — puisque le cache est côté Cloudflare, pas côté client.

Pour éviter d'avoir à purger le cache manuellement après chaque mise à jour : dans le dashboard
Cloudflare, sur la zone du domaine → **Caching → Configuration → Cache Rules → Create rule**,
créer une règle qui matche le hostname `cv.tondomaine.com` avec l'action **Bypass cache**.
Alternative plus rapide mais ponctuelle : **Caching → Configuration → Purge Everything** après
chaque déploiement.

### 5. Lancer les conteneurs

```bash
docker compose up -d --build
```

(Unraid récent inclut `docker compose` par défaut ; sinon installer le plugin **Compose
Manager** depuis Community Applications, ou lancer la commande via SSH comme ci-dessus — les
deux fonctionnent avec le même `docker-compose.yml`.)

Les données persistent dans `./data/cvtailor.db` (monté en volume), donc `docker compose up -d
--build` ne perd jamais les données lors d'une mise à jour.

### 6. Mettre à jour l'app plus tard

```bash
cd /mnt/user/appdata/cv-tailor
git pull
docker compose up -d --build
```

### Accès en LAN sans passer par Cloudflare (optionnel)

Par défaut `docker-compose.yml` n'expose aucun port sur l'hôte. Pour un accès direct depuis le
réseau local (plus rapide, sans écran Cloudflare Access), ajouter dans le service `cv-tailor` :

```yaml
    ports:
      - "8000:8000"
```

Attention : ça rend l'app accessible à quiconque est sur le réseau local **sans** la protection
de Cloudflare Access — acceptable sur un réseau domestique de confiance, à éviter sinon.

## Structure du projet

```
cv-tailor/
  backend/
    main.py            -> app FastAPI, routes API + génération de CV
    models.py           -> modèles de données (SQLModel)
    database.py          -> connexion SQLite
    crud_factory.py       -> routes CRUD génériques
    cv_generator.py        -> extraction de mots-clés + scoring de pertinence
    letter_generator.py     -> sélection du contenu de la lettre de motivation (même moteur)
    docx_generator.py       -> génération du CV et de la lettre au format Word
    linkedin_import.py      -> lecture de l'export de données LinkedIn (.zip)
    linkedin_api_import.py    -> import via la Member Data Portability API (UE/EEE/Suisse)
    ai_generator.py         -> mode IA : sélection + rédaction/traduction via Anthropic/OpenAI
    templates/
      cv_template.html         -> mise en page "Classique"
      cv_template_moderne.html  -> mise en page "Moderne" (2 colonnes)
      cv_template_compact.html  -> mise en page "Compact"
      letter_template.html      -> gabarit de la lettre de motivation (mode mécanique)
      letter_template_ai.html    -> gabarit de la lettre de motivation (mode IA)
  frontend/
    index.html / app.js / style.css -> interface web (aucune dépendance externe)
  data/
    cvtailor.db  -> base SQLite (créée automatiquement)
  Dockerfile          -> image de l'app (inclut les libs système pour l'export PDF)
  docker-compose.yml   -> app + tunnel Cloudflare (cloudflared), voir "Déploiement"
  .env.example          -> modèle pour le token du tunnel Cloudflare + les clés IA optionnelles
```

## Développement

Projet conçu et développé avec l'assistance de [Claude Code](https://claude.com/claude-code)
(Anthropic) : définition de l'architecture, implémentation du backend/frontend, ajout du
support multi-profils et revue du code se sont faits en collaboration avec l'outil, avec
relecture et validation de chaque étape.
