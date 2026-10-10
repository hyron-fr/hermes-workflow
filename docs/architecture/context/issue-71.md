---
type: context
status: draft
tags: [architecture, decision, escalation, recycle, convergence, slice-5, description-epinglee, cadrage]
issues: [71]
---

# Cadrage architectural — issue #71 « t2 mémoire projet » (miroir du point à statuer #29)

## Positionnement (cadre exact)

L'issue #71 (`labels: decision` + `kanban`, `idempotency-key gh-issue-71`,
parent GitHub **#29**) est le **miroir GitHub** de l'issue #29 : un ticket de
décision qui porte le **point à statuer** mesuré sur la carte
**`t_87ba23bf`** (board `pj-hermes-workflow`, « t2 mémoire projet », assignée
à `pj-master`).

Ce n'est **pas une tâche de développement** : le travail attendu est un
arbitrage humain. Le corps de l'issue est explicite — le jeton `/ok` en
**premier élément** d'un commentaire débloque la carte `t_87ba23bf` et la
repart en file ; tout autre commentaire est une demande d'éclaircissement et
ne débloque rien.

### Où s'implante l'issue dans la chaîne d'escalade

L'issue #71 est le **8ᵉ import GitHub** du même point à statuer —
« re-poussage du commit GREEN dev-5 (`6661362`) perdu », chantier #19, slice
5/5 « description-épinglée » (moitié *Description épinglée* du fil Discord).
Chaîne d'escalade conv-5 mesurée :

| # | Issue | Carte portée | Nature |
|---|---|---|---|
| 1ᵉʳ | #19 | (chantier) | Chantier « Discord thread title and description update » |
| 1ᵉʳ import | #27 | `t_f725879f` (conv-5) | GREEN dev-5 `6661362` perdu, banc 10/10 RED |
| 2ᵉ | #29 | `t_f725879f` (conv-5) | Même point, ré-importé par le pont de couverture |
| 3ᵉ | #37 | `t_87ba23bf` (t2 mémoire #29) | Bloquée après crash de worker (gave_up) |
| 4ᵉ | #41 | `t_3f7e0be4` (t3 grill-me) | Verdict grill-me `PROTOTYPE: non` |
| 5ᵉ | #81 | `t_c0e5ce5a` (t3 grill-me) | Banc 7/10, verdict `PROTOTYPE: non` |
| 6ᵉ | #80 | (cadrage conv-5) | État mesuré 2026-10-10 |
| 7ᵉ | #75 | (cadrage conv-5) | Banc 7/10 rejoué, GREEN partial commité |
| 8ᵉ | #74 / #73 | `t_3f7e0be4` | Verdict AMBIGU |
| **9ᵉ (cette issue)** | **#71** | **`t_87ba23bf`** (t2 mémoire #29) | Miroir de #29 ; `/ok` débloque `t_87ba23bf` |

