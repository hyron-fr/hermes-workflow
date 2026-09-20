"""Slice 6 (skill gh-kanban-bridge) — language RED bank: the three translated
documents must come out English, and the frozen literals they cite must survive
verbatim.

Subject of this card: `skills/gh-kanban-bridge/SKILL.md`,
`skills/gh-kanban-bridge/references/SOUL-template.md`,
`skills/gh-kanban-bridge/references/setup.md` — the three documents `dev-6`
translates. The bank never edits them: it only measures them.

Contract executed here (same form as the slice-2 bank and the sibling banks of this
issue):

    python3 pipeline/pj_lang_lint.py [--exclusions F] [<path> ...]

- rc 0 = compliant AND silent (stdout and stderr both empty);
- rc 1 = at least one line carrying a diacritic outside a frozen span, each line
  naming `path:line`;
- rc 2 = usage error (reserved for source facts, never for a violation).

What this bank proves, and what it does NOT
-------------------------------------------

The diacritic scan is NECESSARY but not SUFFICIENT, and on this slice the gap is
large and measured: at origin/dev the three files carry 39 + 58 + 41 = 138 accented
lines over 342 lines, so 204 further lines carry no diacritic at all — and 6 of those
are French prose the scan cannot see (`- Les outils hermes-discord ne sont PAS
disponibles dans les sessions cron/CLI` needs no accent to be French). So this bank
carries a second, LEXICAL control, calibrated by measurement over TWO English corpora:

- candidates: the accent-free lines of the files the ratified plate declares already
  English (`plate-ledger.outside_corpus`, 202 accent-free lines), plus the 319 lines of
  slice 3, which the SAME pipeline already translated and committed;
- detector: a word-bounded list of French-only function words (no English homograph);
- threshold K = 2 distinct tokens per line. Measured: 2 false positives at K = 1 on the
  plate zone (both lines QUOTE French words), 0 on slice 3; 0 at K = 2 and 0 at K = 3 on
  both corpora — 521 English lines, zero false positive. Inside the slice K = 1 flags 25
  lines, K = 2 flags 6, K = 3 flags 0: K = 2 is the measured crossing point, not a
  preference, and at K = 3 the control would measure nothing at all.

Low recall, stated: at K = 2 the control flags 6 of the 204 accent-free lines of the
slice. It is a guard against the worst half-translations, never a completeness proof;
the diff review stays required in `conv-6`.

Why the LIMIT case is the one that matters here
-----------------------------------------------

The scan BLANKS the spans of the declared frozen literals before reporting, so a
translation that also translates a frozen literal goes GREEN — measured on a throwaway
clone, in this order: the three files placed in the ideal translated state leave the
scan `rc=0`, silent, then `Importé depuis` replaced by its English form leaves it
`rc=0`, silent, still. Nothing in the scan can see that defect, and the bridge READS
that literal (`pipeline/gh_kanban_bridge.py:308`, `pipeline/pj_pipeline_deployer.py:270`):
translating it makes the bridge silent, with no error. So the frozen literals cited by
this slice are re-read from the exclusions file by the bank itself and REQUIRED,
character for character, in the translated tree — and the blindness pair (scan GREEN /
control RED on the SAME clone, in the same run, each half asserted) is executed, not
argued.

The other measured blind spot, carried here as a finding and NOT as an acceptance
criterion: the slice also cites strings produced by tracked code that the exclusions
file does not freeze — `[DÉCISION BOUTON] go — issue #N` (emitted by
`plugins/gh-triage-buttons/__init__.py:48`, documented as the routed message in
`SOUL-template.md:70`) and `[setup] terminé` (`setup.md:156`; `setup.sh:47` prints
`[setup] ` through `log()` before `terminé. board=…`). Translating either makes the
document describe a message the code does not send. Widening the exclusions file is a
contract decision that belongs to `conv-6`/the human, not to this bank: this slice's
guard-rail names only the two protocols as non-translatable, so freezing these two
would be a bank deciding an arbitration the graph owns.

The same rule applies to `- Langue : français.` (`SOUL-template.md:83`): it is an
INSTRUCTION to a live agent, not prose about it. Translating it moves the bot to
English, deleting it leaves the bot without a declared language. This bank therefore
requires the directive to survive in SOME form, prints the language it names, and
proves the deletion is detectable — the product decision itself is `conv-6`'s.

Measured interaction carried here (it belongs to `conv-6`'s arbitration)
-----------------------------------------------------------------------

`tests/test_issue2_plate_reproducible.py` (slice 1) asserts the live tree against the
ratified plate's `plate-ledger` per-file numbers, and slice 6 is declared there with
39 / 58 / 41 accented lines over 77 / 98 / 167 lines. Translating the slice therefore
turns 4 of its 23 cases red until the ledger entry moves in the SAME commit — measured
on a throwaway clone: `4 failed, 19 passed`, the failure text naming the three files and
both figures. `test_limite_le_registre_de_la_planche_suit_la_slice` executes that rule
on the ledger directly (accents AND lines, per file), and proves it bites by mutating
its own clone, so the arbitration is argued on a measurement rather than on a guess.

Scope of the bank: the three files of THIS slice only. A bank covering the whole corpus
would be red for reasons owned by the other slices, and no slice could converge.
`tests/**` is the only write perimeter of this card (peer programming: `dev-6` owns the
sources in the same worktree).
"""
import hashlib
import re
import shutil
import subprocess
import sys
import unicodedata
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

# Slice 6, as declared by the plan (`slices.json`, `slices[5]`) and by the ratified
# plate's ledger. Frozen here on purpose: the bank validates neither the plan by itself
# nor the ledger by itself.
SLICE_K = 6
SLICE_FILES = [
    "skills/gh-kanban-bridge/SKILL.md",
    "skills/gh-kanban-bridge/references/SOUL-template.md",
    "skills/gh-kanban-bridge/references/setup.md",
]

# Character class of the contract: latin letters carrying a diacritic or a latin
# ligature, lowercase AND uppercase. Same class as the sibling banks and the plate's
# `character_class_chars` — re-declared here instead of imported from the subject, so a
# subject that widens its own class cannot widen the bank's.
ACCENTS = "àâäçéèêëîïôöùûüÿœæñÀÂÄÇÉÈÊËÎÏÔÖÙÛÜŸŒÆÑ"
LIGATURES = {"œ": "oe", "æ": "ae", "Œ": "OE", "Æ": "AE"}

