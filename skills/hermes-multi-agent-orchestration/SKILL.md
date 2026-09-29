---
name: hermes-multi-agent-orchestration
description: "Use when designing multi-agent workflows with Hermes kanban."
version: 1.0.0
tags: [hermes, kanban, bots, orchestration]
---

# Multi-agent orchestration with the Hermes builtin

Class: build a multi-agent pipeline (e.g. a scrum orchestrator profile + specialist
bots) with the builtin primitives ONLY — durable kanban, Bot Mode, hooks, cron —
without a custom orchestration engine.

## Rules that always hold

- **Builtin vs on-top, kept explicitly apart.** Durable builtin systems:
  delegate_task, cron, curator, kanban (+ Bot Mode = desktop UI on top of the
  profiles; a bot IS a profile). The YAML workflow engine (`workflows/*.yaml` +
  gate loading `workflow_template_id`) and the GitHub bridge are CUSTOM glue
  of the hermes-experiment repo: NEVER present them as builtin; name them as
  custom whenever they come into play. (Express user correction.)
- **Check the source before asserting** a kanban capability:
  `hermes_cli/kanban_db.py` (statuses, transitions, columns) +
  `hermes kanban <verb> --help` (e.g. no `update` sub-command).
- **The state machine is builtin and untouchable.** 9 fixed statuses:
  `triage, todo, scheduled, ready, running, blocked, review, done, archived`.
  No custom statuses without patching the core — the design is against it. The
  business "steps" live in the native columns `workflow_template_id` +
  `current_step_key` (card data, filterable through
  `kanban list --workflow-template-id/--step-key`). Advancing a step =
  bookkeeping by the orchestrator on the card, not a status transition.
- **Two kinds of gate, do not confuse them.** (1) Admission gate = hook
  `kanban_task_claimed`, BEFORE the worker is spawned. (2) Result gate = AFTER
  the work: `kanban_request_review` / `kanban_request_changes` (native —
  "the tests fail, rework your code" is that path, not the claim gate)
  or a PR completion contract (`--completion-contract`, done refused while the
  required checks are not green). Reusing the claim gate as an after-the-fact
  check is impossible: it runs before the work exists.
- **Link direction = who waits for whom (verified in `kanban_db.py`).** `link
  <parent> <child>` / `create --parent X`: the CHILD waits for the parent to
  finish (multiple parents = logical AND; `recompute_ready` keeps the child `todo`
  while a parent is not done, and the summary of every done parent is injected
  into the child worker through `_ctx_parent_results`). A "summary/submitted"
  card that must wait for its sub-tasks is built BACKWARDS: each sub-task is a
  PARENT of the summary card (decompose pattern: the root is linked under each
  child and wakes up once the whole graph is done). Never
  `--parent <summary>` onto one of its own inputs — deadlock (the input waits
  for the summary to be done, which waits for the inputs to deliver).
- **An orchestration root card is not a one-shot worker.** A spawned worker
  cannot "hand back control": `complete` marks it done (closing the upstream
  ticket/issue too early), `block` is sticky. The root that deploys a graph
  parks itself in `--triage` (at import: `create --triage`), a deterministic
  script deploys children+links, then it leaves triage through
  `kb.specify_triage_task` (a direct Python call, no LLM; the CLI
  `kanban specify` goes through the auxiliary LLM; `kanban promote` REFUSES triage).
 Once a child of all its tasks, it wakes up on its own at the end.
 Corollary: a worker that has ALREADY delivered can keep spinning without being able
 to hand back control (100 k+ token context, dozens of API calls, repeated
 `skill_view`/`terminal` tools with no write). Detect it by the ARTEFACTS, not by the
 process: compare the mtime of the produced files and the output volume — if they no
 longer move, the worker is finished even though the card says `running`. Recovery: kill,
 `kanban reclaim <id>` (the card goes back to `ready` and the dispatcher respawns it), and
 check that the new run really PRODUCES before concluding.
- **One fan-out mechanism per board.** The dispatcher's auto-decompose
  and a custom deployer both target triage roots: on the same
  board they duplicate the graph (parasite children that bypass the
  human gates). Disable one of the two; a custom deployer skips the
  roots that already carry a `decomposed` event. Auto-decompose is ON by
  default (`kanban.auto_decompose: true`) and **reads the config of the profile whose
  gateway holds the dispatcher lock**, not the card's profile config.
  An expensive corollary: profiles are islands, so setting
  `auto_decompose: false` in `~/.hermes/config.yaml` covers ONLY the
  default profile's gateway — if the lock is held by another profile, the
  decomposer keeps firing. **Identify the dispatcher profile BEFORE
  patching**: a card's `claimed {'lock': '<host>:<pid>'}` event gives
  the PID of the gateway that spawns; comparing it with `hermes gateway list`
  gives the profile (the `.dispatcher.lock` file can be empty — do not trust it).
  Then `auto_decompose: false` + `auto_decompose_per_tick: 0` in
  THAT profile's config.yaml, and restart its gateway.
