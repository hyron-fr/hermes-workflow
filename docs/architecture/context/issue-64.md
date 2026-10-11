---
type: context
status: draft
tags: [architecture, decision, escalation, convergence, slice-5, description-epinglee, cadrage]
issues: [64]
---

# Cadrage architectural — issue #64 « t5 validate » (escalade conv-5, carte `t_ec7bc24c`)

## Positionnement (cadre exact)

L'issue #64 (`labels: decision + kanban`, `idempotency-key gh-issue-64`) est
une **escalade de décision** de la carte **`t_ec7bc24c`** (« t5 validate »,
board `pj-hermes-workflow`, assignée à `pj-master`), bloquée sur le chantier
**#19** (« Discord thread title and description update ») via le ticket
intermédiaire **#22** (« t5 validate », re-import stérile du point conv-5).

C'est une **nouvelle échelle de la chaîne conv-5** déjà documentée par les
notes [[issue-27]], [[issue-29]], [[issue-41]], [[issue-70]], [[issue-81]] :
le point à statuer est toujours le **même** — la convergence de la slice 5 de
#19 (bloc Description épinglé), dont le commit GREEN original `6661362` est
**définitivement perdu** (vérifié 2026-10-11 : `git cat-file -t 6661362` →
fatal, absent de toutes refs locales/remote/reflog/GitHub).

**Particularité de #64 (distincte de #27/#29/#41/#70/#81)** : le corps de
l'issue ne détaille **aucun** motif de blocage (« Motif déclaré : (non
détaillé) ») et ne cite pas de verdict grill-me. Le cadrage ne peut donc que
**décrire l'état mesuré** de la slice 5 sur le worktree partagé, et ne peut
pas reformuler le motif de blocage déclaré — c'est une lecture conservative
(positionne, ne tranche pas).

**Ce que la décision débloque** : le jeton `/ok` sur l'issue #64 (premier
élément) fait déboucler la carte `t_ec7bc24c` et la repart en file. Tout
autre commentaire est une demande d'éclaircissement et ne débloque rien.

**Le présent cadrage ne tranche pas** : il positionne le point à statuer
dans l'architecture existante, identifie les composants impactés, et fixe les
critères de décision. Le re-poussage du GREEN (le commit est perdu, il faut
le re-faire ou le re-écrire) est porté par le dev après le `/ok`, jamais par
ce cadrage.

## Croisement infrastructure / fonctionnel / code

### Infrastructure (frontières traversées)

- **GitHub** — surface de décision (commentaire `/ok` sur l'issue #64,
  `idempotency-key gh-issue-64`) et surface de preuve (commits de la branche,
  PR éventuelle). L'issue #64 est le miroir de la carte `t_ec7bc24c` ; le
  pont de couverture a identifié #64 comme recouvrant #22 (travail en vol) et
  a suspendu l'import en attente de décision humaine (commentaire
  `pj-coverage-gate`).
- **Kanban Hermes** — source de vérité de l'état des cartes : `t_ec7bc24c`
  (t5 validate) en `todo` porte le point à statuer ; le graphe #19
  (t1..t5 + t3b) est déjà construit, les slices 1–4 sont livrées, la slice 5
  est en cours de convergence.
- **Git / worktree partagé** — surface de livraison : le branch head de
  `wt/issue-19-discord-thread-title-description` (worktree `t_c22a7e74`)
  est la **preuve de livraison** de la slice 5. État mesuré (ci-dessous) :
  tip `9fcd207`, GREEN partial présent, banc 7/10 (3 RED).
- **Aucun nouveau port** : les trois surfaces (GitHub, kanban, git)
  existent ; l'issue #64 réutilise la boucle de décision #5
  ([[pj-decision]] : `decision_from_comment` calcule, l'appelant applique).

### Fonctionnel (capacité traversée)

La capacité traversée est **convergence + preuve de livraison** (pas une
fonctionnalité nouvelle). Le chantier #19 (« Discord thread title and
description update ») est déjà cadré par les notes `issue-27`, `issue-29`,
`issue-41`, `issue-70`, `issue-81` (escalades de la même chaîne conv-5) et
la note composant `pj-thread-name` (slices 2–4 livrées). #64 porte :

