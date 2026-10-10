---
type: context
status: draft
tags: [architecture, decision, escalation, recycle, convergence, slice-5, description-epinglee, cadrage]
issues: [70]
---

# Cadrage architectural — issue #70 « t3b doc-cadrage » (escalade conv-5, carte `t_7979348c`)

## Positionnement (cadre exact)

L'issue #70 (`labels: decision + kanban`, `idempotency-key gh-issue-70`, parent
**#30** « slice 5/5 — convergence », qui est lui-même un enfant de #19 « Discord
thread title and description update ») est une **escalade de décision** de la carte
**`t_7979348c`** (board `pj-hermes-workflow`), bloquée sur le chantier #30.

C'est l' **escalade conv-5** de la chaîne — l'enchaînement exact mesuré sur
l'historique GitHub :

| # | Issue | Carte bloquée | Motif | Date |
|---|---|---|---|---|
| 1ᵉʳ | #30 | `t_f725879f` (conv-5) | GREEN dev-5 `6661362` absent du worktree partagé, banc 10/10 RED | 2026-10 |
| 2ᵉ | #70 | `t_7979348c` | **non détaillé** (motif déclaré vide) ; carte importée le 2026-10-08, issue créée le 2026-10-08 11:20 UTC, import kanban le 2026-10-08 19:21 UTC | 2026-10-08 |
| 3ᵉ | #80 | (carte 6ᵉ) | point à statuer mesuré au 2026-10-10 | 2026-10-10 |
| 4ᵉ | #75 | (carte 7ᵉ) | banc 7/10 rejoué, GREEN partial commité, verdict AMBIGU | 2026-10-11 |
| 5ᵉ | #74 | `t_3f7e0be4` (sur #27) | 8ᵉ escalation conv-5 | 2026-10-11 |
| 6ᵉ | #73 | (carte 5ᵉ) | point à statuer mesuré au 2026-10-11 | 2026-10-11 |

**Particularité de #70 (distincte de #41/#81)** : le corps de l'issue porte le
motif « (non détaillé) ». Les précédentes escalades (notamment #41, #81)
détallaient le point à statuer (banc, fixes manquants, verdict grill-me).
Ici, le constat est reporté **entièrement à la carte** `t_7979348c` — le cadrage
ne peut donc que **décrire l'état mesuré** de la slice 5 (le point de
convergence) et ne peut pas reformuler le motif de blocage déclaré. C'est une
lecture **conservative** : le cadrage positionne, ne tranche pas le motif.

**Ce que la décision débloque** : le jeton `/ok` sur l'issue #70 (premier
élément) fait déboucler la carte `t_7979348c` et la repart en file. Tout autre
commentaire est une demande d'éclaircissement.

**Verdict grill-me** (carte `t_1d781414`, commentaire sur l'issue #43, toujours
valable) : `PROTOTYPE: non`, `AMBIGU: aucune`, `ARTEFACT: aucun`. Le périmètre
est gelé par le banc (contrat-5, blackboard racine `t_83401cbb`). L'unique action
= s'assurer que les 10 tests passent et pousser sur
`wt/issue-19-discord-thread-title-description`.

## Croisement infrastructure / fonctionnel / code

### Infrastructure (frontières traversées)

- **GitHub** — surface de décision : commentaire `/ok` sur l'issue #70
  (l'enfant de #30). Adapter : `gh` CLI, lu par le pont. La carte
  `t_7979348c` est l'objet de la reprise.
- **Kanban Hermes** — source de vérité de l'état des cartes. L'effet est
  `comment` + `unblock` sur `t_7979348c`, invoqués en `subprocess` par le
  câblage de #5 ([[pj-decision]] : `decision_from_comment` calcule,
  l'appelant applique).
- **Git / worktree partagé** — surface de livraison : le branch head de
  `wt/issue-19-discord-thread-title-description` (worktree `t_c22a7e74`)
  est la **preuve de livraison** de la slice 5. État mesuré (ci-dessous) :
  tip `9fcd207`, GREEN partial présent, 3 tests rouges.
- **Aucun nouveau port** : les trois surfaces (GitHub, kanban, git)
  existent ; l'issue #70 réutilise la boucle de décision #5.

### Fonctionnel (capacité traversée)

La capacité traversée est **convergence + preuve de livraison** (pas une
fonctionnalité nouvelle). Le chantier #19 (« Discord thread title and
description update ») est déjà cadré par les notes `issue-27`, `issue-29`,
`issue-41`, `issue-81` (escalades de la même chaîne conv-5) et la note
composant `pj-thread-name` (slices 2–4 livrées). #70 porte :

