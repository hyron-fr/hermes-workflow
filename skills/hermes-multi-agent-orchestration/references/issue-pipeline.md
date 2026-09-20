# GitHub issue → multi-agent PR pipeline (pj pattern)

Class: one orchestrator (Discord bot profile, e.g. pj-master) + workers (e.g.
pj-dev) turn every GitHub issue into a validated spec, then into a PR. Shared
memory (single bank + `project:<repo>` tags), never bound to the profile.

Validated end to end: import → t1..t5 → human go → dev phase →
t6 → PR opened (without merge) → issue closed by the push bridge.

## Per-repo infrastructure (done once)

1. Base branch `dev` on the remote repo: `git push origin
   origin/<main>:refs/heads/dev` (from a local checkout) or, without a checkout,
   `gh api -X POST repos/<owner>/<repo>/git/refs -f ref=refs/heads/dev -f
   sha=<sha of the main branch>`.
2. Anchor clone ON dev: `git clone --branch dev <url> ~/pj-repos/<repo>` —
   the worktree resolver branches from the upstream tip of THAT checkout, so the
   anchor must sit on the intended base branch (never a main checkout on another
   branch).
3. `hermes kanban boards create pj-<repo>` then
   `hermes kanban boards set-default-workdir pj-<repo> ~/pj-repos/<repo>`:
   `--workspace worktree` cards land in `<repo>/.worktrees/<id>`
   without projects.db — hence readable by every profile of the pipeline.
4. Bridge wrapper `${HERMES_WORKFLOW}/pipeline/pj_bridge_<repo>.sh`: export a PATH with
   ~/.local/bin (the cron scheduler does not see gh), then `GH_REPO`,
   `KANBAN_BOARD=pj-<repo>`, `KANBAN_ASSIGNEE=<orchestrator>`,
   `BOT_GRACE_SECONDS=0` if no drill bot serves the repo,
   `PJ_IMPORT_TRIAGE=1` (import into triage — the root must never be
   claimable as a worker) ; `exec python3 <canonical repo>/pipeline/
   gh_kanban_bridge.py "$@"`.
5. Cron `--no-agent` */5 per repo, created ON THE ORCHESTRATOR PROFILE (HERMES_HOME
   of that profile) ; empty stdout = silent tick.

## Graph deployer (deterministic script, no-agent cron)

Root imported into triage → script WITHOUT an LLM:
- derives repo + issue number from the `Importé depuis <url issue>` line of the body
  (skip otherwise) ; idempotence: skip if children already present or event
  `decomposed` ; idempotency-key per step `<prefix>-t<k>-<repo>-<n>`.
