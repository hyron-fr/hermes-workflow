"""Slice 10 (skill pj-pipeline) — language RED bank, card t_41c68068.

Subject of this card (the single document `dev-10` translates, card t_e0d5b2a1):

    skills/pj-pipeline/SKILL.md

The bank only MEASURES it: it never edits it (`tests/**` is this card's whole write
perimeter — `dev-10` owns the source in the same worktree).

Contract executed here (same form as the slice-2 bank and the sibling slice banks):

    python3 pipeline/pj_lang_lint.py [--exclusions F] [<path> ...]

- rc 0 = compliant AND silent (stdout and stderr both empty);
- rc 1 = at least one line carrying a diacritic outside a frozen span, each line
  naming `path:line`;
- rc 2 = usage error (never a violation, and vice versa).

What this bank proves, and what it does NOT
-------------------------------------------

The diacritic scan is NECESSARY but not SUFFICIENT. This slice's file carries 317
lines of which 181 are accented (measured at `origin/dev`, reproduced by the case
below and declared identically by the ratified plate's ledger), and French prose
survives translation without carrying a single diacritic. So the bank also carries
one LEXICAL control, calibrated by measurement (see
`test_limite_no_unaccented_french_prose...`): a word-bounded list of French-only
function words, threshold K = 2 distinct tokens per line, 0 false positives measured
over the 202 accent-free lines of the zone the RATIFIED plate itself declares already
English (`plate-ledger.outside_corpus`).

Low recall, stated: at K = 2 the control flags 6 of the accent-free lines of this
slice at the reference revision (printed file and line by the failure). It is a guard
against a half-translation, never a completeness proof; the diff review stays required
in `conv-10`.

The second subject of this slice is the CONTRACT ITSELF
-------------------------------------------------------

`skills/pj-pipeline/SKILL.md` is the skill that TEACHES the card format
(5 numbered sections + Gherkin) and the pipeline's machine vocabulary. Translating it
can therefore break two things the diacritic scan cannot see:

1. the format contract it teaches — a reworded section title is invisible to the scan
   if it carries no diacritic, yet the card linter reads those titles by regex;
2. the machine vocabulary it cites (kanban states, CLI flags, `slices.json` keys,
   cron expressions, the pipeline's own step names) — the readers live in
   `pipeline/`, `agents/*/scripts/` and `plugins/`.

Both are judged here, and the vocabulary is judged on its backticked CITATION with the
production file that reads each token printed as provenance — a bare English word that
happens to be a state name is prose, a backticked token is a citation of the contract.

Corrections to the card's own prose (measured, printed in the failure paths)
----------------------------------------------------------------------------

1. The card announces "317 l., 181 accentuées, 17 citations de littéraux gelés". The
   first two are reproduced EXACTLY (317 lines by `str.splitlines()` — 316 by `wc -l`,
   the two definitions are printed side by side — and 181 accented lines, equal to the
   ratified ledger). The third is NOT: the two DECLARED frozen literals are cited
   `Importé depuis` 0 times and `ROOM:` 1 time at the reference revision. A case
   demanding "17 citations of frozen literals" would be red forever, so the citation
   half is written as "count preserved reference -> HEAD" (0 == 0 and 1 == 1, both
   PRINTED as such) and the weight of the limit nature sits on the contract this slice
   really carries: the 77 backticked machine tokens with a proven production reader
   (91 citations measured at the reference revision).
2. The sister card `t_e0d5b2a1` (dev-10) announces in its limit scenario that the 5
   section titles of the card contract must stay "mot pour mot" through the
   translation, while this card's own guard-rails, the human decision of 2026-09-20 and
   the ratified plate's `gate_labels` all state the opposite: the section titles ARE
   translated (and `pj_lang_lint`'s exemptions are the two machine protocols and
   nothing else, so an accented French title cannot survive anyway). The bank does NOT
   arbitrate that: it judges the language-agnostic contract (all 5 sections still
   taught, in the FR or the EN form) and BANS the one form no reading accepts — the
   DE-ACCENTUATED French label (`Fonctionnalite:`), which is neither language, is
   invisible to the diacritic scan, and is refused by the linter's own regexes. The
   linter-acceptance status of each presented title is PRINTED as a diagnostic, not
   asserted, because its green depends on slice 2 (`pipeline/pj_card_lint.py`), which
   is not this slice's perimeter.
3. `[gate] ` — the gate comment prefix asserted by the sibling slice-7 bank — is cited
   ZERO times here (measured); this bank does not carry that assertion.

No real clock, no randomness: every fixture is a throwaway git repository built by this
bank from VERSIONED bytes (`git show origin/dev:<path>`), and every count is recomputed
from the bytes in hand rather than asserted as a copied literal.
"""
import hashlib
import importlib.util
import io
import json
import os
import re
import subprocess
import sys
import tokenize
import unicodedata
from pathlib import Path

import ast
import pytest
import yaml

REPO = Path(__file__).resolve().parents[1]

SLICE = ("skills/pj-pipeline/SKILL.md",)

TOOL_REL = "pipeline/pj_lang_lint.py"
EXCLUSIONS_REL = "pipeline/pj_lang_lint.exclusions.yaml"
PLATE_REL = "docs/architecture/context/issue-2-plate.html"
LINTER_REL = "pipeline/pj_card_lint.py"

