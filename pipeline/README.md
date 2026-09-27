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
- `pipeline/pj_escalate.py` — escalation of blocked cards to the Discord thread
  of their issue (see below)
- `workflows/spec.yaml` — first validation workflow (**spec** phase)
- `workflows/smoke.yaml` — minimal test workflow (1 dsh agentic step)
- `workflows/schemas/*.json` — JSON schemas of the structured outputs
- `workflows/templates/ticket.md` — ticket template (deterministic check)

## Escalation tool `pj_escalate.py`

Escalates kanban cards that are **blocked** to the Discord thread of their GitHub
issue. Deterministic (0 LLM), idempotent per `(card, last blocking event)`,
triggered by a global `no_agent` cron (`main()` iterates the `pj-*` boards, hence
**no** repo suffix in its wrapper).

All of its configuration comes from the environment — no identifier, no machine
path in the file. Three variables are **required**, the others are
**optional** with a default derived from the home directory:

| variable | status | default |
|---|---|---|
| `PJ_ESCALATE_CHANNEL_ID` | **required** | — (channel of the issue threads) |
| `PJ_ESCALATE_USER_ID` | **required** | — (recipient of the decisions) |
| `PJ_ESCALATE_GUILD_ID` | **required** | — |
| `PJ_ESCALATE_REPOS_ROOT` | optional | `$HOME/pj-repos` |
| `PJ_ESCALATE_STATE_DIR` | optional | `$HOME/.hermes/state` |
| `PJ_ESCALATE_THREAD_HELPER` | optional | `$HOME/.hermes/scripts/discord_thread.py` |
| `PJ_ESCALATE_ORG` | optional | `hyron-fr` |
| `PJ_ESCALATE_GH_BIN` | optional | resolution via `shutil.which` + verified candidates |

**A missing or EMPTY required variable refuses the tick loudly**: `ConfigError`,
a message on the error stream naming the variable, exit code `2`, no send, no
state write. An empty value is never an identifier (measured: `target=""`
makes the post fail, the state does not advance, and the same message is
reposted on every tick, indefinitely). The state directory is validated by an
**write probe** at the very start of the tick, before any board scan: otherwise
a local `PermissionError` would only arrive after the earlier boards have posted.

`PJ_ESCALATE_GH_BIN` is the only case where "set to empty" is a **legitimate**
state: it expresses "guard unavailable, loud escalation" — the warning goes out,
the tick continues. A **missing** variable, in contrast, lets the resolution
by verified candidates do its work.

Discord identifiers are **never** written in the repo (public): the wrapper
`agents/pj-master/scripts/pj_escalate_all.sh` reads the `PJ_ESCALATE_*` from the
profile's `.env` (`~/.hermes/profiles/<profil>/.env`, outside the repo) and
exports them to the tick, exporting **only** that prefix.

The inputs and outputs pass through injection points (`runner` for the
subprocesses, `poster` for the Discord send, `conn_factory` for the kanban
database; default = real implementation): the full tick is exercised without
network and without a real executable.

## Publishing and identity check `pj_publish.py`

`pj_escalate.py` **runs from the profile**, not from this repo: the installed
copy (`~/.hermes/profiles/pj-master/scripts/pj_escalate.py`) and the versioned
copy (`pipeline/pj_escalate.py`) are two distinct files, and nothing brings them
closer automatically. `pipeline/pj_publish.py` **compares** these two copies and
**refuses** to switch until the gap is established — and until the cron wrapper
exports the required variables that the sanitized copy reads from the
environment.

The versioned copy is **sanitized** (no Discord identifier, no machine path:
see the table above). The identity cannot therefore rest on the raw bytes, but
on the **content as it runs** — identical content **and** a wrapper that
provides the required variables.

```bash
# Check only (default mode, READ-ONLY): identity + wrapper exports
python3 pipeline/pj_publish.py --check --wrapper agents/pj-master/scripts/pj_escalate_all.sh

# Check of an explicit pair, on fixtures
python3 pipeline/pj_publish.py --check --source pipeline/pj_escalate.py --target /tmp/copy.py

# Publish (switch) — requires an explicit --target, refuses if the wrapper is faulty
python3 pipeline/pj_publish.py --publish \
    --target ~/.hermes/profiles/pj-master/scripts/pj_escalate.py
```

| argument | role |
|---|---|
| `--check` | **default**, read-only: no write, no `mkdir`, no temporary file |
| `--publish` | switches the installed copy or copies (requires `--target`); refused if the wrapper does not export the required ones; **idempotent** (a target already identical is not rewritten) |
| `--target` | installed copy to check/switch — **repeatable**; without it, the two known targets are checked (`<profil>/scripts/` and `~/.hermes/scripts/`) |
| `--source` | versioned copy (default: `pipeline/pj_escalate.py`, next to the file) |
| `--wrapper` + `--require-env` | checks the `export` **before** any switch; `--require-env` absent = the contract of the versioned copy (`REQUIRED_VARS`) |
| `--coverage --coverage-json J --diff-base REF` | perimeter mode: refuses an empty perimeter and a report that does not instantiate the changed file |
| `--home` | injectable home directory (default: `HOME`) — no machine path coded |

Exit codes: `0` compliant, `1` delivered gap (divergence, missing export, file
changed below the threshold), `2` execution error (target/source/wrapper absent
or unreadable, empty perimeter, missing argument). Priority `2 > 1 > 0`.

### The publishing gesture — the order is a guard-rail

The installed wrapper **exports nothing** today (252 o, plain `exec python3 <path>`).
Switching the sanitized copy **before** adding the `export` kills the tick:
`escalation_config` raises `ConfigError`, the process exits with `rc=2` and **no
escalation goes out at all** — silently, since nobody reads the cron's output file.
The order below is therefore not a convenience:

1. **check**: `python3 pipeline/pj_publish.py --check --wrapper <installed wrapper>` —
   establishes the gap **and** the absence of `export` (the tool names the variable and the wrapper);
2. **the human** adds the `export` of the required variables to the wrapper (file
   **outside** the repo; the worker does not write to it);
3. **re-check**: the same `--check` must now see the variables
   (`wrapper exports …: compliant`) — this is the proof that the variable is "seen by
   the tick", not just written;
4. **publish**: `--publish --target ~/.hermes/profiles/pj-master/scripts/pj_escalate.py`
   (the copy the cron executes); add `--target ~/.hermes/scripts/pj_escalate.py`
   if the second installed copy must follow;
5. **verify by execution**: run a tick of the wrapper and verify that it stays
   **mute** (`rc=0`, 0 spurious escalation). A tick that talks for an already-
   processed card signals that the switch landed in the wrong place.

The `--publish` **re-verifies the identity after the write**: if the written
content does not re-read identically to the source, the tool exits with `2` and
says so — never "published" on a write that was not re-read.

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
