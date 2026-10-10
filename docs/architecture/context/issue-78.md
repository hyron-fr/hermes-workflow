---
type: context
status: draft
tags: [architecture, decision, escalation, conv-5, slice-5, description-epinglee, rattachement, cadrage]
issues: [78]
---

# Cadrage architectural — issue #78 « t3 grill-me » (6ᵉ escalade conv-5, échelon redondant)

## Positionnement (cadre exact)

L'issue **#78** (labels `decision` + `kanban`, `idempotency-key gh-issue-78`,
parent **#43**, ouverte le 2026-10-08) est un ticket de **DÉCISION** du
pipeline : « Point à statuer » sur la carte **`t_1d781414`** (board
`pj-hermes-workflow`), elle-même bloquée depuis le 2026-10-08 sur le ticket
**#43**.

**Verdict du t3 #43 (carte `t_1d781414`, mesuré 08/10 13 h CEST)** :
0 question ouverte (3 ambiguïtés toutes levées par mesure),
`PROTOTYPE: non / AMBIGU: aucune / ARTEFACT: aucun`. **Issue #43 est un
échelon redondant, rattachable à #45** (flux opérationnel, dev-k prêt). Le
`/ok` porte sur #45 (thread Discord `1557708797487882291`). Au go : t4
produit la spec de rattachement + fermeture de `t_64c54708`.

