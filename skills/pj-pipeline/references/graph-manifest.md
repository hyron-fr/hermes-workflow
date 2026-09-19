# Manifeste de graphe d'une issue (`slices.json`)

Artefact de spec, PAS un livrable : il vit sous le dossier du board
(`~/.hermes/kanban/boards/<board>/specs/<n>/slices.json`), jamais dans le repo.
Zéro bruit dans les PR, lisible par tous les profils du pipeline.

Il est écrit par le worker de validation (gate humain franchi) puis consommé par un
cron déterministe 0-LLM qui construit cartes + liens. Le worker n'crée aucune carte
lui-même : c'est la séparation qui a supprimé les dérives de graphe (cartes fantômes,
liens inversés, assignees hors pipeline).

## Schéma

```json
{
  "issue": 42,
  "repo": "dino-game",
  "branch": "wt/issue-42-score-persistant",
  "slices": [
    {
      "k": 1,
      "slug": "score-persistant",
      "depends_on": [],
      "parallel": {
        "test": "test-1 : scénarios du score persistant",
        "dev":  "dev-1 : implémentation du score persistant"
      },
      "convergence": "conv-1 : réconcilier tests et implémentation",
      "doc": "doc-1 : documenter le module score"
    }
  ]
}
```

| clé | portée | rôle |
|---|---|---|
| `issue` / `repo` | racine | identité de l'issue ; servent aux idempotency-keys |
| `branch` | racine | **une seule pour toute l'issue** — c'est elle qui fait partager le worktree |
| `k` | slice | numéro contigu depuis 1 |
| `depends_on` | slice | numéros de slices amont, tous strictement < `k` |
| `parallel.test` / `.dev` | slice | deux cartes indépendantes, lancées en parallèle |
| `convergence` | slice | carte qui juge/réconcilie le lot (parent des deux) |
| `doc` | slice | carte de documentation, après convergence |

Le constructeur répète `--branch <branche racine>` sur CHAQUE carte en worktree. Sans
elle, le resolver retombe silencieusement sur un worktree par carte et le parallélisme
est décorrélé (les deux rôles ne partagent plus rien).

## Ce que le validateur doit REFUSER

Chaque règle correspond à une dérive qui a réellement atteint un board :

1. `issue` / `repo` absents, `slices[]` vide.
2. `k` non contigus depuis 1 — un trou = une carte jamais produite.
3. `depends_on` contenant une valeur ≥ `k` — dépendance inversée (attente mutuelle) ou
   auto-dépendance.
4. `branch` absente, ou divergente d'une slice à l'autre.
5. `branch` au MAUVAIS FORMAT — un `branch` dérivé d'un **id de carte**
   (`wt/t_109333ba`) au lieu du nom d'issue (`wt/issue-<n>-<slug>`) passe un validateur
   qui ne contrôle que la présence et l'unicité, et se propage silencieusement : la
   branche devient un artefact d'exécution, illisible et non reproductible d'une carte à
   l'autre. Le validateur doit contrôler le **motif** (`^wt/issue-<n>-`), et l'audit
   compare en plus la branche déclarée à celle de la carte worktree amont
   (`kanban show <t1> --json` → `branch_name`) — un écart signifie que le worker a
   recopié l'id de carte qu'il avait sous les yeux.
6. Une carte `test` sans ses **trois natures de scénario** : nominal + cas **limite** +
   **erreur**. Deux scénarios suffisent à une carte ordinaire, pas à une carte de test.
7. Une entrée `parallel` vide — un rôle annoncé mais aucune carte.

**Le validateur accepte tout ce qu'il ne teste pas.** Un manifeste de plusieurs dizaines de
Ko, conforme sur les comptages et les scénarios, peut encore porter une branche inexploitable :
la conformité d'un artefact se juge sur les règles qu'on a ÉCRITES, donc toute règle laissée
hors du validateur (format d'un identifiant, cohérence avec la carte amont) est une tolérance
silencieuse. Quand un gate passe vert sur un artefact qui contredit la convention documentée,
c'est le gate qu'il faut étendre, pas la convention qu'il faut excuser.

Un manifeste invalide → `request-changes` sur la carte de validation : c'est un gate,
pas une politesse. L'exigence des trois natures est ce qui rend les cas limites
OPPOSABLES (sinon ils restent un vœu pieux que le worker one-shot oublie).

## Construction

- **Test à blanc obligatoire** : `PJ_DRY_RUN=1` imprime le plan et ne crée RIEN.
  Vérifier la topologie, puis seulement lancer le run réel.
- **Idempotency-key sur CHAQUE création** (`pj-<clé>-<repo>-<n>`) : le constructeur est
  un cron */5 — sans clé, deux ticks proches dupliquent le graphe.
- **Tick muet quand aucun travail** : le script repère les cartes de soumission sans
  enfants et sort en silence s'il n'y en a pas (0 LLM, 0 écriture).
- **Anti-deadlock** : tous les liens posés APRÈS la création des cartes, dans le sens
  « carte de production → PARENT de la carte de soumission ». L'agrégateur n'est jamais
  parent de ses entrées.
- **Vérifier les assignees APRÈS un déploiement réel** (`kanban show <id> --json`), pas
  en relisant le script : un assignee par défaut posé sur le constructeur s'applique à
  toutes les cartes qu'il crée, et la carte du spécialiste part sur l'orchestrateur sans
  erreur ni avertissement.
