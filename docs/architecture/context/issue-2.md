---
type: context
status: draft
tags: [architecture, i18n, translation, documentation, cadrage]
issues: [2]
---

# Architectural cadrage — issue #2 « Rewrite in english »

## Positioning (exact frame)

Issue #2 is a **documentation-wide transformation**, not a feature. Its body is one
sentence — « Rewrite all documents in english » — and it introduces **no functional
change**: no behaviour, no component, no port is added or removed. Its deliverable
is a **linguistic state of the repository**: every human- and agent-facing document
and string rendered in English, where today the repository is authored in French.

It therefore positions itself **across every textual surface** of the project,
rather than inside one component. It is the first issue whose diff is **entirely
prose and string literals**, and whose acceptance is measurable mechanically
(a scan for residual French), not by runtime behaviour.

Scope measured on `origin/dev` @ `3c6d59b`: **124 tracked files**, of which **93
carry French diacritics** (`é è ê à ç ù î ô û ë ï`) — a lower bound on the real
surface, since much French prose has no accent (e.g. « dans », « pour », « rien »).
The true inventory of French content is larger than the accent count suggests.

## Cross-section infrastructure / functional / code

### Infrastructure (external boundaries crossed)

**None.** This issue does not touch GitHub, the kanban board, Discord, Hindsight,
or git worktrees beyond the ordinary branch/PR mechanics. It is a pure in-repo
rewrite: the only external adapter involved is the **PR** at `t6` (never merged by
an agent) and the eventual `doc-memory` push to Hindsight, both downstream of this
cadrage.

### Functional (capabilities touched)

The issue is a **cross-cutting refactor of prose**, analogous to a rename that
touches every layer but changes no behaviour. The capabilities it traverses are
the **documentation surfaces** of the framework, not its runtime capabilities:

1. **Project narration** — `README.md`, `pipeline/README.md`, `.env.example`,
   `LICENSE`-adjacent prose, `workflows/templates/ticket.md`.
2. **Agent identity/behaviour** — `agents/*/SOUL.md` (the four profiles' operating
   contracts) and `skills/**/SKILL.md` (procedural memory).
3. **Deterministic tool I/O** — `pipeline/*.py` and `bridge/*.py` docstrings, help
   text, and **user-facing output strings** (error messages, verdicts).
4. **Workflow schemas/config** — `workflows/*.yaml` + `workflows/schemas/*.json`
   (labels, descriptions, prompts embedded in the pipeline definitions).
5. **Tests** — `tests/*.py` assert on **French strings as contracts** (see TDD).

### Code (components, ports, adapters)

The decisive structural fact of this issue is **duplication**: the deterministic
tools exist in **several copies**, and translating « all documents » forces a
choice about which copy is canonical. Measured on `origin/dev`:

- `pj_card_lint.py` — 3 copies: `pipeline/`, `agents/pj-master/scripts/`,
  `skills/pj-pipeline/scripts/`
- `pj_slices_lint.py` — 3 copies: `pipeline/`, `bridge/`, `agents/pj-master/scripts/`
- `pj_docs_lint.py` — 2 copies: `pipeline/`, `bridge/`
- `pj_docs_memory.py` — 2 copies: `pipeline/`, `bridge/`
- `pj_graphwatch.py` — 3 copies: `pipeline/`, `bridge/`, `agents/pj-master/scripts/`
- `pj_coverage_gate.py`, `pj_room.py`, `pj_room_keeper.py`, `pj_spawn_guard.py` —
  mirrored in `pipeline/` + `bridge/` (+ `agents/pj-master/scripts/` for the rooms)

The tests import from **`bridge/`** (e.g. `test_pj_slices_lint.py` loads
`bridge/pj_slices_lint.py`). Translating only one copy leaves divergent English and
French siblings — the exact class of "documented state that contradicts the code"
this role exists to prevent.

## SDD reading (spec-driven)

The spec is the source of truth; the documentation describes the **delivered**,
never an intention. Here the "spec" is the issue body (one sentence) plus the
repository as it stands at `dev`. The delivered state is **English-only prose**,
verifiable by a mechanical residual-French scan. This cadrage describes only what
exists today; it does not invent components or a translation policy — the policy
(which copy is canonical, whether tests are rewritten or kept French) is a **spec
decision for `t4`/`t5`**, not for this note.

## DDD reading (bounded contexts, aggregates, events)

- **Bounded contexts** (unchanged by this issue — translation is orthogonal to the
  four runtime contexts *admission / spec graph / development / delivery*).
