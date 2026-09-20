"""Slice 11 (reference issue-pipeline) — language RED bank, card t_bc3f47a0.

Subject of this card, and the ONE document `dev-11` translates (card t_0daf268e):

    skills/hermes-multi-agent-orchestration/references/issue-pipeline.md

The bank only MEASURES it: it never edits it. `tests/**` is this card's whole write
perimeter, and `dev-11` owns the source in the same worktree (peer programming
test || dev, same branch `wt/issue-2-rewrite-in-english`).

Contract executed here (same form as the slice-2 bank and the sibling slice banks of
this issue):

    python3 pipeline/pj_lang_lint.py [--exclusions F] [<path> ...]

- rc 0 = compliant AND silent (stdout and stderr both empty);
- rc 1 = at least one line carrying a diacritic outside a frozen span, each line
  naming `path:line`;
- rc 2 = usage error (reserved for source facts, never for a violation).

The two states measured when this bank was written
--------------------------------------------------

`dev-11` had not landed its translation yet: at `HEAD` the file is byte-identical to
`origin/dev` (289 lines, 171 accented, sha256 compared in the probe), so the RED is
the LIVE state and not a reconstruction — the nominal and the two error cases name
the file and its 171 accented lines.

What this bank proves, and what it does NOT
-------------------------------------------

The diacritic scan is NECESSARY but not SUFFICIENT. This document carries 289 lines
of which 171 are accented (measured at `origin/dev`, reproduced below by the case
that recomputes them, and declared identically by the ratified plate's ledger: slice
11, `ref-issue-pipeline`, `lines: 289`, `accented_lines: 171`), so **118 lines carry
no diacritic at all** — and French prose survives translation without losing an
accent. Measured: the bank's lexical detector flags 12 of those 118 lines at the
reference revision (threshold K = 2 distinct French-only words per line) and must
flag 0 at the translated tip. That pair is EXECUTED in the same run.

Low recall, stated: 12 of 118 accent-free lines. It is a guard against the worst
half-translations, never a completeness proof; the diff review stays required in
conv-11.

Calibration: the detector is re-measured over 1288 accent-free lines this pipeline
already produced — the ratified plate's `outside_corpus` (3 files: the two vault MOCs
and the issue-2 framing note) plus every slice the plate declares `kind: translate`
whose COMMITTED copy (HEAD, not the working tree) now carries zero accented line
(measured: 7 files, the slices 3, 7 and 8 deliverables). 0 false positive at K = 2.

Corrections to the card's own prose (measured, printed in the failure paths)
----------------------------------------------------------------------------

1. The card announces "18 citations de littéraux gelés". Measured at `origin/dev`:
   `Importé depuis` occurs **1 time** (line 37, inside the span
   ``Importé depuis <url issue>``) and `ROOM:` **0 times** (0 == 0, printed as such).
   The figure 18 is not reproducible, and a case demanding 18 positive citations
   would be red forever. The limit nature is therefore written as "count preserved
   reference -> HEAD" for the two frozen protocols, while its real weight sits on the
   machine vocabulary this document teaches (measurement below) — the contract the
   translation can silently break.
2. The card announces "171 accentuées" — reproduced exactly, and the ratified plate's
   ledger declares the same number for the same path.

The contract this document really carries
-----------------------------------------

`skills/hermes-multi-agent-orchestration/references/issue-pipeline.md` is the reference
that teaches the most machine contracts of this skill: the card-format labels the
linters read, the kanban states, the CLI verbs, the manifest keys, the worktree
naming. Translating it can break two families the diacritic scan cannot see:

1. the FR gate labels it teaches (`Fonctionnalité:` / `Scénario:` and the 5 section
   titles) — a DE-ACCENTUATED form (`Fonctionnalite:`) is neither language, matches no
   branch of the card linter, and carries no diacritic;
2. the backticked machine vocabulary whose reader is a TRACKED production file
   (`pipeline/`, `agents/*/scripts/`, `plugins/`) — a renamed token makes its reader
   silent, with no error.

Both are judged, and the vocabulary is judged on its backticked CITATION with the
production file that reads each token printed as provenance. A bare English word that
happens to be a state name is prose; a backticked token is a citation of the contract.

Two measured exclusions, each with its reason
---------------------------------------------

- The ACCENTED gate labels of the ratified plate (`Fonctionnalité:`, `Scénario:`) are
  PROVEN-reader tokens (read by the card linters' regexes) yet are TRANSLATED by the
  human decision of 2026-09-20 (plate `gate_labels`, `corrected_by` slice 2). Pinning
  their count would red a correct translation, and the scan forbids leaving the French
  form in the corpus anyway (they are not frozen spans). They are therefore excluded
  from the pinned set and printed as such.
- The PLACEHOLDER-bearing spans (`--parent <t5>`, `pj-<slug>`, `<repo> #<N> · <titre>`,
  `gh-issue-<n>`) are read by production files verbatim, but the translation legitimately
  RENAMES the bracketed placeholder itself (`<orchestrateur>` -> `<orchestrator>`,
  `<titre>` -> `<title>`). They are judged on the placeholder-free part only by being
  printed as diagnostics; the pinned set is the 35 placeholder-free reader-proven tokens.

No real clock, no randomness: every fixture is a throwaway git repository or a throwaway
clone built by this bank from VERSIONED bytes (`git show origin/dev:<path>`), and every
count is recomputed from the bytes in hand rather than asserted as a copied literal.
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[1]

SLICE = ("skills/hermes-multi-agent-orchestration/references/issue-pipeline.md",)

TOOL_REL = "pipeline/pj_lang_lint.py"
EXCLUSIONS_REL = "pipeline/pj_lang_lint.exclusions.yaml"
PLATE_REL = "docs/architecture/context/issue-2-plate.html"
LINTER_REL = "pipeline/pj_card_lint.py"

TOOL = REPO / TOOL_REL
EXCLUSIONS = REPO / EXCLUSIONS_REL
PLATE = REPO / PLATE_REL
LINTER = REPO / LINTER_REL

SLICE_K = 11
# The pre-state of this slice: the branch's merge base against `origin/dev`, i.e. the
# bytes the translation starts from. Read through `git show`, never from a copy kept
# beside this bank, so the reference cannot drift with the tree under test.
REF_REF = "origin/dev"

# A neighbour of this slice: same directory, subject of another slice (9). It is the
# trap of the error decor — a bench matching by basename or by suffix imputes its state
# to this slice and vice versa.
NEIGHBOUR_REL = "skills/hermes-multi-agent-orchestration/references/kanban-builtins.md"

# Character class of the contract, identical to the scanner, to the sibling banks and to
# the ratified plate's `character_class_chars`. Re-declared here on purpose: a bank that
# imported the class from the subject would widen with the subject. The nominal case
# asserts this literal equals the class the plate declares.
ACCENTS = "àâäçéèêëîïôöùûüÿœæñÀÂÄÇÉÈÊËÎÏÔÖÙÛÜŸŒÆÑ"

# The two and only frozen machine protocols. `Importé depuis` occurs once at the
# reference revision, `ROOM:` zero times: both counts are ASSERTED as preserved and
# PRINTED, so a 0 == 0 is never mistaken for a pass of anything else.
PROTOCOLES = ("Importé depuis", "ROOM:")

# French-only function words: no English homograph. Same list and threshold as the
# sibling banks, RE-CALIBRATED here over this tree's already-English corpora.
LEXIQUE_FR = [
    "dans", "avec", "sans", "sous", "chez", "vers", "entre", "cette", "leur",
    "leurs", "nous", "vous", "elles", "sont", "tous", "toute", "toutes", "donc",
    "ainsi", "aussi", "mais", "cependant", "lorsque", "depuis", "selon", "afin",
    "puis", "ensuite", "jamais", "doit", "doivent", "faut", "ceux", "celle",
    "celui", "soit", "dont", "quand", "alors", "aucun", "aucune", "carte",
    "cartes", "fichier", "fichiers", "seuil", "travaille", "ecrire", "ecrit",
]
SEUIL_LEXICAL = 2

MOT_FR = re.compile(
    r"(?<![\w-])(%s)(?![\w-])"
    % "|".join(re.escape(t) for t in sorted(LEXIQUE_FR, key=len, reverse=True)),
    re.I,
)

SPAN_RE = re.compile(r"`([^`\n]+)`")
STRICT_RE = re.compile(r"([\w./-]+\.md):(\d+)")
LEDGER_RE = re.compile(
    r"<script[^>]*id=[\"']plate-ledger[\"'][^>]*>(?P<json>.*?)</script>", re.S | re.I
)
HEADING_RE = re.compile(r"^#{1,6}\s")
FENCE_RE = re.compile(r"^\s*```")
TABLE_SEP_RE = re.compile(r"^\s*\|?[\s:|-]*-[\s:|-]*\|[\s:|-]*$")
CONTRACT_ITEM_RE = re.compile(r"^\s*(\d)\.\s+\*\*(.+?)\*\*", re.M)
# A bracketed/dollar placeholder inside a backticked span: the translation renames it.
PLACEHOLDER_RE = re.compile(r"[<>{}$]")

ENGLISH_STUB = ("# Title\n\nAll English prose, without a single diacritic.\n"
                "No contract is cited here.\n")

_READERS = None


# --------------------------------------------------------------------------- outils


def _run(cmd, cwd=None, env=None):
    return subprocess.run(cmd, cwd=str(cwd) if cwd else None, capture_output=True,
                          text=True, timeout=300, env=env)


def git(*args, cwd=REPO):
    p = _run(["git", "-C", str(cwd), *args])
    assert p.returncode == 0, "git %s failed: %s" % (" ".join(args), p.stderr)
    return p.stdout


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def tracked(root=REPO):
    """Canonical enumeration: the INDEX, never a directory walk.

    Each `git worktree` under `.worktrees/` carries a full copy of the corpus, so a walk
    counts the tree several times over.
    """
    p = subprocess.run(["git", "-C", str(root), "ls-files", "-z"], capture_output=True)
    assert p.returncode == 0, p.stderr.decode()
    return sorted(x.decode("utf-8") for x in p.stdout.split(b"\x00") if x)


def git_show(rel, ref=REF_REF):
    """The versioned bytes of `rel` at `ref` — the pre-state of the translation."""
    p = _run(["git", "-C", str(REPO), "show", "%s:%s" % (ref, rel)])
    assert p.returncode == 0, (
        "cannot read the pre-state `%s:%s`: %s\n"
        "the reference revision is where this slice really is French, so every fixture "
        "must come from it" % (ref, rel, p.stderr))
    return p.stdout


def head_text(rel):
    f = REPO / rel
    assert f.is_file(), (
        "slice file absent from the tree: %s\n"
        "this bank is written BEFORE the translation (peer programming test || dev): "
        "that failure is the expected RED." % rel)
    return f.read_text(encoding="utf-8")


def flat(text):
    """Markdown wraps the prose: the contract is judged on FLATTENED text with the line
    breaks collapsed, otherwise a label split across two lines is invisible."""
    return re.sub(r"\s+", " ", text)


def normalise(s):
    return re.sub(r"\s+", " ", s).strip()


def strip_accents(s):
    return "".join(c for c in s if c not in ACCENTS)


def sep_key(s):
    """Comparison key of a label: whitespace collapsed, spaces around `/` and `:`
    removed. The separator is not part of the contract, the tokens are."""
    s = re.sub(r"\s*/\s*", "/", normalise(s))
    return re.sub(r"\s*:\s*", ":", s).lower()


def require_upstream():
    manquants = [rel for rel, p in ((TOOL_REL, TOOL), (EXCLUSIONS_REL, EXCLUSIONS))
                 if not p.is_file()]
    if manquants:
        pytest.fail(
            "upstream deliverable absent from the tree: %s\n"
            "this bank is written BEFORE the implementation (peer programming "
            "test || dev): this failure is the expected RED." % ", ".join(manquants))


# ------------------------------------------------------------------------ exclusions


def declared_exclusions():
    """(literals, raw text) read INDEPENDENTLY of the scanner.

    The bank does not ask the subject which literals it blanches: it re-reads the
    versioned declaration, otherwise an exemption ADDED by the slice would go unnoticed —
    which is exactly the bypass the limit case must refuse.
    """
    assert EXCLUSIONS.is_file(), "exclusions file absent: %s" % EXCLUSIONS
    raw = EXCLUSIONS.read_text(encoding="utf-8")
    doc = yaml.safe_load(raw)
    lits = []

    def walk(node, list_ctx=False):
        if isinstance(node, dict):
            for key, val in node.items():
                kl = str(key).strip().lower()
                if kl in ("litteral", "literal", "litteraux", "literaux") \
                        and isinstance(val, str):
                    lits.append(val)
                    continue
                walk(val, kl in ("protocoles", "geles", "gelés", "frozen_literals"))
        elif isinstance(node, (list, tuple)):
            for val in node:
                if isinstance(val, str) and list_ctx:
                    lits.append(val)
                else:
                    walk(val, list_ctx)

    walk(doc)
    return [x.strip() for x in dict.fromkeys(lits) if x and x.strip()], raw


def frozen_literals():
    lits, _ = declared_exclusions()
    assert lits, "%s declares no frozen literal" % EXCLUSIONS_REL
    return lits


def residual(line, literals):
    """The line minus every frozen span — the scanner's own granularity (span, not line)."""
    for lit in literals:
        if lit:
            line = line.replace(lit, "")
    return line


