---
type: context
status: draft
tags: [architecture, decision, escalation, mirror, conv-5, convergence, slice-5, description-epinglee, cadrage]
issues: [52]
---

# Cadrage architectural — issue #52 « t3 grill-me » (miroir du point à statuer #42)

## Positionnement (cadre exact)

L'issue #52 (`labels: decision + kanban`, `idempotency-key gh-issue-52`,
parent #42) est le **miroir GitHub de la carte `t_6eaf5341`** (board
`pj-hermes-workflow`, assignée `pj-master`) : le corps de l'issue n'est que le
« point à statuer » de cette carte, bloquée sur le ticket **#42** (conv-5,
issue #19 slice 5/5 « Description épinglée », commit GREEN `6661362` perdu).

C'est le **re-import stérile du même point de décision** que la chaîne conv-5
déjà documentée par les notes [[issue-27]], [[issue-29]], [[issue-41]],
[[issue-64]], [[issue-70]], [[issue-81]] : le point à statuer est toujours le
**même** — la convergence de la slice 5 de #19, dont le commit GREEN original
`6661362` est définitivement absent.

**Particularité de #52 (distincte de la chaîne)** : contrairement aux
miroirs #27/#29 (escalade de `t_f725879f`), #41/#81 (grill-me de #43) ou
#64/#70 (miroirs de cartes `t5`/`t3b`), le point à statuer de #52 ne se
tranche **pas** sur l'issue #52 elle-même : la carte `t_6eaf5341` attend le
jeton `/ok` sur l'issue **#42** (le porteur du point), qui débloque
`t_566c200d` (t3 grill-me de #28) et ré-ouvre la chaîne RECYCLE
(`t_f1aa13e4` → `t_854f0f77`). Un `/ok` posé sur #52 ne débloque rien :
l'anti-doublon est la convention de la doctrine (`ticket porteur = #42/#45`,
pas le miroir). #52 est donc un **miroir stérile** : son graphe de slice est
un no-op, sa seule valeur est de pointer vers le porteur.

**Ce que la décision débloque** : le jeton `/ok` sur l'issue **#42** (pas #52)
fait déboucler la carte `t_566c200d` et ré-ouvre le re-GREEN de la slice 5.
Tout autre commentaire est une demande d'éclaircissement.

**Le présent cadrage ne tranche pas** : il positionne le point à statuer dans
l'architecture existante, identifie les composants impactés, et fixe les
critères de décision. Le re-poussage du GREEN (le commit est perdu, il faut
le re-faire depuis le banc) est porté par le dev après le `/ok`, jamais par
ce cadrage.

## Croisement infrastructure / fonctionnel / code

### Infrastructure (frontières traversées)

- **GitHub** — surface de décision : commentaire `/ok` sur l'issue **#42**
  (le porteur), lu par le pont `gh`/coverage-gate. L'issue #52 est la surface
  miroir : y commenter `/ok` serait un no-op (anti-doublon). Adapter : `gh`
  CLI, lu par le pont. La carte `t_6eaf5341` est l'objet de la reprise.
- **Kanban Hermes** — source de vérité de l'état des cartes. L'effet est
  `comment` + `unblock` sur `t_566c200d` (via #42), invoqués en `subprocess`
  par le câblage de #5 ([[pj-decision]] : `decision_from_comment` calcule,
  l'appelant applique ; [[pj-notify]] : l'enfant notifiée puis fermée, le
  parent notifié jamais fermé).
- **Git / worktree partagé** — surface de livraison : le branch head de
  `wt/issue-19-discord-thread-title-description` (worktree partagé
  `t_c22a7e74`) est la **preuve de livraison** de la slice 5. État mesuré
  (2026-10-11, rejouable) : tip `95d4db0`, GREEN partial commité,
  `M pipeline/pj_room_keeper.py` non-commité dans l'arbre.
- **Aucun nouveau port** : les trois surfaces (GitHub, kanban, git)
  existent ; l'issue #52 réutilise la boucle de décision #5.

### Fonctionnel (capacité traversée)

