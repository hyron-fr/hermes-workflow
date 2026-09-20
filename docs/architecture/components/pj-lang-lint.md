---
type: component
status: draft
tags: [architecture, i18n, pipeline, gate]
issues: [2]
---

# Component — pj_lang_lint (language gate)

## Purpose

`pipeline/pj_lang_lint.py` is the deterministic gate that keeps the migrated
corpus English. It reports every line of a versioned `.md` that still carries a
diacritic **outside a frozen span**. It is the mechanical acceptance measure for
issue #2 "Rewrite in english": `rc 0` (silent) means the corpus is compliant,
`rc 1` lists the residual French.

## Contract

Frozen by `tests/test_lang_lint.py`:

- **no argument** — enumerates the TRACKED `.md` of the work tree via
  `git ls-files '*.md'`, never a directory walk. Each worktree carries its own
  copy of the corpus, so `os.walk` would report sibling worktrees as if they
  were the tree.
- **explicit `<path>`** — restricts the scan to that path; a path that was asked
  for and cannot be found is a usage error (`rc 2`), never a violation.
- **return codes** — `rc 0` compliant (stdout and stderr both silent); `rc 1`
  at least one violation, each line naming path + line + faulty text; `rc 2`
  usage error (missing path, missing/unreadable exclusions file, unknown flag).

## Granularity: the span, not the line

The detector removes the spans matching the frozen literals before judging the
line: English prose that quotes a protocol stays clean, while a diacritic
elsewhere on the same line is still reported. A line of prose that trips a
detector through a false positive is a **failed translation**, not an exclusion.

## Exclusions: the frozen literals

`pipeline/pj_lang_lint.exclusions.yaml` declares exactly two machine protocols,
verbatim and untranslated:

- `Importé depuis` — bridge marker read by `pj_pipeline_deployer.py` and
  `gh_kanban_bridge.py`; translating it silences the bridge, with no error.
- `ROOM:` — machine-only room marker read by `pj_room_keeper.py`, anchored
  anywhere in the body, with no human reader.

The file is YAML (outside the `.md` corpus the scan enumerates), versioned, and
each entry cites the line that reads it, so the declaration can be re-read by
the script it names. It must carry no accented prose of its own — an accented
word in a comment would silently widen the exemptions.

## Boundaries (hexagonal)

The gate is a pure function over the index and the file text — no DOM, Canvas,
network or clock. Its only external touch is `git` (subprocess) to resolve the
tree root and enumerate tracked files, plus the filesystem read of the corpus.
Its observable output (the `[pj-lang-lint] ...` lines) is the contract the bench
locks.

## Delivered by

Slice 2 (issue #2): `pipeline/pj_lang_lint.py`,
`pipeline/pj_lang_lint.exclusions.yaml`, `tests/test_lang_lint.py`.