def expected_violations(text, literals):
    """Line numbers of `text` carrying a diacritic OUTSIDE a frozen span, per THIS bank."""
    out = []
    for num, line in enumerate(text.splitlines(), 1):
        if any(c in ACCENTS for c in residual(line, literals)):
            out.append(num)
    return out


# ------------------------------------------------------------------------- provenance


def production_readers():
    """Tracked executable files (`.py`/`.sh`) outside `tests/` and `docs/`.

    A backtick token of the slice is treated as a machine contract only when one of these
    files carries it verbatim: that is the falsifiable form of "this literal is frozen" —
    a token with no reader is prose or a placeholder, and prose is what the translation
    is allowed to rewrite.
    """
    global _READERS
    if _READERS is None:
        out = {}
        for rel in tracked():
            if rel.split("/")[0] in ("tests", "docs") or rel in SLICE:
                continue
            if not rel.endswith((".py", ".sh")):
                continue
            f = REPO / rel
            try:
                out[rel] = f.read_text(encoding="utf-8", errors="replace")
            except OSError:  # pragma: no cover - unreadable tracked file
                continue
        _READERS = out
    return _READERS


def proven_reader(span):
    """(file, line) of the first tracked production file carrying `span`, else (None, None)."""
    for rel, txt in sorted(production_readers().items()):
        i = txt.find(span)
        if i >= 0:
            return rel, txt[:i].count("\n") + 1
    return None, None


