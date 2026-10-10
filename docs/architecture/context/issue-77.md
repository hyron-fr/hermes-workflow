---
type: context
status: draft
tags: [architecture, decision, escalation, convergence, recycle, slice-5, cadrage]
issues: [77]
---

# Cadrage architectural — issue #77 « t3 grill-me » (7ᵉ escalade conv-5)

## Positionnement (cadre exact)

L'issue #77 (`label: decision` + `kanban`, `idempotency-key gh-issue-77`,
importée en carte racine `t_692a0092` sur le board `pj-hermes-workflow`) est
une **escalade de décision** de la carte **`t_12b728e1`** (« t3 grill-me issue
#32 », assignée à `pj-master`), **bloquée depuis 165 h** (mesuré le
2026-10-10 : `blocked_at=1791075626`, warning de la carte confirmé).

C'est la **septième et dernière** escalade conv-5 de la chaîne :

| # | Issue | Carte bloquée | Motif |
|---|---|---|---|
| 1ᵉʳ | #27 | `t_f725879f` (conv-5) | GREEN dev-5 `6661362` perdu, banc 10/10 RED |
| 2ᵉ | #29 | `t_f725879f` (conv-5) | Miroir, ré-importé par le pont de couverture |
| 3ᵉ | #45 | `t_854f0f77` (dev GREEN RECYCLE) | GREEN partial 7/10, recycle du GREEN perdu |
| 4ᵉ | #41 | `t_3f7e0be4` (t3 grill-me) | Quadrante + verdict ; Q1 posée à l'humain |
| 5ᵉ | #81 | `t_c0e5ce5a` (t3 grill-me) | Quadrante + verdict ; `/ok` attendu |
| 6ᵉ | #80 | (t3 grill-me) | Miroir conv-5, point à statuer mesuré 2026-10-10 |
| **7ᵉ** | **#77** | **`t_12b728e1`** (t3 grill-me #32) | **1 question non levable : l'action de débloquage du GREEN dev-5 perdu** |

