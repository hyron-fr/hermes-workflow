---
type: context
status: draft
tags: [architecture, decision, recycle, convergence, slice-5, description-epinglee, cadrage]
issues: [66]
---

# Cadrage architectural — issue #66 « slice 5/5 — dev (GREEN) — RECYCLE : re-livrer le commit GREEN perdu »

## Positionnement (cadre exact)

L'issue #66 (`labels: kanban` + `decision`, `idempotency-key gh-issue-66`,
OPEN) est le **miroir GitHub de la carte RECYCLE `t_e826bb9d`** (board
`pj-hermes-workflow`, assignée à `pj-master`), **neuvième import** du même
point à statuer conv-5 : le **re-poussage du commit GREEN dev-5 `6661362`
perdu** de la slice 5/5 du chantier **#19** (« Discord thread title and
description update »).

Le body de l'issue porte le point à statuer tel quel : verdict conv-5
(HEAD `55e6659`, banc 7/10 RED mesuré, rejouable) → **3 fixes keeper exacts
+ upsert-desc/pin dans le helper** ; le GREEN original `6661362` est
définitivement absent du dépôt, GREEN partial présent, pas de replay
possible ; `/ok` requis pour re-spawn. La carte cible déclarée dans le body
(`t_7aaf3d49`, slice 5/5 dev GREEN RECYCLE, assignée à `pj-dev`) est la
carte de re-livraison effective ; la chaîne d'escalade antérieure est
documentée par les notes [[issue-27]] (1ᵉʳ), [[issue-29]] (2ᵉ),
[[issue-41]] (4ᵉ) et [[issue-81]] (5ᵉ escalade conv-5, point à statuer
re-mesuré au 2026-10-10/11).