- **A card on a pipeline board can be run by a foreign profile,
  silently.** A dispatcher held by another profile applies ITS
  `kanban.default_assignee` to triage cards and to the children it
  auto-decomposes: the work leaves for a profile unrelated to the pipeline,
  hence with no graph, **no human gate and no notification at all**. A
  notification contract that relies on the pipeline having created the card is
  a contract with a hole: detection must come from reading the board, not from
  trusting the provenance. Sweep (assignee/creator, not the display):
  `sqlite3 <board>/kanban.db "SELECT id,status,assignee,created_by FROM tasks
  WHERE assignee='<foreign-profile>' OR created_by LIKE '%decompos%';"`.
- **Stopping an actor outside the pipeline: kill THEN neutralise, and re-read the
  board.** `kill` alone leaves the card `running` with a claim: the dispatcher
  respawns it on the next tick. Chain: (1) kill the profile's workers
  (`ps -eo pid,args | grep 'hermes.*-p <profile>.*chat -q'`), check 0
  remaining. **A killed worker stays visible as a zombie** (`Zs [hermes] <defunct>`):
  `ps -p <pid>` counts it as ALIVE and makes you believe a process is active. Filter
  `grep -v defunct` (or read the STAT column) before concluding. A zombie that lingers
  runs nothing any more but keeps its claim: release it with
  `kanban reclaim <id>`, not by killing again; (2) neutralise each card. `kanban block` **is refused depending on the
  starting status** (observed from `todo` — "cannot block"); `reassign`
  works even from `todo` but makes the card spawnable by the new
  profile: if the stop must be final, archive. (3) Re-read the board and
  confirm that no card is `ready`/`running` on the target profile — a
  card neutralised "in the display" can stay engageable.
- **A card's format is checked mechanically, not by prompt.** A
  format instruction in the SOUL drifts (one-shot workers, respawns). The
  contract (mandatory sections, BDD scenarios, DoR/DoD, guardrails,
  out-of-scope, INVEST/Small sizing) must be covered by a deterministic
  0-LLM LINTER called before the human gate, with an exit code — that is what
  makes the requirement enforceable. The linter excludes PROCESS cards
  (pipeline steps, an imported root whose body is the upstream source) and
  done/archived cards, otherwise it produces false positives in bulk.
  The format brief must also be injected into the bodies the deployer
  creates, otherwise only the derived cards inherit it.
- **A deterministic gate is worth only its PERIMETER, and too wide a perimeter
  kills the gate.** A linter (card format, documentation vault,
  coverage) that scans the whole repository reports PRE-EXISTING content —
  dozens of files predating the convention, all legitimate: the gate
  becomes unusable and gets disabled instead of fixed. Restrict it
  to the zone where the convention applies (the vault directories,
  not all of `docs/`; the files of the diff, not the whole repo). Corollary on
  exclusions: they change the count, so a test written BEFORE an exclusion
  was added (`_version.py`, `*.d.ts`, configs, test tree) fails
  afterwards — it is the test that is obsolete, not the implementation.
- **A control that filters by pattern must filter GENERALLY, not with a closed
  list.** A linter that excludes pipeline steps by enumeration
  (`^t[1-6]\b`) turns any step added later (`t3b`, `t4a`) into false
  positives in bulk — precisely when a step is added, hence when
  the linter is run. Write the general pattern (`^t\d+[a-z]?\b`).
- **Prove a gate in BOTH directions: silent on a healthy input AND red
  on a faulty input.** A gate that is only green proves nothing (missing
  report, ignored scope, exclusion too wide); a gate that is only red destroys
  trust. Building a deliberately faulty input and checking
  exit 1 is part of the gate's delivery, not a comfort test.
- **A human gate as a button cannot depend on a custom_id scheme
  the emitter does not know.** When the worker emits the button through a
  generic helper and the listener lives in a plugin written for another
  scheme, the clicks are inert and the client shows "didn't respond in
  time" (the ACK never arrives). Rule: the listener must `defer()` the ACK
  IMMEDIATELY (before any resolution), accept the schemes emitted by the
  helpers in place, and resolve the target card server-side (from the context
  of the thread/message) instead of demanding a payload the emitter ignores.
  The bot API cannot simulate a click: test the handler on the
  real board (mock of the adapter, real kanban), not by hoping for a click.
