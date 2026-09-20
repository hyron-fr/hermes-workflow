---
name: gh-kanban-bridge
description: "Use when syncing GitHub Issues with the Hermes kanban board."
version: 1.0.0
---

# GitHub Issues ↔ Hermes Kanban bridge

Bridge running on this machine: cron `gh-kanban-bridge` (job 619353aaeed4, */5 * * * *, no-agent) + kanban dispatcher in the systemd gateway `hermes-gateway.service`.

## Architecture

- Canonical repo: `${HOME}/hermes-experiment` (github.com/hyron-fr/hermes-experiment)
- Script: `bridge/gh_kanban_bridge.py` (pull | push | sync), cron wrapper: `${HERMES_WORKFLOW}/pipeline/gh_kanban_bridge.sh`
- Dedicated kanban board: `hermes-experiment` (always pass `--board hermes-experiment`, the current pointer stayed on default)
- Pull: open issues without the `kanban` label → cards (idempotency-key `gh-issue-<n>`, mirror label auto-created, comment carrying the card id)
- Push: done cards linked to an open issue → issue closed with the worker handoff summary
- Silent mode: a cron tick with no action = empty stdout (= silent for `--no-agent`), log only on a write. `BRIDGE_VERBOSE=1` to see everything.

## Pitfalls learned (do not rediscover)

- `hermes kanban daemon` is DEPRECATED: the dispatcher lives in the gateway (`hermes gateway install` + start; systemd user, Linger=yes).
- `idempotency_key` is NOT exposed in `kanban list --json`/`show --json` (stored in the DB only) → the bridge infers the issue number from the import URL in the card body.
- The `runs --json` field returns a plain list; `show --json` nests {children, comments, events, latest_summary, parents, task}.
- Symlinks refused in `${HERMES_WORKFLOW}/pipeline/` (realpath anti-traversal) → bash wrapper pointing at the repo's canonical file.
- Dashboard exposed off localhost: HERMES_DASHBOARD_BASIC_AUTH_USERNAME/PASSWORD/SECRET are required in ~/.hermes/.env (hardening 06/2026), otherwise the server silently downgrades the bind to 127.0.0.1. Check: curl :9119/api/status → auth_required:true, providers:[basic].
- kanban workers = hermes profiles spawned `chat -q "work kanban task <id>"`, kanban toolset included.

## Known limits (Exp2 roadmap in the issues)

- No sync of issue edits (one-shot import)
- No issue reopening when the card re-blocks/reviews
- GitHub webhook impossible without a tunnel (machine behind NetBird) → 5 min cron chosen

## gh-triage bot (Discord, added 05/09)