- **Aggregate root**: unchanged — the root kanban card of the issue.
- **Value objects touched as *strings*, not as invariants**: the card format
  (5 sections + Gherkin + DoR/DoD + INVEST) and `slices.json` are *described* in
  French today; translating their descriptions does not change their shape. The
  **section headers** themselves (« Contexte & Objectif », « Critères
  d'acceptation »…) are a value-object contract — see TDD.
- **Domain events**: none new. The issue adds no status transitions.

The one genuinely DDD-shaped question is whether the **canonical string language
of the deterministic tools' output** is a domain invariant: today `pj_card_lint`,
`pj_slices_lint`, `pj_docs_lint` emit French error messages, and the tests assert
those exact strings. Changing the message language changes the **observable
contract** of the core — that is the TDD frontier below.

## TDD reading (contracts that become testable)

This is the crux of the cadrage. The test suite **pins French strings as
contracts**, so a naive translation breaks CI unless tests are rewritten in
lockstep. Concrete cases measured in `tests/`:

- `test_pj_slices_lint.py` asserts error substrings `"aucune slice"`,
  `"contigus"`, `"dépendance"`, `"branch"`, `"issue"`, and the scenario-tags
  `limite`/`erreur` (via `LIMITE_RE`/`ERREUR_RE`).
- `test_card_lint_is_spec.py` mirrors `pj_card_lint.is_spec` filtering and asserts
  French section semantics (title patterns `t1 worktree` etc.).
- `test_pj_room*.py`, `test_pj_coverage_gate.py`, `test_pj_docs_lint.py`,
  `test_pj_docs_memory.py`, `test_pj_graphwatch.py` similarly exercise French
  messages/verbs.

Two facts soften this: the **linters are already bilingual** — `pj_card_lint.py`
accepts `context|contexte`, `feature|fonctionnalité`, `scenario|scénario`,
`given|étant donné`, `definition of ready|définition of ready` — so the *input*
language is not the risk; the **output strings** and the **test assertions** are.
The TDD contract for this issue is therefore: *translate a tool's output strings
and its asserting tests in the same slice*, never one without the other.

## Hexagonal reading (the core stays pure)

The **pure core** is the deterministic validators/linters/planners
(`pj_card_lint.lint`, `pj_slices_lint.validate`, `pj_docs_lint.scan`,
`pj_coverage_gate`, `pj_graphwatch.check_topology`, `pj_room.detect_livelock`) —
functions over data structures with **no** DOM, Canvas, network, filesystem or
clock. Translation is **safe for the core's purity** (it only rewrites string
literals and docstrings), but it **touches the core's observable output**, which is
exactly what the tests lock. The hexagonal discipline here is: keep the rewrite
*inside* the pure functions' string literals and docstrings — do not use the
opportunity to smuggle I/O or behaviour into a doc change.

## Components impacted by issue #2

No functional component's behaviour changes. **Text surfaces** to be rewritten
(and the choice points they raise):

| surface | content | choice point |
|---|---|---|
| `README.md`, `pipeline/README.md` | project narration | prose only, no contract |
| `.env.example`, `workflows/templates/ticket.md` | templates | template section headers are a contract (`pj_card_lint` reads them) |
| `agents/*/SOUL.md`, `skills/**/SKILL.md` | agent behaviour contracts | prose; keep directives semantically identical |
| `pipeline/*.py`, `bridge/*.py` | docstrings + **output strings** | output strings = test contract (TDD frontier) |
| `workflows/*.yaml`, `schemas/*.json` | pipeline defs + prompts | prompt language is functional (drives LLM output) |
| `tests/*.py` | assertions on French strings | rewrite **in lockstep** with the tool output |
| duplicated tool copies (`agents/`/`bridge/`/`pipeline/`/`skills/`) | canonical copy? | spec decision: consolidate vs translate all |

## Boundaries crossed (summary)

```
repository @ dev (124 files, French)
  ├─ prose (README, SOUL, skills)            → English, no contract risk
  ├─ templates + section headers            → English, but headers are a lint contract
  ├─ tool docstrings + output strings        → English, output = test contract (TDD)
  ├─ workflow YAML prompts                   → English, functional (drives LLM)
  └─ test assertions                          → English, in lockstep with the tools
  → PR (t6)  →  (never agent-merged)  →  doc-memory → Hindsight
```

The one boundary that must be settled **before** development mass-starts is the
**canonical-copy question** for the duplicated deterministic tools: translating
three divergent copies is wasted work and re-introduces the exact "documented
state ≠ code" inconsistency this role guards against. That decision belongs to
the spec (`t4`) and the human gate (`t5`); this cadrage flags it, it does not
arbitrate it.
