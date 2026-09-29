"""Slice 8 (skill orchestration) — language RED bank, card t_7dcd13d5.

Subject of this card: `skills/hermes-multi-agent-orchestration/SKILL.md`
(542 lines, 360 accented lines at `origin/dev`) — the ONE document `dev-8`
translates (card t_c6f019d8). The bank never edits it: `tests/**` is this
card's whole write perimeter, and `dev-8` owns the source in the same worktree
(peer programming test || dev, same branch `wt/issue-2-rewrite-in-english`).

Contract executed here (same form as the slice-2 bank and the sibling banks of
this issue):

    python3 pipeline/pj_lang_lint.py [--exclusions F] [<path> ...]

- rc 0 = compliant AND silent (stdout and stderr both empty);
- rc 1 = at least one line carrying a diacritic outside a frozen span, each line
  naming `path:line`;
- rc 2 = usage error (reserved for source facts, never for a violation).

What this bank proves, and what it does NOT
-------------------------------------------

The diacritic scan is NECESSARY but not SUFFICIENT. This slice carries 542 lines
of which 360 are accented at the reference revision, so **182 lines carry no
diacritic at all** — and French prose survives translation without losing an
accent. Measured at `origin/dev`, the bank's lexical detector flags 19 of those
182 lines (threshold K = 2 distinct French-only words per line); at the
translated tip it flags 0. That pair is EXECUTED in the same run
(`test_limite_aucune_prose...`), so the control is neither vacuous nor a
false-positive machine.

The detector is calibrated over 521 accent-free lines this pipeline itself
produced: the ratified plate's `outside_corpus` (202 lines) plus every slice the
plate declares `kind: translate` whose COMMITTED copy (HEAD) now carries zero
accented line (slice 3: README.md + CONTRIBUTING.md +
workflows/templates/ticket.md, 319 lines). Measured: 0 false positive at K = 2,
and 2 at K = 1 (printed as a diagnostic, not asserted: those two lines QUOTE
French and a later slice could clean them).

Low recall, stated: at K = 2 the control saw 19 of the 182 accent-free lines of
this slice at `origin/dev`. It is a guard against the worst half-translations,
never a completeness proof; the diff review stays required in `conv-8`.

Measured corrections to the card's own prose
--------------------------------------------

1. The card announces "9 citations de littéraux gelés". Measured at
   `origin/dev`: `Importé depuis` is cited **0 times** (0 == 0, printed as such)
   and `ROOM:` **once** (line 326, inside the span ``ROOM: <room_id>``), i.e.
   **1 citation**, not 9. The figure 9 is the plate's `gate_labels.translated`
   list — 9 gate LABELS that slice 2 TRANSLATES by human decision of 2026-09-20
   — so counting them as frozen citations would red a correct translation, and
   freezing them would contradict the ratified decision. The limit case
   therefore (a) requires the exemption list to stay EXACTLY the 2 protocols,
   (b) requires each literal's occurrence count to survive reference -> HEAD,
   and (c) puts its real weight on the machine vocabulary whose reader is a
   TRACKED production file (111 tokens, each with provenance), plus the
   `[gate]` marker re-read by `pipeline/gate_hook.py`.
2. The card announces "542 lignes, 360 accentuées" — reproduced exactly, and the
   ratified plate's ledger declares the same two numbers with the same file path.

Trap measured on this slice: a backticked span is NOT a contract by itself
-----------------------------------------------------------------------------

The translation RENAMES 14 bracketed placeholder spans, and that is CORRECT
editing, not a defect: `--parent <synthèse>` -> `--parent <summary>`,
`<chemin>` -> `<path>`, `<branche>` -> `<branch>`, `PROFIL:TITRE` ->
`PROFILE:TITLE`, `providers.<nom>.default_model` -> `providers.<name>....`.
A rule of the form "every backticked token is a frozen literal" would red this
correct translation for 14 reasons. The bank therefore judges a span only when
a TRACKED production file (`.py`/`.sh`, outside `tests/` and `docs/`) carries it
verbatim — the falsifiable form of "this literal is frozen" — and it EXECUTES
the guard that separates the two sets (`renamed_with_proven_reader`), with its
own negative control in the same run.

Two same-named files, one trap
------------------------------

The corpus tracks 24 `.md` and the name `SKILL.md` is shared by many of them
(as are `README.md`, `SOUL.md`). Every comparison below is made on the EXACT
relative path (`rel == nom`, `set(SLICE)`), never on a basename or a suffix: a
bench matching by suffix would impute a neighbour's violation to this slice and
send a correct `dev-8` into a rewrite loop.

State of the tree when this bank was written, and how the RED is proven
----------------------------------------------------------------------

`dev-8` landed its translation (commit `bb4863b`, pushed, 0 unpushed) while this
bank was being written, so the live tree is already GREEN: `11 passed`. The RED
is proven on a THROWAWAY CLONE whose slice file is restored to the versioned
bytes of `origin/dev` (`git show origin/dev:<path>` -> `write_text`; never a copy
kept beside the bank, and never a `checkout` of the reference inside the shared
worktree, which would rewrite the peer's perimeter) — `6 failed, 5 passed`, the
six failures all naming the file and its 360 accented lines outside a frozen
span. The same command on the live tree prints `11 passed`. Both runs are pasted
in the card comment.

The five cases that stay green on the reference state are green for a stated
reason, not by accident: three clone the branch HEAD and therefore judge the
state the translation DELIVERED (blindness pair, ledger rule, machine
vocabulary), one calibrates the lexical detector over corpora that do not include
this slice, and one is a `build_tree` decor that carries its own French bytes. Each
of them names, in its own mutation, the artifact that makes it red.

No real clock, no randomness: every fixture is a throwaway git repository or a
throwaway clone built by this bank from VERSIONED bytes, and every count is
recomputed from the bytes in hand rather than asserted as a copied literal.
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

SLICE = ("skills/hermes-multi-agent-orchestration/SKILL.md",)

TOOL_REL = "pipeline/pj_lang_lint.py"
EXCLUSIONS_REL = "pipeline/pj_lang_lint.exclusions.yaml"
PLATE_REL = "docs/architecture/context/issue-2-plate.html"
GATE_READER_REL = "pipeline/gate_hook.py"

TOOL = REPO / TOOL_REL
EXCLUSIONS = REPO / EXCLUSIONS_REL
PLATE = REPO / PLATE_REL

SLICE_K = 8
# The pre-state of this slice: the branch's merge base against `origin/dev`, i.e. the
# bytes the translation starts from. Read through `git show`, never from a copy kept
# beside this bank, so the reference cannot drift with the tree under test.
REF_REF = "origin/dev"

# Character class of the contract, identical to the slice-1/2/5/6/7 banks, to the
# scanner and to the ratified plate's `character_class_chars`. Re-declared here on
# purpose: a bank that imported the class from the subject would widen with the subject.
# `test_nominal_...` asserts this literal equals the class the plate declares.
ACCENTS = "àâäçéèêëîïôöùûüÿœæñÀÂÄÇÉÈÊËÎÏÔÖÙÛÜŸŒÆÑ"

# The two and only frozen machine protocols. This slice cites `Importé depuis` 0 times
# and `ROOM:` once (measured at the reference revision) — the counts are asserted and
# PRINTED, so a 0 == 0 is never mistaken for a pass of anything else.
PROTOCOLES = ("Importé depuis", "ROOM:")

# The gate marker this slice documents, and the tracked production file that re-reads
# it. Asserted by NAME because it is the only machine marker of the document whose
# reader is not one of the two frozen protocols: translating it makes every worker
# blind to its gate verdict, with no error.
GATE_MARKER = "[gate]"
CITE_GATE = "`[gate]`"

# French-only function words: no English homograph. Same list and same threshold as the
# slice-5/6/7 banks, RE-MEASURED here over this tree's already-English corpora (see the
# calibration case).
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

# A translated file of the decor: accent-free, cites no contract of the slice.
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


def lines_of(root, rel):
    return (Path(root) / rel).read_text(encoding="utf-8").splitlines()


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


def machine_vocabulary(text):
    """{span: 'reader:line'} for the backticked code tokens of `text` with PROVENANCE.

    Only tokens written INSIDE a backtick span are collected, and only those a tracked
    production file carries verbatim: `` `ready` `` is a citation of a machine state,
    while the bare English word "ready" is prose a translation may add or remove at will.
    Counting the bare word would red a correct translation.
    """
    vocab = {}
    for span in spans_of(text):
        if not garde(span):
            continue
        r, n = proven_reader(span)
        if r:
            vocab[span] = "%s:%d" % (r, n)
    return vocab


def renamed_spans(ref, head):
    """Spans of the reference the translation DROPPED or RENAMED (measured, not listed).

    A translated document legitimately rewrites bracketed placeholders
    (``--parent <synthèse>`` -> ``--parent <summary>``). This function returns those
    spans so the guard below can prove NONE of them is a machine contract.
    """
    h = set(spans_of(head))
    return sorted(s for s in spans_of(ref) if s not in h)


def renamed_with_proven_reader(vocab, renamed):
    """The intersection that must be EMPTY: a renamed span a production file reads.

    Non-empty means the translation broke a machine contract by rewriting a literal, and
    the case that calls this must fail loudly rather than silently judge nothing.
    """
    return sorted(set(renamed) & set(vocab))


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

    The corpus tracks 24 `.md` and the name `SKILL.md` is shared by many, so a suffix
    test would impute a neighbour's violation to this slice.
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
            "slice 8 NOT translated: %d accented line(s), of which %d outside a frozen "
            "span.\n  - %s\n(this bank is written BEFORE the translation: this failure "
            "IS the expected RED)"
            % (total, len(restes), "\n  - ".join(restes[:8])))


def skeleton(text):
    """The document's SKELETON: what a translation must not rewrite, only reword.

    `version` is deliberately NOT part of the judged set: bumping a skill's version is a
    legitimate editorial act, and judging it would red a correct translation. It is
    printed as a diagnostic instead.
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
    """Discrepancies of the skeleton reference -> HEAD, field by field."""
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


