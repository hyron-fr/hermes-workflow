---
type: context
status: draft
tags: [architecture, decision, escalation, recycle, convergence, slice-5, delivery-proof, cadrage]
issues: [68]
---

# Cadrage architectural — issue #68 « t2 mémoire projet » (point à statuer sur `t_5e667a92`)

## Positionnement (cadre exact)

L'issue **#68** (`label: decision` + `kanban`, `idempotency-key gh-issue-68`,
titre GitHub « t2 mémoire projet », parent GitHub **#31**) est un ticket de
**DÉCISION** : le point à statuer sur la carte **`t_5e667a92`** (« t2 mémoire
projet », assignée à `pj-master`, board `pj-hermes-workflow`, **blocked**
depuis le 2026-10-03), elle-même miroir du chantier **#31** (« slice 5/5 —
convergence », parent GitHub #19).

Ce n'est **ni** un ticket de dev **ni** un port main→dev : c'est l'escalade de
décision humaine de la boucle de livraison #5 ([[pj-decision]], [[pj-notify]],
[[pj-escalade]] : la boucle de décision #5), portée par le gate de couverture
[[pj-bridge-coverage-gate]].

### Mesure directe du blocage (état du 2026-10-11)

La carte `t_5e667a92` n'est **pas** bloquée par un point de décision : son
**run 283 a CRASHÉ** le 2026-10-03 18:29 (`pid 109877 not alive`,
`Provider temporarily unavailable — retrying automatically`, cycles 1/5→3/5,
interrupted during API call), avec `gave_up sticky` (`failures: 1`,
`limit: 1`, `retry_status: ready`). Le body de la carte est trivial
(`hindsight_recall` banque `pj` + post du résumé en commentaire) : **aucune
question n'est ouverte** sur le fil.

### Le point à statuer (tel quel, mesuré le 2026-10-11)

