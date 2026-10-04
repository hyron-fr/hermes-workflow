---
type: context
status: draft
tags: [architecture, pipeline, worktree, convergence, decision, cadrage]
issues: [31, 19]
---

# Cadrage architectural — issue #31 « slice 5/5 — convergence »

## Positionnement (cadre exact)

L'issue #31 est un **point à statuer** (étiquette `decision`), importé du pont
GitHub vers le kanban (`gh-issue-31`) : elle est le miroir de la carte `t_f725879f`
(`slice 5/5 — convergence` de l'issue **#19**), bloquée depuis le 2026-10-03.
Elle n'est **pas** une évolution fonctionnelle du pipeline : c'est un point de
décision humaine sur l'état du **worktree partagé** de #19.

**Constat partagé (mesuré, rejouable)** — dans le worktree partagé
`/home/elix/pj-repos/hermes-workflow/.worktrees/t_c22a7e74` (branche
`wt/issue-19-discord-thread-title-description`, base `origin/dev @ 009f0a7`) :

- HEAD = `49bb284` (dernier commit **test-5 RED** — le banc du bloc Description).
  Le commit **GREEN dev-5 `6661362`** (déclaré par la carte `t_d1d4eb41`, run 272)
  **n'existe nulle part** : `git cat-file -t 6661362` → `fatal: Not a valid object
  name`, 0 branche locale ni distante ne le contient, absent du reflog de la
  branche.
- `grep -rln "build_description_lines\|DESCRIPTION_MARKER\|sync_description\
  \|build_description_for_card\|sync_all_descriptions" pipeline/ bridge/ skills/`
  → **0 occurrence** : l'API de la slice 5 est absente du code.
- Le helper `skills/gh-kanban-bridge/scripts/discord_thread.py` ne porte pas
  `upsert-desc`/`pin` (seuls `create`/`send`/`threads`/`rename`/`delete`).
- Rejoué : `pytest tests/test_thread_description.py -q` = **10 failed** (état
  RED), non 10 passed comme l'affirmait le handoff de dev-5.

**L'issue demande** un jugement humain (jeton `/ok` en tête de commentaire, ou
question d'éclaircissement) pour trancher : le commit GREEN a-t-il été perdu
(rollback/rebase/force-push du worktree partagé, ou clôture de `dev-5` avant push
effectif), et que faire (re-pousser `6661362` ou un successeur sur la branche,
puis re-déclencher la convergence).

## Croisement infrastructure / fonctionnel / code

### Infrastructure (frontières traversées)

- **Worktree partagé / branche issue** — le point de fracture est l'**état du
  worktree** : la branche porte les slices 1→4 livrées (maquette, lecteurs du nom,
  formateur pur + table des 4 états, keeper écrivain unique avec coalescence,
  jusqu'à `422878f`) + le banc RED de la slice 5 (`26bad5d`, `49bb284`), mais
  **pas** le GREEN de la slice 5. La frontière traversée est **l'intégrité de
  l'histoire de la branche partagée** : un commit déclaré « poussé » (handoff
  `dev-5` : push `0 0`, banc 10/10 verts, suite 20/542) qui n'existe plus dans
  l'objet git est une divergence worktree↔déclarations.
- **Pipeline de convergence (RED → GREEN → conv → doc)** — la carte de
  convergence (`t_f725879f`, assignée `pj-test`) exige en DoR `dev-5 done` **avec
  le commit poussé** ; sans le code, le verdict est prononcé « sur du code absent
  », ce que le périmètre test-only interdit (re-implanter n'est pas permis).
  C'est la **frontière du verdict** : la convergence juge l'existence et la
  cohérence du livré, pas son absence.
- **Décision humaine via le pont** — l'issue miroir #31 est le canal de décision :
  `/ok` débloque la carte (elle repart en file, à re-juger après re-poussée),
  tout autre commentaire est une demande d'éclaircissement. La frontière
  agent↔humain ici est **l'identité du commit manquant** : seul l'humain
  (ou le dispatcher avec l'outil dev-5) peut dire si le commit est récupérable
  ou doit être re-fabriqué.

### Fonctionnel (capacité traversée)

La capacité traversée est **« convergence de la slice 5 du livrable #19 »** :
le bloc **Description épinglée** (arbitrage Q2 = 2b : message dédié épinglé,
jamais le champ `topic`, trois lignes issue/branche/PR omises si non résolues).
C'est la **seconde moitié du livrable #19** (la première — titre — est livrée
aux slices 2-4). La convergence de la slice 5 est le dernier contrôle de contenu
avant `doc-5`, `doc-review` et `t6` (ouverture de la PR).

### Code (composants, ports, adapters)

- **`pipeline/engine.py`** — porte le **core pur** du bloc Description que le
  commit manquant devait ajouter : `DESCRIPTION_MARKER` (marqueur `[description]`
  de déduplication) et `build_description_lines(issue_url, branch, pr_url, log)`
  (composition pure : 4 lignes max, ligne omise si source `None`, journalisation
  bruyante). Absent du HEAD courant.
- **`pipeline/pj_room_keeper.py`** — porte l'**écrivain** du bloc que le commit
  manquant devait ajouter : `build_description_for_card` (lecteurs de sources
  injectables : `specs_reader`, `pr_reader`, `issue_url_lookup`), `sync_description`
  (dédup par marqueur `[description]`, édit jamais 2ᵉ post, accueil intact),
  `sync_all_descriptions` (NE LÈVE JAMAIS : un lecteur de source qui lève est
  capturé et tracé). Absent du HEAD courant.
- **`skills/gh-kanban-bridge/scripts/discord_thread.py`** (helper versionné, avec
  sa copie runtime `~/.hermes/scripts/discord_thread.py`) — devait gagner les
  capacités **`upsert-desc` + `pin`** (édition/épinglage d'un message). Absentes
  des deux copies. La divergence D2 (la copie runtime ne porte pas ces capacités)
  est déjà déclarée par le handoff de dev-5.
- **`tests/test_thread_description.py`** — le **banc RED** de la slice 5 (10 cas :
  3 nominal / 3 limite / 4 erreur), présent à HEAD (`26bad5d`). Il gèle le contrat
  de l'API manquante : c'est la preuve que le RED existe et que le GREEN est
  absent (10/10 failed, chaque échec nomme l'API absente).

## Lecture SDD (spec-driven)

La source de vérité est le **manifeste de slices** de #19
(`~/.hermes/kanban/boards/pj-hermes-workflow/specs/19/slices.json`, validé au
gate humain t5, sha `e69d6ee3…`). La slice 5 y déclare :

- **fichiers** : `pipeline/engine.py`, `pipeline/pj_escalate.py`,
  `pipeline/pj_room_keeper.py`, `skills/gh-kanban-bridge/scripts/discord_thread.py`,
  `tests/test_thread_description.py` ;
- **contrat GREEN** : le fil porte un message Description épinglé, unique et à
  jour, sans jamais échouer sur une source manquante (DoD de `dev-5` : au plus
  **1** message Description par fil, idempotent : mise à jour) ;
- **contrat de convergence** : un seul message Description, épinglé, lignes
  correspondant aux valeurs réelles (issue URL / branche déclarée / PR ouverte),
  PR fermée → ligne omise, doublon détecté → refus + `request-changes`.

L'état du worktree **viole** la spec : la slice 5 est déclarée « GREEN poussé »
par le handoff de `dev-5` (carte `t_d1d4eb41`, run 272) mais le commit n'existe
pas. L'issue #31 est le canal par lequel cette **incohérence spec↔livré** est
tranchée par l'humain.

## Lecture DDD

Pas d'agrégat, d'entité ni de value object de domaine : l'issue #31 est un
**incident d'infrastructure de pipeline**, pas un fait de domaine. Les seules
notions pertinentes :

- **Domain event (processus)** — la **transition du verdict de convergence**
  (bloqué → débloqué par décision humaine). L'événement « le commit GREEN est
  manquant » est un **fait d'état du worktree**, pas un événement de domaine :
  il ne change ni le contrat du bloc Description ni la table des 4 états.
- **Règle du pipeline (non-régression de confiance)** — un handoff qui déclare
  « commit poussé, banc 10/10 verts » mais dont le commit n'existe plus dans
  l'objet git est un **faux vert de livraison** : c'est le même genre de défaut
  que la règle du sceau de l'issue #2 (la couverture se juge sur l'objet réel,
  pas sur la déclaration).

## Lecture TDD (contrat testable)

Le contrat testable de l'issue #31 est **l'existence du GREEN** dans le worktree
partagé, pas le comportement du bloc Description (celui-ci est déjà gelé par le
banc `tests/test_thread_description.py`, 10 cas) :

1. **Existence du commit** : `git cat-file -t 6661362` (ou du commit successeur)
   → doit rendre `commit`, pas `fatal`. Mesurable sans réseau, sans horloge.
2. **Présence de l'API** : `grep -rln "build_description_lines\|sync_description\
   \|DESCRIPTION_MARKER" pipeline/ bridge/ skills/` → ≥ 1 occurrence dans
   `pipeline/engine.py` et `pipeline/pj_room_keeper.py` (et `upsert-desc`/`pin`
   dans le helper versionné).
3. **Vert du banc** : `pytest tests/test_thread_description.py -q` → **10 passed**
   (non 10 failed), sans modification du banc (sha256 gelé par le RED `test-5` :
   `d1a94283…`).
4. **Non-régression** : suite complète → les rouges pré-existants (20)
   inchangés, +10 du banc verts, 0 nouveau rouge.

Jusqu'à ce que (1)-(4) soient verts, la convergence ne peut **pas** être jugée :
c'est le garde-fou de la DoR de `t_f725879f`.

## Lecture hexagonale

Pas de frontière core/adapter en cause : le bloc Description **devait** être
livré avec `build_description_lines` en **core pur** (composition, aucune
dépendance Discord/gh/git) et les adaptateurs `sync_description`/`sync_all_
descriptions` en **keeper** (lecture d'état injectée, écriture best-effort).
L'issue #31 ne déplace aucune décision dans l'adapter ; elle porte sur
**l'existence même du livré** dans le worktree. La frontière pertinente est
**l'état du worktree partagé** (infra) par rapport à **la spec du manifeste**
(source de vérité) : c'est une violation d'intégrité d'histoire, pas de
purité du core.

## Composants impactés par l'issue #31

- **Worktree partagé `t_c22a7e74` / branche `wt/issue-19-discord-thread-title-
  description`** — **impacté directement** : l'état de la branche est incohérent
  avec le handoff de dev-5. Toute correction (re-poussée ou re-fabrication du
  commit) s'opère ici, sur cette branche, sans merge vers `dev`.
- **Carte `t_f725879f` (slice 5/5 — convergence, `pj-test`)** — **bloquée** :
  ne peut prononcer le verdict que si le GREEN est présent. L'issue #31 est son
  canal de décision.
- **Cartes en aval** : `t_e9484d73` (doc-5), `t_8b687be8` (doc-review),
  `t_ad99e220` (t6 submitted #19), `t_fb5ab27f` (worktree-rm), `t_63c4f6cb`
  (doc-memory) — **bloquées en cascade** par la convergence.
- **`pipeline/engine.py`** — **à compléter** : `DESCRIPTION_MARKER` +
  `build_description_lines` (core pur) absents de HEAD.
- **`pipeline/pj_room_keeper.py`** — **à compléter** : adaptateurs de sources
  (`specs_reader`, `pr_reader`, `issue_url_lookup`), `build_description_for_card`,
  `sync_description`, `sync_all_descriptions` absents de HEAD.
- **`skills/gh-kanban-bridge/scripts/discord_thread.py`** — **à compléter** :
  capacités `upsert-desc` + `pin` absentes (et sa copie runtime
  `~/.hermes/scripts/discord_thread.py` — divergence D2 déjà déclarée).
- **`tests/test_thread_description.py`** — **présent et gelé** (10 cas RED) :
  il ne se modifie pas ; il attend le GREEN.

## Frontières traversées (résumé)

```
manifeste specs/19/slices.json (spec, source de vérité)
  → worktree partagé / branche issue (état git réel : GREEN 6661362 absent)
  → verdict de convergence (t_f725879f, pj-test) — bloqué, DoR non satisfait
  → décision humaine via issue miroir #31 (/ok ou question d'éclaircissement)
  → re-poussée du commit GREEN (dev-5 / dispatcher)
  → convergence re-jugée → doc-5 → doc-review → t6 (PR) → merge → post-merge
```

La frontière critique n'est **pas** le comportement du bloc Description (gelé
par le banc RED, arbitré par Q2 = 2b) mais **l'intégrité de l'histoire de la
branche partagée** : un commit déclaré poussé qui n'existe plus dans l'objet git
est un défaut de livraison qui bloque toute la suite. Le jugement humain porte
sur **la récupération ou la re-fabrication du commit**, pas sur le contrat.

## Ambiguïtés — restantes (portées à t3/t4/t5)

1. **Le commit `6661362` est-il récupérable ?** — s'il a été perdu par un
   force-push/rebase du worktree partagé, il faut le re-fabriquer (re-pousser le
   travail de dev-5) ; s'il existe encore dans un ref local/récupérable, il
   suffit de le re-pousser. **Non levable sans le dispatcher/dev-5** : le
   contenu du commit n'est pas dans l'objet git courant.
2. **Le banc `tests/test_thread_description.py` doit-il être modifié ?** — Non :
   il est gelé par le RED `test-5` (sha256 `d1a94283…`). Si le GREEN re-fabriqué
   ne passe pas le banc tel quel, c'est un **écart au contrat** à nommer, pas
   une retouche silencieuse du banc.
3. **La copie runtime `~/.hermes/scripts/discord_thread.py` doit-elle être
   synchronisée ?** — Hors périmètre de l'issue #31 : la publication live est
   une opération de fin de graphe (carte `worktree-rm` / post-merge), contrôlée
   par identité. La divergence D2 est déjà déclarée.

## Hors-scope (à confirmer)

- **La ré-implémentation du bloc Description** : périmètre dev-5 (`pj-dev`),
  pas de la convergence (`pj-test`) ni du cadrage (`pj-doc`).
- **La décision de merge de la branche vers `dev`** : carte `t6` + `worktree-rm`,
  jamais une carte de slice.
- **La traduction anglaise du corpus** : issue #2 (close).
- **Le renommage du fil Discord réel #19** : réservé à la slice 4 (quota
  coalescé par le keeper, fenêtre de 600 s).
