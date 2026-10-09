---
type: context
status: draft
tags: [architecture, decision, escalation, convergence, slice-5, description-epinglee, cadrage]
issues: [40]
---

# Cadrage architectural — issue #40 « t3 grill-me » (5ᵉ escalade conv-5)

## Positionnement (cadre exact)

L'issue #40 (`label: decision` + `kanban`, `idempotency-key gh-issue-40`, parent
#27) est une **escalade de décision** de la carte **`t_e59e64e5`**
(« t3 grill-me issue #31 », assignée à `pj-master`, board
`pj-hermes-workflow`), bloquée sur le chantier **#31** (« slice 5/5 —
convergence », lui-même escalade de la carte conv-5 `t_f725879f` du chantier
#19).

C'est la **cinquième escalade conv-5** de la chaîne :

| # | Issue | Carte bloquée | Motif |
|---|---|---|---|
| 1ᵉʳ | #27 | `t_f725879f` (conv-5) | GREEN dev-5 `6661362` perdu, banc 10/10 RED |
| 2ᵉ | #29 | `t_f725879f` (conv-5) | Même point, ré-importé par le pont de couverture |
| 3ᵉ | #45 | `t_854f0f77` (dev GREEN RECYCLE) | GREEN partial présent (7/10), 3 fixes keeper + upsert-desc/pin manquants |
| 4ᵉ | #41 | `t_3f7e0be4` (t3 grill-me) | Quadrante + verdict produits ; Q1 posée à l'humain |
| **5ᵉ** | **#40** | **`t_e59e64e5`** (t3 grill-me #31) | Point à statuer : trancher (A) /ok sur #31 vs (B) re-pousser le GREEN d'abord |

Le **point à statuer** (tel quel, mesuré le 2026-10-09) : la carte `t_e59e64e5`
est bloquée en attente de la réponse humaine — trancher entre :
- **(A)** débloquer conv-5 avec `/ok` sur l'issue #31, ou
- **(B)** re-pousser le code GREEN slice 5 d'abord (recommandé).

L'humain tranchera en commentant sur l'issue GitHub #31
(https://github.com/hyron-fr/hermes-workflow/issues/31).

**Ce que la décision débloque** : le jeton `/ok` sur l'issue #40 (premier
élément) fait déboucler la carte `t_e59e64e5` et la repart en file.
L'effet attendant dépend de la tranchée :
- Si (A) `/ok` sur #31 : la carte `t_e59e64e5` repart en file, le grill-me
  reformule, puis le dev applique les retouches restantes.
- Si (B) re-pousser le GREEN d'abord : le dev repousse le commit GREEN
  (ou son équivalent) sur `wt/issue-19-discord-thread-title-description`,
  le banc passe 10/10, puis la carte repart.

Tout autre commentaire est une demande d'éclaircissement et ne débloque rien.