# The two and only frozen machine protocols, as the ratifier names them.
PROTOCOLES = ["Importé depuis", "ROOM:"]

# French-only function words: no English homograph. Calibrated — see the module
# docstring. This list belongs to the BANK's lexical control, never to the scan (whose
# exemptions live in the versioned exclusions file, and would be widened by a word list).
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

# The baseline state the citations are enumerated from: the pre-translation tree, which
# is what says WHICH frozen literal this slice quotes and where.
BASE_REF = "origin/dev"


# --------------------------------------------------------------------------- tools


def _run(cmd, cwd=None):
    return subprocess.run(cmd, cwd=str(cwd) if cwd else None,
                          capture_output=True, text=True, timeout=300)


def _require_outils():
    """Explicit RED when the slice-2 deliverable (the scan) is missing."""
    manquants = [rel for rel, p in ((TOOL_REL, TOOL), (EXCLUSIONS_REL, EXCLUSIONS))
                 if not p.is_file()]
    if manquants:
        pytest.fail(
            "upstream deliverable of slice 2 absent from the tree: %s\n"
            "this bank is written BEFORE the translation (peer programming test || "
            "dev): this failure is the expected RED." % ", ".join(manquants))


def scan(paths=(), cwd=REPO, exclusions=EXCLUSIONS):
    """Run the scan. CompletedProcess: rc IS the contract."""
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


def git(*args, cwd=REPO):
    p = _run(["git", "-C", str(cwd), *args])
    assert p.returncode == 0, "git %s failed: %s" % (" ".join(args), p.stderr)
    return p.stdout


def baseline(rel):
    """The pre-translation content of a slice file — the citation inventory."""
    p = _run(["git", "-C", str(REPO), "show", "%s:%s" % (BASE_REF, rel)])
    assert p.returncode == 0, (
        "%s absent de %s : %s" % (rel, BASE_REF, p.stderr.strip()[:200]))
    return p.stdout


def lines_of(root, rel):
    return (Path(root) / rel).read_text(encoding="utf-8").splitlines()


def accented_lines(lines):
    return [n for n, l in enumerate(lines, 1) if any(c in ACCENTS for c in l)]


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def tracked_md(root=REPO):
    """Canonical enumeration: `git ls-files '*.md'`, never a directory walk."""
    p = subprocess.run(["git", "-C", str(root), "ls-files", "-z", "*.md"],
                       capture_output=True)
    assert p.returncode == 0, p.stderr.decode()
    return sorted(x.decode("utf-8") for x in p.stdout.split(b"\x00") if x)


def sans_accent(txt):
    """Accent-free form: what a 'décatie' citation of a frozen literal looks like."""
    d = unicodedata.normalize("NFD", txt)
    return "".join(c for c in d if unicodedata.category(c) != "Mn")


def deaccent(txt, garder=()):
    """The ideal translated state: prose loses its diacritics, `garder` is restored."""
    out = []
    for ch in txt:
        if ch in LIGATURES:
            out.append(LIGATURES[ch])
        elif ch in ACCENTS:
            out.append(sans_accent(ch))
        else:
            out.append(ch)
    txt = "".join(out)
    for lit in garder:
        txt = txt.replace(sans_accent(lit), lit)
    return txt


def rendre_propre_au_scan(root):
    """Put the slice in a state the SCAN reports clean, inside `root`.

    Two steps, both mechanical: the prose loses its diacritics (with the declared frozen
    literals restored), and the accented residues that a tracked CODE file carries
    verbatim are replaced by an accent-free form. The helper is IDEMPOTENT: on a tree
    that is already scan-clean it changes nothing, and that is not an error — the witness
    this helper owes is the resulting scan, not a hash it cannot produce.

    The second step is a convenience of the fixture, never a claim about the product:
    it is what isolating the ERROR case's single source requires. Whether the shipped
    document may translate a code-carried literal is `conv-6`'s arbitration, and the
    `litteraux_machine` control reports it separately.

    Returns ({rel: (sha256_before, sha256_after)}, [(rel, token)]).
    """
    machine = {}
    for rel, num, span, tok, _ in litteraux_machine(root):
        machine.setdefault(rel, set()).add(tok)
    hashes, remplaces = {}, []
    for rel in SLICE_FILES:
        f = Path(root) / rel
        avant = sha256(f)
        txt = deaccent(f.read_text(encoding="utf-8"), garder=PROTOCOLES)
        for tok in sorted(machine.get(rel, ()), key=len, reverse=True):
            if tok in txt:
                txt = txt.replace(tok, sans_accent(tok).replace(" ", "-"))
                remplaces.append((rel, tok))
        f.write_text(txt, encoding="utf-8")
        hashes[rel] = (avant, sha256(f))
    return hashes, remplaces


# Punctuation trimmed off a token before it is matched against the code's own literals.
TRIM_CHARS = "`*_\"'()[]{}.,;:!?«»…—–-"


def residual(line, literals):
    """The line minus every frozen span: whatever is left is prose to be judged."""
    for lit in literals:
        if lit:
            line = line.replace(lit, "")
    return line


# --------------------------------------------------------- literals emitted by code

CODE_GLOBS = ["*.py", "*.sh", "*.yaml", "*.yml", "*.js", "*.cjs", ".mjs", "*.example"]
# Inline code (backticks) only. Bold emphasis is PROSE the translation must rewrite;
# backticks are the document CITING a machine-readable form. Measured on the baseline:
# the bold spans yield 13 ordinary French words (`Créer`, `Priorité`, `terminé` used as
# a verb, ...) that happen to appear inside some string literal, and one shared basename
# (`__init__.py`) then credits them all — an artefact, not an emission contract.
CITATION_BACKTICK = re.compile(r"`([^`\n]*)`")
QUOTED_STRING = re.compile(r"\"([^\"\n]*)\"|'([^'\n]*)'")
# A renvoi au code: a repo path, optionally with the line number inside that file.
RENVOI_CODE = re.compile(r"([\w./-]+\.(?:py|sh|yaml|yml|js|cjs|mjs))(?::(\d+))?")
# Lines that EMIT a message rather than merely contain one.
EMISSION = re.compile(r"\b(echo|printf|log|print|warn|error|notify|announce|send|"
                      r"instruction_for|emit|append|body|summary|msg|message)\b")