- **le point de décision** : la slice 5 est-elle convergée ? État mesuré :
  NON — 3 fixes keeper + 2 capacités helper manquent.
- **la chaîne de livraison** : qui applique les 3 fixes keeper restants et
  ajoute `upsert-desc`/`pin` dans le helper ? (Le dev, après le `/ok`.)
- **le verdict de convergence** : après les fixes, le banc
  `tests/test_thread_description.py` passe-t-il 10/10 GREEN ?

### Code (composants impactés)

| composant | état mesuré (2026-10-11) | impact slice 5 |
|---|---|---|
| `pipeline/engine.py` | `DESCRIPTION_MARKER` + `build_description_lines` présents | Livré dans le GREEN partial |
| `pipeline/pj_room_keeper.py` | `build_description_for_card`, `sync_description`, `sync_all_descriptions` présents | 3 tests RED : 1 fix de logique de dédup + 1 fix de non-lèvement + 1 fix de gestion d'erreur `gh pr list` |
| `tests/test_thread_description.py` | 10 cas, 7 GREEN / 3 RED | Banc qui gèle le contrat `contrat-5` |
| `skills/gh-kanban-bridge/scripts/discord_thread.py` | Commandes `create`/`send`/`rename`/`threads` seulement | **`upsert-desc` + `pin` à ajouter** |

Le **core pur** à préserver : `build_description_lines` (composition pure :
issue_url, branch, pr_url → list[str], 0 réseau) et
`build_description_for_card` (sources injectées). L'écriture du message et
de l'épingle passent par l'adapter injecté `write_message` / le helper Discord.

## Lecture SDD (spec-driven)

La spec est le body de l'issue **#19** (arbitrages `Q1=1a`, `Q2=2b`, `Q3=d`) ;
l'issue #70 **est** le point à statuer de sa carte `t_7979348c`. Le verdict du
grill-me (carte `t_1d781414`) fixe le périmètre : l'unique action = s'assurer
que les 10 tests passent et pousser sur
`wt/issue-19-discord-thread-title-description`. La doc décrit le livré :
ici le « livré » attendu est le GREEN 10/10 (3 fixes keeper + upsert-desc/pin) ;
jusqu'au `/ok`, l'état mesuré est 7/10 GREEN + helper incomplet.

## Lecture DDD (bounded contexts, agrégats, événements)