def ledger_slice(k=SLICE_K):
    raw = ledger().get("slices")
    assert raw, "the plate ledger carries no `slices` entry"
    recs = raw if isinstance(raw, dict) else {r.get("k"): r for r in raw}
    rec = recs.get(k) or (recs.get(str(k)) if isinstance(recs, dict) else None)
    assert rec, "slice %d absent from the plate ledger" % k
    return rec


def accented_lines(lines):
    return [l for l in lines if any(c in ACCENTS for c in l)]


def sync_ecarts(root):
    """[(rel, field, declared, measured)] — the plate's ledger against the tree it describes.

    The ledger carries per-file `lines` and `accented_lines`; the slice-1 bench compares
    them to the live tree. A translation that moves one without the other is the
    intermediate state that bench reports as a failure, so the rule is executed here
    directly — on a clone for the discrimination proof, and printed for the live tree so
    `conv-8` arbitrates on a measurement rather than a guess.
    """
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
        lignes = lines_of(root, rel)
        for champ, mesure in (("lines", len(lignes)),
                              ("accented_lines", len(accented_lines(lignes)))):
            declare = entry.get(champ)
            if declare != mesure:
                ecarts.append((rel, champ, declare, mesure))
    return ecarts


def offenders(source, is_path=True):
    """[(line, tokens, text)] for the accent-free French lines of a document.

    `source` is a relative path of the slice by default; pass `is_path=False` to judge a
    text held in memory (the calibration corpus is read from the tree by the caller).
    """
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
    """(paths, why) — the accent-free lines the detector must NOT fire on.

    Two sources, because they answer different questions: the plate's `outside_corpus` is
    a RATIFIED declaration of what counts as already-English, and the second corpus is
    DERIVED — every slice the plate declares `kind: translate` whose COMMITTED copy (HEAD,
    not the working tree) now carries zero accented line, i.e. slices this pipeline has
    already translated. Reading HEAD keeps the calibration immune to a sibling slice's
    in-flight edits in the shared worktree.
    """
    declare = [e.get("path") for e in ledger().get("outside_corpus") or [] if e.get("path")]
    recs = ledger().get("slices") or []
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