def _quoted_strings(txt):
    out = []
    for m in QUOTED_STRING.finditer(txt):
        out.append(m.group(1) if m.group(1) is not None else m.group(2))
    return out


def _code_files():
    """Tracked non-test code files: where a machine literal is emitted or matched."""
    globs = ("py", "sh", "yaml", "yml", "js", "cjs", "mjs", "example")
    return [r for r in git("ls-files").splitlines()
            if r.endswith(tuple("." + g for g in globs)) and not r.startswith("tests/")]


def litteraux_machine_baseline():
    """[(rel, line, span, token, emitters)] — the machine literals of the BASELINE.

    A candidate is an ACCENTED INLINE-CODE CITATION of a slice file at `origin/dev`
    whose accented token sits inside a quoted string literal of a tracked code file.
    Both halves are required: the document must cite a machine-readable form (backticks,
    not emphasis), and a program must carry that form in a string (so translating it
    leaves the document describing a message nothing emits).

    Measured on the slice (this figure is MEASURED by a probe, never hand-kept — an
    earlier revision of this docstring claimed 3 sites including two `[DÉCISION BOUTON]`
    citations; the rule as written selects ONE): `[setup] terminé` (setup.md:156 at
    `origin/dev`), the completion line `skills/gh-kanban-bridge/scripts/setup.sh:177`
    prints (`log "terminé. board=..."`). The `[DÉCISION BOUTON]` examples live in a bold
    emphasis span, not an inline-code citation, and the rule reads citations
    (`CITATION_BACKTICK`) only — deliberately, because bold emphasis is prose the
    translation must rewrite while backticks are the document CITING a machine form.

    The inventory is taken at `origin/dev` and NOT on the live tree: once the translation
    lands, the citations are gone from the documents and a live-only rule would return an
    empty set — the case would then pass for having nothing to look at.
    """
    return litteraux_machine(lambda rel: baseline(rel))


def _lecteur(source):
    """`lire(rel) -> str` — from a ROOT DIRECTORY or from a reader function.

    The rule needs two sources: the live tree of the shared worktree, and the
    pre-translation baseline read out of git (`origin/dev`). Passing the root path for
    the first and a `lambda` for the second keeps every call site readable, and this
    helper is where the two are reconciled — a caller that hands a path where a callable
    is expected is a bank defect, not a finding about the subject.
    """
    if callable(source):
        return source

    def lire(rel):
        return (Path(source) / rel).read_text(encoding="utf-8", errors="replace")

    return lire


def litteraux_machine(source):
    """The same rule applied to a source of file texts (root directory OR `lire(rel)`)."""
    lire = _lecteur(source)
    lits = declared_literals()[0]
    code = _code_files()
    txt = {}
    for r in code:
        try:
            txt[r] = (Path(REPO) / r).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
    quoted = {r: _quoted_strings(t) for r, t in txt.items()}
    out = []
    for rel in SLICE_FILES:
        for num, ligne in enumerate(lire(rel).splitlines(), 1):
            for m in CITATION_BACKTICK.finditer(ligne):
                span = m.group(1).strip()
                if not span or span in lits or not any(c in ACCENTS for c in span):
                    continue
                for tok in re.split(r"[\s|]+", span):
                    tok = tok.strip(TRIM_CHARS)
                    if len(tok) < 4 or not any(c in ACCENTS for c in tok):
                        continue
                    emetteurs = []
                    for r in sorted(quoted):
                        if not any(tok in q for q in quoted[r]):
                            continue
                        for nn, line in enumerate(txt[r].splitlines(), 1):
                            if not EMISSION.search(line):
                                continue
                            if any(tok in q for q in _quoted_strings(line)):
                                emetteurs.append("%s:%d" % (r, nn))
                    if emetteurs:
                        out.append((rel, num, span, tok, emetteurs))
    vus, uniq = set(), []
    for rel, num, span, tok, em in out:
        if (rel, num, tok) in vus:
            continue
        vus.add((rel, num, tok))
        uniq.append((rel, num, span, tok, em))
    return uniq


def _renvoi_code(txt, emetteurs):
    """The document's POINTER to the code carrying the literal, or None.

    A renvoi is a pointer, and a pointer must point somewhere real: the document names
    the emitter's repo path, or its basename WITH a line number that is really one of
    the lines where that file carries the literal. A bare basename proves nothing —
    `__init__.py` is shared by many plugins, so it would credit any unrelated citation —
    and that is why only those two forms are admitted.
    """
    for e in emetteurs:
        chemin, _, lnum = e.rpartition(":")
        base = Path(chemin).name
        if chemin in txt:
            return "%s (chemin nommé)" % chemin
        for m in RENVOI_CODE.finditer(txt):
            cite, ligne = m.group(1), m.group(2)
            if Path(cite).name != base:
                continue
            if ligne is not None and ligne == lnum:
                return "%s:%s (cité, ligne d'émission vérifiée)" % (base, ligne)
    return None


def sort_des_litteraux_machine(root=REPO):
    """[(rel, line, span, token, verdict, evidence)] — what `root` did with each literal.

    The inventory is the BASELINE's (`origin/dev`), because that is where the citations
    exist to be counted; the verdict is read on `root`.

    Three outcomes are admissible, and only three:
    - `verbatim` — the citation survives (kept or frozen in the exclusions file);
    - `renvoi` — the literal is gone but the document now names the code that carries it
      (`_renvoi_code`);
    - `perdu` — gone with nothing pointing at the code: the instruction to recognise a
      real message was deleted rather than translated. The only failing outcome.
    """
    out = []
    for rel, num, span, tok, em in litteraux_machine_baseline():
        txt = "\n".join(lines_of(root, rel))
        if tok in txt or span in txt:
            out.append((rel, num, span, tok, "verbatim", span))
            continue
        cible = _renvoi_code(txt, em)
        out.append((rel, num, span, tok, "renvoi" if cible else "perdu", cible or em[0]))
    return out


