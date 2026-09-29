---
name: kanban-gate
description: "Use when working a kanban card preceded by a deterministic gate. Read the [gate] verdict and act (pass=continue, fail=block/retry)."
version: 1.0.0
---

# kanban-gate

Worker skill for the kanban cards preceded by a deterministic gate
(`gate_hook.py` triggered by the `kanban_task_claimed` hook).

## Role

When you work a kanban card, the dispatcher has run a deterministic gate
**right before** spawning you. The verdict is written as a structured
comment `[gate] pass|fail: <message>` on the card.

**You MUST read that verdict before acting** and behave accordingly.

## Protocol

1. **Read the card**: `kanban_show` (or `hermes kanban show <id> --json`).
   Look for the most recent comment starting with `[gate] `.
2. **Interpret**:
   - `[gate] pass: ...` → the gate is green. **Continue** the work normally.
   - `[gate] fail: ...` → the gate is red. **Do not** perform the work.
     Block the card with the gate reason: `kanban_block <id> --reason "<gate message>"`.
3. **Never ignore** a `fail` verdict. A gate fail means that a deterministic
   precondition is not satisfied (missing template, red CI,
   invalid schema, etc.) — the work would be invalid.

## Example

```
Comment: [gate] fail: gate fail (exit 1): test -f ./templates/ticket.md
→ Action: kanban_block t_xxx --reason "gate fail: missing ticket.md template"
```

## Notes

- The gate is **deterministic** (a shell script), not an LLM opinion. Its verdict
  is binding.
- If no `[gate]` comment is present (a card with no gate), continue
  normally — the gate is optional.
- The verdict is written by the dispatcher (author = dispatcher profile), not
  by a worker.