def spans_of(text):
    """Distinct backticked spans of `text`, in first-appearance order, stripped."""
    out = []
    for s in SPAN_RE.findall(text):
        s = s.strip()
        if s and s not in out:
            out.append(s)
    return out


def garde(span):
    """A span is judged only if it looks like a machine token rather than punctuation."""
    return len(span) >= 3 and len([c for c in span if c.isalnum()]) >= 2


def gate_labels():
    """The plate's `gate_labels.translated` records: (fr, en, read_by)."""
    recs = ledger().get("gate_labels", {}).get("translated")
    assert recs, ("the ratified plate carries no `gate_labels.translated` record: the "
                  "translated-label exclusion of this bank has lost its subject")
    return [(r.get("fr"), r.get("en"), r.get("read_by")) for r in recs]


def translated_fr_labels():
    """The FR gate labels the human decision of 2026-09-20 turns into English.

    They are read by the card linters (so they look like frozen literals) but they are
    TRANSLATED: pinning their count here would red a correct translation, and leaving the
    French form in the corpus is forbidden by the scan itself (they are not frozen spans).
    """
    out = []
    for fr, en, _ in gate_labels():
        if fr and en and fr != en:
            out.append(fr)
    assert len(out) >= 2, (
        "the plate declares fewer than 2 FR labels translated (%r): the exclusion of this "
        "bank would be vacuous" % out)
    return out


def machine_vocabulary(text):
    """(pinned, excluded, placeholders) — the backticked code tokens with PROVENANCE.

    - `pinned`: placeholder-free tokens a tracked production file carries verbatim, minus
      the FR gate labels the human decision translates;
    - `excluded`: the FR gate labels found among the reader-proven tokens (printed, their
      count is EXPECTED to fall);
    - `placeholders`: reader-proven tokens carrying a bracketed placeholder — the
      translation legitimately renames the placeholder itself, so they are not pinned.

    Only tokens written INSIDE a backtick span are collected: `` `ready` `` is a citation
    of a machine state, while the bare English word "ready" is prose a translation may add
    or remove at will. Counting the bare word would red a correct translation.
    """
    vocab = {}
    for span in spans_of(text):
        if not garde(span):
            continue
        r, n = proven_reader(span)
        if r:
            vocab[span] = "%s:%d" % (r, n)
    trad = set(translated_fr_labels())
    excluded = {s: p for s, p in vocab.items() if s in trad}
    placeholders = {s: p for s, p in vocab.items()
                    if s not in trad and PLACEHOLDER_RE.search(s)}
    pinned = {s: p for s, p in vocab.items()
              if s not in trad and not PLACEHOLDER_RE.search(s)}
    return pinned, excluded, placeholders


def cited_span(span):
    """The backticked citation of `span` — the form a document writes to reference it."""
    return "`%s`" % span


def labels_taught_at_ref():
    """The gate labels the REFERENCE REVISION really teaches (FR or EN form).

    Deliberately derived from the versioned pre-state, never from the document under test:
    measured at `origin/dev`, this document teaches 8 of the plate's 9 labels —
    `jamais / ne pas` is a DETECTION vocabulary token, taught by no version of this
    document, and demanding it at HEAD would red a correct translation forever.
    """
    ref = sep_key(flat(git_show(SLICE[0])))
    out = []
    for fr, en, reader in gate_labels():
        forms = {sep_key(fr), sep_key(en)}
        if any(f and f in ref for f in forms):
            out.append((fr, en, reader))
    assert out, ("the reference revision teaches NONE of the plate's gate labels: this "
                 "case has lost its subject")
    return out


def label_problems(text):
    """Discrepancies of the taught contract against the labels the pre-state teaches.

    Two families, both measured on the document itself:

    1. MISSING — a label taught by the reference revision is taught NOWHERE in the
       document (prose, numbered item or backticked span): the translation dropped a
       contract this document exists to describe. Accepted in the FR or the EN form — the
       LANGUAGE is deliberately not judged here (the human decision of 2026-09-20 makes
       the EN form canonical and the plate's gate_labels carry the mapping).
    2. DE-ACCENTUATED FRENCH — the accent-stripped French form of a label appears while
       NEITHER the French nor the translated form appears anywhere in the document:
       `Fonctionnalite:` is neither language, is invisible to the diacritic scan, and
       matches no branch of the card linter. Naming the line makes the red actionable.
    """
    key = sep_key(flat(text))
    problems, seen = [], []

    for fr, en, reader in labels_taught_at_ref():
        fr_k, en_k = sep_key(fr), sep_key(en)
        forme = fr_k if fr_k and fr_k in key else (en_k if en_k and en_k in key else None)
        if forme is None:
            problems.append(
                "MISSING: gate label %r / %r (read by %s) is taught by no unit of the "
                "document — the translation dropped part of the card-format contract it "
                "describes" % (fr, en, reader))
        else:
            seen.append((fr, en if forme == en_k else "<FR form>"))

    for fr, en, _ in labels_taught_at_ref():
        if fr == en or not any(c in ACCENTS for c in normalise(fr)):
            continue  # a label with no diacritic has no de-accentuated variant to ban
        if sep_key(fr) in key or sep_key(en) in key:
            continue  # the correct form is taught somewhere: nothing is de-accentuated
        bare = sep_key(strip_accents(fr))
        if not bare or bare not in key:
            continue
        for num, line in enumerate(text.splitlines(), 1):
            if bare in sep_key(line) or bare in key:
                problems.append(
                    "DE-ACCENTUATED FRENCH (%s:%d): %r is neither the French label %r nor "
                    "its translated form %r — it is the French label with its diacritics "
                    "removed, which the language scan cannot see and the card linter "
                    "refuses (no regex branch matches it)"
                    % (SLICE[0], num, line.strip()[:90], fr, en))
                break
    return problems, seen


def labels_present_in_english(text):
    """The judged labels whose ENGLISH form the document already presents anywhere."""
    key = sep_key(flat(text))
    out = []
    for fr, en, _ in labels_taught_at_ref():
        if fr == en or not any(c in ACCENTS for c in normalise(fr)):
            continue  # no de-accentuated variant to ban
        en_k = sep_key(en)
        if en_k and en_k in key:
            out.append((fr, en))
    return out