- **le point de décision** : la slice 5 est-elle convergée ? État mesuré :
  NON — 3 fixes keeper manquent, le helper Discord n'a pas `upsert-desc`/`pin`.
- **la chaîne de livraison** : qui applique les 3 fixes keeper restants et
  ajoute les 2 capacités helper ? (Le dev, après le `/ok`.)
- **le verdict de convergence** : après les fixes, le banc
  `tests/test_thread_description.py` passe-t-il 10/10 GREEN ?

### Code (composants impactés)

| composant | état mesuré (2026-10-11) | impact slice 5 |
|---|---|---|
| `pipeline/engine.py` | `DESCRIPTION_MARKER` + `build_description_lines` présents (L221/L224) | Livré dans le GREEN partial |
| `pipeline/pj_room_keeper.py` | `build_description_for_card` (L572), `sync_description` (L695), `sync_all_descriptions` (L799) présents | **3 tests RED** : (1) `sync_description` appelle `build_description_for_card` SANS `issue_url_lookup` → `issue_url` non résolue → verdict `thread_id=None` ; (2) `_gh_repo()` (L657) perd l'ORG `hyron-fr` (`.rsplit("/", 1)[-1]`) → URL Issue sans ORG ; (3) `sync_all_descriptions` ne transmet pas `issue_url_lookup` à `build_description_for_card` |
| `tests/test_thread_description.py` | 10 cas, 7 GREEN / 3 RED | Banc qui gèle le contrat `contrat-5` |
| `skills/gh-kanban-bridge/scripts/discord_thread.py` | Commandes `create`/`send`/`rename`/`threads` seulement | **`upsert-desc` + `pin` à ajouter** |

Le **core pur** à préserver : `build_description_lines` (composition pure :
issue_url, branch, pr_url → list[str], 0 réseau) et
`build_description_for_card` (sources injectées). L'écriture du message et
de l'épingle passent par l'adapter injecté `write_message` / le helper Discord.

## Lecture SDD (spec-driven)

La spec est le body de l'issue **#19** (arbitrages `Q1=1a`, `Q2=2b`, `Q3=d`) ;
l'issue #64 **est** le point à statuer de sa carte `t_ec7bc24c`. La spec est
la source de vérité : le livrable de #64 n'est pas un code, mais **l'état de
convergence de la slice 5 de #19** : soit les 3 fixes keeper + les 2 capacités
helper sont appliqués et le banc passe 10/10 GREEN, soit l'escalade se
poursuit. La doc décrit le livré : ici le « livré » attendu est le GREEN 10/10
; jusqu'au `/ok`, l'état mesuré est 7/10 GREEN + helper incomplet.

## Lecture DDD (bounded contexts, agrégats, événements)

