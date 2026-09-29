---
type: reference
status: draft
tags: [architecture, bench, seal, provenance, rule, integrity]
issues: [2]
---

# The declared-delta rule — what the seal guard actually protects

Arbitration `t_afa81532`, option (b). This note records the RULE, not the file that
carries it: it must stay true after any future amendment of the plate bench, so every
point below is a **verifiable constraint** ("reddens when…"), never a description of a
file's current shape.

## The rule

The plate-bench integrity guard is **"byte-identical to the seal, OR every divergence
entirely carried by a dated, attributed, caused and declared `provenance.amendments[]`
entry"**. The seal `e4da869d8e` stays frozen; the ledger is a LIVING register that a
human go can amend, and the guard exists to distinguish an *authorized* divergence from
a *silent* one.

The guard is **not** "the register is immutable". That phrasing was refuted on
2026-09-26 by a newer human go (3b), which authorized the slice-9 amendment of the
ledger. What is frozen is the SEAL, not the numbers.

## The 5 testable points

### 1. What the guard protects

The guard protects **the bytes of the plate and of its measurement script at the seal
`e4da869d8e`** — the plate `docs/architecture/context/issue-2-plate.html` (git blob
`430d0375…`, content sha256 `958f7c61…`) and the script
`docs/architecture/context/issue-2-plate.measure.py` (git blob `96560ad4…`, content
sha256 `1a08dd06…`).

**Reddens when** the plate or the script, read from the tree, no longer matches those
sealed blobs and no `provenance.amendments[]` entry carries the divergence.

### 2. What a receiving amendment must declare

Six **required** fields (a covering entry must carry all six; free fields such as
`changed` / `not_changed` / `dated_tension` may accompany them):

| field | meaning |
|---|---|
| `date` | `YYYY-MM-DD` |
| `by` | the card and the human decision that authorized it |
| `cause` | a measurable fact (e.g. a merged PR, a measured line growth) |
| `slices` | a **non-empty** list of the slices whose numbers changed |
| `frame` | the numbers covered (slice line, register fields, totals) and what is not |
| `not_changed_seal` | the seal and its blobs, stated unchanged |

**Reddens when** an entry is missing any of the six fields, when `slices` is empty,
when it is mis-dated, or when it declares a divergence that no slice actually carries
(a declaration with no object is a blank cheque — it reddens too).

### 3. What is never amendable

`issue-2-plate.measure.py` and any mutation of a seal blob. The reproducibility proof —
that the plate's totals can be re-measured from the tree — rests on those bytes. The
script measures; it is not measured.

**Reddens when** the measurement script changes, or any seal blob is mutated, even with
a covering amendment entry.

### 4. What the prose may do

Outside the `plate-ledger` machine block, prose can diverge **only on a declared slice
line** (the `class='k'>N` row of §4 of the plate). No other prose may move.

**Reddens when** prose outside the ledger block diverges on a line that is not a
declared slice line, even if the numbers themselves are unchanged.

### 5. What reconductibility engages

A guard that requires "byte-identical to the seal" across several benches (the slice
benches `tests/test_slice6..11*` carry the same guard) is judged with THIS rule, bench
by bench, measurement attached — not re-decided slice by slice.

**Reddens when** a bench asserts byte-identity to the seal while the branch is ahead of
the seal, and the divergence is not entirely carried by a dated/attributed/caused/
declared entry.

## What a reader takes away

The seal is frozen at `e4da869d8e`; the ledger is a living register a human go may
amend. A red bench is not a defect when the divergence is an amendment that the six
fields fully account for — it is a defect when the divergence is silent, mis-dated,
field-less, object-less, or touches the sealed bytes.
