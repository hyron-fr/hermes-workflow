---
type: context
status: draft
tags: [architecture, decision, escalation, grill-me, convergence, slice-5, description-epinglee, cadrage]
issues: [73]
---

# Cadrage architectural — issue #73 « t3 grill-me » (5ᵉ escalade conv-5)

## Positionnement (cadre exact)

L'issue #73 (`label: decision` + `kanban`, `idempotency-key gh-issue-73`,
carte liée **`t_e59e64e5`** par sa ligne canonique
`carte: pj-hermes-workflow/t_e59e64e5`, board `pj-hermes-workflow`,
parent **#31**) est une **escalade de décision** de la carte
**`t_e59e64e5`** (« t3 grill-me », assignée `pj-master`), bloquée sur le
chantier **#31** (« slice 5/5 — convergence », miroir de la carte conv-5
`t_f725879f` du chantier #19).

C'est la **cinquième escalade conv-5** de la chaîne :

| # | Issue | Carte bloquée | Motif (résumé) |
|---|---|---|---|
| 1ᵉʳ | #27 | `t_f725879f` (conv-5) | GREEN dev-5 `6661362` perdu, banc 10/10 RED |
| 2ᵉ | #29 | `t_f725879f` (conv-5) | Même point, ré-importé par le pont de couverture |
| 3ᵉ | #45 | `t_854f0f77` (dev GREEN RECYCLE) | GREEN partial (7/10), fixes + upsert-desc/pin manquants |
| 4ᵉ | #41 | `t_3f7e0be4` (t3 grill-me) | GREEN partial, 2 fixes keeper + helper restants |
| **5ᵉ** | **#73** | **`t_e59e64e5`** (t3 grill-me, parent #31) | **Verdict grill-me produit, `/ok` attend sur #31 ou #73** |

## Le point à statuer (mesuré le 2026-10-11, rejouable)

Mesuré sur le worktree partagé `t_c22a7e74` (branche
`wt/issue-19-discord-thread-title-description`, tip **`5c723a6`**, local =
remote `5c723a6`) :

- Le commit **`6661362`** (GREEN dev-5 original) est **définitivement absent**
  du dépôt local et du remote : `git cat-file -t 6661362` →
  `fatal: Not a valid object name`.
- Le **GREEN partial** est **commité** dans l'arbre :
  - `DESCRIPTION_MARKER` (L221) + `build_description_lines` (L224) dans
    `pipeline/engine.py` ;
  - `build_description_for_card` (L572), `sync_description` (L695),
    `sync_all_descriptions` (L799) dans `pipeline/pj_room_keeper.py` ;
  - le keeper **appelle déjà** `pin` (L776) et `upsert-desc` (L896) via le
    helper — mais ces commandes n'existent pas encore dans le helper.
- Le banc `tests/test_thread_description.py` (387 lignes, 10 cas) est
  **7 GREEN / 3 RED**, rejoué le 2026-10-11 par exécution
  (`uv run --with pytest --with pytest-randomly --with pyyaml --with
  langgraph python -m pytest tests/test_thread_description.py -v
  -p no:randomly` → `3 failed, 7 passed in 0.16s`) :
  1. `test_nominal_un_seul_message_epingle_mis_a_jour_pas_duplique` — la dédup
     par marqueur ne mène pas à un seul message épinglé mis à jour ;
  2. `test_erreur_gh_pr_list_en_erreur_ligne_omise_tracee_pas_exception` — la
     gestion d'erreur de `gh pr list` qui lève n'est pas en place ;
  3. `test_erreur_le_reader_de_source_qui_leve_ne_tue_pas_le_tick` — un
     lecteur de source qui lève ne doit pas tuer le tick ; `len(ecrits) == 1`
     échoue (0 message écrit).
- Les capacités **`upsert-desc` / `pin`** sont **absentes** du helper
  `skills/gh-kanban-bridge/scripts/discord_thread.py` : `main()` ne gère que
  `create`, `send`, `threads`, `rename` (grep : 0 hit sur `upsert-desc|pin`).

**Ce que la décision débloque** : le jeton `/ok` sur l'issue #73 (ou sur son
parent #31, premier élément du commentaire) fait déboucler la carte
`t_e59e64e5` et la repart en file. L'effet attendant : **appliquer les 3
retouches keeper restantes + ajouter `upsert-desc`/`pin` dans le helper**,
puis le banc passe 10/10. Tout autre commentaire est une demande
d'éclaircissement.