- **Bounded context traversé** : *convergence / livraison* — chevauche
  *développement* (slice 5 de #19) et *décision humaine* (l'escalade
  #22→#64), sans en être un nouveau : c'est la **jonction** entre les deux.
- **Agrégat racine** : la **carte `t_ec7bc24c`** (invariant : elle ne repart
  en `ready` que sur un `/ok` portant sa ligne canonique
  `carte: pj-hermes-workflow/t_ec7bc24c`). L'**issue #64** est l'objet de
  décision qui la matérialise.
- **Value objects** : le **branch head SHA** (`9fcd207` mesuré) ; le **banc
  7/10** (état de convergence partiel) ; l'**idempotency-key** `gh-issue-64`.
- **Domain events** : `/ok` humain sur l'issue #64 → unblock de
  `t_ec7bc24c` → re-spawn → dev applique les 3 fixes keeper + ajoute
  `upsert-desc`/`pin` → banc 10/10 GREEN → convergence → doc → doc-review →
  PR → merge.

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
  — gestion d'erreur quand `gh pr list` lève (la ligne PR est omise mais
  tracée, pas d'exception).
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
issue #64 (GitHub, labels decision + kanban, idempotency-key gh-issue-64)
  → commentaire /ok humain (surface de décision)
  → unblock de t_ec7bc24c (kanban)
  → re-spawn → dev applique 3 fixes keeper + upsert-desc/pin
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
  - **remote** = `9fcd207` (en sync, `git rev-list --left-right --count HEAD...@{u}` = `0 0`).
  - `git status --short` : `?? docs/architecture/context/issue-27.md`,
    `?? docs/architecture/context/issue-29.md` (notes non commitées, hors
    périmètre de la slice 5).
- `git cat-file -t 6661362` → **fatal : Not a valid object name**
  (définitivement absent de toutes refs).
- `grep DESCRIPTION_MARKER|build_description|sync_description` sur
  `pipeline/` → **présents** dans `pipeline/engine.py` (L221, L224) et
  `pipeline/pj_room_keeper.py` (L572, L695, L799) (GREEN partial livré
  dans l'arbre).
- `grep upsert-desc|pin` sur `skills/gh-kanban-bridge/scripts/discord_thread.py`
  → **0 hit** (capacité non livrée).
- Banc `tests/test_thread_description.py` : **7/10 GREEN, 3 RED** (mesuré
  2026-10-11, rejouable via
  `python3 -m pytest tests/test_thread_description.py -q -p no:randomly`
  dans le venv hermes-agent).
  Les 3 cas rouges :
  - `test_nominal_un_seul_message_epingle_mis_a_jour_pas_duplique`
    → `sync_description` (L725) appelle `build_description_for_card(card, log=log)`
    SANS `issue_url_lookup` → `_issue_url_from_card` ne résout pas l'URL →
    verdict `thread_id=None` au lieu de `TH-19`.
  - `test_erreur_gh_pr_list_en_erreur_ligne_omise_tracee_pas_exception`
    → `_gh_repo()` (L657) fait `.rsplit("/", 1)[-1]` sur `GH_REPO`
    (`hyron-fr/hermes-workflow`) → perd l'ORG `hyron-fr` → URL Issue
    `https://github.com/hermes-workflow/issues/19` au lieu de
    `https://github.com/hyron-fr/hermes-workflow/issues/19`.
  - `test_erreur_le_reader_de_source_qui_leve_ne_tue_pas_le_tick`
    → `sync_all_descriptions` (L824) appelle `build_description_for_card`
    SANS `issue_url_lookup` → `_issue_url_from_card` lève ou ne résout pas →
    le bloc n'est pas écrit (0 écrit au lieu de 1).
- `pj_docs_lint.py` sur `/home/elix/pj-repos/hermes-workflow` → `exit=0`.

## Composants impactés (résumé)

- **Décision (cette issue)** : `pipeline/pj_decision.py` ([[pj-decision]]) +
  `pipeline/pj_escalate.py` / `pipeline/pj_notify.py` ([[pj-notify]]) — la
  boucle #5, aucun changement de code.
- **Travail débloqué (slice 5 de #19, à compléter)** :
  - `pipeline/pj_room_keeper.py` — 3 fixes :
    (1) `sync_description` L725 : transmettre `issue_url_lookup` (et
        `specs_reader`, `pr_reader`) à `build_description_for_card` ;
    (2) `_gh_repo()` L657 : ne pas `.rsplit` (conservation de l'ORG `hyron-fr`)
        ou reconstituer l'URL complète avec l'ORG ;
    (3) `sync_all_descriptions` L824 : transmettre `issue_url_lookup` à
        `build_description_for_card` (comme `sync_description`).
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
3. **Le motif de blocage de la carte `t_ec7bc24c`** — déclaré « (non
   détaillé) » sur l'issue #64 ; le détail est sur la carte elle-même. Le
   cadrage décrit l'état mesuré de la slice 5, ne reformule pas le motif.
4. **La publication live des copies `~/.hermes/scripts/`** (divergence D2
   déclarée dans le handoff `dev-5`) — opération de fin de graphe contrôlée
   par identité, hors périmètre de cette décision.
