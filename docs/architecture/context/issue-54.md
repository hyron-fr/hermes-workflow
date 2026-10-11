---
type: context
status: draft
tags: [architecture, decision, escalation, conv-5, recycle, slice-5, green-re-push, cadrage]
issues: [54]
---

# Cadrage architectural — issue #54 « slice 5/5 — dev (GREEN) — RECYCLE : re-livrer le commit GREEN perdu »

## Positionnement (cadre exact)

L'issue #54 (`labels: kanban` + `decision`, `idempotency-key gh-issue-54`,
comment GitHub 2026-10-08 19:22) est le **miroir kanban de la carte
`t_854f0f77`** (board `pj-hermes-workflow`, assignée `pj-dev`, titre « slice 5/5
— dev (GREEN) — RECYCLE : re-livrer le commit GREEN perdu »), bloquée sur le
ticket **#45**. Son corps pointe `t_854f0f77` comme carte à statuer ; le jeton
`/ok` commenté comme premier élément débloque et relance la carte.

Elle s'implante dans l'**architecture existante** du chantier **#19**
(« Discord thread title and description update », moitié « Description
épinglée »), en tant que **miroir de décision de la chaîne conv-5** :
`#19 → #27 → #29 → #45 → #41 → #60 → #66 → …` (état mesuré au 2026-10-11).

Le point à statuer mesuré :

- Le commit GREEN dev-5 **`6661362`** est **définitivement perdu**
  (`git cat-file -t 6661362` → `fatal: Not a valid object name`, 0 hit sur
  refs/reflogs/fsck/GitHub, état vérifié au 2026-10-08).
- Le périmètre de re-livraison est gelé par la conv-5 : **3 fixes keeper**
  (a) `sync_description` injecte `issue_url_lookup` ;
  (b) `_gh_repo()` conserve l'ORG (rsplit perdait `hyron-fr`) ;
  (c) `sync_all_descriptions` injecte `issue_url_lookup`) **+ 2 commandes
  helper** (`upsert-desc`, `pin`) dans `discord_thread.py`, **banc
  `tests/test_thread_description.py` 10/10**, **nouveau commit**
  (interdit de rejouer `6661362`), **push vérifié `0 0`** avant
  `kanban_complete`.