- **`/ok` en 1ᵉʳ élément** sur l'issue #68 → la carte `t_5e667a92` est
  **débloquée** et repart en file (unblock mécanique via la boucle de décision
  #5 : `decision_from_comment` calcule `effect=unblock`, l'appelant applique —
  jamais l'inverse).
- **Tout autre commentaire** est une demande d'éclaircissement : aucun geste,
  la carte reste bloquée.
- L'effet **attendant** (une fois la carte repartie) : le re-GREEN de la
  **slice 5 de #19** — le commit GREEN dev-5 `6661362` est **définitivement
  absent** (`git cat-file -t 6661362` → `fatal: Not a valid object name`,
  confirmé encore le 2026-10-11).

### Ce que le présent cadrage **ne tranche pas**

Il ne tranche **pas** le tranchement lui-même (le jeton `/ok` est porté par
l'humain sur le fil GitHub de l'issue #68) ni le contenu du re-GREEN (porté
par le dev après l'unblock). Il **positionne** : le point à statuer dans
l'architecture existante, les composants impactés, et les critères de
décision.

## Croisement infrastructure / fonctionnel / code

### Infrastructure (frontières traversées)

- **GitHub** — surface de décision : commentaire `/ok` sur l'issue #68.
  Adapter : `gh` CLI, lu par le pont. L'issue #68 est l'objet de décision
  enfant de la carte `t_5e667a92`.
- **Kanban Hermes** — source de vérité de l'état des cartes. L'effet est
  `unblock` de `t_5e667a92`, invoqué par le câblage de #5
  ([[pj-decision]] : `decision_from_comment` calcule, l'appelant applique).
- **Git / worktree partagé** — surface de livraison du re-GREEN : la branche
  `wt/issue-19-discord-thread-title-description` (worktree `t_c22a7e74`) est
  la **preuve de livraison** de la slice 5. État mesuré : GREEN partial
  commité (baseline `55e6659`), banc `3 failed, 7 passed`.
- **Aucun nouveau port** : les trois surfaces (GitHub, kanban, git) existent ;
  l'issue #68 réutilise la boucle de décision #5.

### Fonctionnel (capacité traversée)

La capacité traversée est **convergence + preuve de livraison** (pas une
fonctionnalité nouvelle). Le chantier #19 (« Discord thread title and
description update ») est déjà cadré par les notes `issue-27` (escalade 1ᵉʳ),
`issue-29` (escalade 2ᵉ), `issue-41` (escalade 4ᵉ) et `issue-81`
(escalade 5ᵉ), ainsi que par la note composant `pj-thread-name` (slices 2–4).
#68 porte :

- **le point de décision** : la carte `t_5e667a92` est-elle débloquée
  (unblock) ? (Le verdict grill-me t3 : `PROTOTYPE: non`, `AMBIGU: aucune`,
  `ARTEFACT: aucun` — aucune ambiguïté bloquante.)
- **la chaîne de livraison** : qui applique le re-GREEN (3 fixes keeper +
  `upsert-desc`/`pin`) ? (Le dev, après le `/ok`.)
- **le verdict de convergence** : après le re-GREEN, le banc
  `tests/test_thread_description.py` passe-t-il 10/10 GREEN ?

### Code (composants impactés)

| composant | état mesuré (2026-10-11) | impact slice 5 |
|---|---|---|
| `pipeline/engine.py` | `DESCRIPTION_MARKER` + `build_description_lines` présents (3 hits grep) | Livré dans le GREEN partial |
| `pipeline/pj_room_keeper.py` | `build_description_for_card`, `sync_description`, `sync_all_descriptions` présents ; GREEN partial commité (`55e6659` baseline) | 3 tests RED : 1 fix de logique de dédup + 1 fix de non-lèvement + 1 fix de gestion d'erreur `gh pr list` |
| `tests/test_thread_description.py` | 387 lignes, 10 cas, **3 failed, 7 passed** (rejoué 2026-10-11) | Banc qui gèle le contrat `contrat-5` |
| `skills/gh-kanban-bridge/scripts/discord_thread.py` | Commandes `create`/`send`/`rename`/`threads` seulement ; **`upsert-desc` + `pin` absents** (grep : 0 hit) | **`upsert-desc` + `pin` à ajouter** |

Le **core pur** à préserver : `build_description_lines` (composition pure :
issue_url, branch, pr_url → list[str], 0 réseau) et
`build_description_for_card` (sources injectées). L'écriture du message et
de l'épingle passent par l'adapter injecté `write_message` / le helper
Discord.

## Lecture SDD (spec-driven)

La spec est le body de l'issue **#31** (parent GitHub) : « slice 5/5 —
convergence », point à statuer sur `t_f725879f` (carte conv-5, chantier #19),
GREEN dev-5 `6661362` absent du worktree partagé, banc 10/10 RED. L'issue
#68 **est** le point à statuer de sa carte `t_5e667a92` (miroir de #31,
importé par le gate de couverture). Le verdict du grill-me (carte
`t_a33bafa1`) fixe le périmètre : `PROTOTYPE: non`, `AMBIGU: aucune`,
`ARTEFACT: aucun`. La doc décrit le livré : ici le « livré » attendu est le
GREEN 10/10 (3 fixes keeper + `upsert-desc`/`pin`) ; jusqu'au `/ok`, l'état
mesuré est **3 failed, 7 passed** + helper incomplet.

## Lecture DDD (bounded contexts, agrégats, événements)

- **Bounded context traversé** : *convergence / livraison* — chevauche
  *développement* (slice 5 de #19) et *décision humaine* (l'escalade
  conv-5), sans en être un nouveau : c'est la **jonction** entre les deux.
- **Agrégat racine** : la **carte `t_5e667a92`** (invariant : elle ne repart
  en `ready` que sur un `/ok` portant sa ligne canonique
  `carte: pj-hermes-workflow/t_5e667a92`). L'**issue #68** est l'objet de
  décision qui la matérialise.
- **Value objects** : le **branch head SHA** de
  `wt/issue-19-discord-thread-title-description` (mesuré 2026-10-11) ; le
  **banc 3 failed, 7 passed** (état de convergence partiel) ;
  l'**idempotency-key** `gh-issue-68` ; le verdict grill-me
  (`PROTOTYPE: non, AMBIGU: aucune`).
- **Domain events** : `/ok` humain sur l'issue #68 → unblock de
  `t_5e667a92` → re-spawn (grill-me reformule) → dev applique le re-GREEN
  (3 fixes keeper + `upsert-desc`/`pin`) → banc 10/10 GREEN → convergence →
  doc → doc-review → PR → merge.

## Lecture TDD (contrats testables)

Le contrat testable est le **banc `tests/test_thread_description.py`**
(387 lignes, 10 cas), rejouable sans Discord ni réseau (sources injectées) :

- `build_description_lines(issue_url, branch, pr_url, log=print) -> list[str]`
  — composition pure, 4 lignes, omission des `None`/vides (4 cas GREEN).
- `keeper.build_description_for_card(card, *, …, specs_reader, pr_reader,
  issue_url_lookup)` — assemblage des sources injectées (2 cas GREEN,
  1 cas RED : le reader qui lève ne doit pas tuer le tick).
- `keeper.sync_description(cards, *, fetch_messages, write_message, log=None)`
  — écrivain best-effort : dédup par marqueur, `edit` jamais second post
  (1 cas RED : un seul message épinglé mis à jour pas dupliqué).
- **1 cas RED supplémentaire** :
  `test_erreur_gh_pr_list_en_erreur_ligne_omise_tracee_pas_exception` —
  gestion d'erreur quand `gh pr list` lève (la ligne PR est omise mais tracée,
  pas d'exception).
- Les **3 cas RED** sont les critères d'acceptation restants de la slice 5 ;
  leur passage GREEN est la preuve de convergence.

## Lecture hexagonale (le core reste pur)

Le **core pur** : `build_description_lines` (fonction pure : issue_url,
branch, pr_url → list[str], 0 réseau, 0 horloge, 0 aléa) et
`build_description_for_card` (sources injectées, 0 réseau). L'écriture du
message épinglé et de l'épingle passe par le helper `discord_thread.py`
(adapter REST, hors core). Le contrat d'interface (marqueur `[description]`,
`sync_description`, `sync_all_descriptions`) est testable sans Discord :
les sources et l'adaptateur sont injectés.

La frontière à respecter : **la description est une lecture d'état**
(gh/git/blackboard) résolue **hors** du core, puis injectée dans le
formateur pur. Jamais l'inverse : le formateur ne lit pas le réseau.

## Frontières traversées (résumé)

```
issue #68 (GitHub, label decision + kanban, parent #31)
  → commentaire /ok humain (surface de décision)
  → unblock de t_5e667a92 (kanban)
  → re-spawn grill-me → reformulation → dev applique le re-GREEN (3 fixes keeper + upsert-desc/pin)
  → banc test_thread_description.py 10/10 GREEN (preuve de convergence)
  → doc → doc-review → PR → merge
```

Deux frontières : **GitHub ↔ kanban** (décision → effet) et
**git ↔ worktree partagé** (preuve de livraison). Le point de fragilité n'est
pas l'appel réseau mais **la couverture commit-à-commit** : un fix
non-commité dans l'arbre n'est pas un travail livré.

## État mesuré (2026-10-11, rejouable)

- `origin/dev` = `7091678` (tip mesuré).
- `wt/issue-19-discord-thread-title-description` (worktree `t_c22a7e74`) :
  - tip = `9fcd207` (docs cadrage issue #73) au-dessus du GREEN partial
    commité (`55e6659` baseline).
  - `git status --short` : 2 fichiers non suivis
    (`issue-27.md`, `issue-29.md`) — aucun fix non-commité dans l'arbre.
- `git cat-file -t 6661362` → **fatal : Not a valid object name**
  (définitivement absent).
- `grep DESCRIPTION_MARKER` sur `pipeline/engine.py` → **3 hits** (GREEN
  partial présent).
- `grep upsert-desc|pin` sur
  `skills/gh-kanban-bridge/scripts/discord_thread.py` → **0 hit**
  (capacité non livrée).
- Banc `tests/test_thread_description.py` : **3 failed, 7 passed**
  (rejoué 2026-10-11, rejouable via
  `python3 -m pytest tests/test_thread_description.py -q -p no:randomly`).
- `pj_docs_lint.py` sur `/home/elix/pj-repos/hermes-workflow` → `exit=0`.

## Composants impactés (résumé)

- **Décision (cette issue)** : `pipeline/pj_decision.py` ([[pj-decision]]) +
  `pipeline/pj_escalate.py` / `pipeline/pj_notify.py` ([[pj-notify]]) — la
  boucle #5, aucun changement de code.
- **Travail débloqué (slice 5 de #19, à compléter)** :
  - `pipeline/pj_room_keeper.py` — 3 fixes : (1) logique de déduplication
    pour qu'un seul message épinglé soit mis à jour (pas dupliqué),
    (2) non-lèvement quand un reader de source lève (le tick ne meurt pas),
    (3) gestion d'erreur quand `gh pr list` lève (la ligne PR est omise mais
    tracée, pas d'exception).
  - `skills/gh-kanban-bridge/scripts/discord_thread.py` — ajout des
    capacités `upsert-desc` (édition du message du fil) et `pin`
    (épingle du message).
- **Vault** : à la convergence, la slice 5 gagnera sa note composant et le
  MOC `docs/architecture/README.md` sera mis à jour par la carte `doc-k` —
  hors périmètre de cette décision.

## Non tranché (et qui doit le rester ici)

Le cadrage ne tranche **pas** :
1. **Le contenu exact des 3 fixes keeper** — porté par le dev après le
   `/ok` (le banc définit le contrat, pas le cadrage).
2. **La forme des capacités `upsert-desc`/`pin`** — portée par le dev ; le
   banc ne les teste pas directement (le helper est un adapter, injecté).
3. **La publication live des copies `~/.hermes/scripts/`** (divergence D2
   déclarée dans le handoff `dev-5`) — opération de fin de graphe contrôlée
   par identité, hors périmètre de cette décision.

Ces points sont **documentés**, pas décidés ici.