TOOL = REPO / TOOL_REL
EXCLUSIONS = REPO / EXCLUSIONS_REL
PLATE = REPO / PLATE_REL
LINTER = REPO / LINTER_REL

SLICE_K = 10
# The pre-state of this slice: the branch's merge base against `origin/dev`, i.e. the
# bytes the translation starts from. Read through `git show`, never from a copy kept
# beside this bank, so the reference cannot drift with the tree under test.
REF_REF = "origin/dev"

# A neighbour of this slice that lives in the SAME directory and is the subject of
# another slice (9). It is the trap of the error decor: a bench matching by basename or
# by suffix imputes its state to this slice, and vice versa.
NEIGHBOUR_REL = "skills/pj-pipeline/references/graph-manifest.md"

# Character class of the contract, identical to the slice-1 bench, to the scanner and to
# the ratified plate's `character_class_chars`. Re-declared here on purpose: a bank that
# imported the class from the subject would widen with the subject. The nominal case
# asserts this literal equals the class the plate declares.
ACCENTS = "àâäçéèêëîïôöùûüÿœæñÀÂÄÇÉÈÊËÎÏÔÖÙÛÜŸŒÆÑ"

# The two and only frozen machine protocols. This slice cites `Importé depuis` 0 times and
# `ROOM:` 1 time (measured at the reference revision); the counts are ASSERTED as
# preserved, never as a non-zero literal, and both are printed.
PROTOCOLES = ("Importé depuis", "ROOM:")

# French-only function words: no English homograph. Same list and same threshold as the
# slice-5/slice-7 banks, RE-CALIBRATED here over this tree's already-English zone.
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
# A numbered bold list item: the shape this document uses to teach the 5 mandatory
# sections of a card body (`1. **Contexte & Objectif** — …`).
CONTRACT_ITEM_RE = re.compile(r"^\s*(\d)\.\s+\*\*(.+?)\*\*", re.M)

ENGLISH_STUB = (
    "# Neighbour document\n\nAlready English prose, without a single diacritic.\n"
    "No machine contract is cited here.\n"
)

_READERS = None


# --------------------------------------------------------------------------- tools


def _run(cmd, cwd=None, env=None):
    return subprocess.run(cmd, cwd=str(cwd) if cwd else None, capture_output=True,
                          text=True, timeout=300, env=env)


def git(*args, cwd=REPO):
    p = _run(["git", "-C", str(cwd), *args])
    assert p.returncode == 0, "git %s failed: %s" % (" ".join(args), p.stderr)
    return p.stdout


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def sha256_bytes(data):
    return hashlib.sha256(data.encode("utf-8") if isinstance(data, str) else data).hexdigest()


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
        "the reference revision is where this slice really is French, so the error "
        "fixtures must come from it" % (ref, rel, p.stderr))
    return p.stdout


def head_text(rel):
    f = REPO / rel
    assert f.is_file(), (
        "slice file absent from the tree: %s\n"
        "this bank is written BEFORE the translation (peer programming test || dev): "
        "that failure is the expected RED." % rel)
    return f.read_text(encoding="utf-8")


def flat(text):
    """The text with markdown line wraps collapsed.

    A cited literal can be split by a wrap (`Importé` / `depuis`) and the translation is
    allowed to re-wrap, so every COUNT below is taken on the flattened text; a
    line-by-line motif would be blind to exactly the citation it is looking for.
    """
    return re.sub(r"[ \t]*\n[ \t]*", " ", text)


def normalise(s):
    return re.sub(r"\s+", " ", s).strip()


def strip_accents(s):
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if unicodedata.category(c) != "Mn")


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


def code_view_py(text):
    """`text` with every COMMENT and DOCSTRING blanked out, line-based (offsets kept).

    Measured defect this exists to prevent: `` `<repo> #<N> · <titre>` `` was credited to
    `plugins/pj-buttons/pj-buttons/__init__.py:17`, a line of that file's DOCSTRING — the
    plugin's real regex is `([A-Za-z0-9._-]+)\\s*#(\\d+)` and reads no title at all. The
    simulated translation (nature B) translated `<titre>` into `<title>`, which is
    CORRECT, and the bank reported it as a damaged machine contract. 20 of the 77 credited
    tokens were in that state; only a CODE occurrence proves a reader.
    """
    lines = text.splitlines(keepends=True)

    def blank(idx):
        if 0 <= idx < len(lines):
            lines[idx] = re.sub(r"[^\n]", " ", lines[idx])

    try:
        tree = ast.parse(text)
    except SyntaxError:
        tree = None
    if tree is not None:
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                                     ast.ClassDef)):
                continue
            for st in (node.body or [])[:1]:
                if isinstance(st, ast.Expr) and isinstance(st.value, ast.Constant) \
                        and isinstance(st.value.value, str):
                    for ln in range(st.lineno - 1, (st.end_lineno or st.lineno)):
                        blank(ln)
    try:
        for tok in tokenize.generate_tokens(io.StringIO(text).readline):
            if tok.type == tokenize.COMMENT:
                r, c = tok.start
                lines[r - 1] = lines[r - 1][:c] + re.sub(r"[^\n]", " ", lines[r - 1][c:])
    except (tokenize.TokenError, IndentationError):
        pass
    return "".join(lines)


def code_view_sh(text):
    """`text` with full-line comments blanked (a shell comment starts its line)."""
    out = []
    for line in text.splitlines(keepends=True):
        out.append(re.sub(r"[^\n]", " ", line)
                   if line.lstrip().startswith("#") else line)
    return "".join(out)