def linter_section_patterns():
    """The card linter's own section regexes, loaded by path (the repo's idiom)."""
    assert LINTER.is_file(), "card linter absent: %s" % LINTER_REL
    import importlib.util
    spec = importlib.util.spec_from_file_location("pj_card_lint_slice11", str(LINTER))
    assert spec is not None and spec.loader is not None, (
        "cannot load %s by path: the diagnostic of this slice has lost its subject"
        % LINTER_REL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    patterns = getattr(mod, "SECTION_PATTERNS", None)
    assert patterns and len(patterns) >= 5, (
        "%s exposes %r section pattern(s): the diagnostic of this slice has lost its "
        "subject" % (LINTER_REL, patterns and len(patterns)))
    return patterns


# -------------------------------------------------------------------------------- scan


def scan(paths=(), cwd=REPO, exclusions=EXCLUSIONS):
    cmd = [sys.executable, str(TOOL)]
    if exclusions is not None:
        cmd += ["--exclusions", str(exclusions)]
    cmd += [str(p) for p in paths]
    return _run(cmd, cwd=cwd)


def out_of(p):
    return p.stdout + p.stderr


def resume(p, quoi):
    return ("%s: rc=%d\n--- stdout ---\n%s\n--- stderr ---\n%s"
            % (quoi, p.returncode, p.stdout, p.stderr))


def reported(out):
    """`path:NN` pairs of the contract's own report shape, deduplicated."""
    vus, uniq = set(), []
    for ligne in out.splitlines():
        for m in STRICT_RE.finditer(ligne):
            cle = (m.group(1), int(m.group(2)))
            if cle in vus:
                continue
            vus.add(cle)
            uniq.append((cle[0], cle[1], ligne.strip()))
    return uniq


def named_exact(out):
    """Names reported by the scan, kept as EXACT relative paths (never basenames).

    The corpus tracks several dozen `.md` and the file names are shared across
    directories, so a suffix test would impute a neighbour's violation to this slice.
    """
    return sorted({rel for rel, _, _ in reported(out)})


# --------------------------------------------------------------------------- fixtures


def build_tree(root, files):
    """Throwaway git repository: `files` = {relative path: content}, all tracked."""
    env = dict(os.environ)
    env.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1",
               GIT_TERMINAL_PROMPT="0", HOME=str(root))
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    p = _run(["git", "init", "-q"], cwd=root, env=env)
    assert p.returncode == 0, "git init failed: %s" % p.stderr
    for rel, txt in files.items():
        cible = root / rel
        cible.parent.mkdir(parents=True, exist_ok=True)
        cible.write_text(txt, encoding="utf-8")
    p = _run(["git", "add", "--", *files], cwd=root, env=env)
    assert p.returncode == 0, "git add failed: %s" % p.stderr
    return root


def precondition_translated(literals=None):
    """Nominal/limit precondition: the slice IS translated — the expected RED otherwise.

    The failure NAMES the file and the line of every remaining accented line outside a
    frozen span, so the RED is actionable rather than a boolean.
    """
    require_upstream()
    lits = literals if literals is not None else frozen_literals()
    index = set(tracked())
    absents = [rel for rel in SLICE if not (REPO / rel).is_file() or rel not in index]
    if absents:
        pytest.fail("slice file(s) absent from the disk or the index: %s" % ", ".join(absents))

    restes, total = [], 0
    for rel in SLICE:
        for num, line in enumerate(head_text(rel).splitlines(), 1):
            if not any(c in ACCENTS for c in line):
                continue
            total += 1
            reste = residual(line, lits)
            if any(c in ACCENTS for c in reste):
                restes.append("%s:%d — %s" % (rel, num, reste.strip()[:70]))
    if restes:
        pytest.fail(
            "slice 11 NOT translated: %d accented line(s), of which %d outside a frozen "
            "span.\n  - %s\n(this bank is written BEFORE the translation: this failure "
            "IS the expected RED)"
            % (total, len(restes), "\n  - ".join(restes[:8])))


def ledger():
    if not PLATE.is_file():
        pytest.fail("ratified plate absent: %s" % PLATE)
    m = LEDGER_RE.search(PLATE.read_text(encoding="utf-8"))
    assert m, "no `plate-ledger` machine block in %s" % PLATE_REL
    try:
        return json.loads(m.group("json"))
    except json.JSONDecodeError as exc:
        pytest.fail("plate-ledger unreadable (%s)" % exc)


def ledger_slice(k=SLICE_K):
    raw = ledger().get("slices")
    assert raw, "the plate ledger carries no `slices` entry"
    recs = raw if isinstance(raw, dict) else {r.get("k"): r for r in raw}
    rec = recs.get(k) or (recs.get(str(k)) if isinstance(recs, dict) else None)
    assert rec, "slice %d absent from the plate ledger" % k
    return rec


def skeleton(text):
    """The document's SKELETON: what a translation must not rewrite, only reword."""
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    fm = yaml.safe_load(m.group(1)) if m else None
    lines = text.splitlines()
    return {
        "frontmatter_keys": sorted(fm) if isinstance(fm, dict) else None,
        "headings": sum(1 for l in lines if HEADING_RE.match(l)),
        "fence_delimiters": sum(1 for l in lines if FENCE_RE.match(l)),
        "table_separators": sum(1 for l in lines if TABLE_SEP_RE.match(l)),
        "numbered_items": len(CONTRACT_ITEM_RE.findall(text)),
    }


def skeleton_problems(rel, ref, head):
    """Discrepancies of the skeleton reference -> HEAD, field by field."""
    s_ref, s_head = skeleton(ref), skeleton(head)
    return ["%s: %s %r -> %r (a translation reworks the prose, it does not restructure "
            "the document)" % (rel, champ, s_ref[champ], s_head[champ])
            for champ in sorted(s_ref) if s_ref[champ] != s_head[champ]]


def accented_lines(lines):
    return [l for l in lines if any(c in ACCENTS for c in l)]


def offenders(source, is_path=True):
    """[(line, tokens, text)] for the accent-free French lines of a document."""
    text = head_text(source) if is_path else source
    hits = []
    for n, line in enumerate(text.splitlines(), 1):
        if any(c in ACCENTS for c in line):
            continue  # the scan already reports these; this control judges the rest
        toks = sorted({m.group(1).lower() for m in MOT_FR.finditer(line)})
        if len(toks) >= SEUIL_LEXICAL:
            hits.append((n, toks, line.strip()))
    return hits


def english_corpora():
    """(declared, derived) — the accent-free lines the detector must NOT fire on.

    Two sources, because they answer different questions: the plate's `outside_corpus` is
    a RATIFIED declaration of what counts as already-English, and the second is DERIVED —
    every slice the plate declares `kind: translate` whose COMMITTED copy (HEAD, not the
    working tree) now carries zero accented line. Reading HEAD keeps the calibration
    immune to a sibling slice's in-flight edits in the shared worktree.
    """
    doc = ledger()
    declare = [e.get("path") for e in doc.get("outside_corpus") or [] if e.get("path")]
    recs = doc.get("slices") or []
    recs = list(recs.values()) if isinstance(recs, dict) else recs
    deja = []
    for rec in recs:
        if str(rec.get("kind")) != "translate":
            continue
        fichiers = rec.get("files") or {}
        noms = sorted(fichiers) if isinstance(fichiers, dict) else sorted(fichiers)
        noms = [r for r in noms if r not in SLICE]
        if not noms:
            continue
        copies = []
        for rel in noms:
            p = _run(["git", "-C", str(REPO), "show", "HEAD:%s" % rel])
            if p.returncode != 0:
                copies = []
                break
            copies.append(p.stdout.splitlines())
        if copies and not any(accented_lines(c) for c in copies):
            deja.extend(noms)
    return declare, deja


def calibration_report(paths):
    """(lines examined, false positives) for the lexical detector over `paths`."""
    n, faux = 0, []
    for rel in paths:
        p = REPO / rel
        if not p.is_file():
            faux.append((rel, 0, ["<absent>"], "file of the calibration corpus absent"))
            continue
        for line in p.read_text(encoding="utf-8").splitlines():
            if any(c in ACCENTS for c in line):
                continue
            n += 1
            toks = sorted({m.group(1).lower() for m in MOT_FR.finditer(line)})
            if len(toks) >= SEUIL_LEXICAL:
                faux.append((rel, 0, toks, line.strip()[:90]))
    return n, faux


