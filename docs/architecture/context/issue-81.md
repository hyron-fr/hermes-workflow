---
type: context
status: draft
tags: [architecture, decision, escalation, recycle, convergence, slice-5, description-epinglee, cadrage]
issues: [81]
---

# Cadrage architectural — issue #81 « t3 grill-me » (5ᵉ escalade conv-5)

## Positionnement (cadre exact)

L'issue #81 (`label: decision` + `kanban`, `idempotency-key gh-issue-81`, parent
#43) est une **escalade de décision** de la carte **`t_c0e5ce5a`**
(« t3 grill-me issue #43 », assignée à `pj-master`, board
`pj-hermes-workflow`), bloquée sur le chantier **#43** (« t3 grill-me »,
lui-même escalade de la carte `t_1d781414` du chantier #30).

C'est la **cinquième escalade conv-5** de la chaîne :

| # | Issue | Carte bloquée | Motif |
|---|---|---|---|
| 1ᵉʳ | #27 | `t_f725879f` (conv-5) | GREEN dev-5 `6661362` perdu, banc 10/10 RED |
| 2ᵉ | #29 | `t_f725879f` (conv-5) | Même point, ré-importé par le pont de couverture |
| 3ᵉ | #45 | `t_854f0f77` (dev GREEN RECYCLE) | GREEN partial présent (7/10), 3 fixes keeper + upsert-desc/pin manquants |
| 4ᵉ | #41 | `t_3f7e0be4` (t3 grill-me) | Quadrante + verdict produits ; Q1 posée à l'humain |
| **5ᵉ** | **#81** | **`t_c0e5ce5a`** (t3 grill-me) | Quadrante + verdict produits ; `/ok` débloque la carte |

Le **point à statuer** (tel quel, mesuré le 2026-10-10) :

- Le commit **`6661362`** (GREEN dev-5 original) est **définitivement absent** du
  dépôt local et du remote (`git cat-file -t 6661362` → `Not a valid object name`).
- Le **GREEN partial** est présent dans le worktree partagé
  `t_c22a7e74` (tip `6a2d8e3`, 4 commits au-dessus du RED test-5 `49bb284`) :
  `DESCRIPTION_MARKER`, `build_description_lines`, `build_description_for_card`,
  `sync_description`, `sync_all_descriptions` existent dans
  `pipeline/engine.py` et `pipeline/pj_room_keeper.py`.
- Le banc `tests/test_thread_description.py` est **7/10 GREEN, 3 RED** :
  - `test_nominal_un_seul_message_epingle_mis_a_jour_pas_duplique`
  - `test_erreur_gh_pr_list_en_erreur_ligne_omise_tracee_pas_exception`
  - `test_erreur_le_reader_de_source_qui_leve_ne_tue_pas_le_tick`
- Un fix non-commité est présent dans `pipeline/pj_room_keeper.py`
  (`git status --short` → `M pipeline/pj_room_keeper.py`).
- La capacité `upsert-desc` / `pin` est **absente** du helper
  `skills/gh-kanban-bridge/scripts/discord_thread.py` (grep : 0 hit).

**Ce que la décision débloque** : le jeton `/ok` sur l'issue #81 (premier
élément) fait déboucler la carte `t_c0e5ce5a` et la repart en file.
L'effet attendant : **appliquer les 3 fixes keeper restants + ajouter
`upsert-desc`/`pin` dans le helper**, puis le banc passe 10/10.
Tout autre commentaire est une demande d'éclaircissement.