# --------------------------------------------------------------------------- fixtures


@pytest.fixture(scope="module")
def clone_base(tmp_path_factory):
    """Throwaway clone at the branch's commit: mutations never touch the live tree."""
    require_upstream()
    commit = git("rev-parse", "HEAD").strip()
    d = tmp_path_factory.mktemp("slice8") / "clone"
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


def test_nominal_le_scan_sort_0_et_muet_sur_le_fichier_de_la_slice():
    """Nominal: rc 0 AND silent on the document of the slice.

    The two halves are one contract: a scan that prints a report while returning 0 is
    not compliant with it either.
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


def test_nominal_le_scan_sans_argument_ne_nomme_plus_la_slice_dans_tout_le_corpus():
    """Nominal, enumeration branch: the no-argument form takes another code path
    (`git ls-files` over the whole corpus) and must not name the file of this slice.

    The assertion is on the NAMES, not on rc: while other slices are still French the
    whole-tree scan legitimately returns 1, and this slice's own contribution is what
    this case isolates. The consistency half is asserted too — rc 1 implies at least one
    named line, so the enumeration branch cannot pass by printing nothing. Exact relative
    paths only — see the module docstring.
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


def test_nominal_le_fichier_de_la_slice_est_celui_de_la_planche_et_le_squelette_survit():
    """Nominal: the perimeter and the character class are the RATIFIED ones, and the
    document SKELETON survives the translation.

    Three independent sources are closed against each other here: the plate's ledger (the
    declared file list), the plate's declared character class, and the tree (skeleton
    reference -> HEAD). The ledger's per-file NUMBERS are deliberately NOT asserted here:
    a translation and its ledger entry belong to the same commit, and editing slice 1's
    artifact is outside this slice's declared perimeter — the rule is executed on a clone
    by `test_limite_le_registre_de_la_planche...`, and the live state is printed there for
    `conv-8`.
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
        if entry.get("accented_lines") != len(expected_violations(ref, ())):
            ecarts.append("%s: ledger declares %r accented lines, the reference "
                          "revision has %d"
                          % (rel, entry.get("accented_lines"),
                             len(expected_violations(ref, ()))))
        ecarts += skeleton_problems(rel, ref, head_text(rel))
    assert not ecarts, "perimeter/skeleton in discrepancy:\n  " + "\n  ".join(ecarts)
    print("witness perimeter: slice %d = %r, character class %r, skeleton ref=%r head=%r"
          % (SLICE_K, declare, classe, skeleton(git_show(SLICE[0])),
             skeleton(head_text(SLICE[0]))))


# --------------------------------------------------------------------------- limite


def test_limite_les_litteraux_geles_declares_sont_les_deux_protocoles_et_restent_verbatim():
    """Limit: the exemption file is not widened, and every declared frozen literal keeps
    its exact number of occurrences reference -> HEAD.

    Measured at the reference revision: this slice cites `Importé depuis` 0 times and
    `ROOM:` 1 time (line 326, inside the span ``ROOM: <room_id>``), so the citation half
    is 1 + 0 and is PRINTED as such — the weight of this case is the non-widening plus
    the machine vocabulary of the next case. What this case forbids is the bypass:
    blanching French that is still in the corpus.
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
    print("witness frozen literals: declared %r, occurrences (literal, ref, head) %r"
          % (lits, vus))


