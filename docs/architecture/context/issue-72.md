---
type: context
status: draft
tags: [architecture, decision, escalation, convergence, discord, notification, cadrage]
issues: [72]
---

# Cadrage architectural — issue #72 « t3 grill-me »

## Positionnement (cadre exact)

L'issue #72 est un **ticket de décision** (`labels: decision + kanban`,
`state: OPEN`) — **pas une tâche de dev**. C'est la **nouvelle racine de
l'escalade conv-5**, importée par le pont GitHub le 10/10 19:21 avec
l'`idempotency-key gh-issue-72` ; le gate de couverture l'a posée le 08/10
11:20 (recouvre #19, #29, #43, #44) avant l'import.

Son body est le **point à statuer de la carte `t_a444c5ff`** (t3 grill-me,
board `pj-hermes-workflow`, assignée `pj-master`), **miroir de la carte
`t3` de l'issue #29** (même body, même motif) : bloquée **168 h en
`needs_input`** depuis le 04/10. Le **parent GitHub de #72 est l'issue #29**
(« slice 5/5 — convergence », `label: decision`).

La portée de fond est **trancher le blocage conv-5** du chantier **#19**
(« Discord thread title and description update », 5 slices) : le commit
**GREEN dev-5 `6661362`** (slice 5/5 « Description épinglée ») est **absent
du worktree partagé** — et, mesuré depuis le 09/10, **définitivement perdu**
(`git cat-file -t 6661362` → fatal, refs/reflog/fsck vides, API GitHub 422).

**Ce que #72 porte, concrètement** : le jeton `/ok` en **premier élément**
sur l'issue débloque la carte cible `t_a444c5ff` et la repart en file ;
tout autre commentaire est une demande d'éclaircissement et ne débloque
rien. **Le jeton ne fait pas de dev** : il libère la machine de décision,
le re-GREEN est porté par le pipeline RECYCLE de l'issue #45.

Le présent cadrage **ne tranche pas** : il positionne le point à statuer
dans l'architecture existante, identifie les composants impactés, et fixe
les critères de décision. L'arbitrage de fond est **déjà rendu par l'humain**
(JB, fil Discord du 09/10, enregistré sur les cartes miroir) :
- **Option B** : re-pousser le GREEN via `/ok` sur **#45 RECYCLE** ;
- #44 tranché par `/ok` dans le thread Discord #44 ;
- **#33 : le re-poussage par cycle normal = NOUVEAU commit, PAS un replay
  de `6661362`.**

## Croisement infrastructure / fonctionnel / code

### Infrastructure (frontières traversées)

- **GitHub** — surface de décision (commentaire `/ok` sur l'issue #72,
  `idempotency-key gh-issue-72`) et surface de preuve (commits, PR). Le gate
  de couverture a identifié #72 comme recouvrant #19, #29, #43, #44 :
  c'est **la même chaîne bloquée**, re-soumise après le miroir #29.
- **Kanban Hermes** — source de vérité de l'état des cartes : `t_a444c5ff`
  (conv-5, miroir de `t_f725879f` issue #29) en `blocked` porte le point à
  statuer ; le jeton `/ok` sur #72 débloque cette carte mais ne déclenche
  **aucune** écriture de code.
- **Git / worktree partagé** — surface de livraison : le branch head de
  `wt/issue-19-discord-thread-title-description` (worktree `t_c22a7e74`)
  est la **preuve de livraison** de la slice 5. Un commit absent du branch
  head = travail non livré, quel que soit le handoff du worker (mesuré : le
  handoff de `dev-5` revendiquait « 0 0 vs `@{u}`, arbre propre » sur un
  commit introuvable).

### Fonctionnel (capacité traversée)

La capacité traversée est **convergence + preuve de livraison**, pas la
fonctionnalité #19 elle-même. #19 est déjà cadré par `issue-19` (worktree
`t_c22a7e74`) et par la note composant `pj-thread-name` (slices 2–4) ; ses
slices 1–4 sont livrées, la slice 5 est en cours de **re-livraison RECYCLE**.
Ce que #72 porte :

- **le point de décision** : le travail de la slice 5 est-il re-livré ?
- **la chaîne de re-push** : qui repousse le GREEN (nouveau commit, option
  B) sur `wt/issue-19-discord-thread-title-description` ?
- **le verdict de convergence** : après re-push, le banc
  `tests/test_thread_description.py` passe-t-il 10/10 ?

C'est une **boucle de décision + re-livraison**, pas une évolution de
fonctionnalité. Le code de la slice 5 (bloc Description épinglé,
`build_description_lines`, `sync_description`, capacité `edit`/`pin` du
helper Discord) est décrit par le banc — ce cadrage ne le redécrit pas.

### Code (composants impactés)

État mesuré au **2026-10-11 01:10** sur le worktree partagé
`t_c22a7e74` (`wt/issue-19-discord-thread-title-description`, HEAD
`9fcd207` == origin, `0 0`) :

| composant | état mesuré | slice #19 |
|---|---|---|
| `tests/test_thread_description.py` | **banc 7/10** (3 RED rejoués : `test_nominal_un_seul_message_epingle_mis_a_jour_pas_duplique`, `test_erreur_gh_pr_list_en_erreur_ligne_omise_tracee_pas_exception`, `test_erreur_le_reader_de_source_qui_leve_ne_tue_pas_le_tick`) | 5 |
| `pipeline/engine.py` | `build_description_lines` + `DESCRIPTION_MARKER` **livrés** (`55e6659`, baseline conv-audit) | 5 (partiel) |
| `pipeline/pj_room_keeper.py` | `sync_description` (L695) + `sync_all_descriptions` (L799) **présents** (`dccf75f`, +414 L, OOM-fix) mais **3 retouches à refermer** (contrat-5, nommées ci-dessous) | 5 (partiel) |
| `skills/gh-kanban-bridge/scripts/discord_thread.py` | helper 112 L ; **aucune capacité `upsert-desc` ni `pin`** | 5 (restant) |

**Les 3 retouches nommées (contrat-5, blackboard `t_854f0f77`)** — toutes
dans `pipeline/pj_room_keeper.py`, zéro écriture dans `tests/` :

1. `sync_description` / `sync_all_descriptions` : résolution du fil depuis
   l'ancre d'import du body (`Importé depuis …/issues/N`) ; le
   `thread_lookup` module-level ne doit être appelé que si le fil n'est pas
   déductible du body → referme `test_nominal_un_seul_message_epingle_…` ;
2. `_issue_url_from_card` : lire l'org complet depuis l'ancre du body au
   lieu de reconstituer via `_gh_repo()` (le banc patche le module-level
   `issue_url_lookup` ; sans cet attribut, repli `hermes-workflow` nu) →
   referme `test_erreur_gh_pr_list_en_erreur_…` ;
3. `sync_all_descriptions` : le verdict est écrit (bloc partiel : Issue +
   PR, Branche omise) même quand `specs_reader` lève — capté, tracé, le tick
   ne meurt pas → referme `test_erreur_le_reader_de_source_qui_leve_…`.

+ 2 capacités helper **`upsert-desc` / `pin`** dans `discord_thread.py`
(REST, hors core). Périmètre gelé par le verdict conv-5 ; `diag2.py`
(non versionné, artefact d'audit) à supprimer — **non livrable, ne pas
adopter**.

## Lecture SDD (spec-driven)

La spec de #72 est le `point à statuer` : le GREEN dev-5 n'est **pas**
repoussé sous forme de nouveau commit, et le banc reste 7/10. Le livrable
de #72 n'est **pas** un code, mais **l'état de convergence de la slice 5 de
#19** : soit le pipeline RECYCLE (#45 → `t_854f0f77`) livre un nouveau
commit et le banc passe 10/10, soit l'escalade se poursuit. La doc décrit ce
qui existe aujourd'hui (le GREEN partiel commité `dccf75f` + `55e6659` dans
`origin/dev @ 2027333`, le banc 7/10, le worktree de re-push) — pas une
intention.

## Lecture DDD (bounded contexts, agrégats, événements)

- **Bounded context** : *convergence / livraison* — jonction entre
  *développement* (slice 5 de #19) et *décision humaine* (l'escalade
  #27/#29/#41/#81/#72), sans en être un nouveau.
- **Agrégat racine** : la **carte `t_a444c5ff` (conv-5)** — invariant : elle
  ne repart en `ready` que sur un `/ok` humain portant son `id` exact
  (commentaire sur l'issue #72). L'**issue #72** est l'objet de décision qui
  matérialise la carte.
- **Value objects** : le **commit SHA** `6661362` (définitivement perdu —
  ne doit plus être cité comme cible, option B = nouveau commit) ; le
  **branch head** `9fcd207` ; l'**idempotency-key** `gh-issue-72`.
- **Domain events** : `/ok` humain sur l'issue #72 → unblock de
  `t_a444c5ff` → (parallèle, déjà arbitrée) `/ok` sur #45 → claim de
  `t_854f0f77` (dev-5 RECYCLE, assigné `pj-dev`, parent bloquant
  `t_f1aa13e4` t5 validate #45) → nouveau commit sur
  `wt/issue-19-discord-thread-title-description` → convergence GREEN → doc
  → doc-review → PR (#19) → merge.

## Lecture TDD (contrats testables)

Le contrat testable de #72 n'est pas un code, mais **des invariants
mesurables** :

- **Le banc `tests/test_thread_description.py` passe 10/10** — 10 cas,
  rejouable sans Discord ni réseau (sources injectées). Commande de
  vérification (DoD) :
  `uv run --with pytest --with pyyaml --with langgraph pytest tests/test_thread_description.py`
  → `10 passed, 0 failed`.
- **Le branch head de
  `wt/issue-19-discord-thread-title-description` contient un NOUVEAU commit
  GREEN** (option B, jamais un replay de `6661362`) — vérifiable par
  `git log --oneline` + `pj_graphwatch` (couverture commit-à-commit +
  chemin réel du worktree).
- **Les 3 retouches nommées (contrat-5) sont refermées** — les 3 cas
  `test_*` qui sont aujourd'hui RED passent sans toucher `tests/`.

Ces invariants sont mesurables par `pj_graphwatch` (cf. commits `009f0a7`,
`9e49771`, `318bea1` de l'issue #2) et par le pont de couverture
(`pj_coverage_gate`) qui a identifié #72 comme recouvrant #19 et #29.

## Lecture hexagonale (le core reste pur)

Le core pur de la slice 5 est `build_description_lines` (fonction pure :
issue_url, branch, pr_url → list[str], 0 réseau, 0 horloge, 0 aléa) —
livré dans `pipeline/engine.py` (`55e6659`). L'écriture du message épinglé
passe par le helper `discord_thread.py` (adapter REST, hors core) —
capacités `upsert-desc`/`pin` à ajouter. Le contrat d'interface
(marqueur `[description]`, `build_description_for_card`, `sync_description`,
`sync_all_descriptions`) est testable sans Discord : les sources et
l'adaptateur sont injectés.

La frontière à respecter : **la description est une lecture d'état**
(gh/git/blackboard) résolue **hors** du core, puis injectée dans le
formateur pur. Jamais l'inverse : le formateur ne lit pas le réseau. Les 3
retouches keeper (contrat-5) sont exactement dans cette frontière :
résolution du fil/issue depuis le body (pas de réseau), pas de lecture
directe du réseau dans `build_description_for_card`.

## Composants impactés par l'issue #72

| composant | impact | état mesuré 2026-10-11 |
|---|---|---|
| `tests/test_thread_description.py` | banc de convergence (gelé, intouchable) | 7/10, 3 RED rejoués |
| `pipeline/engine.py` | `build_description_lines` + marqueur | livré (`55e6659`) |
| `pipeline/pj_room_keeper.py` | 3 retouches keeper (contrat-5) | à refermer |
| `skills/gh-kanban-bridge/scripts/discord_thread.py` | capacités `upsert-desc` / `pin` | à ajouter (112 L, sans) |
| `diag2.py` (non versionné) | artefact d'audit conv-5 | à supprimer, non livrable |
| `bridge/pj_room_keeper.py` + `agents/pj-master/scripts/pj_room_keeper.py` | miroirs du keeper | à mettre à jour avec le GREEN (divergence connue, hors périmètre #72) |

## Hors-scope

- **Le re-push effectif du GREEN** : porté par `dev-5`/`dispatcher` (carte
  `t_854f0f77`, assignée `pj-dev`) sur le worktree partagé `t_c22a7e74`,
  **jamais** par ce cadrage.
- **La convergence effective de la slice 5** : portée par la carte
  conv-5 après le `/ok` humain.
- **Les slices 1–4 de #19** : déjà livrées, cadrées par `issue-19` et
  `pj-thread-name`.
- **La duplication bridge↔pipeline↔agents des `pj_*.py`** : divergence
  connue (les 3 copies du keeper), non traitée par #72.
- **Le replay du commit `6661362`** : explicitement exclu par l'arbitrage
  #33 — le re-GREEN est un **nouveau commit**, pas un replay.

## Frontières traversées (résumé)

```
issue #72 (GitHub, label decision + kanban, parent #29)
  → commentaire /ok humain (surface de décision)
  → unblock de t_a444c5ff (kanban, miroir de t_f725879f)
  → (parallèle, arbitrée) /ok sur #45 → claim de t_854f0f77 (dev-5 RECYCLE)
  → NOUVEAU commit GREEN sur wt/issue-19-discord-thread-title-description
  → banc test_thread_description.py 10/10 (preuve de livraison)
  → convergence GREEN → doc → doc-review → PR (#19) → merge
```

Deux frontières : **GitHub ↔ kanban** (décision → effet) et
**git ↔ worktree partagé** (preuve de livraison). Le point de fragilité n'est
pas l'appel réseau mais **la couverture commit-à-commit** : un commit absent
du branch head est un travail non livré, quel que soit le handoff du worker.

## État mesuré (2026-10-11, 01:10)

- `origin/dev` = `2027333` (docs issue #29 ; GREEN partiel `dccf75f` +
  `55e6659` y sont).
- `wt/issue-19-discord-thread-title-description` (worktree partagé
  `t_c22a7e74`) : **local = remote = `9fcd207`** (0 0), HEAD = note de
  cadrage issue #73.
- `git cat-file -t 6661362` → **fatal : Not a valid object name** (commit
  définitivement perdu, confirmé depuis le 09/10).
- Worktree de l'issue #72 (t1) : `t_053063e2`, branche `wt/t_053063e2`, HEAD
  `7091678` (dev + 2 notes cadrage #29/#81), checkout propre.
- Banc `tests/test_thread_description.py` : **7/10** rejoué (`uv run
  --with pytest --with pyyaml --with langgraph pytest
  tests/test_thread_description.py` → `3 failed, 7 passed`), les 3 rouges
  nommés par le contrat-5.
- Carte cible `t_a444c5ff` : `blocked` depuis le 04/10 (168 h,
  `needs_input`), assignée `pj-master`, miroir de `t_f725879f` (issue #29).
- Pipeline RECYCLE #45 : `t_f1aa13e4` (t5 validate) `blocked` en attente du
  GO humain ; `t_854f0f77` (dev-5 RECYCLE) en `todo`, assigné `pj-dev`,
  parent bloquant `t_f1aa13e4`.
