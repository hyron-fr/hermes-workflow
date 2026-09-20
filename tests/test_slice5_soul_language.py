"""Slice 5 (SOUL dev/doc/test) — language RED bank: the translated documents must
come out English, and the contracts they cite must survive verbatim.

Subject of this card: `agents/pj-dev/SOUL.md`, `agents/pj-doc/SOUL.md`,
`agents/pj-test/SOUL.md` — the three documents `dev-5` translates. The bank never
edits them: it only measures them.

Contract executed here (same form as the slice-2 bank and the plan's control):

    python3 pipeline/pj_lang_lint.py [--exclusions F] [<path> ...]

- rc 0 = compliant AND silent (stdout and stderr both empty);
- rc 1 = at least one line carrying a diacritic outside a frozen span, each line
  naming `path:line`;
- rc 2 = usage error (reserved for source facts, never for a violation).

What this bank proves, and what it does NOT
-------------------------------------------

The diacritic scan is NECESSARY but not SUFFICIENT: measured on this very slice, the
three files carry 147 lines with no diacritic at all, and 31 of them are French prose
(`- Ancres worktree : clones dev ${HOME}/pj-repos/<repo> — travaille UNIQUEMENT dans`
carries no diacritic and no scan can see it). A bank that stopped at the scan would
call a half-translated document green. So this bank also carries one LEXICAL control,
calibrated by measurement, not by taste:

- calibration zone: the paths the RATIFIED plate itself declares as already English
  (`plate-ledger.outside_corpus`), read by the bank, not by the subject. Measured: 202
  accent-free lines over 3 files — non-vacuous and derived from a ratified artifact.
- detector: a word-bounded list of French-only function words (no English homograph).
- threshold K = 2 distinct tokens per line. Measured: 0 false positives over those 202
  lines; 10 flagged lines inside the slice. K = 1 is measurably too low (two English
  lines of `docs/architecture/context/issue-2.md` fire, because they QUOTE the French
  words `dans` and `aucune`), K = 3 leaves only 4 — K = 2 is the measured crossing
  point, not a preference.

Low recall, stated: at K = 2 the control flags 10 of the 147 accent-free lines of the
slice, and those 10 are printed by the failure, file and line. It is a guard against
half-translations, never a completeness proof; the diff review stays required in
`conv-5`.

Scope of the bank: the three files of THIS slice only. A bank covering the whole
corpus would be red for reasons owned by other slices, and no slice could converge.
`tests/**` is the only write perimeter of this card (peer programming: `dev-5` owns
the sources in the same worktree).

Measured interaction carried here (it belongs to `conv-5`'s arbitration)
-----------------------------------------------------------------------

`tests/test_issue2_plate_reproducible.py` (slice 1) asserts the live tree against the
ratified plate's `plate-ledger` per-file numbers. The translation of this slice
therefore makes 4 of its 23 cases red until the ledger entry for slice 5 is updated in
the same commit. `test_erreur_une_slice_deja_traduite_est_nommee_et_non_comptee_...`
executes that pair on a throwaway clone and asserts the guard FIRES AND NAMES the
files, so the arbitration is argued on a measurement rather than on a guess.
"""
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[1]
TOOL_REL = "pipeline/pj_lang_lint.py"
EXCLUSIONS_REL = "pipeline/pj_lang_lint.exclusions.yaml"
PLATE_REL = "docs/architecture/context/issue-2-plate.html"

TOOL = REPO / TOOL_REL
EXCLUSIONS = REPO / EXCLUSIONS_REL
PLATE = REPO / PLATE_REL

# Slice 5, as declared by the plan (`specs/2/slices.json`) and by the ratified plate's
# ledger. Frozen here on purpose: the bank validates neither the plan by itself nor the
# ledger by itself.
SLICE_K = 5
SLICE_FILES = [
    "agents/pj-dev/SOUL.md",
    "agents/pj-doc/SOUL.md",
    "agents/pj-test/SOUL.md",
]

# Character class of the contract: latin letters carrying a diacritic or a latin
# ligature, lowercase AND uppercase. Same class as the slice-1 bench and the plate's
# `character_class_chars` — the bank re-declares it instead of importing it from the
# subject, so a subject that widens its own class cannot widen the bank's.
ACCENTS = "àâäçéèêëîïôöùûüÿœæñÀÂÄÇÉÈÊËÎÏÔÖÙÛÜŸŒÆÑ"