**Ce que la décision débloque** : le jeton `/ok` (premier élément d'un
commentaire GitHub sur l'issue #66) débloque la carte RECYCLE et relance la
production du GREEN — **nouveau commit**, jamais un replay de `6661362`
(absent du dépôt : `git cat-file -t 6661362` → `Not a valid object name`,
rejoué le 2026-10-11 sur le dépôt principal). Tout autre commentaire est une
demande d'éclaircissement et ne débloque rien.

Le présent cadrage **ne tranche pas** : il positionne le point à statuer
dans l'architecture existante, identifie les composants impactés et fixe les
critères de décision. Le re-poussage du GREEN est porté par la carte
RECYCLE après le `/ok`, jamais par ce cadrage.

## Croisement infrastructure / fonctionnel / code

### Infrastructure (frontières traversées)

- **GitHub** — surface de décision : commentaire `/ok` sur l'issue #66
  (`idempotency-key gh-issue-66`). Adapter : `gh` CLI, lu par le pont
  gh-kanban-bridge. L'issue est un **miroir** de la carte `t_e826bb9d` :
  elle ne porte pas de code, elle porte la décision.
- **Kanban Hermes** — source de vérité de l'état des cartes. `t_e826bb9d`
  (miroir, `archived` en attente de décision) et `t_7aaf3d49` (RECYCLE,
  `pj-dev`, `blocked` sur le jeton `/ok`) sont les deux faces du même point
  à statuer. L'effet du `/ok` est `unblock` + re-spawn de la carte RECYCLE.
- **Git / worktree partagé** — surface de livraison : le branch head de
  `wt/issue-19-discord-thread-title-description` est la **preuve de
  livraison** de la slice 5 (couverture commit-à-commit, cf.
  `docs/architecture/context/issue-29.md`). Un commit absent du branch head
  est un travail non livré, quel que soit le handoff du worker.
- **Aucun nouveau port** : les trois surfaces (GitHub, kanban, git)
  existent déjà ; l'issue #66 réutilise la boucle de décision de l'issue
  #5 ([[pj-decision]]) et le gate de couverture du pont
  ([[pj-bridge-coverage-gate]]).

### Fonctionnel (capacité traversée)

La capacité traversée est **re-livraison + preuve de livraison** (pas une
fonctionnalité nouvelle). Le chantier #19 est déjà cadré par les notes
[[issue-27]], [[issue-29]], [[issue-41]], [[issue-81]] et la note
composant `pj-thread-name` (slices 2–4 livrées sur la branche
`wt/issue-19-discord-thread-title-description`). #66 porte :

- **le point de décision** : le GREEN partial présent est-il suffisant pour
  relancer la production du GREEN ? (Verdict conv-5 : non — 3 fixes keeper
  + upsert-desc/pin restent à livrer.)
- **la chaîne de livraison** : qui applique les 3 fixes keeper et ajoute
  `upsert-desc`/`pin` dans le helper ? (La carte RECYCLE `t_7aaf3d49`,
  `pj-dev`, après le `/ok`.)
- **le verdict de convergence** : après livraison, le banc
  `tests/test_thread_description.py` passe-t-il 10/10 GREEN ?

### Code (composants impactés)

État mesuré le 2026-10-11 sur le **tip de la branche issue-19**
(`wt/issue-19-discord-thread-title-description` @ `9fcd207`, remote en sync) :

| composant | état mesuré | impact slice 5 |
|---|---|---|
| `pipeline/engine.py` | `build_description_lines` + `DESCRIPTION_MARKER` présents (4 hits grep) | Livré dans le GREEN partial |
| `pipeline/pj_room_keeper.py` | `build_description_for_card` (L572), `_issue_url_from_card` (L636), `_gh_repo` (L656), `sync_description` (L695), `sync_all_descriptions` (L799) présents (9 hits grep) | **3 fixes à livrer** (ci-dessous) |
| `tests/test_thread_description.py` | 387 lignes, 10 cas, **7/10 GREEN, 3 RED** (rejoué le 2026-10-11 depuis le tip `9fcd207` : `3 failed, 7 passed in 0.81s`) | Banc qui gèle le contrat `contrat-5` |
| `skills/gh-kanban-bridge/scripts/discord_thread.py` | Commandes `create`/`send`/`rename`/`threads` seulement (`upsert-desc` / `pin` : **0 hit** grep au tip) | **capacités à ajouter** |
| `git cat-file -t 6661362` | `fatal: Not a valid object name` (dépôt principal + remote) | GREEN original définitivement absent |

**Les 3 fixes keeper restants** (mesurés depuis les 3 tests RED) :

1. **`sync_description` (L695)** — le fil de la carte n'est pas résolu
   (`thread_id=None` au lieu de `TH-19`) : `thread_lookup` n'est pas passé
   en paramètre ni invoqué avec le bon contexte ; le test
   `test_nominal_un_seul_message_epingle_mis_a_jour_pas_duplique` lève
   `AssertionError: le fil de la carte doit être résolu :
   {'card_id': 't_cart', 'thread_id': None, ...}`.
2. **`_gh_repo()` (L656)** — le `rsplit("/", 1)[-1]` perd l'org `hyron-fr` :
   `https://github.com/hermes-workflow/issues/19` au lieu de
   `https://github.com/hyron-fr/hermes-workflow/issues/19`. Le test
   `test_erreur_gh_pr_list_en_erreur_ligne_omise_tracee_pas_exception`
   lève `AssertionError: la ligne Issue (ancre) reste présente`.
3. **`sync_all_descriptions` (L799)** — un lecteur de source qui lève
   (`specs_reader` sur `specs/19/slices.json` introuvable) ne doit pas
   tuer le tick : capturer, tracer, continuer. Le test
   `test_erreur_le_reader_de_source_qui_leve_ne_tue_pas_le_tick` lève
   `AssertionError` (le tick meurt au lieu de continuer).

## Lecture SDD (spec-driven)

La spec est le body de l'issue **#19** (arbitrages `Q1=1a`, `Q2=2b`,
`Q3=d`) et le banc `tests/test_thread_description.py` (387 lignes, 10 cas)
qui gèle le contrat `contrat-5` du bloc Description épinglé. L'issue #66
**est** le point à statuer de sa carte `t_e826bb9d` : le GREEN partial est
présent mais 3 tests sont RED et le helper n'a pas les capacités
`upsert-desc`/`pin`. La doc décrit le livré : ici le « livré » attendu est
le GREEN 10/10 (3 fixes keeper + upsert-desc/pin) ; jusqu'au `/ok`,
l'état mesuré est 7/10 GREEN + helper incomplet + GREEN original absent.