**Verdict du grill-me** (commentaire de la carte `t_e59e64e5`,
2026-10-04, posté dans le fil Discord #19 msg `1556088035538509945`) :

```
PROTOTYPE: non
AMBIGU: aucune (ambiguïté 1 levée seule par mesure git ;
         ambiguïté 2 = arbitrage humain, pas une ambiguïté de spec)
ARTEFACT: aucun
```

Les deux ambiguïtés de la carte `t_e59e64e5` :

| # | Ambiguïté | Levable seule ? | Conclusion |
|---|---|---|---|
| 1 | Le commit GREEN slice 5 a-t-il été perdu ou jamais poussé ? | **Oui** | Mesuré : `6661362` absent de tout ref local/remote ; le GREEN n'a jamais été poussé (ou perdu par rebase entre 13:19 et 13:39 le 2026-10-03). |
| 2 | Débloquer conv-5 (`/ok`) ou re-pousser le code d'abord ? | **Non** | Arbitrage humain. Recommandation : re-pousser le code d'abord (option B), puis `/ok`. |

## Croisement infrastructure / fonctionnel / code

### Infrastructure (frontières traversées)

- **GitHub** — surface de décision : commentaire `/ok` sur l'issue #73
  (miroir de l'escalade de la carte `t_e59e64e5`, parent #31). Adapter :
  `gh` CLI, lu par le pont. La carte `t_e59e64e5` est l'objet de la reprise.
- **Kanban Hermes** — source de vérité de l'état des cartes. L'effet est
  `comment` + `unblock` sur `t_e59e64e5`, invoqués en `subprocess` par le
  câblage de #5 ([[pj-decision]] : `decision_from_comment` calcule,
  l'appelant applique).
- **Git / worktree partagé** — surface de livraison : le branch head de
  `wt/issue-19-discord-thread-title-description` (worktree `t_c22a7e74`) est
  la **preuve de livraison** de la slice 5. État mesuré : tip `5c723a6`,
  GREEN partial commité, 3 tests rouges, helper incomplet.
- **Aucun nouveau port** : les trois surfaces (GitHub, kanban, git) existent ;
  l'issue #73 réutilise la boucle de décision #5.

### Fonctionnel (capacité traversée)

La capacité traversée est **convergence + preuve de livraison** (pas une
fonctionnalité nouvelle). Le chantier #19 (« Discord thread title and
description update ») est déjà cadré par les notes [[issue-27]] (escalade
1ᵉʳ), [[issue-29]] (escalade 2ᵉ), [[issue-41]] (escalade 4ᵉ) et la note
composant `pj-thread-name` (slices 2–4 livrées). #73 porte :

- **le point de décision** : le GREEN partial est-il suffisant pour
  considérer la slice 5 comme convergée ? (Verdict grill-me : non, 3
  retouches keeper + 2 capacités helper manquent.)
- **la chaîne de livraison** : qui applique les 3 retouches keeper restantes
  et ajoute `upsert-desc`/`pin` dans le helper ? (Le dev, après le `/ok`.)
- **le verdict de convergence** : après les retouches, le banc
  `tests/test_thread_description.py` passe-t-il 10/10 GREEN ?

### Code (composants impactés)

| composant | état mesuré (2026-10-11) | impact slice 5 |
|---|---|---|
| `pipeline/engine.py` | `DESCRIPTION_MARKER` (L221) + `build_description_lines` (L224) commités | Livré dans le GREEN partial commité |
| `pipeline/pj_room_keeper.py` | `build_description_for_card` (L572), `sync_description` (L695), `sync_all_descriptions` (L799) commités ; appels `pin` (L776) + `upsert-desc` (L896) déjà écrits | 3 tests RED : dédup par marqueur, non-lèvement quand un reader lève, gestion d'erreur `gh pr list` |
| `tests/test_thread_description.py` | 387 lignes, 10 cas, 7 GREEN / 3 RED | Banc qui gèle le contrat `contrat-5` |
| `skills/gh-kanban-bridge/scripts/discord_thread.py` | Commandes `create`/`send`/`threads`/`rename` seulement | **`upsert-desc` + `pin` à ajouter** |

Le **core pur** à préserver : `build_description_lines` (composition pure :
issue_url, branch, pr_url → list[str], 0 réseau) et
`build_description_for_card` (sources injectées). L'écriture du message et de
l'épingle passent par l'adapter injecté `write_message` / le helper Discord.

## Lecture SDD (spec-driven)

La spec est le body de l'issue **#19** (arbitrages `Q1=1a`, `Q2=2b`,
`Q3=d`) ; l'issue #73 **est** le point à statuer de sa carte
`t_e59e64e5`. Le verdict du grill-me (carte `t_e59e64e5`) fixe le périmètre :
l'unique action = s'assurer que les 10 tests passent et pousser sur
`wt/issue-19-discord-thread-title-description`. La doc décrit le livré :
ici le « livré » attendu est le GREEN 10/10 (3 retouches keeper +
`upsert-desc`/`pin`) ; jusqu'au `/ok`, l'état mesuré est 7/10 GREEN + helper
incomplet + commit GREEN original perdu.