def code_view(rel, text):
    return code_view_py(text) if rel.endswith(".py") else code_view_sh(text)


def production_readers():
    """Tracked executable files (`.py`/`.sh`) outside `tests/` and `docs/`, CODE view only.

    A backtick token of the slice is treated as a machine contract only when the CODE of
    one of these files carries it verbatim — never a comment, never a docstring: that is
    the falsifiable form of "this literal is frozen", and it is what keeps a correct
    translation from reddening on a token no program reads.
    """
    global _READERS
    if _READERS is None:
        out = {}
        for rel in tracked():
            if rel.split("/")[0] in ("tests", "docs") or rel in SLICE:
                continue
            if not rel.endswith((".py", ".sh")):
                continue
            try:
                raw = (REPO / rel).read_text(encoding="utf-8", errors="replace")
            except OSError:  # pragma: no cover - unreadable tracked file
                continue
            out[rel] = code_view(rel, raw)
        _READERS = out
    return _READERS


def proven_reader(span):
    """(file, line) of the first tracked production file carrying `span`, else (None, None)."""
    for rel, txt in sorted(production_readers().items()):
        i = txt.find(span)
        if i >= 0:
            return rel, txt[:i].count("\n") + 1
    return None, None


def gate_labels():
    """The plate's `gate_labels.translated` — the FR/EN pairs read by the card linter."""
    raw = ledger().get("gate_labels") or {}
    pairs = raw.get("translated") or []
    assert pairs, "the ratified plate declares no translated gate label"
    return [{"fr": p.get("fr"), "en": p.get("en"), "read_by": p.get("read_by")}
            for p in pairs if p.get("fr") and p.get("en")]


def translated_fr_labels():
    """The FR forms the human decision of 2026-09-20 turns into English.

    They are EXCLUDED from the machine vocabulary: their citation count is expected to
    fall (the accented ones cannot even survive the scan), so pinning them as "count
    preserved" would red a correct translation forever. That is the one exclusion of
    this bank, and it is derived from the ratified plate, not chosen.
    """
    return {p["fr"] for p in gate_labels() if p["fr"] != p["en"]}


def machine_vocabulary():
    """{span: 'reader:line'} for the backticked code tokens of the slice with PROVENANCE.

    Only tokens written INSIDE a backtick span are collected: `` `ready` `` is a citation
    of a machine state, while the bare English word "ready" is prose a translation may add
    or remove at will. Counting the bare word would red a correct translation.
    """
    skip = translated_fr_labels()
    vocab, excl = {}, {}
    for rel in SLICE:
        for span in SPAN_RE.findall(git_show(rel)):
            span = span.strip()
            if not span or span in vocab or span in excl:
                continue
            r, n = proven_reader(span)
            if not r:
                continue
            if span in skip:
                excl[span] = "%s:%d" % (r, n)
                continue
            vocab[span] = "%s:%d" % (r, n)
    return vocab, excl


def cited_span(span):
    """The backticked citation of `span` — the form a document writes to reference it."""
    return "`%s`" % span


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

    Two files of this directory are named `SKILL.md` / `graph-manifest.md` elsewhere in
    the corpus, so a suffix test would impute a neighbour's violation to this slice.
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
    p = _run(["git", "init", "-q"], cwd=root)
    assert p.returncode == 0, "git init failed: %s" % p.stderr
    for rel, txt in files.items():
        cible = root / rel
        cible.parent.mkdir(parents=True, exist_ok=True)
        cible.write_text(txt, encoding="utf-8")
    p = _run(["git", "add", "--", *files], cwd=root)
    assert p.returncode == 0, "git add failed: %s" % p.stderr
    return root


def precondition_translated(literals=None):
    """Nominal/limit precondition: the slice IS translated — the expected RED otherwise.

    The failure NAMES the file and the line of every remaining accented line outside a
    frozen span, so the RED is actionable rather than a boolean.
    """
    require_upstream()
    lits = literals if literals is not None else frozen_literals()
    absents = [rel for rel in SLICE
               if not (REPO / rel).is_file() or rel not in tracked()]
    if absents:
        pytest.fail("slice file(s) absent from the disk or the index: %s"
                    % ", ".join(absents))

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
            "slice 10 NOT translated: %d accented line(s), of which %d outside a frozen "
            "span.\n  - %s\n(this bank is written BEFORE the translation: this failure "
            "IS the expected RED)"
            % (total, len(restes), "\n  - ".join(restes[:8])))


def skeleton(text):
    """The document's SKELETON: what a translation must not rewrite, only reword.

    `version` is deliberately NOT part of the judged set: bumping a skill's version is a
    legitimate editorial act, and judging it would red a correct translation.
    """
    fm = None
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if m:
        fm = yaml.safe_load(m.group(1)) or {}
    lines = text.splitlines()
    return {
        "frontmatter_keys": sorted(fm) if isinstance(fm, dict) else None,
        "name": fm.get("name") if isinstance(fm, dict) else None,
        "headings": sum(1 for l in lines if HEADING_RE.match(l)),
        "fence_delimiters": sum(1 for l in lines if FENCE_RE.match(l)),
        "table_separators": sum(1 for l in lines if TABLE_SEP_RE.match(l)),
    }