## Lecture DDD (bounded contexts, agrégats, événements)

- **Bounded context traversé** : *convergence / livraison* — chevauche
  *développement* (slice 5 de #19) et *décision humaine* (l'escalade
  #27→#29→#41→#81→#66), sans en être un nouveau : c'est la **jonction**
  entre les deux.
- **Agrégat racine** : la **carte `t_7aaf3d49`** (RECYCLE, invariant : elle
  ne repart en `ready` que sur un `/ok` portant sa ligne canonique
  `carte: pj-hermes-workflow/t_7aaf3d49`). L'**issue #66** est l'objet de
  décision qui la matérialise sur GitHub.
- **Value objects** : le **branch head SHA** (`9fcd207` mesuré) ; le **banc
  7/10** (état de convergence partiel) ; l'**idempotency-key**
  `gh-issue-66` ; le **verdict conv-5** (3 fixes keeper + upsert-desc/pin).
- **Domain events** : `/ok` humain sur l'issue #66 → unblock de
  `t_7aaf3d49` → dev applique les 3 fixes keeper + ajoute
  `upsert-desc`/`pin` → banc 10/10 GREEN → convergence → doc → doc-review →
  PR → merge.

## Lecture TDD (contrats testables)

Le contrat testable est le **banc `tests/test_thread_description.py`**
(387 lignes, 10 cas), rejouable sans Discord ni réseau (sources injectées,
0 réseau, 0 sous-processus) :

- `build_description_lines(issue_url, branch, pr_url, log=print) ->
  list[str]` — composition pure, omission des `None`/vides (cas GREEN).
- `keeper.build_description_for_card(card, *, …, specs_reader, pr_reader,
  issue_url_lookup)` — assemblage des sources injectées ; **1 cas RED** :
  le fix `_gh_repo()` (perte de l'org) fait échouer la ligne Issue (ancre).
- `keeper.sync_description(cards, *, fetch_messages, write_message,
  log=None)` — écrivain best-effort : dédup par marqueur, `edit` jamais
  second post ; **1 cas RED** : le fil de la carte n'est pas résolu
  (`thread_id=None`).
- `keeper.sync_all_descriptions(cards, *, …, specs_reader, pr_reader,
  issue_url_lookup)` — câblage best-effort ; **1 cas RED** : un lecteur de
  source qui lève tue le tick au lieu de le capturer et tracer.
- Les **3 cas RED** sont les critères d'acceptation restants de la slice
  5 ; leur passage GREEN est la preuve de convergence.

## Lecture hexagonale (le core reste pur)

Le **core pur** : `build_description_lines` (fonction pure : issue_url,
branch, pr_url → list[str], 0 réseau, 0 horloge, 0 aléa) et
`build_description_for_card` (sources injectées, 0 réseau). L'écriture du
message épinglé et de l'épingle passe par le helper `discord_thread.py`
(adapter REST, hors core). Le contrat d'interface (marqueur
`[description]`, `sync_description`, `sync_all_descriptions`) est testable
sans Discord : les sources et l'adaptateur sont injectés.

La frontière à respecter : **la description est une lecture d'état**
(gh/git/blackboard) résolue **hors** du core, puis injectée dans le
formateur pur. Jamais l'inverse : le formateur ne lit pas le réseau. Les 3
fixes keeper restants respectent cette frontière : ils corrigent la
résolution du fil, la lecture de l'org et le best-effort du tick, sans
ajouter de dépendance réseau au core.

## Frontières traversées (résumé)

```
issue #66 (GitHub, labels kanban + decision, miroir de t_e826bb9d)
  → commentaire /ok humain (surface de décision)
  → unblock de t_7aaf3d49 (kanban, carte RECYCLE)
  → dev applique 3 fixes keeper + upsert-desc/pin (git, worktree partagé)
  → banc test_thread_description.py 10/10 GREEN (preuve de convergence)
  → doc → doc-review → PR → merge
```

Deux frontières : **GitHub ↔ kanban** (décision → effet) et
**git ↔ worktree partagé** (preuve de livraison). Le point de fragilité
n'est pas l'appel réseau mais **la couverture commit-à-commit** : un commit
absent du branch head est un travail non livré, quel que soit le handoff du
worker.

## État mesuré (2026-10-11, rejouable)

- `origin/dev` = `2027333` (docs cadrage issue #29).
- `wt/issue-19-discord-thread-title-description` :
  - **local** (worktree partagé) = `9fcd207` (docs cadrage issue #73,
    tip de la branche).
  - **remote** = `9fcd207` (en sync).
- `git cat-file -t 6661362` → **fatal : Not a valid object name**
  (dépôt principal + remote).
- `grep DESCRIPTION_MARKER|build_description|sync_description` sur
  `pipeline/` au tip `9fcd207` → **présents** (9 hits keeper, 4 hits
  engine).
- `grep upsert-desc|"pin"|'pin'` sur
  `skills/gh-kanban-bridge/scripts/discord_thread.py` au tip `9fcd207` →
  **0 hit** (capacités non livrées).
- Banc `tests/test_thread_description.py` : **7/10 GREEN, 3 RED** (rejoué
  le 2026-10-11 depuis le tip `9fcd207` via
  `uv run --with pytest --with pytest-randomly --with pyyaml --with
  langgraph --with hermes-agent -m pytest tests/test_thread_description.py
  -q -p no:randomly` → `3 failed, 7 passed in 0.81s`).
- `pj_docs_lint.py` sur `/home/elix/pj-repos/hermes-workflow` → `exit=0`.

## Composants impactés (résumé)

- **Décision (cette issue)** : `pipeline/pj_decision.py` ([[pj-decision]])
  + `pipeline/pj_escalate.py` / `pipeline/pj_notify.py` ([[pj-notify]]) —
  la boucle #5, aucun changement de code.
- **Travail débloqué (slice 5 de #19, à compléter)** :
  - `pipeline/pj_room_keeper.py` — 3 fixes :
    (1) `sync_description` : résolution du fil via `thread_lookup` (passage
    en paramètre + invocation avec le bon contexte) ;
    (2) `_gh_repo()` : conservation de l'org complet (`hyron-fr`) plutôt
    que le `rsplit` qui le perd ;
    (3) `sync_all_descriptions` : capture du lecteur qui lève (best-effort,
    le tick ne meurt pas).
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
3. **La voie de re-poussage** : nouveau commit sur
   `wt/issue-19-discord-thread-title-description` (worktree partagé
   `t_c22a7e74`) vs branche dédiée `wt/issue-19-restore-green-5`
   (`t_4d471dce`, stale). Le body de l'issue #66 décline le choix par
   défaut : nouveau commit sur la branche issue-19 (pas de replay de
   `6661362`).
4. **La publication live des copies `~/.hermes/scripts/`** (divergence D2
   déclarée dans le handoff `dev-5`) — opération de fin de graphe
   contrôlée par identité, hors périmètre de cette décision.

Ces points sont **documentés**, pas décidés ici.

## Hors-scope

- **Le re-push effectif du GREEN** : porté par la carte RECYCLE
  `t_7aaf3d49` (`pj-dev`) après le `/ok`, jamais par ce cadrage.
- **La convergence effective de la slice 5** : portée par la carte
  RECYCLE après le `/ok`.
- **Les slices 1–4 de #19** : déjà livrées, cadrées par la note
  `pj-thread-name` et les notes [[issue-27]]/[[issue-29]].
- **La duplication bridge↔pipeline↔agents des `pj_*.py`** : divergence
  connue (les 3 copies du keeper sont identiques à ce stade), non traitée
  par #66.
- **Le verdict de convergence** : porté par `pj-test` sur la carte RECYCLE
  après le `/ok`, pas par ce cadrage.
