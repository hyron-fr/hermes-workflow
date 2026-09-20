"""Slice 7 (skills pipelines + gate) — language RED bank, card t_f5632bae.

Subjects (the three documents `dev-7` translates, card t_8788aa3f):

    skills/hermes-kanban-multiagent-pipelines/SKILL.md
    skills/hermes-kanban-multiagent-pipelines/references/activating-kanban.md
    skills/kanban-gate/SKILL.md

The bank only MEASURES them: it never edits them (`tests/**` is this card's whole
write perimeter — `dev-7` owns the sources in the same worktree).

Contract executed here (same form as the slice-2 bank and the sibling slice banks):

    python3 pipeline/pj_lang_lint.py [--exclusions F] [<path> ...]

- rc 0 = compliant AND silent (stdout and stderr both empty);
- rc 1 = at least one line carrying a diacritic outside a frozen span, each line
  naming `path:line`;
- rc 2 = usage error (never a violation, and vice versa).

What this bank proves, and what it does NOT
-------------------------------------------

The diacritic scan is NECESSARY but not SUFFICIENT. This slice's three files carry
225 lines of which 92 are accented and 133 accent-free (measured at `origin/dev`),
and French prose survives translation without carrying a diacritic. So the bank also
carries one LEXICAL control, calibrated by measurement (see `test_limite_...prose...`):
a word-bounded list of French-only function words, threshold K = 2 distinct tokens per
line, zero false positives measured over the 202 accent-free lines of the zone the
RATIFIED plate itself declares already English (`plate-ledger.outside_corpus`).

Low recall, stated: at K = 2 the control flags 4 of the 133 accent-free lines of this
slice (printed file and line by the failure). It is a guard against a half-translation,
never a completeness proof; the diff review stays required in `conv-7`.

Measured corrections to the card's own prose
--------------------------------------------

1. The card's limit scenario reads "the frozen literals CITED BY THE SLICE stay
   verbatim". Measured at `origin/dev`: this slice cites `Importé depuis` 0 times and
   `ROOM:` 0 times. A case demanding a non-zero citation count would be red forever, so
   the check below is written as "count preserved reference -> HEAD" (0 == 0, printed as
   such) and the WEIGHT of the limit case sits on the contract the slice really does
   carry: the machine vocabulary whose reader is a tracked production file (see
   `test_limite_la_vocabulaire_machine...`, 20 tokens with provenance) plus the `[gate] `
   comment prefix, which is this slice's own subject and is read by
   `pipeline/gate_hook.py`.
2. The card announces "225 lines" — reproduced exactly: 111 + 68 + 46 = 225, and the
   ratified plate's ledger declares the same numbers with 92 accented lines.

Two same-named files, one trap
------------------------------

This slice contains TWO files whose basename is `SKILL.md`
(`skills/hermes-kanban-multiagent-pipelines/SKILL.md` and `skills/kanban-gate/SKILL.md`),
and the whole corpus carries many more. Every comparison below is therefore made on the
EXACT relative path (`rel == nom`, `set(SLICE)`), never on a basename or a suffix: a
bench matching by suffix would impute a neighbour's violation to this slice and send a
correct `dev-7` into a rewrite loop.

No real clock, no randomness: every fixture is a throwaway git repository built by this
bank from VERSIONED bytes (`git show origin/dev:<path>`), and every count is recomputed
from the bytes in hand rather than asserted as a copied literal.
"""
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[1]

SLICE = (
    "skills/hermes-kanban-multiagent-pipelines/SKILL.md",
    "skills/hermes-kanban-multiagent-pipelines/references/activating-kanban.md",
    "skills/kanban-gate/SKILL.md",
)

TOOL_REL = "pipeline/pj_lang_lint.py"
EXCLUSIONS_REL = "pipeline/pj_lang_lint.exclusions.yaml"
PLATE_REL = "docs/architecture/context/issue-2-plate.html"

TOOL = REPO / TOOL_REL
EXCLUSIONS = REPO / EXCLUSIONS_REL
PLATE = REPO / PLATE_REL

