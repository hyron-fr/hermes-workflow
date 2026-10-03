---
type: context
status: draft
tags: [architecture, discord, notification, thread, cadrage]
issues: [19]
---

# Cadrage architectural — issue #19 « Discord thread title and description update »

## Positionnement (cadre exact)

L'issue #19 demande de faire évoluer **le titre et la description** du thread
Discord d'une issue en fonction de **l'état** de cette issue. Le format a été
**arbitré par l'humain** le 02/10/2026 (Q1 = 1a, Q2 = 2b, Q3 = d) et
**matérialisé** par une maquette inerte versionnée dans ce vault
(`issue-19-maquette.html` + `issue-19-maquette.measure.py`, commit `12abc16`).

**Contrat arbitré du titre** (Q1 = 1a) :

```
<icône> <repo>|#<numéro d'issue>|<titre de l'issue>
  - 🎬 démarrage — jusqu'à la validation du plan
  - ⚙️ in progress — les agents travaillent
  - ⚠ bloqué — une intervention humaine est requise
  - 🛑 terminé
```

L'identité (`<repo>|#<n>`) est **fixe d'un état à l'autre** : seule l'icône
change. Le `<titre>` vient de l'issue GitHub, jamais de la carte kanban.
La spec initiale proposait `👆` pour l'intervention humaine ; l'arbitrage
**Q3 = d** l'a remplacé par `⚠` — le token `👆` est déclaré **obsolète** au
registre de la maquette, et tout marqueur candidat non retenu (`1b`, `1c`)
doit rester absent du rendu.

**Contrat arbitré de la description** (Q2 = 2b) : un **message dédié épinglé**
dans le thread — jamais le champ `topic` (mesuré : `PATCH {"topic": …}` → 200
puis `topic = None`, la valeur est jetée en silence), et l'accueil du thread
reste intact. Trois lignes, chacune **omise** si non résolue (jamais de
placeholder) :

```
Issue    : URL d'import de la carte racine, repli gh issue view N --json url
Branche  : specs/<n>/slices.json → clé branch (déclarée une fois par issue)
PR       : gh pr list --repo <org>/<repo> --head <branche> --json url
```

C'est une **évolution de la surface de notification Discord**, pas une nouvelle
fonctionnalité métier : le pipeline produit déjà un thread par issue, le
renomme déjà à chaque transition d'étape, et poste déjà du contenu déterministe
dedans. L'issue #19 **change la forme** (format de titre, contenu de
description) et **enrichit la sémantique d'état** (ajout des états « démarrage »
et « intervention humaine requise »), sans toucher au cœur de décision.

**Écart mesuré entre la spec et l'existant (à nommer, pas à trancher ici)** :