- **Adding a specialist profile to a pipeline = widening the admission
  guardrail BEFORE creating a single card for it.** A board guardrail
  (assignee allow-list) refuses any unknown assignee: the new cards
  are blocked before their spawn, silently — the guard does exactly its
  job, nothing reports the error. Mandatory order: (1) widen the allow-list
  at the source, (2) copy over the DEPLOYED version the hooks really
  call (a guard often lives in two copies: the repo + a copy in
  the profile's scripts/), (3) restart the gateway holding the dispatcher,
  (4) test admission on a real board: one card per allowed profile AND one
  per forbidden profile, run the hook by hand, check ready vs blocked,
  archive the test cards. As long as (2)+(3) are not done, the test passes
  and the pipeline blocks anyway.
- **Parallelism and convergence: the builtin `kanban swarm` gives the topology.**
  `hermes kanban swarm --worker PROFILE:TITLE --verifier P --synthesizer P` writes
  a graph root → parallel workers → verifier (parents = all the workers) →
  synthesizer (parent = verifier). The shared "blackboard" is a structured
  JSON comment on the root card (`[swarm:blackboard]`), so the coordination
  lives in the native tables (comments/events) — no extra service or scheduler.
  For a **convergence loop** (peer programming: two roles in
  parallel then reconciliation), the primitive is the native review lane:
  `kanban request-review [--reviewer <profile>]` moves the card to `review`
  (dispatched if `kanban.review_dispatch`, default ON); `kanban request-changes
  <id> <reason>` SENDS it BACK to the implementer (review → todo, parent gating
  reapplied) — that is the "no, rework it" of the cycle, not a status to invent.
  Parallelism caps: `kanban.max_in_progress` (global) and
  `kanban.max_in_progress_per_profile` (otherwise N boards multiply the budget).
- **Two cards share a worktree by BRANCH IDENTITY, not by path.**
  Verified in `kanban_db_workspace.py`: the resolver does
  `if actual_branch == branch_name: return <path>, branch` — so two cards
  declaring the SAME `--branch` reuse the same worktree, while a
  DIFFERENT branch makes it fall back **silently** to a worktree private to
  the card (`<repo>/.worktrees/<task-id>`, branch `wt/<task-id>`) with no
  warning at all: peer programming becomes isolated work and the cards no
  longer share anything. Rule: **one branch per ISSUE**
  (`wt/issue-<n>-<slug>`, never derived from the card id), declared once in
  the graph manifest and repeated on ALL the cards of the slice; after
  deployment, check that two sibling cards have the same `workspace_path` AND the same
  `branch_name` (`kanban show <id> --json`) and that a single worktree exists on the git
  side (`git worktree list | grep -c`). Design consequence: a single worktree per
  issue ⇒ slices that overlap are SEQUENTIAL — real parallelism
  exists only between slices with disjoint components.
- **Coverage is measured on the card's perimeter, not on the whole repo.**
  A global per-file threshold (e.g. vitest `thresholds.perFile`) fails on code
  the card did not touch: the worker ends up blocked for work that
  is not its own. A card's gate scopes to ITS files (the diff list
  `git diff --name-only <base>...HEAD` crossed with the coverage report);
  keep a global threshold as an extra anti-regression guardrail, but it does not
  condition the card. And **limit cases are first-class
  tests** just like the nominal one: nominal + limit + error, otherwise the
  spec is incomplete (not "smaller").
- **NEVER retype a secret read from a config file.** The reading
  tools mask the keys (`sk-…`): the displayed value is not the real value,
  and copying it "while filling it in" produces a 401 (`token_not_found_in_db`)
  discovered only at the first real run. A new profile therefore copies the config
  of the source profile by PROGRAM (read the YAML, write the YAML — the key crosses
  without being displayed), never by manual rewriting.
- **A brand-new profile inherits nothing: duplicate the source profile's config.**
  The provider must be rewritten with its TWO keys (`model.default` AND
  `providers.<name>.default_model`) — otherwise `hermes profile list` and the picker keep
  the old model. A profile's secrets live in ITS `.env` (copy the required service
  keys, e.g. memory); platform variables (bot token)
  are NOT copied — a token belongs to one profile at a time.
- **Verify a claim BEFORE writing it into a plan or a spec.** A
  plan meant for an implementer without context propagates every error: each
  path, count and key name cited must be re-read at the source when it is
  written (figures drift: a profile `.env`, a linter regex, a
  version pinned in a lock). Same rule for a plan that cites an
  environment behaviour: read it in the code, not from memory.
