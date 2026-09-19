---
type: context
status: draft
tags: [architecture, pipeline, issue-smoke-test, cadrage]
issues: [1]
---

# Cadrage architectural — issue #1 « Vérifier le cycle complet du pipeline »

## Positionnement (cadre exact)

L'issue #1 n'introduit **aucune fonctionnalité nouvelle** : c'est une **issue de
test du framework** qui demande de vérifier que le cycle complet tourne de bout en
bout — le pont importe, le déployeur construit le graphe `t1..t5`, et les quatre
maillons (spécialisation des profils, portes humaines, graphe de développement,
traçabilité) s'exécutent.

Cette issue se positionne donc **à cheval sur l'intégralité des frontières** du
projet `hermes-workflow` : elle ne s'implante dans **aucun** composant de code en
particulier, elle **traverse** le système de l'entrée (issue GitHub) à la sortie
(futur PR → fermeture d'issue), en passant par le board kanban, le déployeur, la
phase de spec, la porte humaine, puis le graphe de développement. Sa « livraison »
est une **preuve observée** (le graphe déployé et les maillons actifs), pas un
diff de code.

C'est le seul type d'issue dont le livrable est un **état du board** plutôt qu'un
changement de dépôt : elle valide l'outillage lui-même, comme un smoke test
end-to-end du pipeline.

## Croisement infrastructure / fonctionnel / code

### Infrastructure (frontières externes traversées)

- **GitHub** — point d'entrée (issue) et point de sortie (PR, fermeture d'issue).
  Adapter : `gh` CLI via `bridge/gh_kanban_bridge.py` (pull → carte `triage`,
  push → fermeture).
- **Kanban Hermes** — source de vérité durable. Table SQLite locale
  (`~/.hermes/kanban/boards/<board>/kanban.db`). Toute décision s'y reporte en
  commentaire de carte.
- **Discord** — canal de grill-me (questions humaines) et de notification live du
  moteur de pipeline. Adapter : `pipeline/discord_thread.py`, un thread par issue.
- **Hindsight** — mémoire projet partagée (banque `pj`), alimentée en post-merge
  par `pj_docs_memory.py`. Adapter : API HTTP `localhost:9078`.
- **Git worktrees** — ancres `${HOME}/pj-repos/<repo>` sur `dev` ; un worktree
  partagé par issue (branche `wt/issue-<n>-<slug>`).
- **Crons** — pont (`pj-bridge-<repo>`), déployeur (`pj-deploy-<repo>`), graphe
  (`pj-graphwatch`), rooms (`pj-room-keeper`) : tous **0 LLM**, tick silencieux
  quand rien à faire.

### Fonctionnel (capacités traversées)

L'issue #1 parcourt les cinq capacités du framework, dans l'ordre :

1. **Admission** (pont + gate de couverture + spawn guard) : une issue ouverte
   sans label devient une carte `triage` ; une issue recouvrant du travail en vol
   est signalée, pas importée.
2. **Construction du graphe de spec** (déployeur `pj_pipeline_deployer.py`) :
   `t1 worktree`, `t2 mémoire`, `t3 grill-me`, `t3b doc-cadrage`, `t4 draft spec`,
   `t5 validate` — mécanique, déterministe.
3. **Qualification d'ambiguïté** (`t3`) : quadrant d'ambiguïté + verdict
   `PROTOTYPE:` / `AMBIGU:` / `ARTEFACT:` — ne convoque l'humain que si une
   ambiguïté non levable le justifie.
4. **Porte humaine** (`t5`) : `go` explicite avant tout développement de masse.
5. **Graphe de développement** (`pj_graphwatch.py` depuis `slices.json`) :
   `test-k ∥ dev-k → conv-k → doc-k → doc-review → t6 PR → worktree-rm →
   doc-memory → fermeture d'issue`.

### Code (composants, ports, adapters)

- **Core pur (hexagonal)** — les fonctions déterministes testables sans I/O :
  `pj_card_lint.lint`, `pj_slices_lint.validate`, `pj_docs_lint.scan`,
  `pj_room.detect_livelock`, `pj_graphwatch.build_plan` / `check_topology`,
  `gh_kanban_bridge.coverage_verdict`, `pj_room_keeper.decide`. Aucune dépendance
  réseau/fichier/UI : ce sont les **contrats** que `tests/` (113 tests) verrouille.
- **Ports** — `kanban` (CLI hermes), `gh` (CLI GitHub), Discord (REST), Hindsight
  (HTTP), git (worktree). Tous franchis par des adapters `subprocess` (`sh()`,
  `kanban()`, `gh()`).
- **Adapters** — `bridge/`, `pipeline/` (backends `hermes`/`dsh`/`claude`,
  moteur LangGraph `engine.py`), `agents/*/SOUL.md` (comportement des profils).

## Lecture SDD (spec-driven)

La spec est la source de vérité ; la documentation décrit le **livré**, jamais une
intention. Pour l'issue #1, la « spec » est le body de l'issue + le graphe
déployé : le livrable observable est **l'existence et l'exécution** des cartes
`t1..t5` + `t3b`, vérifiable par `kanban list`. La doc de cadrage ci-présente ne
décrit que ce qui existe déjà dans le dépôt (framework livré au commit initial) ;
elle ne spécule sur aucun composant futur.

