# Pipeline YAML — moteur d'orchestration kanban

Moteur de pipeline défini en YAML qui structure le comportement sur les
tickets kanban Hermes, en mélangeant étapes **déterministes** (commandes
shell : check template, CI, update kanban/GitHub) et **agentiques** (agents
externes : hermes profile+modèle, dsh/DeepSeek Harness, claude).

L'orchestration est pilotée par **structured output** : chaque étape
agentique émet un JSON validé contre un schéma, et un `gate` déterministe
décide de l'itération (`goto`) ou de la sortie.

## Fichiers

- `pipeline/engine.py` — le moteur (parse YAML, exécute les étapes, gate,
  cache d'état, CLI `run`/`list`)
- `pipeline/backends.py` — backends d'exécution agentique (hermes / dsh /
  claude) + extraction JSON robuste
- `workflows/spec.yaml` — premier workflow de validation (phase **spec**)
- `workflows/smoke.yaml` — workflow de test minimal (1 étape agentique dsh)
- `workflows/schemas/*.json` — schémas JSON des sorties structurées
- `workflows/templates/ticket.md` — template de ticket (check déterministe)

## Schéma d'un workflow

```yaml
name: spec
orchestration:
  mode: structured_output
  max_iterations: 10        # borne les sauts ARRIÈRE (itérations)

steps:
  - id: viewpoints
    type: agentic            # ou deterministic / gate
    parallel: true
    prompt: "..."            # template {{ticket.*}} / {{steps.<id>}}
    agents:
      - { role: ddd, backend: hermes, profile: default, model: ... }
      - { role: tdd, backend: dsh, profile: headless }
    output: { kind: structured, schema: ./schemas/viewpoint.json }

  - id: gate
    type: gate
    check: "all(r.get('data',{}).get('status')=='ok' for r in revalidate.get('results',[]))"
    on_fail: revalidate      # saut arrière = itération
    on_pass: finalize        # saut avant = progression
```

Types d'étape :

- `agentic` — un ou plusieurs agents (`agents:` en parallèle, ou `agent:`
  seul). La sortie est extraite (JSON) puis validée contre `output.schema`.
- `deterministic` — `command:` (une commande) ou `actions:` (liste), rendues
  via `{{...}}` puis exécutées en shell.
- `gate` — évalue `check:` (expression Python sur les sorties d'étapes) et
  route via `on_pass`/`on_fail`.

Backends agentiques (`backend:` dans un agent) :

- `hermes` — `hermes -p <profile> chat -q "<prompt>"` (+ `model:` optionnel)
- `dsh` — `dsh --profile <profile> "<prompt>"` (DeepSeek Harness)
- `claude` — `claude -p "<prompt>"` (Claude Code CLI)

## Utilisation

```bash
# Lister les étapes d'un workflow (sans exécuter)
python3 pipeline/engine.py list workflows/spec.yaml

# Exécuter un workflow sur un ticket (simulation)
python3 pipeline/engine.py run workflows/spec.yaml <ticket_id> --dry-run

# Exécution réelle (écrit .pipeline/<ticket>.json + side effects)
python3 pipeline/engine.py run workflows/spec.yaml <ticket_id> --board hermes-experiment
```

## Idempotence / rejouabilité

Le moteur écrit un fichier d'état par ticket (`.pipeline/<ticket>.json`)
qui enregistre la sortie de chaque étape. Un re-run **saute les étapes déjà
réussies** (cache) et ne rejoue que ce qui a échoué ou changé. Supprimer le
fichier d'état force une exécution complète.

## Contexte de template

Les prompts et commandes utilisent `{{...}}` :

- `{{ticket.id}}`, `{{ticket.title}}`, `{{ticket.body}}`,
  `{{ticket.issue_number}}` (déduit de la ligne "Importé depuis <url>")
- `{{steps.<id>}}` — sortie JSON d'une étape précédente
- `{{board}}` — slug du board

## Traçabilité

- **GitHub = grosses mailles** : le `finalize` édite l'issue (numéro déduit
  du body de carte, même convention que le pont `gh_kanban_bridge.py`).
- **Hermes = détail** : chaque étape et sa sortie sont dans le fichier
  d'état `.pipeline/<ticket>.json` + commentaires kanban.
- **Discord = live** : à chaque passage d'étape (hors `--dry-run`), le
  moteur poste un update dans le thread Discord de l'issue (résolu par le
  nom `🎫 Issue #N — …` via `discord_thread.py threads`). Le thread est
  retrouvé depuis `ticket.issue_number` (déduit de la ligne « Importé
  depuis »). La notification est best-effort : si le thread est introuvable
  ou le post échoue, le pipeline continue sans casser.