# The two and only frozen machine protocols. `Importé depuis` is the one that carries a
# diacritic, so it is also the literal that proves the SPAN granularity: an English line
# quoting it must stay clean while a diacritic elsewhere on that line is still reported.
PROTOCOLES = ["Importé depuis", "ROOM:"]

# French-only function words: no English homograph. Calibrated — see the module
# docstring. Never a hand-maintained word list for the scan itself (the scan's
# exemptions live in the versioned exclusions file); this list belongs to the BANK's
# lexical control and is re-measured by `test_limite_...calibration...`.
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

LEDGER_RE = re.compile(
    r"<script[^>]*id=[\"']plate-ledger[\"'][^>]*>(?P<json>.*?)</script>", re.S | re.I
)


# --------------------------------------------------------------------------- tools


def _run(cmd, cwd=None):
    return subprocess.run(cmd, cwd=str(cwd) if cwd else None,
                          capture_output=True, text=True, timeout=300)


def _require_sujets():
    """Explicit RED when an upstream deliverable of this slice is missing."""
    manquants = [rel for rel, p in ((TOOL_REL, TOOL), (EXCLUSIONS_REL, EXCLUSIONS))
                 if not p.is_file()]
    if manquants:
        pytest.fail(
            "upstream deliverable absent from the tree: %s\n"
            "this bank is written BEFORE the implementation (peer programming "
            "test || dev): this failure is the expected RED." % ", ".join(manquants))


def scan(paths=(), cwd=REPO, exclusions=EXCLUSIONS):
    """Run the scan. Returns the CompletedProcess: rc IS the contract."""
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


def lines_of(rel):
    return (REPO / rel).read_text(encoding="utf-8").splitlines()


def accented_lines(rel_or_lines):
    """Line numbers carrying a character of the contract's class."""
    if isinstance(rel_or_lines, (str, Path)):
        lines = (REPO / rel_or_lines if isinstance(rel_or_lines, str)
                 else rel_or_lines).read_text(encoding="utf-8").splitlines()
    else:
        lines = rel_or_lines
    return [n for n, l in enumerate(lines, 1) if any(c in ACCENTS for c in l)]


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def git(*args, cwd=REPO):
    p = _run(["git", "-C", str(cwd), *args])
    assert p.returncode == 0, "git %s failed: %s" % (" ".join(args), p.stderr)
    return p.stdout


def tracked_md(root=REPO):
    """Canonical enumeration of the bank: `git ls-files '*.md'`, never a walk.

    Used by `test_limite_la_calibration_...`'s non-vacuity witness: the count of tracked
    `.md` is what distinguishes "the corpus shrank" from "the corpus moved".
    """
    p = subprocess.run(["git", "-C", str(root), "ls-files", "-z", "*.md"],
                       capture_output=True)
    assert p.returncode == 0, p.stderr.decode()
    return sorted(x.decode("utf-8") for x in p.stdout.split(b"\x00") if x)


def offenders(rel):
    """[(line, sorted tokens, text)] for the accent-free French lines of `rel`."""
    p = REPO / rel
    hits = []
    for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
        if any(c in ACCENTS for c in line):
            continue  # the scan already reports these; this control judges the rest
        toks = sorted({m.group(1).lower() for m in MOT_FR.finditer(line)})
        if len(toks) >= SEUIL_LEXICAL:
            hits.append((n, toks, line.strip()))
    return hits


def ledger():
    if not PLATE.is_file():
        pytest.fail("ratified plate absent: %s" % PLATE)
    m = LEDGER_RE.search(PLATE.read_text(encoding="utf-8"))
    assert m, ("no `plate-ledger` machine block in %s: the plan's per-file numbers "
               "cannot be read" % PLATE)
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


def declared_exclusions():
    """(literals, raw text) of the versioned exclusions file."""
    assert EXCLUSIONS.is_file(), "exclusions file absent: %s" % EXCLUSIONS
    raw = EXCLUSIONS.read_text(encoding="utf-8")
    doc = yaml.safe_load(raw)
    lits = []

    def walk(node, list_ctx=False):
        if isinstance(node, dict):
            for key, val in node.items():
                kl = str(key).strip().lower()
                if kl in ("litteral", "literal") and isinstance(val, str):
                    lits.append(val)
                    continue
                walk(val, kl in ("protocoles", "geles", "frozen_literals"))
        elif isinstance(node, (list, tuple)):
            for val in node:
                if isinstance(val, str) and list_ctx:
                    lits.append(val)
                else:
                    walk(val, list_ctx)

    walk(doc)
    return [l.strip() for l in lits if l and l.strip()], raw


