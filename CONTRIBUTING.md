# Contributing

Thanks for your interest. This repository is an **agent pipeline**: the contribution
rules mostly concern what must stay **deterministic** and **verifiable**.

---

## Before proposing a change

### 1. Open an issue

Every non-trivial change starts with an issue. Describe:

- the **observed symptom** (not just the desired solution);
- the **exact command** that reproduces it and its real output;
- the expected behaviour.

> A PR that fixes a bug must be able to cite **the exact line** where the bug
> shows up. A PR whose premise does not hold against the code will be refused,
> however well written.

### 2. Check for overlap

Before opening a new issue, look for one that already covers the topic
(open, or with an open PR). This repository applies that rule to itself: its
GitHub bridge blocks the import of an issue that overlaps in-flight work.

---

## Design rules (non-negotiable)

### What is mechanical is scripted, without an LLM

Everything that can be deterministic stays so: issue import, graph building,
linters, quality gates. **An idle pipeline must cost zero tokens.** The LLM steps
in only where judgement is required (writing a spec, arbitrating an ambiguity).

A PR that adds an LLM call on a mechanical path will be refused.

### A quality gate is exercised in BOTH directions

A check that only tests a healthy case proves nothing (scope ignored, report
missing, exclusion too broad). Every gate must ship with:

1. a **healthy** case → exit 0, silent;
2. a **faulty** case → exit 1, with an actionable message.

Both must be in the test suite.

### A pattern filter filters GENERALLY, never by a closed list

A linter that excludes `^t[1-6]\b` turns every step added later (`t3b`, `t4a`)
into a false positive **precisely when a step is added**. Write the general
pattern (`^t\d+[a-z]?\b`).

### A deterministic gate is only worth its SCOPE

A check that scans the whole repository reports **pre-existing** content: it
becomes unusable and gets disabled instead of fixed. Restrict it to the area the
convention applies to (the vault directories, not all of `docs/`; the files in the
diff, not the whole repo).

### No hardcoded path, no hardcoded variable

- Never `/home/<user>/...`: resolve from `Path(__file__)` or a documented
  variable.
- Never an environment identifier (Discord channel, guild) in the code: use an
  environment variable, with an empty default.
- Never an executable assumed by absolute path: `shutil.which()` then a list of
  **verified** candidates (`isfile` + `X_OK`).

> A cron has no interactive PATH. A hardcoded path that works in your shell
> fails in production, silently.

### The direction of kanban links is `link <parent> <child>` — the child WAITS for the parent

A synthesis card is built **backwards** (each production is a parent of the
synthesis). Never `--parent <synthesis>` on one of its inputs: deadlock.

### Pipeline cards are created mechanically

Never create by hand the cards a script knows how to build (the `t1..t5` graph,
slices, worktrees). A hand-written graph drifts from the spec; a graph built from
`slices.json` is verifiable.

---

## Tests

```bash
python3 -m pytest tests/ -q      # must print 113 passed
```

- The tests load their modules **from this repository** (relative paths via
  `REPO`), never from an external location. A test that reads `/home/<user>/...`
  passes on its author's machine and fails everywhere else.
- No "change-detector" test (one that pins a value meant to change: a count, a
  catalogue, a version number).
- A test that reads a file's **source text** is refused: it tests the form, not
  the behaviour. Extract the logic into a pure function and call it.
- Every bug fix comes with an **invariant** test that fails on the previous
  code.

### Checking that a test really fails for the right reason

A green test does not prove that it tests what it claims. A useful counter-check:
hide or move the resource under test and verify that the suite fails — otherwise
the test was reading something else.

---

## Sanitisation (public repository)

**No secret, no infrastructure data, no environment identifier.**
Before pushing:

```bash
# keys, tokens, private IPs, personal paths, Discord identifiers
grep -rnE "sk-[A-Za-z0-9_-]{10,}|/home/[a-z]+|[0-9]{17,19}" --include="*.py" --include="*.md" .
```

Secrets live in `~/.hermes/profiles/<profile>/.env`, **outside this repository**.
`config.yaml.example` is sanitised: it holds only `${VAR}` placeholders.

---

## Commits and PRs

- One commit per intent, message in the imperative, explaining the **why**.
- The PR references the issue (`Closes #N`) — without that line, GitHub does not
  link the PR to the issue and closure depends on a single mechanism.
- **The agent never merges.** Merging is a human decision.
- A PR that touches a quality gate must show **both** cases (healthy/faulty)
  in its description.

---

## Reporting a design flaw

The rules above come from defects observed in production. If you discover a new
one, document it: **the symptom, the root cause verified in the code, and the rule
that would have prevented it.** That is how this file was written.