def skeleton_problems(rel, ref, head):
    s_ref, s_head = skeleton(ref), skeleton(head)
    return ["%s: %s %r -> %r (a translation reworks the prose, it does not restructure "
            "the document)" % (rel, champ, s_ref[champ], s_head[champ])
            for champ in sorted(s_ref) if s_ref[champ] != s_head[champ]]


def ledger():
    if not PLATE.is_file():
        pytest.fail("ratified plate absent: %s" % PLATE)
    m = LEDGER_RE.search(PLATE.read_text(encoding="utf-8"))
    assert m, "no `plate-ledger` machine block in %s" % PLATE_REL
    try:
        return json.loads(m.group("json"))
    except json.JSONDecodeError as exc:
        pytest.fail("plate-ledger unreadable (%s)" % exc)


def ledger_slice(k):
    raw = ledger().get("slices")
    assert raw, "the plate ledger carries no `slices` entry"
    recs = raw if isinstance(raw, dict) else {r.get("k"): r for r in raw}
    rec = recs.get(k) or (recs.get(str(k)) if isinstance(recs, dict) else None)
    assert rec, "slice %d absent from the plate ledger" % k
    return rec


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


# --------------------------------------------------- the card-format contract taught here


def contract_items(text):
    """[(number, title)] — the 5 numbered bold items teaching the card format."""
    return [(int(m.group(1)), normalise(m.group(2))) for m in CONTRACT_ITEM_RE.finditer(text)]


def presented_forms(text):
    """Every unit the document presents as part of the contract: numbered items + backticked tokens."""
    units = [("item %d" % n, t) for n, t in contract_items(text)]
    units += [("token", s.strip()) for s in SPAN_RE.findall(text) if s.strip()]
    return units


def sep_key(s):
    """Comparison key of a label: whitespace collapsed, and spaces around `/` and `:`
    removed.

    The reference revision writes `Étant donné/Quand/Alors` where the plate declares
    `Étant donné / Quand / Alors`, and `Fonctionnalite :` where it declares
    `Fonctionnalité:`: a character-for-character comparison reports both labels as dropped
    and reds a document that teaches them. The separator is not part of the contract, the
    tokens are.
    """
    s = re.sub(r"\s*/\s*", "/", normalise(s))
    return re.sub(r"\s*:\s*", ":", s).lower()


def labels_taught_at_ref():
    """The gate labels the REFERENCE REVISION really teaches (FR or EN form).

    Deliberately derived from the versioned pre-state, never from the document under test:
    measured at `origin/dev`, this document teaches 8 of the plate's 9 labels
    (`Contexte & Objectif`, `Critères d'acceptation`, `DoR & DoD`, `Considérations
    techniques`, `Hors-scope`, `Fonctionnalité:`, `Scénario:`, `Étant donné/Quand/Alors`).
    `jamais / ne pas` is a DETECTION vocabulary token, taught by no version of this
    document: demanding it at HEAD would red a correct translation forever.
    """
    ref = sep_key(flat("\n".join(git_show(rel) for rel in SLICE)))
    out = []
    for p in gate_labels():
        forms = {sep_key(p["fr"]), sep_key(p["en"])}
        if any(f and f in ref for f in forms):
            out.append(p)
    assert out, (
        "the reference revision teaches NONE of the plate's gate labels: this case has "
        "lost its subject")
    return out


def label_problems(text):
    """Discrepancies of the taught contract against the labels the pre-state teaches.

    Two families, both measured on the document itself:

    1. MISSING — a label taught by the reference revision is taught NOWHERE in the
       document (prose, numbered item or backticked span): the translation dropped the
       contract it exists to describe. Accepted in the FR or the EN form — the LANGUAGE is
       deliberately not judged here (see correction 2 of the module docstring).
    2. DE-ACCENTUATED FRENCH — the accent-stripped French form of a label appears in the
       document while NEITHER the French nor the translated form appears anywhere in it:
       `Fonctionnalite:` is neither language, is invisible to the diacritic scan, and
       matches no branch of the card linter. Naming the line makes the red actionable.
    """
    flat_txt = flat(text)
    key = sep_key(flat_txt)
    problems, seen = [], []

    for pair in labels_taught_at_ref():
        fr_k, en_k = sep_key(pair["fr"]), sep_key(pair["en"])
        forme = fr_k if fr_k and fr_k in key else (en_k if en_k and en_k in key else None)
        if forme is None:
            problems.append(
                "MISSING: gate label %r / %r (read by %s) is taught by no unit of the "
                "document — the translation dropped part of the card-format contract it "
                "describes" % (pair["fr"], pair["en"], pair["read_by"]))
        else:
            seen.append((pair["fr"], pair["en"] if forme == en_k else "<FR form>"))

    for pair in labels_taught_at_ref():
        fr, en = normalise(pair["fr"]), normalise(pair["en"])
        if fr == en or not any(c in ACCENTS for c in fr):
            continue  # a label with no diacritic has no de-accentuated variant to ban
        if sep_key(fr) in key or sep_key(en) in key:
            continue  # the correct form is taught somewhere: nothing is de-accentuated
        bare = sep_key(strip_accents(fr))
        if not bare or bare not in key:
            continue
        for num, line in enumerate(text.splitlines(), 1):
            if bare in sep_key(line):
                problems.append(
                    "DE-ACCENTUATED FRENCH (%s:%d): %r is neither the French label %r nor "
                    "its translated form %r — it is the French label with its diacritics "
                    "removed, which the language scan cannot see and the card linter "
                    "refuses (no regex branch matches it)"
                    % (SLICE[0], num, line.strip()[:90], pair["fr"], pair["en"]))
                break
            if bare in sep_key(flat(text)):
                problems.append(
                    "DE-ACCENTUATED FRENCH: %r is neither the French label %r nor its "
                    "translated form %r — it is the French label with its diacritics "
                    "removed (markdown wrap splits it across lines)" % (bare, fr, en))
                break
    return problems, seen