**Le point à statuer** (corps de l'issue, repris par la carte `t_692a0092`) :

- Verdict grill-me de `t_12b728e1` : `PROTOTYPE: non / AMBIGU: action de
  débloquage / ARTEFACT: aucun`.
- L'unique question non levable est le **choix d'action sur le commit
  `6661362` (GREEN dev-5 original) perdu** :
  - **(a) re-générer** le GREEN dev-5 depuis le banc (option qui passe par le
    jeton `/ok` sur l'issue #77) ;
  - **(b) replanifier** le point ;
  - **(c) renoncer** au GREEN dev-5.
- Le jeton `/ok` posé **en premier élément** d'un commentaire sur l'issue #77
  débloque la carte `t_12b728e1` et la repart en file ; tout autre commentaire
  est une demande d'éclaircissement et ne débloque rien.

**Ce que la décision débloque** : le cycle dev-5 de #19 (slices GREEN
description Discord du fil conv-5). L'effet attendant après le `/ok` : la carte
`t_12b728e1` repart, le grill-me reformule, le dev re-génère le GREEN dev-5 et
le pousse sur `wt/issue-19-discord-thread-title-description`, le banc
`tests/test_thread_description.py` passe 10/10.

## État mesuré (2026-10-10, rejouable)

Mesuré sur les refs nommées (pas sur le checkout principal), le même jour :

- **`6661362`** (GREEN dev-5 original) : `git cat-file -t 6661362` →
  **fatal : Not a valid object name** — définitivement absent du dépôt local
  et du remote.
- **`origin/dev`** = `2027333` (docs cadrage #29). Le fix
  `8e35b6e` (« le jeton /ok vaut aussi après UNE amorce », `TOKEN_PREFIX_MAX`)
  **n'est PAS dans `origin/dev`** (`git merge-base --is-ancestor 8e35b6e
  origin/dev` → NO). Le fix vit sur `fix/decision-jeton-apres-amorce` (HEAD du
  checkout principal, `7091678`), qui est lui aussi **hors de dev**.
  → Conséquence : un `/ok` posé **avec amorce** (« rattaché /ok », comme le
  2026-10-06 sur l'enfant #31) reste un faux négatif tant que `8e35b6e`
  n'est pas mergé ; seul un `/ok` strictement **en première position**
  débloque aujourd'hui.
- **`wt/issue-19-discord-thread-title-description`** (worktree
  `t_c22a7e74`, tip remote = local `b846a28`) :
  - 10 commits au-dessus de `origin/dev` : `49bb284` (test RED slice 5) →
    `03e09f1` (cadrage #31) → `dccf75f` (fix keeper bouclage infini) →
    `55e6659` (baseline conv-audit) → `6a827a0`/`578b7b2`/`56e2525`/`dbf73da`
    (cadrages #45/#41) → `6a2d8e3` (cadrage #26) → `b846a28` (cadrage #80).
  - **Banc `tests/test_thread_description.py` : 7/10 GREEN, 3 RED** (mesuré
    le 2026-10-10 dans le worktree `t_c22a7e74` via
    `uv run --with pytest --with pyyaml --with langgraph python -m pytest
    tests/test_thread_description.py -v -p no:randomly`) :
    - `test_nominal_un_seul_message_epingle_mis_a_jour_pas_duplique` (dédup du
      message épinglé) ;
    - `test_erreur_gh_pr_list_en_erreur_ligne_omise_tracee_pas_exception`
      (gestion d'erreur `gh pr list`) ;
    - `test_erreur_le_reader_de_source_qui_leve_ne_tue_pas_le_tick`
      (non-lèvement quand un reader de source lève).
  - Le GREEN partial est dans le commit `55e6659` (baseline conv-audit) :
    `DESCRIPTION_MARKER`, `build_description_lines`,
    `build_description_for_card`, `sync_description`,
    `sync_all_descriptions` présents dans `pipeline/engine.py` et
    `pipeline/pj_room_keeper.py`.
- **Helper `skills/gh-kanban-bridge/scripts/discord_thread.py`** (mesuré sur
  la branche du pipeline `wt/t_bb04eb45` = `7091678`) : commandes
  `create` / `send` / `threads` / `rename` seulement — **`upsert-desc` et
  `pin` absents** (grep : 0 hit). Ces deux capacités sont requises par le
  GREEN dev-5 (édition du message du fil + épingle).
- **`55e6659` n'est PAS ancestor de `origin/dev`** : le GREEN partial n'a
  jamais atterri sur dev.
- **Carte cible `t_12b728e1`** : `status: blocked`, assignee `pj-master`,
  enfants `t_2dfedb78`, `t_67ad249d`, warning « blocked for 164 h ».

## Croisement infrastructure / fonctionnel / code

### Infrastructure (frontières traversées)

- **GitHub** — surface de décision : commentaire `/ok` sur l'issue #77
  (premier élément de la phrase). Adapter : `gh` CLI, lu par le pont
  `pipeline/pj_decision.py`. La carte `t_12b728e1` est l'objet de la reprise.
- **Kanban Hermes** — source de vérité de l'état des cartes. L'effet est
  `comment` + `unblock` sur `t_12b728e1`, invoqués en `subprocess` par le
  câblage de #5 ([[pj-decision]] : `decision_from_comment` calcule,
  l'appelant applique ; [[pj-notify]] pour les notifications).
- **Git / worktree partagé** — surface de livraison : le branch head de
  `wt/issue-19-discord-thread-title-description` (worktree `t_c22a7e74`,
  tip `b846a28`) est la **preuve de livraison** du dev-5. État mesuré :
  GREEN partial présent, banc 7/10, helper incomplet.
- **Discord** — thread de l'issue (« hermes-workflow #28 · Décision conv-5
  GREEN dev-5 perdu »), canal où la question a été posée ; hors périmètre de
  cette décision (le point se tranche sur GitHub, pas sur Discord).
- **Aucun nouveau port** : les surfaces (GitHub, kanban, git, Discord)
  existent déjà ; l'issue #77 réutilise la boucle de décision #5.

### Fonctionnel (capacité traversée)

La capacité traversée est **convergence + preuve de livraison** (pas une
fonctionnalité nouvelle). Le chantier #19 (« Discord thread title and
description update ») est déjà cadré par les notes `issue-27` (1ᵉʳ),
`issue-29` (2ᵉ), `issue-41` (4ᵉ), `issue-81` (5ᵉ), `issue-80` (6ᵉ) et le
composant `pj-thread-name` (slices 2–4 livrées). #77 porte :

- **le point de décision** : le GREEN dev-5 `6661362` étant perdu, quelle
  action ? (a) re-générer depuis le banc — `/ok`, (b) replanifier,
  (c) renoncer.
- **la chaîne de livraison** : après le `/ok`, le dev re-génère le GREEN
  dev-5 (3 fixes keeper restants + `upsert-desc`/`pin` dans le helper),
  pousse sur `wt/issue-19-discord-thread-title-description`.
- **le verdict de convergence** : le banc
  `tests/test_thread_description.py` passe-t-il 10/10 GREEN ?

### Code (composants impactés)

| composant | état mesuré (2026-10-10) | impact du dev-5 re-généré |
|---|---|---|
| `pipeline/pj_decision.py` | Fix `8e35b6e` (`TOKEN_PREFIX_MAX`) **hors de dev** | Aucun — la boucle #5 est livrée ; seul le merge du fix change le comportement du jeton avec amorce |
| `pipeline/engine.py` | `DESCRIPTION_MARKER` + `build_description_lines` présents (55e6659) | Livré dans le GREEN partial |
| `pipeline/pj_room_keeper.py` | `build_description_for_card`, `sync_description`, `sync_all_descriptions` présents (55e6659) | **3 fixes restants** : (1) dédup du message épinglé, (2) non-lèvement reader, (3) gestion d'erreur `gh pr list` |
| `tests/test_thread_description.py` | 10 cas, 7 GREEN / 3 RED | Banc qui gèle le contrat ; les 3 RED sont les critères restants |
| `skills/gh-kanban-bridge/scripts/discord_thread.py` | `create`/`send`/`threads`/`rename` seulement | **`upsert-desc` + `pin` à ajouter** |
| `pipeline/pj_escalate.py` / `pipeline/pj_notify.py` | Livrés ([[pj-notify]]) | Aucun changement de code |

Le **core pur** à préserver : `build_description_lines` (composition pure :
issue_url, branch, pr_url → list[str], 0 réseau) et
`build_description_for_card` (sources injectées). L'écriture du message et de
l'épingle passe par l'adapter injecté `write_message` / le helper Discord.

## Lecture SDD (spec-driven)

La spec est le body de l'issue **#19** (arbitrages `Q1=1a`, `Q2=2b`, `Q3=d`)
; l'issue #77 **est** le point à statuer de sa carte `t_12b728e1`. Le verdict
du grill-me (déposé dans le thread Discord + commentaire 1048 de la carte)
fixe le périmètre : `PROTOTYPE: non / AMBIGU: action de débloquage /
ARTEFACT: aucun`. La doc décrit le livré : ici le « livré » attendu est le
GREEN 10/10 re-généré (3 fixes keeper + upsert-desc/pin) ; jusqu'au `/ok`,
l'état mesuré est 7/10 GREEN + helper incomplet + fix `/ok` hors de dev.

## Lecture DDD (bounded contexts, agrégats, événements)

- **Bounded context traversé** : *convergence / livraison* — chevauche
  *développement* (dev-5 de #19) et *décision humaine* (l'escalade
  #27→#29→#45→#41→#81→#80→#77), sans en être un nouveau : c'est la
  **jonction** entre les deux.
- **Agrégat racine** : la **carte `t_12b728e1`** (invariant : elle ne repart
  en `ready` que sur un `/ok` portant sa ligne canonique
  `carte: pj-hermes-workflow/t_12b728e1`). L'**issue #77** est l'objet de
  décision qui la matérialise (carte racine `t_692a0092` sur le board).
- **Value objects** : le **branch head SHA** `b846a28` (tip remote = local,
  mesuré) ; le **banc 7/10** (état de convergence partiel) ;
  l'**idempotency-key** `gh-issue-77` ; le verdict grill-me
  (`PROTOTYPE: non, AMBIGU: action de débloquage, ARTEFACT: aucun`).
- **Domain events** : `/ok` humain sur l'issue #77 (premier élément) →
  unblock de `t_12b728e1` → re-spawn grill-me → reformulation → dev
  re-génère le GREEN dev-5 (3 fixes keeper + `upsert-desc`/`pin`) → banc
  10/10 GREEN → convergence → doc → doc-review → PR → merge.

## Lecture TDD (contrats testables)

Le contrat testable est le **banc `tests/test_thread_description.py`**
(10 cas), rejouable sans Discord ni réseau (sources injectées) :

- `build_description_lines(issue_url, branch, pr_url, log=print) -> list[str]`
  — composition pure, omission des `None`/vides (4 cas GREEN).
- `keeper.build_description_for_card(card, *, …, specs_reader, pr_reader,
  issue_url_lookup)` — assemblage des sources injectées (2 cas GREEN,
  **1 cas RED** : le reader qui lève ne doit pas tuer le tick).
- `keeper.sync_description(cards, *, fetch_messages, write_message, log=None)`
  — écrivain best-effort : dédup par marqueur, `edit` jamais second post
  (**1 cas RED** : un seul message épinglé mis à jour, pas dupliqué).
- **1 cas RED supplémentaire** : `test_erreur_gh_pr_list_en_erreur_ligne_omise_tracee_pas_exception`
  — gestion d'erreur quand `gh pr list` lève (la ligne PR est omise mais
  tracée, pas d'exception).
- Les **3 cas RED** sont les critères d'acceptation restants du dev-5 ;
  leur passage GREEN est la preuve de convergence.

Les capacités helper `upsert-desc`/`pin` ne sont **pas** testées
directement par ce banc : le helper est un adapter (REST Discord), injecté
via `write_message` — sa forme est un choix de dev, pas un contrat du banc.

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
issue #77 (GitHub, label decision + kanban, carte racine t_692a0092)
  → commentaire /ok humain (premier élément, surface de décision)
  → unblock de t_12b728e1 (kanban, 165 h de blocage)
  → re-spawn grill-me → reformulation → dev re-génère le GREEN dev-5
    (3 fixes keeper + upsert-desc/pin)
  → push sur wt/issue-19-discord-thread-title-description (tip b846a28)
  → banc test_thread_description.py 10/10 GREEN (preuve de convergence)
  → doc → doc-review → PR → merge
```

Deux frontières : **GitHub ↔ kanban** (décision → effet) et
**git ↔ worktree partagé** (preuve de livraison). Le point de fragilité
n'est pas l'appel réseau mais **la couverture commit-à-commit** : un fix
non-commité dans l'arbre n'est pas un travail livré.

## Non tranché (et qui doit le rester ici)

Le cadrage ne tranche **pas** :

1. **Le choix (a)/(b)/(c) sur le GREEN perdu** — c'est le point à statuer
   lui-même ; seul le `/ok` (option (a), re-générer) ou une précision
   humaine (b/c) le lève. Le cadrage documente les trois options, ne les
   arbitre pas.
2. **Le contenu exact des 3 fixes keeper** — porté par le dev après le
   `/ok` (le banc définit le contrat, pas le cadrage).
3. **La forme des capacités `upsert-desc`/`pin`** — porté par le dev ; le
   banc ne les teste pas directement (le helper est un adapter, injecté).
4. **Le merge du fix `8e35b6e`** (jeton après amorce) sur `origin/dev` —
   opération de fin de graphe contrôlée par identité, hors périmètre de
   cette décision. Un `/ok` strictement en première position débloque
   aujourd'hui, sans ce merge.
5. **La publication live des copies `~/.hermes/scripts/`** — hors
   périmètre.

Ces points sont **documentés**, pas décidés ici.