SLICE_K = 7
# The pre-state of this slice: the branch's merge base against `origin/dev`, i.e. the
# bytes the translation starts from. Read through `git show`, never from a copy kept
# beside this bank, so the reference cannot drift with the tree under test.
REF_REF = "origin/dev"

# Character class of the contract, identical to the slice-1 bench, to the scanner and to
# the ratified plate's `character_class_chars`. Re-declared here on purpose: a bank that
# imported the class from the subject would widen with the subject. `test_nominal_...`
# asserts this literal equals the class the plate declares.
ACCENTS = "àâäçéèêëîïôöùûüÿœæñÀÂÄÇÉÈÊËÎÏÔÖÙÛÜŸŒÆÑ"

# The two and only frozen machine protocols. This slice cites NEITHER of them (measured
# at the reference revision: 0 and 0) — the assertion below is the count contract, and
# the fact is printed so a 0 == 0 is never mistaken for a pass of anything else.
PROTOCOLES = ("Importé depuis", "ROOM:")

# The comment prefix this slice documents as a protocol, and the production file that
# re-reads it. Frozen as a literal because `kanban-gate` is the skill of that protocol:
# translating it makes every worker blind to the gate verdict, with no error.
GATE_PREFIX = "[gate] "
GATE_READER_REL = "pipeline/gate_hook.py"

# French-only function words: no English homograph. Same list and same threshold as the
# slice-5 bank, RE-MEASURED here over this tree's already-English zone (see the case).
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

ENGLISH_STUB = "# Title\n\nAll English prose, without a single diacritic.\nNo contract is cited here.\n"

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
    a token with no reader is prose, and prose is what the translation is allowed to
    rewrite.
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


def machine_vocabulary():
    """{span: 'reader:line'} for the backticked code tokens of the slice with PROVENANCE.

    Only tokens written INSIDE a backtick span are collected: `` `ready` `` is a citation of
    a machine state, while the bare English word "ready" is prose a translation may add or
    remove at will. Counting the bare word would red a correct translation (measured on the
    simulated-success pass: one legitimate sentence containing "ready" flipped the count).
    """
    vocab = {}
    for rel in SLICE:
        for span in SPAN_RE.findall(git_show(rel)):
            span = span.strip()
            if not span or span in vocab:
                continue
            r, n = proven_reader(span)
            if r:
                vocab[span] = "%s:%d" % (r, n)
    return vocab


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

    Two files of this slice are named `SKILL.md` and the corpus carries many more, so a
    suffix test would impute a neighbour's violation to this slice.
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
            "slice 7 NOT translated: %d accented line(s), of which %d outside a frozen "
            "span.\n  - %s\n(this bank is written BEFORE the translation: this failure "
            "IS the expected RED)"
            % (total, len(restes), "\n  - ".join(restes[:8])))


def frozen_literals():
    lits, _ = declared_exclusions()
    assert lits, "%s declares no frozen literal" % EXCLUSIONS_REL
    return lits


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


def ledger_slice(k):
    raw = ledger().get("slices")
    assert raw, "the plate ledger carries no `slices` entry"
    recs = raw if isinstance(raw, dict) else {r.get("k"): r for r in raw}
    rec = recs.get(k) or (recs.get(str(k)) if isinstance(recs, dict) else None)
    assert rec, "slice %d absent from the plate ledger" % k
    return rec