- **Bounded context traversé** : *convergence / livraison* — chevauche
  *développement* (slice 5 de #19) et *décision humaine* (l'escalade
  #30→#70→#80→#75→#74→#73), sans en être un nouveau : c'est la **jonction**
  entre les deux.
- **Agrégat racine** : la **carte `t_7979348c`** (invariant : elle ne repart en
  `ready` que sur un `/ok` portant sa ligne canonique
  `carte: pj-hermes-workflow/t_7979348c`). L'**issue #70** est l'objet de
  décision qui la matérialise.
- **Value objects** : le **branch head SHA** (`9fcd207` mesuré) ; le **banc
  7/10** (état de convergence partiel) ; l'**idempotency-key** `gh-issue-70` ;
  le verdict grill-me (`PROTOTYPE: non, AMBIGU: aucune`).
- **Domain events** : `/ok` humain sur l'issue #70 → unblock de
  `t_7979348c` → re-spawn (grill-me reformule) → dev applique les 3 fixes
  keeper + ajoute `upsert-desc`/`pin` → banc 10/10 GREEN → convergence →
  doc → doc-review → PR → merge.

## Lecture TDD (contrats testables)

Le contrat testable est le **banc `tests/test_thread_description.py`**
(10 cas), rejouable sans Discord ni réseau (sources injectées) :

- `build_description_lines(issue_url, branch, pr_url, log=print) -> list[str]`
  — composition pure, 4 lignes, omission des `None`/vides (4 cas GREEN).
- `keeper.build_description_for_card(card, *, …, specs_reader, pr_reader,
  issue_url_lookup)` — assemblage des sources injectées (2 cas GREEN,
  1 cas RED : le reader qui lève ne doit pas tuer le tick).
- `keeper.sync_description(cards, *, fetch_messages, write_message, log=None)`
  — écrivain best-effort : dédup par marqueur, `edit` jamais second post
  (1 cas RED : un seul message épinglé mis à jour pas dupliqué).
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
issue #70 (GitHub, labels decision + kanban, parent #30)
  → commentaire /ok humain (surface de décision)
  → unblock de t_7979348c (kanban)
  → re-spawn grill-me → reformulation → dev applique 3 fixes keeper + upsert-desc/pin
  → banc test_thread_description.py 10/10 GREEN (preuve de convergence)
  → doc → doc-review → PR → merge
```

Deux frontières : **GitHub ↔ kanban** (décision → effet) et
**git ↔ worktree partagé** (preuve de livraison). Le point de fragilité n'est
pas l'appel réseau mais **la couverture commit-à-commit** : un fix non-commité
dans l'arbre n'est pas un travail livré.

## État mesuré (2026-10-11, rejouable)

- `origin/dev` = `2027333` (docs cadrage #29).
- `wt/issue-19-discord-thread-title-description` :
  - **local** (worktree `t_c22a7e74`) = `9fcd207` (docs cadrage #73 ; le tip a
    avancé depuis les notes #41/#81, qui mesuraient `6a2d8e3` / `6a827a0`).
  - **remote** = `9fcd207` (en sync).
  - `git status --short` : `?? docs/architecture/context/issue-27.md`,
    `?? docs/architecture/context/issue-29.md` (notes non commitées, hors
    périmètre de la slice 5).
- `git cat-file -t 6661362` → **fatal : Not a valid object name**
  (définitivement absent).
- `grep DESCRIPTION_MARKER|build_description|sync_description` sur
  `pipeline/` → **présents** dans `pipeline/engine.py` et
  `pipeline/pj_room_keeper.py` (GREEN partial livré dans l'arbre).
- `grep upsert-desc|pin` sur `skills/gh-kanban-bridge/scripts/discord_thread.py`
  → **0 hit** (capacité non livrée).
- Banc `tests/test_thread_description.py` : **7/10 GREEN, 3 RED** (mesuré
  2026-10-11, rejouable via
  `uv run --with pytest --with pytest-randomly --with pyyaml --with langgraph -m pytest tests/test_thread_description.py -v -p no:randomly`).
  Les 3 cas rouges :
  - `test_nominal_un_seul_message_epingle_mis_a_jour_pas_duplique`
  - `test_erreur_gh_pr_list_en_erreur_ligne_omise_tracee_pas_exception`
  - `test_erreur_le_reader_de_source_qui_leve_ne_tue_pas_le_tick`
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
3. **Le motif de blocage de la carte `t_7979348c`** — déclaré « (non
   détaillé) » sur l'issue #70 ; le détail est sur la carte elle-même. Le
   cadrage décrit l'état mesuré de la slice 5, ne reformule pas le motif.
4. **La publication live des copies `~/.hermes/scripts/`** (divergence D2
   déclarée dans le handoff `dev-5`) — opération de fin de graphe contrôlée
   par identité, hors périmètre de cette décision.

Ces points sont **documentés**, pas décidés ici.
