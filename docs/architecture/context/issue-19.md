---
type: context
status: draft
tags: [architecture, discord, notification, thread, cadrage]
issues: [19]
---

# Cadrage architectural — issue #19 « Discord thread title and description update »

## Positionnement (cadre exact)

L'issue #19 demande de faire évoluer **le titre et la description** du thread
Discord d'une issue en fonction de **l'état** de cette issue, selon un format
explicitement spécifié :

```
Title : <icon> <project>|<ticket>|<title>
  - 🎬 pour le démarrage
  - ⚙️ lorsque les agents travaillent
  - 👆 si l'utilisateur doit intervenir
  - 🛑 si terminé

Description :
  - lien issue GitHub
  - branche git
  - si dispo, lien vers PR
```

C'est une **évolution de la surface de notification Discord**, pas une nouvelle
fonctionnalité métier : le pipeline produit déjà un thread par issue, le
renomme déjà à chaque transition d'étape, et poste déjà du contenu déterministe
dedans. L'issue #19 **change la forme** (format de titre, contenu de
description) et **enrichit la sémantique d'état** (ajout des états « démarrage »
et « intervention humaine requise »), sans toucher au cœur de décision.

**Écart mesuré entre la spec et l'existant (à nommer, pas à trancher ici)** :

| axe | existant (`pipeline/engine.py`) | demandé par #19 |
|---|---|---|
| format de titre | `{icon} {status} - issue {N} {title}` | `<icon> <project>\|<ticket>\|<title>` |
| icônes d'état | ⚙️ running / ✅ done / ❌ fail / 🔁 retry | 🎬 démarrage / ⚙️ travail / 👆 intervention / 🛑 terminé |
| description | aucune (le helper ne pose pas de description ; seul le message d'accueil existe) | lien issue + branche + lien PR |

La spec **remplace** le couple (format, jeu d'icônes) existant ; elle ne
l'étend pas. Deux des quatre icônes demandées (🎬, 👆) n'ont **aucun
équivalent** dans le jeu actuel (qui distingue `fail` et `retry` au lieu de
« démarrage » et « intervention humaine ») : la spec réintroduit l'**état
« attend l'humain »** dans le titre (aujourd'hui exprimé seulement par
`pj_escalate.py` qui *poste* un message d'escalade, sans toucher le titre).

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
  du nom — la « description » de la spec relève soit du **message d'accueil**
  (premier post), soit d'un **topic de forum**, mais pas d'un champ PATCHable
  sur un thread public ancré à un channel. C'est une **ambiguïté d'infra** à
  lever en t3/t4, pas un détail d'implémentation.
- **Git / GitHub** — la description demandée (lien issue, branche, lien PR) exige
  de lire **l'état git** de l'issue (branche du worktree, PR ouverte). Ces
  données ne sont **pas** toutes disponibles dans le `ticket` kanban chargé par
  `ticket_context()` (qui ne connaît que `title`, `body`, `status`,
  `issue_number` déduit de la ligne « Importé depuis <url> »). La branche et la
  PR sont des **informations de slice/de PR**, produites plus tard dans le
  cycle (t1 crée le worktree, t6 ouvre la PR) : les porter dans la description
  du thread suppose de les **résoudre** (via `gh`, via le blackboard, ou via
  l'état de `pj_graphwatch`), pas de les avoir déjà sous la main.

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
escalade, jamais un état « 👆 » dans le titre).

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
  le message d'escalade. C'est le **deuxième consommateur du nom du thread**.
- **`pipeline/gh_triage_poll.py`** — crée le thread initial au format `🎫 Issue
  #<N> — <titre>` (via le SOUL gh-triage), point de départ du cycle de vie du
  nom.
- **Helper `discord_thread.py`** (2 copies) — adapter REST : `create` / `send` /
  `rename` / `threads` / `delete`. `rename` est la seule écriture de nom ;
  **aucune** écriture de description/topic n'existe.

## Lecture SDD (spec-driven)

La spec (body de l'issue) est la source de vérité. Elle fixe un **format
littéral** — `<icon> <project>|<ticket>|<title>` — et un **jeu d'icônes**
fermé (🎬 ⚙️ 👆 🛑), plus trois lignes de description (issue / branche / PR).
Toute doc décrivant le livré devra figer **deux contrats rejouables** :

1. la **forme exacte du titre** (séparateur `|`, ordre `project|ticket|title`,
   icône en tête) — vérifiable par une fonction de formatage pure, pas par un
   appel réseau ;
2. la **table d'état → icône** (4 états, bijection) — testable sans Discord.

La doc ci-présente ne décrit que ce qui existe et est mesuré. Le format demandé
**n'existe pas** encore dans le code ; la spec est un objectif, pas un constat.

## Lecture DDD

Pas d'agrégat ni d'entité de domaine : le thread Discord est un **artefact
d'infrastructure**, un miroir de l'état de l'issue. Les seules notions
pertinentes :

- **Value object** — le **nom du thread** (chaîne formatée). C'est lui qui
  porte l'état et qui est **consommé en lecture** par `resolve_thread` et
  `thread_index` pour retrouver le thread. Sa **grammaire est un contrat** : la
  changer (format `|` au lieu de « issue N ») casse silencieusement les deux
  résolveurs qui le parsent — c'est le point de fragilité central de #19.
- **Domain event** — la **transition d'état** de l'issue (démarrage → travail →
  intervention humaine → terminé). Aujourd'hui la transition « attend l'humain »
  n'existe pas comme état de titre ; elle n'est matérialisée que par l'envoi
  d'un message (`pj_escalate.py`) et le `kanban_block`.

## Lecture TDD (contrat testable)

Les contrats à figer sont **purs** (aucun réseau, aucune horloge) :

1. **formateur de titre** : `title_icon(état) → icône` et
   `format_title(project, ticket, title, état) → "<icône> <project>|<ticket>|<title>"`
   — testables sur les 4 états + les cas limites (titre vide, ticket non
   numérique, séparateur `|` présent dans le titre d'origine → échappement ?).
2. **table d'état → icône** : bijection, une icône par état, `👆` uniquement pour
   « intervention humaine » (pas pour `fail`/`retry`), `🛑` pour terminé.
3. **rétro-compatibilité des résolveurs** : `resolve_thread` et `thread_index`
   doivent **continuer** à retrouver le thread après le changement de format.
   C'est le contrat de non-régression critique : les deux parseurs actuels
   (`issue #N`, `repo #N`) **ne matchent plus** le format `repo|N|title`. Le
   RED ici est « un thread renommé au nouveau format n'est plus retrouvé » —
   le GREEN doit couvrir les deux formats, ou faire évoluer les résolveurs dans
   la même slice.

Le RED/GREEN de l'issue : tant que `resolve_thread` ne retrouve pas un thread
renommé `<icon> <project>|<ticket>|<title>`, l'issue n'est pas résolue — le
renommage seul (sans mise à jour des deux consommateurs du nom) est un faux
vert qui casse la notification d'étape et l'escalade.

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
  potentiellement à faire évoluer pour distinguer l'état « 👆 » dans le titre.
- `pipeline/gh_triage_poll.py` + SOUL gh-triage — **producteur du nom initial**
  (`🎫 Issue #N — …`), point d'entrée du cycle de vie du titre.
- Helper `discord_thread.py` (2 copies) — **adapter** : `rename` (déjà là),
  **aucun** support de description/topic à ce jour ; à étendre si la spec exige
  une vraie description.
- `pipeline/engine.py` seul n'a **pas** de miroir `bridge/engine.py` (les autres
  `pj_*.py` sont en quasi-duplication bridge↔pipeline, seul `pj_graphwatch`
  diverge) — le périmètre code de #19 est donc `pipeline/`, pas `bridge/`.

## Ambiguïtés à lever (portées en t3/t4, non tranchées ici)

1. **« description » du thread** : Discord ne PATCH pas de description sur un
   thread public (type 11). La spec vise-t-elle le **message d'accueil** (premier
   post, mis à jour par édition), un **topic de forum**, ou un **pin** de message ?
2. **source de la branche / de la PR** : ces valeurs n'existent qu'après t1/t6 ;
   qui les résout (gh, blackboard, état graphwatch) et que vaut la description
   **avant** qu'elles existent (placeholder, omission) ?
3. **grammaire exacte** : séparateur `|` (échappement si `|` apparaît dans le
   titre d'origine ?), identité de `<ticket>` (numéro GitHub ou id de carte
   kanban `t_…` ?), `<project>` (slug `hermes-workflow` ou repo `hyron-fr/…` ?).
4. **rétro-compatibilité des résolveurs** : la spec ne mentionne pas
   `resolve_thread`/`thread_index` ; les faire évoluer dans la même slice est
   **imposé par le contrat de non-régression**, pas optionnel.

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
  → formatage pur (core) : <icône> <project>|<ticket>|<title> + description
  → adapter discord_thread.py : PATCH /channels/<id> {name}  (+ description ?)
  → thread Discord (artefact miroir)
  ← consommé en lecture par resolve_thread (engine) ET thread_index (escalate)
```

Deux frontières sont franchies à chaque changement de format : **Discord REST**
(en écriture, via l'adapter) et **le contrat de lecture du nom** (en lecture,
par deux résolveurs qui parse le nom). La frontière critique n'est pas l'appel
réseau mais la **grammaire du nom** : la changer sans mettre à jour les deux
consommateurs est une régression silencieuse qui désactive la notification
d'étape et l'escalade.
