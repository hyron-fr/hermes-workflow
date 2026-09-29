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

`tests/test_issue2_plate_reproducible.py` (slice 1) asserted the live tree against the
ratified plate's `plate-ledger` per-file numbers. The translation of this slice therefore
made 4 of its 23 cases red until the ledger entry for slice 5 was updated in the same
commit — the premise this bank wrote down when it was RED. SUPERSEDED, 2026-09-26: the
plate-bench was re-architected to judge the FROZEN seal instead of the live tree, and the
slice-5 ledger amendment ships in the same commit as the translation, so translating the
slice no longer turns the bench red — the bench judges the DECLARED delta. Case 5
(`test_erreur_une_slice_deja_traduite_...`) is re-scoped on conv-5 to assert that the
guard STILL fires: it strips the slice-5 amendment entry from a working-tree clone and
requires the bench to red and name slice 5 — so the arbitration (ledger update belongs to
the same commit as the translation) stays argued on a measurement, under the new
semantics.
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


def strip_amendment_slice(clone_dir, k):
    """Remove from the CLONE's working-tree ledger the amendment entries whose
    `slices` list contains `k` — the measured UNDECLARED mutation case 5 exercises.

    Measured, not hand-parsed by eye: the ledger is round-tripped through JSON, the
    entries are filtered, and the strip is proven by re-reading (the entry count must
    drop by exactly the number of removed entries). The mutation touches the CLONE's
    file only — never the parent's `docs/**` (peer perimeter, measured trap of 2026-09-20:
    a `git checkout` aimed at the parent restored files in the PARENT tree).
    """
    plate = Path(clone_dir) / PLATE_REL
    txt = plate.read_text(encoding="utf-8")
    m = LEDGER_RE.search(txt)
    assert m, "no `plate-ledger` machine block in the clone's %s" % PLATE_REL
    ledger = json.loads(m.group("json"))
    amend = (ledger.get("provenance") or {}).get("amendments") or []
    keep = [a for a in amend
            if not (isinstance(a, dict) and k in (a.get("slices") or []))]
    assert len(keep) < len(amend), (
        "nothing to strip: no amendment entry declares slice %d in %s — the mutation "
        "premise no longer holds" % (k, PLATE_REL))
    ledger["provenance"]["amendments"] = keep
    plate.write_text(
        txt[:m.start("json")] + json.dumps(ledger, indent=2, ensure_ascii=False)
        + txt[m.end("json"):], encoding="utf-8")
    m2 = LEDGER_RE.search(plate.read_text(encoding="utf-8"))
    assert m2, "the re-read of the clone's ledger failed after the strip"
    check = json.loads(m2.group("json"))
    assert len(check["provenance"]["amendments"]) == len(keep), \
        "strip not applied in the clone's ledger"


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
    """Error, replayed INSIDE the clone: the undeclared-delta guard must still fire.

    History, measured (conv-5, 2026-09-27): when this case was written it asserted that
    translating the slice turns the slice-1 bench red until the ledger is updated in the
    same commit — true under the pre-2026-09-26 bench, which asserted the live tree
    against the ratified ledger. The bench was re-architected (9c4ad14, t_887e9508) to
    judge the FROZEN seal: its guard compares only the working-tree PLATE against the
    seal and tolerates a divergence ENTIRELY declared in `provenance.amendments[]`
    (guard re-margined on t_6e730cef). Two consequences, both measured:

    - the slice-5 amendment ships in the same commit as the translation (dd689ed), so
      the delivered tree is GREEN — and the SOUL files themselves can no longer turn the
      bench red, because the seal's per-file numbers are a snapshot, not a live assertion
      on the prose;
    - the mutation the guard actually watches is the PLATE: strip the slice-5 amendment
      entry and the guard must red and name slice 5.

    First re-scope attempt (same run, conv-5) asserted the guard on the delivered tree
    alone (bench green, then red after the strip, no intermediate mutation applied to
    anything the guard watches): proven TAUTOLOGICAL — with the guard neutralized the
    case stayed green, i.e. it could not fail. Rejected; the mutation below is the
    non-vacuous form, validated end-to-end in a throwaway clone before commit.

    Assertions, in the SAME run:
    - witness: `origin/dev` pre-state still carries the 145 accented lines (the state
      this card's historical RED was measured against — non-vacuity);
    - the scan turns GREEN on the slice's delivered files (rc 0, silent) — the scan
      contract still holds on the tree under test;
    - NEGATIVE witness: the slice-1 bench is GREEN on the untouched clone — the
      DECLARED delta is accepted, so the RED below is caused by the strip and cannot be
      a bench defect;
    - MUTATION: the slice-5 amendment entry is stripped from the CLONE's working-tree
      ledger (JSON round-tripped, re-read, entry count proven to drop) — never the
      parent's `docs/**` (peer perimeter, measured trap of 2026-09-20);
    - the slice-1 bench turns RED and NAMES slice 5 as diverging without an amendment —
      the guard still fires, so a commit that ships the translation WITHOUT the ledger
      update is caught.
    """
    p = _run([sys.executable, "-m", "pytest",
              "tests/test_issue2_plate_reproducible.py", "-q"],
             cwd=clone["dir"])
    witness_green = out_of(p)
    assert p.returncode == 0, (
        "NEGATIVE witness failed: on the untouched clone (delivered tree + DECLARED "
        "slice-5 amendment) the slice-1 bench must be GREEN — rc=%d\n%s"
        % (p.returncode, witness_green[-2000:]))

    pre_state = {}
    for rel in SLICE_FILES:
        p = _run(["git", "-C", str(REPO), "show", "origin/dev:%s" % rel])
        assert p.returncode == 0, (
            "cannot read the slice's pre-state `origin/dev:%s`: %s" % (rel, p.stderr))
        pre_state[rel] = p.stdout

    pre = sum(len(accented_lines(t.splitlines())) for t in pre_state.values())
    assert pre > 0, (
        "non-vacuity witness: `origin/dev` carries no accented line in the slice, so "
        "the historical RED this card blessed would have been spurious")
    print("witness: origin/dev pre-state carries %d accented lines over %d files"
          % (pre, len(SLICE_FILES)))

    p = scan(SLICE_FILES, cwd=clone["dir"])
    assert p.returncode == 0, (
        "on the delivered slice the scan must be GREEN (rc 0), got %d\n"
        + resume(p, "scan(slice livree)"))
    assert p.stdout.strip() == "" and p.stderr.strip() == "", (
        "rc 0 must be SILENT (stdout AND stderr empty)\n" + resume(p, "scan(slice livree)"))

    strip_amendment_slice(clone["dir"], SLICE_K)
    print("witness: slice-5 amendment stripped from the CLONE's working-tree ledger "
          "(UNDECLARED mutation)")

    bench = _run([sys.executable, "-m", "pytest",
                  "tests/test_issue2_plate_reproducible.py", "-q"], cwd=clone["dir"])
    sortie = out_of(bench)
    assert bench.returncode != 0, (
        "the guard did NOT fire: with the slice-5 amendment stripped from the "
        "working-tree ledger the slice-1 bench must be RED — it stayed green:\n%s"
        % sortie[-3000:])
    assert re.search(r"slice %d\b" % SLICE_K, sortie), (
        "the guard must NAME slice %d as diverging without an amendment; its output "
        "does not:\n%s" % (SLICE_K, sortie[-3000:]))
    assert "amendments" in sortie, (
        "the guard's verdict must attribute the red to the missing "
        "`provenance.amendments[]` declaration:\n%s" % sortie[-3000:])
    print("witness: slice-1 bench rc=%d on the undeclared delta; slice %d named "
          "(guard fires under the re-architected seal semantics)"
          % (bench.returncode, SLICE_K))