@pytest.fixture(scope="module")
def clone_base(tmp_path_factory):
    """Throwaway clone at the branch's commit, OVERLAID with the working tree's version
    of the slice's files.

    Both halves are needed and each closes a trap:
    - a real `git clone` gives the fixture a tree with `origin/dev` in it, so the
      pre-state of the slice is reachable from inside the fixture;
    - `git clone` alone takes the COMMITTED state, so a bank that only cloned would
      judge the pin and not the tree under translation (measured on this card: the
      fixtures came back clean while the live tree was still French). Overlaying the
      three files from the live tree makes the fixture measure what this run measures.
    """
    for rel in (TOOL_REL, EXCLUSIONS_REL):
        assert (REPO / rel).is_file(), "upstream deliverable absent: %s" % rel
    commit = git("rev-parse", "HEAD").strip()
    d = tmp_path_factory.mktemp("slice5") / "clone"
    p = _run(["git", "clone", "--no-hardlinks", "--quiet", str(REPO), str(d)])
    assert p.returncode == 0, "clone impossible: %s" % p.stderr
    p = _run(["git", "-C", str(d), "checkout", "--detach", commit])
    assert p.returncode == 0, "checkout %s impossible: %s" % (commit, p.stderr)
    for rel in SLICE_FILES:
        src, dst = REPO / rel, d / rel
        assert src.is_file(), "the tree under test does not carry %s" % rel
        shutil.copyfile(src, dst)
    return {"dir": d, "commit": commit}


@pytest.fixture
def clone(clone_base, tmp_path):
    """Playable copy: each test mutates ITS copy, never the module-scoped one."""
    d = tmp_path / "clone"
    shutil.copytree(clone_base["dir"], d)
    for rel in SLICE_FILES:
        assert (d / rel).is_file(), "the clone does not carry %s" % rel
    return {"dir": d, "commit": clone_base["commit"]}


def scan_rel(clone_ctx, rel):
    """Scan one subject INSIDE the clone, from the clone's own root."""
    return scan([rel], cwd=clone_ctx["dir"])


# ------------------------------------------------------------------------ nominal


def test_nominal_le_scan_sort_0_et_ne_parle_pas_sur_les_fichiers_de_la_slice():
    """Nominal: rc 0 and silent on the three files of the slice.

    `rc == 0` and the silence are the two halves of the contract: a scan that prints
    a report while returning 0 is not compliant with it.
    """
    _require_sujets()
    p = scan(SLICE_FILES)
    assert p.returncode == 0, (
        "the three translated documents must scan clean\n" + resume(p, "scan(slice)"))
    assert p.stdout.strip() == "" and p.stderr.strip() == "", (
        "rc 0 must be SILENT (stdout AND stderr empty)\n" + resume(p, "scan(slice)"))


def test_nominal_le_scan_sans_argument_ne_signale_plus_la_slice_dans_l_arbre_entier():
    """Nominal, enumeration branch: the no-argument form takes another code path
    (`git ls-files` over the whole corpus) and must not name any of the three files.

    The assertion on the named files is separate from rc: while the rest of the corpus
    is still French the whole-tree scan legitimately returns 1, and the slice's own
    contribution is what this case isolates.
    """
    _require_sujets()
    p = scan()
    nommes = sorted({rel for rel in SLICE_FILES
                     if re.search(r"(?m)^.*%s:\d+" % re.escape(rel), out_of(p))})
    assert not nommes, (
        "the whole-tree scan still names the slice's files: %s\n" % nommes
        + resume(p, "scan()"))


def test_nominal_les_trois_fichiers_sont_ceux_que_la_planche_declare_pour_la_slice():
    """The slice's perimeter is the plan's, and the file STRUCTURE is unchanged.

    A translation that rewrites a document (merging lines, dropping sections) is not a
    translation: the plate's per-file line count is the ratified reference, so a
    structure change must be visible in the same commit as the ledger it invalidates.
    """
    rec = ledger_slice(SLICE_K)
    files = rec.get("files")
    declare = sorted(files) if isinstance(files, (list, tuple)) else sorted(files or {})
    assert declare == sorted(SLICE_FILES), (
        "plate slice %d declares %r, the slice is %r" % (SLICE_K, declare,
                                                         sorted(SLICE_FILES)))
    ecarts = []
    for rel in SLICE_FILES:
        entry = files.get(rel) if isinstance(files, dict) else None
        if not isinstance(entry, dict):
            ecarts.append("%s: no per-file numbers in the ledger" % rel)
            continue
        n = len(lines_of(rel))
        if entry.get("lines") != n:
            ecarts.append("%s: ledger declares %r lines, tree has %d"
                          % (rel, entry.get("lines"), n))
    assert not ecarts, ("the slice no longer matches the ratified plate:\n  "
                        + "\n  ".join(ecarts))


