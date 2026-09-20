---
type: context
status: draft
tags: [architecture, i18n, bench, datation, cadrage]
issues: [2]
---

# Dating rule for state benches — the anchoring key and INDÉTERMINÉ

Arbitration `t_ca894fd4`, decision 3. This note records the general rule that the
arbitration produced, and the five measured points of the current state. It is
self-contained: it does not refer to a discussion thread, and it defines every
non-obvious term it uses.

## The rule

**A bench that ratifies a DATED artifact must date its own judgment.** A frozen
number is correct; what is wrong by construction is confronting frozen constants
with a LIVING tree. Every state artifact — the "before" register, the "after"
measure, the plate, the ledger — requires an explicit anchoring key. Outside that
key the verdict is `INDÉTERMINÉ`, never a FAIL — and there is no "green" outside
the key either.

The rule corrects a category error: the plate register of issue #2 describes the
tree AT ONE revision. Judged against a living tree, it inevitably produces a
divergence the moment a translation slice rewrites a corpus file. That divergence
is a **conflict of deadline**, not a defect — nobody lied, the calendar did.

## The anchoring key

The register (`docs/architecture/context/issue-2-plate.html`, machine block
`plate-ledger`) describes the tree at the commit `6d787c5` (full SHA
`6d787c5960eab1f3ec7595513c106a5dd1af98a1`) — the commit that carried the ratified
plate. The slice-1 bench declares this same revision as its frozen key
`ANCRAGE_REVISION = "6d787c5"` (in `tests/test_issue2_plate_reproducible.py`).

The state the register describes is the **"before"** state: 20 files / 3052 lines /
1559 accented lines, the corpus as it stood before the translation slices were
carried.

## How the bench dates its judgment

Three positions, three verdicts:

- **tree at the key** → `DÉTERMINÉ`: register, prose and tree are actually
  confronted, file by file;
- **tree outside the key** → `INDÉTERMINÉ`: the bench names the key AND the
  measured revision, and abstains via a named `pytest.skip` — never a weakened
  assertion, never a false green;
- **key unresolvable** → `AncrageIrresolu`, naming the key: a bench that cannot
  date its judgment must SAY so, not improvise.

A corollary: "the tree is not yet bilingual" is a PROVISIONAL state, never a
contract. The slice-1 case that asserted the contrary was inverted, not deleted.

## The five measured points of the current state

1. **The product/tooling contradiction does not exist.** The contradiction is
   INTERNAL to the bench: it names `i18n-lint-bilingue` as the corrector, then
   requires the tree to have remained uncorrected. For a reader: nobody lied, the
   calendar did.

2. **The subject is dated and datable.** It is born of the SPLIT of slice 2's
   input lot, not of a production defect. Measured: `7a53357` → 23 passed,
   `978fbcb` → 4 failed.

3. **Slice 1's corpus holds 5 files that no slice carries.** The 4
   `agents/*/SOUL.md` (335 accented lines across 629 lines: pj-master 337,
   pj-dev 80, pj-doc 108, pj-test 104) and `docs/architecture/context/issue-2.md`
   (168 lines, 5 accented — citations of the frozen contract). These 335 accented
   lines are what block the language scan and stall dev-4/dev-5 — NOT the `docs/`.

4. **`tests/test_pj_card_lint_i18n.py` is a spec artifact with no object.**
   Declared by `slices.json`, existing nowhere (`git ls-files` → 0), indexed
   nowhere (`git log --all --diff-filter=A` → 0 commits — it never existed). And
   no perimeter card is feasible beyond the graph already built: `t6 submitted #2`
   already has 25 parents and 2 children, so `pj-graphwatch` no longer re-selects
   it — an extra slice would be a plan with no executor. This is the mechanical
   reason decision 2 attaches the lot to the existing slice k=2.

5. **Name drift with no code effect.** `slices.json` declared
   `frozen_literals_file = pipeline/i18n_gate_terms.yaml`, read by nobody
   (verified: the repo, `~/.hermes/scripts/`, the pj-master profile). The real
   deliverable is `pipeline/pj_lang_lint.exclusions.yaml`, read by
   `pj_lang_lint.py`. The blocking loop is unreadable: whoever follows
   `slices.json` looks for an absent file and never sees the rule written in the
   other.

## A residual gap, flagged for the spec

The dating mechanism (decision 3) gates the four measurement cases. The register
FORM cases still anchor on "the last commit that touches the plate" (the
`clone_base` fixture resolves `git log -1 -- <plate>`), not on the declared key.
Consequence, measured by the convergence card `t_c20aecf3` on disposable clones:
committing any edit to the plate turns 5 register-form cases red, even though the
prose itself is irrelevant to them. Closing this gap — anchoring `clone_base` on
`ANCRAGE_REVISION` instead of the plate's last commit — is a spec decision, not a
worker decision. Until then, the plate prose must not be rewritten.

## What a reader takes away

The plate's register is a DATED artifact: it says what the tree looked like at
`6d787c5`. A translated tree does not make the bench red *as a verdict* — the
bench reports `INDÉTERMINÉ`, naming its key — and the red the scan shows today is
the corpus that no slice has carried yet (the four SOUL files). That is a
deadline, not a lie, and not a defect in the documentation.
