# Pipeline YAML — kanban orchestration engine

A pipeline engine defined in YAML that structures the behaviour on Hermes
kanban tickets, mixing **deterministic** steps (shell commands: template check,
CI, kanban/GitHub update) and **agentic** ones (external agents: hermes
profile+model, dsh/DeepSeek Harness, claude).

The orchestration is driven by **structured output**: every agentic step
emits a JSON validated against a schema, and a deterministic `gate`
decides the iteration (`goto`) or the exit.

## Files

- `pipeline/engine.py` — the engine (parse YAML, run the steps, gate,
  state cache, `run`/`list` CLI)
- `pipeline/backends.py` — agentic execution backends (hermes / dsh /
  claude) + robust JSON extraction
- `workflows/spec.yaml` — first validation workflow (**spec** phase)
- `workflows/smoke.yaml` — minimal test workflow (1 dsh agentic step)
- `workflows/schemas/*.json` — JSON schemas of the structured outputs
- `workflows/templates/ticket.md` — ticket template (deterministic check)

## Workflow schema

```yaml
name: spec
orchestration:
  mode: structured_output
  max_iterations: 10        # bounds the BACKWARD jumps (iterations)

steps:
  - id: viewpoints
    type: agentic            # or deterministic / gate
    parallel: true
    prompt: "..."            # template {{ticket.*}} / {{steps.<id>}}
    agents:
      - { role: ddd, backend: hermes, profile: default, model: ... }
      - { role: tdd, backend: dsh, profile: headless }
    output: { kind: structured, schema: ./schemas/viewpoint.json }

  - id: gate
    type: gate
    check: "all(r.get('data',{}).get('status')=='ok' for r in revalidate.get('results',[]))"
    on_fail: revalidate      # backward jump = iteration
    on_pass: finalize        # forward jump = progress
```

Step types:

- `agentic` — one or more agents (`agents:` in parallel, or `agent:`
  alone). The output is extracted (JSON) then validated against `output.schema`.
- `deterministic` — `command:` (one command) or `actions:` (a list), rendered
  through `{{...}}` then run in a shell.
- `gate` — evaluates `check:` (a Python expression over the step outputs) and
  routes through `on_pass`/`on_fail`.

Agentic backends (`backend:` in an agent):

- `hermes` — `hermes -p <profile> chat -q "<prompt>"` (+ optional `model:`)
- `dsh` — `dsh --profile <profile> "<prompt>"` (DeepSeek Harness)
- `claude` — `claude -p "<prompt>"` (Claude Code CLI)

## Usage

```bash
# List the steps of a workflow (without running it)
python3 pipeline/engine.py list workflows/spec.yaml

# Run a workflow on a ticket (simulation)
python3 pipeline/engine.py run workflows/spec.yaml <ticket_id> --dry-run

# Real run (writes .pipeline/<ticket>.json + side effects)
python3 pipeline/engine.py run workflows/spec.yaml <ticket_id> --board hermes-experiment
```

## Idempotence / replayability

The engine writes one state file per ticket (`.pipeline/<ticket>.json`)
recording the output of every step. A re-run **skips the steps that already
succeeded** (cache) and only replays what failed or changed. Deleting the
state file forces a full run.

## Template context

The prompts and commands use `{{...}}`:

- `{{ticket.id}}`, `{{ticket.title}}`, `{{ticket.body}}`,
  `{{ticket.issue_number}}` (deduced from the "Importé depuis <url>" line)
- `{{steps.<id>}}` — JSON output of a previous step
- `{{board}}` — board slug

## Traceability

- **GitHub = coarse grain**: `finalize` edits the issue (number deduced
  from the card body, same convention as the `gh_kanban_bridge.py` bridge).
- **Hermes = detail**: every step and its output are in the state
  file `.pipeline/<ticket>.json` + kanban comments.
- **Discord = live**: on every step transition (outside `--dry-run`), the
  engine posts an update in the issue's Discord thread (resolved by the
  name `🎫 Issue #N — …` through `discord_thread.py threads`). The thread is
  found back from `ticket.issue_number` (deduced from the "Importé depuis"
  line). The notification is best-effort: if the thread cannot be found
  or the post fails, the pipeline carries on without breaking.