## Lecture DDD (bounded contexts, agrégats, événements)

- **Bounded context traversé** : *convergence / livraison* — chevauche
  *développement* (slice 5 de #19) et *décision humaine* (l'escalade
  #27→#29→#45→#41→#73), sans en être un nouveau : c'est la **jonction**
  entre les deux.
- **Agrégat racine** : la **carte `t_e59e64e5`** (invariant : elle ne repart
  en `ready` que sur un `/ok` portant sa ligne canonique
  `carte: pj-hermes-workflow/t_e59e64e5`). L'**issue #73** est l'objet de
  décision qui la matérialise.
- **Value objects** : le **branch head SHA** (`5c723a6` mesuré) ; le **banc
  7/10** (état de convergence partiel) ; l'**idempotency-key** `gh-issue-73` ;
  le verdict grill-me (`PROTOTYPE: non, AMBIGU: aucune`).
- **Domain events** : `/ok` humain sur l'issue #73 → unblock de
  `t_e59e64e5` → re-spawn (grill-me reformule) → dev applique les 3 retouches
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
issue #73 (GitHub, label decision + kanban, parent #31, carte t_e59e64e5)
  → commentaire /ok humain (surface de décision)
  → unblock de t_e59e64e5 (kanban)
  → re-spawn grill-me → reformulation → dev applique 3 retouches keeper + upsert-desc/pin
  → banc test_thread_description.py 10/10 GREEN (preuve de convergence)
  → doc → doc-review → PR → merge
```

Deux frontières : **GitHub ↔ kanban** (décision → effet) et
**git ↔ worktree partagé** (preuve de livraison). Le point de fragilité n'est
pas l'appel réseau mais **la couverture commit-à-commit** : un travail
commité mais functionnellement incomplet (7/10) n'est pas un travail livré.

## État mesuré (2026-10-11, rejouable)

- `wt/issue-19-discord-thread-title-description` :
  - **local** (worktree `t_c22a7e74`) = `5c723a6`.
  - **remote** = `5c723a6` (en sync, `git fetch` vérifié).
- `git cat-file -t 6661362` → **fatal : Not a valid object name**
  (définitivement absent).
- `DESCRIPTION_MARKER`/`build_description*`/`sync_description*` commités
  (voir lignes ci-dessus) ; `git status --short` propre sur ces fichiers.
- `upsert-desc`/`pin` : **absents** de
  `skills/gh-kanban-bridge/scripts/discord_thread.py` (grep : 0 hit).
- Banc `tests/test_thread_description.py` : **7 GREEN / 3 RED** (rejoué par
  exécution le 2026-10-11).
- `pj_docs_lint.py` sur `/home/elix/pj-repos/hermes-workflow` → `exit=0`
  (preuve collée dans le commentaire de carte).

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
    (épingle du message) ; le keeper les appelle déjà (L776, L896).
- **Vault** : à la convergence, la slice 5 gagnera sa note composant et le
  MOC `docs/architecture/README.md` sera mis à jour par la carte `doc-k` —
  hors périmètre de cette décision.

## Non tranché (et qui doit le rester ici)

Le cadrage ne tranche **pas** :
1. **La voie de re-pousée du GREEN slice-5** (re-run dev-5 / reprise
   manuelle / autre) — l'arbitrage humain, verdict grill-me : 0 ambiguïté
   bloquante mais la décision opérationnelle reste à l'humain.
2. **La cause de la perte de `6661362`** (force-push ? clôture avant push ?)
   — levée par mesure git (ambiguïté 1 de la carte), documentée, pas tranchée
   ici.
3. **Le contenu exact des 3 retouches keeper** — porté par le dev après le
   `/ok` (le banc définit le contrat, pas le cadrage).
4. **La forme des capacités `upsert-desc`/`pin`** — porté par le dev ; le
   banc ne les teste pas directement (le helper est un adapter, injecté).
5. **La publication live des copies `~/.hermes/scripts/`** (divergence D2
   déclarée dans le handoff `dev-5`) — opération de fin de graphe contrôlée
   par identité, hors périmètre de cette décision.

Ces points sont **documentés**, pas décidés ici.
