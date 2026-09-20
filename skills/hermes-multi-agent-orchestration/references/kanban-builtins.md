# Kanban builtins — transition table & room mechanics

## Statuses (kanban_db.py:89, fixed)

`triage, todo, scheduled, ready, running, blocked, review, done, archived`

Useful card columns: `workflow_template_id`, `current_step_key`,
`completion_contract`, `tenant` (loose namespace), `idempotency_key` (automation
dedup, not exposed by list/show --json).

## Transitions and triggers

| Transition | Trigger | Mechanism |
|---|---|---|
| create → triage | human/bot | `kanban create` (`--triage`) |
| triage → todo | grooming | `hermes kanban specify <id>` (an aux-LLM tightens title+body) or manual edit |
| todo → ready | dispatcher, AUTO once every parent is done | `kanban_link` |
| ready → running | dispatcher, atomic claim + worker spawn | dispatch tick (admission gate here) |
| running → blocked | worker/human, + AUTO after `failure_limit` consecutive failures | `kanban_block` (circuit breaker) |
| blocked → running | human/bot | `kanban_unblock` |
| running → review | worker | `kanban_request_review` |
| review → running | reviewer | `kanban_request_changes` (you take your code back) |
| running → done | worker | `kanban_complete` (+ PR contract when declared) |
| done → archived | human/gc | `hermes kanban archive` / `gc` |
| (parking) scheduled | known timing/follow-up | `hermes kanban schedule` |

Alternative initial statuses at creation: `--initial-status blocked|running`.
Reassignment: `hermes kanban reassign` / `reclaim` (a card can change
worker between steps — the alternative to one card per step).

## Result gate vs claim gate

- Claim gate (hook `kanban_task_claimed`): admission filter, verdict in a
  `[gate] pass|fail` comment. An observer — exit code ignored.
- Result gate: either a reviewer profile (`kanban_request_review` →
  `request_changes`), or a completion contract (`--completion-contract
  OWNER/REPO` or `local-only`): `done` is refused without the required checks green,
  with durable `pr_acceptance` and `last_failure_error` events for the
  retry.

## Rooms (group chats) — mechanics

- 2-6 bots; your message → ≤3 serial rounds × ≤10 messages/round; a member
  answers only if it has something to add, otherwise it passes; the room
  settles when a full round is silent.
- `@mention` scopes the round to the mentioned bots; `@user` escalates to the human (needs-you
  badge; pending prompts light it up again too).
- Every member = a persistent session `Group: <name>` (a context that survives).
- Durable: if all members share a gateway, the gateway's driver
  carries the room — closing the desktop does not interrupt it (log catch-up).
- Multi-machine possible (Desktop relay / `hermes peer`) but the durable
  driver is only guaranteed on a shared gateway.
- `message_agent`: bot↔bot fire-and-forget DM, ONLY from the canonical
  Bot Chat (never in a room, never in the CLI).
- Plugin hooks: `on_room_member_activity` projects turn.started/turn.settled.
