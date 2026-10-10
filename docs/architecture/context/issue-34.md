---
type: context
status: draft
tags: [architecture, decision, escalation, recycle, convergence, crash-recovery, kanban, cadrage]
issues: [34]
---

# Cadrage architectural — issue #34 « t1 worktree » (miroir de décision, crash recovery)

## Positionnement (cadre exact)

L'issue **#34** (`label: kanban` + `decision`, `idempotency-key gh-issue-34`,
OPEN) est un **ticket de décision** importé par le pont `gh-kanban-bridge`
après le gate de couverture (`pj_coverage_gate`), commenté par
`jeanbaptistepriez` le 2026-10-03 : « Import suspendu — cette issue recouvre
du travail en vol : #29 (PR ouverte / graphe déjà construit) ».

Elle **n'est pas** une tâche de développement ni une escalade autonome :
c'est le **miroir du point à statuer** de la carte **`t_2678f842`**
(« t1 worktree », issue #29, board `pj-hermes-workflow`), bloquée depuis le
**2026-10-03 18:40** après un crash de worker (run 293, `sticky=true`,
`retry_status=ready`).

Le **point à statuer** (mesuré 2026-10-10) :

| fait | preuve |
|---|---|
| `t_2678f842` est **blocked** | `hermes kanban --board pj-hermes-workflow show t_2678f842` → `status: blocked` |
| Motif : crash provider, pas de travail inachevé | run 293 : « Provider temporarily unavailable — Interrupted during API call » ; `git status --short` dans `.worktrees/t_2678f842` → **vide** (worktree propre, HEAD = `009f0a7` = `origin/dev` au moment du fork) |
| Le contenu GREEN dev-5 est **déjà dans `origin/dev`** | `origin/dev @ 2027333` contient le cadrage #29 (commit `2027333`, 1 commit au-dessus du graphwatch `009f0a7`) ; mémoire #19 état 09/10 vérifiée par t2 |
| Le re-push de `6661362` **n'est plus** le point à statuer | le commit est définitivement absent du dépôt local et du remote (`git cat-file -t 6661362` → `Not a valid object name`, mesuré #29/#41) ; le GREEN est livré sous forme de commits `dccf75f` + `55e6659` sur `wt/issue-19-discord-thread-title-description` (worktree `t_c22a7e74`) |
| #44 et #45 restent **OPEN** | 4ᵉ et 5ᵉ échelons conv-5, en attente de go JB (mesuré t2, 2026-10-10) |

**Ce que la décision débloque** : le jeton `/ok` sur l'issue #34 (premier
élément) fait déboucler la carte `t_2678f842` et la repart en file.
L'effet attendant : **re-spawn de la carte** (le worktree est propre, HEAD =
`origin/dev` au moment du fork — aucun travail à reprendre). Tout autre
commentaire est une demande d'éclaircissement et ne débloque rien.

**Le périmètre de la décision** est **mécanique** : rétablir une carte
crashée après un incident provider temporaire. Aucun arbitrage de goût,
aucune ambiguïté de périmètre — le verdict grill-me t2 est
`PROTOTYPE: non, AMBIGU: aucune, ARTEFACT: aucun`.

## Croisement infrastructure / fonctionnel / code

### Infrastructure (frontières traversées)

