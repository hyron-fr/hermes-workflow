---
type: context
status: draft
tags: [architecture, decision, escalation, worktree, pipeline, cadrage]
issues: [62]
---

# Cadrage architectural — issue #62 « t1 worktree »

## Positionnement (cadre exact)

L'issue **#62** est un **ticket de décision** (labels `kanban` + `decision`) qui
sert de point à statuer pour la carte **`t_df6f3ff7`** du board
`pj-hermes-workflow`. Le corps de l'issue indique :

> **Point à statuer** sur la carte `t_df6f3ff7` (board `pj-hermes-workflow`),
> bloquée sur le ticket #34.
>
> **Pour trancher**, commentez cette issue avec le jeton `/ok` en **premier
> élément** : la carte est débloquée et repart en file.

L'issue #62 est le **miroir kanban** de la carte racine `t_df6f3ff7`, qui elle-même
pointe vers le ticket GitHub **#34** (lui-même escalade de la chaîne **conv-5** du
chantier **#19** « Discord thread title and description update »).

**Ce que la décision débloque** : le jeton `/ok` posé en tête de commentaire sur
l'issue #62 débloque la carte `t_df6f3ff7` (statut `todo` → `ready`), permettant au
pipeline de repartir. Tout autre commentaire est traité comme une demande
d'éclaircissement et ne débloque rien.

### Chaîne de contexte

| Maillon | Description |
|---|---|
| Chantier #19 | « Discord thread title and description update » (5 slices) |
| Slice 5 / conv-5 | Convergence du bloc Description épinglée |
| #27 → #28 → #30 → #31 → #34 | Escalades successives conv-5 |
| **#34** | Point à statuer sur la carte `t_2678f842` (t1 worktree, bloquée, crash run 293) |
| **#62** | **Miroir kanban de #34** — point à statuer sur `t_df6f3ff7` |

Le GREEN dev-5 original (`6661362`) est définitivement perdu (absent de toutes
refs). Le travail effectif débloqué par le `/ok` est le re-spawn de la chaîne
pipeline pour compléter la slice 5.

## Croisement infrastructure / fonctionnel / code

### Infrastructure (frontières traversées)

- **GitHub** — surface de décision : commentaire `/ok` sur l'issue #62.
  Adapter : `gh` CLI, lu par le pont `gh-kanban-bridge`.
- **Kanban Hermes** — source de vérité de l'état des cartes. L'effet est
  `unblock` + re-enfilement de `t_df6f3ff7`.
- **Git / worktree** — surface de livraison : la branche
  `wt/issue-19-discord-thread-title-description` (worktree `t_c22a7e74`) est la
  preuve de livraison de la slice 5. État mesuré (2026-10-11) : tip `9fcd207`,
  banc 7/10 (3 RED).
- **Aucun nouveau port** : les trois surfaces (GitHub, kanban, git) existent déjà.
  L'issue #62 réutilise la boucle de décision #5 ([[pj-decision]], [[pj-escalate]],
  [[pj-notify]]).

### Fonctionnel (capacité traversée)

La capacité traversée est **décision humaine / déblocage de pipeline** (pas une
fonctionnalité nouvelle). L'issue #62 matérialise le point de décision qui permet
au pipeline de poursuivre la slice 5 du chantier #19.

- **Le point de décision** : le `/ok` débloque `t_df6f3ff7`.
- **La chaîne de livraison** : après déblocage, le pipeline re-spawn
  (grill-me → spec → dev → convergence → doc → review → PR → merge).
- **Le verdict de convergence** : le banc `tests/test_thread_description.py`
  doit passer 10/10 GREEN avant merge.

### Code (composants impactés)

| composant | état mesuré (2026-10-11) | impact |
|---|---|---|
| `pipeline/pj_decision.py` ([[pj-decision]]) | Present on `origin/dev` | Pas de changement — boucle #5 réutilisée |
| `pipeline/pj_escalate.py` ([[pj-escalate]]) | Present on `origin/dev` | Pas de changement |
| `pipeline/pj_notify.py` ([[pj-notify]]) | Present on `origin/dev` | Pas de changement |
| `pipeline/pj_room_keeper.py` | 3 fixes keeper manquants (banc 7/10) | Débloqué par le pipeline post-`/ok` |
| `skills/gh-kanban-bridge/scripts/discord_thread.py` | `upsert-desc` / `pin` absents | Ajout porté par le dev après `/ok` |
| `tests/test_thread_description.py` | 10 cas, 7 GREEN / 3 RED | Banc qui gèle le contrat `contrat-5` |
| `pipeline/engine.py` | `DESCRIPTION_MARKER` + `build_description_lines` présents | Livré dans le GREEN partial |

## Lecture SDD (spec-driven)

La spec de référence est le body de l'issue **#19** (arbitrages `Q1=1a`, `Q2=2b`,
`Q3=d`). L'issue #62 **est** le point à statuer de la carte `t_df6f3ff7`. Le
livrable attendu n'est pas un code mais **l'état de convergence de la slice 5** :
le banc 10/10 GREEN. La doc décrit le livré ; ici le « livré » est l'état de
convergence, pas un artefact nouveau.

## Lecture DDD (bounded contexts, agrégats, événements)