L'enfant GitHub de #78 est **#88** (« t3 grill-me », parent #78), importée
le 2026-10-08 21:26 dans le kanban comme carte racine **`t_9c2c7b8b`**
(parents : `t_1c5b3b6b`, `t_79485336`, `t_6df79d04`, `t_3d16c640`,
`t_26e05ccb`, `t_a898ca6a` — le graphe t1..t5 + t3b de l'issue #78).

C'est la **sixième escalade conv-5** de la chaîne :

| # | Issue | Carte | Motif |
|---|---|---|---|
| 1ᵉʳ | #27 | `t_f725879f` (conv-5) | GREEN dev-5 `6661362` perdu, banc 10/10 RED |
| 2ᵉ | #29 | `t_f725879f` (conv-5) | Même point, ré-importé par le pont de couverture |
| 3ᵉ | #45 | `t_854f0f77` (dev GREEN RECYCLE) | GREEN partial présent (7/10), 3 fixes keeper + `upsert-desc`/`pin` manquants |
| 4ᵉ | #41 | `t_3f7e0be4` (t3 grill-me) | Quadrante + verdict produits ; Q1 posée à l'humain |
| 5ᵉ | #81 | `t_c0e5ce5a` (t3 grill-me) | `/ok` débloque la carte |
| **6ᵉ** | **#78** | **`t_9c2c7b8b` (carte racine importée)** | **Échelon redondant : le point à statuer est déjà statué — le `/ok` rattaché à #45 suffit** |

Le **point à statuer** de #78 n'est plus qu'un pointeur vers un verdict
déjà rendu : la carte `t_1d781414` est **blocked** avec le motif « Attente
réponse humaine : t3 #43 qualifié — 0 question ouverte ». Toute la substance
de la décision (re-livrer le GREEN slice 5/5 via le flux #45) est portée par
**l'issue #45 et sa room Discord**, pas par #78.

## Ce que la décision débloque

Le jeton `/ok` commenté **en premier élément** sur l'issue #78 débloque la
carte `t_9c2c7b8b` (carte racine importée) et la repart en file. Toute
autre réponse est une demande d'éclaircissement et ne débloque rien.
L'effet opérationnel attendu : le flux **rattachement** — t4 produit la spec
de rattachement de #43/#78 vers #45, fermeture de `t_64c54708` (grill-me
obsolète), et poursuite de la livraison slice 5 par le flux #45 (dev-k).
Boucle de décision implémentée : `pipeline/pj_decision.py`
([[pj-decision]]) + `pipeline/pj_escalate.py` / `pipeline/pj_notify.py`
([[pj-notify]]) — **aucun changement de code n'est attendu de cette issue**.

## État mesuré au 2026-10-10 (rejouable)

Mesures exécutées ce jour, sur le dépôt `/home/elix/pj-repos/hermes-workflow`
et son worktree partagé `t_c22a7e74` (branche
`wt/issue-19-discord-thread-title-description`) :

- `origin/dev` = `2027333` (docs(cadrage) issue #29).
- Worktree partagé `t_c22a7e74` :
  - HEAD = `b846a28` (docs(cadrage) issue #80) ;
  - `git status --short` : ` M pipeline/pj_room_keeper.py` + `?? diag2.py`
    (fix keeper non-commité + orphelin de diagnostic — identique à ce qui a
    fait l'objet des escalades précédentes) ;
  - `tests/test_thread_description.py` : **10 cas** ;
  - banc rejoué (`uv run --with pytest --with pyyaml --with langgraph
    --with langchain-core python -m pytest
    tests/test_thread_description.py -p no:randomly`) : **3 failed, 7 passed
    en 0,17 s** — les 3 rouges nommés :
    - `test_nominal_un_seul_message_epingle_mis_a_jour_pas_duplique`
    - `test_erreur_gh_pr_list_en_erreur_ligne_omise_tracee_pas_exception`
    - `test_erreur_le_reader_de_source_qui_leve_ne_tue_pas_le_tick`
- `git cat-file -t 6661362` → `fatal: Not a valid object name` (le GREEN
  original reste **définitivement absent** du dépôt et du remote).
- `pipeline/engine.py` L221–228 : `DESCRIPTION_MARKER = "[description]"` +
  `build_description_lines(...)` — **présents** (GREEN partial dans l'arbre).
- `pipeline/pj_room_keeper.py` : `build_description_for_card` (L572),
  `sync_description` (L715), `sync_all_descriptions` (L829) — **présents**.
- `skills/gh-kanban-bridge/scripts/discord_thread.py` : grep `upsert-desc`
  → **0 hit** (capacité non livrée).
- `pj_docs_lint.py` sur le dépôt → `exit=0`.

L'état de convergence n'a pas bougé depuis le 08/10 : le GREEN partial
persiste (banc 7/10), le GREEN original est toujours perdu, et les capacités
`upsert-desc`/`pin` du helper restent absentes. **Le point à statuer de #78
ne change rien à cet état : il redirige vers #45.**

## Croisement infrastructure / fonctionnel / code

### Infrastructure (frontières traversées)

- **GitHub** — surface de décision : commentaire `/ok` sur l'issue #78
  (enfant de #43, parent de #88). Adapter : `gh` CLI, lu par le pont
  ([[pj-bridge-coverage-gate]] : exemption du parent par soustraction,
  label `decision`, ancre des graphes).
- **Kanban Hermes** — source de vérité de l'état des cartes. L'effet est
  `comment` + `unblock` sur `t_9c2c7b8b` (carte racine importée de #78),
  invoqués en `subprocess` par le câblage de #5 ([[pj-decision]] :
  `decision_from_comment` calcule, l'appelant applique ; [[pj-notify]] :
  l'enfant notifiée puis fermée, le parent notifié jamais fermé).
- **Git / worktree partagé** — surface de **livraison** (non de décision) :
  le branch head de `wt/issue-19-discord-thread-title-description`
  (worktree `t_c22a7e74`) est la preuve de livraison de la slice 5.
  **#78 ne s'y implante pas** : aucun commit attendu de cette issue ; seul
  le flux rattaché (#45) y committe.
- **Aucun nouveau port** : les trois surfaces (GitHub, kanban, git)
  existent ; l'issue #78 réutilise la boucle de décision #5.

### Fonctionnel (capacité traversée)

La capacité traversée est **décision / convergence** (pas une
fonctionnalité nouvelle). Le chantier **#19** (« Discord thread title and
description update », moitié « Description épinglée », slice 5/5) est déjà
cadré par les notes `issue-27` (escalade 1ᵉʳ), `issue-29` (2ᵉ), `issue-41`
(4ᵉ), `issue-81` (5ᵉ) et la note composant `pj-thread-name` (slices 2–4
livrées). **#78 porte uniquement** :

- **le point de décision** : l'échelon #43 est-il rattachable à #45 ?
  (Verdict t3 #43 : oui, échelon redondant, 0 question ouverte.)
- **la chaîne de livraison** : au `/ok`, t4 produit la spec de
  rattachement + fermeture de `t_64c54708`, et le flux #45 (dev-k) poursuit
  la re-livraison du GREEN.
- **le verdict de convergence** : inchangé — le banc
  `tests/test_thread_description.py` doit passer 10/10 (état mesuré :
  7/10, 3 rouges nommés ci-dessus).

### Code (composants impactés)

| composant | état mesuré (2026-10-10) | impact slice 5 |
|---|---|---|
| `pipeline/engine.py` | `DESCRIPTION_MARKER` + `build_description_lines` présents (L221–228) | Livré dans le GREEN partial |
| `pipeline/pj_room_keeper.py` | `build_description_for_card` (L572), `sync_description` (L715), `sync_all_descriptions` (L829) présents ; fix non-commité dans l'arbre | 3 tests RED : (1) dédup — un seul message épinglé mis à jour pas dupliqué, (2) `gh pr list` en erreur → ligne omise tracée pas exception, (3) reader de source qui lève ne tue pas le tick |
| `tests/test_thread_description.py` | 387 lignes, 10 cas, 7 GREEN / 3 RED | Banc qui gèle le contrat `contrat-5` |
| `skills/gh-kanban-bridge/scripts/discord_thread.py` | Commandes `create`/`send`/`rename`/`threads` seulement | **`upsert-desc` + `pin` à ajouter** |
| `pipeline/pj_decision.py`, `pj_escalate.py`, `pj_notify.py` | Boucle de décision #5 existante | Aucune modification attendue |

Le **core pur** à préserver : `build_description_lines` (composition pure :
issue_url, branch, pr_url → list[str], 0 réseau) et
`build_description_for_card` (sources injectées). L'écriture du message et
de l'épingle passent par l'adapter injecté `write_message` / le helper
Discord.

## Lecture SDD (spec-driven)

La spec est le body de l'issue **#19** (arbitrages `Q1=1a`, `Q2=2b`,
`Q3=d`) ; l'issue #78 **est** le point à statuer de sa carte importée
`t_9c2c7b8b`, qui pointe elle-même la carte `t_1d781414` (verdict déjà
rendu : échelon redondant rattachable à #45). Le périmètre est gelé par le
banc (contrat-5, blackboard racine `t_83401cbb`) : l'unique action de la
slice 5 = s'assurer que les 10 tests passent et pousser sur
`wt/issue-19-discord-thread-title-description`. La doc décrit le livré :
ici le « livré » attendu reste le GREEN 10/10 (3 fixes keeper +
`upsert-desc`/`pin`) ; jusqu'au `/ok`, l'état mesuré est 7/10 GREEN + fix
non-commité + helper incomplet.

## Lecture DDD (bounded contexts, agrégats, événements)

- **Bounded context traversé** : *décision humaine / convergence* —
  chevauche *développement* (slice 5 de #19) sans en être un nouveau :
  c'est la **jonction** entre les deux.
- **Agrégat racine** : la **carte `t_9c2c7b8b`** (invariant : elle ne
  repart en `ready` que sur un `/ok` portant sa ligne canonique
  `carte: pj-hermes-workflow/t_9c2c7b8b`). L'**issue #78** est l'objet de
  décision qui la matérialise ; son enfant #88 est le miroir GitHub de ce
  même point à statuer.
- **Value objects** : le **branch head SHA** (`b846a28` mesuré) ; le **banc
  7/10** (état de convergence partiel, inchangé depuis le 08/10) ;
  l'**idempotency-key** `gh-issue-78` ; le verdict t3 #43
  (`PROTOTYPE: non, AMBIGU: aucune, ARTEFACT: aucun`).
- **Domain events** : `/ok` humain sur l'issue #78 → unblock de
  `t_9c2c7b8b` → t4 produit la spec de rattachement + fermeture de
  `t_64c54708` → flux #45 (dev-k) : dev applique les 3 fixes keeper +
  `upsert-desc`/`pin` → banc 10/10 GREEN → convergence → doc → doc-review →
  PR → merge.

## Lecture TDD (contrats testables)

Le contrat testable est le **banc `tests/test_thread_description.py`**
(387 lignes, 10 cas), rejouable sans Discord ni réseau (sources injectées) :

- `build_description_lines(issue_url, branch, pr_url, log=print) ->
  list[str]` — composition pure, 4 lignes, omission des `None`/vides
  (4 cas GREEN).
- `keeper.build_description_for_card(card, *, …, specs_reader, pr_reader,
  issue_url_lookup)` — assemblage des sources injectées (2 cas GREEN,
  1 cas RED : le reader qui lève ne doit pas tuer le tick).
- `keeper.sync_description(cards, *, fetch_messages, write_message,
  log=None)` — écrivain best-effort : dédup par marqueur, `edit` jamais
  second post (1 cas RED : un seul message épinglé mis à jour pas
  dupliqué).
- 1 cas RED supplémentaire : `test_erreur_gh_pr_list_en_erreur_ligne_omise_tracee_pas_exception`
  — gestion d'erreur quand `gh pr list` lève (la ligne PR est omise mais
  tracée, pas d'exception).

Les **3 cas RED** sont les critères d'acceptation restants de la slice 5 ;
leur passage GREEN est la preuve de convergence. **Aucun nouveau contrat
testable** n'est introduit par #78 (issue de décision, pas de dev).

## Lecture hexagonale (le core reste pur)

Le **core pur** : `build_description_lines` (fonction pure : issue_url,
branch, pr_url → list[str], 0 réseau, 0 horloge, 0 aléa) et
`build_description_for_card` (sources injectées, 0 réseau). L'écriture du
message épinglé et de l'épingle passe par le helper `discord_thread.py`
(adapter REST, hors core). Le contrat d'interface (marqueur
`[description]`, `sync_description`, `sync_all_descriptions`) est testable
sans Discord : les sources et l'adaptateur sont injectés.

La frontière à respecter : **la description est une lecture d'état**
(gh/git/blackboard) résolue **hors** du core, puis injectée dans le
formateur pur. Jamais l'inverse : le formateur ne lit pas le réseau.

## Frontières traversées (résumé)

```
issue #78 (GitHub, labels decision+kanban, parent #43, enfant #88)
  → commentaire /ok humain (surface de décision)
  → unblock de t_9c2c7b8b (carte racine importée, kanban)
  → t4 : spec de rattachement #43/#78 → #45 + fermeture t_64c54708
  → flux #45 (dev-k) : 3 fixes keeper + upsert-desc/pin
  → banc test_thread_description.py 10/10 GREEN (preuve de convergence)
  → doc → doc-review → PR → merge
```

Deux frontières : **GitHub ↔ kanban** (décision → effet) et
**git ↔ worktree partagé** (preuve de livraison, exercée par le flux #45,
pas par #78). Le point de fragilité reste **la couverture
commit-à-commit** : un fix non-commité dans l'arbre n'est pas un travail
livré.

## Composants impactés (résumé)

- **Décision (cette issue)** : `pipeline/pj_decision.py`
  ([[pj-decision]]) + `pipeline/pj_escalate.py` / `pipeline/pj_notify.py`
  ([[pj-notify]]) — la boucle #5, **aucun changement de code**.
- **Travail débloqué (rattaché au flux #45, pas exécuté par #78)** :
  - `pipeline/pj_room_keeper.py` — 3 fixes : (1) déduplication (un seul
    message épinglé mis à jour, pas dupliqué), (2) non-lèvement quand un
    reader de source lève, (3) gestion d'erreur `gh pr list`.
  - `skills/gh-kanban-bridge/scripts/discord_thread.py` — ajout des
    capacités `upsert-desc` (édition du message du fil) et `pin`
    (épingle du message).
- **Vault** : cette note (`issue-78`) référencée depuis le MOC
  `docs/architecture/README.md` ; à la convergence de la slice 5, la note
  composant `pj-thread-name` (slices 2–4) et le MOC seront mis à jour par
  les cartes `doc-k` — hors périmètre de cette décision.

## Non tranché (et qui doit le rester ici)

Le cadrage ne tranche **pas** :
1. **Le contenu exact des 3 fixes keeper** — porté par le dev du flux #45
   après le `/ok` (le banc définit le contrat, pas le cadrage).
2. **La forme des capacités `upsert-desc`/`pin`** — portée par le dev ; le
   banc ne les teste pas directement (le helper est un adapter, injecté).
3. **La publication live des copies `~/.hermes/scripts/`** (divergence D2
   déclarée dans le handoff `dev-5`) — opération de fin de graphe contrôlée
   par identité, hors périmètre de cette décision.

Ces points sont **documentés**, pas décidés ici.
