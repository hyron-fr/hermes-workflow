---
type: context
status: draft
tags: [architecture, decision, escalation, conv-5, green-lost, cadrage, re-import, miroir, lissage]
issues: [63]
---

# Cadrage architectural — issue #63 « t3b doc-cadrage »

## Positionnement (cadre exact)

L'issue **#63** est un **ticket de décision** (`labels: decision + kanban`,
`OPEN`) qui matérialise un **point à statuer** sur la carte
**`t_e706d361`** (board `pj-hermes-workflow`, assignée à `pj-master`,
statut `todo` — pipeline déployé, 3 parents insatisfaits : `t_7fc9ee0d`
todo, `t_9f15f1ad` blocked, `t_d6625664` todo).

**Nature** : c'est le **3ᵉ import** (miroir) du même point à statuer que
les issues **#27**, **#30** et **#36** (escalade de la carte `conv-5`
**`t_f725879f`** du chantier #19, « slice 5/5 — convergence », GREEN
dev-5 `6661362` perdu). Le pont de couverture a identifié #63 comme
recouvrant #36 (« t3b doc-cadrage ») — le commentaire du gate du
2026-10-08 09:28 l'atteste : « recouvre du travail en vol : #36 ».

**Caveat de lissage (mesuré, 2026-10-11)** : le body de l'issue #63
pointe vers la carte `t_e706d361` (la racine du pipeline de #36, statut
`todo`, assignée à `pj-master`), **et non** vers la carte `t_f725879f`
(conv-5, statut `blocked`, assignée à `pj-test`) qu'elle décrit en
chaîne. Le body de #36 pointait lui vers `t_7979348c` (t3b doc-cadrage
de #30, bloquée après crash worker). Le verdict t3 grill-me de #36
(09/10, carte `t_9f15f1ad`) a tranché que la cible effective du `/ok`
est `t_f725879f` (conv-5) : le lissage de #63 est du même ordre —
la chaîne conv-5 (#19→#27→#28→#30→#31→#36→#40→#41→#44→#45→#63) ne
contient ni `t_e706d361` ni `t_7979348c` ; le point à statuer effectif
reste le re-poussage du GREEN slice 5 sur `t_f725879f`.

**État mesuré de la branche (2026-10-11, worktree partagé
`t_c22a7e74`, branche `wt/issue-19-discord-thread-title-description`) :**

- HEAD local = `9fcd207` (docs cadrage issue #73), 30 commits au-dessus
  de `origin/dev` (`2027333`).
- Le banc `tests/test_thread_description.py` est présent sur la branche
  (absent de `origin/dev`).
- Le commit GREEN `6661362` est **toujours absent** de tout le dépôt
  (`git cat-file -t 6661362` → `fatal: Not a valid object name`,
  re-vérifié 2026-10-11).
- La suite de docs cadrage s'est enrichie sur la branche : issues
  #26, #31, #41, #45, #73, #74, #75, #80 (miroirs successifs du même
  point à statuer conv-5).

**Décision demandée** : commentez l'issue #63 avec le jeton `/ok` en
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
  #63) et surface de preuve (commits de la branche, PR éventuelle).
  L'issue #63 est un **re-import** du point à statuer : le pont de
  couverture (`pj_coverage_gate`) a identifié #63 comme recouvrant #36
  (travail en vol sur `t_e706d361` / `t_f725879f`).
- **Git / worktree partagé** — surface de livraison : le branch head
  de `wt/issue-19-discord-thread-title-description` est la **preuve
  de livraison** de la slice 5. Le commit `6661362` est absent
  (mesuré 2026-10-11 : `git cat-file -t 6661362` → `fatal: Not a
  valid object name`).
- **Kanban Hermes** — source de vérité de l'état des cartes :
  `t_f725879f` (conv-5) est en `blocked` (le point à statuer
  principal, verdict NEGATIF de `pj-test` 2026-10-08 : banc 7/10,
  3 rouges nommés, helper incomplet, push non vérifié) ;
  `t_e706d361` (racine du pipeline de #36) est en `todo` (3 parents
  insatisfaits : `t_7fc9ee0d` todo, `t_9f15f1ad` blocked,
  `t_d6625664` todo). La carte de convergence de #63 est
  `t_944b4bb3` (racine du graphe de #63, `todo`, parents = t1..t5 +
  t3b de #63).

### Fonctionnel (capacité traversée)

La capacité traversée est **décision humaine sur blocage** (issue
#5, livrée — [[pj-decision]], [[pj-notify]]) au service de la
capacité **convergence / preuve de livraison** de la slice 5 du
chantier #19. #63 ne traverse aucune nouvelle capacité
fonctionnelle : elle **réutilise** la boucle de décision #5 et le
pont de couverture, et ré-importe le point à statuer de
`t_f725879f` (ou de `t_e706d361`, selon le caveat de lissage).

Les deux moitiés de #19 :
- **Moitié titre (slices 1–4, livrées)** : formateur pur
  `format_title` + table `TITLE_ICONS` dans `pipeline/engine.py`,
  3 lecteurs du nom de thread, keeper comme écrivain unique du
  titre avec coalescence par fenêtre `TITLE_WINDOW = 600 s`.
- **Moitié description (slice 5, GREEN perdu)** : le bloc
  Description épinglé dans le fil Discord — c'est ce que le point
  à statuer porte. Le code GREEN existe en working tree non
  commité (mesuré 2026-10-10 par `pj-master` : HEAD `6a2d8e3`,
  uncommitted diff sur `pipeline/pj_room_keeper.py` +43/−13 lignes,
  banc 7/10) mais n'est **pas** sur la branche committée.

### Code (composants impactés)

- **`pipeline/pj_decision.py`** ([[pj-decision]]) — core pur de
  décision `/ok` (issue #5, slice 4). Le fix `8e35b6e`
  (`fix/decision-jeton-apres-amorce`) élargit `_token_index`
  (`TOKEN_PREFIX_MAX`) pour accepter le jeton après ≤ 1 amorce.
  **Non présent dans `origin/dev`** (mesuré : worktree
  `t_a9c53a5c` est à `origin/dev` @ `2027333`, 0 commits en avant,
  0 occurrence de `TOKEN_PREFIX_MAX`). Le tranchement `/ok` de #63
  **n'est faisable sans faux négatif qu'après merge de la
  PR #46 sur `dev`**.
- **`tests/test_thread_description.py`** — le banc de décision
  (10 cas : 3 nominal / 3 limite / 4 erreur). Présent sur
  `wt/issue-19-discord-thread-title-description`, absent de
  `origin/dev`. État mesuré 2026-10-10 : 7 passed / 3 failed
  (les 3 rouges nommés par `pj-test` : L725 `sync_description`
  sans `issue_url_lookup`, L657 `_gh_repo()` perd l'org, L824+
  `sync_all_descriptions` sans `issue_url_lookup`).
- **`pipeline/pj_room_keeper.py`** — porteur de l'écriture de la
  description (slice 5, non livrée sur la branche). Uncommitted
  diff mesuré 2026-10-10 : +43/−13 lignes (correctif OOM +
  3 retouches keeper). Le correctif OOM (boucle de journalisation
  infinie dans `build_description_for_card`, `logger=log_list.append`
  réinjecté dans la boucle → OOM-kill du cgroup 4 GiB, corrigé par
  itération sur instantané `_emit`) est **nécessaire** pour que le
  banc ne tue pas le worker.
- **`pipeline/pj_escalate.py`** ([[pj-escalate]]) — escalade
  déterministe des cartes bloquées vers Discord. Le tranchement
  `/ok` sur #63 passe par cette chaîne si la carte cible est
  `blocked`. Non impacté par la slice 5.
- **`bridge/pj_*.py`** + **`pipeline/pj_*.py`** +
  **`agents/pj-master/scripts/pj_*.py`** — copies live/versionnées.
  Divergence D1 vivante : `pj_escalate.py` live sha
  `0ed3264c…` ≠ versionné `87c3463b…` (déclarée, jamais silencieuse).
- **`skills/gh-kanban-bridge/scripts/discord_thread.py`** — helper
  Discord (adapter REST). Les capacités `upsert-desc` et `pin` sont
  **absentes** (mesuré 2026-10-10) — le 4ᵉ fichier du périmètre
  GREEN n'est pas livré. La slice 5 doit les ajouter.

## Lecture SDD (spec-driven)

La spec de #63 est le `point à statuer` : le commit GREEN dev-5
`6661362` est absent de tous les worktrees et de `origin`. Le
livrable de #63 n'est **pas** un code, mais **l'état de convergence
de la slice 5 de #19** : soit le code est repoussé et le banc passe
GREEN, soit l'escalade se poursuit. La doc décrit ce qui existe
aujourd'hui (le banc 7/10 sur la branche, le correctif OOM en
working tree, le worktree de re-push) — pas une intention.

## Lecture DDD (bounded contexts, agrégats, événements)

- **Bounded context** : *convergence / livraison* — chevauche
  *développement* (slice 5 de #19) et *décision humaine* (l'escalade
  #27/#29/#30/#36/#63), sans en être un nouveau : c'est la
  **jonction** entre les deux.
- **Agrégat racine** : la **carte `t_f725879f` (conv-5)** — invariant :
  elle ne repart en `ready` que sur un `/ok` humain portant son `id`
  exact (le commentaire sur l'issue #63). L'**issue #63** est l'objet
  de décision qui matérialise la carte.
- **Value objects** : le **branch head SHA** (`9fcd207` mesuré
  2026-10-11, `6661362` attendu) ; le **commit SHA** de la slice 5 ;
  l'**idempotency-key** `gh-issue-63`.
- **Domain events** : `/ok` humain sur l'issue #63 → unblock de
  `t_e706d361` (ou `t_f725879f` selon le lissage tranché) →
  re-push de `6661362` (ou son équivalent) par `dev-5`/`dispatcher`
  sur `wt/issue-19-discord-thread-title-description` →
  convergence GREEN → doc → doc-review → PR (t6) → merge.

## Lecture TDD (contrats testables)

Le contrat testable de #63 n'est pas un code, mais **un invariant
mesurable** :

- **Le branch head de `wt/issue-19-discord-thread-title-description`
  contient un commit GREEN de la slice 5** — vérifiable par
  `git log --oneline` sur la branche et par `git cat-file -t` sur
  le SHA du commit.
- **Le banc `tests/test_thread_description.py` passe GREEN** — 10 cas,
  rejouable sans Discord ni réseau (sources injectées).
- **Les 3 rouges nommés par `pj-test` (2026-10-08)** sont corrigés :
  `sync_description` passe `issue_url_lookup` ; `_gh_repo()`
  préserve l'org ; `sync_all_descriptions` passe `issue_url_lookup`.

Ces invariants sont mesurables par `pj_graphwatch` (couverture
commit-à-commit + chemin réel du worktree) et par le pont de
couverture (`pj_coverage_gate`) qui a identifié #63 comme recouvrant
#36.

## Lecture hexagonale (le core reste pur)

Le core pur de la slice 5 est `build_description_lines` (fonction
pure : issue_url, branch, pr_url → list[str], 0 réseau, 0 horloge,
0 aléa). L'écriture du message épinglé et de l'épingle passe par le
helper `discord_thread.py` (adapter REST, hors core). Le contrat
d'interface (marqueur `[description]`, `build_description_for_card`,
`sync_description`, `sync_all_descriptions`) est testable sans
Discord : les sources et l'adaptateur sont injectés.

La frontière à respecter : **la description est une lecture d'état**
(gh/git/blackboard) résolue **hors** du core, puis injectée dans le
formateur pur. Jamais l'inverse : le formateur ne lit pas le réseau.

## Composants impactés par l'issue #63

| composant | impact | état mesuré 2026-10-11 |
|---|---|---|
| `tests/test_thread_description.py` | banc de convergence (sur la branche, absent de dev) | 7/10 (mesuré 10-10) |
| `pipeline/pj_room_keeper.py` | porteur de l'écriture de la description | uncommitted diff +43/−13 (correctif OOM + 3 retouches) |
| `pipeline/engine.py` | formateur pur du titre (livré, slices 3–4) | présent sur la branche |
| `pipeline/pj_escalate.py` | escalade déterministe (non impacté par slice 5) | D1 vivante (live ≠ versionné) |
| `skills/gh-kanban-bridge/scripts/discord_thread.py` | capacités `upsert-desc`/`pin` absentes | non livré |
| `pipeline/pj_decision.py` | core pur `/ok` (fix `8e35b6e` non sur dev) | PR #46 en attente |
| `bridge/pj_*.py` + `agents/pj-master/scripts/pj_*.py` | miroirs/copies du keeper | divergences déclarées |

## Hors-scope

- **Le re-push du commit GREEN slice 5** : porté par `dev-5`/
  `dispatcher` sur le worktree partagé, **jamais** par ce cadrage.
- **La convergence effective de la slice 5** : portée par la carte
  `t_f725879f` après le `/ok` humain.
- **Les slices 1–4 de #19** : déjà livrées, cadrées par la note
  `issue-19` et la note composant `pj-thread-name`.
- **La duplication bridge↔pipeline↔agents des `pj_*.py`** :
  divergence connue (les copies sont identiques à ce stade),
  non traitée par #63.
- **Le verdict de convergence** : porté par `pj-test` sur la carte
  `t_f725879f`, pas par ce cadrage.
- **Les imports précédents du même point à statuer** (#27, #29,
  #30, #31, #36, #40, #41, #44, #45, #73, #74, #75, #80) : chacun
  porte sa propre note de cadrage ; #63 est le 3ᵉ miroir
  documentaire (après #36 et les notes issues #41/#45/#73/#74/#75/#80).

## Frontières traversées (résumé)

```
issue #63 (GitHub, label decision + kanban)
  → commentaire /ok humain (surface de décision)
  → unblock de t_e706d361 / t_f725879f (kanban)
  → re-push du GREEN slice 5 sur wt/issue-19-discord-thread-title-description (git)
  → banc test_thread_description.py GREEN (preuve de livraison)
  → convergence GREEN → doc → doc-review → PR (t6) → merge
```

Deux frontières : **GitHub ↔ kanban** (décision → effet) et
**git ↔ worktree partagé** (preuve de livraison). Le point de
fragilité n'est pas l'appel réseau mais **la couverture
commit-à-commit** : un commit absent du branch head est un travail
non livré, quel que soit le handoff du worker.

## État mesuré (2026-10-11)

- `origin/dev` = `2027333`.
- `wt/issue-19-discord-thread-title-description` :
  - **local** (worktree partagé t_c22a7e74) = `9fcd207` (30 commits
    au-dessus de `origin/dev`), dernier = `docs(cadrage): issue #73 —
    5e escalade conv-5, point a statuer mesure au 2026-10-11, note
    issue-73 + MOC` ;
  - **remote** = `9fcd207` (poussé, `git ls-remote` vérifié).
- `git cat-file -t 6661362` → **fatal : Not a valid object name**
  (commit absent du dépôt local et du remote, re-vérifié
  2026-10-11).
- Worktree de l'issue #63 : `t_a9c53a5c` (`wt/issue-63-doc-cadrage`,
  base `origin/dev` @ `2027333`, état clean).
- Banc `tests/test_thread_description.py` : **7/10** (mesuré
  2026-10-10, 3 rouges nommés par `pj-test`).
- Carte `t_f725879f` (conv-5) : `blocked` (verdict NEGATIF 2026-10-08,
  15 runs : 10 crashed, 1 timed_out, 4 blocked).
- Carte `t_e706d361` (racine pipeline #36) : `todo` (3 parents
  insatisfaits).
- `pj_docs_lint.py` sur `/home/elix/pj-repos/hermes-workflow` →
  `exit=0`.
