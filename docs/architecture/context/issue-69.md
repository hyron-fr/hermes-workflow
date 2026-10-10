---
type: context
status: draft
tags: [architecture, decision, escalation, recycle, convergence, slice-5, description-epinglee, cadrage]
issues: [69]
---

# Cadrage architectural — issue #69 « t5 validate » (escalade conv-5, carte `t_f1aa13e4`)

## Positionnement (cadre exact)

L'issue #69 (`labels: kanban + decision`, titre « t5 validate », state OPEN,
ouvert le 2026-10-08 11:15 UTC) est le **miroir GitHub de la carte
`t_f1aa13e4`** (t5 validate, assignée à `pj-master`, board
`pj-hermes-workflow`), elle-même **bloquée (needs_input)** sur le chantier
#45 (« slice 5/5 — dev (GREEN) — RECYCLE : re-livrer le commit GREEN perdu »).

C'est une **escalade de décision** de la chaîne conv-5 du chantier #19
(« Discord thread title and description update »). Le motif déclaré sur la
carte, mesuré au blocage (2026-10-08) et inchangé à la date de cette note
(2026-10-11) :

- Spec #45 postée sur GitHub (issue updated) + message Go/No-go dans le
  thread Discord conv-5 `1556098965206863982`.
- En attente du **GO humain** pour débloquer `t_854f0f77` (slice 5/5 GREEN).
- **Périmètre gelé** : 2 fixes keeper + `upsert-desc`/`pin` + suppression
  `diag2.py` + 1 ligne patch banc. Banc 8/10 → 10/10 attendu.

**Ce que la décision débloque** : le jeton `/ok` en **premier élément** du
commentaire sur l'issue #69 débloque la carte `t_f1aa13e4` et la repart en
file (elle crée alors `t6 submitted` + sous-tâches dev, règle ANTI-DEADLOCK
du SOUL). Tout autre commentaire est une demande d'éclaircissement et ne
débloque rien.

**Rappel du fix de grammaire** (commit `8e35b6e`, dans `origin/dev`) :
`_token_index` accepte le jeton en tête **ou immédiatement après une amorce**
(`TOKEN_PREFIX_MAX = 1`) — « rattaché /ok » vaut donc autant qu'« /ok » seul.
Au-delà d'une amorce, le jeton est *cité* et ne décide plus rien.

## Croisement infrastructure / fonctionnel / code

### Infrastructure (frontières traversées)

- **GitHub** — surface de décision : commentaire `/ok` sur l'issue #69
  (miroir de `t_f1aa13e4`). Adapter : `gh` CLI, lu par le pont.
