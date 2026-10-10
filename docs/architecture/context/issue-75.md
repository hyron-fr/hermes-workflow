---
type: context
status: draft
tags: [architecture, decision, escalation, recycle, convergence, slice-5, description-epinglee, cadrage]
issues: [75]
---

# Cadrage architectural — issue #75 « t3 grill-me » (7ᵉ escalade conv-5)

## Positionnement (cadre exact)

L'issue #75 (`label: decision` + `kanban`, `idempotency-key gh-issue-75`,
parent #28) est une **escalade de décision** de la carte **`t_566c200d`**
(board `pj-hermes-workflow`), bloquée sur le chantier **#28** (« slice 5/5 —
convergence », lui-même escalade de la carte conv-5 `t_f725879f` du chantier
#19).

Le **commentaire de grill-me** de l'issue #75 qualifie le point :
`PROTOTYPE: non` / `AMBIGU: cause perte commit 6661362 ; choix action de
débloquage` / `ARTEFACT: aucun`. Le quadruplet de la carte bloquée :
(1) commit GREEN `6661362` introuvable — cause non levable seule (force-push ?
clôture avant push ?) ; (2) l'action de débloquage = **arbitrage humain**
(re-push du commit vs re-génération du GREEN depuis le banc RED test-5) ;
(3) le motif exact du blocage est déjà documenté (conv-5 `t_f725879f` :
GREEN manquant, banc 10/10 RED rejoué, HEAD `49bb284`).

C'est la **septième escalade conv-5** de la chaîne :

| # | Issue | Carte bloquée | Motif (résumé) |
|---|---|---|---|
| 1ᵉʳ | #27 | `t_f725879f` (conv-5) | GREEN dev-5 `6661362` perdu, banc 10/10 RED |
| 2ᵉ | #29 | `t_f725879f` (conv-5) | Même point, ré-importé par le pont de couverture |
| 3ᵉ | #45 | `t_854f0f77` (dev GREEN RECYCLE) | GREEN partial (7/10), fixes + upsert-desc/pin manquants |
| 4ᵉ | #41 | `t_3f7e0be4` (t3 grill-me) | GREEN partial (8/10 → 7/10 corrigé), 2 fixes keeper + helper restants |
| 5ᵉ | #81 | `t_c0e5ce5a` (t3 grill-me) | GREEN partial (7/10), 3 fixes keeper + upsert-desc/pin restants |
| 6ᵉ | #80 | (cadrage) | Point à statuer mesuré (2026-10-10) |
| **7ᵉ** | **#75** | **`t_566c200d`** (grill-me) | **Verdict AMBIGU : cause de perte + choix re-push vs re-générer** |

Le **point à statuer** (tel quel, mesuré le 2026-10-11) :

- Le commit **`6661362`** (GREEN dev-5 original) est **définitivement absent**
  du dépôt local et du remote (`git cat-file -t 6661362` →
  `Not a valid object name`).
- La branche `wt/issue-19-discord-thread-title-description` pointe sur
  **`b846a28`** (worktree partagé `t_c22a7e74`, local **et** remote en sync) :
  4 commits au-dessus de `49bb284` (RED test-5), soit `55e6659`
  (conv-audit baseline) + `6a827a0` / `578b7b2` / `56e2525` / `dbf73da`
  (notes de cadrage #45/#41 + corrections) + `6a2d8e3` (cadrage #26) +
  `b846a28` (cadrage #80). **Aucun commit GREEN de slice 5 ne se trouve sur
  cette branche** : le travail « GREEN partial » n'a jamais été re-poussé.
- Les fonctions de slice 5 **sont présentes dans l'arbre** (héritées de
  `55e6659`) : `DESCRIPTION_MARKER` (L221), `build_description_lines` (L224)
  dans `pipeline/engine.py` ; `build_description_for_card` (L572),
  `sync_description` (L695), `sync_all_descriptions` (L799) dans
  `pipeline/pj_room_keeper.py`. L'arbre est **propre** (`git status --short`
  vide) — le fix non-commité signalé par les notes #41/#81 n'existe plus sous
  cette forme ; l'écart est désormais **commité mais fonctionnellement
  incomplet**.