def offenders(source, is_path=True):
    """[(line, tokens, text)] for the accent-free French lines of a document.

    `source` is a relative path of the slice by default; pass `is_path=False` to judge a
    text held in memory (the calibration zone is read from the tree by the caller).
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


# -------------------------------------------------------------------------- nominal


def test_nominal_le_scan_sort_0_et_muet_sur_les_trois_fichiers_de_la_slice():
    """Nominal: rc 0 and silent on the three documents of the slice.

    `rc == 0` and the silence are the two halves of the contract: a scan printing a
    report while returning 0 is not compliant with it.
    """
    precondition_translated()
    p = scan(SLICE)
    assert p.returncode == 0, resume(
        p, "scan of the three translated documents: exit 0 expected")
    assert out_of(p).strip() == "", (
        "a compliant corpus must be SILENT (stdout AND stderr empty); obtained:\n%r"
        % out_of(p))
    print("witness nominal: %d files of the slice -> rc=0, silent" % len(SLICE))


def test_nominal_le_scan_sans_argument_ne_nomme_plus_la_slice_dans_tout_le_corpus():
    """Nominal, enumeration branch: the no-argument form takes another code path
    (`git ls-files` over the whole corpus) and must not name any of the three files.

    The assertion is on the NAMES, not on rc: while the rest of the corpus is still
    French the whole-tree scan legitimately returns 1, and the slice's own contribution
    is what this case isolates. Exact relative paths only — see the module docstring.
    """
    precondition_translated()
    p = scan()
    noms = set(named_exact(out_of(p)))
    fautifs = sorted(noms & set(SLICE))
    assert not fautifs, (
        "the whole-tree scan still NAMES files of this slice: %r\n%s"
        % (fautifs, out_of(p)))
    print("witness whole corpus: %d tracked .md, %d violation(s) elsewhere, 0 on the slice"
          % (len([r for r in tracked() if r.endswith(".md")]), len(noms)))


def test_nominal_le_perimetre_et_le_squelette_des_documents_sont_ceux_de_la_planche():
    """Nominal: the perimeter and the character class are the RATIFIED ones, and the
    document SKELETON survives the translation (a translation reworks prose, it does not
    rewrite documents — merging sections or dropping tables is out of scope).

    Three independent sources are closed against each other here: the plan's ledger
    (paths and line counts), the plate's declared character class, and the tree.
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

    ecarts = []
    for rel in SLICE:
        entry = files.get(rel) if isinstance(files, dict) else None
        ref = git_show(rel)
        n_ref = len(ref.splitlines())
        acc_ref = len(expected_violations(ref, ()))
        if not isinstance(entry, dict):
            ecarts.append("%s: no per-file numbers in the ledger" % rel)
        else:
            if entry.get("lines") != n_ref:
                ecarts.append("%s: ledger declares %r lines, the reference revision has %d"
                              % (rel, entry.get("lines"), n_ref))
            if entry.get("accented_lines") != acc_ref:
                ecarts.append("%s: ledger declares %r accented lines, the reference "
                              "revision has %d" % (rel, entry.get("accented_lines"), acc_ref))
        ecarts += skeleton_problems(rel, ref, head_text(rel))
    assert not ecarts, ("perimeter/skeleton in discrepancy:\n  " + "\n  ".join(ecarts))
    print("witness perimeter: slice %d = %r, character class %r, lines %s"
          % (SLICE_K, declare, classe,
             [len(git_show(r).splitlines()) for r in SLICE]))


# --------------------------------------------------------------------------- limite