**Verdict du grill-me** (carte `t_acc83f5a`, commentaire sur l'issue #41) :
`PROTOTYPE: non`, `AMBIGU: aucune`, `ARTEFACT: aucun`. Le périmètre est gelé
par le banc (contrat-5, blackboard racine `t_83401cbb`). L'unique action =
s'assurer que les 10 tests passent et pousser sur
`wt/issue-19-discord-thread-title-description`.

## Croisement infrastructure / fonctionnel / code

### Infrastructure (frontières traversées)

- **GitHub** — surface de décision : commentaire `/ok` sur l'issue #40
  (l'enfant de #27, qui porte la carte `t_e59e64e5`). Adapter : `gh` CLI,
  lu par le pont. La carte `t_e59e64e5` est l'objet de la reprise.
- **Kanban Hermes** — source de vérité de l'état des cartes. L'effet est
  `comment` + `unblock` sur `t_e59e64e5`, invoqués en `subprocess` par le
  câblage de #5 ([[pj-decision]] : `decision_from_comment` calcule,
  l'appelant applique).
- **Git / worktree partagé** — surface de livraison : le branch head de
  `wt/issue-19-discord-thread-title-description` (worktree `t_c22a7e74`)
  est la **preuve de livraison** de la slice 5. État mesuré : tip
  `dbf73da`, GREEN partial présent, banc à rejouer.
- **Aucun nouveau port** : les trois surfaces (GitHub, kanban, git)
  existent ; l'issue #40 réutilise la boucle de décision #5.

### Fonctionnel (capacité traversée)

La capacité traversée est **convergence + preuve de livraison** (pas une
fonctionnalité nouvelle). Le chantier #19 (« Discord thread title and
description update ») est déjà cadré par la note `issue-27` (escalade 1ᵉʳ),
la note `issue-29` (escalade 2ᵉ), la note `issue-41` (escalade 4ᵉ) et la
note composant `pj-thread-name` (slices 2–4 livrées). #40 porte :

- **le point de décision** : trancher entre (A) débloquer avec `/ok` sur
  #31, ou (B) re-pousser le GREEN d'abord.
- **la chaîne de livraison** : qui applique les retouches restantes
  (2 fixes keeper + upsert-desc/pin) et pousse le GREEN sur
  `wt/issue-19-discord-thread-title-description` ?
- **le verdict de convergence** : après les retouches, le banc
  `tests/test_thread_description.py` passe-t-il 10/10 GREEN ?

### Code (composants impactés)

| composant | état mesuré (2026-10-09) | impact slice 5 |
|---|---|---|
| `pipeline/engine.py` | `DESCRIPTION_MARKER` + `build_description_lines` présents | Livré dans le GREEN partial |
| `pipeline/pj_room_keeper.py` | `build_description_for_card`, `sync_description`, `sync_all_descriptions` présents | 2–3 tests RED : fixes de dédup + non-lèvement + journalisation |
| `tests/test_thread_description.py` | 22024 octets, 10 cas, état à rejouer | Banc qui gèle le contrat `contrat-5` |
| `skills/gh-kanban-bridge/scripts/discord_thread.py` | Commandes `create`/`send`/`rename`/`threads` seulement | **`upsert-desc` + `pin` à ajouter** |

Le **core pur** à préserver : `build_description_lines` (composition pure :
issue_url, branch, pr_url → list[str], 0 réseau) et
`build_description_for_card` (sources injectées). L'écriture du message
et de l'épingle passent par l'adapter injecté `write_message` / le helper
Discord.

## Lecture SDD (spec-driven)

La spec est le body de l'issue **#19** (arbitrages `Q1=1a`, `Q2=2b`, `Q3=d`) ;
l'issue #40 **est** le point à statuer de sa carte `t_e59e64e5`. Le verdict du
grill-me (carte `t_acc83f5a`) fixe le périmètre : l'unique action = s'assurer
que les 10 tests passent et pousser sur
`wt/issue-19-discord-thread-title-description`. La doc décrit le livré :
ici le « livré » attendu est le GREEN 10/10 (2–3 fixes keeper + upsert-desc/pin) ;
jusqu'au `/ok`, l'état mesuré est le GREEN partial avec banc à rejouer.

## Lecture DDD (bounded contexts, agrégats, événements)

- **Bounded context traversé** : *convergence / livraison* — chevauche
  *développement* (slice 5 de #19) et *décision humaine* (l'escalade
  #27→#29→#45→#41→#40), sans en être un nouveau : c'est la **jonction**
  entre les deux.
- **Agrégat racine** : la **carte `t_e59e64e5`** (invariant : elle ne repart en
  `ready` que sur un `/ok` portant sa ligne canonique
  `carte: pj-hermes-workflow/t_e59e64e5`). L'**issue #40** est l'objet de
  décision qui la matérialise.
- **Value objects** : le **branch head SHA** (`dbf73da` mesuré) ; le **banc
  10 cas** (état de convergence à rejouer) ; l'**idempotency-key**
  `gh-issue-40` ; le verdict grill-me (`PROTOTYPE: non, AMBIGU: aucune`).
- **Domain events** : `/ok` humain sur l'issue #40 → unblock de
  `t_e59e64e5` → grill-me reformule → tranchée (A) ou (B) → dev applique
  les retouches restantes + pousse le GREEN → banc 10/10 GREEN →
  convergence → doc → doc-review → PR → merge.

## Lecture TDD (contrats testables)

Le contrat testable est le **banc `tests/test_thread_description.py`**
(22024 octets, 10 cas), rejouable sans Discord ni réseau (sources injectées) :

- `build_description_lines(issue_url, branch, pr_url, log=print) -> list[str]`
  — composition pure, 4 lignes, omission des `None`/vides (4 cas).
- `keeper.build_description_for_card(card, *, …, specs_reader, pr_reader,
  issue_url_lookup)` — assemblage des sources injectées (2–3 cas).
- `keeper.sync_description(cards, *, fetch_messages, write_message, log=None)`
  — écrivain best-effort : dédup par marqueur, `edit` jamais second post
  (1–2 cas).
- Les **cas RED restants** sont les critères d'acceptation de la slice 5 ;
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
issue #40 (GitHub, label decision + kanban, parent #27)
  → commentaire /ok humain (surface de décision)
  → unblock de t_e59e64e5 (kanban)
  → tranchée : (A) /ok sur #31 ou (B) re-pousser le GREEN d'abord
  → dev applique les retouches restantes + pousse le GREEN
  → banc test_thread_description.py 10/10 GREEN (preuve de convergence)
  → doc → doc-review → PR → merge
```

Deux frontières : **GitHub ↔ kanban** (décision → effet) et
**git ↔ worktree partagé** (preuve de livraison). Le point de fragilité n'est
pas l'appel réseau mais **la couverture commit-à-commit** : un commit absent
du branch head est un travail non livré, quel que soit le handoff du worker.

## État mesuré (2026-10-09, rejouable)

- `origin/dev` = `2027333` (docs cadrage issue #29).
- `wt/issue-19-discord-thread-title-description` :
  - **local** (worktree `t_c22a7e74`) = `dbf73da` (7 commits au-dessus de
    `49bb284` RED test-5 : `dccf75f` fix keeper bouclage, `55e6659` baseline,
    `03e09f1` cadrage #31, `6a827a0` cadrage #45, `578b7b2` cadrage #41,
    `56e2525` correction écart, `dbf73da` correction écart).
  - **remote** = `dbf73da` (en sync).
  - `git status --short` : `?? diag2.py` (fichier temporaire, pas de fix
    non-commité dans `pipeline/pj_room_keeper.py`).
- `git cat-file -t 6661362` → **fatal : Not a valid object name**
  (définitivement absent du dépôt local et du remote).
- `grep DESCRIPTION_MARKER|build_description|sync_description` sur
  `pipeline/` → **présents** dans `pipeline/engine.py` et
  `pipeline/pj_room_keeper.py` (GREEN partial livré dans l'arbre).
- `grep upsert-desc|pin` sur
  `skills/gh-kanban-bridge/scripts/discord_thread.py` → **0 hit**
  (capacité non livrée).
- Banc `tests/test_thread_description.py` : **22024 octets, 10 cas**,
  état à rejouer via `uv run --with pytest … -m pytest
  tests/test_thread_description.py -v -p no:randomly`.
- Worktree dédié à #40 (`t_a9eb5474`, `wt/t_a9eb5474`) : à `origin/dev`
  (`2027333`), **ne contient pas** le GREEN partial de la slice 5
  (0 occurrence de l'API dans `pipeline/`, banc absent). Le travail de
  convergence se fait sur `t_c22a7e74`.
- `pj_docs_lint.py` sur `/home/elix/pj-repos/hermes-workflow` → `exit=0`.

## Composants impactés (résumé)

- **Décision (cette issue)** : `pipeline/pj_decision.py` ([[pj-decision]]) +
  `pipeline/pj_escalate.py` / `pipeline/pj_notify.py` ([[pj-notify]]) — la
  boucle #5, aucun changement de code.
- **Travail débloqué (slice 5 de #19, à compléter)** :
  - `pipeline/pj_room_keeper.py` — 2–3 fixes : (1) logique de
    déduplication pour qu'un seul message épinglé soit mis à jour
    (pas dupliqué), (2) non-lèvement quand un reader de source lève
    (le tick ne meurt pas), (3) correction de la journalisation de
    `build_description_for_card` (bouclage infini).
  - `skills/gh-kanban-bridge/scripts/discord_thread.py` — ajout des
    capacités `upsert-desc` (édition du message du fil) et `pin`
    (épingle du message).
- **Vault** : à la convergence, la slice 5 gagnera sa note composant et
  le MOC `docs/architecture/README.md` sera mis à jour par la carte
  `doc-k` — hors périmètre de cette décision.

## Non tranché (et qui doit le rester ici)

Le cadrage ne tranche **pas** :
1. **La tranchée (A) vs (B)** — portée par l'humain via `/ok` sur l'issue
   #40 ou commentaire sur #31.
2. **Le contenu exact des 2–3 fixes keeper** — porté par le dev après le
   `/ok` (le banc définit le contrat, pas le cadrage).
3. **La forme des capacités `upsert-desc`/`pin`** — porté par le dev ; le
   banc ne les teste pas directement (le helper est un adapter, injecté).
4. **La publication live des copies `~/.hermes/scripts/`** (divergence D2
   déclarée dans le handoff `dev-5`) — opération de fin de graphe contrôlée
   par identité, hors périmètre de cette décision.

Ces points sont **documentés**, pas décidés ici.