def non_attribuables(root):
    """[(rel, line, text)] — accented residues that NO tracked code carries.

    These are ordinary French prose left in the document: the scan reports them, and
    nothing can explain them away. This is the set that must be empty.
    """
    lits = declared_literals()[0]
    machine = {(rel, num) for rel, num, _, _, _ in litteraux_machine(root)}
    out = []
    for rel in SLICE_FILES:
        for num, ligne in enumerate(lines_of(root, rel), 1):
            reste = residual(ligne, lits)
            if not any(c in ACCENTS for c in reste):
                continue
            if (rel, num) in machine:
                continue
            out.append((rel, num, reste.strip()[:90]))
    return out


# --------------------------------------------------------------------- exclusions


def declared_literals():
    """(literals, raw text) — the exclusions file read INDEPENDENTLY of the scan.

    Asking the scan which spans it blanks would let a widened exemption pass unnoticed,
    and that is precisely the bypass this bank exists to refuse.
    """
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


def citations_baseline():
    """{rel: {literal: [line numbers]}} — what this slice cites at origin/dev.

    Measured, never hand-written: a hand-kept list of citations drifts the moment the
    document is re-read, and it would silently stop covering the slice.
    """
    lits = declared_literals()[0]
    out = {}
    for rel in SLICE_FILES:
        txt = baseline(rel)
        per = {}
        for lit in lits:
            sites = [n for n, l in enumerate(txt.splitlines(), 1) if lit in l]
            if sites:
                per[lit] = sites
        out[rel] = per
    return out


def citations_manquantes(root):
    """[(rel, literal, baseline lines)] — frozen literals the tree no longer carries."""
    ecarts = []
    for rel, per in citations_baseline().items():
        txt = "\n".join(lines_of(root, rel))
        for lit, sites in per.items():
            if lit not in txt:
                ecarts.append((rel, lit, sites))
    return ecarts


def citations_decatiees(root):
    """[(rel, line, literal, text)] — a frozen literal cited without its diacritic."""
    lits = declared_literals()[0]
    ecarts = []
    for rel in SLICE_FILES:
        for n, line in enumerate(lines_of(root, rel), 1):
            for lit in lits:
                if lit in line:
                    continue
                if sans_accent(lit) in sans_accent(line):
                    ecarts.append((rel, n, lit, line.strip()[:110]))
    return ecarts


# ------------------------------------------------------------------------ lexical



def offenders(root, rel):
    """[(line, sorted tokens, text)] for the accent-free French lines of `rel`."""
    hits = []
    for n, line in enumerate(lines_of(root, rel), 1):
        if any(c in ACCENTS for c in line):
            continue  # the scan reports these; this control judges the rest
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
    import json
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


def sync_ecarts(root):
    """[(rel, field, declared, measured)] — the ledger against the tree it describes.

    The plate's ledger carries per-file `lines` and `accented_lines`; the slice-1 bench
    compares them to the live tree. A translation that moves one without the other is
    the intermediate state that bench reports as a failure, so the rule is executed here
    directly, on both fields, before the interaction is argued in `conv-6`.
    """
    rec = ledger_slice()
    files = rec.get("files") or {}
    assert isinstance(files, dict), (
        "slice %d: `files` is not a path->numbers mapping in the ledger: %r"
        % (SLICE_K, files))
    ecarts = []
    for rel in SLICE_FILES:
        entry = files.get(rel)
        if not isinstance(entry, dict):
            ecarts.append((rel, "entrée", "présente", "absente"))
            continue
        lignes = lines_of(root, rel)
        for champ, mesure in (("lines", len(lignes)),
                              ("accented_lines", len(accented_lines(lignes)))):
            declare = entry.get(champ)
            if declare != mesure:
                ecarts.append((rel, champ, declare, mesure))
    return ecarts


def _etat_traduit():
    """Precondition of the nominal cases: the slice IS translated.

    The bank is written BEFORE the translation (peer programming test || dev, same
    worktree): until `dev-6` delivers, this failure IS the expected RED.

    It fails on the residues NO tracked code carries — ordinary French prose, which
    nothing can explain away — and it PRINTS, without failing, the residues a tracked
    code file carries verbatim. Those are the arbitration this card must not decide: an
    accented literal read by code (e.g. the message a shell script prints) cannot be
    translated by the document alone, and it is not in the exclusions file either. Both
    lists are printed so the RED is actionable and the arbitration is visible.
    """
    _require_outils()
    absents = [rel for rel in SLICE_FILES
               if not (REPO / rel).is_file() or rel not in tracked_md(REPO)]
    if absents:
        pytest.fail("slice file(s) absent from the disk or the index: %s\n"
                    "tracked corpus: %r" % (", ".join(absents), tracked_md(REPO)))

    total = 0
    for rel in SLICE_FILES:
        total += len(accented_lines(lines_of(REPO, rel)))

    machine = litteraux_machine(REPO)
    for rel, num, span, tok, em in machine:
        print("witness littéral machine (arbitrage conv-6) : %s:%d %r porté par %r"
              % (rel, num, tok, em[:3]))

    restes = non_attribuables(REPO)
    if restes:
        pytest.fail(
            "slice 6 NOT translated: %d accented line(s), %d of them outside a frozen "
            "span AND carried by no tracked code (ordinary French prose).\n  - %s\n"
            "(%d further accented residue(s) are cited verbatim by tracked code: see the "
            "`witness littéral machine` lines above — those are conv-6's arbitration, "
            "not this card's)\n"
            "(the bank is written BEFORE the translation: this failure is the expected "
            "RED)"
            % (total, len(restes), "\n  - ".join("%s:%d — %s" % r for r in restes[:8]),
               len(machine)))


# ------------------------------------------------------------------------ fixtures


@pytest.fixture(scope="module")
def clone_base(tmp_path_factory):
    """Throwaway clone at the branch's commit: mutations never touch the live tree."""
    _require_outils()
    commit = git("rev-parse", "HEAD").strip()
    d = tmp_path_factory.mktemp("slice6") / "clone"
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
    for rel in SLICE_FILES:
        assert (d / rel).is_file(), "the clone does not carry %s" % rel
    return {"dir": d, "commit": clone_base["commit"]}


def scan_rel(ctx, *rels):
    """Scan the named subjects INSIDE the clone, from the clone's own root."""
    return scan([r for r in rels], cwd=ctx["dir"])


# ------------------------------------------------------------------------ nominal