def test_limite_les_litteraux_geles_declares_sont_les_deux_protocoles_et_restent_verbatim():
    """Limit: the exemption file is not widened, and every declared frozen literal keeps
    its exact number of occurrences reference -> HEAD.

    Measured at the reference revision: this slice cites `Importé depuis` 0 times and
    `ROOM:` 0 times, so the citation half is 0 == 0 and is PRINTED as such — the weight of
    this case is the non-widening plus the machine vocabulary of the next case. What this
    case forbids is the bypass: blanching French that is still in the corpus.
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
        vus.append((lit, n_ref))
        if n_ref != n_head:
            ecarts.append("frozen literal %r: %d occurrence(s) at %s -> %d at HEAD "
                          "(the reader of that literal goes silent, with no error)"
                          % (lit, n_ref, REF_REF, n_head))
        # case is part of "verbatim": `Room:` keeps the exact-form count intact
        ci_ref = sum(git_show(rel).lower().count(lit.lower()) for rel in SLICE)
        ci_head = sum(head_text(rel).lower().count(lit.lower()) for rel in SLICE)
        if ci_ref != ci_head:
            ecarts.append("a CASE VARIANT of %r was introduced: %d case-insensitive "
                          "occurrence(s) -> %d" % (lit, ci_ref, ci_head))
    assert not ecarts, ("the frozen literals of this slice are not preserved:\n  - "
                        + "\n  - ".join(ecarts))
    print("witness frozen literals: declared %r, occurrences reference -> HEAD %r"
          % (lits, vus))


def test_limite_le_vocabulaire_machine_cite_par_la_slice_est_preserve_verbatim():
    """Limit — the contract this slice really carries: the code tokens it teaches.

    Every backtick token of the slice whose reader is a TRACKED PRODUCTION file
    (`pipeline/`, `plugins/`, `agents/*/scripts/` …) must keep the same number of
    occurrences reference -> HEAD. A token with no reader is prose and is deliberately NOT
    judged; the vocabulary and its provenance are printed, so a red is diagnosable.

    The `[gate] ` prefix is asserted by name, because it is the subject of
    `skills/kanban-gate/SKILL.md` and is re-read by `pipeline/gate_hook.py`. Falsifiability
    is EXECUTED in the same run: a copy of the document with the prefix renamed must red
    the very function that judges it.
    """
    precondition_translated()
    ref_all = "\n".join(git_show(rel) for rel in SLICE)
    head_all = "\n".join(head_text(rel) for rel in SLICE)

    vocab = machine_vocabulary()
    assert len(vocab) >= 10, (
        "only %d machine token(s) of this slice have a proven reader in the tree: the "
        "provenance scan is broken, or the tokens moved — %r" % (len(vocab), vocab))

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

    # the gate prefix, by name, with its reader quoted
    reader = (REPO / GATE_READER_REL).read_text(encoding="utf-8")
    assert GATE_PREFIX in reader, (
        "%s no longer carries %r: this assertion has lost its subject"
        % (GATE_READER_REL, GATE_PREFIX))
    cite_gate = cited_span(GATE_PREFIX)
    n_ref, n_head = ref_all.count(cite_gate), head_all.count(cite_gate)
    assert n_ref > 0, ("the slice cites %s %d time(s) at %s: the prefix assertion has no "
                       "subject" % (cite_gate, n_ref, REF_REF))
    assert n_head == n_ref, (
        "the gate comment prefix %s: %d citation(s) at %s -> %d at HEAD. Every worker of "
        "this pipeline reads its gate verdict through that prefix; translating it makes "
        "the gate invisible with no error"
        % (cite_gate, n_ref, REF_REF, n_head))

    # Falsifiability, same function, same call form: rename the prefix in a copy.
    mutant = head_all.replace(cite_gate, "`[gate-ALT] `")
    assert mutant != head_all, "the mutation was not applied (no occurrence to rename)"
    assert mutant.count(cite_gate) != n_ref, (
        "the mutation left %d citation(s) of %s: the case cannot falsify the assertion it "
        "is meant to prove" % (mutant.count(cite_gate), cite_gate))
    print("witness machine vocabulary: %d token(s) with provenance -> 0 discrepancy; "
          "gate prefix %s %d citation(s) reference -> HEAD; mutation renames it to %d"
          % (len(vocab), cite_gate, n_ref, mutant.count(cite_gate)))
    for span, prov in sorted(vocab.items()):
        print("    %-45r <- %s" % (span[:45], prov))


def test_limite_aucune_prose_francaise_sans_diacritique_ne_subsiste():
    """Limit — the blind spot of a diacritic scan, made executable.

    This slice carries 133 accent-free lines at the reference revision; French prose can
    survive translation over several lines without losing one accent, and the scanner is
    structurally blind to it. Two things are measured in the same run:

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
    n_lignes = 0
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
          "positive; positive control %r -> %r; slice 7 flags %d"
          % (zone, n_lignes, temoin, toks, len(ecarts)))


# --------------------------------------------------------------------------- erreur


