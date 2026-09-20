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

Build a team of agents/bots that collaborate on a kanban board, with steps
orchestrated by a lead (scrrum), with forced interfaces (Discord, GitHub PR, worktree)
and the whole thing versionable.

## Principle — a lone SOUL is a shell

A concrete pipeline = **a skill loaded into the profile** (expectations + protocols, versioned)
**+ native mechanisms wired in** (worktree, completion-contract, dispatcher) **+ a declared
loop** (the lead creates the children → the dispatcher promotes → the worker runs).

## Pitfall #1: autonomous worker vs interactive grooming

A skill/SOUL written for an **interactive** exchange (ask questions, wait for the
answer) **crashes** as soon as the dispatcher spawns the same profile as an **autonomous
worker**: the worker exits cleanly (rc=0) without `kanban_complete` or `kanban_block` → the
dispatcher counts a `protocol_violation`, retries until `failure_limit`, then `gave_up` → card
`blocked` with "worker exited cleanly without calling kanban_complete or kanban_block".

**Rule for every kanban worker skill/SOUL: by definition any run must end with a terminal
kanban tool call (comment/complete/block).** A run that ends without a terminal act is
counted as a defect, whatever it did. When the worker needs the human, it calls
`kanban_block` + `kanban_comment` (with the Discord thread link in the comment),
then waits for the `unblock`.

For **genuinely interactive** grooming (a human facing the bot in session), do not go
through an autonomous worker: the card stays `blocked` waiting for input, the human does
`unblock` + `complete` by hand after the discussion.

## Structuring a versioned repo

```
my-pipeline/
├── profiles/<profile-name>/SKILL.md  # per-step expectations (source of truth, versioned)
├── runbook/interfaces.md             # discord/github/worktree: where the config lives
├── deploy/deploy.sh                  # materialises skills → real Hermes profiles
└── .gitignore                        # *.db, state.db, .env, auth.json (NEVER the state)
```

Version: profiles/*/SKILL.md + runbook + deploy. Never: kanban.db (state),
state.db (sessions), .env/auth.json (secrets). The state is rebuilt, not the code.
The board is the state; it is never versioned.

## Builtin mechanisms that force the interfaces

| Interface | kanban mechanism | Effect |
|---|---|---|
| Implementation in an isolated worktree | `--workspace worktree --branch feature/<id>` | worker on a branch, not main; a non-scratch workspace survives completion |
| PR validation (required CI checks) | `--completion-contract OWNER/REPO` on the card | `done` is **refused** while the required checks are not green — no custom code |
| Advice / review | `kanban_request_review` / `kanban_request_changes` | native review→re-run loop |
| Human input | `kanban_block` + `kanban_comment` (Discord link) | worker waits, the human answers then unblocks |

Check the real CLI (`hermes kanban create --help`) for the exact flags:
`--workspace`, `--branch`, `--completion-contract`.

## Enabling kanban — two distinct layers (do not confuse them)

| Layer | What it is | Activation |
|---|---|---|
| Desktop visual board | bundled desktop plugin `kanban`, shipped `defaultEnabled: false` | **Capabilities → Plugins → the "Kanban" row → the Desktop column**; deep-link `/skills?tab=plugins&plugin=kanban`. Live, no restart. |
| Tools `kanban_*` in session | agent surface | root key `toolsets` of config.yaml (see the pitfall below) |

The Desktop board is a **renderer** setting (localStorage
`hermes.desktop.pluginDecisions.v2`): no CLI flag turns it on, so the agent
cannot flip it for the user — give the exact UI path + the deep-link.
The **backend** is wired in every case: the REST router `/api/plugins/kanban/*`
(≈47 routes) is mounted from the bundled plugin `plugins/kanban/dashboard`, a mount
independent of the toggle. Check the current board with `hermes kanban boards list`.

A `ready` card is only executed when it has an **assignee**: without
`kanban.default_assignee` (or an assignee set by hand) the board stays inert even switched on.

The files of truth, what the desktop plugin brings, and how to diagnose the dispatcher
lock: `references/activating-kanban.md`.

## Deployment pitfalls

- **The source directories must carry the EXACT NAME of the real Hermes profiles**
  (`projecta-scrum`, not `scrum`). Always run the deploy in `--dry-run` first — it
  reveals the naming mismatch before the copy.
- Enabling the kanban tools in an interactive session: the **top-level** key `toolsets`
  of config.yaml, read literally by the check_fn `_profile_has_kanban_toolset()`
  (`load_config().get("toolsets", [])`). Verified command:
  `hermes config set toolsets '["kanban"]'` → correct YAML (`toolsets:` then `- kanban`).
  Do not use the dotted form `hermes config set toolsets.0 kanban` (it writes a faulty
  dict `'0': kanban`). **`platform_toolsets.cli` is a decoy here**: the CLI list
  contains `kanban` through a read-time fallback, but the check_fn reads ONLY the root
  key — so adding `kanban` there releases nothing, and the absence of the root key
  leaves the 14 `kanban_*` filtered even if `hermes-cli` lists them. Spawned workers
  have the tools automatically (HERMES_KANBAN_TASK), with no config at all. `platform_toolsets.cli.*` RESTRICTS instead (an
explicit list = a narrow opt-in) — do not confuse the two. Spawned workers have the tools
  automatically (HERMES_KANBAN_TASK).
- Profiles created via `hermes profile create` are islands: they do NOT inherit the
  `providers:` section of the source. Copy the block (base_url + api_key + models) or "Unknown
  provider ... agent_init_failed". Check with `hermes -p <profile> doctor`.
- Each worker must have a skill that encodes the expected workspace type (scratch vs
  worktree) and the mandatory terminal kanban act.
- kanban CLI: `--board` BEFORE the subcommand; `comment` = positional argument. Profiles =
  lowercase alphanumerics; board `--switch` creates `boards/<slug>/kanban.db` (`init` alone
  requires `boards create`).