La capacité traversée est **convergence + preuve de livraison** (pas une
fonctionnalité nouvelle). Le chantier #19 (« Discord thread title and
description update ») est déjà cadré par les notes [[issue-27]] (escalade
1ᵉʳ), [[issue-29]] (escalade 2ᵉ), [[issue-41]] (escalade 4ᵉ), [[issue-81]]
(escalade 5ᵉ) et la note composant `pj-thread-name` (slices 2–4 livrées).
#52 porte :

- **le point de décision** : le GREEN partial est-il suffisant pour
  considérer la slice 5 comme convergée ? (Verdict mesuré : non — 3 cas du
  banc restent rouges avant le dernier fix non-commité, et les capacités
  helper `upsert-desc`/`pin` sont absentes.)
- **la chaîne de livraison** : qui ré-ouvre le RECYCLE ? (L'humain, par un
  `/ok` sur #42 ou sur #45 — Q1 posée par la t3 de #52.)
- **le verdict de convergence** : après les fixes, le banc
  `tests/test_thread_description.py` passe-t-il 10/10 GREEN ?

### Code (composants impactés)

| composant | état mesuré (2026-10-11) | impact slice 5 |
|---|---|---|
| `pipeline/engine.py` | `DESCRIPTION_MARKER` + `build_description_lines` commités (commité depuis `dccf75f`/`55e6659`) | Livré dans le GREEN partial |
| `pipeline/pj_room_keeper.py` | `build_description_for_card`, `sync_description`, `sync_all_descriptions` présents ; delta **non-commité** (mesuré : `M`, 125 ins/35 del) | Le fix non-commité fait passer le banc 8/10 → 9/10 ; il **n'est pas un travail livré** tant qu'il n'est pas commité (règle de la couverture commit-à-commit) |
| `tests/test_thread_description.py` | 10 cas ; **mesuré 2026-10-11 : 9 GREEN / 1 RED** (`test_erreur_le_reader_de_source_qui_leve_ne_tue_pas_le_tick`) | Banc qui gèle le contrat `contrat-5` ; le dernier rouge est le critère d'acceptation restant |
| `skills/gh-kanban-bridge/scripts/discord_thread.py` | `create`/`send`/`rename`/`threads` seulement (`grep upsert-desc\|pin` → 0 hit) | **`upsert-desc` + `pin` à ajouter** (capacité helper non livrée) |

Le **core pur** à préserver : `build_description_lines` (composition pure :
issue_url, branch, pr_url → list[str], 0 réseau) et
`build_description_for_card` (sources injectées). L'écriture du message et
de l'épingle passe par l'adapter injecté `write_message` / le helper Discord.

**Écart mesuré vs la chaîne** : les notes [[issue-64]] et [[issue-81]]
mesurent le banc **7/10** (3 rouges) ; la mesure du 2026-10-11 sur le
worktree partagé `t_c22a7e74` donne **9/10 (1 rouge)** — les deux autres cas
rouges (`test_nominal_un_seul_message_epingle_mis_a_jour_pas_duplique`,
`test_erreur_gh_pr_list_en_erreur_ligne_omise_tracee_pas_exception`) sont
devenus GREEN, vraisemblablement par le delta non-commité de
`pj_room_keeper.py` (mesurable, non-attribué ici). La **convergence n'est
pas atteinte** : il reste 1 rouge + le helper incomplet + le fix non-commité.
Cette divergence se résout par la mesure du jour ; le contrat (banc 10/10)
ne change pas.

## Lecture SDD (spec-driven)

La spec est le body de l'issue **#19** (arbitrages `Q1=1a`, `Q2=2b`,
`Q3=d`) ; l'issue #52 **n'en est pas le point à statuer direct** — elle est
le miroir du point à statuer de #42 (carte `t_6eaf5341`). La doctrine
(SDD) fixe : la doc décrit le **livré** ; ici le « livré » attendu est le
GREEN 10/10 de la slice 5 (3 fixes keeper + `upsert-desc`/`pin` helper)
commité sur `wt/issue-19-discord-thread-title-description`. Jusqu'au `/ok`
sur #42, l'état mesuré est : GREEN partial commité + 1 cas rouge + delta
non-commité + helper incomplet. Le re-GREEN est porté par le dev après le
`/ok` ; ce cadrage ne le produit pas.