def test_nominal_le_scan_sort_0_et_muet_sur_les_trois_fichiers_de_la_slice():
    """Nominal: rc 0 AND silent on the three files of the slice.

    The two halves are one contract: a scan that prints a report while returning 0 is
    not compliant with it either.
    """
    _etat_traduit()
    p = scan(SLICE_FILES)
    assert p.returncode == 0, (
        "the three translated documents must scan clean\n" + resume(p, "scan(slice)"))
    assert out_of(p).strip() == "", (
        "rc 0 must be SILENT (stdout AND stderr empty)\n" + resume(p, "scan(slice)"))


def test_nominal_le_scan_sans_argument_ne_nomme_plus_la_slice_dans_tout_l_arbre():
    """Nominal, enumeration branch: the no-argument form takes another code path
    (`git ls-files` over the whole corpus) and must not name any of the three files.

    The assertion on the NAMED files is separate from rc: while the other slices are
    still French the whole-corpus scan legitimately returns 1, and the slice's own
    contribution is what this case isolates. Comparison is on the exact relative path,
    never on a basename — `pipeline/README.md` is another slice's file.
    """
    _etat_traduit()
    p = scan()
    noms = {m.group(1) for l in out_of(p).splitlines()
            for m in [re.search(r"([\w./-]+\.md):(\d+)", l)] if m}
    fautifs = sorted(noms & set(SLICE_FILES))
    assert not fautifs, (
        "the whole-corpus scan still names the slice's files: %r\n%s"
        % (fautifs, out_of(p)))
    assert p.returncode in (0, 1), resume(p, "scan() → 0 (compliant) or 1 (elsewhere)")
    print("witness slice translated: %d tracked .md, %d file(s) named outside the slice"
          % (len(tracked_md(REPO)), len(noms)))


def test_nominal_les_trois_fichiers_sont_ceux_declares_et_la_structure_est_intacte():
    """Nominal, perimeter: the slice is the plan's, the files are tracked, and the
    translation did not restructure the documents.

    A translation REWRAPS prose; it does not merge sections or drop blocks. The plate's
    per-file line count is the ratified reference for that, so a structural change must
    be visible in the ledger (covered by the ledger case) rather than silent here.
    """
    declare = sorted(str(k) for k in (ledger_slice().get("files") or {}))
    assert declare == sorted(SLICE_FILES), (
        "plate slice %d declares %r, the slice is %r"
        % (SLICE_K, declare, sorted(SLICE_FILES)))
    for rel in SLICE_FILES:
        assert (REPO / rel).is_file(), "%s absent: %s" % (rel, REPO / rel)
        assert rel in tracked_md(REPO), (
            "%s is not tracked by the index: the bank would measure a file the branch "
            "does not carry" % rel)
    total = sum(len(lines_of(REPO, rel)) for rel in SLICE_FILES)
    acc = sum(len(accented_lines(lines_of(REPO, rel))) for rel in SLICE_FILES)
    assert total > 0, "the slice carries no line at all"
    print("witness perimeter: %d lines over 3 files, %d accented at the instant of the "
          "measurement" % (total, acc))


# ------------------------------------------------------------------------- limite


def test_limite_les_litteraux_geles_cites_par_la_slice_sont_restes_verbatim():
    """Limit: every frozen literal the slice cites is still present, character for
    character — read from the exclusions file by the bank, never asked to the scan.

    Two halves: the literal is still there, and it is not there in a DÉCATIE form (the
    accent stripped), which is what a partial translation of a quoted protocol leaves
    behind. The citation inventory itself is measured at `origin/dev`.
    """
    _etat_traduit()
    lits = declared_literals()[0]
    for prot in PROTOCOLES:
        assert prot in lits, (
            "the frozen protocol %r is no longer declared in %s: without it a correct "
            "citation of the corpus would be reported as French" % (prot, EXCLUSIONS_REL))

    cites = citations_baseline()
    total = sum(len(v) for per in cites.values() for v in per.values())
    assert total > 0, (
        "non-vacuity: the slice cites none of the declared literals %r at %s, so this "
        "case would measure nothing" % (lits, BASE_REF))

    manquants = citations_manquantes(REPO)
    assert not manquants, (
        "frozen literal(s) cited by the slice and no longer present verbatim:\n  - "
        + "\n  - ".join("%s: %r (cité %s au %s)"
                        % (rel, lit, sites, BASE_REF)
                        for rel, lit, sites in manquants))
    ecarts = citations_decatiees(REPO)
    assert not ecarts, (
        "frozen literal cited in a DÉCATIE form (diacritic lost):\n  - "
        + "\n  - ".join("%s:%d %r in %r" % e for e in ecarts))
    print("witness citations: %r, cited by %d file(s), %d site(s) at %s"
          % (lits, len([r for r, per in cites.items() if per]), total, BASE_REF))