- **`~` can point somewhere other than the expected HOME.** Some commands run
  in a context whose `$HOME` differs (sandboxed session): `ls ~/.hermes/...`
  returns "no such file" while the pipeline is intact. Before concluding that
  something disappeared, check `echo "HOME=$HOME user=$(whoami)"` and `pwd`; use
  absolute paths (`/home/<user>/.hermes/...`) in scripts and checks.
  A "vanished" directory is almost always a change of context, not a
  deletion.
- **Memory per project ≠ bank per profile (user requirement).**
  `bank_id_template` `{workspace}` yields a constant ("hermes", forced in
  agent_init.py) and the hindsight_* tools have no bank parameter:
  per-project isolation of a multi-profile pipeline = shared bank + tags
  `project:<slug>` mandatory on every retain (recall stays at the bank
  level; tag filtering goes through the REST API memories/list, not through the
  tool). A pipeline's memory must never depend on the profile that is
  running — it lives per project.
- **Cross-profile worktree: avoid `--project`.** It resolves the repo through the
  profile HOME's projects.db — a worker spawned under another profile does not
  see it. Anchor explicitly: `--workspace worktree:<absolute-repo-path>`
  or `hermes kanban boards set-default-workdir <slug> <path>` (per-board
  anchor, readable by every profile; the base = upstream tip of the anchor
  checkout → clone the anchor ON the wanted base branch, e.g. dev).
- **The dispatcher lock (`.dispatcher.lock`) is per machine, not per
  profile.** On a gateway (re)start it can switch to another one —
  the `claimed {'lock': ...}` event says who really spawns. The auto-assign
  `kanban.default_assignee` of the DISPATCHER PROFILE can overwrite the assignee of an
  imported card: check the root's assignee after deployment and
  `kanban reassign` if needed (a card assigned to the wrong profile is
  run by that profile when it becomes ready).
- **Cost: ticks consume nothing, the cost is per issue.** Crons
  `--no-agent`, the kanban dispatcher and plugins with deterministic handlers
  never call the LLM (silent tick = 0 call); the cost concentrates in the
  worker runs (~7-10 per issue processed, prompt cache ≥90 % observed) and
  the decompose auxiliary LLM. A pipeline at rest costs zero.
- **A Discord token belongs to one profile at a time.** Moving a bot
  to another profile = stop the OLD profile's gateway before putting
  the token in the new .env — two live profiles with the same token
  refuse to start the gateway (duplicate credential). The listeners
  `on_interaction` (buttons) live on the gateway carrying the token: after
  a move, reinstall the plugin on the new profile, otherwise the
  clicks are inert (fallback: a "go" text in the thread or CLI unblock).

## Recipe: scrum orchestrator pattern

1. **Input**: a card assigned to the scrum profile (dispatcher spawn) OR a Discord
   discussion (a cron/webhook of the scrum profile watches — the board opens
   nothing by itself: `kanban_create` + `assignee` engage a worker).
2. **Grooming**: ≤3 questions at a time in `kanban_comment` + `kanban_block`;
   the human answers then `unblock`; on respawn the worker re-reads the WHOLE thread.
   Conversational alternative: room/DM + `@user` (escalation).
3. **Split**: `kanban_create` children (one per domain) + `kanban_link
   parent→child`, assignee = specialist profile. Same board + links
   (recommended: auto promotion + visible dependency graph); a separate
   board only to really isolate a domain.
4. **Cascade**: parent done → children `todo→ready` on the NEXT dispatcher
   tick. To speed up: a hook on kanban events or a manual `hermes kanban
   dispatch`. A worker can create sub-children (free depth —
   no max_spawn_depth on the kanban side).
