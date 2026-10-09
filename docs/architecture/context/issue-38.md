---
type: context
status: draft
tags: [architecture, decision, escalation, recycle, convergence, slice-5, description-epinglee, cadrage]
issues: [38]
---

# Cadrage architectural — issue #38 « t3 grill-me » (miroir #27/#29, carte `t_a444c5ff`)

## Positionnement (cadre exact)

L'issue **#38** (titre « t3 grill-me », labels `decision` + `kanban`,
`idempotency-key gh-issue-38`, importée dans le kanban comme tâche
`t_40bc08d6` assignée à `pj-master`) est la **troisième importation du même
point à statuer conv-5** : le blocage de la carte **`t_a444c5ff`** (« t3
grill-me » sur l'issue #29, assignée à `pj-master`, board
`pj-hermes-workflow`), bloquée sur le chantier **#19** (« Discord thread title
and description update ») — elle-même escalade de la carte conv-5
`slice 5/5`.

Chaîne des escalades du même point (mesurée, 2026-10-09) :

| # | Issue | Carte bloquée | État |
|---|---|---|---|
| 1 | #27 | `t_f725879f` (slice 5/5, `pj-test`) | GREEN dev-5 `6661362` perdu, banc 10/10 RED |
| 2 | #29 | `t_f725879f` (slice 5/5, `pj-test`) | Même point, ré-importé par le pont (`gh-issue-29`) |
| **3** | **#38** | **`t_a444c5ff`** (t3 grill-me, `pj-master`) | **Miroir : trancher le blocage conv-5, 2 questions à l'humain** |