@pytest.fixture(scope="module")
def clone_base(tmp_path_factory):
    """Throwaway clone at the branch's commit: mutations never touch the live tree."""
    require_upstream()
    commit = git("rev-parse", "HEAD").strip()
    d = tmp_path_factory.mktemp("slice11") / "clone"
    p = _run(["git", "clone", "--no-hardlinks", "--quiet", str(REPO), str(d)])
    assert p.returncode == 0, "clone impossible: %s" % p.stderr
    p = _run(["git", "-C", str(d), "checkout", "--detach", commit])
    assert p.returncode == 0, "checkout %s impossible: %s" % (commit, p.stderr)
    return {"dir": d, "commit": commit}


@pytest.fixture
def clone(clone_base, tmp_path):
    """Playable copy: each test mutates ITS copy, never the module-scoped one."""
    d = tmp_path / "clone"
    shutil.copytree(clone_base["dir"], d)
    for rel in SLICE:
        assert (d / rel).is_file(), "the clone does not carry %s" % rel
    return {"dir": d, "commit": clone_base["commit"]}


def scan_rel(ctx, *rels):
    """Scan the named subjects INSIDE the clone, from the clone's own root."""
    return scan(list(rels), cwd=ctx["dir"])


# -------------------------------------------------------------------------- nominal


def test_nominal_the_scan_is_exit_0_and_silent_on_the_slice_file():
    """Nominal: rc 0 AND silent on the document of the slice.

    The two halves are one contract: a scan that prints a report while returning 0 is not
    compliant with it either.
    """
    precondition_translated()
    p = scan(SLICE)
    assert p.returncode == 0, resume(
        p, "scan of the translated document: exit 0 expected")
    assert out_of(p).strip() == "", (
        "a compliant corpus must be SILENT (stdout AND stderr empty); obtained:\n%r"
        % out_of(p))
    n = len(head_text(SLICE[0]).splitlines())
    print("witness nominal: %s -> rc=0, silent, %d ligne(s)" % (SLICE[0], n))


def test_nominal_the_whole_corpus_scan_does_not_name_the_slice_file():
    """Nominal, enumeration branch: the no-argument form takes another code path
    (`git ls-files` over the whole corpus) and must not name the file of this slice.

    The assertion is on the NAMES, not on rc: while other slices are still French the
    whole-tree scan legitimately returns 1, and this slice's own contribution is what
    this case isolates. The consistency half is asserted too — rc 1 implies at least one
    named line, so the enumeration branch cannot pass by printing nothing. Exact relative
    paths only — the corpus is full of same-named `README.md` / `SKILL.md` files.
    """
    precondition_translated()
    p = scan()
    out = out_of(p)
    noms = set(named_exact(out))
    fautifs = sorted(noms & set(SLICE))
    assert not fautifs, (
        "the whole-tree scan still NAMES files of this slice: %r\n%s" % (fautifs, out))
    if p.returncode == 1:
        assert noms, (
            "the scan returns 1 without naming any `path:line` of its report shape: the "
            "contract says each violation names its path\n%s" % out)
    else:
        assert out.strip() == "", (
            "rc=%d with output: the contract says rc 0 is silent\n%s"
            % (p.returncode, out))
    print("witness whole corpus: %d tracked .md, rc=%d, %d violation file(s) elsewhere, "
          "0 on the slice"
          % (len([r for r in tracked() if r.endswith(".md")]), p.returncode, len(noms)))


def test_nominal_the_perimeter_the_ledger_and_the_skeleton_are_the_ratified_ones():
    """Nominal: the perimeter and the character class are the RATIFIED ones, and the
    document SKELETON survives the translation.

    Three independent sources are closed against each other: the plate's ledger (the
    declared file list), the plate's declared character class, and the tree (skeleton
    reference -> HEAD). The ledger's per-file NUMBERS are checked against the REFERENCE
    revision, never against HEAD: a translation and its ledger entry belong to the same
    commit, and editing slice 1's artifact is outside this slice's declared perimeter.
    """
    rec = ledger_slice()
    files = rec.get("files")
    declare = sorted(files) if isinstance(files, (list, tuple)) else sorted(files or {})
    assert declare == sorted(SLICE), (
        "the ratified plate declares slice %d as %r, this bank measures %r"
        % (SLICE_K, declare, sorted(SLICE)))

    classe = ledger().get("character_class_chars")
    assert classe == ACCENTS, (
        "the character class of this bank differs from the one the ratified plate "
        "declares: plate %r vs bank %r — the per-file numbers stop being comparable"
        % (classe, ACCENTS))

    ecarts = []
    for rel in SLICE:
        entry = files.get(rel) if isinstance(files, dict) else None
        assert isinstance(entry, dict), (
            "%s: no per-file numbers in the ledger entry: %r" % (rel, rec))
        ref = git_show(rel)
        if entry.get("lines") != len(ref.splitlines()):
            ecarts.append("%s: ledger declares %r lines, the reference revision has %d"
                          % (rel, entry.get("lines"), len(ref.splitlines())))
        n_ref = len(expected_violations(ref, ()))
        if entry.get("accented_lines") != n_ref:
            ecarts.append("%s: ledger declares %r accented lines, the reference revision "
                          "has %d" % (rel, entry.get("accented_lines"), n_ref))
        ecarts += skeleton_problems(rel, ref, head_text(rel))
    assert not ecarts, "perimeter/skeleton in discrepancy:\n  " + "\n  ".join(ecarts)
    print("witness perimeter: slice %d = %r, character class %r, skeleton ref=%r head=%r"
          % (SLICE_K, declare, classe, skeleton(git_show(SLICE[0])),
             skeleton(head_text(SLICE[0]))))


# --------------------------------------------------------------------------- limite


def test_limite_the_declared_frozen_literals_are_the_two_protocols_and_stay_verbatim():
    """Limit: the exemption file is not widened, and every declared frozen literal keeps
    its exact number of occurrences reference -> HEAD.

    Measured at the reference revision: this slice cites `Importé depuis` 1 time (line 37,
    inside the span ``Importé depuis <url issue>``) and `ROOM:` 0 times, so the citation
    half is 1 + 0 and is PRINTED as such. The card announces 18 citations; that figure is
    not reproducible and is NOT asserted. What this case forbids is the bypass: blanching
    French that is still in the corpus.
    """
    precondition_translated()
    lits, _ = declared_exclusions()
    assert sorted(lits) == sorted(PROTOCOLES), (
        "the exemption file declares %r; EXACTLY %r is expected — widening the exemptions "
        "is the bypass this case refuses (a translation does not blanch the French that "
        "is left)" % (sorted(lits), sorted(PROTOCOLES)))

    ecarts, vus = [], []
    for lit in lits:
        n_ref = sum(git_show(rel).count(lit) for rel in SLICE)
        n_head = sum(head_text(rel).count(lit) for rel in SLICE)
        vus.append((lit, n_ref, n_head))
        if n_ref != n_head:
            ecarts.append("frozen literal %r: %d occurrence(s) at %s -> %d at HEAD "
                          "(the reader of that literal goes silent, with no error)"
                          % (lit, n_ref, REF_REF, n_head))
        ci_ref = sum(git_show(rel).lower().count(lit.lower()) for rel in SLICE)
        ci_head = sum(head_text(rel).lower().count(lit.lower()) for rel in SLICE)
        if ci_ref != ci_head:
            ecarts.append("a CASE VARIANT of %r was introduced: %d case-insensitive "
                          "occurrence(s) -> %d" % (lit, ci_ref, ci_head))
    assert not ecarts, ("the frozen literals of this slice are not preserved:\n  - "
                        + "\n  - ".join(ecarts))
    print("witness frozen literals: declared %r, (literal, ref, HEAD) = %r — the card "
          "announces 18 citations, measured 1 + 0" % (lits, vus))