def test_limite_la_transcription_du_marqueur_gele_est_invisible_au_scan_et_vue_ici(clone):
    """Limit, the blindness pair EXECUTED: the scan cannot see a translated frozen
    literal, and this bank can.

    The scan BLANKS the spans of the declared frozen literals before judging, and the
    translated form carries no diacritic either: `ROOM:` renamed to `ROOM_LINK:` leaves it
    rc 0 and SILENT — while `pipeline/pj_room_keeper.py:76` matches ``ROOM:\\s*(\\S+)``
    and the room↔card link of this slice's own chapter goes silent, with no error. The
    two halves are asserted in the SAME run on the SAME clone, each with its own
    assertion, and the mutation is proven applied by sha256.
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
    n_occ = texte.count("ROOM:")
    remplacement = texte.replace("ROOM:", "ROOM_LINK:")
    assert n_occ and remplacement != texte, (
        "mutation NOT applied: %r carries no occurrence of the frozen literal" % rel)
    cible.write_text(remplacement, encoding="utf-8")
    apres = sha256(cible)
    assert apres != avant, "mutation NOT applied (hash witness): %s" % avant
    print("witness mutation: %s sha256 %s -> %s, %d occurrence(s) du marqueur renommée(s)"
          % (rel, avant[:12], apres[:12], n_occ))

    p = scan_rel(clone, *SLICE)
    assert p.returncode == 0 and out_of(p).strip() == "", (
        "witness of the blind spot: with the frozen literal TRANSLATED the scan must "
        "still be GREEN and silent — it blanks the span before judging, and the renamed "
        "form carries no diacritic. It was not, so 'the scan cannot see this' is not "
        "established on this state\n" + resume(p, "scan(slice, marqueur renommé)"))

    lits = frozen_literals()
    txt = "\n".join(lines_of(clone["dir"], rel))
    manquants = [lit for lit in lits if lit in texte and lit not in txt]
    assert manquants, (
        "the citation control did NOT see the renamed frozen literal while the scan was "
        "green: the guard is blind and this case proves nothing")
    print("witness paire d'aveuglement: scan rc=0 MUET sur le clone renommé, contrôle de "
          "citation ROUGE sur %r — la transcription du protocole est invisible au scan"
          % (manquants,))


def test_limite_le_vocabulaire_machine_cite_par_la_slice_est_preserve_verbatim():
    """Limit — the contract this slice really carries: the code tokens it teaches.

    Every backtick token of the slice whose reader is a TRACKED PRODUCTION file
    (`pipeline/`, `plugins/`, `agents/*/scripts/` …) must keep the same number of
    occurrences reference -> HEAD. A token with no reader is prose or a bracketed
    placeholder and is deliberately NOT judged; the vocabulary and its provenance are
    printed, so a red is diagnosable.

    Two falsifiable guards are EXECUTED in the same run rather than argued:
    (1) the renamed placeholder spans are separated from the machine vocabulary, with a
    negative control that injects a fake reader and requires the guard to name the span;
    (2) the `[gate]` marker — the only machine marker of this document whose reader is
    not one of the two frozen protocols — is asserted BY NAME with its reader quoted, and
    a rename of its citation is shown to change the count this case computes.
    """
    precondition_translated()
    ref_all, head_all = git_show(SLICE[0]), head_text(SLICE[0])

    vocab = machine_vocabulary(ref_all)
    assert len(vocab) >= 100, (
        "only %d machine token(s) of this slice have a proven reader in the tree: the "
        "provenance scan is broken, or the tokens moved — %r" % (len(vocab), sorted(vocab)))
    assert not [s for s in vocab if any(c in ACCENTS for c in s)], (
        "the vocabulary of the reference carries an accented token: it is prose, not a "
        "machine contract — %r" % [s for s in vocab if any(c in ACCENTS for c in s)])

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

    renamed = renamed_spans(ref_all, head_all)
    assert len(renamed) >= 10, (
        "only %d span(s) renamed reference -> HEAD: the reference and the tree are not "
        "the two states this guard is meant to separate — %r" % (len(renamed), renamed))
    fautifs = renamed_with_proven_reader(vocab, renamed)
    assert not fautifs, (
        "the translation REWROTE span(s) a tracked production file reads verbatim: %r\n"
        "those are machine contracts, not placeholders — they must be restored verbatim "
        "(a rename makes the reader silent, with no error)" % fautifs)
    # negative control, same function, same call form: inject one fake reader.
    temoin = renamed_with_proven_reader(dict(vocab, **{renamed[0]: "temoin.py:1"}), renamed)
    assert temoin == [renamed[0]], (
        "the guard is not discriminant: injecting a fake reader for %r did not make it "
        "report that span (%r)" % (renamed[0], temoin))

    # the gate marker, by name, with its reader quoted
    reader = (REPO / GATE_READER_REL).read_text(encoding="utf-8")
    assert GATE_MARKER in reader, (
        "%s no longer carries %r: this assertion has lost its subject"
        % (GATE_READER_REL, GATE_MARKER))
    n_ref, n_head = ref_all.count(CITE_GATE), head_all.count(CITE_GATE)
    assert n_ref > 0, ("the slice cites %s %d time(s) at %s: the marker assertion has no "
                       "subject" % (CITE_GATE, n_ref, REF_REF))
    assert n_head == n_ref, (
        "the gate marker %s: %d citation(s) at %s -> %d at HEAD. Every worker of this "
        "pipeline reads its gate verdict through that marker; translating it makes the "
        "gate invisible with no error"
        % (CITE_GATE, n_ref, REF_REF, n_head))
    mutant = head_all.replace(CITE_GATE, "`[gate-alt]`")
    assert mutant != head_all and mutant.count(CITE_GATE) != n_head, (
        "the mutation was not applied (no occurrence to rename) or did not change the "
        "count this case computes: %d -> %d"
        % (n_head, mutant.count(CITE_GATE)))

    print("witness machine vocabulary: %d token(s) with provenance -> 0 discrepancy; "
          "%d placeholder span(s) renamed and 0 of them read by code (%r…); gate marker "
          "%s %d citation(s) reference -> HEAD, mutation renames it to %d"
          % (len(vocab), len(renamed), renamed[:3], CITE_GATE, n_ref,
             mutant.count(CITE_GATE)))
    for span, prov in sorted(vocab.items()):
        print("    %-45r <- %s" % (span[:45], prov))


def test_limite_aucune_prose_francaise_sans_diacritique_ne_subsiste():
    """Limit — the blind spot of a diacritic scan, made executable.

    This slice carries 182 accent-free lines at `origin/dev`; French prose survives
    translation over several lines without losing one accent, and the scanner is
    structurally blind to it. Three things are measured in the SAME run:

    1. the detector is NON-VACUOUS on this subject: at the reference revision it flags a
       non-zero number of accent-free lines (measured: 19);
    2. the same detector flags ZERO such lines at HEAD, so the pair is red-able by the
       exact state this slice is meant to produce;
    3. a synthetic French line carrying no diacritic is caught by the same detector, so a
       zero at HEAD cannot be an empty rule.
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

    ecarts = ["%s:%d  [%s]  %s" % (SLICE[0], n, ",".join(t), txt[:150])
              for n, t, txt in offenders(SLICE[0])]
    assert not ecarts, (
        "French prose WITHOUT any diacritic still survives in the slice (threshold K>=%d "
        "distinct French-only words per line, 0 false positive measured over the English "
        "corpora of the calibration case):\n  " % SEUIL_LEXICAL + "\n  ".join(ecarts))
    print("witness blind spot: référence %d ligne(s) sans accent signalée(s), tête 0 sur "
          "%d ligne(s) sans accent ; contrôle positif %r -> %r"
          % (len(ref_hits), vues, temoin, toks))


