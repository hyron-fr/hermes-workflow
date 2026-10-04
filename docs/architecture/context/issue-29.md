---
type: context
status: draft
tags: [architecture, convergence, decision, escalation, discord, notification, delivery-proof, cadrage]
issues: [29]
---

# Cadrage architectural — issue #29 « slice 5/5 — convergence »

## Positionnement (cadre exact)

L'issue #29 est une **escalade de décision** (`label: decision` + `kanban`,
`idempotency-key gh-issue-29`) de la carte **`t_f725879f`** (« slice 5/5 —
convergence », assignée à `pj-test`, board `pj-hermes-workflow`), bloquée sur
le chantier **#19** (« Discord thread title and description update »). C'est la
deuxième escalade de cette carte : l'issue **#27** (« slice 5/5 —
convergence », `label: decision`, issue enfant du 03/10) avait déjà escaladé
`conv-5` avec le même motif ; #29 est ré-importée par le pont de couverture
(`gh-issue-29`) après le verdict de #27.

Le **point à statuer** (tel quel, mesuré) : le commit **GREEN dev-5 `6661362`**
est **absent du worktree partagé**
(`/home/elix/pj-repos/hermes-workflow/.worktrees/t_c22a7e74`, branche
`wt/issue-19-discord-thread-title-description`) : branch head = `49bb284`
(RED test-5), **0 occurrence** de l'API slice 5
(`DESCRIPTION_MARKER` / `build_description_lines` /
`build_description_for_card` / `sync_description` / `sync_all_descriptions`)
dans `pipeline/`, `bridge/`, `skills/`, et le banc
`tests/test_thread_description.py` est rejoué **10/10 RED**. Impossible de
juger la convergence sans le code.

**Décision demandée** : commentez l'issue avec le jeton `/ok` en premier
élément → la carte `t_f725879f` est débloquée et repart en file ; le re-poussage
du GREEN (nouveau commit sur `wt/issue-19-discord-thread-title-description`)
est porté par **dev-5/dispatcher**, jamais par ce cadrage. Tout autre
commentaire est une demande d'éclaircissement et ne débloque rien.