def test_limite_the_blindness_pair_on_a_transcribed_protocol(clone):
    """Limit, the blindness pair EXECUTED: the scan cannot see a translated frozen
    literal, and this bank can.

    The scan BLANKS the spans of the declared frozen literals before judging, and the
    translated form carries no diacritic either: `Importé depuis` renamed to
    `Imported from` leaves the scan rc 0 and SILENT — while
    `pipeline/pj_pipeline_deployer.py` reads that literal and the bridge goes silent,
    with no error. The two halves are asserted in the SAME run on the SAME clone, each
    with its own assertion, and the mutation is proven applied by sha256.
    """
    pre = scan_rel(clone, *SLICE)
    assert pre.returncode == 0 and out_of(pre).strip() == "", (
        "positive control: the translated slice must sort 0 and silent before the literal "
        "is touched; without it a later rc 0 proves nothing\n"
        + resume(pre, "scan(slice, état traduit)"))

    rel = SLICE[0]
    cible = clone["dir"] / rel
    avant = sha256(cible)
    texte = cible.read_text(encoding="utf-8")
    n_occ = texte.count("Importé depuis")
    remplacement = texte.replace("Importé depuis", "Imported from")
    assert n_occ and remplacement != texte, (
        "mutation NOT applied: %r carries no occurrence of the frozen literal" % rel)
    cible.write_text(remplacement, encoding="utf-8")
    apres = sha256(cible)
    assert apres != avant, "mutation NOT applied (hash witness): %s" % avant
    print("witness mutation: %s sha256 %s -> %s, %d occurrence(s) du protocole renommée(s)"
          % (rel, avant[:12], apres[:12], n_occ))

    p = scan_rel(clone, *SLICE)
    assert p.returncode == 0 and out_of(p).strip() == "", (
        "witness of the blind spot: with the frozen literal TRANSLATED the scan must "
        "still be GREEN and silent — it blanks the span before judging, and the renamed "
        "form carries no diacritic. It was not, so 'the scan cannot see this' is not "
        "established on this state\n" + resume(p, "scan(slice, protocole renommé)"))

    lits = frozen_literals()
    txt = "\n".join((clone["dir"] / rel).read_text(encoding="utf-8").splitlines())
    manquants = [lit for lit in lits if lit in texte and lit not in txt]
    assert manquants, (
        "the citation control did NOT see the renamed frozen literal while the scan was "
        "green: the guard is blind and this case proves nothing")
    print("witness paire d'aveuglement: scan rc=0 MUET sur le clone renommé, contrôle de "
          "citation ROUGE sur %r — la transcription du protocole est invisible au scan"
          % (manquants,))


def test_limite_the_machine_vocabulary_cited_by_the_slice_is_preserved_with_provenance():
    """Limit — the contract this slice really carries: the code tokens it teaches.

    Every backtick token of the slice whose reader is a TRACKED PRODUCTION file
    (`pipeline/`, `agents/*/scripts/`, `plugins/`) must keep the same number of
    occurrences reference -> HEAD, counted on FLATTENED text. A token with no reader is
    prose and is deliberately NOT judged; the vocabulary and its provenance are printed,
    so a red is diagnosable.

    Two measured exclusions, both PRINTED: the FR gate labels the human decision of
    2026-09-20 translates (pinning them would red a correct translation), and the
    placeholder-bearing spans whose bracketed placeholder the translation renames.
    Falsifiability is EXECUTED in the same run: a copy of the document with one cited
    token renamed must red the very function that judges it.
    """
    precondition_translated()
    ref_all = flat(git_show(SLICE[0]))
    head_all = flat(head_text(SLICE[0]))

    vocab, excl, placeholders = machine_vocabulary(git_show(SLICE[0]))
    assert len(vocab) >= 20, (
        "only %d machine token(s) of this slice have a proven reader in the tree: the "
        "provenance scan is broken, or the tokens moved — %r" % (len(vocab), sorted(vocab)))
    assert len(excl) >= 2, (
        "the translated gate labels are absent from the exclusion set (%r): the vocabulary "
        "would pin French tokens the human decision turns into English" % (sorted(excl),))

    ecarts = []
    for span, prov in sorted(vocab.items()):
        cite = cited_span(span)
        n_ref, n_head = ref_all.count(cite), head_all.count(cite)
        if n_ref != n_head:
            ecarts.append("%s (read by %s): %d citation(s) -> %d"
                          % (cite, prov, n_ref, n_head))
    assert not ecarts, (
        "machine contracts of the slice were damaged by the translation:\n  - "
        + "\n  - ".join(ecarts)
        + "\nvocabulary with provenance: %r" % vocab)

    # Falsifiability, same function, same call form: rename one cited token in a copy.
    cible = max(vocab, key=lambda s: (ref_all.count(cited_span(s)), s))
    cite = cited_span(cible)
    mutant = head_all.replace(cite, cited_span(cible + "-ALT"))
    assert mutant != head_all, (
        "the mutation was not applied (no occurrence of %s to rename)" % cite)
    assert mutant.count(cite) != ref_all.count(cite), (
        "the mutation left %d citation(s) of %s: the case cannot falsify the assertion it "
        "is meant to prove" % (mutant.count(cite), cite))
    print("witness machine vocabulary: %d token(s) pinned with provenance -> 0 "
          "discrepancy; %d translated gate label(s) excluded (%r); %d placeholder span(s) "
          "NOT pinned (%r); mutation renames %s (%d citation(s) -> %d)"
          % (len(vocab), len(excl), sorted(excl), len(placeholders),
             sorted(placeholders), cite, ref_all.count(cite), mutant.count(cite)))
    for span, prov in sorted(vocab.items()):
        print("    %-45r x%d <- %s" % (span[:45], ref_all.count(cited_span(span)), prov))