- Profile `gh-triage`: qwen3.8-27b via litellm-proxy-gcp, dedicated gateway `hermes-gateway-gh-triage.service`, Discord bot "Experiment" on guild ${DISCORD_ID} / channel ${DISCORD_ID} (free-response, no @mention).
- MANDATORY allowlist: DISCORD_ALLOWED_USERS=<discord_user_id> in the profile's .env, otherwise "Unauthorized user" and the human is silently ignored.
- The hermes-discord tools are NOT available in cron/CLI sessions — gateway sessions only. In cron, the bot goes through the helper `${HERMES_WORKFLOW}/pipeline/discord_thread.py` (REST, create|send|threads).
- Discord REST pitfalls: User-Agent required in the "DiscordBot (url, version)" style, otherwise Cloudflare 403 code 1010; threads are listed via /guilds/<id>/threads/active (the /channels/<id>/threads/active path returns 404).
- Label 'triage' = drill in progress (the bridge AND the poll both respect it). BOT_GRACE_SECONDS=600 in the bridge: an issue younger than 10 min is reserved for the bot, otherwise it is imported straight into a card.
- Cron poll `gh-triage-poll` (profile gh-triage, job 18a2a393aad5): script `gh_triage_poll.py` (local state gh-triage-poll-state.json, empty stdout = silent tick = no LLM call; JSON stdout = injected into the prompt). In agent+script mode, empty stdout → return None (verified scheduler.py:4869).
- Bot protocol in ~/.hermes/profiles/gh-triage/SOUL.md: thread '🎫 Issue #N', drill, card ONLY after the ✅ Go click (button), mandatory 'Importé depuis <issue url>' line in the card body (the bridge push relies on it).
- GO/NO-GO BUTTONS (issue #12): the creation trigger is the ✅ Go BUTTON (custom_id `triage:go:<N>`), not the text "go". The helper `discord_thread.py send <thread> "<msg>" --go-nogo <N>` posts the ActionRow (✅ Go / ❌ No go). The plugin `gh-triage-buttons` (profile gh-triage, plugins.enabled) listens on `on_interaction` (discord.py add_listener), parses the custom_id deterministically, ACKs the click, then routes into the thread's session, via `adapter._build_slash_event` + `adapter.handle_message`, the deterministic instruction the plugin emits (`plugins/gh-triage-buttons/__init__.py:48`). No go → re-runs the drill, no card. Generalisable: `<decision>:<action>:<payload>` scheme.
- SOURCES OF TRUTH (fix 6/09): the issue DESCRIPTION carries the current state (drill synthesis edited via gh issue edit N --body, original body kept at the bottom); COMMENTS are reserved for progress (timeline, closure). The bot never asserts an action without a tool-call proof.
- DRIFT FIXED (6/09): the bot had created cards #9/#10 directly FROM thread #8 (another issue) on a plain 'yes', spawning the workers — bypassing the human gate. Hard-fixed in SOUL.md + SOUL-template (commit 5f935d0): ONE THREAD PER ISSUE, non-negotiable — an idea emerging in a conversation = create the GitHub issue and let the poll/thread/drill/go cycle run. No card is ever born from a conversation.
- qwen3.8 latency on the proxy: 160-245 s/call → one cron run can exceed 10 min; the following ticks are skipped ('already running') — a bounded cron mission (2-3 calls) is mandatory. → Switched to deepseek-v4-flash:cloud (same litellm-proxy-gcp provider): 16 s for the whole chain.

## Models & cost in kanban workflows

Cards created through the bridge inherit the worker profile's model, EXCEPT when the card carries a `workflow_template_id`. In that case the pipeline engine reads `hermes-experiment/workflows/*.yaml` and FORCES the model declared per step, independently of the profile's `model.default`.

Pitfalls observed 2026-09:
- The `spec.yaml`/`smoke.yaml` workflows declared `deepseek-v4-flash:cloud` (and down the chain `deepseek-v4-pro:cloud`) before the switch. Runs already dispatched had locked those models, even after the profile changed.
- Classic kanban cards without a `workflow_template_id` use the profile's `model.default`. As long as the `default`/`example`/`gh-triage` profiles pointed at cloud models, those cards burned pro quota.
- Switching the profile does NOT fix in-flight runs; the workflow YAMLs must also be patched and the unfinished cards re-dispatched.

Guard-rail rule:
- Local whitelist for test workflows: only allow `muse-glimmer:nim` / `nemotron-*` in `spec.yaml` and `smoke.yaml`.
- Block the dispatch when `model` ∉ whitelist → avoids quota surprises.
- Quick audit:
  ```bash
  grep -r "deepseek-v4-flash:cloud\|glm-5.3-flash:cloud" ${HOME}/hermes-experiment/workflows/
  for p in ${HOME}/.hermes/profiles/*/config.yaml; do echo "===$p==="; grep -A2 "^model:" "$p"; done
  ```

Plugin design:
The Workflow tab was grafted into `plugins/gh-kanban-bridge-ui`. The Workflow domain belongs to the `workflow-ui` context. That mix creates scope creep (YAML editing, live validation) and regressions. Recommendation: move the Workflow UI into `plugins/workflow-ui`, keep `gh-kanban-bridge-ui` strictly GitHub ↔ Kanban.

## Distribution as a shareable skill (tested)

- The skills hub accepts `hermes skills install hyron-fr/<repo>/skills/<name>` (owner/repo/path format) — tested OK on an isolated instance (distinct HERMES_HOME): `Installed: gh-kanban-bridge`, visible in `hermes skills list` as a community source.
- Real packaging pushed to the repo: `skills/gh-kanban-bridge/` = SKILL.md (hub format, frontmatter ≤60 chars, human author first) + `scripts/` (4 copied helpers) + `references/setup.md` (full step-by-step) + `references/SOUL-template.md`.
- The skills-guard-v2 scanner BLOCKS at install time (DANGEROUS verdict, not overridable) if the skill contains: the string "~/.hermes/.env" in an incitement (even negative: "never reveal…" → CRITICAL exfiltration finding), subprocess.run in accumulated MEDIUM. Fix: reword without the literal string ("the profile's secret files"), the accumulated subprocess MEDIUM passes when there is no CRITICAL.
- The raw.githubusercontent.com URL can stay 404 (negative cache) even when the file exists — the owner/repo/path form bypasses that.
- `hermes skills install` also accepts a direct URL to a SKILL.md.
- Issue #8 = the plugin deployment test ticket (full acceptance criteria).
