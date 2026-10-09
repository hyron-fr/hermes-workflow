---
type: context
status: draft
tags: [architecture, decision, escalation, conv-5, green-lost, cadrage, re-import, lissage]
issues: [36]
---

# Cadrage architectural — issue #36 « t3b doc-cadrage »

## Positionnement (cadre exact)

L'issue **#36** est un **ticket de décision** (`labels: decision + kanban`,
`OPEN`) qui matérialise un **point à statuer** sur la carte
**`t_7979348c`** (board `pj-hermes-workflow`, assignée à `pj-doc`,
statut `blocked` — crash de worker, run 292, `gave_up` sticky,
retry_status `ready`).

**Nature** : c'est le **2ᵉ import** du même point à statuer que les
issues **#27** et **#30** (« slice 5/5 — convergence » de la carte
`conv-5` **`t_f725879f`**, chantier #19). Le GREEN dev-5 `6661362`
est perdu (absent de tous les worktrees et de `origin`), la branche
`wt/issue-19-discord-thread-title-description` pointe sur le RED
test-5, et le banc `tests/test_thread_description.py` rejoue
**10/10 RED**.

**Caveat de lissage (mesuré)** : le body de l'issue #36 pointe vers la
carte `t_7979348c` (t3b doc-cadrage de l'issue #30, bloquée après
crash), **et non** vers la carte `t_f725879f` (conv-5) qu'elle
décrit. Les issues #27 et #30 pointent vers `t_f725879f`. Le
cadrage de t3 grill-me (t_9f15f1ad) doit trancher cette
ambiguïté : le point à statuer effectif est-il la convergence de
`conv-5` (`t_f725879f`) ou le doc-cadrage de `t_7979348c` ?

**Décision demandée** : commentez l'issue #36 avec le jeton `/ok` en
**premier élément** → la carte référencée est débloquée et repart en
file. Tout autre commentaire est une demande d'éclaircissement et ne
débloque rien.