- **Discord** — canal de notification du Go/No-go : thread conv-5
  `1556098965206863982` ([[pj-escalate]] : la chaîne de publication y
  dépose le message d'escalade).
- **Kanban Hermes** — source de vérité de l'état des cartes. L'effet est
  `comment` + `unblock` sur `t_f1aa13e4`, invoqués par le câblage de #5
  ([[pj-decision]] : `decision_from_comment` calcule, l'appelant applique).
- **Git / worktree partagé** — surface de livraison : le branch head de
  `wt/issue-19-discord-thread-title-description` (worktree `t_c22a7e74`)
  est la **preuve de livraison** de la slice 5. État mesuré (ci-dessous) :
  tip `9fcd207`, GREEN partial présent, banc 7/10.
- **Aucun nouveau port** : les quatre surfaces (GitHub, Discord, kanban,
  git) existent ; l'issue #69 réutilise la boucle de décision #5 et la
  chaîne d'escalade #4/#5.

### Fonctionnel (capacité traversée)

La capacité traversée est **convergence + preuve de livraison** (pas une
fonctionnalité nouvelle). Le chantier #19 est déjà cadré par les notes
`issue-27`, `issue-29`, `issue-41`, `issue-81`, `issue-70` (escalades de la
même chaîne conv-5) et la note composant `pj-thread-name` (slices 2–4
livrées). #69 porte :

- **le point de décision** : la slice 5 est-elle convergée ? État mesuré :
  NON — 3 fixes keeper + les capacités `upsert-desc`/`pin` du helper
  manquent (le périmètre déclaré sur la carte parle de 2 fixes keeper,
  l'état mesuré au 2026-10-11 montre 3 cas RED nommés ; la divergence est
  documentée à la section « Non tranché »).
- **la chaîne de livraison** : qui applique les fixes keeper restants et
  ajoute `upsert-desc`/`pin` dans le helper ? (Le dev, via `t_854f0f77`
  après le `/ok`.)
- **le verdict de convergence** : après les fixes, le banc
  `tests/test_thread_description.py` passe-t-il 10/10 GREEN ?

### Code (composants impactés)

| composant | état mesuré (2026-10-11) | impact slice 5 |
|---|---|---|
| `pipeline/engine.py` | `DESCRIPTION_MARKER` + `build_description_lines` présents | Livré dans le GREEN partial |
| `pipeline/pj_room_keeper.py` | `build_description_for_card` (L572), `sync_description` (L695), `sync_all_descriptions` (L799) présents | 3 tests RED : dédup du message épinglé + non-lèvement du reader qui lève + gestion `gh pr list` en erreur |
| `tests/test_thread_description.py` | 10 cas, 7 GREEN / 3 RED | Banc qui gèle le contrat `contrat-5` |
| `skills/gh-kanban-bridge/scripts/discord_thread.py` | Commandes `create`/`send`/`rename`/`threads` seulement | **`upsert-desc` + `pin` à ajouter** |
| `pipeline/pj_decision.py` | `decision_from_comment` + `_token_index` (fix `8e35b6e` : amorce tolérée) | Aucun changement — boucle #5 réutilisée |

Le **core pur** à préserver : `build_description_lines` (composition pure :
issue_url, branch, pr_url → list[str], 0 réseau) et
`build_description_for_card` (sources injectées). L'écriture du message et
de l'épingle passent par l'adapter injecté `write_message` / le helper
Discord.

## Lecture SDD (spec-driven)

La spec est le body de l'issue **#19** (arbitrages `Q1=1a`, `Q2=2b`,
`Q3=d`) ; l'issue #69 **est** le point à statuer de sa carte `t_f1aa13e4`
(via #45). La doc décrit le livré : ici le « livré » attendu est le GREEN
10/10 (fixes keeper + `upsert-desc`/`pin` + suppression `diag2.py` + 1 ligne
patch banc) ; jusqu'au `/ok`, l'état mesuré est 7/10 GREEN + helper
incomplet. Le périmètre est gelé par le banc — le cadrage ne le modifie pas.

## Lecture DDD (bounded contexts, agrégats, événements)

- **Bounded context traversé** : *convergence / livraison* — chevauche
  *développement* (slice 5 de #19) et *décision humaine* (l'escalade
  conv-5), sans en être un nouveau : c'est la **jonction** entre les deux.
- **Agrégat racine** : la **carte `t_f1aa13e4`** (invariant : elle ne
  repart en `ready` que sur un `/ok` portant sa ligne canonique
  `carte: pj-hermes-workflow/t_f1aa13e4`, premier élément ou après une
  amorne). L'**issue #69** est l'objet de décision qui la matérialise.
- **Value objects** : le **branch head SHA** (`9fcd207` mesuré) ; le **banc
  7/10** (état de convergence partiel) ; l'**idempotency-key** `gh-issue-69`
  (fermeture auto de l'issue quand la carte passe done).
- **Domain events** : `/ok` humain sur l'issue #69 → unblock de
  `t_f1aa13e4` → `t6 submitted` + sous-tâches dev (ANTI-DEADLOCK) → dev
  applique les fixes keeper + ajoute `upsert-desc`/`pin` + supprime
  `diag2.py` → banc 10/10 GREEN → convergence → doc → doc-review → PR →
  merge → fermeture auto de #69.

## Lecture TDD (contrats testables)

Le contrat testable est le **banc `tests/test_thread_description.py`**
(10 cas), rejouable sans Discord ni réseau (sources injectées) :

- `build_description_lines(issue_url, branch, pr_url, log=print) ->
  list[str]` — composition pure, 4 lignes, omission des `None`/vides
  (cas GREEN).
- `keeper.build_description_for_card(card, *, …, specs_reader, pr_reader,
  issue_url_lookup)` — assemblage des sources injectées (GREEN ; 1 cas RED :
  le reader qui lève ne doit pas tuer le tick).
- `keeper.sync_description(cards, *, fetch_messages, write_message,
  log=None)` — écrivain best-effort : dédup par marqueur, `edit` jamais
  second post (1 cas RED : un seul message épinglé mis à jour pas
  dupliqué).
- **1 cas RED supplémentaire** : `gh pr list` en erreur — la ligne PR est
  omise mais tracée, pas d'exception.
- **Côté décision** (déjà testé, commit `8e35b6e`) :
  `tests/test_decision_humaine.py` gèle la grammaire du jeton — 4 cas «
  porte le jeton » / 4 cas « le cite » / 1 cas grammaire refusée, dont le
  cas « /ok après une amorce » (le verbatim produit du 2026-10-06).

Les **cas RED** du banc description sont les critères d'acceptation
restants de la slice 5 ; leur passage GREEN est la preuve de convergence.

## Lecture hexagonale (le core reste pur)

Le **core pur** : `build_description_lines` (fonction pure, 0 réseau, 0
horloge, 0 aléa) et `build_description_for_card` (sources injectées).
L'écriture du message épinglé et de l'épingle passe par le helper
`discord_thread.py` (adapter REST, hors core). Le contrat d'interface
(marqueur `[description]`, `sync_description`, `sync_all_descriptions`) est
testable sans Discord : les sources et l'adaptateur sont injectés.

La frontière à respecter : **la description est une lecture d'état**
(gh/git/blackboard) résolue **hors** du core, puis injectée dans le
formateur pur. Jamais l'inverse : le formateur ne lit pas le réseau.

## Frontières traversées (résumé)

```
issue #69 (GitHub, labels kanban + decision, miroir de t_f1aa13e4)
  → commentaire /ok humain (surface de décision)
  → unblock de t_f1aa13e4 (kanban) + notification Discord conv-5
  → t6 submitted + sous-tâches dev (règle ANTI-DEADLOCK)
  → dev applique fixes keeper + upsert-desc/pin + supprime diag2.py + patch banc
  → banc test_thread_description.py 10/10 GREEN (preuve de convergence)
  → doc → doc-review → PR → merge → fermeture auto de #69
```

Quatre frontières : **GitHub ↔ kanban** (décision → effet),
**Discord ↔ kanban** (notification d'escalade), **kanban → graphe dev**
(décomposition post-`/ok`), et **git ↔ worktree partagé** (preuve de
livraison). Le point de fragilité n'est pas l'appel réseau mais **la
couverture commit-à-commit** : un fix non-commité dans l'arbre n'est pas un
travail livré (leçon du GREEN dev-5 `6661362` perdu).

## État mesuré (2026-10-11, rejouable)

- `origin/dev` = `2027333` (docs cadrage #29 ; contient le fix décision
  jeton post-amorce `8e35b6e`).
- Worktree d'issue `t_22c544cd` (branche `wt/t_22c544cd`) : HEAD `7091678`
  (docs cadrage #81), propre, contient `origin/dev`.
- `wt/issue-19-discord-thread-title-description` :
  - **local** (worktree partagé `t_c22a7e74`) = `9fcd207` (docs cadrage
    #73).
  - **remote** = `9fcd207` (en sync, `0 0`).
  - `git status --short` : `?? docs/architecture/context/issue-27.md`,
    `?? docs/architecture/context/issue-29.md` (notes non commitées, hors
    périmètre de la slice 5).
- `git cat-file -t 6661362` → **fatal : Not a valid object name**
  (GREEN dev-5 original définitivement absent du dépôt local et du remote).
- `grep DESCRIPTION_MARKER|build_description|sync_description` sur
  `pipeline/` → **présents** dans `pipeline/engine.py` et
  `pipeline/pj_room_keeper.py` (GREEN partial livré dans l'arbre).
- `grep upsert-desc|pin` sur
  `skills/gh-kanban-bridge/scripts/discord_thread.py` → **0 hit**
  (capacité non livrée).
- Banc `tests/test_thread_description.py` : **7/10 GREEN, 3 RED** (mesuré
  2026-10-11 ; rejouable via `uv run --with pytest --with pyyaml --with
  langgraph --with langchain-core python -m pytest
  tests/test_thread_description.py -v -p no:randomly`). Les 3 cas rouges :
  - `test_nominal_un_seul_message_epingle_mis_a_jour_pas_duplique`
  - `test_erreur_gh_pr_list_en_erreur_ligne_omise_tracee_pas_exception`
  - `test_erreur_le_reader_de_source_qui_leve_ne_tue_pas_le_tick`
- `pj_docs_lint.py` sur `/home/elix/pj-repos/hermes-workflow` → `exit=0`.

## Composants impactés (résumé)

- **Décision (cette issue)** : `pipeline/pj_decision.py` ([[pj-decision]]) +
  `pipeline/pj_escalate.py` / `pipeline/pj_notify.py` ([[pj-notify]]) — la
  boucle #5, aucun changement de code attendu.
- **Travail débloqué (slice 5 de #19, à compléter)** :
  - `pipeline/pj_room_keeper.py` — fixes nommés par le banc : (1) logique de
    déduplication pour qu'un seul message épinglé soit mis à jour (pas
    dupliqué), (2) non-lèvement quand un reader de source lève (le tick ne
    meurt pas), (3) gestion d'erreur quand `gh pr list` lève (ligne omise
    mais tracée).
  - `skills/gh-kanban-bridge/scripts/discord_thread.py` — ajout des
    capacités `upsert-desc` (édition du message du fil) et `pin` (épingle du
    message).
  - Suppression de `diag2.py` + 1 ligne patch banc (périmètre déclaré sur la
    carte).
- **Vault** : à la convergence, la slice 5 gagnera sa note composant et le
  MOC `docs/architecture/README.md` sera mis à jour par la carte `doc-k` —
  hors périmètre de cette décision.

## Non tranché (et qui doit le rester ici)

Le cadrage ne tranche **pas** :
1. **Le contenu exact des fixes keeper** — porté par le dev après le `/ok`
   (le banc définit le contrat, pas le cadrage).
2. **La forme des capacités `upsert-desc`/`pin`** — porté par le dev ; le
   banc ne les teste pas directement (le helper est un adapter, injecté).
3. **La divergence 2 fixes (périmètre déclaré sur la carte) vs 3 cas RED
   (état mesuré 2026-10-11)** — le banc est la source de vérité du périmètre
   réel ; c'est au GO humain d'arbitrer s'il confirme le périmètre tel que
   mesuré.
4. **La publication live des copies `~/.hermes/scripts/`** (divergence D2
   déclarée dans le handoff `dev-5`) — opération de fin de graphe contrôlée
   par identité, hors périmètre de cette décision.

Ces points sont **documentés**, pas décidés ici.