- Le banc `tests/test_thread_description.py` (387 lignes, 10 cas) est
  **7 GREEN / 3 RED**, mesuré le 2026-10-11 par exécution
  (`uv run --with pytest --with pytest-randomly --with pyyaml --with
  langgraph python -m pytest tests/test_thread_description.py -v -p
  no:randomly` → `3 failed, 7 passed in 0.29s`) :
  - `test_nominal_un_seul_message_epingle_mis_a_jour_pas_duplique` — la
    déduplication par marqueur ne mène pas à un seul message épinglé mis à
    jour ;
  - `test_erreur_gh_pr_list_en_erreur_ligne_omise_tracee_pas_exception` — la
    gestion d'erreur de `gh pr list` qui lève n'est pas en place (ligne omise
    + tracée, pas d'exception) ;
  - `test_erreur_le_reader_de_source_qui_leve_ne_tue_pas_le_tick` — un lecteur
    de source qui lève ne doit pas tuer le tick ; l'assertion `len(ecrits) ==
    1` échoue (0 message écrit).
- La capacité **`upsert-desc` / `pin`** est **absente** du helper
  `skills/gh-kanban-bridge/scripts/discord_thread.py` (grep : 0 hit ;
  commandes présentes : `create`, `send`, `threads`, `rename`).

**Ce que la décision débloque** : le jeton `/ok` sur l'issue #75 (premier
élément) fait déboucler la carte `t_566c200d` et la repart en file.
L'effet attendant : **appliquer les 3 retouches keeper restantes + ajouter
`upsert-desc`/`pin` dans le helper**, puis le banc passe 10/10.
Tout autre commentaire est une demande d'éclaircissement.

**L'ambiguïté qualifiée par le grill-me** (celle que cette escalade porte)
n'est plus le contenu des fixes — les bancs les gèlent — mais le **choix de
la voie de re-livraison** : (A) re-pousser un commit GREEN reconstruit à
l'identique du `6661362` perdu, ou (B) re-générer le GREEN depuis le banc RED
test-5 (`49bb284`), en partant de l'arbre actuel qui porte déjà le GREEN
partial commité. La cause de la perte de `6661362` reste non levable seule
(force-push ? clôture avant push ?) — documentée, pas tranchée ici.

## Croisement infrastructure / fonctionnel / code

### Infrastructure (frontières traversées)

- **GitHub** — surface de décision : commentaire `/ok` sur l'issue #75
  (l'enfant de #28). Adapter : `gh` CLI, lu par le pont. La carte
  `t_566c200d` est l'objet de la reprise.
- **Kanban Hermes** — source de vérité de l'état des cartes. L'effet est
  `comment` + `unblock` sur `t_566c200d`, invoqués en `subprocess` par le
  câblage de #5 ([[pj-decision]] : `decision_from_comment` calcule,
  l'appelant applique).
- **Git / worktree partagé** — surface de livraison : le branch head de
  `wt/issue-19-discord-thread-title-description` (worktree `t_c22a7e74`)
  est la **preuve de livraison** de la slice 5. État mesuré : tip `b846a28`,
  GREEN partial commité, 3 tests rouges, helper incomplet.
- **Aucun nouveau port** : les trois surfaces (GitHub, kanban, git)
  existent ; l'issue #75 réutilise la boucle de décision #5.

### Fonctionnel (capacité traversée)

La capacité traversée est **convergence + preuve de livraison** (pas une
fonctionnalité nouvelle). Le chantier #19 (« Discord thread title and
description update ») est déjà cadré par la note `issue-27` (escalade 1ᵉʳ),
la note `issue-29` (escalade 2ᵉ), la note `issue-41` (escalade 4ᵉ), la note
`issue-81` (escalade 5ᵉ) et la note composant `pj-thread-name` (slices 2–4
livrées). #75 porte :

- **le point de décision** : la voie de re-livraison (re-push reconstruit
  vs re-génération depuis le banc RED) — verdict grill-me : AMBIGU, arbitrage
  humain requis ;
- **la chaîne de livraison** : qui applique les 3 retouches keeper restantes
  et ajoute `upsert-desc`/`pin` dans le helper ? (Le dev, après le `/ok`.)
- **le verdict de convergence** : après les retouches, le banc
  `tests/test_thread_description.py` passe-t-il 10/10 GREEN ?

### Code (composants impactés)

| composant | état mesuré (2026-10-11) | impact slice 5 |
|---|---|---|
| `pipeline/engine.py` | `DESCRIPTION_MARKER` (L221) + `build_description_lines` (L224) présents | Livré dans le GREEN partial commité |
| `pipeline/pj_room_keeper.py` | `build_description_for_card` (L572), `sync_description` (L695), `sync_all_descriptions` (L799) présents ; arbre propre | 3 tests RED : dédup par marqueur (un seul message épinglé mis à jour, pas dupliqué), non-lèvement quand un reader lève, gestion d'erreur `gh pr list` |
| `tests/test_thread_description.py` | 387 lignes, 10 cas, 7 GREEN / 3 RED | Banc qui gèle le contrat `contrat-5` |
| `skills/gh-kanban-bridge/scripts/discord_thread.py` | Commandes `create`/`send`/`threads`/`rename` seulement | **`upsert-desc` + `pin` à ajouter** |

Le **core pur** à préserver : `build_description_lines` (composition pure :
issue_url, branch, pr_url → list[str], 0 réseau) et
`build_description_for_card` (sources injectées). L'écriture du message et
de l'épingle passent par l'adapter injecté `write_message` / le helper Discord.

## Lecture SDD (spec-driven)

La spec est le body de l'issue **#19** (arbitrages `Q1=1a`, `Q2=2b`, `Q3=d`) ;
l'issue #75 **est** le point à statuer de sa carte `t_566c200d`. Le verdict du
grill-me (commentaire sur l'issue #75) fixe le périmètre :
`PROTOTYPE: non`, `AMBIGU: cause perte commit 6661362 ; choix action de
débloquage`, `ARTEFACT: aucun`. L'unique action = s'assurer que les 10 tests
passent et pousser sur `wt/issue-19-discord-thread-title-description`.
La doc décrit le livré : ici le « livré » attendu est le GREEN 10/10
(3 retouches keeper + upsert-desc/pin) ; jusqu'au `/ok`, l'état mesuré est
7/10 GREEN + helper incomplet + commit GREEN original perdu.

## Lecture DDD (bounded contexts, agrégats, événements)

- **Bounded context traversé** : *convergence / livraison* — chevauche
  *développement* (slice 5 de #19) et *décision humaine* (l'escalade
  #27→#29→#45→#41→#81→#80→#75), sans en être un nouveau : c'est la
  **jonction** entre les deux.
- **Agrégat racine** : la **carte `t_566c200d`** (invariant : elle ne repart
  en `ready` que sur un `/ok` portant sa ligne canonique
  `carte: pj-hermes-workflow/t_566c200d`). L'**issue #75** est l'objet de
  décision qui la matérialise.
- **Value objects** : le **branch head SHA** (`b846a28` mesuré) ; le **banc
  7/10** (état de convergence partiel) ; l'**idempotency-key** `gh-issue-75` ;
  le verdict grill-me (`PROTOTYPE: non, AMBIGU: cause perte + choix voie,
  ARTEFACT: aucun`).
- **Domain events** : `/ok` humain sur l'issue #75 → unblock de
  `t_566c200d` → re-spawn (grill-me reformule) → dev applique les 3 retouches
  keeper + ajoute `upsert-desc`/`pin` → banc 10/10 GREEN → convergence →
  doc → doc-review → PR → merge.

## Lecture TDD (contrats testables)

Le contrat testable est le **banc `tests/test_thread_description.py`**
(387 lignes, 10 cas), rejouable sans Discord ni réseau (sources injectées) :

- `build_description_lines(issue_url, branch, pr_url, log=print) -> list[str]`
  — composition pure, 4 lignes, omission des `None`/vides (4 cas GREEN).
- `keeper.build_description_for_card(card, *, …, specs_reader, pr_reader,
  issue_url_lookup)` — assemblage des sources injectées (cas GREEN).
- `keeper.sync_description(cards, *, fetch_messages, write_message, log=None)`
  — écrivain best-effort : dédup par marqueur, `edit` jamais second post
  (1 cas RED : un seul message épinglé mis à jour, pas dupliqué).
- `keeper.sync_all_descriptions(cards, *, …, specs_reader, pr_reader,
  issue_url_lookup)` — câblage best-effort, **ne lève jamais** (2 cas RED :
  le reader de source qui lève ne tue pas le tick ; la gestion d'erreur de
  `gh pr list` qui lève).
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
issue #75 (GitHub, label decision + kanban, parent #28)
  → commentaire /ok humain (surface de décision)
  → unblock de t_566c200d (kanban)
  → re-spawn grill-me → reformulation → dev applique 3 retouches keeper + upsert-desc/pin
  → banc test_thread_description.py 10/10 GREEN (preuve de convergence)
  → doc → doc-review → PR → merge
```

Deux frontières : **GitHub ↔ kanban** (décision → effet) et
**git ↔ worktree partagé** (preuve de livraison). Le point de fragilité n'est
pas l'appel réseau mais **la couverture commit-à-commit** : un travail
commité mais functionnellement incomplet (7/10) n'est pas un travail livré.

## État mesuré (2026-10-11, rejouable)

- `origin/dev` = `2027333` (cadrage #29 slice 5/5).
- `wt/issue-19-discord-thread-title-description` :
  - **local** (worktree `t_c22a7e74`) = `b846a28` (4 commits au-dessus de
    `49bb284` RED test-5 : `55e6659` conv-audit baseline, `6a827a0`
    cadrage #45, `578b7b2` + `56e2525` + `dbf73da` cadrage #41 +
    corrections, `6a2d8e3` cadrage #26, `b846a28` cadrage #80).
  - **remote** = `b846a28` (en sync).
  - `git status --short` : **propre** (fix non-commité des notes #41/#81
    désormais commité).
- `git cat-file -t 6661362` → **fatal : Not a valid object name**
  (définitivement absent).
- `grep DESCRIPTION_MARKER|build_description|sync_description` sur
  `pipeline/` → **présents** (GREEN partial commité dans l'arbre).
- `grep upsert-desc|pin` sur `skills/gh-kanban-bridge/scripts/discord_thread.py`
  → **0 hit** (capacité non livrée).
- Banc `tests/test_thread_description.py` : **7 GREEN / 3 RED** (mesuré
  2026-10-11 par exécution, rejouable via `uv run --with pytest --with
  pytest-randomly --with pyyaml --with langgraph python -m pytest
  tests/test_thread_description.py -v -p no:randomly`).
- `gh pr list --head wt/issue-19-discord-thread-title-description --state all`
  → seul PR `#39` (draft, CLOSED, vecteur de preuve jetable).
- `pj_docs_lint.py` sur `/home/elix/pj-repos/hermes-workflow` → `exit=0`.

## Composants impactés (résumé)

- **Décision (cette issue)** : `pipeline/pj_decision.py` ([[pj-decision]]) +
  `pipeline/pj_escalate.py` / `pipeline/pj_notify.py` ([[pj-notify]]) — la
  boucle #5, aucun changement de code.
- **Travail débloqué (slice 5 de #19, à compléter)** :
  - `pipeline/pj_room_keeper.py` — 3 retouches : (1) déduplication par
    marqueur pour qu'un seul message épinglé soit mis à jour (pas dupliqué),
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
1. **La voie de re-livraison** (re-push du commit `6661362` reconstruit à
   l'identique, ou re-génération du GREEN depuis le banc RED test-5 en
   partant de l'arbre actuel) — verdict grill-me : AMBIGU, arbitrage humain
   requis ; le banc gèle le contrat, pas la voie.
2. **La cause de la perte de `6661362`** (force-push ? clôture avant push ?)
   — non levable seule, documentée, pas tranchée ici.
3. **Le contenu exact des 3 retouches keeper** — porté par le dev après le
   `/ok` (le banc définit le contrat, pas le cadrage).
4. **La forme des capacités `upsert-desc`/`pin`** — porté par le dev ; le
   banc ne les teste pas directement (le helper est un adapter, injecté).
5. **La publication live des copies `~/.hermes/scripts/`** (divergence D2
   déclarée dans le handoff `dev-5`) — opération de fin de graphe contrôlée
   par identité, hors périmètre de cette décision.

Ces points sont **documentés**, pas décidés ici.
