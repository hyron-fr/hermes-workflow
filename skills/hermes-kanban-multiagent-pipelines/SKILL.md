---
name: hermes-kanban-multiagent-pipelines
description: "Use when building a versionable multi-agent kanban pipeline."
version: 1.0.0
category: productivity
metadata:
  hermes:
    tags: [kanban, multi-agent, bots, pipeline, orchestrator, versioning]
---

# Hermes Kanban — Multi-agent pipelines (bots + worktree + PR + versioning)

Construire une équipe d'agents/bots qui collaborent sur un board kanban, à étapes
orchestrées par un chef (scrrum), avec interfaces forcées (Discord, GitHub PR, worktree)
et le tout versionnable.

## Principe — une SOUL seule est une coquille

Un pipeline concret = **skill chargée dans le profil** (attentes + protocoles, versionnées)
**+ mécanismes natifs branchés** (worktree, completion-contract, dispatcher) **+ boucle
déclarée** (chef crée les enfants → dispatcher promeut → worker tourne).

## Le piège n°1 : worker autonome vs grooming interactif

Une skill/SOUL écrite pour un échange **interactif** (poser des questions, attendre la
réponse) **crash** dès que le dispatcher spawn le même profil comme **worker autonome** :
le worker sort proprement (rc=0) sans `kanban_complete` ni `kanban_block` → le dispatcher
compte une `protocol_violation`, retente jusqu'à `failure_limit`, puis `gave_up` → carte
`blocked` avec « worker exited cleanly without calling kanban_complete or kanban_block ».

**Règle pour toute skill/SOUL de worker kanban : tout run doit se terminer par un appel
tool kanban terminal (comment/complete/block).** Un run qui finit sans acte terminal compte
comme échec peu importe ce qu'il a fait. Quand le worker a besoin de l'humain, il fait
`kanban_block` + `kanban_comment` (avec le lien du thread Discord dans le commentaire),
puis attend le `unblock`.

Pour un grooming **réellement interactif** (un humain face au bot en session), ne pas passer
par un worker autonome : la carte reste `blocked` en attente d'input, l'humain fait
`unblock` + `complete` à la main après la discussion.

## Structurer un repo versionné

```
mon-pipeline/
├── profiles/<nom-profil>/SKILL.md    # attentes par étape (source de vérité, versionnée)
├── runbook/interfaces.md             # discord/github/worktree : où vit la config
├── deploy/deploy.sh                  # matérialise skills → profils Hermes réels
└── .gitignore                        # *.db, state.db, .env, auth.json (JAMAIS l'état)
```

Versionner : profiles/*/SKILL.md + runbook + deploy. Jamais : kanban.db (état),
state.db (sessions), .env/auth.json (secrets). L'état se reconstruit, pas le code.
Le board est l'état ; il ne se versionne jamais.

## Mécanismes builtin pour forcer les interfaces

| Interface | Mécanisme kanban | Effet |
|---|---|---|
| Implémentation en worktree isolé | `--workspace worktree --branch feature/<id>` | worker sur une branche, pas main; workspace non-scratch survit à la complétion |
| Validation PR (checks CI requis) | `--completion-contract OWNER/REPO` sur la carte | `done` **refusé** tant que checks requis pas verrs — pas de code custom |
| Avis / revue | `kanban_request_review` / `kanban_request_changes` | boucle review→re-run native |
| Entrée humaine | `kanban_block` + `kanban_comment` (lien Discord) | worker attend, humain répond puis unblock |

Vérifier le CLI réel (`hermes kanban create --help`) pour les flags exacts :
`--workspace`, `--branch`, `--completion-contract`.

## Activer kanban — deux couches distinctes (ne pas les confondre)

| Couche | Ce que c'est | Activation |
|---|---|---|
| Board visuel Desktop | plugin desktop bundled `kanban`, livré `defaultEnabled: false` | **Capabilities → Plugins → ligne « Kanban » → colonne Desktop** ; deep-link `/skills?tab=plugins&plugin=kanban`. Live, aucun redémarrage. |
| Tools `kanban_*` en session | surface agent | clef racine `toolsets` de config.yaml (voir pitfall ci-dessous) |

Le board Desktop est un réglage du **renderer** (localStorage
`hermes.desktop.pluginDecisions.v2`) : aucun flag CLI ne l'allume, donc l'agent ne
peut pas le basculer pour l'utilisateur — donner le chemin UI exact + le deep-link.
Le **backend** est prêt dans tous les cas : le router REST `/api/plugins/kanban/*`
(≈47 routes) est monté depuis le plugin bundled `plugins/kanban/dashboard`, montage
indépendant du toggle. Vérifier le board courant avec `hermes kanban boards list`.

Une carte `ready` n'est exécutée que si elle a un **assignee** : sans
`kanban.default_assignee` (ou assignee à la main) le board reste inerte même allumé.

Fichiers de vérité, ce que le plugin desktop apporte, et diagnostic du verrou
dispatcher : `references/activating-kanban.md`.

## Pitfalls de déploiement

- **Les dossiers sources doivent porter le NOM EXACT des profils Hermes réels**
  (`projecta-scrum`, pas `scrum`). Toujours lancer le deploy en `--dry-run` d'abord — il
  révèle le mismatch de nommage avant la copie.
- Activer les tools kanban en session interactive : la clef **top-level** `toolsets`
  de config.yaml, lue littéralement par le check_fn `_profile_has_kanban_toolset()`
  (`load_config().get("toolsets", [])`). Commande vérifiée :
  `hermes config set toolsets '["kanban"]'` → YAML correct (`toolsets:` puis `- kanban`).
  Ne pas passer par la forme pointée `hermes config set toolsets.0 kanban` (écrit un dict
  fautif `'0': kanban`). **`platform_toolsets.cli` est un leurre ici** : la liste CLI
  contient `kanban` par récupération read-time, mais le check_fn ne lit QUE la clef
  racine — donc y ajouter `kanban` ne débloque rien, et l'absence de la clef racine
  laisse les 14 `kanban_*` filtrés même si `hermes-cli` les liste. Les workers spawnés
  ont les tools automatiquement (HERMES_KANBAN_TASK), sans aucune config. `platform_toolsets.cli.*` RESTREINT au contraire (liste
explicite = opt-in étroit) — ne pas confondre. Les workers spawnés ont les tools
  automatiquement (HERMES_KANBAN_TASK).
- Profils créés via `hermes profile create` sont des îles : ils n'héritent PAS la section
  `providers:` du source. Recopier le bloc (base_url + api_key + models) sinon « Unknown
  provider ... agent_init_failed ». Vérifier `hermes -p <profil> doctor`.
- Chaque worker doit avoir une skill qui encode le type de workspace attendu (scratch vs
  worktree) et l'acte kanban terminal obligatoire.
- CLI kanban : `--board` AVANT le sous-commande ; `comment` = arg positionnel. Profils =
  minuscules alphanumériques ; board `--switch` crée `boards/<slug>/kanban.db` (`init` seul
  exige `boards create`).