| axe | existant (`pipeline/engine.py`) | demandé par #19 (arbitré) |
|---|---|---|
| format de titre | `{icon} {status} - issue {N} {title}` | `<icône> <repo>\|#<n>\|<titre>` (Q1 = 1a) |
| icônes d'état | ⚙️ running / ✅ done / ❌ fail / 🔁 retry | 🎬 démarrage / ⚙️ travail / ⚠ intervention / 🛑 terminé (Q3 = d) |
| description | aucune (le helper ne pose pas de description ; seul le message d'accueil existe) | message dédié épinglé : issue + branche + PR (Q2 = 2b) |

La spec **remplace** le couple (format, jeu d'icônes) existant ; elle ne
l'étend pas. La spec initiale proposait `👆` pour l'intervention humaine ;
l'arbitrage **Q3 = d** l'a remplacé par `⚠`. Deux des quatre icônes arbitrées
(🎬, ⚠) n'ont **aucun équivalent** dans le jeu actuel (qui distingue `fail` et
`retry` au lieu de « démarrage » et « intervention humaine ») : la spec
réintroduit l'**état « attend l'humain »** dans le titre (aujourd'hui exprimé
seulement par `pj_escalate.py` qui *poste* un message d'escalade, sans toucher
le titre).

## Croisement infrastructure / fonctionnel / code

### Infrastructure (frontières traversées)

- **Discord REST** — le thread est créé (`POST /channels/<channel_id>/threads`)
  et renommé (`PATCH /channels/<id>` avec `{"name": …}`) par le helper
  `discord_thread.py`, présent en **deux copies** : la versionnée
  `skills/gh-kanban-bridge/scripts/discord_thread.py` (profil gh-triage) et la
  copie runtime `~/.hermes/scripts/discord_thread.py` (profil pj-master). Les
  deux **divergent déjà** (le helper runtime ajoute `delete`, un `prefix` de
  schéma `pj:<…>` vs `triage:<…>`, et un `guild_id` par défaut en dur). Le
  helper **ne sait pas poser de « description » de thread** : il n'expose que
  `create` (nom + message d'accueil), `send`, `rename`, `threads`, `delete`.
  Un thread public (type 11) Discord n'a pas de champ « description » distinct
  du nom — c'est pourquoi l'arbitrage **Q2 = 2b** a tranché pour un **message
  dédié épinglé** (jamais le champ `topic`, mesuré : `PATCH {"topic": …}` → 200
  puis `topic = None`, jeté en silence), l'accueil restant intact.
- **Git / GitHub** — la description demandée (lien issue, branche, lien PR) exige
  de lire **l'état git** de l'issue (branche du worktree, PR ouverte). Ces
  données ne sont **pas** toutes disponibles dans le `ticket` kanban chargé par
  `ticket_context()` (qui ne connaît que `title`, `body`, `status`,
  `issue_number` déduit de la ligne « Importé depuis <url> »). L'arbitrage
  **Q2 = 2b** a fixé les sources : l'URL d'import de la carte racine (repli
  `gh issue view N --json url`), `specs/<n>/slices.json` → clé `branch`, et
  `gh pr list --repo <org>/<repo> --head <branche> --json url`. La branche et la
  PR sont des **informations de slice/de PR**, produites plus tard dans le
  cycle (t1 crée le worktree, t6 ouvre la PR) : une ligne non résolue est
  **omise**, jamais remplacée par un placeholder.

### Fonctionnel (capacité traversée)

La capacité traversée est **« notification d'état d'issue sur Discord »**,
aujourd'hui portée par **deux** producteurs distincts :

1. `pipeline/engine.py` — `notify_step()` poste le statut d'étape et
   `rename_thread()` renomme le thread à chaque transition (running/done/fail/
   retry) pendant l'exécution du workflow YAML (`workflows/*.yaml`).
2. `pipeline/pj_escalate.py` — `build_message()`/`post()` escalade une carte
   bloquée en postant **un message** dans le thread de son issue, **sans**
   renommer le thread.

La spec #19 unifie le **titre** comme vecteur d'état (aujourd'hui seulement le
renommage d'étape du moteur) et ajoute le **contenu descriptif** (aujourd'hui
seulement le message d'accueil du poll, puis les messages de progression). Elle
élargit donc la responsabilité du titre aux états « démarrage » et « attend
l'humain » que le moteur ne distingue pas aujourd'hui (un blocage → `fail` ou
escalade, jamais un état « ⚠ » dans le titre).

### Code (composants, ports, adapters)

- **`pipeline/engine.py`** — cœur du renommage actuel :
  - `resolve_thread(issue_number)` retrouve le thread par **nom** via le motif
    `issue\s*#?\s*<N>` (insensible à la casse) ;
  - `rename_thread(ticket, step, outcome, dry_run, labels)` compose le nom
    `{label} - issue {N} {title}` et PATCH via le helper ;
  - `DEFAULT_STATUS_LABELS` = `{running: "⚙️ running", done: "✅ done",
    fail: "❌ fail", retry: "🔁 retry"}`, surchargés par la clé `status` du YAML.
  Ce module n'existe **que** sous `pipeline/` (pas de copie `bridge/engine.py`).
- **`pipeline/pj_escalate.py`** — `thread_index(cfg)` résout `(repo, issue) →
  thread_id` par le motif `repo\s+#\d+` dans le nom du thread, et `post()` envoie
  le message d'escalade. C'est l'un des trois consommateurs du nom du thread.
- **`pipeline/gh_triage_poll.py`** — crée le thread initial au format `🎫 Issue
  #<N> — <titre>` (via le SOUL gh-triage), point de départ du cycle de vie du
  nom.
- **Helper `discord_thread.py`** (2 copies) — adapter REST : `create` / `send` /
  `rename` / `threads` / `delete`. `rename` est la seule écriture de nom ;
  **aucune** écriture de description/topic n'existe.

## Lecture SDD (spec-driven)

La spec (body de l'issue) est la source de vérité, **précisée par l'arbitrage
humain du 02/10/2026** (Q1 = 1a, Q2 = 2b, Q3 = d). Le format **arbitré** est
littéral — `<icône> <repo>|#<numéro d'issue>|<titre de l'issue>` — avec un jeu
d'icônes fermé (🎬 ⚙️ ⚠ 🛑) et une description en **message dédié épinglé**
(3 lignes : issue / branche / PR). Deux contrats restent à figer dans le code :

1. la **forme exacte du titre** (séparateur `|`, ordre `repo|#n|titre`, icône en
   tête, identité fixe d'un état à l'autre) — vérifiable par une fonction de
   formatage pure, pas par un appel réseau ;
2. la **table d'état → icône** (4 états, bijection) — testable sans Discord.

Le format **n'existe pas encore dans le code** : il est matérialisé par la
maquette inerte `issue-19-maquette.html` (versionnée, commit `12abc16`) et
mesuré par `issue-19-maquette.measure.py`, qui figent **les totaux** (préfixe
22 car., 23 avec ⚙️, budget de titre 78, nom actuel 65) et **les 3 lecteurs du
nom** (`engine.resolve_thread`, `pj_escalate.thread_index`,
`pj-buttons.THREAD_NAME_RE`) comme contrat rejouable avant toute implémentation.
La maquette est un **objectif arbitré**, pas un constat du livré.

## Lecture DDD

Pas d'agrégat ni d'entité de domaine : le thread Discord est un **artefact
d'infrastructure**, un miroir de l'état de l'issue. Les seules notions
pertinentes :

- **Value object** — le **nom du thread** (chaîne formatée). C'est lui qui
  porte l'état et qui est **consommé en lecture** par `resolve_thread`,
  `thread_index` et `THREAD_NAME_RE` pour retrouver le thread. Sa **grammaire
  est un contrat** : la changer (format `|` au lieu de « issue N ») casse
  silencieusement les trois résolveurs qui le parsent — c'est le point de
  fragilité central de #19.
- **Domain event** — la **transition d'état** de l'issue (démarrage → travail →
  intervention humaine → terminé). Aujourd'hui la transition « attend l'humain »
  n'existe pas comme état de titre ; elle n'est matérialisée que par l'envoi
  d'un message (`pj_escalate.py`) et le `kanban_block`.

## Lecture TDD (contrat testable)

Les contrats à figer sont **purs** (aucun réseau, aucune horloge) :

1. **formateur de titre** : `title_icon(état) → icône` et
   `format_title(repo, ticket, title, état) → "<icône> <repo>|#<ticket>|<title>"`
   — testables sur les 4 états + les cas limites (titre vide, ticket non
   numérique, séparateur `|` présent dans le titre d'origine → échappement ?).
2. **table d'état → icône** : bijection, une icône par état, `⚠` uniquement pour
   « intervention humaine » (pas pour `fail`/`retry`), `🛑` pour terminé.
   Le token `👆` est **obsolète** (arbitrage Q3 = d) : aucun état ne doit plus
   le produire.
3. **rétro-compatibilité des résolveurs** : `resolve_thread`, `thread_index` et
   `THREAD_NAME_RE` (pj-buttons) doivent **continuer** à retrouver le thread
   après le changement de format. C'est le contrat de non-régression critique :
   les trois parseurs actuels (`issue #N`, `repo #N`, `^repo #N`) **ne matchent
   plus** le format `repo|#N|title` — mesuré sur la maquette : les 3 lecteurs
   rendent `None` sur le nouveau format. Le RED ici est « un thread renommé au
   nouveau format n'est plus retrouvé » — le GREEN doit couvrir **les deux
   formats** (les 18 fils vivants portent l'ancien `hermes-workflow #N · …`),
   ou faire évoluer les résolveurs dans la même slice.

Le RED/GREEN de l'issue : tant qu'un résolveur ne retrouve pas un thread
renommé `<icône> <repo>|#<n>|<titre>`, l'issue n'est pas résolue — le
renommage seul (sans mise à jour des trois consommateurs du nom) est un faux
vert qui casse la notification d'étape, l'escalade et les boutons de décision.

## Lecture hexagonale

La frontière à respecter est **la frontière formatage pur / adapter Discord** :
la grammaire du titre et la table d'état→icône sont des **fonctions pures**
(core), sans dépendance DOM/réseau/fichier ; l'écriture du nom (`PATCH`) et la
résolution du thread (`GET threads`) restent dans l'**adapter** `discord_thread.py`.
Aucune décision nouvelle ne doit être déplacée dans l'adapter : il reçoit un nom
déjà formaté, il ne le construit pas. La description (issue + branche + PR) est
une **lecture d'état** (gh/git/blackboard) qui doit être résolue **hors** du
core, puis injectée.

## Composants impactés par l'issue #19

- `pipeline/engine.py` — **à faire évoluer** : `rename_thread` (nouveau format +
  nouvelle table d'icônes), `resolve_thread` (consommateur du nom, à rendre
  compatible), `DEFAULT_STATUS_LABELS` (jeu d'icônes à remplacer/étendre).
- `pipeline/pj_escalate.py` — **exercé** : `thread_index` (consommateur du nom) ;
  potentiellement à faire évoluer pour distinguer l'état « ⚠ » dans le titre.
- `plugins/pj-buttons/pj-buttons/__init__.py` — **exercé** : `THREAD_NAME_RE`
  (`^\s*([A-Za-z0-9._-]+)\s*#(\d+)`), troisième lecteur du nom, matche l'ancien
  format mais rend `None` sur le nouveau (mesuré sur la maquette).
- `pipeline/gh_triage_poll.py` + SOUL gh-triage — **producteur du nom initial**
  (`🎫 Issue #N — …`), point d'entrée du cycle de vie du titre.
- Helper `discord_thread.py` (2 copies) — **adapter** : `rename` (déjà là),
  **aucun** support de description/topic à ce jour ; à étendre si la spec exige
  une vraie description.
- `pipeline/engine.py` seul n'a **pas** de miroir `bridge/engine.py` (les autres
  `pj_*.py` sont en quasi-duplication bridge↔pipeline, seul `pj_graphwatch`
  diverge) — le périmètre code de #19 est donc `pipeline/`, pas `bridge/`.

## Ambiguïtés — résolues par l'arbitrage, ou restantes

**Résolues par l'arbitrage humain du 02/10/2026** (maquette, commit `12abc16`) :

1. **« description » du thread** → **Q2 = 2b** : un **message dédié épinglé**,
   jamais le champ `topic` (mesuré : `PATCH {"topic": …}` → 200 puis
   `topic = None`, jeté en silence). L'accueil du thread reste intact.
2. **source de la branche / de la PR** → branche lue dans
   `specs/<n>/slices.json` (clé `branch`) ; PR via
   `gh pr list --repo <org>/<repo> --head <branche> --json url`. Une ligne non
   résolue est **omise**, jamais remplacée par un placeholder.
3. **grammaire exacte** → **Q1 = 1a** : `<icône> <repo>|#<numéro d'issue>|<titre
   de l'issue>` — `<repo>` = slug `hermes-workflow`, `<ticket>` = numéro d'issue
   GitHub, identité fixe d'un état à l'autre. L'échappement d'un `|` présent
   dans le titre d'origine reste à préciser en implémentation.

**Restantes (portées aux slices suivantes, non tranchées ici)** :

4. **rétro-compatibilité des résolveurs** : les 3 lecteurs (`resolve_thread`,
   `thread_index`, `THREAD_NAME_RE`) rendent `None` sur le nouveau format
   (mesuré). Les faire évoluer pour accepter **les deux formats** est **imposé
   par le contrat de non-régression**, pas optionnel.
5. **coalescence du renommage** : Discord plafonne à ~3 renommages par fenêtre
   (3ᵉ `PATCH name` → 429, `retry_after` ≈ 600 s). Un seul écrivain (le
   keeper), renommage best-effort, priorité `⚠ > 🛑 > ⚙️ > 🎬`.

## Hors-scope (à confirmer)

- **Le core de décision `/ok`** (`pj_decision.py`) et le flux d'escalade de
  message (`pj_escalate.build_message`) : #19 porte le **titre + description**,
  pas le corps des messages d'escalade ni la décision humaine.
- **La duplication bridge↔pipeline** des `pj_*.py` : divergence connue
  (`pj_graphwatch` seul), non traitée par #19.
- **La création initiale du thread** (`gh_triage_poll.py`, SOUL gh-triage) :
  le format `🎫 Issue #N — …` d'origine peut être hors périmètre (seul le
  renommage post-création est visé par la spec) — à confirmer.

## Frontières traversées (résumé)

```
état de l'issue (kanban + gh + git)
  → formatage pur (core) : <icône> <repo>|#<n>|<titre>  + description (épinglée)
  → adapter discord_thread.py : PATCH /channels/<id> {name}  (+ pin du message dédié)
  → thread Discord (artefact miroir)
  ← consommé en lecture par resolve_thread (engine), thread_index (escalate),
    THREAD_NAME_RE (pj-buttons)
```

Deux frontières sont franchies à chaque changement de format : **Discord REST**
(en écriture, via l'adapter) et **le contrat de lecture du nom** (en lecture,
par trois résolveurs qui parsent le nom). La frontière critique n'est pas l'appel
réseau mais la **grammaire du nom** : la changer sans mettre à jour les trois
consommateurs est une régression silencieuse qui désactive la notification
d'étape, l'escalade et les boutons de décision.
