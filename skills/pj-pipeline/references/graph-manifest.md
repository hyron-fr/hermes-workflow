# Issue graph manifest (`slices.json`)

Spec artefact, NOT a deliverable: it lives under the board directory
(`~/.hermes/kanban/boards/<board>/specs/<n>/slices.json`), never in the repo.
Zero noise in the PRs, readable by every profile of the pipeline.

It is written by the validation worker (human gate passed) then consumed by a
deterministic 0-LLM cron that builds cards + links. The worker creates no card
itself: that separation is what removed the graph drifts (phantom cards,
inverted links, assignees outside the pipeline).

## Schema

```json
{
  "issue": 42,
  "repo": "dino-game",
  "branch": "wt/issue-42-score-persistant",
  "slices": [
    {
      "k": 1,
      "slug": "score-persistant",
      "depends_on": [],
      "parallel": {
        "test": "test-1 : scenarios of the persistent score",
        "dev":  "dev-1 : implementation of the persistent score"
      },
      "convergence": "conv-1 : reconcile tests and implementation",
      "doc": "doc-1 : document the score module"
    }
  ]
}
```

| key | scope | role |
|---|---|---|
| `issue` / `repo` | root | issue identity; used by the idempotency-keys |
| `branch` | root | **one single one for the whole issue** — it is what makes the worktree shared |
| `k` | slice | contiguous number from 1 |
| `depends_on` | slice | numbers of upstream slices, all strictly < `k` |
| `parallel.test` / `.dev` | slice | two independent cards, launched in parallel |
| `convergence` | slice | card that judges/reconciles the batch (parent of both) |
| `doc` | slice | documentation card, after convergence |

The builder repeats `--branch <root branch>` on EVERY worktree card. Without
it, the resolver falls back silently on one worktree per card and the parallelism
is decorrelated (the two roles no longer share anything).

## What the validator must REFUSE

Every rule corresponds to a drift that really reached a board:

1. `issue` / `repo` absent, `slices[]` empty.
2. `k` not contiguous from 1 — a hole = a card never produced.
3. `depends_on` holding a value ≥ `k` — inverted dependency (mutual wait) or
   self-dependency.
4. `branch` absent, or divergent from one slice to the next.
5. `branch` in the WRONG FORMAT — a `branch` derived from a **card id**
   (`wt/t_109333ba`) instead of the issue name (`wt/issue-<n>-<slug>`) passes a validator
   that only checks presence and uniqueness, and propagates silently: the
   branch becomes a runtime artefact, unreadable and not reproducible from one card to
   the next. The validator must check the **pattern** (`^wt/issue-<n>-`), and the audit
   additionally compares the declared branch with the one of the upstream worktree card
   (`kanban show <t1> --json` → `branch_name`) — a mismatch means the worker
   copied the card id it had in front of it.
6. A `test` card without its **three kinds of scenario**: nominal + **edge** case +
   **error**. Two scenarios are enough for an ordinary card, not for a test card.
7. An empty `parallel` entry — a role announced but no card.

**The validator accepts everything it does not test.** A manifest of several tens of
Ko, compliant on the counts and the scenarios, can still carry an unusable branch:
the compliance of an artefact is judged on the rules that were WRITTEN, so any rule left
out of the validator (identifier format, consistency with the upstream card) is a silent
tolerance. When a gate goes green on an artefact that contradicts the documented
convention, it is the gate that must be extended, not the convention that must be excused.

An invalid manifest → `request-changes` on the validation card: that is a gate,
not a courtesy. The requirement of the three kinds is what makes the edge cases
OPPOSABLE (otherwise they stay a pious wish that the one-shot worker forgets).

## Construction

- **Mandatory dry run**: `PJ_DRY_RUN=1` prints the plan and creates NOTHING.
  Check the topology, then only launch the real run.
- **Idempotency-key on EVERY creation** (`pj-<key>-<repo>-<n>`) : the builder is
  a */5 cron — without a key, two close ticks duplicate the graph.
- **Silent tick when there is no work**: the script spots the submission cards without
  children and exits silently when there are none (0 LLM, 0 writes).
- **Anti-deadlock**: all links placed AFTER the cards are created, in the
  direction "production card → PARENT of the submission card". The aggregator is never
  parent of its own inputs.
- **Check the assignees AFTER a real deployment** (`kanban show <id> --json`), not
  by re-reading the script: a default assignee set on the builder applies to
  all the cards it creates, and the specialist's card goes to the orchestrator without
  error or warning.
