---
type: context
status: draft
tags: [architecture, decision, convergence, memory, escalation, pipeline, cadrage]
issues: [37]
---

# Cadrage architectural — issue #37 « t2 mémoire projet »

## Positionnement (cadre exact)

L'issue #37 est un ticket de **décision conv-5** (`labels: kanban, decision`) :
un **point à statuer** sur la carte `t_87ba23bf` (« t2 mémoire projet »),
bloquée sur le ticket **#29**. C'est le **miroir** de #27/#29 (même chantier
#19, même carte conv-5 `t_f725879f`), ré-importé par le pont de couverture
avec `idempotency-key gh-issue-37`. La carte est importée dans le board
`pj-hermes-workflow` comme racine `t_3e6defb3`.

**Point à statuer** : la carte `t_87ba23bf` (t2 mémoire projet, assignée à
`pj-master`) est **bloquée** — son worker (run #294) a crashé
(`pid not alive`, provider temporarily unavailable, 2026-10-03 18:40) après
~35 min de cœurs. Motif déclaré : « non détaillé ». Le ticket #29
(`slice 5/5 — convergence`, GREEN dev-5 `6661362` perdu du worktree partagé)
n'a **toujours pas de re-poussage du code GREEN** au moment du cadrage.

**Décision demandée** : commentez l'issue #37 avec le jeton `/ok` en
premier élément → la carte `t_87ba23bf` est débloquée et repart en file ;
le worker rejoue `hindsight_recall`/`hindsight_reflect` (banque `pj`,
tags `project:hermes-workflow`, `issue:37`) et poste le résumé mémoire en
commentaire de sa carte. Tout autre commentaire est une demande
d'éclaircissement et ne débloque rien.

Le présent cadrage **ne tranche pas** : il positionne le point à statuer
dans l'architecture existante, identifie les composants impactés, et fixe
les critères de décision. Le verdict humain (`/ok` sur l'issue) débloque la
carte `t_87ba23bf` ; le re-push du GREEN est porté par `dev-5`/dispatcher,
jamais par ce cadrage.

## Croisement infrastructure / fonctionnel / code

### Infrastructure (frontières traversées)

- **GitHub** — surface de décision (commentaire `/ok` sur l'issue #37,
  `idempotency-key gh-issue-37`) et surface de preuve (commits de la branche,
  PR éventuelle). Le commentaire du gate de couverture (`<!--
  pj-coverage-gate -->`, 2026-10-03) a identifié #37 comme recouvrant #29
  (travail en vol : PR ouverte / graphe déjà construit) — c'est la **même
  carte bloquée** (`t_87ba23bf`), escaladée une fois de plus.
- **Git / worktree partagé** — surface de livraison : le branch head de
  `wt/issue-19-discord-thread-title-description` est la **preuve de livraison**
  de la slice 5 de #19. État mesuré (2026-10-09) :
  - `origin/dev` = `2027333` (docs cadrage #29, au-dessus de `009f0a7`
    graphwatch + `9e49771`/`318bea1`).
  - `wt/issue-19-discord-thread-title-description` local
    (worktree t_c22a7e74) = `dbf73da` (docs cadrage #41 + correction de
    l'écart GREEN partial, au-dessus de `55e6659` baseline conv-audit).
  - `origin/fix/decision-jeton-apres-amorce` = `8e35b6e` (fix du faux
    négatif du jeton `/ok` après une amorce).
  - Le **code GREEN slice 5** (API `build_description_for_card` /
    `sync_description` / `sync_all_descriptions` + les noms module-level
    `thread_lookup` / `issue_url_lookup` / `_resolve_thread_impl` du
    commit perdu `82eedb1`) **n'est toujours pas dans `dev`** — le banc
    `tests/test_thread_description.py` (sur le worktree t_c22a7e74)
    échoue au setup (`ModuleNotFoundError: No module named 'langgraph'`
    dans `pipeline/engine.py:47`) ; les 3 tests rouge de la slice 5
    (`thread_lookup`, `issue_url_lookup`, `_resolve_thread_impl`)
    restent à re-livrer.
- **Kanban Hermes** — source de vérité de l'état des cartes :
  - `t_87ba23bf` (t2 mémoire #29) : **blocked**, run #294 crashé
    (provider temporarily unavailable, sticky `gave_up`).
  - `t_f725879f` (conv-5 de #19) : toujours en attente du re-poussage
    du GREEN.
  - `t_3e6defb3` (racine de l'issue #37) : attend ses 6 parents
    (t1 `t_c415f051`, t2 `t_8d405de6`, t3 `t_46119edc`,
    t3b `t_adb51751` = **cette carte**, t4 `t_9ef3bc0e`,
    t5 `t_2c312496`).

### Fonctionnel (capacité traversée)

La capacité traversée est **mémoire projet + convergence**, pas la
fonctionnalité #19 elle-même. #19 est déjà cadré par la note de
cadrage `issue-19` et par la note composant `pj-thread-name` (slice 4) ;
ses slices 1–4 sont livrées, la slice 5 est en cours de convergence.
Ce que #37 porte :

- **le point de décision** : la carte t2 mémoire est-elle relançable ?
- **la chaîne de re-livraison** : après le `/ok`, qui repousse le GREEN
  slice 5 sur `wt/issue-19-discord-thread-title-description` ?
- **le verdict de convergence** : après re-push, le banc
  `tests/test_thread_description.py` passe-t-il GREEN (10/10) ?

C'est une **boucle de décision + mémoire**, pas une évolution de
fonctionnalité. Le code de la slice 5 (bloc Description épinglé,
`build_description_lines`, `sync_description`, capacité `edit`/`pin` du
helper Discord) est décrit par le banc `tests/test_thread_description.py`
— ce cadrage ne le redécrit pas.

### Code (composants impactés)

- **`pipeline/pj_room_keeper.py`** (+ miroirs `bridge/pj_room_keeper.py`,
  `agents/pj-master/scripts/pj_room_keeper.py`) — porteur de l'écriture de
  la description (slice 5, **non livré**) : `build_description_for_card`,
  `sync_description`, `sync_all_descriptions`. Le GREEN partial (`55e6659`)
  contient déjà 2 des 7 tests verts ; les 3 rouges (`thread_lookup`,
  `issue_url_lookup`, `_resolve_thread_impl`) sont dans le commit perdu
  `82eedb1`.
- **`skills/gh-kanban-bridge/scripts/discord_thread.py`** — helper Discord
  (adapter REST) : `create` / `send` / `rename` / `threads` / `delete`.
  La slice 5 l'étend (capacité `edit`/`pin` du helper, **non livrée**).
- **`pipeline/engine.py`** — formateur pur du titre (`format_title`,
  `title_icon`, `TITLE_ICONS`, `NAME_MAX = 100`, slice 3 livrée). Le
  `rename_thread` délègue au keeper (slice 4). La description
  **n'appartient pas** à `engine.py` : c'est une lecture d'état
  (gh/git) qui doit être résolue hors du core, puis injectée.
- **`tests/test_thread_description.py`** (worktree t_c22a7e74, commits
  `26bad5d` + `49bb284`) — le banc RED de la slice 5 : 10 cas, rejoué
  10/10 RED (ou ERROR sur `langgraph` manquant). C'est lui qui
  **verrouille le contrat d'interface** de la moitié description de #19
  (Q2 = 2b) : `DESCRIPTION_MARKER = "[description]"`,
  `build_description_lines`, `description_log_lines`,
  `keeper.build_description_for_card`, `keeper.sync_description`,
  `keeper.sync_all_descriptions`. Sources injectées, 0 réseau.

## Lecture SDD (spec-driven)

La spec de #37 est le `point à statuer` : la carte `t_87ba23bf` est
bloquée après crash du worker. Le livrable de #37 n'est **pas** un code,
mais **l'état de la mémoire projet** : soit la carte est débloquée et le
worker rejoue `hindsight_recall`/`hindsight_reflect` et poste le résumé,
soit l'escalade se poursuit. La doc décrit ce qui existe aujourd'hui
(une carte bloquée, un crash de worker, le chantier #19 en attente de
re-poussage du GREEN) — pas une intention.

## Lecture DDD (bounded contexts, agrégats, événements)

- **Bounded context** : *convergence / livraison* — chevauche
  *développement* (slice 5 de #19) et *décision humaine* (l'escalade
  #27/#29/#37), sans en être un nouveau : c'est la **jonction** entre
  les deux.
- **Agrégat racine** : la **carte `t_87ba23bf`** (t2 mémoire projet,
  assignée `pj-master`) — invariant : elle ne repart en `ready` que sur
  un `/ok` humain portant son `id` exact (le commentaire sur l'issue
  #37). L'**issue #37** est l'objet de décision qui matérialise la carte.
- **Value objects** : le **branch head SHA** de
  `wt/issue-19-discord-thread-title-description` (`dbf73da` mesuré) ; le
  **commit SHA** du GREEN slice 5 (`6661362` perdu, `82eedb1` équivalent
  connu) ; l'**idempotency-key** `gh-issue-37`.
- **Domain events** : `/ok` humain sur l'issue #37 → unblock de
  `t_87ba23bf` → re-jouage de `hindsight_recall`/`reflect` → résumé
  mémoire posté en commentaire → convergence de la mémoire projet.
  Parallellement, le re-push du GREEN slice 5 (porté par
  `dev-5`/dispatcher) → banc GREEN → convergence effective de la slice 5.

## Lecture TDD (contrats testables)

Le contrat testable de #37 n'est pas un code, mais **un invariant
mesurable** :

- **La carte `t_87ba23bf` repasse en `ready` après le `/ok`** —
  vérifiable par `hermes kanban --board pj-hermes-workflow show
  t_87ba23bf` (statut `ready` ou `running`).
- **Le worker rejoue `hindsight_recall`/`reflect` et poste le résumé** —
  vérifiable par le commentaire de la carte (présence du résumé mémoire
  avec les tags `project:hermes-workflow`, `role:master`, `issue:37`).
- **Le banc `tests/test_thread_description.py` passe GREEN** — 10 cas,
  rejouable sans Discord ni réseau (sources injectées) ; le GREEN est la
  preuve que le re-poussage a bien eu lieu.
- **Les 10 cas du banc** sont les critères d'acceptation de la slice 5 ;
  leur état RED/GREEN est la preuve de convergence.

Ces invariants sont mesurables par `pj_graphwatch` (couverture
commit-à-commit + chemin réel du worktree, cf. commits `009f0a7`,
`9e49771`, `318bea1` de l'issue #2) et par le pont de couverture
(`pj_coverage_gate`) qui a identifié #37 comme recouvrant #29.

## Lecture hexagonale (le core reste pur)

Le core pur de la slice 5 est `build_description_lines` (fonction pure :
issue_url, branch, pr_url → list[str], 0 réseau, 0 horloge, 0 aléa).
L'écriture du message épinglé et de l'épingle passe par le helper
`discord_thread.py` (adapter REST, hors core). Le contrat d'interface
(marqueur `[description]`, `build_description_for_card`,
`sync_description`, `sync_all_descriptions`) est testable sans Discord :
les sources et l'adaptateur sont injectés.

La frontière à respecter : **la description est une lecture d'état**
(gh/git/blackboard) résolue **hors** du core, puis injectée dans le
formateur pur. Jamais l'inverse : le formateur ne lit pas le réseau.

## Composants impactés par l'issue #37

| composant | impact | slice #19 |
|---|---|---|
| `tests/test_thread_description.py` | banc RED (livré, `26bad5d` + `49bb284`) | 5 |
| `pipeline/pj_room_keeper.py` + miroirs | porteur de l'écriture de la description (**non livré**) | 5 |
| `pipeline/engine.py` | formateur pur du titre (livré, slices 3–4) | 3–4 |
| `skills/gh-kanban-bridge/scripts/discord_thread.py` | capacité `edit`/`pin` à ajouter (**non livré**) | 5 |
| `bridge/pj_room_keeper.py` + `agents/pj-master/scripts/pj_room_keeper.py` | miroirs du keeper (**non livrés**) | 5 |
| **Hindsight (banque `pj`)** | mémoire projet à rejouer (crash run #294) | — |
| **Kanban (carte `t_87ba23bf`)** | carte bloquée à débloquer par `/ok` | — |

## Hors-scope

- **Le re-push du GREEN `6661362`/`82eedb1`** : porté par `dev-5`/
  dispatcher sur le worktree t_c22a7e74 (`wt/issue-19-discord-thread-title-description`),
  **jamais** par ce cadrage.
- **La convergence effective de la slice 5** : portée par la carte
  `t_f725879f` après le `/ok` humain.
- **Les slices 1–4 de #19** : déjà livrées, cadrées par la note
  `issue-19` (worktree t_c22a7e74) et la note composant
  `pj-thread-name` (slice 4).
- **La duplication bridge↔pipeline↔agents des `pj_*.py`** : divergence
  connue (les 3 copies du keeper sont identiques à ce stade), non traitée
  par #37.
- **Le verdict de convergence** : porté par `pj-test` sur la carte
  `t_f725879f`, pas par ce cadrage.
- **Le crash du worker run #294** : incident d'infrastructure (provider
  temporarily unavailable), non lié au code ; le re-lancement de la carte
  suffit à rejouer la mémoire.

## Frontières traversées (résumé)

```
issue #37 (GitHub, labels decision + kanban)
  → commentaire /ok humain (surface de décision)
  → unblock de t_87ba23bf (kanban)
  → re-jouage hindsight_recall/reflect (banque pj)
  → résumé mémoire posté en commentaire (preuve de livraison)
  → convergence de la mémoire projet

(parallèle, hors périmètre #37)
issue #31/#45 (GitHub)
  → /ok humain
  → re-push du GREEN slice 5 sur wt/issue-19-discord-thread-title-description
  → banc test_thread_description.py GREEN (preuve de livraison)
  → convergence effective de la slice 5 → doc → doc-review → PR → merge
```

Deux frontières : **GitHub ↔ kanban** (décision → effet) et
**git ↔ worktree partagé** (preuve de livraison). Le point de fragilité
n'est pas l'appel réseau mais **la couverture commit-à-commit** : un
commit absent du branch head est un travail non livré, quel que soit le
handoff du worker.

## État mesuré (2026-10-09)

- `origin/dev` = `2027333` (docs cadrage #29, au-dessus de `009f0a7`
  graphwatch).
- `wt/issue-19-discord-thread-title-description` local
  (worktree t_c22a7e74) = `dbf73da` (docs cadrage #41 + correction de
  l'écart GREEN partial, au-dessus de `55e6659` baseline conv-audit).
- `origin/fix/decision-jeton-apres-amorce` = `8e35b6e` (fix du faux
  négatif du jeton `/ok` après une amorce).
- Le **code GREEN slice 5** (API `build_description_for_card` /
  `sync_description` / `sync_all_descriptions` + les noms module-level
  `thread_lookup` / `issue_url_lookup` / `_resolve_thread_impl` du
  commit perdu `82eedb1`) **n'est toujours pas dans `dev`** — le banc
  `tests/test_thread_description.py` (sur le worktree t_c22a7e74)
  échoue au setup (`ModuleNotFoundError: No module named 'langgraph'`
  dans `pipeline/engine.py:47`) ; les 3 tests rouge de la slice 5
  (`thread_lookup`, `issue_url_lookup`, `_resolve_thread_impl`)
  restent à re-livrer.
- Carte `t_87ba23bf` : **blocked**, run #294 crashé (provider temporarily
  unavailable, sticky `gave_up`), 0 commentaire de résumé mémoire.
- Carte `t_f725879f` (conv-5) : toujours en attente du re-poussage du
  GREEN.
- `git cat-file -t 6661362` → **fatal : Not a valid object name** (commit
  absent du dépôt local et du remote).
