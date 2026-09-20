# Enabling kanban — the two layers, and where to verify it

Two independent things both answer "how do I enable kanban in
Hermes Desktop". Answer both, in this order, and never assert without having read
the cited file (a comment on it is not a reading of it):

| Layer | Where it is defined | Activation |
|---|---|---|
| Visual board in the Desktop app | `apps/desktop/src/plugins/kanban/plugin.tsx` (`defaultEnabled: false`) | Capabilities → Plugins → "Kanban" → the **Desktop** column |
| Tools `kanban_*` in an agent session | `tools/kanban_tools.py`: `_profile_has_kanban_toolset()` reads `load_config().get("toolsets", [])` | `hermes config set toolsets '["kanban"]'` |
| Actual triggering of the cards | `~/.hermes/kanban/.dispatcher.lock` (a single holder per machine) | nothing to enable: check WHO is dispatching |

## The Desktop layer (renderer, no CLI)

The desktop plugin `kanban` is bundled but **inventoried only** as long as
the user does not enable it: it registers the page, the nav, the statusbar counter
and the notifications only after the toggle.

- Decision store: `apps/desktop/src/contrib/plugins-store.ts` — localStorage key
  `hermes.desktop.pluginDecisions.v2`, `pluginActive(id, defaultEnabled)`: the **absence**
  of a decision falls back on the plugin's `defaultEnabled` (hence the opt-in by default).
- Toggle: `apps/desktop/src/app/skills/plugins-tab.tsx` → `setPluginEnabled(id, on)`.
  The tab lives in `app/skills/index.tsx` (`SKILLS_MODES = ['skills','toolsets','mcp','plugins']`).
- Row deep-link: `/skills?tab=plugins&plugin=kanban` (`pluginElementId`).
- Older `?tab=plugins` links are redirected (`app/settings/moved-tabs.ts`).

What the plugin brings once switched on: page `/kanban` + a sidebar navigation
entry, a clickable `running/ready` counter in the statusbar, the `mod+alt+n` shortcut
(new card in triage), in-app toasts + OS notifications on `completed`,
`blocked`, `gave_up`, `crashed`, `timed_out`, `block_loop_detected`.
The OS notifications are **gated** by Settings ▸ Notifications ▸ **Plugin
notifications** — and they only cover the window while the app runs (no replay
of the events that arrived with the app closed; for durable delivery, subscribe a gateway with
`hermes kanban notify-subscribe`).

**Do not tell the user to type `/kanban` in the Desktop**: the slash is
deliberately out of the palette there (`apps/desktop/src/lib/desktop-slash-commands.ts`,
`NO_DESKTOP_SURFACE.advanced`) and answers "use the relevant desktop control". The
path is the board (the page, the ⌘K palette "Kanban: Open board", or the toggle).

## The tools layer (config, verified)

- The check_fn reads ONLY the **root** key `toolsets`: `platform_toolsets.cli` may
  contain `kanban` (a read-time fallback of `_get_platform_tools`) without the
  check_fn passing — so adding `kanban` to the CLI list releases nothing.
- `hermes config set toolsets '["kanban"]'` writes a REAL YAML list (checkable in
  a temporary `HERMES_HOME` before touching the live config). The dotted form
  `toolsets.0` writes a faulty dict.
- The `hermes-cli` bundle **lists** the `kanban_*` in `TOOLSETS` — their invisibility
  comes from the check_fn, not from the list: do not conclude "the toolset is switched on"
  by reading the list.
- Cost: ≈14 `kanban_*` schemas more in every session prompt.

## Diagnosis: who is dispatching?

The board does not open by itself and a single gateway per machine holds the lock.

```bash
fuser -v ~/.hermes/kanban/.dispatcher.lock      # holding PID
cat /proc/<pid>/cmdline | tr '\0' ' '           # which profile (--profile X gateway run)
hermes kanban diagnostics                       # cards in protocol_violation / blocked
tail -3 ~/.hermes/logs/gateway.log              # "another gateway already holds the dispatcher lock … will NOT dispatch"
```

A gateway logging "will NOT dispatch" is normal (singleton lock): the tick
comes from another profile. It is a fault only if NO gateway logs
"embedded in gateway (interval=…)". `kanban.dispatch_in_gateway: false` explicitly
disables the tick for a profile — check it before looking elsewhere.