def test_limite_la_calibration_du_controle_lexical_est_re_mesuree_sur_deux_corpus():
    """Limit, non-vacuity of the control itself: over English corpora this pipeline
    produced, the SAME detector returns zero.

    A threshold that fired on English prose would be a false-positive machine and no
    translation could ever satisfy it. Two corpora, because they answer different
    questions: the plate's `outside_corpus` is a RATIFIED declaration of what counts as
    already-English, and the second is DERIVED from the plate (slices it declares
    `kind: translate` whose committed copy now carries zero accented line). The zone
    comes from the ledger, not from this bank's convenience, and its size is asserted
    non-empty so a shrunken calibration cannot pass silently.
    """
    require_upstream()
    declare, deja = english_corpora()
    assert declare, ("the plate declares no already-English file (`outside_corpus`), so "
                     "the threshold of this control cannot be calibrated")
    absents = [rel for rel in declare + deja if not (REPO / rel).is_file()]
    assert not absents, "calibration corpus cites files absent from the tree: %r" % absents

    n_lignes, faux = calibration_report(declare + deja)
    assert n_lignes >= 300, (
        "calibration corpus too small to prove anything (%d accent-free lines over %d "
        "file(s)): %r" % (n_lignes, len(declare + deja), declare + deja))
    assert not faux, (
        "the lexical detector fires on prose these corpora are declared already English "
        "(%d false positive(s) over %d lines): the control is not discriminant\n  "
        % (len(faux), n_lignes)
        + "\n  ".join("%s:%d %s" % f[:3] for f in faux[:10]))
    print("witness calibration: 0 faux positif sur %d ligne(s) sans accent — %d fichier(s) "
          "déclaré(s) par la planche + %d fichier(s) de slice(s) déjà traduite(s) : %r"
          % (n_lignes, len(declare), len(deja), deja))