def test_erreur_un_fichier_oublie_est_nomme_avec_sa_ligne_par_le_meme_appel(tmp_path):
    """Error: one of the slice's files is left French.

    The pair is measured in the SAME run: the live slice sorts 0 (positive half — the RED
    of this card while the slice is still French), then a throwaway repository where one
    file carries the EXACT French bytes of the reference revision sorts 1 and NAMES it,
    with the line numbers recomputed from those bytes — and names no translated file of
    the same decor, which holds two English stubs.
    """
    precondition_translated()
    p = scan(SLICE)
    assert p.returncode == 0, resume(
        p, "positive half of the pair: the translated slice must sort 0")

    oublie = SLICE[2]
    francais = git_show(oublie)
    literals = frozen_literals()
    attendu = expected_violations(francais, literals)
    assert attendu, ("the reference revision of %s carries no violation: the decor would "
                     "measure nothing" % oublie)

    fichiers = {rel: ENGLISH_STUB for rel in SLICE}
    fichiers[oublie] = francais
    root = build_tree(tmp_path / "oublie", fichiers)
    assert sha256(root / oublie) == sha256_bytes(francais), (
        "the forgotten file of the decor is not the reference revision's bytes")
    suivis = [r for r in tracked(root) if r.endswith(".md")]
    assert sorted(suivis) == sorted(SLICE), (
        "the decor must track exactly the three paths of the slice: %r -> %r"
        % (sorted(SLICE), sorted(suivis)))

    q = scan(SLICE, cwd=root)
    assert q.returncode == 1, resume(
        q, "a file of the slice left entirely French: exit 1 expected")
    trouves = reported(out_of(q))
    noms = sorted({rel for rel, _, _ in trouves})
    assert noms == [oublie], (
        "only the forgotten file must produce a violation, compared on the EXACT relative "
        "path; named: %r\n%s" % (noms, out_of(q)))
    lignes = sorted({n for rel, n, _ in trouves if rel == oublie})
    assert lignes == attendu, (
        "%s: the scan reported line(s) %r, this bank recomputes %r from the same bytes "
        "(%s)" % (oublie, lignes, attendu, REF_REF))

    # discrimination of the same call, file by file: the English stubs sort 0
    s = scan([SLICE[0]], cwd=root)
    assert s.returncode == 0, resume(s, "a translated file of the same decor: exit 0")
    assert out_of(s).strip() == "", (
        "the translated file must be silent:\n%r" % out_of(s))
    print("witness forgotten file: %s (bytes of %s) -> rc=1, %d line(s) named, %d "
          "recomputed; README-style stub alone -> rc=0 silent"
          % (oublie, REF_REF, len(lignes), len(attendu)))


def test_erreur_le_scan_de_tout_le_corpus_nomme_aussi_le_fichier_oublie(tmp_path):
    """Error, enumeration branch: the no-argument form must name the forgotten file too.

    Same decor, same bytes, one different code path (`git ls-files` over the whole
    corpus): a defect that only one of the two forms sees is a defect the gate reports
    inconsistently.
    """
    precondition_translated()
    oublie = SLICE[1]
    fichiers = {rel: ENGLISH_STUB for rel in SLICE}
    fichiers[oublie] = git_show(oublie)
    root = build_tree(tmp_path / "corpus", fichiers)

    q = scan((), cwd=root)
    assert q.returncode == 1, resume(
        q, "whole-corpus scan of a decor holding one French file: exit 1 expected")
    noms = named_exact(out_of(q))
    assert oublie in noms, (
        "the whole-corpus scan must NAME the forgotten file %s; it named %r\n%s"
        % (oublie, noms, out_of(q)))
    autres = [rel for rel in SLICE if rel != oublie and rel in noms]
    assert not autres, (
        "the English stubs of the same decor must not be named: %r\n%s"
        % (autres, out_of(q)))
    assert len([r for r in tracked(root) if r.endswith(".md")]) == len(SLICE), (
        "the decor must track exactly the three paths of the slice")
    print("witness whole corpus in the decor: rc=%d, named %r (tracked .md in the decor: %d)"
          % (q.returncode, noms, len(SLICE)))


def sha256_bytes(data):
    return hashlib.sha256(data.encode("utf-8") if isinstance(data, str) else data).hexdigest()