- La décision de JB du 2026-10-10 (#33) arbitre la voie : **re-poussage par
  cycle normal** (nouveau commit), pas de replay du SHA perdu.

**Ce que la décision débloque** : le `/ok` sur l'issue #54 (premier élément)
débloque la carte `t_854f0f77` et la relance en file. L'effet attendu :
application des 3 fixes keeper + ajout des 2 commandes helper, passage du banc
10/10, nouveau commit sur `wt/issue-19-discord-thread-title-description`,
push vérifié `0 0`.

## Croisement infrastructure / fonctionnel / code

### Infrastructure (frontières traversées)

- **GitHub** — surface de décision : commentaire `/ok` sur l'issue #54
  (miroir de la carte `t_854f0f77`). Adapter : `gh` CLI, lu par le pont de
  couverture `pj_bridge_coverage.py`. La carte `t_854f0f77` est l'objet de la
  décision.
- **Kanban Hermes** — source de vérité de l'état des cartes. L'effet est
  `comment` + `unblock` sur `t_854f0f77`, invoqués en `subprocess` par le
  câblage du pont.
- **Git / worktree partagé** — surface de livraison : la branche
  `wt/issue-19-discord-thread-title-description` (worktree partagé
  `t_c22a7e74`) est la **preuve de livraison** de la slice 5. Le GREEN
  partial (banc 7/10, 3 rouges nommés) est présent dans l'arbre ; le re-GREEN
  (banc 10/10) reste à produire.
- **Discord** — canal de notification : les décisions et les re-poussages sont
  notifiés dans le thread de la chaîne conv-5 (`1558029650494758932`).
- **Aucun nouveau port** : les quatre surfaces (GitHub, kanban, git, Discord)
  existent déjà ; l'issue #54 réutilise la boucle de décision du chantier #19.

### Fonctionnel (capacité traversée)

La capacité traversée est **convergence + preuve de livraison** (pas une
fonctionnalité nouvelle). Le chantier #19 est déjà cadré par les notes
`issue-27` (escalade 1ᵉʳ), `issue-29` (escalade 2ᵉ), `issue-41` (escalade
4ᵉ), `issue-60` (escalade 6ᵉ), `issue-64` (miroir t5) et la note composant
`pj-thread-name` (slices 2–4 livrées). #54 porte :

- **le point de décision** : le périmètre re-GREEN (3 fixes keeper + 2
  commandes helper) est-il complet et mesurable ? (Oui — fixé par la conv-5
  et par les 3 rouges nommés du banc.)
- **la chaîne de livraison** : qui applique les 3 fixes keeper et ajoute
  `upsert-desc`/`pin` dans le helper ? (Le dev, après le `/ok`.)
- **le verdict de convergence** : après les fixes, le banc
  `tests/test_thread_description.py` passe-t-il 10/10 GREEN ?

### Code (composants impactés)

| composant | état mesuré (2026-10-11) | impact slice 5 |
|---|---|---|
| `pipeline/pj_room_keeper.py` | `build_description_for_card` (L572), `sync_description` (L695), `sync_all_descriptions` (L799) présents ; 3 fixes à appliquer : (a) L715 `thread_lookup` injectable, (b) L637 `_gh_repo()` conserve l'ORG, (c) L815 `issue_url_lookup` injecté | 3 tests RED à refermer |
| `pipeline/engine.py` | `DESCRIPTION_MARKER` (L221), `build_description_lines` (L234) présents | Livré dans le GREEN partial |
| `tests/test_thread_description.py` | 387 lignes, 10 cas ; **3 failed / 7 passed** mesuré au 2026-10-11 | Banc qui gèle le contrat `contrat-5` |
| `skills/gh-kanban-bridge/scripts/discord_thread.py` | Commandes `create`/`send`/`threads`/`rename` seulement ; **`upsert-desc` + `pin` absents** (grep : 0 hit) | 2 commandes à ajouter |

Le **core pur** à préserver : `build_description_lines` (composition pure :
issue_url, branch, pr_url → list[str], 0 réseau) et
`build_description_for_card` (sources injectées). L'écriture du message et de
l'épingle passe par le helper `discord_thread.py` (adapter REST, hors core).

## Lecture SDD (spec-driven)

La spec est le body de l'issue **#19** (arbitrages `Q1=1a`, `Q2=2b`, `Q3=d`)
; l'issue #54 **est** le miroir de la carte `t_854f0f77` (RECYCLE GREEN). Le
périmètre est gelé par la conv-5 et par les 3 rouges nommés du banc :
l'unique action = appliquer les 3 fixes keeper + ajouter les 2 commandes
helper + passer le banc 10/10 + pousser un nouveau commit sur
`wt/issue-19-discord-thread-title-description`. La doc décrit le livré :
ici le « livré » attendu est le re-GREEN 10/10 ; jusqu'au `/ok`, l'état
mesuré est GREEN partial 7/10 + helper incomplet.

## Lecture DDD (bounded contexts, agrégats, événements)

- **Bounded context traversé** : *convergence / livraison* — chevauche
  *développement* (slice 5 de #19) et *décision humaine* (l'escalade
  #27→#29→#45→#41→#60→#66→#54), sans en être un nouveau : c'est la
  **jonction** entre les deux.
- **Agrégat racine** : la **carte `t_854f0f77`** (invariant : elle ne repart
  en `ready` que sur un `/ok` portant sa ligne canonique
  `carte: pj-hermes-workflow/t_854f0f77`). L'**issue #54** est l'objet de
  décision qui la matérialise.
- **Value objects** : le **branch head SHA** de
  `wt/issue-19-discord-thread-title-description` ; le **banc 7/10** (état de
  convergence partiel) ; l'**idempotency-key** `gh-issue-54` ; le périmètre
  re-GREEN (3 fixes + 2 commandes, gelé).
- **Domain events** : `/ok` humain sur l'issue #54 → unblock de
  `t_854f0f77` → re-spawn dev → application des 3 fixes keeper + ajout des 2
  commandes helper → banc 10/10 GREEN → nouveau commit → push vérifié `0 0`
  → convergence → doc → doc-review → PR → merge.

## Lecture TDD (contrats testables)

Le contrat testable est le **banc `tests/test_thread_description.py`**
(387 lignes, 10 cas : 3 nominal / 3 limite / 4 erreur), rejouable sans
Discord ni réseau (sources injectées) :

- `build_description_lines(issue_url, branch, pr_url, log=print) -> list[str]`
  — composition pure, 4 lignes, omission des `None`/vides (4 cas GREEN).
- `keeper.build_description_for_card(card, *, …, specs_reader, pr_reader,
  issue_url_lookup)` — assemblage des sources injectées (2 cas GREEN).
- `keeper.sync_description(cards, *, fetch_messages, write_message, log=None)`
  — écrivain best-effort : dédup par marqueur, `edit` jamais second post.
- **Les 3 cas RED** (mesurés au 2026-10-11) sont les critères
  d'acceptation restants de la slice 5 :
  1. `test_nominal_un_seul_message_epingle_mis_a_jour_pas_duplique` —
     `sync_description` doit résoudre le fil par l'ancre d'import quand
     `thread_lookup` n'est pas injecté.
  2. `test_erreur_gh_pr_list_en_erreur_ligne_omise_tracee_pas_exception` —
     le banc patche le module-level `issue_url_lookup` ; le code n'a pas cet
     attribut, le repli `_gh_repo` renvoie `hermes-workflow` sans org.
  3. `test_erreur_le_reader_de_source_qui_leve_ne_tue_pas_le_tick` — même
     cause : le reader de source qui lève ne doit pas tuer le tick.
- Leur passage GREEN est la preuve de convergence.

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
issue #54 (GitHub, labels kanban+decision, miroir de t_854f0f77)
  → commentaire /ok humain (surface de décision)
  → unblock de t_854f0f77 (kanban)
  → re-spawn dev (pj-dev)
  → application 3 fixes keeper + ajout upsert-desc/pin
  → banc test_thread_description.py 10/10 GREEN (preuve de convergence)
  → nouveau commit sur wt/issue-19-discord-thread-title-description
  → push vérifié 0 0
  → convergence → doc → doc-review → PR → merge
```

Quatre frontières : **GitHub ↔ kanban** (décision → effet),
**kanban ↔ dev** (spawn → travail), **dev ↔ git** (code → commit),
**git ↔ remote** (push → preuve). Le point de fragilité n'est pas l'appel
réseau mais **la couverture commit-à-commit** : un fix non-commité dans
l'arbre n'est pas un travail livré.

## État mesuré (2026-10-11, rejouable)

- `origin/dev` = `2027333` (docs cadrage issue #29).
- Worktree issue #54 : `/home/elix/pj-repos/hermes-workflow/.worktrees/t_d0633fb4`
  sur `wt/t_d0633fb4`, base `origin/dev` (`2027333`), HEAD = `564128d`
  (3 commits d'avance, 0 behind), propre.
- Worktree partagé du chantier #19 : `t_c22a7e74` sur
  `wt/issue-19-discord-thread-title-description`, HEAD = `95d4db0`
  (docs cadrage issue #58 + MOC).
- `git cat-file -t 6661362` → **fatal : Not a valid object name**
  (définitivement absent).
- GREEN partial présent dans l'arbre : `DESCRIPTION_MARKER` +
  `build_description_lines` + `build_description_for_card` +
  `sync_description` + `sync_all_descriptions` (grep : présents dans
  `pipeline/pj_room_keeper.py` et `pipeline/engine.py`).
- `grep upsert-desc|pin` sur `skills/gh-kanban-bridge/scripts/discord_thread.py`
  → **0 hit** (capacités non livrées).
- Banc `tests/test_thread_description.py` : **3 failed / 7 passed**
  (mesuré au 2026-10-11 via `uv run --with pytest --with pyyaml --with
  langgraph python -m pytest tests/test_thread_description.py -v -p
  no:randomly` ; les 3 rouges nommés :
  `test_nominal_un_seul_message_epingle_mis_a_jour_pas_duplique`,
  `test_erreur_gh_pr_list_en_erreur_ligne_omise_tracee_pas_exception`,
  `test_erreur_le_reader_de_source_qui_leve_ne_tue_pas_le_tick`).
- `pj_docs_lint.py` sur `/home/elix/pj-repos/hermes-workflow` → `exit=0`.

## Composants impactés (résumé)

- **Décision (cette issue)** : `pipeline/pj_bridge_coverage.py` (pont de
  couverture, détecte le `/ok` et débloque la carte) +
  `pipeline/pj_decision.py` ([[pj-decision]]) — la boucle #5, aucun
  changement de code.
- **Travail débloqué (slice 5 de #19, à compléter)** :
  - `pipeline/pj_room_keeper.py` — 3 fixes : (a) `sync_description` injecte
    `thread_lookup`/`issue_url_lookup` ; (b) `_gh_repo()` conserve l'ORG ;
    (c) `sync_all_descriptions` injecte `issue_url_lookup`.
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
2. **La forme des commandes `upsert-desc`/`pin`** — porté par le dev ; le
   banc ne les teste pas directement (le helper est un adapter, injecté).
3. **La publication live des copies `~/.hermes/scripts/`** (divergence
   déclarée dans le handoff `dev-5`) — opération de fin de graphe contrôlée
   par identité, hors périmètre de cette décision.

Ces points sont **documentés**, pas décidés ici.

## Liens croisés

- [[issue-27]] — escalade 1ᵉʳ de la chaîne conv-5 (même chantier #19).
- [[issue-29]] — escalade 2ᵉ de la chaîne conv-5.
- [[issue-41]] — escalade 4ᵉ de la chaîne conv-5 (grill-me, verdict gelé).
- [[issue-60]] — escalade 6ᵉ de la chaîne conv-5 (re-import stérile).
- [[issue-64]] — miroir de décision t5 (même chantier #19).
- [[pj-thread-name]] — note composant des slices 2–4 livrées.
- [[issue-19]] — chantier parent (« Discord thread title and description
  update »).