5. **Iteration/consolidation**: a quick opinion WITHIN a run = `delegate_task`
   (ephemeral); a durable opinion = a card. Stabilisation criterion written in
   the orchestrator's SOUL/prompt; consolidation = `kanban_complete
   (artifacts=[...])` — copied to durable storage before the scratch is cleaned.

## Pitfalls

- **An empty `default_assignee` = the DISPATCHER profile becomes the assignee.**
  Verified in the source: `kanban_decompose._resolve_profile_from_cfg` falls back to
  `get_active_profile_name()` when `kanban.default_assignee`/`orchestrator_profile`
  are empty — so the profile that RUNS the dispatcher (embedded gateway) assigns itself
  the cards. Symptom experienced: cards "created by auto-decomposer" assigned to an
  unrelated business profile (example-local) on a board dedicated to another pipeline.
  Fix: set `kanban.default_assignee` + `kanban.orchestrator_profile` in the profile
  THAT HOLDS THE DISPATCHER (not only in the pipeline's profile), and
  `kanban.auto_decompose: false` (default = True). Check the gateway log:
  `kanban dispatcher: default_assignee='<profile>'`.
- **Admission guardrail (board isolation).** When a board must be reserved for
  a list of assignees, the config is not enough (it gets lost again: another gateway,
  config recreated). A guard script wired on TWO hooks:
  `on_kanban_dispatch_tick` (fires AFTER the `_dispatch_tick_lock` is released → it can
  block without deadlock, and the card is not claimed on the next tick) +
  `kanban_task_claimed` (fires after the claim, hence BEFORE the spawn but WITHOUT being
  able to cancel the current claim: report only). Never attempt a blocking `kanban block`
  from `kanban_task_claimed` believing you are cancelling the spawn — it already happened.
- **Clean without loss: prove the work is already elsewhere before
  deleting.** Before deleting worktrees/branches believed obsolete,
  check for each one that the branch is ALREADY in the base (ancestor —
  `git merge-base --is-ancestor origin/<wt> origin/dev`) AND that the tree is clean
  (`git status --porcelain`). A "finished" worktree can carry unpushed
  commits. After a human MERGE, the remote branch survives the kanban cleanup:
  `gh api -X DELETE repos/<owner>/<repo>/git/refs/heads/<branch>`.
- **Break the links BEFORE archiving parasite cards.** Auto-decompose
  chains its children as PARENTS of the imported root: archiving the child does not
  unlink the root, which stays `todo` waiting for an archived parent — it will
  never wake up. Order: `kanban unlink <parasite> <root>` (and between
  parasites), then archive the parasites, then put the root back in its
  starting state to go through the pipeline again. The only transition back to
  `triage` is a direct UPDATE in the database (`kanban promote`/`specify` do not do
  triage ← todo) — acceptable for a repair, to be documented on the
  card with a comment.
- Declare any new card type IN the admission gate before
  creating it — otherwise a 429 rate-limit crash is declared as `protocol_violation` and
  falsely blocks the pipeline (the gate refuses, not the work).
- Workers do not spawn each other: "the architect delegates" = it creates
  linked cards and the DISPATCHER spawns. The data flow goes through the
  board (comments/attachments), never through the parent's memory — that is what
  makes the cascade durable and crash-safe.
- Changing a profile's model fixes neither the runs in flight nor the cards
  carrying a `workflow_template_id` (model forced per step by the custom
  engine): patch the YAML too and redispatch the unfinished cards.
- Kanban hooks are observers: exit code ignored, the influence travels
  through comments/cards.

## Room lifecycle (operations)

- **Room lifecycle = 4 states + one marker on the card.** The engine knows
  no link to a card: the room↔ticket link is carried by a `ROOM: <room_id>` marker
  in the card body (set at creation — `kanban edit` refuses active cards,
  hence a database migration for existing ones). Cycle: `ensure` (creation) → `ask` (animation) →
  `report` (transcript → `kanban_comment`) → `disband`. The state is read from the events:
  a discussion is FINISHED when a `room.activity` event carries `status` ∈ {settled, bounded}
  for its `discussion_event_id` (`bounded` = ceiling of 3 rounds / 10 messages reached).
- **Cycle safety rules (otherwise you lose work or saturate).** (1) `ask`
  only if the room is EMPTY (users=0) and the card active — re-animating an ongoing
  deliberation would restart it from scratch. (2) `disband` only after `report`: dissolving
  an unreported deliberation loses the agents' work. `pending` (deliberation in progress)
  is NEVER touched — reporting it mid-way would truncate the debate. (3) an EMPTY room
  on a finished card dissolves directly (nothing to preserve) — otherwise those rooms consume
  a `MAX_ACTIVE_ROOMS` slot for life.
- **A dissolved `room_id` is REMOVED FOR GOOD** (`hosted_room_retired_ids`,
  `create_room` raises `RoomConflictError: room_id belongs to a disbanded room`). That is not
  a bug: a dissolved id must never resume an old history. Consequence: a cycle
  automation must treat that error as terminal (ignore the room), never
  retry in a loop. Corollary: do not dissolve lightly — it is irreversible.
- **A gate/parser looking for a marker must find it EVERYWHERE in the body.** A regex
  anchored `^MARKER: (\S+)$` in MULTILINE misses the real case where the marker is buried in a
  line (card created on a single line): the automation goes silent with no error.
  Look for `MARKER:\s*(\S+)` without an anchor — and test that case (a regression experienced).

- **A room livelock must be detected and cut, otherwise the card dies with it.** The
  multi-gateway contention produces a stable non-progressive state: the gateway that wins the lease
  marks another's task `running` as `indeterminate`, the reconciliation cannot
  recover it and **defers** it serially (`turn.deferred`, `reason=member_unavailable`), while
  `plan_next_task` keeps answering `task/member_turn` — so the engine restarts
  indefinitely and the card stays `running`. **Detection signature: ≥2 consecutive
  `turn.deferred` with `reason=member_unavailable` at the end of the journal, with no `message.member`
  between them.** Count CONSECUTIVE defers, not the total (a long deliberation legitimately
  has many) and reset on any `message.member`/`turn.settled` (real
  progress). A single defer is not enough to cut (a transient incident).
- **The way out of a livelock is `request_room_stop` (fence `room.stop_requested`), not a
  kill.** `gateway.hosted_rooms.request_room_stop(db, room_id=…, cancel_id=…,
  expected_gateway_id=…, expected_epoch=…)`: `_pending_discussion` then ignores every
  `message.user` with seq ≤ the last stop, so the blocked deliberation is deemed closed and
  `plan_next_task` returns `idle`. Check afterwards that the plan really is `idle` — that is the
  only proof the livelock is broken. Trace the automatic stop on the card
  (comment + dedicated marker): a machine-triggered stop must stay auditable.
  Careful: a later new `message.user` restarts a deliberation — that is intended.
- **A card worker cannot "hand back control": it can live on as a zombie.** Observed:
  a kanban worker that has delivered its artefacts keeps its LLM calls in a loop (80 calls,
  150 k+ of context) and its process shows up as `Zs [hermes] <defunct>` — so `ps -p <pid>`
  answers **present** although it is dead. Always filter `grep -v defunct` before
  concluding that a worker runs. Repair a card stuck in `running`: stop the process,
  `kanban reclaim <id>` (releases the claim, the card goes back to `ready` and is respawned with all
  the context of the comments — including the room report).

- **A bridge that imports "every open issue" manufactures duplicate graphs.** With no
  coverage gate, a change request filed as a NEW issue starts a full new graph
  (t1..t5) while the delivery is in flight. Experienced: 3 issues (#4, #9, #10) for a
  single change, ~776 min of agent burned to conclude "redundant with #4". The gate is
  applied BEFORE the import and combines two signals: (1) `#N` references in the issue body
  (excluding URLs and bare numbers), (2) title overlap (Jaccard) against the issues having
  an open PR or a graph. **The gate does not decide**: it comments the issue with the two
  possible issues (attach / assume) and lets the human decide — a silent block
  would be worse than the duplicate.