- **Bounded context traversé** : *décision humaine / pipeline* — chevauche
  *convergence/livraison* (slice 5 de #19) et *décision humaine* (l'escalade
  #34→#62), sans en être un nouveau : c'est la **jonction** entre les deux.
- **Agrégat racine** : la **carte `t_df6f3ff7`** (invariant : elle ne repart en
  `ready` que sur un `/ok` portant sa ligne canonique
  `carte: pj-hermes-workflow/t_df6f3ff7`). L'**issue #62** est l'objet de décision
  qui la matérialise.
- **Value objects** : l'**idempotency-key** `gh-issue-62` ; le **branch head SHA**
  (`9fcd207` mesuré) ; le **banc 7/10** (état de convergence partiel).
- **Domain events** : `/ok` humain sur l'issue #62 → unblock de `t_df6f3ff7` →
  re-spawn pipeline → dev applique les 3 fixes keeper + ajoute `upsert-desc`/`pin`
  → banc 10/10 GREEN → convergence → doc → doc-review → PR → merge.

## Lecture TDD (contrats testables)

Le contrat testable est le **banc `tests/test_thread_description.py`** (10 cas),
rejouable sans Discord ni réseau (sources injectées) :

- `build_description_lines(issue_url, branch, pr_url, log=print) -> list[str]`
  — composition pure, 4 lignes, omission des `None`/vides (4 cas GREEN).
- `keeper.build_description_for_card(card, *, …, specs_reader, pr_reader,
  issue_url_lookup)` — assemblage des sources injectées (2 cas GREEN,
  1 cas RED : le reader qui lève ne doit pas tuer le tick).
- `keeper.sync_description(cards, *, fetch_messages, write_message, log=None)`
  — écrivain best-effort : dédup par marqueur, `edit` jamais second post
  (1 cas RED : un seul message épinglé mis à jour pas dupliqué).
- **1 cas RED supplémentaire** : `test_erreur_gh_pr_list_en_erreur_ligne_omise_tracee_pas_exception`
  — gestion d'erreur quand `gh pr list` lève (la ligne PR est omise mais tracée,
  pas d'exception).

Les **3 cas RED** sont les critères d'acceptation restants de la slice 5 ; leur
passage GREEN est la preuve de convergence.

## Lecture hexagonale (le core reste pur)

Le **core pur** : `build_description_lines` (fonction pure : issue_url, branch,
pr_url → list[str], 0 réseau, 0 horloge, 0 aléa) et
`build_description_for_card` (sources injectées, 0 réseau). L'écriture du message
épinglé et de l'épingle passe par le helper `discord_thread.py` (adapter REST, hors
core). Le contrat d'interface (marqueur `[description]`, `sync_description`,
`sync_all_descriptions`) est testable sans Discord : les sources et l'adaptateur
sont injectés.

La frontière à respecter : **la description est une lecture d'état**
(gh/git/blackboard) résolue **hors** du core, puis injectée dans le formateur pur.
Jamais l'inverse : le formateur ne lit pas le réseau.

## Frontières traversées (résumé)

```
issue #62 (GitHub, labels kanban + decision, parent #34)
  → commentaire /ok humain (surface de décision)
  → unblock de t_df6f3ff7 (kanban)
  → re-spawn pipeline → dev applique 3 fixes keeper + upsert-desc/pin
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
  - **local** (worktree `t_c22a7e74`) = `9fcd207` (docs cadrage #73).
  - **remote** = `9fcd207` (en sync).
  - `git status --short` : `?? docs/architecture/context/issue-27.md`,
    `?? docs/architecture/context/issue-29.md` (notes non commitées).
- `git cat-file -t 6661362` → **fatal : Not a valid object name**
  (définitivement absent).
- `grep DESCRIPTION_MARKER|build_description` sur `pipeline/` → **présents** dans
  `pipeline/engine.py` et `pipeline/pj_room_keeper.py` (GREEN partial livré).
- `grep upsert-desc|pin` sur `skills/gh-kanban-bridge/scripts/discord_thread.py`
  → **0 hit** (capacité non livrée).
- Banc `tests/test_thread_description.py` : **7/10 GREEN, 3 RED** (mesuré
  2026-10-11).
- `pj_docs_lint.py` sur `/home/elix/pj-repos/hermes-workflow` → `exit=0`.

## Composants impactés (résumé)

- **Décision (cette issue)** : `pipeline/pj_decision.py` ([[pj-decision]]) +
  `pipeline/pj_escalate.py` / `pipeline/pj_notify.py` ([[pj-notify]]) — la
  boucle #5, aucun changement de code.
- **Travail débloqué (slice 5 de #19, à compléter)** :
  - `pipeline/pj_room_keeper.py` — 3 fixes keeper.
  - `skills/gh-kanban-bridge/scripts/discord_thread.py` — ajout
    `upsert-desc` + `pin`.
- **Vault** : la slice 5 gagnera sa note composant et le MOC
  `docs/architecture/README.md` sera mis à jour par la carte `doc-k` —
  hors périmètre de cette décision.

## Non tranché (et qui doit le rester ici)

Le cadrage ne tranche **pas** :
1. **Le contenu exact des 3 fixes keeper** — porté par le dev après le
   `/ok` (le banc définit le contrat, pas le cadrage).
2. **La forme des capacités `upsert-desc`/`pin`** — porté par le dev ; le
   banc ne les teste pas directement (le helper est un adapter, injecté).
3. **Le motif de blocage de la carte `t_df6f3ff7`** — déclaré « (non
   détaillé) » sur l'issue #62 ; le détail est sur la carte elle-même. Le
   cadrage décrit l'état mesuré, ne reformule pas le motif.
4. **La publication live des copies `~/.hermes/scripts/`** (divergence D2
   déclarée dans le handoff `dev-5`) — opération de fin de graphe contrôlée
   par identité, hors périmètre de cette décision.

Ces points sont **documentés**, pas décidés ici.