Le présent cadrage **ne tranche pas** : il positionne le point à
statuer dans l'architecture existante, identifie les composants
impactés, et fixe les critères de décision. Le verdict humain
(`/ok` sur l'issue) débloque la carte ; le re-poussage du GREEN suit
(porté par `dev-5` / dispatcher, jamais par ce cadrage).

## Croisement infrastructure / fonctionnel / code

### Infrastructure (frontières traversées)

- **GitHub** — surface de décision (commentaire `/ok` sur l'issue
  #36) et surface de preuve (commits de la branche, PR éventuelle).
  L'issue #36 est une **re-import** du point à statuer : le pont de
  couverture (`pj_coverage_gate`) a identifié #36 comme recouvrant
  #27 et #30 (travail en vol sur `t_f725879f`).
- **Git / worktree partagé** — surface de livraison : le branch head
  de `wt/issue-19-discord-thread-title-description` est la **preuve
  de livraison** de la slice 5. Le commit `6661362` est absent
  (mesuré : `git cat-file -t 6661362` → `Not a valid object name`).
- **Kanban Hermes** — source de vérité de l'état des cartes :
  `t_f725879f` (conv-5) est en `blocked` (le point à statuer
  principal) ; `t_7979348c` (t3b doc-cadrage de #30) est en
  `blocked` après crash (le point référencé par le body de #36).
  La carte de convergence de #36 est `t_e706d361` (racine du
  graphe de #36, `todo`, parents = t1..t5 + t3b).

### Fonctionnel (capacité traversée)

La capacité traversée est **décision humaine sur blocage** (issue
#5, livrée — [[pj-decision]], [[pj-notify]]) au service de la
capacité **convergence / preuve de livraison** de la slice 5 du
chantier #19. #36 ne traverse aucune nouvelle capacité
fonctionnelle : elle **réutilise** la boucle de décision #5 et le
pont de couverture, et ré-importe le point à statuer de
`t_f725879f` (ou de `t_7979348c`, selon le caveat de lissage).

Les deux moitiés de #19 :
- **Moitié titre (slices 1–4, livrées)** : formateur pur
  `format_title` + table `TITLE_ICONS` dans `pipeline/engine.py`,
  3 lecteurs du nom de thread, keeper comme écrivain unique du
  titre avec coalescence par fenêtre `TITLE_WINDOW = 600 s`.
- **Moitié description (slice 5, GREEN perdu)** : le bloc
  Description épinglé dans le fil Discord — c'est ce que le point
  à statuer porte.

### Code (composants impactés)

- **`pipeline/pj_decision.py`** ([[pj-decision]]) — core pur de
  décision `/ok` (issue #5, slice 4). Le fix `8e35b6e`
  (`fix/decision-jeton-apres-amorce`) élargit `_token_index`
  (`TOKEN_PREFIX_MAX`) pour accepter le jeton après ≤ 1 amorce.
  **Non présent dans `origin/dev`** (mesuré : worktree
  `t_5245f7ab` est à `origin/dev` @ `2027333`, 0 commits en avant,
  0 occurrence de `TOKEN_PREFIX_MAX`). Le tranchement `/ok` de
  #36 **n'est faisable sans faux négatif qu'après merge de la
  PR #46 sur `dev`**.
- **`tests/test_decision_humaine.py`** — le banc de décision (banc
  34 cas : 4 « porte le jeton » + 4 « le cite » + 1 grammaire
  refusée + les 25 cas antérieurs). Paramétré par
  `DECISION_MODULE` et `PJ_BRIDGE_COPY`.
- **`pipeline/pj_escalate.py`** ([[pj-escalate]]) — escalade
  déterministe des cartes bloquées vers Discord. Le tranchement
  `/ok` passe par `pj_decision.py` → `unblock` kanban, pas par
  l'escalade.
- **`pipeline/pj_notify.py`** ([[pj-notify]]) — notifications de
  décision. L'enfant #36 est notifiée puis fermée ; le parent est
  notifié, jamais fermé.
- **`tests/test_thread_description.py`** — le banc RED de la slice
  5 (10 cas, rejoué 10/10 RED). Le contrat testable de la
  convergence.
- **`pipeline/pj_room_keeper.py`** — porteur de l'écriture de la
  description (slice 5, non livrée). Miroirs dans `bridge/` et
  `agents/pj-master/scripts/`.
- **`skills/gh-kanban-bridge/scripts/discord_thread.py`** —
  helper Discord (adapter REST) : `create` / `send` / `rename` /
  `threads` / `delete`. La capacité `edit`/`pin` (upsert-desc) est
  **absente** du code (dans le GREEN perdu `6661362`).
- **`pipeline/pj_coverage_gate.py`** — gate de couverture du
  pont. A identifié #36 comme recouvrant #27 et #30 (travail en
  vol).

## Lecture SDD (spec-driven)

La spec de #36 est le **point à statuer** : le commit GREEN dev-5
`6661362` est absent du worktree partagé, la branche pointe sur le
RED test-5, et le banc rejoue 10/10 RED. Le livrable de #36 n'est
**pas** un code, mais **l'état de convergence de la slice 5 de
#19** : soit le code est repoussé et le banc passe GREEN, soit
l'escalade se poursuit. La doc décrit ce qui existe aujourd'hui
(le banc RED, le travail non livré, le worktree de re-push) —
pas une intention.

Le manifeste `specs/19/slices.json` (le plan de slices) est
**absent du dépôt** (mesuré) — il est la source de la ligne
`**Branche**` du bloc Description ; son absence est gérée par le
contrat (ligne omise + log bruyant).

## Lecture DDD (bounded contexts, agrégats, événements)

- **Bounded context traversé** : *décision humaine sur blocage*
  (contexte #5, livré) au service du contexte *convergence /
  livraison* (slice 5 de #19). #36 est une **re-import** de ce
  contexte : elle ne crée pas de nouveau bounded context, elle
  réutilise l'existant.
- **Agrégat racine** : la **carte `t_f725879f` (conv-5)** —
  invariant : elle ne repart en `ready` que sur un `/ok` humain
  portant son `id` exact. L'**issue #36** est l'objet de décision
  qui la matérialise (2ᵉ import après #27 et #30).
- **Value objects** : le **branch head SHA** (attendu : `6661362`
  ou son équivalent ; mesuré : `49bb284` sur
  `wt/issue-19-discord-thread-title-description`, `2027333` sur
  `origin/dev`) ; le **commit SHA** de la slice 5 ; l'
  **idempotency-key** `gh-issue-36` ; le **caveat de lissage**
  (body pointe vers `t_7979348c` et non `t_f725879f`).
- **Domain events** : `/ok` humain sur l'issue #36 → unblock de la
  carte référencée (`t_7979348c` ou `t_f725879f` selon le
  verdict t3) → re-push de `6661362` (ou son équivalent) par
  `dev-5`/`dispatcher` sur `wt/issue-19-discord-thread-title-description`
  → convergence GREEN → doc → doc-review → PR (t6) → merge.

## Lecture TDD (contrats testables)

Le contrat testable de #36 n'est pas un code, mais **un invariant
mesurable** :

- **Le branch head de `wt/issue-19-discord-thread-title-description`
  contient le commit `6661362` (ou son équivalent)** — vérifiable
  par `git cat-file -t 6661362` dans le dépôt principal et par
  `git log --oneline` sur la branche.
- **Le banc `tests/test_thread_description.py` passe GREEN** —
  10 cas, rejouable sans Discord ni réseau (sources injectées).
- **Le banc `tests/test_decision_humaine.py` passe GREEN** — 34
  cas (après merge de la PR #46 sur `dev`), rejouable sans réseau.

Ces invariants sont mesurables par `pj_graphwatch` (couverture
commit-à-commit + chemin réel du worktree) et par le pont de
couverture (`pj_coverage_gate`) qui a identifié #36 comme
recouvrant #27 et #30.

## Lecture hexagonale (le core reste pur)

Le **core pur** de la slice 5 est `build_description_lines`
(fonction pure : issue_url, branch, pr_url → list[str], 0 réseau,
0 horloge, 0 aléa). L'écriture du message épinglé et de l'épingle
passe par le helper `discord_thread.py` (adapter REST, hors
core). Le contrat d'interface (marqueur `[description]`,
`build_description_for_card`, `sync_description`,
`sync_all_descriptions`) est testable sans Discord : les sources
et l'adaptateur sont injectés.

La frontière à respecter : **la description est une lecture
d'état** (gh/git/blackboard) résolue **hors** du core, puis
injectée dans le formateur pur. Jamais l'inverse : le formateur
ne lit pas le réseau.

Le core pur de la décision est `pj_decision.py`
(`decision_from_comment` calcule, l'appelant applique) — aucune
modification de code n'est attendue de ce cadrage.

## Composants impactés par l'issue #36

| composant | impact | slice #19 |
|---|---|---|
| `pipeline/pj_decision.py` | core pur de décision `/ok` (fix `8e35b6e` non mergé dans `origin/dev`) | 4 (issue #5) |
| `tests/test_decision_humaine.py` | banc 34 cas (après merge PR #46) | 4 (issue #5) |
| `tests/test_thread_description.py` | banc RED (livré, `26bad5d` + `49bb284`) | 5 |
| `pipeline/pj_room_keeper.py` + miroirs | porteur de l'écriture de la description (**non livré**) | 5 |
| `pipeline/engine.py` | formateur pur du titre (livré, slices 3–4) | 3–4 |
| `pipeline/pj_escalate.py` | `thread_index` élargi (livré, slice 2) | 2 |
| `plugins/pj-buttons/pj-buttons/__init__.py` | `THREAD_NAME_RE` élargi (livré, slice 2) | 2 |
| `skills/gh-kanban-bridge/scripts/discord_thread.py` | capacité `edit`/`pin` à ajouter (**non livré**) | 5 |
| `bridge/pj_room_keeper.py` + `agents/pj-master/scripts/pj_room_keeper.py` | miroirs du keeper (**non livrés**) | 5 |
| `pipeline/pj_coverage_gate.py` | identification de #36 comme recouvrant #27/#30 | — |

## Hors-scope

- **Le re-push de `6661362`** : porté par `dev-5`/`dispatcher` sur
  le worktree `t_4d471dce` (`wt/issue-19-restore-green-5`),
  **jamais** par ce cadrage.
- **La convergence effective de la slice 5** : portée par la carte
  `t_f725879f` après le `/ok` humain.
- **Les slices 1–4 de #19** : déjà livrées, cadrées par la note
  `issue-19` et la note composant `pj-thread-name` (slice 4).
- **La duplication bridge↔pipeline↔agents des `pj_*.py`** :
  divergence connue, non traitée par #36.
- **Le verdict de convergence** : porté par `pj-test` sur la
  carte `t_f725879f`, pas par ce cadrage.
- **Le caveat de lissage** (body pointe vers `t_7979348c` et non
  `t_f725879f`) : à trancher par t3 grill-me (t_9f15f1ad), pas par
  ce cadrage.
- **Le merge de la PR #46 sur `dev`** (fix `8e35b6e`) : hors
  périmètre de ce cadrage, mais **prérequis** pour le
  tranchement `/ok` sans faux négatif.

## Frontières traversées (résumé)

```
issue #36 (GitHub, labels decision + kanban, re-import)
  → commentaire /ok humain (surface de décision)
  → unblock de t_7979348c ou t_f725879f (kanban, selon verdict t3)
  → re-push de 6661362 sur wt/issue-19-discord-thread-title-description (git)
  → banc test_thread_description.py GREEN (preuve de livraison)
  → convergence GREEN → doc → doc-review → PR (t6) → merge
```

Deux frontières : **GitHub ↔ kanban** (décision → effet) et
**git ↔ worktree partagé** (preuve de livraison). Le point de
fragilité n'est pas l'appel réseau mais **la couverture
commit-à-commit** : un commit absent du branch head est un
travail non livré, quel que soit le handoff du worker.

## État mesuré (2026-10-09, rejouable)

- `origin/dev` = `2027333` (worktree partagé de l'issue #36 :
  `t_5245f7ab`, branche `wt/t_5245f7ab`, 0 commits en avant).
- `git cat-file -t 6661362` → **fatal : Not a valid object name**
  (commit absent du dépôt local et du remote).
- `wt/issue-19-discord-thread-title-description` (worktree
  `t_c22a7e74`) = `dbf73da` (docs issue-41), **0 occurrence** de
  `6661362` dans `pipeline/`, `bridge/`, `skills/`, `tests/`.
- `pipeline/pj_decision.py` (worktree `t_5245f7ab`) : **0
  occurrence** de `TOKEN_PREFIX_MAX` / `_token_index` — le fix
  `8e35b6e` n'est pas dans `origin/dev`.
- `tests/test_decision_humaine.py` : 34 cas (après le fix
  `8e35b6e` sur la branche `fix/decision-jeton-apres-amorce`,
  non mergé dans `origin/dev`).
- `tests/test_thread_description.py` : **10/10 RED** rejoué.
- `specs/` absent du dépôt (mesuré).
- `skills/gh-kanban-bridge/scripts/discord_thread.py` : commandes
  `create`, `send`, `threads`, `rename` seulement — pas
  d'`upsert-desc`, pas de `pin`.
- Carte `t_7979348c` : `blocked` (crash de worker, run 292,
  `gave_up` sticky).
- Carte `t_f725879f` : `blocked` (point à statuer principal).
- `pj_docs_lint.py` sur `/home/elix/pj-repos/hermes-workflow` →
  `exit=0` (mesuré avant l'ajout de cette note).
