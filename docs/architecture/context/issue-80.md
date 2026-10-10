---
type: context
status: draft
tags: [architecture, decision, escalation, recycle, convergence, slice-5, description-epinglee, cadrage]
issues: [80]
---

# Cadrage architectural — issue #80 « t3 grill-me » (6ᵉ escalade conv-5)

## Positionnement (cadre exact)

L'issue #80 (`label: decision` + `kanban`, `idempotency-key gh-issue-80`,
parent **#42**) est une **escalade de décision** de la carte
**`t_cd75a2e4`** (« t3 grill-me issue #42 », assignée à `pj-master`, board
`pj-hermes-workflow`), bloquée depuis 2026-10-08 (57 h au 2026-10-10 23:30).

C'est la **sixième escalade conv-5** de la chaîne :

| # | Issue | Carte bloquée | Motif |
|---|---|---|---|
| 1ᵉʳ | #26 | `t_f725879f` (conv-5) | GREEN dev-5 `6661362` perdu, banc 10/10 RED |
| 2ᵉ | #27 | `t_f725879f` (conv-5) | Même point, ré-importé par le pont de couverture |
| 3ᵉ | #29 | `t_f725879f` (conv-5) | Miroir de décision de #27 |
| 4ᵉ | #41 | `t_3f7e0be4` (t3 grill-me) | Quadrante + verdict produits ; GREEN partial 8/10 |
| 5ᵉ | #43 | `t_c0e5ce5a` (t3 grill-me, parent #42) | GREEN partial 7/10, 3 fixes keeper restants |
| **6ᵉ** | **#80** | **`t_cd75a2e4`** (t3 grill-me, parent #42) | **Re-import de #42 : même point, même verdict, /ok toujours absent** |

Le **point à statuer** (tel quel, mesuré le 2026-10-10) :

- Le commit **`6661362`** (GREEN dev-5 original) est **définitivement absent**
  du dépôt local et du remote (`git cat-file -t 6661362` → `fatal: Not a valid
  object name`).
- Le **GREEN partial** est présent dans le worktree partagé
  `t_c22a7e74` (branche `wt/issue-19-discord-thread-title-description`,
  tip `6a2d8e3`, 9 commits au-dessus de `49bb284` RED test-5) :
  `DESCRIPTION_MARKER`, `build_description_lines` (engine.py L221/L224),
  `build_description_for_card` (L572), `sync_description` (L715),
  `sync_all_descriptions` (L829), `_discord_pin` (L801) présents dans
  `pipeline/pj_room_keeper.py`.
- Le banc `tests/test_thread_description.py` est **7/10 GREEN, 3 RED**
  (mesuré 2026-10-10, rejouable via `uv run --with pytest … -m pytest
  tests/test_thread_description.py -v -p no:randomly`) :
  - `test_nominal_un_seul_message_epingle_mis_a_jour_pas_duplique`
  - `test_erreur_gh_pr_list_en_erreur_ligne_omise_tracee_pas_exception`
  - `test_erreur_le_reader_de_source_qui_leve_ne_tue_pas_le_tick`
- Un fix non-commité est présent dans `pipeline/pj_room_keeper.py`
  (`git status --short` → `M pipeline/pj_room_keeper.py`, 43 insertions /
  13 suppressions) + fichier de diagnostic non versionné (`?? diag2.py`).
- La capacité `upsert-desc` / `pin` est **absente** du helper
  `skills/gh-kanban-bridge/scripts/discord_thread.py`
  (grep : 0 hit ; le helper ne porte que `bot_token`, `api`,
  `go_nogo_components`, `main`).
- Le jeton `/ok` est **absent** sur les issues #42, #43, #80 au 2026-10-10
  23:30 — la carte `t_cd75a2e4` reste bloquée.

**Ce que la décision débloque** : le jeton `/ok` sur l'issue #80 (premier
élément) fait déboucler la carte `t_cd75a2e4` et la repart en file.
L'effet attendant : **appliquer les 3 fixes keeper restants + ajouter
`upsert-desc`/`pin` dans le helper**, puis le banc passe 10/10.
Tout autre commentaire est une demande d'éclaircissement.

