---
type: context
status: draft
tags: [architecture, convergence, decision, escalation, discord, delivery-proof, cadrage, slice-5, description-epinglee]
issues: [26]
---

# Cadrage architectural — issue #26 « slice 5/5 — convergence »

## Positionnement (cadre exact)

L'issue #26 **n'est pas une tâche de développement** : c'est une **issue de
décision** (labels `decision` + `kanban`, parent #19), escaladée par
`pipeline/pj_escalate.py` depuis la carte **`t_f725879f`** (« slice 5/5 —
convergence », assignée à `pj-test`, board `pj-hermes-workflow`), bloquée sur
le chantier **#19** (« Discord thread title and description update »). Elle
matérialise la boucle de décision livrée par l'issue #5
([[pj-decision]], [[pj-notify]] : issue enfant par carte bloquée, décision =
commentaire GitHub dont le premier élément est `/ok`, l'enfant est l'objet de
décision, Discord ne notifie pas).

#26 est le **premier miroir GitHub** de ce point à statuer conv-5. Les
escalades suivantes de la même carte `t_f725879f` ont produit #27, #29, #31,
#41 et #45 — même motif, même carte, re-imports par le pont de couverture
(`gh-issue-26`, `gh-issue-27`, …). Les cadrages de ces escalades vivent dans
le dépôt principal (`docs/architecture/context/issue-27.md`, `issue-29.md`,
`issue-41.md`) et ne sont pas encore dans le worktree partagé. Le **point à
statuer** (tel quel, mesuré au 2026-10-03) :

> Motif déclaré : GREEN dev-5 (commit `6661362`) absent du worktree partagé :
> branch head = `49bb284` (RED test-5), 0 occurrence de l'API slice 5 dans
> `pipeline/bridge/skills`, banc 10/10 RED rejoué. Impossible de juger la
> convergence sans le code ; à re-pousser par dev-5/dispatcher.

Le **cadre exact** est celui du cadrage parent [[issue-19]] (slice 5
`description-epinglee`, arbitrage humain **Q2 = 2b**) : le fil Discord d'une
issue porte un **message Description dédié ÉPINGLÉ** (jamais le champ `topic` —
mesuré : `PATCH {"topic": …}` rend 200 puis `topic = None`, jeté en silence),
dont les lignes se résolvent depuis des sources **injectées** (issue_url,
branch, pr_url) et se **taissent proprement** quand la valeur n'existe pas —
une ligne non résolue est omise, jamais remplacée par un placeholder.

**Ce que la décision débloque** : le jeton `/ok` en premier élément du
commentaire GitHub sur cette issue fait débloquer la carte `t_f725879f` et la
repart en file (effet porté par le câblage [[pj-decision]] : `decision_from_comment`
calcule, l'appelant applique). L'effet **attendant** qui suit, hors périmètre
de cette issue : la re-livraison du GREEN de la slice 5 (le commit `6661362`
est perdu — voir état mesuré), portée par **dev-5/dispatcher**, jamais par ce
cadrage. Tout autre commentaire est une demande d'éclaircissement et ne
débloque rien.

Le présent cadrage **ne tranche pas** : il positionne le point à statuer dans
l'architecture existante, identifie les composants impactés, et fixe les
critères de décision. Il décrit l'état du **livré partiel** mesuré
aujourd'hui (2026-10-10) — jamais une intention.

## Croisement infrastructure / fonctionnel / code

### Infrastructure (frontières traversées)

- **GitHub** — surface de décision (commentaire `/ok` sur l'issue #26,
  `idempotency-key gh-issue-26`) et surface de preuve (commits de la branche,
  PR). Adapter : `gh` CLI, lu par le pont `bridge/gh_kanban_bridge.py`
  (fonctions `push`, `coverage_context`, `issue_number_of`).
- **Kanban Hermes** — source de vérité du plan. Effet de la décision :
  `unblock` de `t_f725879f` (board `pj-hermes-workflow`), invoqué en
  `subprocess` par le câblage de #5 ([[pj-decision]]).
- **Discord** — le but du travail débloqué : le thread du ticket #19.
  Adapter : `skills/gh-kanban-bridge/scripts/discord_thread.py` (aujourd'hui :
  `bot_token`, `api`, `go_nogo_components`, `main` — les capacités `pin` et
  `edit/upsert` de message sont **annoncées par le contrat mais absentes** du
  helper ; le keeper les appelle via `subprocess` `_discord_pin`).
- **Aucun nouveau port** : les trois surfaces existent déjà ; l'issue #26
  réutilise la boucle de décision #5 et n'en ajoute aucune.

### Fonctionnel (capacité traversée)

- **Capacité** : « bloc Description épinglé du thread Discord » (moitié
  description du chantier #19, slice 5 `description-epinglee`).
- **Règle de produit (arbitrage 2b, gélée par le banc)** :
  1. Un fil ne porte qu'**UN** bloc Description, identifiable par le marqueur
     `[description]` (première ligne) ; un second cycle **met à jour** le
     message existant (édition par `edit_id`), n'en crée jamais un second ;
  2. Les lignes `**Issue**` / `**Branche**` / `**PR**` sont omises si leur
     source ne se résout pas — **jamais de placeholder, jamais de valeur
     inventée** ;
  3. L'**Issue** est l'ancre : c'est la seule ligne qui peut rester seule ;
  4. L'absence d'une source est **journalisée bruyamment** (jamais muette) ;
  5. L'écriture est **best-effort** : un échec de lecture de source ne tue
     jamais le tick du keeper.
- **Glossaire** : `marqueur [description]` (dédup), `verdict par carte`
  (`{card_id, thread_id, action: post|edit, ok, pinned}`), `ancre d'import`
  (l'URL `…/issues/N` du body de la carte).

### Code (où l'évolution s'implante)

| composant | rôle | état mesuré 2026-10-10 |
|---|---|---|
| `pipeline/engine.py` — `DESCRIPTION_MARKER` + `build_description_lines(issue_url, branch, pr_url, log=print)` | **core pur** de la slice 5 : composition du bloc (0 réseau, 0 horloge) | **LIVRÉ** (commit `55e6659`, baseline GREEN partial) |
| `pipeline/pj_room_keeper.py` — `build_description_for_card`, `sync_description`, `sync_all_descriptions`, `_discord_pin` | porteur de l'écriture (seul sait lire l'état du board **et** le plan de slices) ; écrivain unique (arbitrage 2b) | **PARTIELLEMENT LIVRÉ** : fonctions présentes (commits `55e6659`/`dccf75f`) mais **3/10 bancs échouent** (voir état mesuré) ; `git status` porte 1 fichier modifié non commité (`M pipeline/pj_room_keeper.py`) + 1 fichier non versionné (`diag2.py`) |
| `tests/test_thread_description.py` (387 lignes, 10 cas) | banc RED gélant le contrat `contrat-5` (publié sur le blackboard) ; sources et adaptateurs **injectés** (0 réseau) | **LIVRÉ** (RED `26bad5d` + `49bb284`) — rejouable, 7/10 GREEN mesuré 2026-10-10 |
| `skills/gh-kanban-bridge/scripts/discord_thread.py` | helper Discord (adapter REST) ; la slice 5 doit y ajouter les capacités `upsert-desc` (édition) et `pin` (épingle) | **NON LIVRÉ** : 0 occurrence de `pin`/`upsert` dans le helper |
| `pipeline/engine.py` — titre (slices 2–4) | formateur pur du titre, 4 états, 3 lecteurs du nom | LIVRÉ ([[pj-thread-name]]) — hors périmètre slice 5 |
| `bridge/` + `agents/pj-master/scripts/` — miroirs du keeper | copies du keeper (divergence connue, hors périmètre) | non impactés ici |

Frontières du code : **le formateur pur** (`engine.build_description_lines`)
reçoit ses trois valeurs **injectées** ; **les lecteurs de sources**
(`specs_reader`, `pr_reader`, `issue_url_lookup`, `thread_lookup`) sont des
injections testables ; **l'écriture** (post/édit/épinglage du message
Discord) passe par `write_message` injecté en test et par le helper
`discord_thread.py` en production. Le keeper **n'est pas le core pur** : il
assemble état du board + plan de slices + écriture — c'est le port
d'infrastructure de la slice 5.

## Lecture SDD (spec-driven)

La spec de #26 est le **point à statuer** (corps de l'issue) : le commit GREEN
dev-5 `6661362` est absent du worktree partagé, le banc rejoué 10/10 RED. Le
livrable de #26 n'est **pas** un code, mais **l'état de convergence de la
slice 5 de #19** : soit le code est repoussé et le banc passe GREEN, soit
l'escalade se poursuit (c'est ce qu'a fait le pipeline depuis : re-GREEN
partiel + nouvelles escalades #27/#29/#31/#41/#45). La doc décrit ce qui
existe aujourd'hui (banc, GREEN partial, worktree de re-push) — pas une
intention.

## Lecture DDD (bounded contexts, agrégats, événements)

- **Bounded context** : *convergence / livraison* — jonction entre
  *développement* (slice 5 de #19) et *décision humaine* (l'escalade), sans
  en être un nouveau.
- **Agrégat racine** : la **carte `t_f725879f` (conv-5)** — invariant : elle
  ne repart en `ready` que sur un `/ok` humain (commentaire GitHub dont le
  premier élément est `/ok`). L'**issue #26** est l'objet de décision qui la
  matérialise.
- **Entités** : la carte conv-5 (identifiée par `task_id` + board), la slice 5
  (identifiée par son banc + son commit attendu).
- **Value objects** : le **branch head SHA** (`49bb284` mesuré le 2026-10-03,
  `6661362` attendu puis perdu) ; le **marqueur `[description]`** ;
  l'**idempotency-key** `gh-issue-26` ; le verdict par carte
  (`{card_id, thread_id, action, ok, pinned}`) — immuable, comparable, sans
  identité propre.
- **Domain events** : `/ok` humain sur l'issue #26 → `unblock` de
  `t_f725879f` → re-livraison du GREEN slice 5 par dev-5/dispatcher sur
  `wt/issue-19-discord-thread-title-description` → convergence GREEN (banc
  10/10) → doc → doc-review → PR (t6) → merge.

## Lecture TDD (contrats testables)

Le contrat testable de #26 n'est pas un code, mais **un invariant mesurable** :

- **Le branch head de `wt/issue-19-discord-thread-title-description` contient
  le GREEN de la slice 5** (le commit `6661362` ou son équivalent) —
  vérifiable par `git cat-file -t 6661362` et par `git log --oneline` de la
  branche.
- **Le banc `tests/test_thread_description.py` passe GREEN — 10/10** : rejouable
  sans Discord ni réseau (`uv run --with pytest --with pyyaml --with
  langgraph --with openai python -m pytest tests/test_thread_description.py
  -p no:randomly`), sources et adaptateurs injectés.
- **Les 10 cas du banc sont les critères d'acceptation de la slice 5** ; leur
  état RED/GREEN est la preuve de convergence.
- **Le keeper ne lève jamais** : `sync_description` / `sync_all_descriptions`
  capturent chaque échec de lecture de source et journalisent (cas `test_erreur_…`).

Ces invariants sont mesurables par `pj_graphwatch` (couverture
commit-à-commit + chemin réel du worktree, cf. commits `009f0a7`, `9e49771`,
`318bea1`) et par le pont de couverture (`pj_coverage_gate`), qui a identifié
#26 comme recouvrant #19 et les escalades en vol.

## Lecture hexagonale (le core reste pur)

- **Core pur** : `engine.build_description_lines(issue_url, branch, pr_url,
  log=print) -> list[str]` — composition 0 réseau, 0 horloge, 0 aléa, testable
  directement. Il contient le marqueur `DESCRIPTION_MARKER = "[description]"`.
- **Port d'infrastructure** : `pipeline/pj_room_keeper.py` — assemble l'état
  du board, le plan de slices et l'écriture Discord ; il **n'est pas pur** et
  ne doit pas rester pur : ses lecteurs (`specs_reader`, `pr_reader`,
  `issue_url_lookup`, `thread_lookup`) et son écriture (`fetch_messages`,
  `write_message`) sont injectables, ce qui rend le banc rejouable hors ligne.
- **Adapter** : `skills/gh-kanban-bridge/scripts/discord_thread.py` — REST
  Discord (post/édit/épinglage), appelé par le keeper via `subprocess`
  (`_discord_pin`), jamais par le core.
- **Frontière à respecter** : la description est une **lecture d'état**
  (gh / git / slices.json) résolue **hors** du core, puis **injectée** dans le
  formateur pur. Jamais l'inverse : le formateur ne lit pas le réseau.

## Composants impactés par l'issue #26

| composant | impact | slice #19 |
|---|---|---|
| `tests/test_thread_description.py` | banc gélant le contrat `contrat-5` (livré, RED `26bad5d` + `49bb284`) ; 7/10 GREEN mesuré 2026-10-10 | 5 |
| `pipeline/engine.py` (`DESCRIPTION_MARKER`, `build_description_lines`) | core pur du bloc (livré dans le GREEN partial `55e6659`) | 5 |
| `pipeline/pj_room_keeper.py` (+ miroirs `bridge/`, `agents/pj-master/scripts/`) | porteur de l'écriture (**partiellement livré** — 3 cas du banc échouent, 1 fichier modifié non commité) | 5 |
| `skills/gh-kanban-bridge/scripts/discord_thread.py` | capacités `upsert-desc` / `pin` à ajouter (**non livré**) | 5 |
| `pipeline/pj_decision.py` + `pipeline/pj_escalate.py` + `pipeline/pj_notify.py` | boucle de décision de #5 (rien ne change ici ; [[pj-decision]], [[pj-escalate]], [[pj-notify]]) | — |
| `bridge/gh_kanban_bridge.py` | pont de couverture qui a importé #26 et qui identifie le recouvrement de #19 (rien ne change ici) | — |

## État mesuré (2026-10-10, rejouable)

Mesures faites dans le worktree partagé
`/home/elix/pj-repos/hermes-workflow/.worktrees/t_c22a7e74` (branche
`wt/issue-19-discord-thread-title-description`), le 2026-10-10 :

- `git cat-file -t 6661362` → **fatal : Not a valid object name** (le GREEN
  dev-5 original est définitivement absent de tous les refs).
- Branch head local = **`dbf73da`** (docs #41 ; 9 commits au-dessus de
  `49bb284` RED test-5, dont `55e6659` baseline « GREEN partial » et
  `dccf75f` fix keeper bouclage). **Le point à statuer du 2026-10-03 a donc
  évolué** : le branch head n'est plus `49bb284`.
- API slice 5 **présente** dans `pipeline/pj_room_keeper.py`
  (`build_description_for_card` L572, `sync_description` L715,
  `sync_all_descriptions` L829, `_discord_pin` L801) et dans
  `pipeline/engine.py` (`DESCRIPTION_MARKER` L221,
  `build_description_lines` L224) — le constat « 0 occurrence » du motif
  d'escalade est **désouté**.
- Capacités `pin`/`upsert-desc` du helper
  `skills/gh-kanban-bridge/scripts/discord_thread.py` : **0 occurrence**
  (le helper ne porte que `bot_token`, `api`, `go_nogo_components`, `main`).
- `git status --short` : `M pipeline/pj_room_keeper.py` (43 insertions /
  13 suppressions non commitées) + `?? diag2.py` (fichier de diagnostic
  non versionné).
- Banc `tests/test_thread_description.py` rejoué
  (`uv run --with pytest --with pyyaml --with langgraph --with openai
  python -m pytest tests/test_thread_description.py -p no:randomly` dans le
  worktree t_c22a7e74) : **7 passed, 3 failed** :
  1. `test_nominal_un_seul_message_epingle_mis_a_jour_pas_duplique` — le cycle
     « édition du bloc existant » ne passe pas (le test attend `action ==
     "edit"` au second cycle ; le verdict ne porte pas l'attente du banc) ;
  2. `test_erreur_gh_pr_list_en_erreur_ligne_omise_tracee_pas_exception` —
     l'échec de `pr_reader` (RuntimeTime « gh introuvable ») n'est **pas
     journalisé** dans `out["log"]` (le banc exige « gh » dans le log) ;
  3. `test_erreur_le_reader_de_source_qui_leve_ne_tue_pas_le_tick` —
     `sync_all_descriptions` ne capte pas le `raise` de `specs_reader` :
     le bloc n'est pas écrit (`ecrits == []`), le tick lève au lieu de
     continuer (le banc attend 1 écriture).
- `python3 ~/.hermes/scripts/pj_docs_lint.py /home/elix/pj-repos/hermes-workflow`
  → `exit=0`.

**Lecture de cet état** : le point à statuer du motif d'escalade (« GREEN
absent, banc 10/10 RED, à re-pousser par dev-5/dispatcher ») est **obsolète
pour sa partie « 0 occurrence / 10 RED »**. La slice 5 est **partiellement
livrée** dans l'arbre (GREEN partial mesuré à 7/10, 3 retouches nommées dans
le banc), mais la convergence n'est **pas** atteinte : 3 cas du banc échouent
et les capacités `pin`/`upsert-desc` du helper Discord sont absentes.

## Non tranché (et qui doit le rester ici)

Le cadrage ne tranche **pas** :

1. **Le contenu exact des 3 retouches keeper** (édition du bloc existant,
   journalisation de l'échec de `pr_reader`, capture du `raise` de
   `specs_reader` dans `sync_all_descriptions`) — porté par le dev après le
   `/ok` ; le banc définit le contrat, pas le cadrage.
2. **La forme des capacités `upsert-desc`/`pin` du helper**
   `discord_thread.py` — porté par le dev ; le banc ne teste pas le helper
   directement (c'est un adapter, injecté).
3. **Le re-poussage du GREEN** (nouveau commit sur
   `wt/issue-19-discord-thread-title-description` incluant les 3 retouches +
   le commit du helper) — porté par dev-5/dispatcher, **jamais** par ce
   cadrage.
4. **Le verdict de convergence** (10/10 GREEN) — porté par `pj-test` sur la
   carte `t_f725879f`, pas par ce cadrage.

Ces points sont **documentés**, pas décidés ici.

## Frontières traversées (résumé)

```
issue #26 (GitHub, label decision + kanban, parent #19)
  → commentaire /ok humain (surface de décision)
  → unblock de t_f725879f (kanban)
  → re-livraison du GREEN slice 5 sur wt/issue-19-discord-thread-title-description (git)
  → banc test_thread_description.py 10/10 GREEN (preuve de livraison)
  → convergence GREEN → doc → doc-review → PR (t6) → merge
```

Deux frontières : **GitHub ↔ kanban** (décision → effet) et
**git ↔ worktree partagé** (preuve de livraison). Le point de fragilité n'est
pas l'appel réseau mais **la couverture commit-à-commit** : un commit absent
du branch head est un travail non livré, quel que soit le handoff du worker.

## Hors-scope

- **Le re-poussage du GREEN** : porté par `dev-5`/`dispatcher` sur le
  worktree partagé t_c22a7e74 (branche
  `wt/issue-19-discord-thread-title-description`), **jamais** par ce
  cadrage.
- **La convergence effective de la slice 5** (verdict 10/10 GREEN) : portée
  par la carte `t_f725879f` après le `/ok` humain.
- **Les slices 1–4 de #19** : déjà livrées, cadrées par la note [[issue-19]]
  et la note composant [[pj-thread-name]] (slice 4).
- **La duplication bridge↔pipeline↔agents des `pj_*.py`** : divergence connue,
  non traitée par #26.
- **Les escalades suivantes de la même carte** (#27, #29, #31, #41, #45) :
  chacune a son propre cadrage ; #26 est le premier miroir et le présent
  cadrage en tient compte (état mesuré au 2026-10-10, après les GREEN
  partiels de `55e6659` et `dccf75f`).
