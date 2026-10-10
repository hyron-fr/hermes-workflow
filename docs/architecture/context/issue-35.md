---
type: context
status: draft
tags: [architecture, decision, escalation, kanban, import, cadrage]
issues: [35]
---

# Cadrage architectural — issue #35 « t2 mémoire projet »

## Positionnement (cadre exact)

L'issue **#35** est un **ticket de DROIT** (labels `kanban` + `decision`), pas un
ticket de décision au sens jeton : son corps reprend le template « point à
statuer / `/ok` » de la carte bloquée `t_5e667a92` (issue #31) via l'import du
gate de couverture (`<!-- pj-coverage-gate -->` : « recouvre du travail en vol
: #31 »). Le jeton `/ok` n'y débloque **rien** — le pipeline réel de #35 est le
pipeline de spec standard (t2 → t3 → t3b → t4 → t5, racine `t_80f55f14`),
importé par le pont le 08/10 (idempotency-key `gh-issue-35`).

C'est la **5ᵉ occurrence** du même point à statuer conv-5 de la chaîne du
chantier **#19** (« Discord thread title and description update »), après
#27/#29 (1ʳᵉ-2ᵉ), #31 (3ᵉ) et #45 (4ᵉ, RECYCLE GREEN). Le point à statuer
hérité de #31 : la carte conv-5 `t_f725879f` était bloquée parce que le commit
**GREEN dev-5 `6661362` était perdu** — et il l'est toujours : `git cat-file -t
6661362` → **fatal : Not a valid object name** (mesuré 10/10 sur l'origin/dev
`2027333` et sur la branche `wt/issue-19-discord-thread-title-description` @
`dbf73da`).

Ce que #35 porte : **le cadrage de la reprise** — positionner la chaîne
conv-5 dans l'état ACTUEL du dépôt (GREEN partial, banc 7/10), identifier les
composants impactés, et orienter le flux de spec aval (t4) qui doit pointer
vers **#45 RECYCLE GREEN**, jamais vers le flux « converger sur 6661362 »
(observé en t3 du #27 : `PROTOTYPE: non`, graphe normal, 1 seule slice de
production = `t_7aaf3d49`).

Le présent cadrage **ne tranche pas** : il positionne, identifie, oriente. Le
re-push du GREEN (nouveau commit, pas de replay de `6661362`) est porté par la
carte RECYCLE `t_7aaf3d49` (`pj-dev`), jamais par ce cadrage.

## Croisement infrastructure / fonctionnel / code

### Infrastructure (frontières traversées)

- **GitHub** — surface de décision du gate de couverture (commentaire
  `<!-- pj-coverage-gate -->` identifiant #35 comme recouvrant #31, donc le
  travail en vol #19) et surface de preuve (état de la branche
  `wt/issue-19-discord-thread-title-description` : head remote `dbf73da`,
  23 commits au-dessus de `origin/dev` `2027333`). Le label `decision` posé
  par le gate est un **résidu de l'import**, pas un signal de flux jeton.
- **Git / worktree partagé** — surface de livraison de la slice 5 de #19.
  État mesuré (10/10) : le branch head `dbf73da` **contient** partiellement
  l'API slice 5 (`DESCRIPTION_MARKER`, `build_description_lines` dans
  `pipeline/engine.py` ; 9 occurrences de
  `sync_all_descriptions` / `build_description_for_card` /
  `sync_description` dans `pipeline/pj_room_keeper.py`), mais le banc
  `tests/test_thread_description.py` est **7/10 GREEN, 3 rouges nommés**
  (cf. cadrage issue-41, commit `dbf73da`) et le worktree `t_c22a7e74` porte
  **43 insertions non committées** dans `pipeline/pj_room_keeper.py` +
  `diag2.py` (fichier de diag non tracké). Le GREEN est donc **partial et
  non convergé** : ni `6661362` ni son équivalent n'ont produit un banc
  10/10.
- **Kanban Hermes** — source de vérité de l'état des cartes : `t_f725879f`
  (conv-5, issue #19) porte le point de convergence ; `t_7aaf3d49` (RECYCLE
  GREEN, `pj-dev`, blocked) est la carte de re-livraison ; `t_5e667a92`
  (t2 mémoire de #31) est **crashée depuis le 03/10** (indisponibilité
  provider, run 283, `gave_up` sticky, jamais livrée) — c'est elle dont #35
  reprend le template.

### Fonctionnel (capacité traversée)

La capacité traversée est **convergence + preuve de livraison de la slice 5
de #19**, pas la fonctionnalité #19 elle-même (titre + description du thread
Discord, déjà cadrée par les notes `issue-19`, `issue-27`, `issue-29`,
`issue-31` (via le commit `03e09f1`), et le composant `pj-thread-name`).
Ce que #35 porte :

- **le point de décision hérité** : le travail de la slice 5 est-il livré ?
  → mesuré : **non** (GREEN partial, banc 7/10, fixes non committés) ;
- **la chaîne de re-livraison** : qui repousse le GREEN ? → la carte
  RECYCLE `t_7aaf3d49` avec **un nouveau commit** (3 fixes keeper +
  2 commandes helpers `upsert-desc` / `pin` dans `discord_thread.py`) ;
- **le verdict de convergence** : après re-push, le banc
  `tests/test_thread_description.py` passe-t-il **10/10 GREEN** ?

C'est une **boucle de décision + re-livraison**, pas une évolution de
fonctionnalité. Les 10 cas du banc `tests/test_thread_description.py`
verrouillent le contrat d'interface de la moitié description de #19 :
`DESCRIPTION_MARKER = "[description]"`, `build_description_lines`,
`description_log_lines`, `keeper.build_description_for_card`,
`keeper.sync_description`, `keeper.sync_all_descriptions`.

### Code (composants impactés)

| composant | état mesuré (10/10, `origin/dev` `2027333`) | impact de la chaîne conv-5 |
|---|---|---|
| `tests/test_thread_description.py` | présent dans `wt/issue-19-discord-thread-title-description` @ `dbf73da` (absent de `origin/dev`) | **banc de convergence** : 7/10 GREEN, 3 rouges nommés ; 10 cas = critères d'acceptation de la slice 5 |
| `pipeline/engine.py` | `DESCRIPTION_MARKER` + `build_description_lines` (L221–L234) présents dans la branche (absents de `origin/dev`) | **formateur pur** de la description (issue #19 slice 5) — core, 0 réseau |
| `pipeline/pj_room_keeper.py` | 9 occurrences de l'API description (`sync_all_descriptions`, `build_description_for_card`, `sync_description`) ; 43 insertions non committées dans `t_c22a7e74` | **écrivain unique** de la description (miroir du titre, slice 4) — fixes nommés : `L725` passthrough `issue_url_lookup`/`thread_lookup`, `L657` org-loss dans `_gh_repo()`, `L824+` `issue_url_lookup` manquant dans `sync_all_descriptions` |
| `skills/gh-kanban-bridge/scripts/discord_thread.py` | capacités `create`/`send`/`rename`/`threads`/`delete` ; **aucune** `upsert-desc` ni `pin` | **adapter REST** à étendre : 2 commandes `upsert-desc` / `pin` (non livrées) |
| `bridge/pj_room_keeper.py` + `agents/pj-master/scripts/pj_room_keeper.py` | miroirs du keeper | doivent suivre les fixes du keeper principal |

Note de divergence connue : les notes de cadrage #27/#29 situaient le
formateur de la description dans `pipeline/engine.py` (L221–234 mesuré ici)
et l'écriture dans `pipeline/pj_room_keeper.py` — l'API `build_description_lines`
est bien dans `engine.py`, la façade `build_description_for_card` dans le
keeper. La frontière hexagonale tient : le formateur est pur, l'écriture
délègue au helper Discord (adapter).

## Lecture SDD (spec-driven)

La spec de #35 est le **point à statuer hérité de #31** : le commit GREEN
dev-5 `6661362` est perdu et la slice 5 de #19 n'est pas convergée. Le
livrable de #35 n'est **pas** un code, mais **le cadrage de la reprise** :
positionner la chaîne conv-5 dans l'état mesuré du dépôt, orienter le flux
aval (t4 → #45 RECYCLE GREEN), et documenter les composants impactés. La doc
décrit ce qui existe aujourd'hui (GREEN partial, banc 7/10, fixes non
committés, API partiellement dans `engine.py`/keeper) — pas une intention.

## Lecture DDD (bounded contexts, agrégats, événements)

- **Bounded context** : *convergence / livraison* — chevauche
  *développement* (slice 5 de #19) et *décision humaine* (l'escalade
  #27/#29/#31/#35/#45), sans en être un nouveau : c'est la **jonction**
  entre les deux. #35 est le 5ᵉ import de cette jonction.
- **Agrégat racine** : la **carte `t_f725879f` (conv-5)** — invariant : elle
  ne repart en `ready` que sur un `/ok` humain portant son `id` exact.
  L'**issue #35** n'est pas l'objet de décision de ce jeton (le template
  « `/ok` débloque » est un résidu de l'import) : c'est l'objet de cadrage
  qui matérialise la reprise.
- **Value objects** : le **branch head SHA** (`dbf73da` mesuré sur la
  branche, `2027333` sur `origin/dev`) ; le **commit SHA perdu** `6661362`
  (absent, mesuré) ; l'**idempotency-key** `gh-issue-35`.
- **Domain events** : cadrage #35 (ce document) → t4 pointe vers #45
  RECYCLE GREEN → re-push du GREEN par `t_7aaf3d49` (nouveau commit sur
  `wt/issue-19-discord-thread-title-description`) → banc 10/10 GREEN →
  convergence slice 5/5 → doc → doc-review → PR → merge.

## Lecture TDD (contrats testables)

Le contrat testable de la reprise n'est pas un code, mais **des invariants
mesurables** :

- **Le banc `tests/test_thread_description.py` passe 10/10 GREEN** —
  rejouable sans Discord ni réseau (sources injectées) ; c'est le critère
  de convergence de la slice 5.
- **`pj_coverage_gate.py --json coverage.json --diff-base origin/dev`
  sort `exit=0`** avec couverture > 80 %/fichier sur `pj_room_keeper.py`,
  `engine.py`, `discord_thread.py`.
- **Le branch head contient un commit qui n'est pas `6661362`** (replay
  interdit) et le push est vérifié `0 0` vs origin.
- **Aucun test tautologique** dans le banc.

Ces invariants sont mesurables par `pj_graphwatch` (couverture
commit-à-commit + chemin réel du worktree, cf. commits `009f0a7`,
`9e49771`, `318bea1` de l'issue #2) et par le pont de couverture
(`pj_coverage_gate`) qui a identifié #35 comme recouvrant #31.

## Lecture hexagonale (le core reste pur)

Le core pur de la slice 5 est `build_description_lines` dans
`pipeline/engine.py` (fonction pure : issue_url, branch, pr_url → list[str],
0 réseau, 0 horloge, 0 aléa) — mesuré présent dans la branche
(`DESCRIPTION_MARKER` L221, `build_description_lines` L224). L'écriture du
message épinglé et de l'épingle passe par le helper `discord_thread.py`
(adapter REST, hors core). Le contrat d'interface (marqueur
`[description]`, `build_description_for_card`, `sync_description`,
`sync_all_descriptions` dans le keeper) est testable sans Discord : les
sources et l'adaptateur sont injectés.

La frontière à respecter : **la description est une lecture d'état**
(gh/git/blackboard) résolue **hors** du core, puis injectée dans le
formateur pur. Jamais l'inverse : le formateur ne lit pas le réseau.

## Composants impactés par la reprise portée par #35

| composant | impact | porteur |
|---|---|---|
| `tests/test_thread_description.py` | banc de convergence (7/10 → 10/10 attendu) | `t_7aaf3d49` (RECYCLE GREEN) |
| `pipeline/engine.py` | formateur pur de la description (présent dans la branche, absent de `origin/dev`) | `t_7aaf3d49` |
| `pipeline/pj_room_keeper.py` | écrivain de la description + 3 fixes nommés (43 ins. non committées dans `t_c22a7e74`) | `t_7aaf3d49` |
| `skills/gh-kanban-bridge/scripts/discord_thread.py` | 2 commandes `upsert-desc` / `pin` à ajouter | `t_7aaf3d49` |
| `bridge/pj_room_keeper.py` + `agents/pj-master/scripts/pj_room_keeper.py` | miroirs du keeper | `t_7aaf3d49` |
| `diag2.py` (worktree `t_c22a7e74`) | fichier de diag non tracké, à supprimer avant le GREEN | `t_7aaf3d49` |

## Hors-scope

- **Le re-push du GREEN** : porté par `t_7aaf3d49` (RECYCLE GREEN, `pj-dev`)
  avec **un nouveau commit**, jamais par ce cadrage.
- **La convergence effective de la slice 5** : portée par la carte
  `t_f725879f` (conv-5) après le re-push.
- **Les slices 1–4 de #19** : déjà livrées, cadrées par les notes `issue-19`
  et le composant `pj-thread-name` (slice 4).
- **Le verdict de convergence** : porté par `pj-test` sur la carte
  `t_f725879f`, pas par ce cadrage.
- **La duplication bridge↔pipeline↔agents des `pj_*.py`** : divergence
  connue (les 3 copies du keeper), non traitée par #35.
- **Les escalades précédentes** (#27/#29/#31/#45) : déjà cadrées par leurs
  notes ; #35 en reprend le point à statuer sans les redécrire.

## Frontières traversées (résumé)

```
issue #35 (GitHub, labels kanban+decision, import gate de couverture)
  → cadrage de la reprise (ce document, t3b)
  → t4 pointe vers #45 RECYCLE GREEN (flux de spec, PROTOTYPE: non)
  → re-push du GREEN par t_7aaf3d49 (nouveau commit, git)
  → banc test_thread_description.py 10/10 GREEN (preuve de livraison)
  → convergence slice 5/5 → doc → doc-review → PR → merge
```

Deux frontières : **GitHub ↔ kanban** (import de droite → cadrage → flux de
spec) et **git ↔ worktree partagé** (preuve de livraison). Le point de
fragilité n'est pas l'appel réseau mais **la couverture commit-à-commit** :
un commit absent du branch head est un travail non livré, quel que soit le
handoff du worker ; un GREEN partial (banc 7/10, fixes non committés) est
un travail **non convergé**.

## État mesuré (2026-10-10)

- `origin/dev` = **`2027333`** (cadrage issue #29 + fixes graphwatch :
  `009f0a7`, `9e49771`, `318bea1`).
- `wt/issue-19-discord-thread-title-description` :
  - **local + remote** (worktree `t_c22a7e74`) = **`dbf73da`** (23 commits
    au-dessus de `origin/dev`), dernier = `docs(issue-41): corrige l'écart
    — GREEN partial dans 55e6659, banc 7/10, 3 retouches nommées` ;
  - `git cat-file -t 6661362` → **fatal : Not a valid object name** (commit
    perdu, mesuré) ;
  - `pipeline/engine.py` : `DESCRIPTION_MARKER` (L221) +
    `build_description_lines` (L224) **présents** ;
  - `pipeline/pj_room_keeper.py` : 9 occurrences de l'API description,
    **43 insertions non committées** (fixes keeper en cours) ;
  - `diag2.py` non tracké (diag de `sync_all_descriptions`) ;
  - `skills/gh-kanban-bridge/scripts/discord_thread.py` : **aucune**
    `upsert-desc` ni `pin` (capacités à ajouter).
- Banc `tests/test_thread_description.py` : **7/10 GREEN, 3 rouges nommés**
  (mesuré sur la branche @ `dbf73da`, cf. cadrage issue-41).
- Carte `t_5e667a92` (t2 mémoire de #31) : crashée depuis le 03/10,
  livraison jamais produite — template repris par #35.
- `pj_docs_lint.py` sur `/home/elix/pj-repos/hermes-workflow` → `exit=0`
  (vérifié avant et après ce cadrage).