def test_limite_la_transcription_du_litteral_gele_est_invisible_au_scan_et_vue_ici(clone):
    """Limit, the blindness pair — BOTH halves in one run, on a throwaway clone.

    The scan removes the declared spans before judging, so a translation that also
    translates the literal goes GREEN: nothing in the scan can see that defect, and the
    bridge READS that literal (`gh_kanban_bridge.py:308`, its silent failure mode).

    The pair is measured on ONE state, in this order: the clone is put in a state the
    scan reports clean (positive control, asserted), and only THEN is the frozen literal
    translated. A state where French remains elsewhere would return rc 1 for that reason
    and prove nothing about blindness.
    """
    # 1. positive control: a scan-clean state. `rendre_propre_au_scan` is idempotent, so
    # this holds both before and after dev-6's translation lands.
    _hashes, remplaces = rendre_propre_au_scan(clone["dir"])
    p0 = scan_rel(clone, *SLICE_FILES)
    assert p0.returncode == 0 and out_of(p0).strip() == "", (
        "positive control: the scan-clean state must be rc 0 and silent before the "
        "literal is touched; without it a later rc 0 proves nothing\n"
        + resume(p0, "scan(slice, état propre au scan)"))
    assert not citations_manquantes(clone["dir"]), (
        "positive control: the frozen literals must be intact at this point")
    print("witness état propre: %d résidu(s) retiré(s) %r -> scan rc=0 muet, citations "
          "intactes" % (len(remplaces), remplaces))

    # 2. the defect: the frozen literal itself is translated.
    rel = "skills/gh-kanban-bridge/SKILL.md"
    cible = clone["dir"] / rel
    avant_lit = sha256(cible)
    texte = cible.read_text(encoding="utf-8")
    remplacement = texte.replace("Importé depuis", "Imported from")
    n_occurrences = texte.count("Importé depuis")
    assert n_occurrences and remplacement != texte, (
        "mutation NOT applied: %r carries no occurrence of the frozen literal" % rel)
    cible.write_text(remplacement, encoding="utf-8")
    apres_lit = sha256(cible)
    print("witness mutation: %s sha256 %s -> %s, %d occurrence(s) du littéral traduite(s)"
          % (rel, avant_lit[:12], apres_lit[:12], n_occurrences))
    assert apres_lit != avant_lit, "mutation NOT applied (hash witness): %s" % avant_lit

    p = scan_rel(clone, *SLICE_FILES)
    assert p.returncode == 0 and out_of(p).strip() == "", (
        "witness of the blind spot: with the frozen literal TRANSLATED the scan must "
        "still be GREEN and silent — it blanks the span before judging, and the "
        "translated form carries no diacritic. It was not, so 'the scan cannot see this' "
        "is not established on this state\n" + resume(p, "scan(slice, littéral traduit)"))

    manquants = citations_manquantes(clone["dir"])
    assert manquants, (
        "the citation control did NOT see the translated frozen literal while the scan "
        "was green: the guard is blind and this bank's limit case proves nothing")
    assert any(r == rel for r, _, _ in manquants), (
        "the control must name the file whose literal was translated; named: %r"
        % [(r, l) for r, l, _ in manquants])
    print("witness paire d'aveuglement: scan rc=0 MUET et contrôle de citation ROUGE sur "
          "%r — la transcription du protocole est invisible au scan" % (manquants[0][:2],))


def test_limite_le_registre_de_la_planche_voit_la_slice_traduite_et_nomme_les_deux_champs(clone):
    """Limit: the plate's ledger rule BITES on a translated slice — executed on a clone,
    never asserted against the live tree.

    The slice-1 bench compares the ledger's per-file `lines` and `accented_lines` to the
    live tree, so a translation and its ledger entry belong to the same commit. This case
    does NOT require the live tree to be in sync — the ledger lives in slice 1's artifact
    and editing it is outside this slice's declared perimeter: it requires the RULE to be
    discriminating, and prints the live state so `conv-6` arbitrates on a measurement.

    Both fields are flipped by the SAME run, by two mutations applied to the clone: an
    accented line appended to every file of the slice (flips `accented_lines`), and a
    plain line appended to one of them (flips `lines`). One mutation alone would leave the
    other field unexercised.
    """
    rec = ledger_slice()
    print("witness planche: slice %d déclare %r"
          % (SLICE_K, {r.split("/")[-1]: (rec.get("files") or {}).get(r)
                       for r in SLICE_FILES}))
    live = sync_ecarts(REPO)
    print("witness arbre vivant: %d divergence(s) planche <-> arbre à l'instant de la "
          "mesure — %r (diagnostic, hors périmètre de cette carte)"
          % (len(live), live))

    avant = {}
    for rel in SLICE_FILES:
        f = clone["dir"] / rel
        avant[rel] = sha256(f)
        with f.open("a", encoding="utf-8") as fh:
            fh.write("\nLigne restee en francais, avec un accent.")
    with (clone["dir"] / SLICE_FILES[-1]).open("a", encoding="utf-8") as fh:
        fh.write("\nOne more line, no diacritic at all.\n")
    assert all(sha256(clone["dir"] / r) != avant[r] for r in SLICE_FILES), (
        "mutation NOT applied on every file: sha256 %s"
        % {r.split("/")[-1]: v[:8] for r, v in avant.items()})
    print("witness mutation: 3 fichiers du clone amendés, sha256 %s"
          % {r.split("/")[-1]: v[:8] for r, v in avant.items()})

    ecarts = sync_ecarts(clone["dir"])
    assert ecarts, (
        "the ledger check did not fire on the mutated clone: it cannot fail, so it "
        "cannot be a gate")
    nommes = sorted({rel for rel, _, _, _ in ecarts})
    assert nommes == sorted(SLICE_FILES), (
        "the divergence must name the three files of the slice; named: %r" % nommes)
    champs = {champ for _, champ, _, _ in ecarts}
    assert champs == {"lines", "accented_lines"}, (
        "both fields of the ledger must be exercised in the same run; exercised: %r\n%r"
        % (champs, ecarts))
    print("witness registre: %d divergence(s) nommée(s) sur le clone, champs %r — %r"
          % (len(ecarts), sorted(champs), ecarts))


def test_limite_aucune_prose_francaise_sans_diacritique_ne_subsiste():
    """Limit: the lexical control — French prose that carries no diacritic.

    Measured on the frozen tree: the slice's 342 lines carry 204 accent-free lines, and
    6 of them cross the calibrated threshold K = 2 (`- Les outils hermes-discord ne sont
    PAS disponibles dans les sessions cron/CLI — uniquement dans les sessions gateway`
    is one of them and no diacritic scan can see it). The RED is here, and so is the gap
    the diacritic scan cannot close.
    """
    _require_outils()
    ecarts = []
    vues = 0
    for rel in SLICE_FILES:
        lignes = lines_of(REPO, rel)
        vues += len([l for l in lignes if not any(c in ACCENTS for c in l)])
        for n, toks, txt in offenders(REPO, rel):
            ecarts.append("%s:%d  [%s]  %s" % (rel, n, ",".join(toks), txt[:150]))
    assert vues > 0, "the slice carries no accent-free line: decor vide"
    assert not ecarts, (
        "French prose without any diacritic still survives in the slice (threshold "
        "K>=%d distinct French-only words per line, 0 false positive measured over 521 "
        "lines of English this pipeline produced):\n  " % SEUIL_LEXICAL
        + "\n  ".join(ecarts))
    print("witness lexical: %d ligne(s) sans diacritique balayée(s)" % vues)