- **Detecting a "covered issue" needs TWO sources: the native GitHub link AND the branch
  convention.** `closingIssuesReferences` is empty as soon as the PR omits `Closes #N` — verified
  on a real pipeline PR. Without the fallback on `feat/issue-<n>` in `headRefName`, the
  gate lets everything through. And without `Closes #N` in the t6 cards, GitHub never attaches
  the PR to the issue: closing then depends only on the bridge, so any issue opened on the
  same subject starts a brand-new graph.
- **Grill-me must QUALIFY the ambiguity, not summon the human.** Two mandatory
  outputs: (1) a quadrant per ambiguity — *liftable without a human? how? **cost if
  not lifted?***; an ambiguity liftable from the code/memory/docs is lifted alone; (2) a
  machine-readable verdict (`PROTOTYPE:`/`AMBIGU:`/`ARTEFACT:`) picked up by downstream steps.
  `PROTOTYPE: oui` only if the ambiguity cannot be lifted on a **perceptible** deliverable, or
  a perimeter > 3 slices on a domain that "shows", or a previous human rejection on the subject.
  Otherwise `PROTOTYPE: non` — the normal case. Demanding a prototype for every ticket is as harmful
  as a tunnel: it adds a human gate where there is nothing to arbitrate.
- **A "too much work before the first judgement" threshold must be MECHANICAL.** When the
  deliverable is perceptible (visual/UX/read text), the cheapest artefact (mock-up, plate,
  screenshot, diagram) is validated BEFORE the production slices: `prototype_required: true` in
  the graph manifest + a `preview` slice in FIRST position, parent of all the
  others, refused by the validator when absent or misplaced (`exit 1`). Experienced: ~55 h of agent
  and +5 355 lines produced before the first human look, a negative judgement.
- **Never wire an executable to a hard-coded path.** `shutil.which(gh) or "/usr/bin/gh"`
  produced `FileNotFoundError` (gh lives in `~/.local/bin`) in every subprocess without an interactive PATH
  — crons and Python kernels in particular; the bug only shows outside a login shell.
  Resolve it with `which` then a list of verified candidates (`isfile` + `X_OK`), never with an
  absolute default.