**Verdict du grill-me** (mesuré sur la carte `t_cd75a2e4`, commentaire
2026-10-08) : `PROTOTYPE: non`, `AMBIGU: aucune`, `ARTEFACT: aucun`.
Le périmètre est gelé par le banc (contrat-5, blackboard racine
`t_83401cbb`). L'unique action = s'assurer que les 10 tests passent et
pousser sur `wt/issue-19-discord-thread-title-description`.

## Croisement infrastructure / fonctionnel / code

### Infrastructure (frontières traversées)

- **GitHub** — surface de décision : commentaire `/ok` sur l'issue #80
  (l'enfant de #42). Adapter : `gh` CLI, lu par le pont. La carte
  `t_cd75a2e4` est l'objet de la reprise.
- **Kanban Hermes** — source de vérité de l'état des cartes. L'effet est
  `comment` + `unblock` sur `t_cd75a2e4`, invoqués en `subprocess` par le
  câblage de #5 ([[pj-decision]] : `decision_from_comment` calcule,
  l'appelant applique).
- **Git / worktree partagé** — surface de livraison : le branch head de
  `wt/issue-19-discord-thread-title-description` (worktree `t_c22a7e74`)
  est la **preuve de livraison** de la slice 5. État mesuré : tip
  `6a2d8e3`, GREEN partial présent, 3 tests rouges.
- **Aucun nouveau port** : les trois surfaces (GitHub, kanban, git)
  existent ; l'issue #80 réutilise la boucle de décision #5.

### Fonctionnel (capacité traversée)

La capacité traversée est **convergence + preuve de livraison** (pas une
fonctionnalité nouvelle). Le chantier #19 (« Discord thread title and
description update ») est déjà cadré par la note [[issue-26]] (escalade
1ᵉʳ), [[issue-27]] (escalade 2ᵉ), [[issue-29]] (escalade 3ᵉ),
[[issue-41]] (escalade 4ᵉ) et la note composant [[pj-thread-name]]
(slices 2–4 livrées). #80 porte :

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
| `pipeline/engine.py` | `DESCRIPTION_MARKER` (L221) + `build_description_lines` (L224) présents | Livré dans le GREEN partial |
| `pipeline/pj_room_keeper.py` | `build_description_for_card` (L572), `sync_description` (L715), `sync_all_descriptions` (L829), `_discord_pin` (L801) présents ; fix non-commité dans l'arbre (43 ins / 13 sup) | 3 tests RED : 1 fix de dédup + 1 fix de journalisation + 1 fix de non-lèvement |
| `tests/test_thread_description.py` | 387 lignes, 10 cas, 7 GREEN / 3 RED | Banc qui gèle le contrat `contrat-5` |
| `skills/gh-kanban-bridge/scripts/discord_thread.py` | Commandes `bot_token`/`api`/`go_nogo_components`/`main` seulement | **`upsert-desc` + `pin` à ajouter** |

Le **core pur** à préserver : `build_description_lines` (composition pure :
issue_url, branch, pr_url → list[str], 0 réseau) et
`build_description_for_card` (sources injectées). L'écriture du message et
de l'épingle passent par l'adapter injecté `write_message` / le helper
Discord.

## Lecture SDD (spec-driven)

La spec est le body de l'issue **#19** (arbitrages `Q1=1a`, `Q2=2b`, `Q3=d`) ;
l'issue #80 **est** le point à statuer de sa carte `t_cd75a2e4`. Le verdict du
grill-me (carte `t_cd75a2e4`, commentaire 2026-10-08) fixe le périmètre :
l'unique action = s'assurer que les 10 tests passent et pousser sur
`wt/issue-19-discord-thread-title-description`. La doc décrit le livré :
ici le « livré » attendu est le GREEN 10/10 (3 fixes keeper + upsert-desc/pin) ;
jusqu'au `/ok`, l'état mesuré est 7/10 GREEN + fix non-commité + helper
incomplet.

## Lecture DDD (bounded contexts, agrégats, événements)

