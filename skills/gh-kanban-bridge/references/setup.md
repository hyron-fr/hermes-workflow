# Setup: GitHub ↔ kanban bridge + gh-triage Discord bot

Deployment on a new Hermes instance. **A single command** wires
everything: helpers, profile, board, labels, crons. Idempotent — re-running
duplicates nothing.

## Prerequisites

- Hermes Agent installed (`hermes` on the PATH)
- `gh` CLI authenticated on the target repo (`gh auth login`)
- A Discord bot created and invited to the target server (token to put in
  the profile's `.env`, see §Secrets)

## Installation

```bash
bash <skill_dir>/scripts/setup.sh
```

What `setup.sh` does (in order):

1. Checks `gh auth status` (exit 1 when not authenticated)
2. Copies the 4 helpers `scripts/*.py` to `${HERMES_WORKFLOW}/pipeline/`
3. Creates the `gh-triage` profile (if absent) + copies `gh_triage_poll.py` into
   its `scripts/` folder
4. Creates the kanban board (if absent)
5. Creates the GitHub labels `kanban` and `triage` (if absent)
6. Creates the cron `gh-kanban-bridge` (no-agent, `*/5`) if absent
7. Creates the cron `gh-triage-poll` (profile gh-triage, agent) if absent

Every step is guarded by an existence test: re-running `setup.sh` creates
no duplicate (same crons, labels, board).

## Configuration (env, overridable)

| Variable | Default | Role |
|---|---|---|
| `GH_REPO` | hyron-fr/hermes-experiment | target repo |
| `KANBAN_BOARD` | hermes-experiment | kanban board |
| `KANBAN_ASSIGNEE` | default | worker profile |
| `DISCORD_GUILD_ID` | ${DISCORD_ID} | Discord server |
| `DISCORD_CHANNEL_ID` | ${DISCORD_ID} | triage channel |

Example:

```bash
GH_REPO=acme/prod KANBAN_BOARD=prod KANBAN_ASSIGNEE=worker \
  bash <skill_dir>/scripts/setup.sh
```

## Remaining manual steps (outside setup.sh)

`setup.sh` does NOT handle the secrets or the Discord gateway — do them by hand:

### Profile secrets (`~/.hermes/profiles/gh-triage/.env`)

```
DISCORD_BOT_TOKEN=<bot token>
DISCORD_FREE_RESPONSE_CHANNELS=<channel_id>     # no @mention required
DISCORD_ALLOWED_USERS=<discord_user_id>          # MANDATORY (otherwise silence)
```

Get the user's Discord ID: right-click the nickname →
"Copy User ID" (developer mode enabled).

```bash
chmod 600 ~/.hermes/profiles/gh-triage/.env
```

### Profile gateway (Discord bot)

```bash
hermes -p gh-triage config set discord.allowed_guilds "[<guild_id>]"
hermes -p gh-triage config set discord.allowed_channels <channel_id>
hermes -p gh-triage gateway install      # systemd user service
journalctl --user -u hermes-gateway-gh-triage | grep "discord connected"
```

### Main gateway (kanban dispatcher)

```bash
hermes gateway install                   # if not already done
hermes kanban --board <board-slug> list  # check visibility
```

### Bot protocol (SOUL.md)

Copy `references/SOUL-template.md` to
`~/.hermes/profiles/gh-triage/SOUL.md` and adapt the IDs.

## Bridge variables (runtime)

| Variable | Default | Role |
|---|---|---|
| `GH_REPO` | hyron-fr/hermes-experiment | target repo |
| `KANBAN_BOARD` | hermes-experiment | kanban board |
| `KANBAN_ASSIGNEE` | default | worker profile |
| `BOT_GRACE_SECONDS` | 600 | an issue younger than N s is reserved for the bot |
| `DRY_RUN` | 0 | simulation with no write |
| `BRIDGE_VERBOSE` | 0 | log even the ticks with no action |

## Dashboard UI (gh-kanban-bridge tab)

The bridge is also drivable from the Hermes web dashboard through a UI plugin
(a component separate from the skill, distributed by git clone). The tab exposes
three sections: CONFIG (the bridge's 6 variables, persisted into the profile's
`.env` — the Discord token is never read nor returned), STATE (live via
`stats --json`), ACTIONS (pull/push/sync/new with the real output).

### Installation

```bash
# 1. Clone the plugin into ~/.hermes/plugins/
git clone https://github.com/hyron-fr/hermes-experiment.git /tmp/he
cp -r /tmp/he/plugins/gh-kanban-bridge-ui ~/.hermes/plugins/

# 2. Enable the plugin (plugins.enabled gate)
hermes plugins enable gh-kanban-bridge --no-allow-tool-override

# 3. Restart the dashboard (or rescan)
hermes dashboard --stop
hermes dashboard --host 0.0.0.0 --no-open
#   or, without restarting:
curl http://127.0.0.1:9119/api/dashboard/plugins/rescan
```

`setup.sh` does steps 1–2 automatically (copy the plugin from the
repo + enable) and reminds you of the dashboard restart.

### Verification (curl check)

The dashboard sits behind auth (basic/OAuth): obtain a session cookie
and then test the routes.

```bash
# 1. Login (basic provider) → session cookie
curl -c /tmp/hc.txt -X POST http://127.0.0.1:9119/auth/password-login \
  -H "Content-Type: application/json" \
  -d '{"provider":"basic","username":"<user>","password":"<pass>","next":""}'

# 2. Config (6 fields, never the token)
curl -b /tmp/hc.txt http://127.0.0.1:9119/api/plugins/gh-kanban-bridge/config

# 3. State (cards per status + pending push/pull)
curl -b /tmp/hc.txt http://127.0.0.1:9119/api/plugins/gh-kanban-bridge/state

# 4. Sync (triggers the bridge, real output)
curl -b /tmp/hc.txt -X POST http://127.0.0.1:9119/api/plugins/gh-kanban-bridge/sync
```

The tab appears in the sidebar after `after:kanban` (path
`/gh-kanban-bridge`).

## Validation checklist

1. `bash setup.sh` → exit 0, logs the completion line `setup.sh:177` prints
2. `hermes cron list` shows `gh-kanban-bridge` AND `hermes -p gh-triage cron
   list` shows `gh-triage-poll`
3. `gh label list --repo <owner>/<repo>` shows `kanban` AND `triage`
4. `hermes kanban boards list` shows the board (default `hermes-experiment`)
5. Re-run `setup.sh` → exit 0, NO duplicate (same crons, labels, board)
6. `python3 gh_kanban_bridge.py sync` → silent tick (exit 0, empty stdout)
7. Test issue → the poll announces it → thread opened + `triage` label
8. Answers in the thread → structured synthesis posted by the bot
9. "go" → card `ready` (idempotency-key `gh-issue-<n>`) + `kanban` label
10. Dispatcher → worker → `done` → sync closes the issue with the summary
11. Diagram in the thread: ```mermaid block + PNG via mermaid_render.py