## Room vs board (Bot Mode group chats)

- Room (group chat 2-6 bots) = deliberation: an @mention triggers ≤3 rounds ×
  ≤10 msg/round, a bot may pass without answering, `@user` escalates to the human
  (needs-you badge). Each member keeps a persistent session
  `Group: <name>`; the room is durable if all the members share one
  gateway.
- **The room engine lives in the GATEWAY, not in the desktop — a room is
  created and driven from the command line.** The desktop is only a client:
  there is no CLI sub-command `hermes groups`, but everything goes through
  the low-level API `gateway.hosted_rooms` (see below). Do not conclude
  "out of scope" just because the CLI exposes nothing.
- **Real bounds (read in the code, ≠ docs):** `MAX_ACTIVE_ROOMS=256`
  (active rooms per host), `validate_roster` enforces **2-6 members**
  (`MIN/MAX_DISCUSSION_MEMBERS`), `MAX_DISCUSSION_ROUNDS=3`,
  `MAX_DISCUSSION_MESSAGES=10`, `max_concurrent_rooms=4` (simultaneous
  deliberations). The docs' "2-6" is therefore the business limit, not a
  UI limit; the schema's 128 members are a low-level bound.
- **A room is structurally tied to NO card.** The
  `hosted_rooms` table has neither `task_id` nor `issue` (the `task_id` visible elsewhere is
  a TURN identifier, table `hosted_room_remote_runs`). The
  room↔ticket link is a naming convention (`pj-<repo>-issue-<n>`) — hence
  findable without a mapping table, but a rename breaks it.
- **Creating a room from a script (low-level API):**

  ```python
  import sys; sys.path.insert(0, "${HOME}/.hermes/hermes-agent")
  from gateway import hosted_rooms as hr
  hr.create_room(hr.default_db_path(), room_id="pj-repo-issue-8", name="pj repo #8",
      members=[{"member_id": p, "profile": p, "handle": p} for p in PROFILS],
      authority_gateway_id=hr.local_authority_gateway_id())
  ```

  - Roster: exactly `{member_id, profile, handle}` (+ optional `display_name`,
    `target`) — an extra field is refused (`_exact_fields`). The
    profiles must be **local to the gateway** (`~/.hermes/profiles/`).
  - `disband_room(db, room_id=…, expected_gateway_id=…, expected_epoch=…)`:
    the epoch is **mandatory** (idempotent tombstone).
  - Reading: `list_rooms(db)` / `room_state(db, room_id=…)` /
    `read_events(db, room_id=…)`. ⚠️ `read_events` returns a **dict** with the
    key `events` (not a list); `get_room` and `list_events` do not exist.
  - No need for `wakeup()`: `bindings()` re-reads the database on every cycle
    (poll 5 s / 0.25 s active) and the loop discovers the created room on its own.
- **Bots NEVER speak on their own: a `message.user` has to be posted.**
  `plan_next_task` stays `idle` ("no_pending_user_event") — a created room
  stays mute indefinitely. Trigger (EXACT payload `{text, thread_id}`):

  ```python
  hr.append_event(hr.default_db_path(), room_id=rid, event_id=f"ev-{rid}-{tid}",
      kind="message.user", actor={"kind": "user", "id": "pj-master"},
      payload={"text": "…", "thread_id": tid},
      authority_gateway_id=hr.local_authority_gateway_id(), authority_epoch=1)
  ```

  Round 1 = the mentioned members (no mention = all); rounds 2-3 = opt-in
  (a quoted peer that has not spoken yet).
- **⚠️ Multi-gateway trap: the room database is SHARED by all profiles.**
  `default_db_path()` = `~/.hermes/shared-state.db`, whatever the profile
  (deliberate: to keep profile gateways from writing into `state.db`). And
  **every gateway starts its room worker**, with no disabling lever.
  Consequence experienced: with several active gateways, they fight over the room
  lease (`lease_ttl_seconds=30`) and the winner marks `indeterminate` every
  `running` task without its own fence (variable `foreign_running`,
  `hosted_room_driver.py`) — a deliberation can therefore go
  `indeterminate`. **It is NOT self-healing**: the reconciliation cannot
  recover another process's turn, it "defers" it with
  `reason='member_unavailable'` every ~60 s — as long as the lease circulates, the cycle
  `indeterminate → deferred → retry` spins indefinitely and the deliberation stops
  progressing. The lease guarantees mutual exclusion (no duplicate `event_id`) but **not
  progress**. Escape hatch: `request_room_stop` (fence `room.stop_requested`),
  which supersedes earlier turns and makes the planner return to `idle` — prefer
  that fence over a kill. Safe regime: **a single active deliberation** when several
  gateways run. Quantitative diagnostic (`lease_generation` counter, number of
  distinct `run_process_generation`) and the full mechanism:
  `references/hosted-rooms.md`.