# ------------------------------------------------------------------------- limite


def test_limite_le_fichier_d_exclusion_fige_les_deux_protocoles_et_les_cite_verbatim():
    """Limit: the frozen literals the scan removes are declared, verbatim, with the
    reader that carries each one — and the ACCENTED literal is declared, which is what
    makes the span machinery do any work at all on the slice's files.

    Reading the cited line rather than trusting the declaration: a citation that drifts
    (file renamed, line moved, literal translated) is a gap, not a decoration.
    """
    lits, _ = declared_exclusions()
    manquants = [l for l in PROTOCOLES if l not in lits]
    assert not manquants, (
        "the exclusions file no longer freezes %s (declared: %r)" % (manquants, lits))
    accentues = [l for l in lits if any(c in ACCENTS for c in l)]
    assert accentues, (
        "no ACCENTED frozen literal is declared (%r): the span machinery would then "
        "have nothing to remove and the scan would be blind to its own contract" % lits)


def test_limite_le_fichier_d_exclusion_ne_porte_aucune_prose_accentuee():
    """Limit: everything accented inside the exclusions file is INSIDE a declared
    literal.

    The file itself says it: an accented word in a comment would silently widen the
    exemptions, because every accented declared string is subtracted from the scanned
    line. Executing that sentence is the only way to keep it true.
    """
    lits, raw = declared_exclusions()
    reste = raw
    for lit in lits:
        reste = reste.replace(lit, "")
    survivants = sorted({c for c in reste if c in ACCENTS})
    assert not survivants, (
        "accented characters survive outside the declared literals: %r — accented prose "
        "in %s widens the exemptions in silence" % (survivants, EXCLUSIONS_REL))


def test_limite_aucune_ligne_de_prose_francaise_sans_diacritique_ne_subsiste():
    """Limit: the lexical control — French prose that carries no diacritic.

    Measured on the frozen tree: the slice's three files carry 147 accent-free lines,
    of which 31 trip the detector at K >= 1 and 10 cross the calibrated threshold
    K = 2 (`- Ancres worktree : clones dev ${HOME}/pj-repos/<repo> — travaille
    UNIQUEMENT dans` is one of them and no diacritic scan can see it). The RED is here,
    and so is the gap the diacritic scan cannot close.
    """
    _require_sujets()
    ecarts = []
    for rel in SLICE_FILES:
        for n, toks, txt in offenders(rel):
            ecarts.append("%s:%d  [%s]  %s" % (rel, n, ",".join(toks), txt[:150]))
    assert not ecarts, (
        "French prose without any diacritic still survives in the slice "
        "(threshold K>=%d distinct French-only words per line, 0 false positives "
        "measured over the plate's already-English zone):\n  " % SEUIL_LEXICAL
        + "\n  ".join(ecarts))