def test_limite_le_registre_de_la_planche_voit_la_slice_traduite_et_nomme_les_deux_champs(clone):
    """Limit: the plate's ledger rule BITES on a translated slice — executed on a clone,
    never asserted against the live tree.

    The slice-1 bench compares the ledger's per-file `lines` and `accented_lines` to the
    live tree, so a translation and its ledger entry belong to the same commit. This case
    does NOT require the live tree to be in sync — the ledger lives in slice 1's artifact
    and editing it is outside this slice's declared perimeter: it requires the RULE to be
    discriminating, and prints the live state so `conv-8` arbitrates on a measurement.

    Both fields are flipped by the SAME run, by two mutations applied to the clone: an
    accented line appended to the file (flips `accented_lines`), and a plain line appended
    after it (flips `lines`). One mutation alone would leave the other field unexercised.
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
        fh.write("\nLine left in French, with an accent.\n")
        fh.write("One more line, no diacritic at all.\n")
    apres = sha256(f)
    assert apres != avant, "mutation NOT applied on the clone: sha256 %s" % avant
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


# --------------------------------------------------------------------------- erreur


def test_erreur_le_fichier_oublie_est_nomme_avec_sa_ligne_par_le_meme_appel(tmp_path):
    """Error: the file of the slice is left entirely French.

    The pair is measured in the SAME run: the live slice sorts 0 (positive half — the RED
    of this card while the slice was still French), then a throwaway repository where the
    file carries the EXACT French bytes of the reference revision sorts 1 and NAMES it,
    with the line numbers recomputed from those bytes; an English stub of the same decor
    sorts 0 and silent.
    """
    precondition_translated()
    p = scan(SLICE)
    assert p.returncode == 0, resume(
        p, "positive half of the pair: the translated slice must sort 0")

    oublie = SLICE[0]
    francais = git_show(oublie)
    attendu = expected_violations(francais, frozen_literals())
    assert attendu, ("the reference revision of %s carries no violation: the decor would "
                     "measure nothing" % oublie)

    root = build_tree(tmp_path / "oublie", {oublie: francais})
    assert sha256(root / oublie) == hashlib.sha256(
        francais.encode("utf-8")).hexdigest(), (
        "the forgotten file of the decor is not the reference revision's bytes")
    suivis = [r for r in tracked(root) if r.endswith(".md")]
    assert suivis == [oublie], (
        "the decor must track exactly the path of the slice: %r -> %r"
        % ([oublie], suivis))

    q = scan(SLICE, cwd=root)
    assert q.returncode == 1, resume(
        q, "the file of the slice left entirely French: exit 1 expected")
    trouves = reported(out_of(q))
    noms = sorted({rel for rel, _, _ in trouves})
    assert noms == [oublie], (
        "the scan must name the forgotten file on its EXACT relative path; named: %r\n%s"
        % (noms, out_of(q)))
    lignes = sorted({n for rel, n, _ in trouves if rel == oublie})
    assert lignes == attendu, (
        "%s: the scan reported line(s) %r, this bank recomputes %r from the same bytes "
        "(%s)" % (oublie, lignes, attendu, REF_REF))

    # discrimination of the same call form: an English file of the same decor sorts 0
    propre = build_tree(tmp_path / "propre", {oublie: ENGLISH_STUB})
    s = scan(SLICE, cwd=propre)
    assert s.returncode == 0, resume(s, "an English file of the same decor: exit 0")
    assert out_of(s).strip() == "", (
        "the English file must be silent:\n%r" % out_of(s))
    print("witness forgotten file: %s (bytes of %s) -> rc=1, %d line(s) named, %d "
          "recomputed; English stub alone -> rc=0 silent"
          % (oublie, REF_REF, len(lignes), len(attendu)))


def test_erreur_le_scan_de_tout_le_corpus_nomme_aussi_le_fichier_oublie(tmp_path):
    """Error, enumeration branch: the no-argument form must name the forgotten file too.

    Same decor, same bytes, one different code path (`git ls-files` over the whole
    corpus): a defect that only one of the two forms sees is a defect the gate reports
    inconsistently.
    """
    require_upstream()
    oublie = SLICE[0]
    root = build_tree(tmp_path / "corpus", {oublie: git_show(oublie)})
    suivis = [r for r in tracked(root) if r.endswith(".md")]
    assert suivis == [oublie], (
        "the decor must track exactly the path of the slice: %r -> %r"
        % ([oublie], suivis))

    q = scan((), cwd=root)
    assert q.returncode == 1, resume(
        q, "whole-corpus scan of a decor holding the French file: exit 1 expected")
    noms = named_exact(out_of(q))
    assert oublie in noms, (
        "the whole-corpus scan must NAME the forgotten file %s; it named %r\n%s"
        % (oublie, noms, out_of(q)))
    print("witness whole corpus in the decor: rc=%d, named %r (tracked .md in the decor: "
          "%d)" % (q.returncode, noms, len(suivis)))