**Verdict du grill-me** (carte `t_1d781414`, commentaire sur l'issue #43) :
`PROTOTYPE: non`, `AMBIGU: aucune`, `ARTEFACT: aucun`. Le périmètre est gelé
par le banc (contrat-5, blackboard racine `t_83401cbb`). L'unique action =
s'assurer que les 10 tests passent et pousser sur
`wt/issue-19-discord-thread-title-description`.

## Croisement infrastructure / fonctionnel / code

### Infrastructure (frontières traversées)

- **GitHub** — surface de décision : commentaire `/ok` sur l'issue #81
  (l'enfant de #43). Adapter : `gh` CLI, lu par le pont. La carte
  `t_c0e5ce5a` est l'objet de la reprise.
- **Kanban Hermes** — source de vérité de l'état des cartes. L'effet est
  `comment` + `unblock` sur `t_c0e5ce5a`, invoqués en `subprocess` par le
  câblage de #5 ([[pj-decision]] : `decision_from_comment` calcule,
  l'appelant applique).
- **Git / worktree partagé** — surface de livraison : le branch head de
  `wt/issue-19-discord-thread-title-description` (worktree `t_c22a7e74`)
  est la **preuve de livraison** de la slice 5. État mesuré : tip `6a2d8e3`,
  GREEN partial présent, 3 tests rouges.
- **Aucun nouveau port** : les trois surfaces (GitHub, kanban, git)
  existent ; l'issue #81 réutilise la boucle de décision #5.

### Fonctionnel (capacité traversée)

La capacité traversée est **convergence + preuve de livraison** (pas une
fonctionnalité nouvelle). Le chantier #19 (« Discord thread title and
description update ») est déjà cadré par la note `issue-27` (escalade 1ᵉʳ),
la note `issue-29` (escalade 2ᵉ), la note `issue-41` (escalade 4ᵉ) et la note
composant `pj-thread-name` (slices 2–4 livrées). #81 porte :

- **le point de décision** : le GREEN partial est-il suffisant pour
  considérer la slice 5 comme convergée ? (Verdict grill-me : non, 3 fixes
  keeper + 2 capacités helper manquent.)
- **la chaîne de livraison** : qui applique les 3 fixes keeper restants
  et ajoute `upsert-desc`/`pin` dans le helper ? (Le dev, après le `/ok`.)
- **le verdict de convergence** : après les fixes, le banc
  `tests/test_thread_description.py` passe-t-il 10/10 GREEN ?

### Code (composants impactés)

| composant | état mesuré (2026-10-10) | impact slice 5 |
|---|---|---|
| `pipeline/engine.py` | `DESCRIPTION_MARKER` + `build_description_lines` présents | Livré dans le GREEN partial |
| `pipeline/pj_room_keeper.py` | `build_description_for_card`, `sync_description`, `sync_all_descriptions` présents ; fix non-commité dans l'arbre | 3 tests RED : 1 fix de logique de dédup + 1 fix de non-lèvement + 1 fix de gestion d'erreur `gh pr list` |
| `tests/test_thread_description.py` | 387 lignes, 10 cas, 7 GREEN / 3 RED | Banc qui gèle le contrat `contrat-5` |
| `skills/gh-kanban-bridge/scripts/discord_thread.py` | Commandes `create`/`send`/`rename`/`threads` seulement | **`upsert-desc` + `pin` à ajouter** |

Le **core pur** à préserver : `build_description_lines` (composition pure :
issue_url, branch, pr_url → list[str], 0 réseau) et
`build_description_for_card` (sources injectées). L'écriture du message et
de l'épingle passent par l'adapter injecté `write_message` / le helper Discord.

## Lecture SDD (spec-driven)

La spec est le body de l'issue **#19** (arbitrages `Q1=1a`, `Q2=2b`, `Q3=d`) ;
l'issue #81 **est** le point à statuer de sa carte `t_c0e5ce5a`. Le verdict du
grill-me (carte `t_1d781414`) fixe le périmètre : l'unique action = s'assurer
que les 10 tests passent et pousser sur
`wt/issue-19-discord-thread-title-description`. La doc décrit le livré :
ici le « livré » attendu est le GREEN 10/10 (3 fixes keeper + upsert-desc/pin) ;
jusqu'au `/ok`, l'état mesuré est 7/10 GREEN + fix non-commité + helper
incomplet.

## Lecture DDD (bounded contexts, agrégats, événements)

- **Bounded context traversé** : *convergence / livraison* — chevauche
  *développement* (slice 5 de #19) et *décision humaine* (l'escalade #27→#29→#45→#41→#81),
  sans en être un nouveau : c'est la **jonction** entre les deux.
- **Agrégat racine** : la **carte `t_c0e5ce5a`** (invariant : elle ne repart en
  `ready` que sur un `/ok` portant sa ligne canonique
  `carte: pj-hermes-workflow/t_c0e5ce5a`). L'**issue #81** est l'objet de
  décision qui la matérialise.
- **Value objects** : le **branch head SHA** (`6a2d8e3` mesuré) ; le **banc
  7/10** (état de convergence partiel) ; l'**idempotency-key** `gh-issue-81` ;
  le verdict grill-me (`PROTOTYPE: non, AMBIGU: aucune`).
- **Domain events** : `/ok` humain sur l'issue #81 → unblock de
  `t_c0e5ce5a` → re-spawn (grill-me reformule) → dev applique les 3 fixes
  keeper + ajoute `upsert-desc`/`pin` → banc 10/10 GREEN → convergence →
  doc → doc-review → PR → merge.

## Lecture TDD (contrats testables)

Le contrat testable est le **banc `tests/test_thread_description.py`**
(387 lignes, 10 cas), rejouable sans Discord ni réseau (sources injectées) :

- `build_description_lines(issue_url, branch, pr_url, log=print) -> list[str]`
  — composition pure, 4 lignes, omission des `None`/vides (4 cas GREEN).
- `keeper.build_description_for_card(card, *, …, specs_reader, pr_reader,
  issue_url_lookup)` — assemblage des sources injectées (2 cas GREEN,
  1 cas RED : le reader qui lève ne doit pas tuer le tick — fix non-commité).
- `keeper.sync_description(cards, *, fetch_messages, write_message, log=None)`
  — écrivain best-effort : dédup par marqueur, `edit` jamais second post
  (1 cas RED : un seul message épinglé mis à jour pas dupliqué — fix de
  logique de dédup à appliquer).
- **1 cas RED supplémentaire** : `test_erreur_gh_pr_list_en_erreur_ligne_omise_tracee_pas_exception`
  — gestion d'erreur quand `gh pr list` lève (la ligne PR est omise mais tracée,
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
issue #81 (GitHub, label decision + kanban, parent #43)
  → commentaire /ok humain (surface de décision)
  → unblock de t_c0e5ce5a (kanban)
  → re-spawn grill-me → reformulation → dev applique 3 fixes keeper + upsert-desc/pin
  → banc test_thread_description.py 10/10 GREEN (preuve de convergence)
  → doc → doc-review → PR → merge
```

Deux frontières : **GitHub ↔ kanban** (décision → effet) et
**git ↔ worktree partagé** (preuve de livraison). Le point de fragilité n'est
pas l'appel réseau mais **la couverture commit-à-commit** : un fix non-commité
dans l'arbre n'est pas un travail livré.

## État mesuré (2026-10-10, rejouable)

- `origin/dev` = `8e35b6e` (fix decision jeton après amorce).
- `wt/issue-19-discord-thread-title-description` :
  - **local** (worktree `t_c22a7e74`) = `6a2d8e3` (4 commits au-dessus de
    `49bb284` RED test-5 : `dccf75f` fix keeper bouclage, `55e6659` baseline,
    `03e09f1` cadrage #31, `6a2d8e3` cadrage #26).
  - **remote** = `6a2d8e3` (en sync).
  - `git status --short` : `M pipeline/pj_room_keeper.py` (fix non-commité).
- `git cat-file -t 6661362` → **fatal : Not a valid object name** (définitivement absent).
- `grep DESCRIPTION_MARKER|build_description|sync_description` sur
  `pipeline/` → **présents** (GREEN partial livré dans l'arbre).
- `grep upsert-desc|pin` sur `skills/gh-kanban-bridge/scripts/discord_thread.py` →
  **0 hit** (capacité non livrée).
- Banc `tests/test_thread_description.py` : **7/10 GREEN, 3 RED** (mesuré
  2026-10-10, rejouable via `uv run --with pytest … -m pytest
  tests/test_thread_description.py -v -p no:randomly`).
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
2. **La forme des capacités `upsert-desc`/`pin`** — porté par le dev ; le
   banc ne les teste pas directement (le helper est un adapter, injecté).
3. **La publication live des copies `~/.hermes/scripts/`** (divergence D2
   déclarée dans le handoff `dev-5`) — opération de fin de graphe contrôlée
   par identité, hors périmètre de cette décision.

Ces points sont **documentés**, pas décidés ici.