- **Bounded context traversé** : *convergence / livraison* — chevauche
  *développement* (slice 5 de #19) et *décision humaine* (l'escalade
  #26→#27→#29→#41→#43→#80), sans en être un nouveau : c'est la **jonction**
  entre les deux.
- **Agrégat racine** : la **carte `t_cd75a2e4`** (invariant : elle ne repart
  en `ready` que sur un `/ok` portant sa ligne canonique
  `carte: pj-hermes-workflow/t_cd75a2e4`). L'**issue #80** est l'objet de
  décision qui la matérialise.
- **Value objects** : le **branch head SHA** (`6a2d8e3` mesuré) ; le **banc
  7/10** (état de convergence partiel) ; l'**idempotency-key** `gh-issue-80` ;
  le verdict grill-me (`PROTOTYPE: non, AMBIGU: aucune`).
- **Domain events** : `/ok` humain sur l'issue #80 → unblock de
  `t_cd75a2e4` → re-spawn (grill-me reformule) → dev applique les 3 fixes
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
  logique de dédup à appliquer ; 1 cas RED : l'échec de `pr_reader` n'est pas
  journalisé dans le log — fix de traçabilité à appliquer).
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
issue #80 (GitHub, label decision + kanban, parent #42)
  → commentaire /ok humain (surface de décision)
  → unblock de t_cd75a2e4 (kanban)
  → re-spawn grill-me → reformulation → dev applique 3 fixes keeper + upsert-desc/pin
  → banc test_thread_description.py 10/10 GREEN (preuve de convergence)
  → doc → doc-review → PR → merge
```

Deux frontières : **GitHub ↔ kanban** (décision → effet) et
**git ↔ worktree partagé** (preuve de livraison). Le point de fragilité n'est
pas l'appel réseau mais **la couverture commit-à-commit** : un fix non-commité
dans l'arbre n'est pas un travail livré.

## État mesuré (2026-10-10, rejouable)

Mesures faites dans le worktree partagé
`/home/elix/pj-repos/hermes-workflow/.worktrees/t_c22a7e74` (branche
`wt/issue-19-discord-thread-title-description`), le 2026-10-10 23:30 :

- `origin/dev` = `2027333` (docs cadrage issue #29).
- `wt/issue-19-discord-thread-title-description` :
  - **local** (worktree `t_c22a7e74`) = `6a2d8e3` (9 commits au-dessus de
    `49bb284` RED test-5 : `dccf75f` fix keeper bouclage, `55e6659` baseline,
    `03e09f1` cadrage #31, `6a827a0` cadrage #45, `56e2525` cadrage #41
    correction, `dbf73da` cadrage #41 correction 2, `6a2d8e3` cadrage #26).
  - `git status --short` : `M pipeline/pj_room_keeper.py` (43 ins / 13 sup,
    fix non-commité) + `?? diag2.py` (fichier de diagnostic non versionné).
- `git cat-file -t 6661362` → **fatal : Not a valid object name**
  (définitivement absent).
- `grep DESCRIPTION_MARKER|build_description|sync_description` sur
  `pipeline/` → **présents** (GREEN partial livré dans l'arbre).
- `grep upsert-desc|pin` sur `skills/gh-kanban-bridge/scripts/discord_thread.py`
  → **0 hit** (capacité non livrée).
- Banc `tests/test_thread_description.py` : **7/10 GREEN, 3 RED** (mesuré
  2026-10-10, rejouable via `uv run --with pytest --with pyyaml --with
  langgraph --with openai python -m pytest
  tests/test_thread_description.py -v -p no:randomly`).
- Jeton `/ok` **absent** sur les issues #42, #43, #80 au 2026-10-10 23:30.

## Composants impactés (résumé)

- **Décision (cette issue)** : `pipeline/pj_decision.py` ([[pj-decision]]) +
  `pipeline/pj_escalate.py` / `pipeline/pj_notify.py` ([[pj-notify]]) — la
  boucle #5, aucun changement de code.
- **Travail débloqué (slice 5 de #19, à compléter)** :
  - `pipeline/pj_room_keeper.py` — 3 fixes : (1) logique de déduplication
    pour qu'un seul message épinglé soit mis à jour (pas dupliqué),
    (2) journalisation de l'échec de `pr_reader` dans le log,
    (3) non-lèvement quand un reader de source lève (le tick ne meurt pas).
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
