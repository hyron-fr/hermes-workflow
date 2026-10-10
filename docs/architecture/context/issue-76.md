---
type: context
status: draft
tags: [architecture, decision, escalation, recycle, convergence, slice-5, delivery-proof, cadrage]
issues: [76]
---

# Cadrage architectural — issue #76 « t3 grill-me » (escalade conv-5, re-import du point à statuer)

## Positionnement (cadre exact)

L'issue **#76** (`label: decision` + `kanban`, `idempotency-key gh-issue-76`,
titre GitHub « t3 grill-me », importée dans le board le 2026-10-08) est un
**re-import du point à statuer de la carte `t_64c54708`** (« t3 grill-me
issue #30 », assignée `pj-master`, board `pj-hermes-workflow`), bloquée
depuis le 2026-10-04 sur le chantier **#30** lui-même escalade du chantier
**#19** (« Discord thread title and description update »).

Le **point à statuer** (tel quel, repris du body de l'issue, état mesuré le
2026-10-10 dans le worktree partagé `.worktrees/t_c22a7e74`) :

- Le commit **`6661362`** (GREEN dev-5 original) est **définitivement absent**
  du dépôt local et du remote.
- Le **GREEN partial** est présent (branch head `b846a28`, 8 commits au-dessus
  du RED test-5 `49bb284`) : `DESCRIPTION_MARKER`, `build_description_lines`,
  `build_description_for_card`, `sync_description`, `sync_all_descriptions`
  existent dans `pipeline/engine.py` et `pipeline/pj_room_keeper.py`.
- Le banc `tests/test_thread_description.py` est **7/10 GREEN, 3 RED**
  (rejouable : `uv run --with pytest … -m pytest tests/test_thread_description.py -v -p no:randomly`) :
  - `test_nominal_un_seul_message_epingle_mis_a_jour_pas_duplique`
  - `test_erreur_gh_pr_list_en_erreur_ligne_omise_tracee_pas_exception`
  - `test_erreur_le_reader_de_source_qui_leve_ne_tue_pas_le_tick`
- La capacité `upsert-desc` / `pin` est **absente** du helper
  `skills/gh-kanban-bridge/scripts/discord_thread.py`.

**Décision demandée** (Q1 grill-me #30, posée au thread Discord #19) :
`A` = re-pousser le GREEN dev-5 perdu (récupérer le code de dev-5, re-committer
sur `wt/issue-19-discord-thread-title-description`) / `B` = re-implémenter la
slice 5 fresh (nouvelle carte dev, banc 10/10 verts). Le jeton `/ok` en
**premier élément** du commentaire sur l'issue #76 débloque la carte
`c:64c54708` et la repart en file ; tout autre commentaire est une demande
d'éclaircissement.

**Verdict grill-me** (carte `t_64c54708`, commentaire 2026-10-04) :
`PROTOTYPE: non`, `AMBIGU: A1`, `ARTEFACT: aucun`.

## Croisement infrastructure / fonctionnel / code

### Infrastructure (frontières traversées)

- **GitHub** — surface de décision : commentaire `/ok` sur l'issue #76
  (l'enfant de #30, qui est l'enfant de #19). Adapter : `gh` CLI, lu par le
  pont. La carte `t_64c54708` est l'objet de la reprise.
- **Kanban Hermes** — source de vérité de l'état des cartes. L'effet est
  `comment` + `unblock` sur `t_64c54708`, invoqués par le câblage de #5
  ([[pj-decision]] : `decision_from_comment` calcule, l'appelant applique).
- **Git / worktree partagé** — surface de livraison : le branch head de
  `wt/issue-19-discord-thread-title-description` (worktree `t_c22a7e74`)
  est la **preuve de livraison** de la slice 5. État mesuré : tip `b846a28`,
  GREEN partial présent, 3 tests rouges.
- **Aucun nouveau port** : les trois surfaces (GitHub, kanban, git) existent ;
  l'issue #76 réutilise la boucle de décision #5.

### Fonctionnel (capacité traversée)

La capacité traversée est **convergence + preuve de livraison** (pas une
fonctionnalité nouvelle). Le chantier #19 est déjà cadré par la note
`issue-27` (escalade 1ᵉʳ), la note `issue-29` (escalade 2ᵉ), la note
`issue-81` (5ᵉ escalade) et la note composant `pj-thread-name` (slices 2–4
livrées). #76 porte :

- **le point de décision** : le GREEN partial est-il suffisant pour
  considérer la slice 5 comme convergée ? (Verdict grill-me : non, 3 fixes
  keeper + 2 capacités helper manquent.)
- **la chaîne de livraison** : qui applique les 3 fixes keeper restants et
  ajoute `upsert-desc`/`pin` dans le helper ? (Le dev, après le `/ok`.)
- **le verdict de convergence** : après les fixes, le banc
  `tests/test_thread_description.py` passe-t-il 10/10 GREEN ?

### Code (composants impactés)

| composant | état mesuré (2026-10-10) | impact slice 5 |
|---|---|---|
| `pipeline/engine.py` | `DESCRIPTION_MARKER` + `build_description_lines` présents | Livré dans le GREEN partial |
| `pipeline/pj_room_keeper.py` | `build_description_for_card`, `sync_description`, `sync_all_descriptions` présents | 3 tests RED : 1 fix de logique de dédup + 1 fix de non-lèvement + 1 fix de gestion d'erreur `gh pr list` |
| `tests/test_thread_description.py` | 387 lignes, 10 cas, 7 GREEN / 3 RED | Banc qui gèle le contrat `contrat-5` |
| `skills/gh-kanban-bridge/scripts/discord_thread.py` | Commandes `create`/`send`/`rename`/`threads` seulement | **`upsert-desc` + `pin` à ajouter** |

Le **core pur** à préserver : `build_description_lines` (composition pure :
issue_url, branch, pr_url → list[str], 0 réseau) et
`build_description_for_card` (sources injectées). L'écriture du message et
de l'épingle passe par l'adapter injecté `write_message` / le helper Discord.

## Lecture SDD (spec-driven)

La spec est le body de l'issue **#19** (arbitrages `Q1=1a`, `Q2=2b`, `Q3=d`) ;
l'issue #76 **est** le point à statuer de sa carte `t_64c54708`. Le verdict du
grill-me fixe le périmètre : l'unique action = s'assurer que les 10 tests
passent et pousser sur `wt/issue-19-discord-thread-title-description`. La doc
décrit le livré : ici le « livré » attendu est le GREEN 10/10 (3 fixes keeper +
upsert-desc/pin) ; jusqu'au `/ok`, l'état mesuré est 7/10 GREEN + helper
incomplet.

## Lecture DDD (bounded contexts, agrégats, événements)

- **Bounded context traversé** : *convergence / livraison* — chevauche
  *développement* (slice 5 de #19) et *décision humaine* (l'escalade
  #27→#29→#45→#41→#81→#76), sans en être un nouveau : c'est la **jonction**
  entre les deux.
- **Agrégat racine** : la **carte `t_64c54708`** (invariant : elle ne repart
  en `ready` que sur un `/ok` portant sa ligne canonique
  `carte: pj-hermes-workflow/t_64c54708`). L'**issue #76** est l'objet de
  décision qui la matérialise.
- **Value objects** : le **branch head SHA** (`b846a28` mesuré) ; le **banc
  7/10** (état de convergence partiel) ; l'**idempotency-key** `gh-issue-76` ;
  le verdict grill-me (`PROTOTYPE: non, AMBIGU: A1`).
- **Domain events** : `/ok` humain sur l'issue #76 → unblock de
  `t_64c54708` → re-spawn (grill-me reformule) → dev applique les 3 fixes
  keeper + ajoute `upsert-desc`/`pin` → banc 10/10 GREEN → convergence →
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
issue #76 (GitHub, label decision + kanban)
  → commentaire /ok humain (surface de décision)
  → unblock de t_64c54708 (kanban)
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
  - **local** (worktree `t_c22a7e74`) = `b846a28` (8 commits au-dessus de
    `49bb284` RED test-5).
  - `git status --short` : propre (le fix de `dccf75f` est commité).
- `git cat-file -t 6661362` → **fatal : Not a valid object name** (définitivement absent).
- `grep DESCRIPTION_MARKER|build_description|sync_description` sur
  `pipeline/` → **présents** (GREEN partial livré dans l'arbre).
- `grep upsert-desc|pin` sur `skills/gh-kanban-bridge/scripts/discord_thread.py` →
  **0 hit** (capacité non livrée).
- Banc `tests/test_thread_description.py` : **7/10 GREEN, 3 RED** rejoué le
  2026-10-10 dans `t_c22a7e74` :
  `uv run --with pytest --with pytest-randomly --with pyyaml --with langgraph -m pytest tests/test_thread_description.py -v -p no:randomly`
  → `3 failed, 7 passed in 0.68s` ; les 3 cas rouges sont exactement ceux nommés
  ci-dessus. (Environnement : `pyyaml` + `langgraph` requis par
  `pipeline/engine.py`, non préinstallés dans l'env uv ad hoc.)
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