def test_limite_la_calibration_du_controle_lexical_est_re_mesuree_sur_deux_corpus():
    """Limit, non-vacuity of the control itself: over English corpora the SAME pipeline
    produced, the detector returns zero.

    A threshold that fired on English prose would be a false-positive machine and no
    translation could ever satisfy it. Two corpora, because they answer different
    questions: the plate's `outside_corpus` is a RATIFIED declaration of what counts as
    already-English, and slice 3 was translated and committed by this very pipeline (319
    lines). The zone comes from the ledger, not from this bank's convenience, and its
    size is asserted non-empty so a shrunken calibration cannot pass silently.
    """
    _require_outils()
    declare = [e.get("path") for e in ledger().get("outside_corpus") or [] if e.get("path")]
    assert declare, ("the plate declares no already-English file (`outside_corpus`), so "
                     "the threshold of this control cannot be calibrated")
    absents = [rel for rel in declare if not (REPO / rel).is_file()]
    assert not absents, "calibration zone cites files absent from the tree: %r" % absents

    # The second corpus is DERIVED, never hardcoded: the files of every slice the plate
    # declares `kind: translate` whose COMMITTED copy (HEAD, not the working tree) now
    # carries zero accented line — i.e. slices this pipeline has already translated.
    # Reading HEAD rather than the working tree keeps the calibration immune to a
    # sibling slice's in-flight edits in the shared worktree.
    recs = ledger().get("slices") or []
    recs = list(recs.values()) if isinstance(recs, dict) else recs
    deja = []
    for rec in recs:
        if str(rec.get("kind")) != "translate":
            continue
        fichiers = rec.get("files") or {}
        noms = sorted(fichiers) if isinstance(fichiers, dict) else sorted(fichiers)
        noms = [r for r in noms if r not in SLICE_FILES]
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

    n_lignes = 0
    faux = []
    for rel in declare + deja:
        lignes = [l for l in lines_of(REPO, rel) if not any(c in ACCENTS for c in l)]
        n_lignes += len(lignes)
        faux.extend((rel,) + o for o in offenders(REPO, rel))
    assert n_lignes >= 30, (
        "calibration corpus too small to prove anything (%d accent-free lines over %d "
        "file(s)): %r" % (n_lignes, len(declare + deja), declare + deja))
    assert not faux, (
        "the lexical detector fires on prose these corpora are declared already English "
        "(%d false positive(s) over %d lines): the control is not discriminant\n  "
        % (len(faux), n_lignes)
        + "\n  ".join("%s:%d %s" % f[:3] for f in faux[:10]))
    print("witness calibration: 0 faux positif sur %d ligne(s) anglaises — %d fichier(s) "
          "déclaré(s) par la planche + %d fichier(s) de slice(s) déjà traduite(s) : %r"
          % (n_lignes, len(declare), len(deja), deja))


def test_limite_la_directive_de_langue_du_gabarit_n_est_pas_supprimee(clone):
    """Limit, anti-rewrite: the language directive of the bot template is not silently
    dropped.

    `SOUL-template.md:83` carries `- Langue : français.` — an INSTRUCTION to a live
    agent, not prose about it: translating it moves the bot to English, deleting it
    leaves the bot without a declared language. Either is a product decision; deleting
    it quietly is a content rewrite, which this slice excludes. This case therefore
    requires the directive to survive in SOME form and PRINTS the language it names, so
    `conv-6` arbitrates the product question on a measurement. The mutation proof is the
    deletion itself, applied to a clone.
    """
    rel = "skills/gh-kanban-bridge/references/SOUL-template.md"
    motif = re.compile(r"(?i)^\s*[-*]?\s*(langue|language)\s*[:=]")
    present = [(n, l.strip()) for n, l in enumerate(lines_of(REPO, rel), 1)
               if motif.search(l)]
    assert present, (
        "%s no longer declares the language its bot must answer in: dropping the "
        "directive is a rewrite of the document's behaviour, not a translation. Looked "
        "for `Langue:|Language:` in %d line(s)." % (rel, len(lines_of(REPO, rel))))
    for n, txt in present:
        print("witness directive de langue: %s:%d %r" % (rel, n, txt))

    cible = clone["dir"] / rel
    avant = sha256(cible)
    lignes = ["" if motif.search(l) else l for l in lines_of(clone["dir"], rel)]
    cible.write_text("\n".join(lignes) + "\n", encoding="utf-8")
    apres = sha256(cible)
    assert apres != avant, "mutation NOT applied: %s" % rel
    assert not [(n, l) for n, l in enumerate(lines_of(clone["dir"], rel), 1)
                if motif.search(l)], (
        "mutation NOT applied: the clone still declares a language (%s -> %s)"
        % (avant[:12], apres[:12]))
    print("witness suppression: directive retirée du clone, sha256 %s -> %s"
          % (avant[:12], apres[:12]))


# ------------------------------------------------------------------------- erreur