def labels_present_in_english(text):
    """The judged labels whose ENGLISH form the document already presents anywhere.

    The de-accentuated family is exercised on one of THESE: before the translation the
    list is empty, and that emptiness IS the RED of this case — a mutation replacing an
    English label cannot be applied to a document that presents none.
    """
    key = sep_key(flat(text))
    out = []
    for p in labels_taught_at_ref():
        if p["fr"] == p["en"] or not any(c in ACCENTS for c in p["fr"]):
            continue  # no de-accentuated variant to ban
        en = sep_key(p["en"])
        if en and en in key:
            out.append(p)
    return out


def linter_section_patterns():
    """The card linter's own section regexes, loaded by path (the repo's idiom)."""
    assert LINTER.is_file(), "card linter absent: %s" % LINTER_REL
    spec = importlib.util.spec_from_file_location("pj_card_lint_slice10", str(LINTER))
    assert spec is not None and spec.loader is not None, (
        "cannot load %s by path: the acceptance diagnostic of this slice has lost its "
        "subject" % LINTER_REL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    patterns = getattr(mod, "SECTION_PATTERNS", None)
    assert patterns and len(patterns) >= 5, (
        "%s exposes %r section pattern(s): the acceptance diagnostic of this slice has "
        "lost its subject" % (LINTER_REL, patterns and len(patterns)))
    return patterns


# -------------------------------------------------------------------------- nominal


def test_nominal_the_scan_is_exit_0_and_silent_on_the_slice_file():
    """Nominal: rc 0 and silent on the translated document.

    `rc == 0` and the silence are the two halves of the contract: a scan printing a
    report while returning 0 is not compliant with it.
    """
    precondition_translated()
    p = scan(SLICE)
    assert p.returncode == 0, resume(
        p, "scan of the translated document: exit 0 expected")
    assert out_of(p).strip() == "", (
        "a compliant corpus must be SILENT (stdout AND stderr empty); obtained:\n%r"
        % out_of(p))
    print("witness nominal: %s -> rc=0, silent" % SLICE[0])


def test_nominal_the_whole_corpus_scan_does_not_name_the_slice_file():
    """Nominal, enumeration branch: the no-argument form takes another code path
    (`git ls-files` over the whole corpus) and must not name this file.

    The assertion is on the NAMES, not on rc: while the rest of the corpus is still
    French the whole-tree scan legitimately returns 1, and the slice's own contribution
    is what this case isolates. Exact relative paths only.
    """
    precondition_translated()
    p = scan()
    noms = set(named_exact(out_of(p)))
    fautifs = sorted(noms & set(SLICE))
    assert not fautifs, (
        "the whole-tree scan still NAMES the file of this slice: %r\n%s"
        % (fautifs, out_of(p)))
    print("witness whole corpus: %d tracked .md, %d violation(s) elsewhere, 0 on the slice"
          % (len([r for r in tracked() if r.endswith(".md")]), len(noms)))


def test_nominal_the_perimeter_the_ledger_and_the_skeleton_are_the_ratified_ones():
    """Nominal: the perimeter and the character class are the RATIFIED ones, the
    per-file numbers the plate declares are REPRODUCED from the reference revision, and
    the document SKELETON survives the translation.

    Three independent sources are closed against each other here: the plan's ledger
    (paths and line counts), the plate's declared character class, and the tree. The two
    line-count definitions (`str.splitlines()` vs `wc -l`) are printed side by side — the
    ledger is written in the first one, and a count without its definition is not a
    measurement.
    """
    rec = ledger_slice(SLICE_K)
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

    ecarts, mesures = [], []
    for rel in SLICE:
        entry = files.get(rel) if isinstance(files, dict) else None
        ref = git_show(rel)
        n_ref = len(ref.splitlines())
        n_wc = len(ref.split("\n")) - (1 if ref.endswith("\n") else 0)
        acc_ref = len(expected_violations(ref, ()))
        mesures.append((rel, n_ref, n_wc, acc_ref))
        if not isinstance(entry, dict):
            ecarts.append("%s: no per-file numbers in the ledger" % rel)
        else:
            if entry.get("lines") != n_ref:
                ecarts.append("%s: ledger declares %r lines, the reference revision has "
                              "%d by splitlines (%d by wc -l)"
                              % (rel, entry.get("lines"), n_ref, n_wc))
            if entry.get("accented_lines") != acc_ref:
                ecarts.append("%s: ledger declares %r accented lines, the reference "
                              "revision has %d" % (rel, entry.get("accented_lines"), acc_ref))
        ecarts += skeleton_problems(rel, ref, head_text(rel))
    assert not ecarts, ("perimeter/skeleton in discrepancy:\n  " + "\n  ".join(ecarts))
    print("witness perimeter: slice %d = %r, character class %r, "
          "rel/lines(splitlines)/lines(wc-l)/accented %r"
          % (SLICE_K, declare, classe, mesures))


# --------------------------------------------------------------------------- limite


def test_limite_the_declared_frozen_literals_are_the_two_protocols_and_stay_verbatim():
    """Limit: the exemption file is not widened, and every declared frozen literal keeps
    its exact number of occurrences reference -> HEAD, counted on FLATTENED text.

    Measured at the reference revision: this slice cites `Importé depuis` 0 times and
    `ROOM:` 1 time — the 0 == 0 is PRINTED as such, so it is never mistaken for the pass
    of something else. The weight of this case is the non-widening plus the machine
    vocabulary of the next case. What this case forbids is the bypass: blanching French
    that is still in the corpus.
    """
    precondition_translated()
    lits, _ = declared_exclusions()
    assert sorted(lits) == sorted(PROTOCOLES), (
        "the exemption file declares %r; EXACTLY %r is expected — widening the exemptions "
        "is the bypass this case refuses (a translation does not blanch the French that "
        "is left)" % (sorted(lits), sorted(PROTOCOLES)))

    ecarts, vus = [], []
    for lit in lits:
        n_ref = sum(flat(git_show(rel)).count(lit) for rel in SLICE)
        n_head = sum(flat(head_text(rel)).count(lit) for rel in SLICE)
        vus.append((lit, n_ref, n_head))
        if n_ref != n_head:
            ecarts.append("frozen literal %r: %d occurrence(s) at %s -> %d at HEAD "
                          "(the reader of that literal goes silent, with no error)"
                          % (lit, n_ref, REF_REF, n_head))
        # case is part of "verbatim": `Room:` keeps the exact-form count intact
        ci_ref = sum(flat(git_show(rel)).lower().count(lit.lower()) for rel in SLICE)
        ci_head = sum(flat(head_text(rel)).lower().count(lit.lower()) for rel in SLICE)
        if ci_ref != ci_head:
            ecarts.append("a CASE VARIANT of %r was introduced: %d case-insensitive "
                          "occurrence(s) -> %d" % (lit, ci_ref, ci_head))
    assert not ecarts, ("the frozen literals of this slice are not preserved:\n  - "
                        + "\n  - ".join(ecarts))
    print("witness frozen literals: declared %r, (literal, ref, HEAD) = %r" % (lits, vus))


def test_limite_the_machine_vocabulary_cited_by_the_slice_is_preserved_with_provenance():
    """Limit — the contract this slice really carries: the code tokens it teaches.

    Every backtick token of the slice whose reader is a TRACKED PRODUCTION file
    (`pipeline/`, `agents/*/scripts/`, `plugins/`) must keep the same number of
    occurrences reference -> HEAD, counted on FLATTENED text. A token with no reader is
    prose and is deliberately NOT judged; the vocabulary and its provenance are printed,
    so a red is diagnosable.

    The FR gate labels of the plate are EXCLUDED by construction (`translated_fr_labels`)
    and printed as such: their count is expected to fall, and pinning them here would red
    a correct translation. Falsifiability is EXECUTED in the same run: a copy of the
    document with one cited token renamed must red the very function that judges it.
    """
    precondition_translated()
    ref_all = flat("\n".join(git_show(rel) for rel in SLICE))
    head_all = flat("\n".join(head_text(rel) for rel in SLICE))

    vocab, excl = machine_vocabulary()
    assert len(vocab) >= 10, (
        "only %d machine token(s) of this slice have a proven reader in the tree: the "
        "provenance scan is broken, or the tokens moved — %r" % (len(vocab), vocab))
    assert excl, (
        "no translated gate label survived into the exclusion set: the vocabulary would "
        "pin a French token the human decision turns into English, and red a correct "
        "translation forever. Exclusion set: %r" % excl)

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
    print("witness machine vocabulary: %d token(s) with provenance -> 0 discrepancy; "
          "%d token(s) excluded as translated gate labels (%r); mutation renames %s "
          "(%d citation(s) -> %d)"
          % (len(vocab), len(excl), sorted(excl), cite, ref_all.count(cite),
             mutant.count(cite)))
    for span, prov in sorted(vocab.items()):
        print("    %-45r x%d <- %s" % (span[:45], ref_all.count(cited_span(span)), prov))


def test_limite_the_card_format_contract_is_still_taught_and_no_deaccented_french_label():
    """Limit — the contract this document EXISTS to teach, judged on its own text.

    `skills/pj-pipeline/SKILL.md` is the skill that defines the 5 mandatory sections of a
    card body and its machine vocabulary. Translating it can break that contract
    invisibly: a reworded section title carries no diacritic, and a DE-ACCENTUATED French
    label (`Fonctionnalite:`) is neither language and matches no branch of the card
    linter.

    GREEN at the reference revision, and it must stay green after the translation: this is
    a NON-REGRESSION guard, not the RED of the bank (the six scan-based cases above carry
    the RED). It judges the language-AGNOSTIC contract — every gate label the pre-state
    teaches is still taught by some unit, in the FR or the EN form — precisely so that it
    reds under NO honest translation: the sister dev card and this card's guard-rails
    disagree on whether the 5 titles are translated by slice 2, and arbitrating that is
    not a test's job. The one form no reading admits is banned outright.

    Both directions of the judge are EXECUTED in the same run: dropping a taught title
    must red it, and replacing a presented form with the accent-stripped French label must
    red it — with a positive control showing the ACCENTED French label (which the card
    linter still reads) stays green wherever it is presented. The linter-acceptance status
    of each presented title is PRINTED, never asserted: its green depends on slice 2
    (`pipeline/pj_card_lint.py`), outside this slice's perimeter.
    """
    require_upstream()
    head = head_text(SLICE[0])
    problems, seen = label_problems(head)
    assert not problems, (
        "the card-format contract taught by %s does not survive the translation:\n  - "
        % SLICE[0] + "\n  - ".join(problems))

    items = contract_items(head)
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
    pairs = [p for p in labels_taught_at_ref()
             if p["fr"] != p["en"] and any(c in ACCENTS for c in p["fr"])]
    assert pairs, "no accented translated gate label in the judged set: nothing to ban"
    present_en = {p["fr"] for p in labels_present_in_english(head)}
    pair = next((p for p in pairs if p["fr"] in present_en), pairs[0])
    fr, en = normalise(pair["fr"]), normalise(pair["en"])
    bare = normalise(strip_accents(pair["fr"]))
    cible = en if fr in present_en else fr
    mutant_b = head.replace(cible, bare, 1)
    assert mutant_b != head, (
        "mutation B not applied: neither %r nor %r is presented verbatim by the document"
        % (fr, en))
    probs_b, _ = label_problems(mutant_b)
    assert probs_b, (
        "mutation B (%r -> %r) left the judge GREEN: nothing here would catch a "
        "de-accentuated French label, which is invisible to the language scan"
        % (cible, bare))

    # positive control, same judge and same call form: the ACCENTED French label stays
    # accepted (the card linter still reads it — refusing it would red a verbatim reading)
    probs_pos, _ = label_problems(head)
    assert not probs_pos, ("positive control FAILED: the judge reds the document in its "
                           "reference form: %r" % probs_pos)

    # diagnostic only: does the card linter accept the titles the document presents?
    patterns = linter_section_patterns()
    diag = []
    for num, lab in [i for i in items if i[0] <= 5]:
        accepte = []
        for nom, rx in patterns:
            if rx.search("# %s" % lab):
                accepte.append(nom)
        diag.append((num, lab, accepte))
    print("witness taught contract: %d numbered section(s), %d unit(s); plate labels "
          "taught (FR or EN): %r" % (len(items), len(presented_forms(head)), seen))
    print("    English forms ALREADY taught at the reference revision: %d (the slice's "
          "translation job on this contract is real)" % len(present_en))
    print("    linter acceptance of the presented titles (DIAGNOSTIC, not an assertion — "
          "green depends on slice 2): %r" % diag)
    for num, lab, accepte in diag:
        if not accepte:
            print("    PENDING (owner: slice 2 / arbitration card t_ca894fd4): %s no longer "
                  "accepts the title this document presents: %r" % (LINTER_REL, lab))
    print("    falsifiability (same judge, same call form): title removed -> %d "
          "problem(s); %r -> %r -> %d problem(s); reference form -> %d problem(s)"
          % (len(probs_a), cible, bare, len(probs_b), len(probs_pos)))


def test_limite_no_unaccented_french_prose_survives_calibrated_on_the_plate_english_zone():
    """Limit — the blind spot of a diacritic scan, made executable.

    This document carries 181 accented lines and, at the reference revision, 136
    accent-free ones; French prose can survive translation over several lines without
    losing one accent, and the scanner is structurally blind to it. Two things are
    measured in the same run:

    1. the detector is CALIBRATED here: it flags NONE of the accent-free lines of the
       files the ratified plate declares already English (`plate-ledger.outside_corpus`) —
       a threshold that fires on real English would be a false-positive machine;
    2. the slice flags ZERO such lines at HEAD; the offending lines are printed by the
       failure, file and line.
    """
    precondition_translated()

    zone = [e.get("path") for e in (ledger().get("outside_corpus") or []) if e.get("path")]
    assert zone, ("the plate declares no already-English file (`outside_corpus`): the "
                  "threshold of this control cannot be calibrated")
    absents = [rel for rel in zone if not (REPO / rel).is_file()]
    assert not absents, "calibration zone cites files absent from the tree: %r" % absents
    n_lignes, n_skip = 0, 0
    faux = []
    for rel in zone:
        text = (REPO / rel).read_text(encoding="utf-8")
        n_lignes += len([l for l in text.splitlines() if not any(c in ACCENTS for c in l)])
        faux += [(rel, n, t) for n, _, t in offenders(text, is_path=False)]
    assert n_lignes >= 30, (
        "calibration zone too small to prove anything (%d accent-free lines over %d "
        "files): %r" % (n_lignes, len(zone), zone))
    assert not faux, (
        "the detector fires on prose the plate declares already English (%d false "
        "positive(s) over %d accent-free lines): the control is not discriminant\n  "
        % (len(faux), n_lignes) + "\n  ".join("%s:%d %s" % f for f in faux[:10]))

    # positive control, same detector: a French line WITHOUT any diacritic must be caught
    temoin = "les cartes dans le worktree sont decoupees sans accents"
    toks = sorted({m.group(1).lower() for m in MOT_FR.finditer(temoin)})
    assert len(toks) >= SEUIL_LEXICAL, (
        "positive control FAILED: the detector no longer sees French prose at all (%d "
        "token(s) on %r) — the zero above is vacuous" % (len(toks), temoin))

    ecarts = []
    for rel in SLICE:
        for n, tks, txt in offenders(rel):
            ecarts.append("%s:%d  [%s]  %s" % (rel, n, ",".join(tks), txt[:150]))
    assert not ecarts, (
        "French prose WITHOUT any diacritic still survives in the slice (threshold K>=%d "
        "distinct French-only words per line, 0 false positive measured over the %d "
        "accent-free lines of the plate's already-English zone):\n  "
        % (SEUIL_LEXICAL, n_lignes) + "\n  ".join(ecarts))
    print("witness blind spot: calibration zone %r = %d accent-free lines, 0 false "
          "positive; positive control %r -> %r; slice 10 flags %d"
          % (zone, n_lignes, temoin, toks, len(ecarts)))


# --------------------------------------------------------------------------- erreur


def test_erreur_a_forgotten_file_is_named_with_its_recomputed_lines(tmp_path):
    """Error: the file of the slice is left entirely French.

    The decor is built FIRST and judged in this run, so the error machinery is executed
    even while the slice is still French. It tracks the slice path (holding the EXACT
    French bytes of the reference revision) plus ONE English neighbour of the same
    directory, and asserts the scan names the slice path and NOT the neighbour — the
    exact-relative-path discipline: a bench matching by basename would impute the
    neighbour's state to this slice. The positive half (the live translated file sorts 0)
    closes the pair.
    """
    oublie = SLICE[0]
    francais = git_show(oublie)
    literals = frozen_literals()
    attendu = expected_violations(francais, literals)
    assert attendu, ("the reference revision of %s carries no violation: the decor would "
                     "measure nothing" % oublie)

    fichiers = {oublie: francais, NEIGHBOUR_REL: ENGLISH_STUB}
    root = build_tree(tmp_path / "oublie", fichiers)
    assert sha256(root / oublie) == sha256_bytes(francais), (
        "the forgotten file of the decor is not the reference revision's bytes")
    assert sha256(root / NEIGHBOUR_REL) == sha256_bytes(ENGLISH_STUB), (
        "the neighbour of the decor is not the English stub")
    suivis = [r for r in tracked(root) if r.endswith(".md")]
    assert sorted(suivis) == sorted(fichiers), (
        "the decor must track exactly the two paths written into it: %r -> %r"
        % (sorted(fichiers), sorted(suivis)))

    q = scan([oublie], cwd=root)
    assert q.returncode == 1, resume(
        q, "the slice file left entirely French: exit 1 expected")
    trouves = reported(out_of(q))
    noms = sorted({rel for rel, _, _ in trouves})
    assert noms == [oublie], (
        "only the forgotten file must produce a violation, compared on the EXACT relative "
        "path (the English neighbour %s must stay unnamed); named: %r\n%s"
        % (NEIGHBOUR_REL, noms, out_of(q)))
    lignes = sorted({n for rel, n, _ in trouves if rel == oublie})
    assert lignes == attendu, (
        "%s: the scan reported line(s) %r, this bank recomputes %r from the same bytes "
        "(%s)" % (oublie, lignes, attendu, REF_REF))

    # discrimination of the same call, file by file: the English neighbour sorts 0
    s = scan([NEIGHBOUR_REL], cwd=root)
    assert s.returncode == 0, resume(s, "the English neighbour of the same decor: exit 0")
    assert out_of(s).strip() == "", (
        "the translated neighbour must be silent:\n%r" % out_of(s))
    print("witness forgotten file: %s (bytes of %s) -> rc=1, %d line(s) named, %d "
          "recomputed; neighbour %s alone -> rc=0 silent"
          % (oublie, REF_REF, len(lignes), len(attendu), NEIGHBOUR_REL))

    # positive half: the live file is translated
    precondition_translated()
    p = scan(SLICE)
    assert p.returncode == 0, resume(
        p, "positive half of the pair: the translated slice must sort 0")


def test_erreur_the_whole_corpus_scan_names_the_forgotten_file(tmp_path):
    """Error, enumeration branch: the no-argument form must name the forgotten file too.

    Same decor, same bytes, one different code path (`git ls-files` over the whole
    corpus): a defect that only one of the two forms sees is a defect the gate reports
    inconsistently.
    """
    oublie = SLICE[0]
    fichiers = {oublie: git_show(oublie), NEIGHBOUR_REL: ENGLISH_STUB}
    root = build_tree(tmp_path / "corpus", fichiers)

    q = scan((), cwd=root)
    assert q.returncode == 1, resume(
        q, "whole-corpus scan of a decor holding one French file: exit 1 expected")
    noms = named_exact(out_of(q))
    assert oublie in noms, (
        "the whole-corpus scan must NAME the forgotten file %s; it named %r\n%s"
        % (oublie, noms, out_of(q)))
    autres = [rel for rel in fichiers if rel != oublie and rel in noms]
    assert not autres, (
        "the English neighbour of the same decor must not be named: %r\n%s"
        % (autres, out_of(q)))
    assert len([r for r in tracked(root) if r.endswith(".md")]) == len(fichiers), (
        "the decor must track exactly the two paths written into it")
    print("witness whole corpus in the decor: rc=%d, named %r (tracked .md in the decor: "
          "%d)" % (q.returncode, noms, len(fichiers)))

    precondition_translated()
