# Rooms Bot Mode (Group Chats) — mechanics, diagnostics, operations

Depth for work on the rooms. The rules that are always true stay in SKILL.md
("Room vs board"); this file carries the exact API, the bounds, and the diagnosis of failures.

## Where the engine lives

The desktop is only a CLIENT. The engine is in the gateway:

| File | Role |
|---|---|
| `gateway/hosted_rooms.py` | persistence: `create_room`, `disband_room`, `request_room_stop`, `append_event`, `read_events`, `list_rooms`, `room_state`, `default_db_path` |
| `gateway/hosted_room_discussion.py` | pure policy: `validate_roster`, `validate_room`, `plan_next_task`, `_pending_discussion` |
| `tui_gateway/hosted_room_service.py` | the service (`bindings()`, `start_hosted_room_service()`) |
| `tui_gateway/hosted_room_driver.py` | the loop and the lease (`HostedRoomRuntime`, `acquire_lease`, `defer_indeterminate_task`) |

No `hermes groups` CLI sub-command: everything goes through these Python modules.

## Real bounds (read in the code, ≠ user doc)

| Constant | Value | Meaning |
|---|---|---|
| `MAX_ACTIVE_ROOMS` | 256 | rooms active at the same time per host |
| `MIN/MAX_DISCUSSION_MEMBERS` | 2 / 6 | imposed by `validate_roster` — this is the business limit |
| `MAX_DISCUSSION_ROUNDS` | 3 | rounds per discussion |
| `MAX_DISCUSSION_MESSAGES` | 10 | messages per discussion |
| `max_concurrent_rooms` | 4 | deliberations really running at the same time |
| `lease_ttl_seconds` | 30 | lifetime of a room lease (renewed during a turn) |
| `indeterminate_defer_seconds` | 60 | delay before deferring an indeterminate task |
| `MAX_MEMBERS` | 128 | LOW-LEVEL bound of the schema, unreachable through the API |

## Persistence: one database SHARED by every profile

`default_db_path()` returns `~/.hermes/shared-state.db` **whatever the profile** (HERMES_HOME
changes nothing). This is deliberate: it keeps the profile gateways from opening `state.db` in
write mode (a multi-writer corruption vector). Direct consequence: every gateway of one
installation sees and serves the same rooms.

Tables useful for diagnosis: `hosted_rooms`, `hosted_room_events`, `hosted_room_retired_ids`,
`hosted_room_driver_tasks`, `hosted_room_driver_leases`.

## API — signatures and traps

```python
import sys; sys.path.insert(0, "<path>/hermes-agent")
from gateway import hosted_rooms as hr

hr.create_room(db, room_id=..., name=..., members=[{...}], authority_gateway_id=...)
hr.disband_room(db, room_id=..., expected_gateway_id=..., expected_epoch=...)   # epoch MANDATORY
hr.request_room_stop(db, room_id=..., cancel_id=..., expected_gateway_id=..., expected_epoch=...)
rooms = hr.list_rooms(db)
room  = hr.room_state(db, room_id=...)
events = hr.read_events(db, room_id=...)['events']    # dict, key 'events'
hr.append_event(db, room_id=..., event_id=..., kind=..., actor=..., payload=...,
                authority_gateway_id=..., authority_epoch=...)
```

- `create_room` is **idempotent** (same room_id = same room returned).
- **These do NOT exist**: `get_room`, `list_events`. Use `list_rooms` / `room_state` /
  `read_events`. Getting the name wrong costs an `AttributeError` in the middle of a diagnosis.
- Roster: exactly `{member_id, profile, handle}` — `display_name` and `target` optional.
  Any other field is refused (`_exact_fields`). The profiles must be **local to the gateway**
  (`local_profiles()` = the sub-directories of `~/.hermes/profiles/` + `default`).
- No `wakeup()` needed after an out-of-process `create_room`: `bindings()` re-reads the database
  on every cycle (5 s poll at rest, 0.25 s when active) and discovers the room on its own.

## Bots NEVER speak spontaneously

`plan_next_task` returns `status='idle'`, `reason='no_pending_user_event'` as long as no
`message.user` exists. A room created and never animated therefore stays silent indefinitely —
that is not a failure, that is the contract.

Trigger (payload **exact** `{text, thread_id}`):

```python
hr.append_event(db, room_id=rid, event_id=f"ev-{rid}-{tid}", kind="message.user",
    actor={"kind": "user", "id": "<orchestrator profile>"},
    payload={"text": "...", "thread_id": tid},
    authority_gateway_id=hr.local_authority_gateway_id(), authority_epoch=1)
```

Round 1 = the members **mentioned** (no mention = ALL); rounds 2-3 = opt-in (a cited peer
that has not spoken yet). Do not manufacture an `@` when the whole room is to be queried.

## End of a deliberation: the exact criterion

`_pending_discussion` considers a discussion closed when a `room.activity` event carries
`status` ∈ `{settled, bounded}` for its `discussion_event_id` (`bounded` = ceiling reached:
3 rounds or 10 messages). A `room.stop_requested` event **supersedes** any earlier user
message: only the `message.user` of `seq` > last stop stay "pending".

## Event kinds

`message.user`, `message.member`, `turn.settled`, `turn.failed`, `turn.cancelled`,
`turn.deferred`, `room.activity`, `room.stop_requested`.

## Livelock: `indeterminate` → `deferred` in a loop

**Mechanism.** A gateway that acquires a room lease marks `indeterminate` every `running` task
that does not carry its own fence (`foreign_running`, `hosted_room_driver.py`). The
reconciliation CANNOT take another process's turn over: it defers the task
with `reason='member_unavailable'` every ~60 s (`indeterminate_defer_seconds`).

**Consequence: this is NOT self-healing.** As long as several gateways hand the
lease back and forth, the cycle `indeterminate → deferred → retry → indeterminate` turns forever:
`plan_next_task` stays `task`/`member_turn`, the room stays `pending`, and the deliberation no
longer progresses. The lease guarantees mutual exclusion (never two concurrent executions,
no duplicate `event_id`) but **does not guarantee progress**.

**Diagnosis — measure the contention:**

```sql
-- How many times the lease was (re)taken: a counter that climbs = contention.
SELECT room_id, lease_generation FROM hosted_room_driver_leases ORDER BY lease_generation DESC;
-- How many different PROCESSES really ran turns on the room.
SELECT run_process_generation, count(*) FROM hosted_room_driver_tasks
  WHERE room_id='<rid>' AND run_process_generation IS NOT NULL GROUP BY 1;
-- Reason for a defer: member_unavailable = contention, not a room bug.
SELECT status, count(*) FROM hosted_room_driver_tasks WHERE room_id='<rid>' GROUP BY status;
```

A two-digit `lease_generation` on a young room, or several distinct
`run_process_generation` values for the same room, confirm the contention. Also check how many
gateways are running (`hermes gateway list`): each one starts its room worker.

**Escape hatch — the stop fence.** `request_room_stop` appends a `room.stop_requested`
that supersedes the earlier turns: the scheduler goes straight back to
`idle`/`no_pending_user_event` and the defer loop stops. That is the clean way out of a livelock
(preferable to a kill), and it preserves the transcript (`read_events` keeps everything) — to be
reported on the board before dissolution.

**Root fix: not applied.** The room worker is started unconditionally by
every gateway (`_start_post_connect_services` → `_hosted_room_worker_watcher`) and there is
neither a config key nor a hook to disable it: restricting it to the gateway that holds the dispatcher
requires patching the core. Failing that, the safe regime is **a single active deliberation** when
several gateways are running, with the stop fence as the guard-rail.