- Board = commitment: decisions, artifacts, statuses, audit. The pivot bot
  (scrum) takes part in the room AND carries the kanban_* tools: it writes the
  conclusions in `kanban_comment`. A room never replaces the board as the
  source of truth.
- `message_agent` (bot↔bot DM, fire-and-forget) exists only in the canonical
  Bot Chat — in a room, @mentioning is enough.
- Cost: the room runs several bots per exchange; the board one worker
  at a time. Deliberate in the room, deliver on the board.

## See also

- Skill `hermes-kanban-multiagent-pipelines`: activating both layers
  (Desktop board = Capabilities toggle, tools = root key `toolsets`),
  and its `references/activating-kanban.md` for the diagnostic "who holds the
  dispatcher lock" (`fuser -v ~/.hermes/kanban/.dispatcher.lock`).
- `kanban-gate`: worker protocol for reading/acting on the `[gate]` verdict.
- `gh-kanban-bridge`: GitHub↔kanban bridge + the custom glue (YAML workflows).
- Bundled `hermes-agent` skill: routing table to the official docs.
- `references/kanban-builtins.md`: transition table + room mechanics.
- `references/hosted-rooms.md`: low-level rooms API (signatures, real bounds,
  event kinds, shared database), lifecycle, and the multi-gateway livelock diagnostic
  (`lease_generation` counter, `request_room_stop` fence).
- `references/issue-pipeline.md`: the full GitHub issue → PR pipeline — import
  into triage, mechanical deployer, human block/unblock gates, submitted/PR,
  card format contract (5 sections + BDD + DoR/DoD + INVEST).
- `pj-pipeline/references/graph-manifest.md`: schema of the graph manifest
  (`slices.json`) and the rules its validator must refuse — the concrete
  counterpart of the "the graph is built mechanically" rule.
- `scripts/kanban_card_lint.py`: deterministic 0-LLM linter for the card format
  contract (sections, BDD, DoR/DoD, guardrails, sizing) — exit 1 when
  non-compliant; to be called BEFORE a human validation gate.
- `scripts/pj_repo_watch.py`: automatic onboard watcher for new repos
  (live copy in the orchestrator profile's scripts/), onboard in 2 phases.
- The cron scheduler resolves `--script` in the PROFILE's scripts/
  (`~/.hermes/profiles/<name>/scripts/`), not `${HERMES_WORKFLOW}/pipeline/` (which is only the
  default profile's case) — copy the scripts there (no symlink, refused by realpath).
  A script in the wrong place = repeated silent failure `Script not found`: the ticks
  of a no-agent cron all look alike, so CHECK `Last run: ok` in
  `hermes cron list` after creation (otherwise you wrongly believe the automation runs).
  An empty stdout is NOT proof that a cron works.
- A bot profile's allowlist (`DISCORD_ALLOWED_USERS=<discord_user_id>`): without it
  the human is ignored silently, and a fail-closed button handler rejects the click with no
  message. Check the real ID through `/guilds/<id>/members` of the Discord API, not from memory.
- **The bridge is parameterised by env — one copy serves N projects.**
  `GH_REPO` + `KANBAN_BOARD` + `KANBAN_ASSIGNEE` (+ `BOT_GRACE_SECONDS`, and a flag to
  import into `triage` instead of `ready`). Two repos on the SAME board collide:
  the idempotency key is `gh-issue-<n>`, numbered per repo → 1 board per repo. A
  default `BOT_GRACE_SECONDS` reserves fresh issues for a triage bot: set it
  to 0 on boards without a bot, otherwise new issues look ignored for 10 min.
  An empty repo (no commit) is neither clonable nor branchable — the issue import can
  still run (pending cards): split the onboard into two phases (board+crons
  at repo creation, branch+clone at the first commit).
- Auto-onboard of new repos: deterministic watcher (live copy
  `scripts/pj_repo_watch.py`, cron */10 on the orchestrator profile) —
  detects any non-archived repo without a `pj-<slug>` board and runs the
  4 onboard steps (dev branch, anchor clone, wrappers, crons) then sets
  the board LAST as a completion marker; idempotent, an empty repo
  = deferred to the first commit, retried on the next tick on failure.