Le **point à statuer** (tel quel, du body de #38) : trancher le blocage
conv-5 — GREEN dev-5 / commit `6661362` absent du worktree #19, banc 10/10 RED
rejoué — avec **2 questions ouvertes pour l'humain** (thread Discord de #19) :

1. Comment restaurer le GREEN dev-5 — **ré-exécuter dev-5** vs **re-push du
   commit existant** vs **abandon slice 5** ?
2. #29 doit-elle porter le **débloque ET la re-convergence** ?

**Verdict grill-me** (commenté sur `t_a444c5ff`) : `PROTOTYPE: non`. La carte
est **`blocked` (needs_input)** depuis le 2026-10-03 ; à re-soumettre quand
l'humain a répondu, puis `unblock` → reformulation.

### Ce que t2 (mémoire) a déjà levé

Le handoff de la carte `t2` mémoire (`t_28522e01`) tranche la **question 1**
sur le volet « re-push du commit existant » : les commits de la branche
`wt/issue-19-restore-green-5` (tip `009f0a7`) sont **déjà ancestors de
`origin/dev`** — le contenu de ce re-push est déjà dans `dev`. La question se
réduit donc à **ré-exécuter dev-5 vs abandonner la slice 5**. La **question 2**
(débloque ET re-convergence) reste à trancher par l'humain.

Le présent cadrage **ne tranche pas** : il positionne ce point à statuer dans
l'architecture existante, identifie les composants impactés, et fixe les
critères de décision. Le verdict humain (`/ok` en premier élément sur l'issue
#38) débloque la carte ; le re-push effectif ou la ré-exécution suit, porté
par le dev, jamais par ce cadrage.

## Croisement infrastructure / fonctionnel / code

### Infrastructure (frontières traversées)

- **GitHub** — surface de décision (commentaire `/ok` en premier élément sur
  l'issue #38, `idempotency-key gh-issue-38`) et surface de preuve (commits de
  la branche, PR éventuelle). Le **gate de couverture** du pont
  (commentaire `<!-- pj-coverage-gate -->` du 2026-10-03) a suspendu l'import
  de #38 en identifiant qu'il recouvrait du **travail en vol** (#19, #29 :
  « PR ouverte / graphe déjà construit »), et a posé la bifurcation
  *rattacher au travail en vol* vs *nouvelle tâche assumée* (label `kanban`).
  Le label `kanban` a été posé : le pont a importé #38 comme `t_40bc08d6`
  (commentaire du 2026-10-08).
- **Kanban Hermes** — source de vérité de l'état des cartes : `t_a444c5ff`
  (t3 grill-me) en `blocked` porte le point à statuer ; `t_40bc08d6` (racine
  importée de #38) est en attente de ses parents `t1..t5` + `t3b` (le présent
  cadrage `t_c6963c19` en fait partie).
- **Git / worktree partagé** — surface de livraison : le branch head de
  `wt/issue-19-discord-thread-title-description` est la **preuve de livraison**
  de la slice 5. État mesuré 2026-10-09 : **tip `dbf73da`** (après les notes
  de cadrage #41/#45 et le commit `55e6659` « conv-audit: baseline état
  courant worktree (GREEN partial, banc 7/10) »).

### Fonctionnel (capacité traversée)

La capacité traversée est **convergence + preuve de livraison**, pas une
fonctionnalité nouvelle. Le chantier #19 est déjà cadré par la note
`issue-19` (worktree partagé, slices 1–4 livrées) et par les notes
`issue-27` / `issue-29` (escalades 1 et 2 du même point). #38 porte :

- **le point de décision** : comment restaurer le GREEN dev-5 (Q1) et si le
  ticket porte le débloque ET la re-convergence (Q2) ;
- **la chaîne de livraison** : après `/ok`, qui ré-exécute la dev-5 (ou
  abandonne la slice 5) et re-pousse sur
  `wt/issue-19-discord-thread-title-description` ?
- **le verdict de convergence** : après le re-push, le banc
  `tests/test_thread_description.py` passe-t-il 10/10 GREEN ?

### Code (composants impactés)

État **mesuré le 2026-10-09** (worktree partagé `t_c22a7e74`, tip `dbf73da`
= remote en sync) :

| composant | état mesuré | impact slice 5 |
|---|---|---|
| `pipeline/engine.py` | `DESCRIPTION_MARKER` + `build_description_lines` **présents** (4 hits grep) | Livré dans le GREEN partial |
| `pipeline/pj_room_keeper.py` | `build_description_for_card`, `sync_description`, `sync_all_descriptions` **présents** (4 hits grep) | GREEN partial ; retouches nommées dans la note `issue-41` (banc 7/10) |
| `tests/test_thread_description.py` | 10 cas ; **7 GREEN / 3 RED** (état du baseline `55e6659`, mesuré 2026-10-08) | Banc qui gèle le contrat `contrat-5` |
| `skills/gh-kanban-bridge/scripts/discord_thread.py` | **0 hit** `upsert-desc` / `pin` | Capacités à ajouter (adapter REST) |
| `pipeline/pj_decision.py` | Core pur de décision `/ok` (issue #5, slice 4) — jeton `/ok` en tête ou après ≤ 1 amorce, argument inerte, péremption au re-blocage | Boucle de décision : aucun changement de code attendu |
| `pipeline/pj_escalate.py` + `pipeline/pj_notify.py` | Boucle #5 (escalade + notification 2 niveaux) | Aucun changement de code attendu |

> **Divergence à noter pour la suite** : la carte `t2` (mémoire) et le body de
> #38 citent le banc **10/10 RED** (état initial post-perte du GREEN). Le
> baseline `55e6659` (2026-10-08) et la note `issue-41` (tip `dbf73da`)
> mesurent **7/10 (3 RED)** — le GREEN partial a été réintégré dans le
> worktree depuis. Le **contrat testable** reste le même (le banc
> `test_thread_description.py`, 10 cas) ; seul l'état courant a changé.

## Lecture SDD (spec-driven)

La spec est le **body de l'issue #38** (miroir du point à statuer de
`t_a444c5ff`) et, en amont, les arbitrages de #19 (`Q1=1a`, `Q2=2b`, `Q3=d` —
voir la note `issue-19`). Le livrable de #38 n'est **pas** un code, mais
**la décision humaine** (Q1 : ré-exécuter vs re-pousser vs abandon ; Q2 :
portée du ticket). Le verdict `PROTOTYPE: non` fixe le périmètre : pas
d'artefact perceptible à valider. La doc décrit ce qui existe aujourd'hui
(le GREEN partial sur la branche, le banc 7/10, la boucle de décision #5) —
pas une intention.

## Lecture DDD (bounded contexts, agrégats, événements)

- **Bounded context** : *convergence / livraison* — chevauche *développement*
  (slice 5 de #19) et *décision humaine* (l'escalade #27→#29→#38), sans en
  être un nouveau : c'est la **jonction** entre les deux.
- **Agrégat racine** : la **carte `t_a444c5ff`** (invariant : elle ne repart
  en `ready` que sur un `/ok` humain portant sa ligne canonique
  `carte: pj-hermes-workflow/t_a444c5ff`). L'**issue #38** est l'objet de
  décision qui la matérialise (miroir de #29).
- **Value objects** : le **branch head SHA** (`dbf73da` mesuré 2026-10-09) ;
  le **SHA perdu** (`6661362`, définitivement absent du dépôt local et du
  remote) ; l'**idempotency-key** `gh-issue-38` ; le verdict grill-me
  (`PROTOTYPE: non`).
- **Domain events** : `/ok` humain sur l'issue #38 → unblock de
  `t_a444c5ff` → reformulation (grill-me) → dev ré-exécute la slice 5 (ou
  abandon) → re-push sur `wt/issue-19-discord-thread-title-description` →
  banc `test_thread_description.py` 10/10 GREEN (preuve de convergence) →
  doc → doc-review → PR → merge.

## Lecture TDD (contrats testables)

Le contrat testable de #38 n'est pas un code nouveau, mais **un invariant
mesurable déjà gelé** :

- **Le banc `tests/test_thread_description.py` (10 cas) passe 10/10 GREEN** —
  rejouable sans Discord ni réseau (sources et adaptateurs injectés) ; c'est
  la **preuve de convergence** de la slice 5.
- **L'API slice 5 est présente et testable** : `DESCRIPTION_MARKER =
  "[description]"`, `build_description_lines(issue_url, branch, pr_url, log)
  -> list[str]` (composition pure), `keeper.build_description_for_card`,
  `keeper.sync_description`, `keeper.sync_all_descriptions`.
- **L'état courant du banc** (7/10 GREEN, 3 RED mesurés dans le baseline
  `55e6659`) est un **value object** rejouable ; son passage à 10/10 est le
  critère d'acceptation de la re-convergence.

Ces invariants sont mesurables par `pj_graphwatch` (couverture
commit-à-commit + chemin réel du worktree) et par le pont de couverture
(`pj_coverage_gate`) qui a identifié #38 comme recouvrant #19 et #29.

## Lecture hexagonale (le core reste pur)

Le **core pur** de la slice 5 : `build_description_lines` (fonction pure :
issue_url, branch, pr_url → list[str], 0 réseau, 0 horloge, 0 aléa) et
`build_description_for_card` (sources injectées, 0 réseau). L'écriture du
message épinglé et de l'épingle passe par le helper `discord_thread.py`
(adapter REST, hors core) — les capacités `upsert-desc` / `pin` y seront
ajoutées, jamais dans le core.

La frontière à respecter : **la description est une lecture d'état**
(gh/git/blackboard) résolue **hors** du core, puis injectée dans le formateur
pur. Jamais l'inverse : le formateur ne lit pas le réseau. Le core de
décision `pj_decision.py` (issue #5) reste inchangé : `decision_from_comment`
calcule, l'appelant applique.

## Frontières traversées (résumé)

```
issue #38 (GitHub, labels decision + kanban, idempotency-key gh-issue-38)
  → commentaire /ok humain en premier élément (surface de décision)
  → unblock de t_a444c5ff (kanban)
  → reformulation grill-me → dev ré-exécute la slice 5 (ou abandon)
  → re-push sur wt/issue-19-discord-thread-title-description (git)
  → banc test_thread_description.py 10/10 GREEN (preuve de convergence)
  → doc → doc-review → PR → merge
```

Deux frontières : **GitHub ↔ kanban** (décision → effet, via le pont
`gh-kanban-bridge` et le gate de couverture `pj_coverage_gate`) et
**git ↔ worktree partagé** (preuve de livraison). Le point de fragilité n'est
pas l'appel réseau mais **la couverture commit-à-commit** : un commit absent
du branch head est un travail non livré, quel que soit le handoff du worker ;
ici le commit `6661362` est définitivement absent (dépôt local et remote),
mais le GREEN partial a été réintégré par le baseline `55e6659`.

## Composants impactés (résumé)

- **Décision (cette issue)** : `pipeline/pj_decision.py` ([[pj-decision]]) +
  `pipeline/pj_escalate.py` / `pipeline/pj_notify.py` ([[pj-notify]]) — la
  boucle #5, **aucun changement de code** attendu.
- **Travail débloqué (slice 5 de #19, à compléter après le `/ok`)** :
  - `pipeline/pj_room_keeper.py` — retouches nommées dans la note
    `issue-41` (banc 7/10 : dédup du message épinglé, non-lèvement quand un
    reader de source lève, journalisation).
  - `skills/gh-kanban-bridge/scripts/discord_thread.py` — ajout des
    capacités `upsert-desc` (édition du message du fil) et `pin` (épingle du
    message).
- **Preuve** : `tests/test_thread_description.py` (banc contrat-5, 10 cas).
- **Vault** : la note de cadrage (la présente) + mise à jour du MOC
  `docs/architecture/README.md` ; à la convergence, la slice 5 gagnera sa
  note composant portée par la carte `doc-k` — hors périmètre de cette
  décision.

## Non tranché (et qui doit le rester ici)

Le cadrage ne tranche **pas** :
1. **Q1 — Ré-exécuter dev-5 vs abandonner la slice 5** : arbitrage humain
   (le re-push du commit existant est exclu : `6661362` est définitivement
   absent, et le contenu de `wt/issue-19-restore-green-5` est déjà dans
   `origin/dev`).
2. **Q2 — Portée du ticket** : #38/#29 porte-t-il le débloque ET la
   re-convergence ?
3. **Le contenu exact des retouches keeper et la forme des capacités
   `upsert-desc`/`pin`** : portés par le dev après le `/ok` (le banc définit
   le contrat, pas le cadrage).

Ces points sont **documentés**, pas décidés ici.

## État mesuré (2026-10-09, rejouable)

- `origin/dev` = `2027333` (docs(cadrage): issue #29 — slice 5/5 convergence).
- `wt/issue-19-discord-thread-title-description` :
  - **local** (worktree partagé `t_c22a7e74`) = `dbf73da` (docs(issue-41):
    corrige l'écart) ;
  - **remote** = `dbf73da` (en sync, relu 2026-10-09).
- `wt/issue-19-restore-green-5` (worktree `t_4d471dce`) = `009f0a7` —
  **déjà ancêtre de `origin/dev`**.
- `6661362` (GREEN dev-5 original) : **définitivement absent**
  (`git cat-file -t 6661362` → `fatal: Not a valid object name`, vérifié sur
  le dépôt local et le remote 2026-10-09).
- GREEN partial **présent** dans `pipeline/engine.py`
  (`DESCRIPTION_MARKER`, `build_description_lines`) et
  `pipeline/pj_room_keeper.py` (`build_description_for_card`,
  `sync_description`, `sync_all_descriptions`) sur `dbf73da`.
- `upsert-desc` / `pin` : **0 hit** dans
  `skills/gh-kanban-bridge/scripts/discord_thread.py` (capacité non livrée).
- Banc `tests/test_thread_description.py` : 10 cas ; **7/10 GREEN, 3 RED**
  (baseline `55e6659`, mesuré 2026-10-08 ; état à rejouer).
- Carte `t_a444c5ff` : `blocked` (needs_input) depuis le 2026-10-03, verdict
  `PROTOTYPE: non`, 2 questions ouvertes pour l'humain.
- `pj_docs_lint.py` sur `/home/elix/pj-repos/hermes-workflow` → `exit=0`.