- creates t1 worktree (`--workspace worktree`), t2 memory, t3 grill-me,
  t4 draft, t5 validate — all `--assignee <orchestrator>`, self-carrying
  bodies (the worker re-reads card+thread, not the parent's memory).
- links (the child waits for the parent): t1,t2,t3 parents of t4 ; t4 parent of
  t5 ; each t_i PARENT of the ROOT (it wakes when everything is done).
- leaves triage via `kb.specify_triage_task` (direct Python import of the
  hermes_cli module ; the `kanban specify` CLI goes through the aux LLM ; `kanban promote`
  refuses the triage status).
- Cron `--no-agent` */5 ON THE ORCHESTRATOR PROFILE: one bash wrapper per board
  exporting `PJ_BOARD=pj-<repo>` then exec'ing the deployer — the scheduler does
  not share the interactive env, the job's env is set inside the wrapper.

## Human gates (block/unblock)

- t3 grill-me: the worker creates the issue's Discord thread
  (`discord_thread.py create <channel> "Issue #N" "..."`), asks ≤3 questions
  (1/message), summarises in the card, `kanban_block` (waiting for a human answer).
- The human answers in the thread → `hermes kanban unblock <id>` → re-spawn:
  the worker re-reads the WHOLE thread + the answers, then `kanban_complete`.
- t5 validate: the worker updates the issue (`gh issue edit N --body` — spec with
  code refs verified in the worktree), notifies Discord (go/no-go buttons),
  `kanban_block` until the explicit go. Never any self-validation.

## Card format contract (user requirement, generalisable)

Every card that specifies or implements (not the process cards) carries 5 numbered
sections in order — this is what makes a spec re-readable by a worker who does not
have the conversation:

1. **Context & Objective** — source (issue #N), value, objective = OBSERVABLE RESULT
   ("the user can X", not "work on X"), upstream/downstream dependencies.
2. **Acceptance criteria (BDD/Gherkin)** — `Feature:` + ≥2 `Scenario:`
   (nominal + edge/error), steps Given/When/Then ; every criterion
   automatable (otherwise write it and say how it will be verified).
3. **DoR & DoD** — DoR: spec validated, worktree ready, parents done, no open question
   (otherwise `kanban_block`, never start "while waiting"). DoD: criteria covered
   by green tests, green repo checks, pushed commits, written handoff, artifacts,
   project memory updated.
4. **Technical considerations & guardrails** — files/contracts touched, constraints,
   explicit prohibitions, risks + fallback.
5. **Out of scope** — what the card does not do AND where the subject is handled.

Explicit **INVEST** sizing, because a worker is one-shot and a catch-all card
cannot be resumed: 1 vertical slice = 1 card ; Independent (dependency =
explicit parent link, never implicit) ; Valuable (demo or E2E test possible) ;
Estimable (otherwise a "spike" card) ; **Small ≤ ~1 agent-day / ≤ ~400 lines / ≤ ~5
files / 1 single domain — over that = split BEFORE creating** ; Testable. A
sub-card references the mother ("issue #N, slice k/N") and carries its OWN
Gherkin/DoR/DoD block.

## Graph extensions: specialised roles (test, doc, archi)

A pipeline with a single "dev" worker generalises by adding per-role cards,
with no new engine — same parent/child mechanics, same gates.

**The dev graph must be MECHANICAL, not built by the LLM.** Having the validate
worker create t6 and its children produced real drift (phantom cards,
reversed links, assignees outside the pipeline). Retained pattern: the t5 worker
writes an artifact JSON manifest (`specs/<n>/slices.json` under the BOARD's own
folder) that validates its entries, then a deterministic 0-LLM script (cron
`--no-agent`) reads that manifest and builds t6 + every card + EVERY link. The graph
becomes reconstructible, re-readable and dry-runnable (`PJ_DRY_RUN=1` prints the
plan without creating anything). An invalid manifest → `request-changes` on t5:
validation is a gate, not a courtesy.

What the manifest validator must REFUSE (each rule matches a drift that really
reached a board):

- `issue` / `repo` absent, `slices[]` empty ;
- `k` not contiguous from 1 (hole = a card never produced) ;
- `depends_on` holding a value ≥ `k` — a slice cannot depend on itself
  nor on a downstream slice (reversed dependency = mutual wait) ;
- **`branch` absent or diverging between slices**: it is what makes them share the
  worktree (see below) ; a manifest without a single branch produces a "parallel"
  batch that shares nothing ;
- a `test` card without its **three scenario natures** (nominal + edge case +
  error): two scenarios are enough for an ordinary card, not for a test card —
  that is the rule that makes edge cases opposable ;
- any `parallel` card empty (a role announced but no card).

**A DEFAULT assignee set on the builder applies to EVERY card it creates.** The
script written for an orchestrator creates orchestrator cards by default: the card
meant for the specialist is silently assigned to the wrong profile (it is then run
by that profile, or blocked by the admission guardrail — in both cases silently,
without error or warning). Every card whose owner differs from the default must
receive its assignee EXPLICITLY at `create` time. Mandatory check AFTER a REAL
deployment: re-read each card's `assignee` (`kanban show <id> --json`) — re-reading
the script proves nothing, the script is right and the board is wrong.

**Per-slice topology, with convergence:**
- the roles of one slice run in parallel when they are independent
  (writing tests vs implementing), then a convergence card
  reconciles them — `request-review` to judge, `request-changes` to send back
  (a loop, not a failure) ;
- sequential roles stay chained by a parent link (the doc after
  convergence, the review after the doc): the dependency carries the order,
  never trust in the prompt ;
- **a dependent slice waits for the UPSTREAM CONVERGENCE**, not only its
  implementation card: both of its sides (test and dev) take `conv-<upstream>`
  as parent, otherwise they start on an unreconciled state ;
- **anti-deadlock unchanged**: t6 and its closing card wait for (are CHILDREN of)
  every implementation card ; none of them is a child of t6 ;
- a post-merge memory card (feeding durable memory from the delivered doc)
  is PARENT of the root and CHILD of the cleanup card: it must check the real
  state of the PR before acting, and `kanban_block` if the human merge has not
  happened — otherwise it blocks the issue closure forever.

**Worktree lifecycle: an UPSTREAM card + a DOWNSTREAM card.** In a parallel
batch, neither sibling card can create the worktree without racing the other:
a dedicated `worktree-mk` card (assigned to the implementation role) creates it
and publishes path+branch on the blackboard ; every slice card depends on
it. Symmetrically, a post-merge `worktree-rm` card removes it — it is a
child of t6, requires `gh pr view <url> --json state == MERGED` AND
`git merge-base --is-ancestor` on every commit before deleting, and
`kanban_block` otherwise (the native kanban cleanup preserves dirty/unpushed
worktrees anyway, but a remote branch survives that cleanup).

**Deterministic branch = worktree sharing.** The resolver compares the card's
branch against the target worktree's and falls back SILENTLY on a worktree of its
own when they differ: the branch is therefore a shared work identifier
(`wt/issue-<n>-<slug>`), declared once for the issue and repeated on
every card — never a `wt/<task-id>`. The graph manifest carries a single
`branch` key, and the build script adds it to every worktree `kanban create` of
a card (`if card.get("branch"): args += ["--branch", card["branch"]]`):
without that `--branch`, the sibling cards share nothing and the peer programming is
silently decoupled.

**Write perimeters disjoint by contract.** Two workers in the same worktree only
get in each other's way if they are allowed to: the test role writes ONLY inside the
test tree, the implementation role ONLY inside the sources, and the blackboard
freezes the `contract-<k>` key (API signatures, test paths) BEFORE either of them
writes. Conflict or doubt → `kanban_block` on the faulty card, never a
`--force` nor a merge of parallel branches.

**Documentation role — four phases, each a card.** (1) in spec: architectural
framing (positioning in the existing system, crossing infrastructure /
functional / code, reading SDD/DDD/TDD/hexagonal) upstream of the draft card ;
(2) in dev: versioned vault + in-code doc AFTER the slice convergence ;
(3) in review: coherence code ↔ doc ↔ objective, opposable verdict (the vault
linter's output, not an appreciation) ; (4) post-merge: feeding durable
memory from the vault, idempotent by content hash so an unchanged note is not
re-sent on every pass.

**Convergence loop: bound the iteration.** `request-changes` sends the
implementer back as many times as needed ; the guardrail is the native circuit
breaker (`consecutive_failures` / `kanban.failure_limit`, default 2) which
auto-blocks and escalates to the human. Writing corollary: the convergence card
must list PRECISE, actionable deviations — a "redo it" instruction consumes a full
iteration without resolving anything.

**Spec artifacts outside the repo.** A graph manifest or a framing meant for the
workers (not for the product) go under the board folder
(`~/.hermes/kanban/boards/<board>/specs/<n>/`), not in the repository: zero noise in
the PRs, and readable by every profile. What is a deliverable (doc vault, ADR)
stays in the repo, versioned with the code it describes.

**Versioned documentation vault.** When a role owns the doc, make it
verifiable like code: mandatory frontmatter, internal links resolved by file
name, every note referenced from its index (an orphan note = a lost note),
a dedicated deterministic linter on top of the same rule "an instruction alone → drift".

Implementation: the contract is at once (a) written in the SOUL of the orchestrator AND
of the worker, (b) injected into the bodies the deployer creates (otherwise only
DERIVED cards inherit it), and (c) verified by a deterministic 0-LLM linter called
before the human gate (exit code) — an instruction alone drifts. See
`scripts/pj_card_lint.py` (live copy in the orchestrator profile's scripts/).

## Go → dev phase

On go, the t5 worker writes the graph manifest and validates it (previous section) ;
a deterministic cron then builds t6 "submitted" and the whole set of slice cards
with their links. The worker creates NO dev card itself — that is the rule
that removes graph drift.

**Anti-deadlock (invariant)**: t6 is created with `--parent <t5>`, then each
production card (implementation, convergence, doc, review) is linked as PARENT of t6
(`link <card> <t6>`): t6 wakes when they are all done, and the aggregator is
NEVER parent of its inputs. A production card that ends up CHILD of t6 makes it
wait forever.

The slice cards: `--assignee <role> --workspace worktree --branch <branch
unique to the issue>`, TDD + the repo's checks cycle (e.g. Taskfile.ia.yml:
worktree:start → task:start → task:check → task:submit). All creations carry
an explicit idempotency-key (`pj-<key>-<repo>-<n>`) — the builder is a */5 cron:
without a key, two close ticks duplicate the graph.
t6 awake: it opens the PR (`gh pr create`), posts the URL (card comment +
issue + Discord), `kanban_complete` — or `--completion-contract OWNER/REPO`
on t6 if the repo has required checks. ROOT awake (all t_i done) →
the push bridge closes the issue with the worker's handoff.

## Operational pitfalls

- **The dispatcher lock can be held by another profile — identify it BEFORE
  patching.** A foreign dispatcher applies ITS `default_assignee` to triage
  roots and to the children of its auto-decompose: the work leaves the graph,
  **with no human gate and no Discord notification** (the notification contract
  depends on t5, which never exists). The holder is read from a card's `claimed
  {'lock': '<host>:<pid>'}` event crossed with `hermes gateway
  list` (`.dispatcher.lock` can be empty). Detect leaks by reading the
  board, never by trusting the provenance: `SELECT
  id,status,assignee,created_by FROM tasks WHERE assignee='<foreign-profile>'
  OR created_by LIKE '%decompos%'` ; any card of a `pj-*` board must have
  pipeline parents.
- **Stopping an out-of-pipeline actor = kill THEN neutralise THEN re-read.**
  `kill` alone leaves the card `running` with a claim → respawn at the next
  tick. Kill the profile's workers (`ps -eo pid,args | grep 'hermes.*-p
  <profile>.*chat -q'`), check that none is left, then neutralise each
  card: `kanban block` is REFUSED depending on the starting status
  ("cannot block" from `todo`), `reassign` works from `todo` but renders
  the card spawnable by the new profile (if the stop must be final:
  archive it). Finish with a re-read of the board: a card neutralised in the
  display can still be `ready`/`running`.
- Archiving a card with an active run: `hermes kanban reclaim <id>` FIRST
  — otherwise the in-flight worker keeps writing (parasite children/comments)
  after the archive.
- After a human MERGE of a PR: the kanban cleanup preserves dirty/unpushed
  but does not delete the remote branch — `gh api -X DELETE repos/<owner>/<repo>/git/refs/heads/<wt branch>`
  post-merge, otherwise the wt/ branches accumulate on the repo.
- Auto-onboard of the following repos: a deterministic watcher (live copy in
  the orchestrator profile's scripts/, cron `--no-agent` */10) — detects any
  non-archived repo without a `pj-<slug>` board and runs the 4 steps
  idempotently, the board being set LAST as the completion marker ; an empty
  repo = deferred to the first commit (409 on /commits) ; retry at the next
  tick on an intermediate failure.
- Bridge idempotency-key = `gh-issue-<n>` WITHOUT a repo → 1 board per repo
  mandatory (collision as soon as an issue number is shared between repos).
- Discord buttons inert after a token move: the on_interaction listener
  lives on the OLD profile's gateway — reinstall it on
  the new one, otherwise a text "go" fallback in the thread or the `unblock` CLI.
- Check the living thing after any profile config edit: `chat -q "PONG"` +
  `logs/agent.log` must show `finish_reason=stop` — a 401 auth exits
  cleanly, the CLI banner alone is no proof.
- The hermes-discord tools do not exist in a cron/CLI session: the bot's
  crons go through the REST helper discord_thread.py (create|send|threads),
  whose TOKEN_FILE must point at the .env of the profile that owns the token.
- Portable decision buttons: platform plugin `pj-buttons` (orchestrator
  profile, generalised from gh-triage-buttons). It must accept TWO custom_id
  schemes — `pj:<go|nogo>:<board>/<task_id>` (canonical) and
  `triage:<go|nogo>:<N>` (the one emitted by the generic helper `discord_thread.py
  send --go-nogo <N>`: a one-shot worker calls the helper as is) — and
  resolve the target card SERVER-SIDE from the thread name
  (`<repo> #<N> · <title>` → the board's `blocked` card: validate/grill, not
  the root). ACK (`defer()`) BEFORE any resolution, otherwise the client shows
  "didn't respond in time" ; the click runs no LLM (CLI comment +
  unblock). A listener that accepts only its own scheme renders all
  clicks inert. Porting: copy the plugin folder, add it to
  `plugins.enabled` of the target profile, `hermes plugins doctor <name>`, restart
  the gateway, check the log `Wired native handlers from plugin ...` ; the bot
  API does NOT allow simulating a click → test the handler on the real board
  (adapter mock, real kanban), never by waiting for a click.