Le présent cadrage **ne tranche pas** : il positionne le point à statuer dans
l'architecture existante, identifie les composants impactés, et fixe les
critères de décision. Le verdict humain (`/ok` sur l'issue) débloque la carte
`conv-5` ; le re-push effectif suit.

## Croisement infrastructure / fonctionnel / code

### Infrastructure (frontières traversées)

- **GitHub** — surface de décision (commentaire `/ok` sur l'issue #29,
  `idempotency-key gh-issue-29`) et surface de preuve (commits de la branche,
  PR éventuelle). Le commentaire du gate de couverture a identifié #29 comme
  recouvrant #19 et #27 (travail en vol) : c'est la **même carte bloquée**
  (`t_f725879f`), escaladée deux fois.
- **Git / worktree partagé** — surface de livraison : le branch head de
  `wt/issue-19-discord-thread-title-description` est la **preuve de livraison**
  de la slice 5. Un commit absent du branch head = travail non livré, quel que
  soit le handoff du worker (mesuré : le handoff de `dev-5` revendiquait
  « 0 0 vs `@{u}`, arbre propre » sur un commit introuvable).
- **Kanban Hermes** — source de vérité de l'état des cartes : `t_f725879f`
  (conv-5) en `blocked` porte le point à statuer ; `t_21efb666` (la carte de
  convergence issue #29) est parente du graphe de l'issue #19.

### Fonctionnel (capacité traversée)

La capacité traversée est **convergence + preuve de livraison**, pas la
fonctionnalité #19 elle-même. #19 est déjà cadré par la note de cadrage
`issue-19` (worktree t_c22a7e74, commit `ed75032`, livrée sur la branche non
mergée) et par la note composant `pj-thread-name` (slice 4, commit
`27c453c`) ; ses slices 1–4 sont livrées, et la slice 5 est en cours de
convergence. Ce que #29 porte :

- **le point de décision** : le travail de la slice 5 est-il livré ?
- **la chaîne de re-push** : qui repousse `6661362` (ou son équivalent) sur
  `wt/issue-19-discord-thread-title-description` ?
- **le verdict de convergence** : après re-push, le banc
  `tests/test_thread_description.py` passe-t-il GREEN ?

C'est une **boucle de décision + re-livraison**, pas une évolution de
fonctionnalité. Le code de la slice 5 (bloc Description épinglé,
`build_description_lines`, `sync_description`, capacité `edit/pin` du helper
Discord) est décrit par le banc `tests/test_thread_description.py` — ce
cadrage ne le redécrit pas.

### Code (composants impactés)

- **`tests/test_thread_description.py`** (worktree t_c22a7e74, commit
  `26bad5d` + `49bb284`) — le banc RED de la slice 5 : 10 cas, rejoué 10/10
  RED. C'est lui qui **verrouille le contrat d'interface** de la moitié
  description de #19 (Q2 = 2b) : `DESCRIPTION_MARKER = "[description]"`,
  `build_description_lines`, `description_log_lines`,
  `keeper.build_description_for_card`, `keeper.sync_description`,
  `keeper.sync_all_descriptions`. Sources injectées, 0 réseau.
- **`pipeline/pj_room_keeper.py`** (worktree t_c22a7e74, commit `422878f`
  slice 4) — porteur de l'écriture du titre (slice 4 livrée : `sync_all_titles`
  + coalescence `TITLE_WINDOW = 600`) ; **porteur attendu de l'écriture de la
  description** (slice 5, non livrée : `sync_all_descriptions` à ajouter dans
  le même cycle de tick, best-effort). C'est le seul composant qui sait lire
  l'état du board **et** le plan de slices.
- **`pipeline/engine.py`** (worktree t_c22a7e74) — formateur pur du titre
  (`format_title`, `title_icon`, `TITLE_ICONS`, `NAME_MAX = 100`, slice 3
  livrée) ; le `rename_thread` délègue désormais au keeper (slice 4). La
  description **n'appartient pas** à `engine.py` : c'est une lecture d'état
  (gh/git) qui doit être résolue hors du core, puis injectée.
- **`pipeline/pj_escalate.py`** (worktree t_c22a7e74, commit `b1ed6b4` slice 2
  + `04099bc`) — `thread_index` élargi au nouveau format (motif
  `(?:\S+\s+)?<repo>\|#0*(\d+)\b`, L267). Non impacté par la slice 5.
- **`plugins/pj-buttons/pj-buttons/__init__.py`** (worktree t_c22a7e74, commit
  `b1ed6b4`) — `THREAD_NAME_RE` élargi aux deux séparateurs (`#` et `|#`,
  L35). Non impacté par la slice 5.
- **`skills/gh-kanban-bridge/scripts/discord_thread.py`** — helper Discord
  (adapter REST) : `create` / `send` / `rename` / `threads` / `delete`.
  **Aucune** capacité `pin` ni `edit` de message à ce stade. La slice 5
  l'étend (capacité `edit`/`pin` du helper).
- **`bridge/pj_room_keeper.py`** + **`agents/pj-master/scripts/pj_room_keeper.py`**
  (worktree t_c22a7e74) — miroirs/copies du keeper. La slice 5 les touche
  aussi (l'écriture de la description y est portée).

## Lecture SDD (spec-driven)

La spec de #29 est le `point à statuer` : le commit GREEN dev-5 `6661362` est
absent du worktree partagé. Le livrable de #29 n'est **pas** un code, mais
**l'état de convergence de la slice 5 de #19** : soit le code est repoussé et
le banc passe GREEN, soit l'escalade se poursuit. La doc décrit ce qui existe
aujourd'hui (le banc RED, le travail non livré, le worktree de re-push) — pas
une intention.

## Lecture DDD (bounded contexts, agrégats, événements)

- **Bounded context** : *convergence / livraison* — chevauche
  *développement* (slice 5 de #19) et *décision humaine* (l'escalade #27/#29),
  sans en être un nouveau : c'est la **jonction** entre les deux.
- **Agrégat racine** : la **carte `t_f725879f` (conv-5)** — invariant : elle ne
  repart en `ready` que sur un `/ok` humain portant son `id` exact (le
  commentaire sur l'issue #29). L'**issue #29** est l'objet de décision qui
  matérialise la carte.
- **Value objects** : le **branch head SHA** (`49bb284` mesuré, `6661362`
  attendu) ; le **commit SHA** de la slice 5 ; l'**idempotency-key**
  `gh-issue-29`.
- **Domain events** : `/ok` humain sur l'issue #29 → unblock de
  `t_f725879f` → re-push de `6661362` (ou son équivalent) par
  `dev-5`/`dispatcher` sur `wt/issue-19-discord-thread-title-description` →
  convergence GREEN → doc → doc-review → PR (t6) → merge.

## Lecture TDD (contrats testables)

Le contrat testable de #29 n'est pas un code, mais **un invariant mesurable** :

- **Le branch head de `wt/issue-19-discord-thread-title-description` contient
  le commit `6661362` (ou son équivalent)** — vérifiable par
  `git cat-file -t 6661362` dans le dépôt principal et par
  `git log --oneline` sur la branche.
- **Le banc `tests/test_thread_description.py` passe GREEN** — 10 cas,
  rejouable sans Discord ni réseau (sources injectées).
- **Les 10 cas du banc** sont les critères d'acceptation de la slice 5 ;
  leur état RED/GREEN est la preuve de convergence.

Ces invariants sont mesurables par `pj_graphwatch` (couverture
commit-à-commit + chemin réel du worktree, cf. commits `009f0a7`, `9e49771`,
`318bea1` de l'issue #2) et par le pont de couverture
(`pj_coverage_gate`) qui a identifié #29 comme recouvrant #19 et #27.

## Lecture hexagonale (le core reste pur)

Le core pur de la slice 5 est `build_description_lines` (fonction pure :
issue_url, branch, pr_url → list[str], 0 réseau, 0 horloge, 0 aléa). L'écriture
du message épinglé et de l'épingle passe par le helper `discord_thread.py`
(adapter REST, hors core). Le contrat d'interface (marqueur `[description]`,
`build_description_for_card`, `sync_description`, `sync_all_descriptions`)
est testable sans Discord : les sources et l'adaptateur sont injectés.

La frontière à respecter : **la description est une lecture d'état**
(gh/git/blackboard) résolue **hors** du core, puis injectée dans le
formateur pur. Jamais l'inverse : le formateur ne lit pas le réseau.

## Composants impactés par l'issue #29

| composant | impact | slice #19 |
|---|---|---|
| `tests/test_thread_description.py` | banc RED (livré, `26bad5d` + `49bb284`) | 5 |
| `pipeline/pj_room_keeper.py` + miroirs | porteur de l'écriture de la description (**non livré**) | 5 |
| `pipeline/engine.py` | formateur pur du titre (livré, slices 3–4) | 3–4 |
| `pipeline/pj_escalate.py` | `thread_index` élargi (livré, slice 2) | 2 |
| `plugins/pj-buttons/pj-buttons/__init__.py` | `THREAD_NAME_RE` élargi (livré, slice 2) | 2 |
| `skills/gh-kanban-bridge/scripts/discord_thread.py` | capacité `edit`/`pin` à ajouter (**non livré**) | 5 |
| `bridge/pj_room_keeper.py` + `agents/pj-master/scripts/pj_room_keeper.py` | miroirs du keeper (**non livrés**) | 5 |

## Hors-scope

- **Le re-push de `6661362`** : porté par `dev-5`/`dispatcher` sur le worktree
  t_4d471dce (`wt/issue-19-restore-green-5`), **jamais** par ce cadrage.
- **La convergence effective de la slice 5** : portée par la carte
  `t_f725879f` après le `/ok` humain.
- **Les slices 1–4 de #19** : déjà livrées, cadrées par la note `issue-19`
  (worktree t_c22a7e74) et la note composant `pj-thread-name` (slice 4).
- **La duplication bridge↔pipeline↔agents des `pj_*.py`** : divergence connue
  (les 3 copies du keeper sont identiques à ce stade), non traitée par #29.
- **Le verdict de convergence** : porté par `pj-test` sur la carte
  `t_f725879f`, pas par ce cadrage.

## Frontières traversées (résumé)

```
issue #29 (GitHub, label decision + kanban)
  → commentaire /ok humain (surface de décision)
  → unblock de t_f725879f (kanban)
  → re-push de 6661362 sur wt/issue-19-discord-thread-title-description (git)
  → banc test_thread_description.py GREEN (preuve de livraison)
  → convergence GREEN → doc → doc-review → PR (t6) → merge
```

Deux frontières : **GitHub ↔ kanban** (décision → effet) et
**git ↔ worktree partagé** (preuve de livraison). Le point de fragilité n'est
pas l'appel réseau mais **la couverture commit-à-commit** : un commit absent du
branch head est un travail non livré, quel que soit le handoff du worker.

## État mesuré (2026-10-04)

- `origin/dev` = `009f0a7` (3 commits graphwatch : `009f0a7`, `9e49771`,
  `318bea1`).
- `wt/issue-19-discord-thread-title-description` :
  - **local** (worktree t_c22a7e74) = `49bb284` (16 commits au-dessus de
    `origin/dev`), dernier = `test(issue-19): nettoyage import inutiles du
    banc RED slice 5` ;
  - **remote** (`ls-remote`, relu 2026-10-04) = `03e09f1`, au-dessus de
    `49bb284` : le cadrage de l'issue #31 (« point de décision slice 5/5
    convergence #19 »). **Le re-push du GREEN n'a pas encore eu lieu** : le
    remote ne contient toujours pas l'API slice 5.
- `git cat-file -t 6661362` → **fatal : Not a valid object name** (commit
  absent du dépôt local et du remote).
- Worktree de re-push : `t_4d471dce` (`wt/issue-19-restore-green-5`, base
  `009f0a7`), branché par la carte t1 de l'issue #30.
- Banc `tests/test_thread_description.py` : **10/10 RED** rejoué.
- `pj_docs_lint.py` sur `/home/elix/pj-repos/hermes-workflow` → `exit=0`.