def test_limite_la_calibration_du_controle_lexical_est_re_mesuree_sur_l_arbre():
    """Limit, non-vacuity of the control itself: on the corpus the RATIFIED plate
    declares already English, the same detector returns zero. A threshold that fired on
    English prose would be a false-positive machine, and no translation could ever
    satisfy it.

    The zone comes from `plate-ledger.outside_corpus` (a ratified decision, not the
    bank's own convenience) and its size is asserted to be non-empty: a calibration zone
    that shrank to nothing would turn this case into a green that measured nothing.

    Discriminating pair, in the same call form: the same `offenders()` call is applied to
    the calibration zone (expects zero) and to a synthetic French line built here
    (expects a hit). A detector that returned nothing for both would pass the first half
    alone — this is the half that keeps it falsifiable.
    """
    zone = [e.get("path") for e in ledger().get("outside_corpus") or [] if e.get("path")]
    assert zone, ("the plate declares no already-English file (`outside_corpus`), so the "
                  "threshold of this control cannot be calibrated")
    absents = [rel for rel in zone if not (REPO / rel).is_file()]
    assert not absents, "calibration zone cites files absent from the tree: %r" % absents
    n_lignes = sum(len(lines_of(rel)) for rel in zone)
    assert n_lignes >= 30, (
        "calibration zone too small to prove anything (%d lines over %d files): %r"
        % (n_lignes, len(zone), zone))
    faux = [(rel, n, txt) for rel in zone for n, _, txt in offenders(rel)]
    assert not faux, (
        "the lexical detector fires on prose the plate declares already English "
        "(%d false positives over %d lines): the control is not discriminant\n  "
        % (len(faux), n_lignes)
        + "\n  ".join("%s:%d %s" % f for f in faux[:10]))
    print("witness: calibration zone %r, %d accent-free lines, %d false positives"
          % (zone, n_lignes, len(faux)))
    print("witness: tracked .md enumerated by the bank: %d" % len(tracked_md()))

    # positive control, same detector: a French line WITHOUT any diacritic must be
    # caught. Without this half, a detector broken to always return [] would green.
    temoin = "les cartes dans le worktree sont decoupees sans accents"
    toks = sorted({m.group(1).lower() for m in MOT_FR.finditer(temoin)})
    assert len(toks) >= SEUIL_LEXICAL, (
        "positive control FAILED: the detector no longer sees French prose at all "
        "(%d tokens on %r) — the zero above is vacuous" % (len(toks), temoin))
    print("witness: positive control %r -> %r" % (temoin, toks))


# -------------------------------------------------------------------------- erreur


def test_erreur_un_fichier_oublie_est_nomme_avec_sa_ligne_et_le_scan_sort_1(clone):
    """Error: one of the slice's files is left out of the translation.

    The mutation is APPLIED in the clone and proven twice in the same run (the file's
    sha256 changes AND the scan's rc flips), the expected line number is MEASURED after
    the mutation rather than hardcoded, and the scan is required to name the forgotten
    file — and only it.
    """
    rel = "agents/pj-doc/SOUL.md"
    cible = clone["dir"] / rel
    avant_hash = sha256(cible)
    ajout = "\nLe document est resté en français faute de traduction.\n"
    avant_txt = cible.read_text(encoding="utf-8")
    avant_lignes = len(avant_txt.splitlines())
    p_avant = scan_rel(clone, rel)
    assert p_avant.returncode == 0, (
        "EXPECTED RED while the slice is still French: the error case can only be "
        "exercised once the subject is translated, because its first witness is "
        "`the subject is clean BEFORE the mutation`. Measured rc=%d.\n"
        % p_avant.returncode + resume(p_avant, "scan(%s) before mutation" % rel))

    with cible.open("a", encoding="utf-8") as fh:
        fh.write(ajout)
    apres_hash = sha256(cible)
    lignes = cible.read_text(encoding="utf-8").splitlines()
    # The expected line number is MEASURED from the mutation, never incremented by a
    # hand-written literal: `+ 1` was wrong here (the appended block carries a leading
    # blank line, so the file grows by two) and a wrong literal would have been reported
    # as a failure of a correct scanner.
    n_mutation = len(lignes)
    attendu = len((avant_txt.rstrip("\n") + ajout).splitlines()) + 1
    print("witness: %s sha256 %s -> %s ; lines %d -> %d (expected mutation line %d)"
          % (rel, avant_hash[:12], apres_hash[:12], avant_lignes, n_mutation, attendu))
    assert apres_hash != avant_hash, "mutation NOT applied (hash witness): %s" % avant_hash
    assert n_mutation == attendu, (
        "the mutated file has %d lines, the mutation was computed to yield %d"
        % (n_mutation, attendu))

    p = scan_rel(clone, rel)
    assert p.returncode == 1, (
        "a forgotten file must return rc 1 (violations), got %d\n"
        + resume(p, "scan(%s) apres mutation" % rel))
    assert "%s:%d" % (rel, n_mutation) in out_of(p), (
        "the forgotten file must be named WITH its line (%s:%d):\n%s"
        % (rel, n_mutation, out_of(p)))
    autres = [f for f in SLICE_FILES if f != rel and f in out_of(p)]
    assert not autres, (
        "the report must be specific to the mutated file, it also names %r:\n%s"
        % (autres, out_of(p)))