- **GitHub** — surface de décision : commentaire `/ok` sur l'issue #34
  (l'enfant importée par le pont). Adapter : `gh` CLI, lu par le pont.
  La carte `t_2678f842` est l'objet de la reprise.
- **Kanban Hermes** — source de vérité de l'état des cartes. L'effet est
  `comment` + `unblock` sur `t_2678f842`, invoqués en `subprocess` par le
  câblage de #5 ([[pj-decision]] : `decision_from_comment` calcule,
  l'appelant applique). Le blocage est de type `gave_up`/`crashed`
  (mort du worker PID), pas de type `blocked` — le fix #44
  (élargissement de `BLOCK_EVENT_KINDS` à `gave_up`/`crashed`) rend
  `t_2678f842` escaladable par `pj_escalate.py` ; sans ce fix, la carte
  reste invisible à l'humain (silence total).
- **Git / worktree partagé** — surface de livraison : le worktree
  `t_2678f842` (`.worktrees/t_2678f842`, branche `wt/t_2678f842`) est
  **propre** (HEAD = `009f0a7`, tree vide). Le re-spawn relance le
  cycle t1→…→t5 de #29 sur une base saine.
- **Aucun nouveau port** : les trois surfaces (GitHub, kanban, git)
  existent ; l'issue #34 réutilise la boucle de décision #5.

### Fonctionnel (capacité traversée)

La capacité traversée est **décision humaine sur blocage** (issue #5,
livrée) au service de la capacité **récupération après crash** (nouvelle,
non livrée : le fix #44 élargit `BLOCK_EVENT_KINDS` pour que les cartes
`gave_up`/`crashed` soient escaladées comme les cartes `blocked`).

Le chantier #29 (« slice 5/5 — convergence ») est déjà cadré par les
notes `issue-27` (escalade 1ᵉʳ), `issue-29` (escalade 2ᵉ) et
`issue-41` (escalade 4ᵉ). #34 porte :

- **le point de décision** : la carte `t_2678f842` est-elle à débloquer
  (re-spawn) ou à laisser bloquée en attendant le verdict de #44/#45 ?
- **la chaîne de re-spawn** : après le `/ok`, le dispatcher relance
  `t_2678f842` ; le worktree est propre, le cycle t1→…→t5 de #29
  reprend sur une base saine.
- **le verdict de convergence** : porté par les cartes en aval
  (`t_21efb666`, `t_58c956c8` — enfants de `t_2678f842`), pas par #34.

### Code (composants impactés)

| composant | état mesuré (2026-10-10) | impact #34 |
|---|---|---|
| `pipeline/pj_escalate.py` | `BLOCK_EVENT_KINDS = ("blocked", "block_loop_detected", "gave_up", "crashed")` (fix #44, non-mergé dans `origin/dev @ 2027333`) | Rendre `t_2678f842` escaladable (le crash est de type `gave_up`/`crashed`) |
| `bridge/gh_kanban_bridge.py` | Pont d'import : a créé l'issue #34 (idempotency-key `gh-issue-34`) après le gate de couverture | Aucun changement de code (import déjà fait) |
| `.worktrees/t_2678f842` (branche `wt/t_2678f842`) | HEAD = `009f0a7`, tree propre | Re-spawn de la carte sur cette base ; aucun travail à reprendre |
| `t_2678f842` (kanban) | `blocked` (run 293, `sticky=true`) | `/ok` → unblock → re-spawn par le dispatcher |

Le **core pur** de la décision (pattern [[pj-decision]]) :
`decision_from_comment` (calcule la décision portée par un commentaire,
ne l'applique jamais). L'effet (`unblock`) est appliqué par l'appelant
(`pj_decision.py`), jamais par le core.

## Lecture SDD (spec-driven)

La spec est le body de l'issue **#34** (le « point à statuer » : la carte
`t_2678f842` est bloquée sur #29, le jeton `/ok` en débloque). Le livrable
de #34 n'est **pas** un code, mais **l'état de la carte `t_2678f842`** :
soit elle est débloquée et re-spaunée, soit l'escalade se poursuit.
La doc décrit ce qui existe aujourd'hui (la carte bloquée, le worktree
propre, le GREEN déjà dans `origin/dev`) — pas une intention.

## Lecture DDD (bounded contexts, agrégats, événements)

- **Bounded context traversé** : *décision humaine sur blocage*
  (contexte #5, livré) au service du contexte *récupération après
  crash* (nouveau, non livré : fix #44).
- **Agrégat racine** : la **carte `t_2678f842`** (invariant : elle ne
  repart en `ready` que sur un `/ok` portant sa ligne canonique
  `carte: pj-hermes-workflow/t_2678f842`). L'**issue #34** est l'objet
  de décision qui la matérialise.
- **Value objects** : le **HEAD du worktree** (`009f0a7` mesuré,
  tree propre) ; le **run id du crash** (`293`) ; l'**idempotency-key**
  `gh-issue-34` ; le verdict grill-me (`PROTOTYPE: non`).
- **Domain events** : `/ok` humain sur l'issue #34 → unblock de
  `t_2678f842` → re-spawn par le dispatcher → cycle t1→…→t5 de #29
  reprend sur une base saine (worktree propre, HEAD = `origin/dev`).

## Lecture TDD (contrats testables)

Le contrat testable de #34 n'est pas un code, mais **un invariant
mesurable** :

- **La carte `t_2678f842` est en `ready` (ou `running`) après le `/ok`** —
  vérifiable par `hermes kanban --board pj-hermes-workflow show
  t_2678f842` (statut ≠ `blocked`).
- **Le worktree `t_2678f842` est propre** — `git status --short` dans
  `.worktrees/t_2678f842` → vide (0 modifié, 0 non-tracké).
- **Le re-spawn relance le cycle t1→…→t5 de #29** — les enfants de
  `t_2678f842` (`t_21efb666`, `t_58c956c8`) repassent en `ready` quand
  le parent est débloqué.

Ces invariants sont mesurables par le pont de couverture
(`pj_coverage_gate`) et par le dispatcher (qui re-spawn la carte sur
le `/ok`).

## Lecture hexagonale (le core reste pur)

Le **core pur** de la décision : `decision_from_comment` (fonction
pure : commentaire → décision, 0 réseau, 0 horloge, 0 aléa). L'effet
(`unblock`) est appliqué par l'adapter (`pj_decision.py`), jamais par
le core.

La frontière à respecter : **la décision est un calcul**, jamais
l'application. Le core ne sait pas débloquer une carte ; il sait
calculer si un commentaire porte un `/ok` pour une carte donnée.

## Frontières traversées (résumé)

```
issue #34 (GitHub, label kanban + decision, idempotency-key gh-issue-34)
  → commentaire /ok humain (surface de décision)
  → unblock de t_2678f842 (kanban)
  → re-spawn par le dispatcher (worktree propre, HEAD = origin/dev)
  → cycle t1→…→t5 de #29 reprend sur une base saine
```

Deux frontières : **GitHub ↔ kanban** (décision → effet) et
**kanban → dispatcher** (re-spawn). Le point de fragilité n'est pas
l'appel réseau mais **la couverture de type de blocage** : un crash de
worker (`gave_up`/`crashed`) n'est pas un `blocked` — sans le fix #44,
la carte reste invisible à l'humain.

## État mesuré (2026-10-10, rejouable)

- `origin/dev` = `2027333` (docs cadrage #29, 1 commit au-dessus du
  graphwatch `009f0a7`).
- `t_2678f842` : **blocked** (run 293, `sticky=true`, `retry_status=ready`),
  0 commentaire.
- `.worktrees/t_2678f842` : HEAD = `009f0a7`, tree **propre**
  (`git status --short` → vide).
- `wt/t_ce3496b2` (worktree t1 de #34, `.worktrees/t_ce3496b2`) :
  HEAD = `2027333`, tree propre (livré il y a ~4 min par t1).
- `git cat-file -t 6661362` → **fatal : Not a valid object name**
  (commit définitivement absent, mesuré #29/#41).
- #44 et #45 : **OPEN** (4ᵉ et 5ᵉ échelons conv-5, en attente de go JB).
- `pj_docs_lint.py` sur `/home/elix/pj-repos/hermes-workflow` → `exit=0`.

## Composants impactés (résumé)

- **Décision (cette issue)** : `pipeline/pj_decision.py`
  ([[pj-decision]]) + `pipeline/pj_escalate.py` (fix #44 :
  `BLOCK_EVENT_KINDS` élargi à `gave_up`/`crashed`) — le câblage #5,
  le fix #44 est **hors périmètre** de #34 (porté par sa propre carte).
- **Travail débloqué (re-spawn)** : le dispatcher relance `t_2678f842`
  sur le worktree propre ; le cycle t1→…→t5 de #29 reprend.
- **Vault** : à la convergence, le MOC `docs/architecture/README.md`
  sera mis à jour par la carte `doc-k` — hors périmètre de cette décision.

## Non tranché (et qui doit le rester ici)

Le cadrage ne tranche **pas** :
1. **Le verdict de convergence de #29** — porté par les cartes en
   aval (`t_21efb666`, `t_58c956c8`), pas par #34.
2. **Le merge du fix #44** (`BLOCK_EVENT_KINDS` élargi) — porté par sa
   propre carte, hors périmètre de #34.
3. **La publication live des copies `~/.hermes/scripts/`** (divergence
   D2 déclarée) — opération de fin de graphe contrôlée par identité.

Ces points sont **documentés**, pas décidés ici.