def test_limite_the_card_format_contract_is_still_taught_and_no_deaccented_french_label():
    """Limit — the contract this document EXISTS to teach, judged on its own text.

    This reference defines the 5 mandatory sections of a card body and the Gherkin labels
    the linters read. Translating it can break that contract invisibly: a reworded section
    title carries no diacritic, and a DE-ACCENTUATED French label (`Fonctionnalite:`) is
    neither language and matches no branch of the card linter.

    GREEN at the reference revision, and it must stay green after the translation: this is
    a NON-REGRESSION guard, not the RED of the bank (the scan-based cases above carry the
    RED). It judges the language-AGNOSTIC contract — every gate label the pre-state teaches
    is still taught by some unit, in the FR or the EN form — precisely so that it reds
    under NO honest translation: the human decision of 2026-09-20 makes the EN form
    canonical and the plate's `gate_labels` carry the mapping. The one form no reading
    admits is banned outright.

    Both directions of the judge are EXECUTED in the same run: dropping a taught title
    must red it, and replacing a presented form with the accent-stripped French label must
    red it — with a positive control showing the reference form stays green. The
    linter-acceptance status of each presented title is PRINTED, never asserted: its green
    depends on slice 2 (`pipeline/pj_card_lint.py`), outside this slice's perimeter.
    """
    require_upstream()
    head = head_text(SLICE[0])
    problems, seen = label_problems(head)
    assert not problems, (
        "the card-format contract taught by %s does not survive the translation:\n  - "
        % SLICE[0] + "\n  - ".join(problems))

    items = [(int(m.group(1)), m.group(2)) for m in CONTRACT_ITEM_RE.finditer(head)]
    assert len(items) >= 5, (
        "only %d numbered bold item(s) found: the document no longer teaches the 5 "
        "sections of the card format — measured %r" % (len(items), items))
    nums = [n for n, _ in items]
    assert nums == sorted(nums) and len(set(nums)) == len(nums), (
        "the numbered sections are out of order or duplicated: %r" % nums)

    # falsifiability A: dropping a taught title must red the very judge used above
    n, titre = items[-1]
    mutant_a = head.replace("**%s**" % titre, "**section removed**", 1)
    assert mutant_a != head, "mutation A not applied (title %r not found verbatim)" % titre
    probs_a, _ = label_problems(mutant_a)
    assert probs_a, (
        "mutation A (title %r removed) left the judge GREEN: the MISSING family is blind, "
        "so this case does not prove the contract is still taught" % titre)

    # falsifiability B: the de-accentuated French label must be caught
    pairs = [(fr, en) for fr, en, _ in labels_taught_at_ref()
             if fr != en and any(c in ACCENTS for c in normalise(fr))]
    assert pairs, "no accented translated gate label in the judged set: nothing to ban"
    present_en = {fr for fr, _ in labels_present_in_english(head)}
    pair = next((p for p in pairs if p[0] in present_en), pairs[0])
    fr, en = normalise(pair[0]), normalise(pair[1])
    bare = normalise(strip_accents(pair[0]))
    cible = en if pair[0] in present_en else fr
    mutant_b = head.replace(cible, bare, 1)
    assert mutant_b != head, (
        "mutation B not applied: neither %r nor %r is presented verbatim by the document"
        % (fr, en))
    probs_b, _ = label_problems(mutant_b)
    assert probs_b, (
        "mutation B (%r -> %r) left the judge GREEN: nothing here would catch a "
        "de-accentuated French label, which is invisible to the language scan"
        % (cible, bare))

    # positive control, same judge and same call form: the reference form stays accepted
    probs_pos, _ = label_problems(head)
    assert not probs_pos, ("positive control FAILED: the judge reds the document in its "
                           "reference form: %r" % probs_pos)

    # diagnostic only: does the card linter accept the titles the document presents?
    patterns = linter_section_patterns()
    diag = []
    for num, lab in [i for i in items if i[0] <= 5]:
        accepte = [nom for nom, rx in patterns if rx.search("# %s" % lab)]
        diag.append((num, lab, accepte))
    print("witness taught contract: %d numbered section(s); plate labels taught (FR or EN) "
          "%r; English forms ALREADY taught at the reference revision: %d"
          % (len(items), seen, len(present_en)))
    print("    linter acceptance of the presented titles (DIAGNOSTIC, not an assertion — "
          "green depends on slice 2): %r" % diag)
    for num, lab, accepte in diag:
        if not accepte:
            print("    PENDING (owner: slice 2 / arbitration card t_ca894fd4): %s no longer "
                  "accepts the title this document presents: %r" % (LINTER_REL, lab))
    print("    falsifiability (same judge, same call form): title removed -> %d "
          "problem(s); %r -> %r -> %d problem(s); reference form -> %d problem(s)"
          % (len(probs_a), cible, bare, len(probs_b), len(probs_pos)))


def test_limite_no_unaccented_french_prose_survives_calibrated_on_two_corpora():
    """Limit — the blind spot of a diacritic scan, made executable.

    This document carries 171 accented lines and 118 accent-free ones; French prose
    survives translation over several lines without losing one accent, and the scanner is
    structurally blind to it. Three things are measured in the SAME run:

    1. the detector is NON-VACUOUS on this subject: at the reference revision it flags a
       non-zero number of accent-free lines (measured: 12);
    2. the same detector flags ZERO such lines at HEAD, so the pair is red-able by the
       exact state this slice is meant to produce;
    3. a synthetic French line carrying no diacritic is caught by the same detector, so a
       zero at HEAD cannot be an empty rule.

    The threshold is calibrated over 1288 accent-free lines this pipeline already produced
    (the plate's `outside_corpus` plus the committed copies of the slices it declares
    `kind: translate`): 0 false positive at K = 2.
    """
    precondition_translated()
    ref, head = git_show(SLICE[0]), head_text(SLICE[0])

    vues = len([l for l in head.splitlines() if not any(c in ACCENTS for c in l)])
    assert vues > 0, "the slice carries no accent-free line: decor vide"
    ref_hits = offenders(ref, is_path=False)
    assert ref_hits, (
        "the lexical detector flags NOTHING on the reference revision either: the control "
        "is vacuous on this subject and its zero at HEAD proves nothing")

    temoin = "les cartes dans le worktree sont decoupees sans accents"
    toks = sorted({m.group(1).lower() for m in MOT_FR.finditer(temoin)})
    assert len(toks) >= SEUIL_LEXICAL, (
        "positive control FAILED: the detector no longer sees French prose at all (%d "
        "token(s) on %r) — the zero below is vacuous" % (len(toks), temoin))

    declare, deja = english_corpora()
    assert declare, ("the plate declares no already-English file (`outside_corpus`), so "
                     "the threshold of this control cannot be calibrated")
    absents = [r for r in declare + deja if not (REPO / r).is_file()]
    assert not absents, "calibration corpus cites files absent from the tree: %r" % absents
    n_lignes, faux = calibration_report(declare + deja)
    assert n_lignes >= 300, (
        "calibration corpus too small to prove anything (%d accent-free lines over %d "
        "file(s)): %r" % (n_lignes, len(declare + deja), declare + deja))
    assert not faux, (
        "the detector fires on prose these corpora are declared already English (%d false "
        "positive(s) over %d accent-free lines): the control is not discriminant\n  "
        % (len(faux), n_lignes)
        + "\n  ".join("%s:%d %s" % f[:3] for f in faux[:10]))

    ecarts = ["%s:%d  [%s]  %s" % (SLICE[0], n, ",".join(t), txt[:150])
              for n, t, txt in offenders(SLICE[0])]
    assert not ecarts, (
        "French prose WITHOUT any diacritic still survives in the slice (threshold K>=%d "
        "distinct French-only words per line, 0 false positive measured over the %d "
        "accent-free lines of the calibration corpora):\n  "
        % (SEUIL_LEXICAL, n_lignes) + "\n  ".join(ecarts))
    print("witness blind spot: référence %d ligne(s) sans accent signalée(s), tête 0 sur "
          "%d ligne(s) sans accent ; calibration %d ligne(s) sur %d fichier(s), 0 faux "
          "positif ; contrôle positif %r -> %r"
          % (len(ref_hits), vues, n_lignes, len(declare + deja), temoin, toks))