## Lecture DDD (bounded contexts, agrégats, événements)

- **Bounded context traversé** : *convergence / livraison* — chevauche
  *développement* (slice 5 de #19) et *décision humaine* (la chaîne
  #27→#29→#45→#41→#81→…→#52), sans en être un nouveau : c'est la
  **jonction** entre les deux.
- **Agrégat racine** : la **carte `t_6eaf5341`** (invariant : elle ne repart
  en `ready` que quand sa chaîne de parents — dont le point de #42 — est
  close). L'**issue #52** est l'objet miroir qui la matérialise sur GitHub ;
  l'issue **#42** est le porteur du point à statuer.
- **Value objects** : le **branch head SHA** (`95d4db0` mesuré 2026-10-11) ;
  le **banc 9/10** (état de convergence partiel, mesuré ce jour) ;
  l'**idempotency-key** `gh-issue-52` ; le verdict t3 de #52
  (`PROTOTYPE: non, AMBIGU: aucune, ARTEFACT: aucun`).
- **Domain events** : `/ok` humain sur #42 (ou #45) → unblock de
  `t_566c200d` / ré-ouverture du RECYCLE → re-GREEN slice 5 (commit du delta
  non-commité + 3ᵉ fix + `upsert-desc`/`pin`) → banc 10/10 GREEN →
  convergence → doc → doc-review → PR → merge. Le `/ok` sur #52 **n'est pas
  un domain event de la chaîne** (miroir stérile, anti-doublon).

## Lecture TDD (contrats testables)

Le contrat testable est le **banc `tests/test_thread_description.py`**
(10 cas), rejouable sans Discord ni réseau (sources injectées) :

- `build_description_lines(issue_url, branch, pr_url, log=print) ->
  list[str]` — composition pure, omission des `None`/vides (cas GREEN).
- `keeper.build_description_for_card(card, *, …, specs_reader, pr_reader,
  issue_url_lookup)` — assemblage des sources injectées (GREEN).
- `keeper.sync_description(cards, *, fetch_messages, write_message,
  log=None)` — écrivain best-effort : dédup par marqueur, `edit` jamais
  second post (GREEN).
- `test_erreur_gh_pr_list_en_erreur_ligne_omise_tracee_pas_exception` —
  gestion d'erreur quand `gh pr list` lève (GREEN).
- **1 cas restant (mesuré 2026-10-11)** :
  `test_erreur_le_reader_de_source_qui_leve_ne_tue_pas_le_tick` — le reader
  de source qui lève ne doit pas tuer le tick (le bloc tient sans la branche,
  ligne omise, tracée) ; ce passage GREEN est la **preuve de convergence
  restant** de la slice 5, conjointement à l'ajout de `upsert-desc`/`pin`
  dans le helper (adapter, injecté — le banc ne le teste pas directement).

Les contrats du delta non-commité de `pj_room_keeper.py` deviennent
testables seulement **une fois commités** (règle de la couverture
commit-à-commit : un fix dans l'arbre non-commité n'est pas un travail
livré).

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
L'ajout de `upsert-desc`/`pin` se fait dans l'adapter, jamais dans le core.

## Frontières traversées (résumé)

```
issue #52 (GitHub, label decision + kanban, parent #42, MIROIR stérile)
  → /ok sur #42 (le porteur) OU sur #45 (la spec RECYCLE)  ← le seul /ok valide
  → unblock t_566c200d / ré-ouverture RECYCLE (kanban)
  → re-GREEN slice 5 : commit du delta + fix restant + upsert-desc/pin helper
  → banc test_thread_description.py 10/10 GREEN (preuve de convergence)
  → doc → doc-review → PR → merge
```

Deux frontières : **GitHub ↔ kanban** (décision → effet, sur le porteur #42
pas sur le miroir #52) et **git ↔ worktree partagé** (preuve de livraison).
Le point de fragilité n'est pas l'appel réseau mais **la couverture
commit-à-commit** : un fix non-commité dans l'arbre n'est pas un travail
livré — et un `/ok` posé sur le miroir n'est pas un effet.

## État mesuré (2026-10-11, rejouable)

- `origin/dev` = `2027333` (docs cadrage #29).
- Worktree issue #52 (t1) : `wt/t_29c99273` @ `564128d` (3 ahead de dev,
  0 behind) — base du présent commit de cadrage.
- Worktree partagé de la slice 5 (`t_c22a7e74`, branche
  `wt/issue-19-discord-thread-title-description`) :
  - **local = remote** = `95d4db0` (en sync ; GREEN partial commité depuis
    `49bb284` : `dccf75f` fix keeper bouclage, `55e6659` baseline GREEN
    partial, puis les notes cadrage #73/#58).
  - `git status --short` : `M pipeline/pj_room_keeper.py` (delta 125 ins/35
    del **non-commité**), `M tests/test_thread_description.py`, notes
    `issue-27.md`/`issue-29.md` untracked.
- Banc `tests/test_thread_description.py` (`uv`/`pytest -p no:randomly`) :
  **9 GREEN / 1 RED** — le rouge :
  `test_erreur_le_reader_de_source_qui_leve_ne_tue_pas_le_tick`.
- `git cat-file -t 6661362` → **fatal : Not a valid object name**
  (définitivement absent, confirmé 2026-10-11).
- `grep -c "upsert-desc\|'pin'\|\"pin\""
  skills/gh-kanban-bridge/scripts/discord_thread.py` → **0 hit**
  (capacité helper non livrée, confirmé 2026-10-11).
- Board : `t_6eaf5341` (miroir de #52) en `todo`, 3 parents non satisfaits
  (`t_2b705c54`, `t_cd75a2e4` blocked, `t_dbe12c4a`) ; t3 de #52
  (`t_62ed2bbc`) blocked sur la Q1 posée à l'humain (`/ok` sur #42 ou #45).
- `pj_docs_lint.py` sur `/home/elix/pj-repos/hermes-workflow` → `exit=0`
  (mesure du jour, après le présent commit).

## Composants impactés (résumé)

- **Décision (cette issue)** : `pipeline/pj_decision.py` ([[pj-decision]]) +
  `pipeline/pj_escalate.py` / `pipeline/pj_notify.py` ([[pj-notify]]) — la
  boucle #5, **aucun changement de code** ; le seul effet est le `/ok` sur
  le porteur #42 (pas sur #52).
- **Travail débloqué (slice 5 de #19, à compléter après le `/ok`)** :
  - `pipeline/pj_room_keeper.py` — commit du delta non-commité (les 2 fixes
    déjà validés par le banc 9/10) + le dernier fix (reader qui lève ne tue
    pas le tick).
  - `skills/gh-kanban-bridge/scripts/discord_thread.py` — ajout des
    capacités `upsert-desc` (édition du message du fil) et `pin` (épingle du
    message).
- **Vault** : à la convergence, la slice 5 gagnera sa note composant et le
  MOC `docs/architecture/README.md` sera mis à jour par la carte `doc-k` —
  hors périmètre de cette décision.

## Non tranché (et qui doit le rester ici)

Le cadrage ne tranche **pas** :
1. **Le contenu exact du dernier fix keeper et des capacités
   `upsert-desc`/`pin`** — portés par le dev après le `/ok` (le banc définit
   le contrat, pas le cadrage).
2. **Le choix du porteur du `/ok`** (#42 vs #45) — arbitrage humain (Q1 posée
   par la t3 de #52 dans le thread Discord conv-5 #28).
3. **La publication live des copies `~/.hermes/scripts/`** (divergence D2
   déclarée dans le handoff `dev-5`) — opération de fin de graphe contrôlée
   par identité, hors périmètre de cette décision.

Ces points sont **documentés**, pas décidés ici.