def test_limite_les_litteraux_machine_du_baseline_sont_nommes_et_leur_sort_est_trace():
    """Limit, the OTHER blind spot: accented literals the slice cites at `origin/dev`
    that a tracked code file carries verbatim, and that the exclusions file does NOT
    freeze.

    This case does not DECIDE the product question — it measures it and requires the
    outcome to be traceable, so `conv-6` arbitrates on evidence rather than on an
    impression.

    The inventory is taken at `origin/dev` (the baseline the card describes), because
    that is where the citations exist to be counted: measured there, `[setup] terminé`
    (`setup.md:156`) is the completion line `setup.sh:177` prints (`log() { echo "[setup]
    $*"; }` — the prefix is code, the word is the document's), and `[DÉCISION BOUTON] go
    — issue #N` is emitted by `plugins/gh-triage-buttons/__init__.py:48`.

    Three admissible outcomes in the translated tree, and nothing else:
    - the literal is still cited VERBATIM (frozen or kept) — then it must be attributable
      to a code reader/emitter;
    - it was replaced by a NON-VERBATIM reference to the code that emits it (the peer
      measured: `setup.md` now points at `setup.sh:177` rather than quoting the message);
    - it is gone with no replacement anywhere — that is a loss, and this case reds.
    """
    _require_outils()
    citees = litteraux_machine_baseline()
    assert citees, (
        "no accented literal cited at %s is carried by any tracked code file: the "
        "attribution rule has stopped discriminating, re-measure before reading this as "
        "a green" % BASE_REF)
    for rel, num, span, tok, em in citees:
        assert em, "literal %r at %s:%d (%s) has no named emitter" % (tok, rel, num,
                                                                     BASE_REF)
        print("witness littéral machine (baseline): %s:%d %r <- %r"
              % (rel, num, tok, em[:4]))

    sort = sort_des_litteraux_machine(REPO)
    restant = [r for r in sort if r[4] == "verbatim"]
    remplaces_par_renvoi = [r for r in sort if r[4] == "renvoi"]
    perdus = [r for r in sort if r[4] == "perdu"]
    print("witness sort des littéraux machine: %d encore cité(s) verbatim, %d remplacé(s) "
          "par un renvoi au code, %d perdu(s)"
          % (len(restant), len(remplaces_par_renvoi), len(perdus)))
    for rel, num, span, tok, verdict, preuve in restant:
        print("   encore verbatim : %s:%d %r" % (rel, num, tok))
    for rel, num, span, tok, verdict, preuve in remplaces_par_renvoi:
        print("   renvoi au code : %s:%d %r -> %r" % (rel, num, tok, preuve))
    assert not perdus, (
        "accented literal(s) the code carries, cited at %s, and now GONE from the "
        "document with no reference to the code that carries them — the instruction to "
        "recognise a real message was deleted rather than translated:\n  - "
        % BASE_REF
        + "\n  - ".join("%s:%d %r <- %r" % (r[0], r[1], r[3], r[5]) for r in perdus))

    # Non-vacuity of the verdict function itself: it is exercised in BOTH of its
    # discriminating directions on the same corpus, so a rule that answers "renvoi"
    # whatever it is shown (or "perdu" whatever it is shown) cannot pass here.
    rel0, num0, span0, tok0, em0 = citees[0]
    faux = _renvoi_code("nothing of the sort is named in this text", em0)
    assert faux is None, (
        "the renvoi rule credits a text that names neither the emitter's path nor one of "
        "its lines of emission (%r): it cannot discriminate" % faux)
    chemin0 = em0[0].split(":")[0]
    assert chemin0, "emitter %r carries no path: the rule cannot be exercised" % em0[0]
    assert _renvoi_code("see %s for the message" % chemin0, em0) is not None, (
        "the renvoi rule does not credit a text naming the emitter's own repo path: the "
        "verdict can never be 'renvoi'")
    print("witness discrimination du renvoi: chemin nommé -> crédité ; texte quelconque "
          "-> refusé")


def test_erreur_un_fichier_oublie_est_nomme_a_sa_ligne_et_le_scan_sort_1(clone):
    """Error: one of the slice's files is left out of the translation.

    The mutation is APPLIED to the clone and proven twice in the same run (the file's
    sha256 changes AND the scan's rc flips), the other two files are placed in a state
    the scan reports clean so the report has a SINGLE source, and the expected line
    number is MEASURED after the mutation rather than hardcoded.
    """
    hashes, _ = rendre_propre_au_scan(clone["dir"])
    print("witness état propre: 3 fichiers, sha256 %s"
          % {r.split("/")[-1]: h[1][:8] for r, h in hashes.items()})
    p = scan_rel(clone, *SLICE_FILES)
    assert p.returncode == 0 and out_of(p).strip() == "", (
        "positive half: the slice placed in a scan-clean state must be rc 0 and silent\n"
        + resume(p, "scan(slice) avant la mutation"))

    oublie = "skills/gh-kanban-bridge/references/SOUL-template.md"
    cible = clone["dir"] / oublie
    avant_hash = sha256(cible)
    avant_lignes = len(lines_of(clone["dir"], oublie))
    marqueur = "Ajouté à la main par le banc."
    # The appended prose MUST carry diacritics: the scan's contract is "rc 1 = at least
    # one DIACRITIC outside a frozen span", so an accent-free French sentence is invisible
    # to it by construction and could never obtain the rc this case requires. Measured:
    # with an accent-free block the scan returns rc 0 on the mutated clone, and that
    # failure would be the bank's, not the subject's.
    ajout = "Le document est resté en français faute de traduction."
    assert any(c in ACCENTS for c in marqueur + ajout), (
        "the mutation must carry a diacritic, or the scan cannot see it: %r" % ajout)
    with cible.open("a", encoding="utf-8") as fh:
        fh.write("\n%s\n%s\n" % (marqueur, ajout))
    apres_hash = sha256(cible)
    lignes = lines_of(clone["dir"], oublie)
    # The expected line number is MEASURED on the mutated file, never hardcoded: a
    # literal here would fail a correct implementation the day the wording changes.
    n_mutation = next(n for n, l in enumerate(lignes, 1) if marqueur in l)
    print("witness mutation: %s sha256 %s -> %s, %d -> %d lignes, marqueur L%d"
          % (oublie, avant_hash[:12], apres_hash[:12], avant_lignes, len(lignes),
             n_mutation))
    assert apres_hash != avant_hash, "mutation NOT applied: %s" % avant_hash
    assert len(lignes) > avant_lignes

    q = scan_rel(clone, *SLICE_FILES)
    assert q.returncode == 1, (
        "a forgotten file must return rc 1 (violations), got %d\n"
        + resume(q, "scan(slice) avec %s resté français" % oublie))
    assert "%s:%d" % (oublie, n_mutation) in out_of(q), (
        "the forgotten file must be named WITH its line (%s:%d, MEASURED after the "
        "mutation):\n%s" % (oublie, n_mutation, out_of(q)))
    autres = [rel for rel in SLICE_FILES if rel != oublie and rel in out_of(q)]
    assert not autres, (
        "the report must be specific to the forgotten file; it also names %r:\n%s"
        % (autres, out_of(q)))

    r = scan_rel(clone, oublie)
    assert r.returncode == 1, resume(r, "le seul fichier oublié: exit 1")
    for rel in SLICE_FILES:
        if rel == oublie:
            continue
        s = scan_rel(clone, rel)
        assert s.returncode == 0 and out_of(s).strip() == "", (
            "witness: %s est dans l'état traduit idéal et doit être muet\n%s"
            % (rel, resume(s, "scan(%s)" % rel)))
    print("witness oubli: %s:%d nommé, rc=1 ; les 2 autres fichiers -> rc=0 muet"
          % (oublie, n_mutation))