def test_limite_the_ledger_rule_bites_on_a_translated_slice(clone):
    """Limit: the plate's ledger rule BITES — executed on a clone, never asserted against
    the live tree.

    The slice-1 bench compares the ledger's per-file `lines` and `accented_lines` to the
    live tree, so a translation and its ledger entry belong to the same commit. This case
    does NOT require the live tree to be in sync — the ledger lives in slice 1's artifact
    and editing it is outside this slice's declared perimeter: it requires the RULE to be
    discriminating, and prints the live state so conv-11 arbitrates on a measurement.

    Both fields are flipped by the SAME run, by two mutations applied to the clone: an
    accented line and a plain line appended to the file.
    """
    rec = ledger_slice()
    print("witness planche: slice %d déclare %r" % (SLICE_K, rec.get("files")))
    live = sync_ecarts(REPO)
    print("witness arbre vivant: %d divergence(s) planche <-> arbre à l'instant de la "
          "mesure — %r (diagnostic, hors périmètre de cette carte)" % (len(live), live))

    rel = SLICE[0]
    f = clone["dir"] / rel
    avant = sha256(f)
    with f.open("a", encoding="utf-8") as fh:
        # The appended block carries BOTH axes: the first line carries a real diacritic
        # (it flips `accented_lines`), the second none (it flips `lines`). A mutation that
        # only appends accent-free text leaves the `accented_lines` field unexercised —
        # measured: the case then reports a harness defect, not a green gate.
        fh.write("\nLigne laissée en français, avec un accent.\n")
        fh.write("One more line, no diacritic at all.\n")
    apres = sha256(f)
    assert apres != avant, "mutation NOT applied on the clone: sha256 %s" % avant
    lignes = f.read_text(encoding="utf-8").splitlines()
    assert any(c in ACCENTS for c in lignes[-2]), (
        "the mutation does not carry the axis the ledger rule enforces: the appended "
        "accented line carries no diacritic (%r), so `accented_lines` cannot flip"
        % lignes[-2])
    print("witness mutation: %s sha256 %s -> %s (ligne accentuée + ligne sans accent)"
          % (rel, avant[:12], apres[:12]))

    ecarts = sync_ecarts(clone["dir"])
    assert ecarts, (
        "the ledger check did not fire on the mutated clone: it cannot fail, so it cannot "
        "be a gate")
    nommes = sorted({r for r, _, _, _ in ecarts})
    assert nommes == sorted(SLICE), (
        "the divergence must name the file of the slice; named: %r" % nommes)
    champs = {champ for _, champ, _, _ in ecarts}
    assert champs == {"lines", "accented_lines"}, (
        "both fields of the ledger must be exercised in the same run; exercised: %r\n%r"
        % (champs, ecarts))
    print("witness registre: %d divergence(s) nommée(s) sur le clone, champs %r — %r"
          % (len(ecarts), sorted(champs), ecarts))


def sync_ecarts(root):
    """[(rel, field, declared, measured)] — the plate's ledger against the tree it describes."""
    rec = ledger_slice()
    files = rec.get("files") or {}
    assert isinstance(files, dict), (
        "slice %d: `files` is not a path->numbers mapping in the ledger: %r"
        % (SLICE_K, files))
    ecarts = []
    for rel in SLICE:
        entry = files.get(rel)
        if not isinstance(entry, dict):
            ecarts.append((rel, "entry", "present", "absent"))
            continue
        lignes = (Path(root) / rel).read_text(encoding="utf-8").splitlines()
        for champ, mesure in (("lines", len(lignes)),
                              ("accented_lines", len(accented_lines(lignes)))):
            declare = entry.get(champ)
            if declare != mesure:
                ecarts.append((rel, champ, declare, mesure))
    return ecarts


# --------------------------------------------------------------------------- erreur


def test_erreur_a_forgotten_file_is_named_with_its_recomputed_lines(tmp_path):
    """Error: the file of the slice is left entirely French.

    The pair is measured in the SAME run: a throwaway repository where the slice path
    carries the EXACT French bytes of the reference revision sorts 1 and NAMES it, with
    the line numbers recomputed from those bytes; an English stub of the same decor sorts
    0 and silent. The neighbour of the slice is tracked beside it so a scan matching by
    suffix would be caught naming it too.
    """
    require_upstream()
    oublie = SLICE[0]
    francais = git_show(oublie)
    attendu = expected_violations(francais, frozen_literals())
    assert attendu, ("the reference revision of %s carries no violation: the decor would "
                     "measure nothing" % oublie)
    voisin = ENGLISH_STUB

    root = build_tree(tmp_path / "oublie", {oublie: francais, NEIGHBOUR_REL: voisin})
    assert sha256(root / oublie) == hashlib.sha256(
        francais.encode("utf-8")).hexdigest(), (
        "the forgotten file of the decor is not the reference revision's bytes")
    suivis = sorted(r for r in tracked(root) if r.endswith(".md"))
    assert suivis == sorted([oublie, NEIGHBOUR_REL]), (
        "the decor must track exactly the path of the slice and its neighbour: %r -> %r"
        % (sorted([oublie, NEIGHBOUR_REL]), suivis))

    q = scan(SLICE, cwd=root)
    assert q.returncode == 1, resume(
        q, "the file of the slice left entirely French: exit 1 expected")
    trouves = reported(out_of(q))
    noms = sorted({rel for rel, _, _ in trouves})
    assert noms == [oublie], (
        "the scan must name the forgotten file on its EXACT relative path and NOT its "
        "English neighbour; named: %r\n%s" % (noms, out_of(q)))
    lignes = sorted({n for rel, n, _ in trouves if rel == oublie})
    assert lignes == attendu, (
        "%s: the scan reported line(s) %r, this bank recomputes %r from the same bytes "
        "(%s)" % (oublie, lignes, attendu, REF_REF))

    propre = build_tree(tmp_path / "propre", {oublie: ENGLISH_STUB, NEIGHBOUR_REL: voisin})
    s = scan(SLICE, cwd=propre)
    assert s.returncode == 0, resume(s, "an English file of the same decor: exit 0")
    assert out_of(s).strip() == "", (
        "the English file must be silent:\n%r" % out_of(s))
    print("witness forgotten file: %s (bytes of %s) -> rc=1, %d line(s) named, %d "
          "recomputed, neighbour %s NOT named; English stub alone -> rc=0 silent"
          % (oublie, REF_REF, len(lignes), len(attendu), NEIGHBOUR_REL))


def test_erreur_the_whole_corpus_scan_names_the_forgotten_file_too(tmp_path):
    """Error, enumeration branch: the no-argument form must name the forgotten file too.

    Same decor, same bytes, one different code path (`git ls-files` over the whole
    corpus): a defect that only one of the two forms sees is a defect the gate reports
    inconsistently.
    """
    require_upstream()
    oublie = SLICE[0]
    root = build_tree(tmp_path / "corpus", {oublie: git_show(oublie),
                                            NEIGHBOUR_REL: ENGLISH_STUB})
    suivis = sorted(r for r in tracked(root) if r.endswith(".md"))
    assert suivis == sorted([oublie, NEIGHBOUR_REL]), (
        "the decor must track exactly the path of the slice and its neighbour: %r -> %r"
        % (sorted([oublie, NEIGHBOUR_REL]), suivis))

    q = scan((), cwd=root)
    assert q.returncode == 1, resume(
        q, "whole-corpus scan of a decor holding the French file: exit 1 expected")
    noms = named_exact(out_of(q))
    assert oublie in noms, (
        "the whole-corpus scan must NAME the forgotten file %s; it named %r\n%s"
        % (oublie, noms, out_of(q)))
    assert NEIGHBOUR_REL not in noms, (
        "the whole-corpus scan named the ENGLISH neighbour %s: the decor's discrimination "
        "is broken; named %r" % (NEIGHBOUR_REL, noms))
    print("witness whole corpus in the decor: rc=%d, named %r (tracked .md in the decor: "
          "%d)" % (q.returncode, noms, len(suivis)))