def test_erreur_une_slice_deja_traduite_est_nommee_et_non_comptee_comme_rouge(clone):
    """Error, the pair applied INSIDE the clone: pre-state from `origin/dev`, then the
    slice is translated. The clone's tip is deliberately NOT relied on, so this case
    replays identically before and after `dev-5` commits — a bank that only worked on a
    French tree would break on the very commit it is supposed to bless.

    It restores the three files from `origin/dev` (where they really are French),
    verifies that pre-state carries accented lines (non-vacuity: a slice with none would
    make the whole RED spurious), strips the diacritics in place, and then asserts, in
    the SAME run:

    - the scan turns GREEN on the slice (rc 0) — the RED of this card is reachable;
    - the slice-1 bench (`tests/test_issue2_plate_reproducible.py`) turns RED and NAMES
      the slice's files, because the ratified plate's ledger still declares their
      accented lines. That pair is the arbitration `conv-5` has to carry: the ledger
      update belongs to the same commit as the translation.
    """
    import unicodedata

    map_ = {"œ": "oe", "æ": "ae", "Œ": "OE", "Æ": "AE"}
    # The pre-state is READ from the parent repo (`origin/dev` is where the slice really
    # is French) and WRITTEN into the fixture. Two traps closed, both measured:
    # - `git -C REPO checkout ...` (first version) restored the French files in the PARENT
    #   tree, i.e. wrote outside `tests/**` — in a shared worktree that is a write into the
    #   peer's perimeter, and it made every later run judge a tree the bank had rewritten;
    # - `git -C clone checkout origin/dev` (second version) failed with `référence
    #   invalide: origin/dev`, because a clone of a clone does not carry remote-tracking
    #   refs: only `refs/heads/*` are mapped. Measured with `for-each-ref` on the fixture.
    pre_state = {}
    for rel in SLICE_FILES:
        p = _run(["git", "-C", str(REPO), "show", "origin/dev:%s" % rel])
        assert p.returncode == 0, (
            "cannot read the slice's pre-state `origin/dev:%s`: %s" % (rel, p.stderr))
        pre_state[rel] = p.stdout

    pre = sum(len(accented_lines(t.splitlines())) for t in pre_state.values())
    assert pre > 0, (
        "non-vacuity witness: `origin/dev` carries no accented line in the slice, so the "
        "RED would be spurious")
    print("witness: origin/dev pre-state carries %d accented lines over %d files"
          % (pre, len(SLICE_FILES)))

    for rel in SLICE_FILES:
        cible = clone["dir"] / rel
        cible.write_text(pre_state[rel], encoding="utf-8")

    for rel in SLICE_FILES:
        cible = clone["dir"] / rel
        avant = sha256(cible)
        txt = cible.read_text(encoding="utf-8")
        n_avant = len(accented_lines(txt.splitlines()))
        out = []
        for ch in txt:
            if ch in map_:
                out.append(map_[ch])
            elif ch in ACCENTS:
                d = unicodedata.normalize("NFD", ch)
                out.append("".join(c for c in d if not unicodedata.combining(c)))
            else:
                out.append(ch)
        cible.write_text("".join(out), encoding="utf-8")
        apres = sha256(cible)
        n_apres = len(accented_lines(cible))
        print("witness: %s sha256 %s -> %s ; accented lines %d -> %d"
              % (rel, avant[:12], apres[:12], n_avant, n_apres))
        assert avant != apres, "mutation NOT applied: %s" % rel
        assert n_apres == 0, "the strip left diacritics in %s: %d" % (rel, n_apres)

    p = scan(SLICE_FILES, cwd=clone["dir"])
    assert p.returncode == 0, (
        "on a translated slice the scan must be GREEN (rc 0), got %d\n"
        + resume(p, "scan(slice traduite)"))

    bench = _run([sys.executable, "-m", "pytest",
                  "tests/test_issue2_plate_reproducible.py", "-q"], cwd=clone["dir"])
    sortie = out_of(bench)
    assert bench.returncode != 0, (
        "MEASURED INTERACTION: the slice-1 bench asserts the live tree against the "
        "ratified plate's ledger, so a translated slice must turn it red until the "
        "ledger is updated. It stayed green — the guard did not fire.\n%s"
        % sortie[-3000:])
    nommes = [rel for rel in SLICE_FILES if rel in sortie]
    assert nommes, (
        "the guard must NAME the files whose accented lines no longer match the ledger; "
        "none of %r appears in its output:\n%s" % (SLICE_FILES, sortie[-3000:]))
    print("witness: slice-1 bench rc=%d, names %r" % (bench.returncode, nommes))