## Lecture DDD (bounded contexts, agrégats, événements)

- **Bounded contexts** :
  1. *Admission* (pont, gate de couverture, spawn guard) ;
  2. *Graphe de spec* (déployeur, `t1..t5`, `t3b`, rooms de délibération) ;
  3. *Développement* (graphwatch, slices, test/dev/conv/doc, worktree) ;
  4. *Livraison* (t6 PR, worktree-rm, doc-memory, fermeture d'issue).
- **Agrégat racine** : la **carte kanban racine** d'une issue (invariant = la
  topologie du graphe qui lui est attachée ; elle ne passe `done` que quand tout
  le graphe est terminé — pattern `decompose`).
- **Entités** : les cartes (t1..t6, test-k, dev-k, conv-k, doc-k) ; une carte de
  production est identifiée par son `id` et son statut de cycle de vie.
- **Value objects** : `slices.json` (contrat du graphe de dev : `issue`, `repo`,
  `branch`, `slices[]` avec `k`, `slug`, `depends_on`, `parallel.{test,dev}`,
  `convergence`, `doc`) ; le format de carte (5 sections + Gherkin + DoR/DoD +
  INVEST) ; le `room_id` déterministe `pj-<repo>-issue-<n>`.
- **Domain events** : transitions de statut kanban (`ready`/`running`/`blocked`/
  `done`), verdicts de gate (`pass`/`fail`), `room.activity` (`settled`/`bounded`),
  PR `MERGED`, issue `CLOSED`. Les événements de room (message.user/member,
  turn.settled/deferred) pilotent le cycle `ensure → ask → report → disband`.

## Lecture TDD (contrats testables)

Les contrats que `pj-test` verrouille (déjà couverts par `tests/`, 113 tests) :

- `pj_card_lint` : 5 sections ordonnées + Gherkin (≥2 scénarios, ≥3 étapes) +
  DoR/DoD + garde-fous + signaux INVEST ;
- `pj_slices_lint` : contiguïté des `k`, blocs `parallel`/`convergence`/`doc`,
  dépendances strictement inférieures, ≥3 scénarios par carte test (nominal +
  limite + erreur), slice `preview` en tête si `prototype_required` ;
- `pj_docs_lint` : frontmatter (`type`/`status`/`tags`), wikilinks résolus par
  basename, aucune note orpheline hors MOC ;
- `pj_coverage_gate` : couverture > 80 % **par fichier modifié** (diff base dev) ;
- `pj_graphwatch.check_topology` : sens des liens (production → `t6`, jamais
  l'inverse) — épingle l'anti-deadlock ;
- `pj_room.detect_livelock` : délibération bloquée (defer en série) coupée
  automatiquement.

L'issue #1 est elle-même le **contrat E2E** : « pont importe → déployeur construit
`t1..t5` → les 4 maillons tournent », vérifiable par observation du board.

## Lecture hexagonale (le core reste pur)

Le **core pur** est l'ensemble des fonctions déterministes ci-dessus : elles
manipulent des structures de données (dict de carte, JSON de slices, texte de
note), **sans** DOM, Canvas, réseau, système de fichiers ni horloge réelle. Les
entrées/sorties (kanban, gh, Discord, Hindsight, git) passent par des **ports**
invoqués en `subprocess` dans des **adapters** (`sh()`, `kanban()`, `gh()`). Une
évolution de l'outillage doit préserver cette frontière : toute logique
décisionnelle nouvelle appartient au core (testable), jamais dans un adapter
(inscriptible en shell).

## Composants impactés par l'issue #1

Aucun diff de code attendu. Composants **exercés** (pas modifiés) :

- `bridge/gh_kanban_bridge.py` — import de l'issue en carte `triage` ;
- `pipeline/pj_pipeline_deployer.py` — construction du graphe `t1..t5` + `t3b` ;
- `pipeline/pj_room.py` + `pj_room_keeper.py` — room de délibération de `t4` ;
- `pipeline/pj_graphwatch.py` — graphe de dev (sera exercé après le `go`) ;
- les quatre profils `agents/{pj-master,pj-dev,pj-doc,pj-test}/SOUL.md` — exécutés
  par les workers des cartes ;
- les gates déterministes `pj_spawn_guard.py`, `pj_docs_lint.py`,
  `pj_card_lint.py`, `pj_slices_lint.py` — invoqués en preuve le long du cycle.

## Frontières traversées (résumé)

```
issue GitHub
  → (pont) carte triage
  → (déployeur) graphe t1..t5 + t3b
  → (grill-me) Discord si ambiguïté non levable
  → (doc-cadrage) vault docs/architecture
  → (draft) room Bot Mode
  → (validate) porte humaine (go)
  → (graphwatch) graphe dev test∥dev→conv→doc→t6
  → (t6) PR  → (worktree-rm)  → (doc-memory → Hindsight)  → fermeture issue
```

Chaque flèche est une frontière de contexte (kanban ↔ GitHub ↔ Discord ↔ Hindsight
↔ filesystem) franchie par un adapter déterministe ; aucun saut ne passe par du
code non livré ni par une décision non humaine.