La carte cible `t_87ba23bf` est aujourd'hui `blocked` (statut
`needs_input`/gave_up après crash du worker, run 294, `pid 211892 not alive`
— provider unavailable, 2026-10-03). Son objet d'origine : « résumer les
mémoires du projet (banque `pj`, tags `project:hermes-workflow`, `issue:29`)
en commentaire de cette carte ». **Le résumé a déjà été livré par une autre
carte** : `t_1dd8b0bf` (t2 mémoire issue #71, done le 2026-10-11) a posté le
résumé en commentaire 1281 de la carte ET en commentaire GitHub 6103152677
sur l'issue #71. L'effet du `/ok` sur #71 = débloquer `t_87ba23bf` et la
repartir en file — elle pourra alors vérifier que le résumé existe déjà et
converger sans re-travail, ou produire le récap final si le verdict humain
l'exige.

### Point à statuer (mesuré le 2026-10-11, rejouable)

- Le commit **`6661362`** (GREEN dev-5 original, chantier #19 slice 5/5) est
  **définitivement absent** du dépôt local ET du remote :
  `git cat-file -t 6661362` → `fatal: Not a valid object name` (vérifié dans
  le checkout principal `/home/elix/pj-repos/hermes-workflow` et le worktree
  partagé `t_c22a7e74`).
- Le **GREEN partial** est **commité** dans le worktree partagé
  `t_c22a7e74` (tip `9fcd207`) : `DESCRIPTION_MARKER`
  (`pipeline/engine.py:221`), `build_description_lines` (L224),
  `build_description_for_card` (`pipeline/pj_room_keeper.py:572`),
  `sync_description` (L695), `sync_all_descriptions` (L799).
- `git status --short` dans `t_c22a7e74` : **fix keeper non-commité** —
  `M pipeline/pj_room_keeper.py` (hors de l'arbre commité ; un fix
  non-commité n'est pas un travail livré, cf. [[ADR-0001-identite-asset-et-preuve-sans-oracle-externe]]).
- **Banc `tests/test_thread_description.py` : 7/10 GREEN, 3 RED**, rejoué le
  2026-10-11 dans `t_c22a7e74` via
  `uv run --with pytest --with pyyaml --with langgraph --with duckdb
  python -m pytest tests/test_thread_description.py -p no:randomly -q`
  (l'environnement de deps est requis — `pipeline/engine.py` importe
  `yaml` et `langgraph` en tête de module) :
  - `test_nominal_un_seul_message_epingle_mis_a_jour_pas_duplique` (fix
    keeper de déduplication)
  - `test_erreur_gh_pr_list_en_erreur_ligne_omise_tracee_pas_exception`
    (journalisation bruyante quand le reader PR lève)
  - `test_erreur_le_reader_de_source_qui_leve_ne_tue_pas_le_tick`
    (non-lèvement quand un reader de source lève)
- Les capacités **`upsert-desc`** et **`pin`** sont **absentes** du helper
  Discord : `grep upsert-desc\|"pin"\|'pin'` dans
  `skills/gh-kanban-bridge/scripts/discord_thread.py` → **0 hit**.
- `origin/dev` = `2027333` (docs cadrage #29) ; `wt/t_0534889b` (branche de
  cette carte) = `7091678` (cadrage #81, base dev vérifiée ancestor).

**Ce que la décision débloque** : le `/ok` sur #71 (premier élément) fait
déboucler `t_87ba23bf` et la repart en file. L'effet attendant du chantier #19
: **appliquer les 2 fixes keeper restants + ajouter `upsert-desc`/`pin` dans
le helper**, committer le GREEN partial (fix keeper non-commité), puis le banc
passe 10/10 → preuve de convergence commit-à-commit → merge avec #19.
Ces actions de développement relèvent de la carte débloquée et de sa descendance,
**pas** du périmètre de cette issue de décision.

## Croisement infrastructure / fonctionnel / code

### Infrastructure (frontières traversées)

- **GitHub** — surface de décision : commentaire `/ok` sur l'issue #71
  (l'enfant de #29). Adapter : `gh` CLI, lu par le pont. La carte
  `t_87ba23bf` est l'objet de la reprise.
- **Kanban Hermes** — source de vérité de l'état des cartes. L'effet est
  `unblock` sur `t_87ba23bf` (carte `blocked` → `ready`), invoqué par le
  câblage de #5 ([[pj-decision]] : `decision_from_comment` calcule la
  décision, l'appelant l'applique — jamais l'inverse).
- **Git / worktree partagé** — surface de livraison : le branch head de
  `wt/issue-19-discord-thread-title-description` (worktree `t_c22a7e74`,
  tip `9fcd207`) est la **preuve de livraison** de la slice 5.
- **Hindsight (banque `pj`)** — source de mémoire projet : tags
  `project:hermes-workflow`, `issue:29` / `issue:71` ; la carte cible
  `t_87ba23bf` est une carte « t2 mémoire » dont le contenu est un résumé
  de la banque. Le résumé a été livré par `t_1dd8b0bf` (commentaire 1281 de
  la carte + commentaire GitHub 6103152677).
- **Aucun nouveau port** : les quatre surfaces (GitHub, kanban, git,
  Hindsight) existent ; l'issue #71 réutilise la boucle de décision #5 et le
  flux mémoire existant.

### Fonctionnel (capacité traversée)

La capacité traversée est **convergence + preuve de livraison** (pas une
fonctionnalité nouvelle). Le chantier #19 (« Discord thread title and
description update ») est déjà cadré par la note [[issue-27]] (escalade 1ᵉʳ),
la note [[issue-29]] (escalade 2ᵉ), la note [[issue-41]] (escalade 4ᵉ) et
la note composant [[pj-thread-name]] (slices 2–4 livrées). #71 porte :

- **le point de décision** : le GREEN partial (7/10 banc, 3 fixes keeper
  restants + `upsert-desc`/`pin` manquants) est-il suffisant pour considérer
  la slice 5 comme convergée ? Verdict antérieur grill-me (carte `t_acc83f5a`,
  issue #41) : `PROTOTYPE: non, AMBIGU: aucune, ARTEFACT: aucun` — le
  périmètre est gelé par le banc (contrat-5, blackboard racine `t_83401cbb`).
- **la chaîne de livraison** : qui applique les 2 fixes keeper restants et
  ajoute `upsert-desc`/`pin` dans le helper ? (Le dev, après le `/ok`.)
- **le verdict de convergence** : après les fixes, le banc
  `tests/test_thread_description.py` passe-t-il 10/10 GREEN et est-il
  commité (preuve commit-à-commit) ?

### Code (composants impactés)

| composant | état mesuré (2026-10-11) | impact slice 5 |
|---|---|---|
| `pipeline/engine.py` | `DESCRIPTION_MARKER` (L221) + `build_description_lines` (L224) présents | Livré dans le GREEN partial |
| `pipeline/pj_room_keeper.py` | `build_description_for_card` (L572), `sync_description` (L695), `sync_all_descriptions` (L799) présents ; **fix non-commité dans l'arbre** (`M pipeline/pj_room_keeper.py`) | 3 tests RED : (1) déduplication du message épinglé, (2) journalisation bruyante du reader PR qui lève, (3) non-lèvement du tick quand un reader de source lève |
| `tests/test_thread_description.py` | 387 lignes, 10 cas, **7 GREEN / 3 RED** | Banc qui gèle le contrat `contrat-5` |
| `skills/gh-kanban-bridge/scripts/discord_thread.py` | Commandes `create`/`send`/`rename`/`threads` seulement | **`upsert-desc` + `pin` à ajouter** |

Le **core pur** à préserver : `build_description_lines` (composition pure :
issue_url, branch, pr_url → list[str], 0 réseau) et
`build_description_for_card` (sources injectées). L'écriture du message et
de l'épingle passe par l'adapter injecté `write_message` / le helper Discord.

## Lecture SDD (spec-driven)

La spec est le body de l'issue **#19** (arbitrages `Q1=1a`, `Q2=2b`, `Q3=d`)
; l'issue #71 **est** le point à statuer de sa carte `t_87ba23bf`. Le
verdict du grill-me (carte `t_acc83f5a`, issue #41) fixe le périmètre :
l'unique action = s'assurer que les 10 tests passent, committer le GREEN
partial (fix keeper non-commité) + ajouter `upsert-desc`/`pin` dans le
helper, puis pousser sur `wt/issue-19-discord-thread-title-description`.
La doc décrit le livré : ici le « livré » attendu est le GREEN 10/10
commité ; jusqu'au `/ok`, l'état mesuré est 7/10 GREEN + fix non-commité +
helper incomplet.

## Lecture DDD (bounded contexts, agrégats, événements)

- **Bounded context traversé** : *convergence / livraison* — chevauche
  *développement* (slice 5 de #19) et *décision humaine* (l'escalade
  #27→#29→#37→#41→#81→#80→#75→#74→#73→**#71**), sans en être un nouveau :
  c'est la **jonction** entre les deux.
- **Agrégat racine** : la **carte `t_87ba23bf`** (invariant : elle ne repart
  en `ready` que sur un `/ok` portant sa ligne canonique
  `carte: pj-hermes-workflow/t_87ba23bf`). L'**issue #71** est l'objet de
  décision qui la matérialise.
- **Value objects** : le **branch head SHA** (`9fcd207` mesuré) ; le **banc
  7/10** (état de convergence partiel) ; l'**idempotency-key** `gh-issue-71`
  ; le verdict grill-me (`PROTOTYPE: non, AMBIGU: aucune` — hérité de
  l'escalade 4ᵉ, à confirmer ou infirmer par le `/ok`).
- **Domain events** : `/ok` humain sur l'issue #71 → unblock de
  `t_87ba23bf` → re-spawn (t2 mémoire reformule / vérifie que le résumé
  existe déjà) → dev applique les 2 fixes keeper + ajoute `upsert-desc`/`pin`
  → banc 10/10 GREEN → commit du GREEN partial → convergence → doc →
  doc-review → PR → merge.

## Lecture TDD (contrats testables)

Le contrat testable est le **banc `tests/test_thread_description.py`**
(387 lignes, 10 cas), rejouable sans Discord ni réseau (sources injectées,
mais l'environnement de deps est requis : `uv run --with pytest --with
pyyaml --with langgraph --with duckdb`) :

- `build_description_lines(issue_url, branch, pr_url, log=print) -> list[str]`
  — composition pure, 4 lignes, omission des `None`/vides (4 cas GREEN).
- `keeper.build_description_for_card(card, *, …, specs_reader, pr_reader,
  issue_url_lookup)` — assemblage des sources injectées (2 cas GREEN,
  1 cas RED : le reader qui lève ne doit pas tuer le tick).
- `keeper.sync_description(cards, *, fetch_messages, write_message, log=None)`
  — écrivain best-effort : dédup par marqueur, `edit` jamais second post
  (1 cas RED : un seul message épinglé mis à jour pas dupliqué).
- `test_erreur_gh_pr_list_en_erreur_ligne_omise_tracee_pas_exception`
  (1 cas RED : journalisation bruyante quand le reader PR lève).
- Les **3 cas RED** sont les critères d'acceptation restants de la slice 5 ;
  leur passage GREEN + le commit du fix keeper non-commité sont la preuve de
  convergence.

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
issue #71 (GitHub, labels decision + kanban, parent #29)
  → commentaire /ok humain (surface de décision)
  → unblock de t_87ba23bf (kanban, was blocked/gave_up)
  → t2 mémoire reformule / vérifie le résumé existant (Hindsight)
  → dev applique 2 fixes keeper + upsert-desc/pin, commit du GREEN partial
  → banc test_thread_description.py 10/10 GREEN (preuve de convergence commit-à-commit)
  → doc → doc-review → PR → merge avec #19
```

Deux frontières : **GitHub ↔ kanban** (décision → effet) et
**git ↔ worktree partagé** (preuve de livraison). Le point de fragilité n'est
pas l'appel réseau mais **la couverture commit-à-commit** : un fix non-commité
dans l'arbre n'est pas un travail livré.

## État mesuré (2026-10-11, rejouable)

- `origin/dev` = `2027333` (docs cadrage #29).
- `wt/t_0534889b` (branche de cette carte, worktree scratch
  `/home/elix/.hermes/kanban/boards/pj-hermes-workflow/workspaces/t_0534889b`)
  = `7091678` (cadrage #81, base dev vérifiée ancestor).
- `wt/issue-19-discord-thread-title-description` (worktree partagé
  `t_c22a7e74`) = `9fcd207` (docs cadrage #73) :
  - `git cat-file -t 6661362` → **fatal : Not a valid object name**
    (définitivement absent, local ET remote).
  - `git status --short` : `?? docs/.../issue-27.md`,
    `?? docs/.../issue-29.md`, `M pipeline/pj_room_keeper.py`
    (fix keeper non-commité).
  - `grep DESCRIPTION_MARKER|build_description|sync_description` sur
    `pipeline/` → **présents** (GREEN partial commité dans l'arbre).
  - `grep upsert-desc\|"pin"\|'pin'` sur
    `skills/gh-kanban-bridge/scripts/discord_thread.py` → **0 hit**
    (capacité non livrée).
  - Banc `tests/test_thread_description.py` : **7/10 GREEN, 3 RED** (mesuré
    2026-10-11, rejouable via `uv run --with pytest --with pyyaml --with
    langgraph --with duckdb python -m pytest
    tests/test_thread_description.py -p no:randomly -q`).
- `pj_docs_lint.py` sur `/home/elix/pj-repos/hermes-workflow` → `exit=0`
  (mesuré avant ce commit).

## Composants impactés (résumé)

- **Décision (cette issue)** : `pipeline/pj_decision.py` ([[pj-decision]]) +
  `pipeline/pj_escalate.py` / `pipeline/pj_notify.py` ([[pj-notify]]) — la
  boucle #5, aucun changement de code.
- **Mémoire projet (carte cible)** : Hindsight banque `pj`, tags
  `project:hermes-workflow`, `issue:29` / `issue:71` ; résumé déjà livré par
  `t_1dd8b0bf` (commentaire 1281 + commentaire GitHub 6103152677).
- **Travail débloqué (slice 5 de #19, à compléter)** :
  - `pipeline/pj_room_keeper.py` — 2 fixes : (1) logique de déduplication
    pour qu'un seul message épinglé soit mis à jour (pas dupliqué),
    (2) non-lèvement quand un reader de source lève (le tick ne meurt pas)
    + journalisation bruyante quand le reader PR lève.
  - `skills/gh-kanban-bridge/scripts/discord_thread.py` — ajout des
    capacités `upsert-desc` (édition du message du fil) et `pin`
    (épingle du message).
- **Vault** : à la convergence, la slice 5 gagnera sa note composant et le
  MOC `docs/architecture/README.md` sera mis à jour par la carte `doc-k` —
  hors périmètre de cette décision.

## Non tranché (et qui doit le rester ici)

Le cadrage ne tranche **pas** :
1. **Le contenu exact des 2 fixes keeper** — porté par le dev après le
   `/ok` (le banc définit le contrat, pas le cadrage).
2. **La forme des capacités `upsert-desc`/`pin`** — porté par le dev ; le
   banc ne les teste pas directement (le helper est un adapter, injecté).
3. **La publication live des copies `~/.hermes/scripts/`** (divergence D2
   déclarée dans le handoff `dev-5`) — opération de fin de graphe contrôlée
   par identité, hors périmètre de cette décision.

Ces points sont **documentés**, pas décidés ici.
