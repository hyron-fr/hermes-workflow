# hermes-workflow

An **issue GitHub → PR** pipeline driven by Hermes agents: a GitHub↔kanban
bridge, profile specialisation, human gates, and a development graph built
mechanically.

This repository is the project's **versioned reference**. It holds the agents, the
workflow, the skills and the deterministic tools — **with no secret whatsoever**.

---

## The problem it solves

A GitHub repository has issues; a multi-agent pipeline needs durable state,
human gates and traceability. This project connects the two:

```
issue GitHub
  └─ bridge (import, mirror label)        ← 0 LLM
       └─ kanban graph t1..t5             ← 0 LLM (deployer)
            ├─ t1 worktree
            ├─ t2 project memory (Hindsight)
            ├─ t3 grill-me + ambiguity quadrant
            ├─ t3b scoping doc (architecture)
            ├─ t4 draft spec  (deliberation in a Bot Mode room)
            └─ t5 validate    ← HUMAN GATE (go / no-go)
                 └─ development graph (test ∥ dev → convergence → doc)
                      └─ t6 submitted → PR (never merged by the agent)
```

**Guiding principle**: everything mechanical is **scripted without an LLM**; the LLM
only steps in where judgement is required. An idle pipeline costs zero tokens.

---

## Layout

| path | contents |
|---|---|
| `pipeline/` | **all** the tools: GitHub↔kanban bridge, graph building, linters, quality gates, hooks, admission guardrails |
| `agents/` | each profile's `SOUL.md` + a **sanitised** `config.yaml.example` (the cron wrappers live in `agents/pj-master/scripts/`) |
| `skills/` | the project's Hermes skills (reusable procedures) |
| `workflows/` | YAML workflow schemas and templates |
| `plugins/` | desktop app plugins (Discord buttons, dashboard UI) |
| `assets/` | rendering assets (bundled mermaid) |
| `tests/` | 113 tests, with no external dependency |

> **One copy per file.** The `bridge/` directory existed and duplicated 12
> files from `pipeline/`; one of them (`pj_graphwatch.py`) had diverged by 382
> lines. The duplicates were removed — a file lives in exactly one place.

---

## Installation

### 1. Prerequisites

- Hermes Agent installed (`~/.hermes/`)
- an authenticated `gh` CLI
- a target repository with a `dev` branch

### 2. Create the profiles

```bash
for p in pj-master pj-dev pj-doc pj-test; do hermes profile create "$p"; done
```

### 3. Configure each profile

```bash
cp agents/pj-master/config.yaml.example ~/.hermes/profiles/pj-master/config.yaml
# then edit it: fill in base_url and the API key (never versioned)
```

Secrets live in `~/.hermes/profiles/<profile>/.env`, **outside this repository**.
Expected variables:

```
LITELLM_API_KEY=...
DISCORD_BOT_TOKEN=...
DISCORD_ALLOWED_USERS=...
HERMES_KANBAN_BOARD=pj
```

### 4. Deploy the tools

The `HERMES_WORKFLOW` variable must point at this repository (the scripts use it
to resolve themselves):

```bash
export HERMES_WORKFLOW="$PWD"     # add this to your shell profile
```



```bash
mkdir -p ~/.hermes/scripts
cp pipeline/*.py ${HERMES_WORKFLOW}/pipeline/
cp pipeline/*.py ~/.hermes/profiles/pj-master/scripts/   # the crons resolve here
chmod +x ${HERMES_WORKFLOW}/pipeline/pj_*.py
```

> **Why two copies?** The crons resolve their `--script` in the **profile's**
> `scripts/` directory, not in `${HERMES_WORKFLOW}/pipeline/`. Both locations
> are required.

### 5. Create one board per repository

```bash
hermes kanban boards create pj-<repo>
hermes kanban boards set-default-workdir pj-<repo> /path/to/dev-clone
```

---

## Quality gates (all deterministic, 0 LLM)

| tool | role | failure |
|---|---|---|
| `pj_card_lint.py` | 5 mandatory sections + BDD + DoR/DoD + INVEST | exit 1 |
| `pj_slices_lint.py` | graph contract + a `preview` slice when prototyping is required | exit 1 |
| `pj_coverage_gate.py` | coverage per **changed** file | exit 1 |
| `pj_docs_lint.py` | documentation vault (frontmatter, links, orphans) | exit 1 |
| `pj_spawn_guard.py` | per-board assignee allowlist | blocks the card |

**Rule**: a check that filters by pattern filters **generally**, never by a closed
list — otherwise every step added later becomes a false positive, precisely at the
moment it is added.

---

## Guardrails learned in production

1. **Overlap gate** — an issue that overlaps in-flight work (an open PR, an
   existing graph) is not imported: it is reported for a human decision. Without
   it, a change request filed as a new issue starts a whole new graph.
2. **Ambiguity quadrant** (t3) — every ambiguity is qualified: removable alone or
   not, and the **cost if it is not removed**. Prototyping is required only when a
   non-removable ambiguity concerns a perceivable deliverable.
3. **Direction of kanban links** — `link <parent> <child>`: the **child waits** for
   the parent. A synthesis card is built backwards, otherwise deadlock.
4. **One branch per issue** — sharing a worktree between cards requires the **same**
   `--branch`, otherwise it silently falls back to an isolated worktree.
5. **Anti-livelock guardrail** — a stalled deliberation (serial defers) is
   detected and cut off automatically, with a trace on the card.

---

## Tests

```bash
python3 -m pytest tests/ -q     # 113 passed
```

The tests load their modules **from this repository** (relative paths), never
from an external location.

---

## License

MIT — see `LICENSE`.
