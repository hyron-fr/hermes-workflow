---
name: pj-pipeline
category: software-development
version: 1.0.0
description: "Use when working on the pj pipeline (pj-master, pj-dev)."
tags: [hermes, kanban, github, discord, automation]
---

# pj Pipeline — GitHub Issues → kanban → PR (pj-master / pj-dev)

Operational automation (installed 2026-09-13, validated E2E on example-repo #20 → PR #21 merged).

## Topology

- Profiles: **pj-master** (orchestrator, Discord bot "Experiment", channel #pj-master
  ${DISCORD_ID}, guild ${DISCORD_GUILD} ${DISCORD_ID}, dedicated systemd gateway) and
  **pj-dev** (dev worker). Provider litellm-proxy-gcp — the key is copied PROGRAMMATICALLY
  from ~/.hermes/config.yaml; a key rebuilt from a redacted read_file = 401.
- 1 kanban board per hyron-fr repo: `pj-<slug>`. Clones anchored on dev:
  `${HOME}/pj-repos/<repo>`; one `default_workdir` per board (worktree anchor).
- Crons on the pj-master profile (0 LLM for every one of them): `pj-bridge-<repo>` (pull
  issues/push done) + `pj-deploy-<repo>` (*/5) + `pj-graphwatch-<repo>` (*/5, dev graph) +
  `pj-room-keeper-<repo>` (*/5, room cycle) + `pj-repo-watch` (*/10). The count grows with
  every board/step added — read it from `hermes cron list`, never from memory.
- Memory: shared hindsight bank **pj**, split by `project:<repo>` tags
  (the {workspace} placeholder is hardcoded to "hermes" — no per-worktree bank is possible).
- Discord REST in cron: helper `${HERMES_WORKFLOW}/pipeline/discord_thread.py` (token read
  from pj-master/.env; a DiscordBot-style User-Agent is mandatory, otherwise 403 Cloudflare).

## Flow (1 issue → a graph of cards)

1. The bridge imports the root into **triage** (`PJ_IMPORT_TRIAGE=1`).
2. `pj_pipeline_deployer.py` (deterministic, no LLM): t1 worktree (`--workspace
   worktree:<anchor>`), t2 memory, t3 grill-me; **t3b doc-cadrage** (assignee `pj-doc`,
   architectural positioning SDD/DDD/TDD/hexagonal, crossing infra/functional/code —
   upstream of t4); t4 draft (parents t1+t2+t3+t3b), t5 validate (parent t4); every t_i is a
   **PARENT** of the root; exit from triage through `specify_triage_task` (direct API, no
   LLM).
3. t3/t5: the worker asks its questions on Discord and then `kanban_block`; a human answer →
   `kanban unblock` → a re-spawn that re-reads the whole thread.
4. Human GO: the t5 worker writes the **graph manifest** (next section); a deterministic
   cron builds t6 + the slice cards; PR by the t6 worker; the root wakes up done → the
   bridge closes the issue + a Discord notification.

## Dev graph: validated manifest → deterministic cron

An issue's topology is **never** created by an LLM: on the way out of the human gate, the
t5 worker writes a manifest, validates it, and a cron builds the whole graph. That is what
removed the drifts seen before (phantom cards, inverted links, foreign assignees).

- **Manifest**: `~/.hermes/kanban/boards/<board>/specs/<issue>/slices.json` — keys
  `issue`, `repo`, **`branch`** (ONE only per issue: `wt/issue-<n>-<slug>`), and
  `slices[]` = `{k, slug, depends_on, parallel:{test,dev}, convergence, doc}`.
- **Mandatory validation** (`pj_slices_lint.py`, `exit 0`, otherwise `request-changes` on
  t5): `k` contiguous from 1; `depends_on` strictly smaller (no dependency ahead); `branch`
  present; and the `test` card must carry **≥3 scenarios** — nominal, **edge** case,
  **error** (keywords: limite/edge/bord, erreur/invalide/corrompu).
- **Construction** (`pj_graphwatch.py`, cron `*/5` no-agent, one per board): spots the
  `t6 submitted` cards with no children, reads the manifest, creates ALL the cards with
  idempotency keys (`pj-<key>-<repo>-<issue>`), then lays ALL the links — including the
  anti-deadlock links (production cards PARENT of t6). A silent tick when no t6 is orphaned.
- **`PJ_DRY_RUN=1` prints the plan and creates NOTHING**: check the topology by dry-run
  before any real run, then re-read the board.
- **A builder script with a DEFAULT assignee applies it to EVERY card it creates.** A card
  meant for a specialist profile ends up assigned to the orchestrator — with no error and no
  warning — and the wrong profile then runs it (or the guard-rail blocks it, depending on
  the allow-list). Every card whose owner differs from the default must pass its
  `--assignee` EXPLICITLY. The check is done after a REAL deployment by re-reading every
  card's `assignee` (`kanban show <id> --json`), never by re-reading the script.

## Hard rules (verified in the kanban_db.py source)

- **Direction of the links**: `link P C` = C waits for P to be done (multi-parents OK, all
  terminals required). Anti-deadlock: the dev sub-tasks are PARENTS of t6, NEVER
  `--parent t6` on a dev card.
- The root is not a parent of its steps: every t_i is a parent of the root.
- `promote` refuses from triage → `specify_triage_task` (direct API) or a direct sqlite
  UPDATE (the only triage transition with no CLI).
- A profile's cron resolves `--script` inside `~/.hermes/profiles/<profile>/scripts/`, NOT
  the global one; symlinks refused (realpath).
- **`kanban.auto_decompose: false` + `auto_decompose_per_tick: 0` in the config of the
  PROFILE WHOSE GATEWAY HOLDS THE DISPATCHER LOCK** (the dispatcher reads that profile's
  config — neither the card profile's, nor necessarily `default`'s). LIVED PITFALL: the key
  set in `~/.hermes/config.yaml` stopped nothing, because the lock was held by ANOTHER
  profile's gateway (profiles are islands, there is no inheritance) — the LLM decomposer
  kept hitting triage before the deployer and kept handing the work to a foreign profile.
  Identify the holder with a card's `claimed {'lock': '<host>:<pid>'}` event crossed with
  `hermes gateway list` (`.dispatcher.lock` can be empty), patch THAT profile, restart its
  gateway.
- Empty repo (HTTP 409, size 0): neither a dev branch nor a clone is possible. Two-phase
  watcher: A (wrappers+crons+board) at creation → issues imported into triage, 0 LLM;
  B (dev+clone+default_workdir) at the first commit, anchor resolved dynamically.
- **pj-buttons** plugin (pj-master profile, gateway): it must `defer()` the ACK IMMEDIATELY
  (without an ACK, Discord shows "didn't respond in time"), then comment + unblock through
  the kanban CLI. It accepts TWO custom_id schemes — `pj:<action>:<board>/<task_id>`
  (canonical) and `triage:<action>:<N>` (emitted by the helper
  `discord_thread.py send --go-nogo <N>`) — and resolves the target card server-side from
  the thread name (`<repo> #<N> · <title>` → the **blocked** card of the board: validate or
  grill, not the root). A plugin that only listens to its own scheme leaves the clicks inert
  (the worker emits the helper's scheme).
- After any config change: `pj-master chat -q "PONG"` + `finish_reason=stop` in
  logs/agent.log (a PONG that looked "successful" was once a 401).
- **A model change is only verified if the model ANSWERED.** The CLI summary
  (Session/Duration/Messages) does not show the model: a profile can keep running the old
  one, or fall back to another, with nothing showing it. Read the
  `Turn ended: ... model=<real model>` line of `logs/agent.log` and confront it with the
  intended model. Write BOTH keys (`model.default` AND `providers.<prov>.default_model`)
  into THAT PROFILE's config (`HERMES_HOME=~/.hermes/profiles/<p> hermes config set`) —
  otherwise `hermes profile list` keeps the old one; do not trust the output of `config
  set` without re-reading the file and the Model column.
- **A card of a `pj-*` board can be run by a foreign profile, silently.** A dispatcher held
  by another profile applies ITS `default_assignee`: work outside the graph, with no human
  gate and **no Discord thread** (the notification contract depends on t5, which does not
  exist). Detect it by reading the board, not by trusting the card's provenance —
  `SELECT id,status,assignee,created_by FROM tasks WHERE assignee='<foreign-profile>' OR
  created_by LIKE '%decompos%'` — and check that every card of a `pj-*` board really has
  parents and a `workflow_template_id` from the pipeline.

## Complementary profiles (pj-doc, pj-test, ...)

- **pj-doc** — architectural framing in the spec phase (SDD/DDD/TDD/hexagonal positioning,
  crossing infra/functional/code → `t3b doc-cadrage` card, upstream of t4); keeping the
  `docs/` vault during the dev phase; consistency review during the review phase; Hindsight
  feeding after the merge.
- **pj-test** — carries the tests pj-dev no longer writes: RED/GREEN, and guarantees
  coverage (>80 % per file of the diff). Writes only inside `tests/**`.
- **Adding a specialist profile = widening the admission guard-rail BEFORE creating its
  first card** (see the guard-rail section), then verifying its integration by a REAL run:
  a card assigned to the new profile that reaches `done` with a verifiable output — not a
  `PONG` and not a `ready` card. The most telling end-to-end test: make it produce an
  artifact (framing note, test report) and CHECK its content against the code.

## Bot Mode rooms: owned by pj-master (user decision)

**pj-master runs the rooms end to end** — one room per ticket, `room_id` =
`pj-<repo>-issue-<n>`, the `ensure → ask → report → disband` cycle carried by a
deterministic cron `pj-room-keeper-<board>` (*/5, no-agent). The room↔ticket link is a
`ROOM: <room_id>` marker inside the t4 body (laid down by the deployer; `kanban edit`
refuses active cards, so a card that already exists is migrated in the DB). The **board
stays the source of truth**: at the `report` step the transcript of the deliberation goes
out as a `kanban_comment` on the card. Nothing to do by hand.

Two design points to respect:

- **A room NEVER animates itself**: without `message.user`, the engine stays `idle`
  (`no_pending_user_event`) and the room is an empty shell. It is the `ask` step that
  animates it — hence the pointlessness of creating the room without planning the
  animation.
- **Bots do not need to be pinged to react to the card**: a worker that has the Bot Mode
  toolset sometimes posts its own draft into the room. The two paths (worker and keeper)
  coexist and complement each other — the keeper covers the rooms the worker does not
  animate.

Exact mechanics, bounds, multi-gateway livelock diagnosis and the escape hatch
(`request_room_stop`): `hermes-multi-agent-orchestration` → `references/hosted-rooms.md`.

## Card format contract (user requirement — applied to EVERY task/sub-task)

Every produced card body (t4 draft, t6, dev-k, future sub-cards) carries EXACTLY
5 numbered sections, in this order, plus an INVEST sizing:

1. **Context & Objective** — issue #N, value, objective = observable result (not an
   activity), upstream/downstream dependencies.
2. **Acceptance criteria (BDD/Gherkin)** — `Feature:` + **≥3 `Scenario:` :
   nominal + EDGE CASE + error** (user requirement: edge cases are first-class tests, on
   the same footing as the nominal one — not a bonus at the end of a card), in
   Given / When / Then ; every criterion automatable.
3. **DoR & DoD** — DoR: validated spec, worktree ready, parents done, no open question
   (otherwise `kanban_block`, never start "while waiting"). DoD: green tests, green repo
   checks, pushed commits, written handoff, artifacts, project memory updated.
4. **Technical considerations & guard-rails** — files/contracts touched, constraints,
   **explicit prohibitions**, risks + fallback.
5. **Out of scope** — what the card does NOT do AND where the subject is handled.

**INVEST**: 1 vertical slice = 1 card. Independent (a dependency = an explicit parent link,
never implicit), Negotiable, Valuable (demo/E2E test possible), Estimable (otherwise a
"spike" card), **Small ≤ ~1 agent day / ≤ ~400 lines / ≤ ~5 files / a single domain —
going over = split BEFORE creating**, Testable. A sub-card inherits the mother's context by
reference ("issue #N, slice k/N") and receives its OWN Gherkin/DoR/DoD block.

**Adversarial verification, not a prompt instruction**: `scripts/pj_card_lint.py`
(live copy in the pj-master profile's `scripts/`) lints the bodies by regex, 0 LLM,
exit 1 if non-compliant. Card t5 runs it before asking for the human go — a non-compliant
spec goes back to t4. The format brief is ALSO injected into the bodies that
`pj_pipeline_deployer.py` creates for t4/t5, otherwise only the derived cards inherit it.

```bash
python3 ~/.hermes/profiles/pj-master/scripts/pj_card_lint.py --board pj-<repo> [--all|--task <id>]
```

The linter excludes the process cards, the done/archived cards and tolerates
"Contexte"/"Context" and a varied numbering prefix (`1.`/`### 1.`).

**The exclusion of the process cards must be written as a GENERAL pattern**
(`^t\d+[a-z]?\b`), not as a closed list of the current steps (`^t[1-6]\b`): any step added
later (`t3b`, `t4a`, ...) becomes a mass false positive from its very first card, and it is
exactly when a step is added that the linter would be run. Conversely, a linter that
matches too widely makes the gate decorative.

## A deterministic check validates only its SCOPE

A compliance linter (documentary vault, card format, coverage) that scans the whole
repository produces **false positives on PRE-EXISTING content** — dozens of files
inherited from before the convention, all legitimate. The gate becomes unusable: it gets
turned off instead of fixed.

Rule: a gate validates only **the area where the convention applies** (e.g. the notes under
the vault's two directories, not all of `docs/`; the files of the diff, not the whole
repo). The associated verification requirement: **exercise the gate in BOTH directions —
silent on a healthy repository (exit 0) AND red on a deliberately faulty input
(exit 1)**. A gate that is only green proves nothing (see the "show it RED" rule above).

## A coverage gate must be shown RED

**Run the gate before relying on it**: if it comes out green on the first try on a repo
with partial tests, it measures nothing (missing report, ignored scope, over-wide exclusion
filter). Two lived scope traps:

- the scope is computed over **the modified files** (`git diff --name-only <base>...HEAD`),
  not over the whole report — an old untouched file would fail every slice;
- the exclusions (`is_code_file`, `_version.py`, `*.d.ts`, configs, the test tree) remove
  files from the count: a **test written before an exclusion was added** fails afterwards.
  The test is then obsolete, not the implementation — fix it, never the other way round.

## Admission guard-rail (isolation of the pj-* boards)

`pj_spawn_guard.py` (repo `hermes-experiment/pipeline/`, live copy
`${HERMES_WORKFLOW}/pipeline/`) refuses any work outside the pipeline on a `pj-*` board: it
blocks the card whose `assignee` is not in `DEFAULT_ALLOWED`. Registered on TWO hooks per
gateway profile: `on_kanban_dispatch_tick` (fires AFTER the dispatch lock is released →
blocks without a deadlock, and the card is not claimed on the next tick: **it is the one
that protects**) and `kanban_task_claimed` (fires AFTER the claim → the current spawn is
NOT cancellable; only report there, never rely on it to cancel).

OPERATIONAL RULE: **adding a profile to the pipeline (`pj-doc`, `pj-test`, ...) requires
registering it in `DEFAULT_ALLOWED` AND redeploying the copy used by the hooks, BEFORE
creating the slightest card** — otherwise all its cards are blocked before spawn, silently.
Verify by creating one card per assignee and then applying the `on_kanban_dispatch_tick`
hook: `ready` expected for the pj profiles, `blocked` for the others.

## Test coverage convention (user requirement)

**>80 % per test, over the files MODIFIED by the PR** (patch coverage), not over the whole
repository file by file: a slice must not fail because of an old file it never touched.
Back it with a global non-regression threshold. In TS the native vitest threshold
(`thresholds.perFile`) is global and cannot restrict itself to the diff → compute the
"patch" figure with `git diff --name-only origin/dev...HEAD` crossed with the coverage
report. Exclude the non-executable declarative files (`*.d.ts`, configs, `_version.py`,
the test tree itself).

Two rules that make the difference between a useful gate and a decorative one:

- **A threshold gate must be shown RED the first time it runs.** If it comes out green on
  the first try on a repo where the tests are partial, it tests nothing: check that the
  report really holds the targeted files and that the scope (`perFile`/diff list) is taken
  into account, before relying on it.
- **Edge cases are tested on the same footing as the nominal one** (see the format contract
  above): a coverage gate alone does not catch them — hence the verification by SCENARIO of
  the test card, not only by percentage.

## Sharing a worktree between several cards (peer programming)

**Sharing happens by BRANCH identity, not by path.** Verified in `kanban_db_workspace.py`:
`if actual_branch == branch_name: return <path>, branch` — two cards declaring the **same
`--branch`** reuse the same worktree; a different branch falls back **silently** onto a
worktree private to the card (`<repo>/.worktrees/<task-id>`). Therefore:

- one **branch per issue**, deterministic (`wt/issue-<n>-<slug>`), **never** derived from
  the card id, declared once and repeated on ALL the cards of the slice;
- after deployment, check that two sister cards have the same `workspace_path` AND the same
  `branch_name` (`kanban show <id> --json`) and that only one worktree exists on the git
  side (`git worktree list | grep -c`) — otherwise the `--branch` was not applied;
- design consequence: a single worktree per issue ⇒ slices that overlap are SEQUENTIAL,
  real parallelism exists only between disjoint components;
- write perimeters disjoint by contract (the test role writes only in the tests, the
  implementation only in the sources); conflict → `kanban_block`, never `--force`.

Lifecycle: an **upstream** card creates the worktree (`worktree-mk`, posts path+branch to
the blackboard, every slice card depends on it) and a **downstream** card deletes it after
the merge (`worktree-rm`, child of the PR card, requires `gh pr view --json state ==
MERGED` + `git merge-base --is-ancestor` on every commit, `kanban_block` otherwise).

## Manual onboarding of a new repo (otherwise pj-repo-watch does it)

1. GitHub `dev` branch (from the default). 2. Clone dev → `~/pj-repos/<repo>`.
3. `pj_bridge_<repo>.sh` / `pj_deploy_<repo>.sh` wrappers inside the profile's scripts/.
4. 2 no-agent crons + `pj-<slug>` board + default_workdir (set LAST = idempotent marker of
   a complete onboarding).

## LLM cost

Bridges, deployer, watcher, dispatcher, pj-buttons = **0 LLM**. Per issue processed:
~7-10 runs (deepseek-v4-flash:cloud): t1, t2, t3, t4, t5, each dev-k, t6.

## See also

`references/graph-manifest.md` (schema of the `slices.json` manifest, validation rules,
construction and dry run),
`scripts/pj_card_lint.py` (card compliance linter, 0 LLM),
`scripts/pj_coverage_gate.py` (coverage gate scoped to the diff, 0 LLM — copy it into the
profile's scripts/ before calling it from a card),
`gh-kanban-bridge` (bridge), `hermes-messaging-bots` (bot setup),
`hermes-multi-agent-orchestration` (class rules: link direction, gates, format, parallel
topology + convergence, worktree lifecycle),
`projecta-grooming` (grooming ≤3 questions), `obra/superpowers` (grill-me/brainstorming).

## Writing a plan or a spec that cites what exists

A plan meant for an implementer with no context propagates every error: **re-read at the
source every path, count and key name cited at the moment of writing it**, never from
memory or from a transcript (figures drift: a profile `.env`, a linter regex, a pinned
version, a hardcoded constant, a function signature). Behaviour to check in the code rather
than assume: the direction of kanban links, the worktree sharing rule, config defaults, the
line count of a cited file. When a user decision invalidates part of an already written
plan, REWRITE the sections concerned (no "update: actually..." add-on) — a plan holding two
contradictory truths cannot be executed.
