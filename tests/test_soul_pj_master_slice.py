"""Bank for slice 4 of issue #2 — `agents/pj-master/SOUL.md` (RED, card t_a428fcfe).

Subject: one translated document.

    agents/pj-master/SOUL.md

Three properties are executed here, all of them derived from bytes at run time — never
from a number copied out of the dev card:

1. **Nominal** — `pipeline/pj_lang_lint.py --exclusions pipeline/pj_lang_lint.exclusions.yaml
   agents/pj-master/SOUL.md` exits 0 and says nothing: no diacritic survives outside a
   frozen span in the slice file.
2. **Limit** — the contracts the document CITES are still there, character for character:
   the frozen protocols declared by the exclusion file (measured at the reference
   revision and re-counted at HEAD), the `${...}` placeholders, the `PROTOTYPE:`-family
   verdict tokens, the fenced blocks, the script basenames, and the five ENGLISH gate
   titles of the human decision of 20/09. Plus the property the scanner cannot see:
   unaccented French prose.
3. **Error** — a slice file left French is named with rc 1, proven on a throwaway copy
   whose mutation is certified by sha256, and the violation count is recomputed by this
   bank instead of asserted as a literal.

Why the reference revision and not a French copy kept beside the test: the French source
is the commit that ADDED the file (`git log --format=%H -- <path>`, last entry). It is
versioned, so the error scenario can restore the exact French bytes at any later commit
without this bank carrying a fixture that drifts.

Two measured corrections to the card's prose, both re-derived here rather than relayed:

- the card announces "23 citations of the frozen literals"; measured, this document cites
  `ROOM:` **3** times and `Importé depuis` **0** times. The bank therefore does not pin
  the count the card claims: it counts the citations at the reference revision and
  requires HEAD to carry the same number.
- `Hors-scope` carries no diacritic, so it cannot falsify the span rule; the accented,
  genuinely frozen literal available in this document is `ROOM:` on a page that also
  contains other accents — the case below is built on that shape.

No real clock, no randomness: every working directory is a throwaway git repository built
by this bank, and every count is computed from the bytes in hand.
"""
import hashlib
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SLICE_REL = "agents/pj-master/SOUL.md"
TOOL_REL = "pipeline/pj_lang_lint.py"
EXCLUSIONS_REL = "pipeline/pj_lang_lint.exclusions.yaml"
TOOL = REPO / TOOL_REL
EXCLUSIONS = REPO / EXCLUSIONS_REL
SLICE = REPO / SLICE_REL

# Character class of the ratified contract: latin letters carrying a diacritic, plus the
# latin ligatures. Identical to `pipeline/pj_lang_lint.py` and to the slice-1 bench.
ACCENTS = "àâäçéèêëîïôöùûüÿœæñÀÂÄÇÉÈÊËÎÏÔÖÙÛÜŸŒÆÑ"

# The two machine protocols of the 20/09 decision. They must be DECLARED by the exclusion
# file; the bank reads the file to get their bytes, this tuple only states what it expects
# to find and is asserted, not assumed.
PROTOCOLES_ATTENDUS = ("Importé depuis", "ROOM:")

# Gate titles of the human decision of 20/09 (the card linter accepts both sets; the slice
# translates the FRENCH ones). "DoR & DoD" belongs to both sets, so only the four
# FRENCH-ONLY titles are forbidden — forbidding the shared one would forbid a correct
# translation.
TITRES_EN = (
    "Context & Objective",
    "Acceptance criteria",
    "DoR & DoD",
    "Technical considerations",
    "Out of scope",
)
TITRES_FR_UNIQUES = (
    "Contexte & Objectif",
    "Critères d'acceptation",
    "Considérations techniques",
    "Hors-scope",
)

# Documents tracked in this tree that are ALREADY English: the calibration set of the
# unaccented-French detector below. The detector is accepted only if it flags ZERO of
# their lines; a detector that fires on 272 lines of real English is not a detector.
CALIBRATION_REFS = (
    "docs/architecture/README.md",
    "docs/architecture/components/pj-lang-lint.md",
    "docs/architecture/context/issue-2.md",
    "docs/functional/README.md",
)

# French function words that are NOT valid English words. Collisions with English were
# removed on purpose (`a`, `on`, `en`, `son`, `la`, `si`, `car`, `plus`, `y`, `ma`, `me`,
# `no`) — a token that is also English cannot discriminate.
FR_ONLY = frozenset("""
le les un une des du de ne pas que qui dans avec pour par sur tout toute tous etre
est sont et ou au aux ce cet cette ces sa ses leur leurs il elle ils elles tu je
nous vous aussi donc mais comme sans sous entre vers chez lors apres avant deja
encore jamais toujours rien tres peu beaucoup seul seule chaque quel quelle quelque
autre autres doit doivent peut peuvent fait faire avoir ont meme non
""".split())

# Distinct FR_ONLY words on one line, outside code spans, before the line counts as
# French prose. Calibrated at zero false positives over the calibration set (see the
# witness printed by the test); one or two stray words are not judged.
FR_THRESHOLD = 3

TOKEN_RE = re.compile(r"[a-z]+")
CODE_SPAN_RE = re.compile(r"`[^`]*`")
URL_RE = re.compile(r"https?://\S+")
# A QUOTED FRENCH TERM is a citation, not prose: the English note `issue-2.md` illustrates
# the blind spot with « dans », « pour », « rien » — three French tokens quoted on purpose.
# Blanking every quoted span would also hide real prose ("attente réponse humaine"), so the
# rule is word-count based: a span of at most QUOTED_MAX_WORDS words is a cited term.
QUOTED_RE = re.compile(r"«[^»]*»|“[^”]*”|\"[^\"]*\"")
QUOTED_MAX_WORDS = 4
FENCE_RE = re.compile(r"^\s*```")
HEADING_RE = re.compile(r"^\s{0,6}#{0,6}\s{0,4}(?:\d\.\s*)?")
PLACEHOLDER_RE = re.compile(r"\$\{[A-Z_]+\}")
VERDICT_RE = re.compile(r"\b(PROTOTYPE|AMBIGU|ARTEFACT)\s*:")
SCRIPT_REF_RE = re.compile(r"[\w./-]+\.(?:py|sh)\b")


# --------------------------------------------------------------------------- git


def _run(cmd, cwd=None, env=None):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=180,
                          env=env)


def git(checkout, *args):
    p = _run(["git", "-C", str(checkout), *args])
    assert p.returncode == 0, "git %s failed: %s" % (" ".join(args), p.stderr)
    return p.stdout


def sha256(data):
    if isinstance(data, str):
        data = data.encode("utf-8")
    if isinstance(data, Path):
        data = data.read_bytes()
    return hashlib.sha256(data).hexdigest()


def reference_commit():
    """The commit that ADDED the slice file — the versioned French source."""
    commits = git(REPO, "log", "--format=%H", "--", SLICE_REL).split()
    assert commits, ("%s is not versioned: the error scenario of this slice restores its "
                     "French bytes, so the file must live in the history" % SLICE_REL)
    return commits[-1]


def reference_text():
    commit = reference_commit()
    p = _run(["git", "-C", str(REPO), "show", "%s:%s" % (commit, SLICE_REL)])
    assert p.returncode == 0, "cannot read %s at %s: %s" % (SLICE_REL, commit, p.stderr)
    return p.stdout, commit


def head_text():
    assert SLICE.is_file(), (
        "the slice file is absent from the tree: %s\n"
        "this bank is written BEFORE the translation (peer programming test // dev): "
        "that failure is the expected RED." % SLICE_REL)
    return SLICE.read_text(encoding="utf-8")


# ---------------------------------------------------------------------- literals


def frozen_literals():
    """The frozen literals DECLARED by the exclusion file — read, never hardcoded."""
    assert EXCLUSIONS.is_file(), (
        "the exclusion file is absent: %s (deliverable of slice 2, t_f2b6c1aa)" % EXCLUSIONS_REL)
    txt = EXCLUSIONS.read_text(encoding="utf-8")
    try:
        import yaml
    except ImportError:  # pragma: no cover - PyYAML ships with this environment
        pytest.fail("PyYAML is required to read %s" % EXCLUSIONS_REL)
    doc = yaml.safe_load(txt)
    out = []

    def walk(node, list_ctx=False):
        if isinstance(node, dict):
            for key, val in node.items():
                kl = str(key).strip().lower()
                if kl in ("litteral", "literal", "litteraux", "literaux") and isinstance(val, str):
                    out.append(val)
                else:
                    walk(val, kl in ("protocoles", "geles", "frozen_literals"))
        elif isinstance(node, (list, tuple)):
            for val in node:
                if isinstance(val, str) and list_ctx:
                    out.append(val)
                else:
                    walk(val, list_ctx)

    walk(doc)
    lits = [s for s in dict.fromkeys(x.strip() for x in out) if s]
    assert lits, "%s declares no frozen literal" % EXCLUSIONS_REL
    for proto in PROTOCOLES_ATTENDUS:
        assert proto in lits, (
            "the machine protocol %r is not declared in %s: the corpus cites it verbatim, "
            "so without the exclusion the scan reports a CORRECT translation"
            % (proto, EXCLUSIONS_REL))
    return lits


def residual(line, literals):
    for lit in literals:
        line = line.replace(lit, "")
    return line


def expected_violations(text, literals):
    """Lines of `text` carrying a diacritic OUTSIDE a frozen span — this bank's own count."""
    hits = []
    for num, line in enumerate(text.splitlines(), 1):
        reste = residual(line, literals)
        if any(c in ACCENTS for c in reste):
            hits.append(num)
    return hits


def _blank_citations(line):
    """Blank short QUOTED spans: a cited French term is not French prose.

    One-pass substitution: each maximal quoted span longer than QUOTED_MAX_WORDS words is
    put back untouched, so the regex cannot mis-pair delimiters across a line.
    """
    def repl(m):
        span = m.group(0)
        return " " if len(span.split()) <= QUOTED_MAX_WORDS else span

    return QUOTED_RE.sub(repl, line)


def fr_tokens(line):
    """Distinct FR_ONLY words of a line, with code spans, URLs and citations removed."""
    low = URL_RE.sub(" ", CODE_SPAN_RE.sub(" ", _blank_citations(line))).lower()
    return sorted({t for t in TOKEN_RE.findall(low) if t in FR_ONLY})


def fr_lines(text):
    return [(n, fr_tokens(l)) for n, l in enumerate(text.splitlines(), 1)
            if len(fr_tokens(l)) >= FR_THRESHOLD]


def _title_line(line):
    """A line reduced to its opening proposition: decorations and code spans removed.

    Heading markers, list bullets and section numbering are stripped REPEATEDLY, because a
    document writes `### 2. Acceptance criteria` — one pass would leave `2. Acceptance…`
    and the anchored check would never see the title.
    """
    s = CODE_SPAN_RE.sub("", line)
    for _ in range(4):
        stripped = re.sub(r"^\s*(?:[#>]+|\(?\d+[.)]|[-*+])\s+", "", s)
        if stripped == s:
            break
        s = stripped
    s = re.sub(r"^\*\*(?P<t>[^*]+)\*\*", r"\g<t>", s)
    return s.strip()


def title_problems(text):
    """Gate titles of the 20/09 decision, judged on the document's own section lines.

    The title must OPEN its line (after heading markers, numbering, bullets and bold are
    stripped, exactly as `pj_card_lint` anchors them at line start): a prose mention is not
    the required section title. Returns (missing English, remaining French).
    """
    lines = [_title_line(l) for l in text.splitlines()]
    missing = [t for t in TITRES_EN if not any(l.startswith(t) for l in lines)]
    reste = sorted({t for t in TITRES_FR_UNIQUES for l in lines if l.startswith(t)})
    return missing, reste


def machine_token_problems(ref, head):
    """Contracts a translation must not damage, compared reference -> HEAD.

    Script references are compared by BASENAME because one of them legitimately moved
    (`bridge/` -> `pipeline/`); placeholders, verdict tokens and fence delimiters are
    compared exactly. Returns a list of human-readable discrepancies.
    """
    problems = []
    ref_ph, head_ph = sorted(PLACEHOLDER_RE.findall(ref)), sorted(PLACEHOLDER_RE.findall(head))
    if head_ph != ref_ph:
        problems.append("${...} placeholders: reference %r -> HEAD %r" % (ref_ph, head_ph))

    ref_fences = sum(1 for l in ref.splitlines() if FENCE_RE.match(l))
    head_fences = sum(1 for l in head.splitlines() if FENCE_RE.match(l))
    if head_fences != ref_fences:
        problems.append("fence delimiters: reference %d -> HEAD %d" % (ref_fences, head_fences))

    ref_v = sorted({m.group(0) for m in VERDICT_RE.finditer(ref)})
    head_v = sorted({m.group(0) for m in VERDICT_RE.finditer(head)})
    if head_v != ref_v:
        problems.append("verdict tokens: reference %r -> HEAD %r" % (ref_v, head_v))

    ref_s = sorted({Path(m.group(0)).name for m in SCRIPT_REF_RE.finditer(ref)})
    head_s = sorted({Path(m.group(0)).name for m in SCRIPT_REF_RE.finditer(head)})
    lost = [s for s in ref_s if s not in head_s]
    if lost:
        problems.append("script references dropped: %r (reference set %r)" % (lost, ref_s))
    return problems


# ------------------------------------------------------------------------ fixtures


def make_repo(root, content, rel=SLICE_REL, tracked=True):
    """Throwaway git repository holding the slice file plus the exclusion file.

    The exclusion file is copied at its CANONICAL path so a scan run WITHOUT arguments
    resolves it, whether it looks next to the corpus, next to the cwd or next to the
    script — this bank does not freeze that detail.
    """
    env = dict(os.environ)
    env.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1",
               GIT_TERMINAL_PROMPT="0", HOME=str(root))
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    p = _run(["git", "init", "-q"], cwd=root, env=env)
    assert p.returncode == 0, "git init failed: %s" % p.stderr
    target = root / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    ex = root / EXCLUSIONS_REL
    ex.parent.mkdir(parents=True, exist_ok=True)
    ex.write_text(EXCLUSIONS.read_text(encoding="utf-8"), encoding="utf-8")
    add = [rel, EXCLUSIONS_REL] if tracked else [EXCLUSIONS_REL]
    p = _run(["git", "add", "--", *add], cwd=root, env=env)
    assert p.returncode == 0, "git add failed: %s" % p.stderr
    return env


def scan(args=(), cwd=REPO, exclusions=None):
    cmd = [sys.executable, str(TOOL)]
    if exclusions is not None:
        cmd += ["--exclusions", str(exclusions)]
    cmd += [str(a) for a in args]
    return _run(cmd, cwd=str(cwd))


def output(p):
    return p.stdout + p.stderr


def resume(p, what):
    return ("%s: rc=%d\n--- stdout ---\n%s\n--- stderr ---\n%s"
            % (what, p.returncode, p.stdout, p.stderr))


def named(out):
    """`path:NN` pairs printed by the scan (the contract's own report shape)."""
    found = {}
    for line in out.splitlines():
        for m in re.finditer(r"([\w./-]+\.md):(\d+)", line):
            found.setdefault((m.group(1), int(m.group(2))), line.strip())
    return [(rel, num, line) for (rel, num), line in sorted(found.items())]


# --------------------------------------------------------------------------- tests
# 1. NOMINAL


def test_nominal_the_scan_is_green_and_silent_on_the_slice_file():
    """Scénario nominal — no diacritic outside a frozen span, explicitly on the slice."""
    p = scan(args=[SLICE_REL], cwd=REPO)
    assert p.returncode == 0, resume(
        p, "scan restricted to %s: exit 0 expected (exit 1 = French left, 2 = usage)"
           % SLICE_REL)
    assert output(p).strip() == "", (
        "a compliant file must produce NO output (stdout and stderr both empty):\n%r"
        % output(p))
    print("witness nominal: %s -> rc=0, silent" % SLICE_REL)


def test_nominal_the_reference_revision_of_the_slice_is_french():
    """The RED cannot be vacuous: the versioned French source really carries diacritics.

    Also prints the whole-corpus verdict for context — deliberately NOT asserted: the
    other slices of issue #2 are still French at this point, so a corpus-wide green is
    not this slice's criterion.
    """
    text, commit = reference_text()
    literals = frozen_literals()
    hits = expected_violations(text, literals)
    assert hits, ("the reference revision %s of %s carries no diacritic outside a frozen "
                  "span: this bank would be green before AND after the translation, i.e. "
                  "it could not fail" % (commit[:12], SLICE_REL))

    p = scan(cwd=REPO)
    assert p.returncode in (0, 1), resume(p, "whole-corpus scan: 0 (compliant) or 1 (French left)")
    print("witness reference: %s@%s = %d lines, %d with a diacritic outside a frozen span; "
          "whole-corpus scan at HEAD: rc=%d"
          % (SLICE_REL, commit[:12], len(text.splitlines()), len(hits), p.returncode))


def test_nominal_machine_tokens_of_the_reference_are_still_cited():
    """Nominal — the shell/CLI contracts the document carries are not collateral damage.

    Placeholders, verdict tokens, fenced blocks and script references are machine
    contracts: a translation changes the prose AROUND them. Script references are compared
    by BASENAME, because one of them legitimately moved (`bridge/` -> `pipeline/`).

    Falsifiability, executed in the same run: a throwaway copy of the reference with ONE
    `${HOME}` placeholder removed and ONE script reference renamed must make this check
    red on both fields.
    """
    ref, commit = reference_text()
    head = head_text()

    ref_ph = sorted(PLACEHOLDER_RE.findall(ref))
    assert ref_ph, "the reference revision carries no ${...} placeholder: nothing to compare"
    ref_scripts = sorted({Path(m.group(0)).name for m in SCRIPT_REF_RE.finditer(ref)})
    assert ref_scripts, "the reference revision cites no script: nothing to compare"
    problems = machine_token_problems(ref, head)
    assert not problems, (
        "machine contracts damaged by the translation (reference %s -> HEAD):\n  - %s\n"
        "reference set: %r" % (commit[:12], "\n  - ".join(problems), ref_scripts))

    mute_ph = ref.replace("${HOME}", "HOME", 1)
    assert mute_ph != ref, "the placeholder mutation was not applied"
    mute_script = ref.replace(Path(ref_scripts[0]).name, "renamed_tool.py")
    assert mute_script != ref, "the script mutation was not applied"
    mute = mute_script.replace("${HOME}", "HOME", 1)
    assert sha256(mute) != sha256(ref), "the combined mutation was not applied (sha256 equal)"
    reds = machine_token_problems(ref, mute)
    assert len(reds) >= 2, (
        "the same check must RED on a mutated copy, on BOTH fields (a check that cannot "
        "fail is not a check); it reported %r" % reds)

    head_fences = sum(1 for l in head.splitlines() if FENCE_RE.match(l))
    head_verdicts = sorted({m.group(0) for m in VERDICT_RE.finditer(head)})
    print("witness machine tokens: placeholders %d identical, fenced %d, verdicts %r, "
          "script basenames %d kept (mutation -> %d red field(s): %s)"
          % (len(ref_ph), head_fences, head_verdicts, len(ref_scripts), len(reds),
             " | ".join(reds)))


def test_nominal_the_slice_documents_the_english_gate_titles():
    """Nominal — decision of 20/09: the five gate titles this document specifies are ENGLISH.

    The card linter is bilingual, so keeping the French headings would NOT red the scan
    (`Contexte & Objectif` carries no diacritic and `Hors-scope` neither). Only the
    headings of the document's own normative list are judged, anchored at line start as
    the linter anchors them, with code spans removed: a prose mention is not a heading.
    """
    head = head_text()
    ref, commit = reference_text()
    missing, restes = title_problems(head)
    assert not missing, (
        "the document must name the ENGLISH gate titles of the 20/09 decision as its own "
        "headings; missing: %r" % missing)
    assert not restes, (
        "these FRENCH headings are still presented as the required section titles, although "
        "the 20/09 decision moves them to English (the scan cannot see it: `Hors-scope` and "
        "`Contexte & Objectif` carry no diacritic): %r" % restes)

    # Falsifiability, executed here in BOTH directions:
    #  (a) the check must FIRE on the French state — else it reads nothing;
    #  (b) it must GO GREEN on the exact edit the dev card prescribes (the four French
    #      titles replaced by their English counterparts) — that is the change that greens
    #      this assertion, and this is where it is proven, not asserted;
    #  (c) it must RED again when one English title is dropped from that green copy.
    assert not missing and not restes, (
        "HEAD is not the state this test judges; see the failure above")
    fr_now = title_problems(ref)[1]
    assert sorted(fr_now) == sorted(TITRES_FR_UNIQUES), (
        "the check must report the FOUR French section titles of the reference revision "
        "%s; it reported %r" % (commit[:12], fr_now))

    traduit = ref
    for fr, en in zip(TITRES_FR_UNIQUES, ("Context & Objective", "Acceptance criteria",
                                          "Technical considerations", "Out of scope")):
        assert fr in traduit, "the reference revision no longer carries %r" % fr
        traduit = traduit.replace(fr, en)
    assert sha256(traduit) != sha256(ref), "the simulation was not applied (sha256 equal)"
    miss_ok, fr_ok = title_problems(traduit)
    assert not miss_ok and not fr_ok, (
        "the prescribed edit (four French titles -> English) must GREEN the check: it "
        "reported missing=%r, French left=%r" % (miss_ok, fr_ok))

    retire = traduit.replace("## Acceptance criteria", "## Acceptance", 1)
    assert sha256(retire) != sha256(traduit), "the removal was not applied"
    assert title_problems(retire)[0] == ["Acceptance criteria"], (
        "dropping an English title must be reported, got %r" % title_problems(retire)[0])
    print("witness titles: %d lines judged; reference reports %r ; prescribed edit -> "
          "missing=%r French=%r ; one title dropped -> %r"
          % (len(head.splitlines()), fr_now, miss_ok, fr_ok, title_problems(retire)[0]))


# 2. LIMIT


def test_limite_the_frozen_literals_cited_by_the_slice_are_verbatim():
    """Scénario limite — byte-for-byte preservation of every declared frozen literal.

    The expected counts are COUNTED at the reference revision, never read from the card:
    the card announces 23 citations of frozen literals in this document; measured, it
    cites `ROOM:` 3 times and `Importé depuis` 0 times.
    """
    ref, commit = reference_text()
    head = head_text()
    literals = frozen_literals()

    cites_ok = []
    for lit in literals:
        n_ref = ref.count(lit)
        n_head = head.count(lit)
        assert n_head == n_ref, (
            "the frozen literal %r is cited %d time(s) at the reference revision %s and %d "
            "time(s) at HEAD: translating or dropping a frozen literal makes the reader of "
            "that literal silent, with no error" % (lit, n_ref, commit[:12], n_head))
        cites_ok.append((lit, n_ref))

    cited = [c for c in cites_ok if c[1]]
    assert cited, ("not one of the declared frozen literals %r is cited by the reference "
                   "revision of %s: the exclusion file would then be untestable here"
                   % (literals, SLICE_REL))

    # Case is part of "verbatim": a translator writing `Room:` or `room:` would keep the
    # exact-form count intact, so the check below counts case-INSENSITIVELY too.
    for lit in literals:
        n_ref_ci = ref.lower().count(lit.lower())
        n_head_ci = head.lower().count(lit.lower())
        assert n_head_ci == n_ref_ci, (
            "a case variant of the frozen literal %r was introduced: %d case-insensitive "
            "occurrence(s) at the reference revision, %d at HEAD (the exact form still "
            "counts %d)" % (lit, n_ref_ci, n_head_ci, head.count(lit)))
    print("witness frozen literals: %r all preserved verbatim (cited: %r)"
          % ([l for l, _ in cites_ok], [(l, n) for l, n in cites_ok if n]))


def test_limite_a_frozen_span_is_whitelisted_by_span_and_not_by_line(tmp_path):
    """Scénario limite — the same shape as the document's own `ROOM:` lines.

    Three lines of measured evidence in one run: an English line quoting `ROOM:` is
    silent; the SAME line plus one accented French word is reported (so the whitelist is
    the SPAN, not the line); and the span is what makes it silent, because the diacritic
    lives inside the literal.
    """
    literals = frozen_literals()
    ligne_propre = "The `%s` marker is the room<->card link: the engine knows no other link." % "ROOM:"
    assert not any(c in ACCENTS for c in residual(ligne_propre, literals)), ligne_propre

    ligne_sale = ("The `%s` marker is the room<->card link: the engine ne connaît aucun "
                  "autre lien." % "ROOM:")
    reste = residual(ligne_sale, literals)
    assert any(c in ACCENTS for c in reste), (
        "the decorated line must carry a diacritic OUTSIDE the frozen span — checked in "
        "the same run, otherwise the case proves nothing: %r" % ligne_sale)

    root_ok = tmp_path / "span_ok"
    make_repo(root_ok, "# Pipeline\n\n%s\n" % ligne_propre)
    p_ok = scan(cwd=root_ok)
    assert p_ok.returncode == 0, resume(
        p_ok, "English prose quoting a frozen literal: exit 0 (the span is removed)")

    root_ko = tmp_path / "span_ko"
    make_repo(root_ko, "# Pipeline\n\n%s\n" % ligne_sale)
    p_ko = scan(cwd=root_ko)
    assert p_ko.returncode == 1, resume(
        p_ko, "the same line, French word OUTSIDE the frozen span: exit 1")
    assert any(rel.endswith(SLICE_REL) for rel, _, _ in named(output(p_ko))), (
        "the line must be named with its path and number:\n%s" % output(p_ko))
    print("witness span: clean=%r -> rc=0 ; dirty -> rc=1 %r"
          % (ligne_propre[:52], named(output(p_ko))[0][:1]))


def test_limite_unaccented_french_prose_is_flagged_and_the_scan_cannot_see_it(tmp_path):
    """Scénario limite — the blind spot of a diacritic scan, made executable.

    Half of a French sentence can be translated without touching an accent
    (`Ne pas merger sur dev`), and the scanner is structurally blind to it. Two things are
    measured here:

    1. the detector is CALIBRATED in the same run: it flags none of the already-English
       documents of this tree (a detector that fires on real English is not a detector);
    2. the slice file flags ZERO such lines at HEAD, and the scanner's verdict is
       unchanged when one is injected — that green is the blind spot, not a pass.
    """
    # Scope, STATED: the detector judges the WHOLE document in one pass, fenced blocks
    # included. It is the stricter rule and it is measured as such above. (A two-state
    # fence tracker is not used: on this file, `FENCE_RE` sees 7 fence delimiters, and a
    # naive inside/outside toggle then declares the rest of the page "inside a fence" and
    # would blank 122 of the reference's 133 French lines.)
    #
    # The citation rule must also DISCRIMINATE, measured in the same run: the two lines
    # below differ ONLY by their quote marks.
    cite = "The note cites « dans », « pour », « rien » as examples of the blind spot."
    assert not fr_tokens(cite), (
        "a short quoted citation must not count as prose: %r" % fr_tokens(cite))
    cite_nu = "The note cites dans pour rien as examples of the blind spot."
    assert len(fr_tokens(cite_nu)) >= FR_THRESHOLD, (
        "the same words UNQUOTED must fire, otherwise the citation rule is not a rule but "
        "a word list: %r" % fr_tokens(cite_nu))

    refs = [REPO / r for r in CALIBRATION_REFS if (REPO / r).is_file()]
    assert len(refs) >= 3, ("the calibration set lost its references: %r" % CALIBRATION_REFS)
    calib_lines = 0
    for r in refs:
        text = r.read_text(encoding="utf-8", errors="replace")
        calib_lines += len(text.splitlines())
        hits = fr_lines(text)
        assert not hits, (
            "the detector fires on a document already written in English — it would send a "
            "correct translation into rework. Offending lines of %s:\n%s"
            % (r.relative_to(REPO),
               "\n".join("  L%d %s | %s" % (n, ",".join(t), text.splitlines()[n - 1][:80])
                         for n, t in hits[:5])))
    assert calib_lines >= 150, ("calibration on %d lines is too thin to mean anything"
                                % calib_lines)

    head = head_text()
    head_hits = fr_lines(head)
    assert not head_hits, (
        "%s still carries FRENCH prose on %d line(s) that the diacritic scan cannot see "
        "(calibration: 0 false positive over %d lines of real English in this tree). "
        "Offending lines:\n%s"
        % (SLICE_REL, len(head_hits), calib_lines,
           "\n".join("  L%d [%s] | %s" % (n, ",".join(t), head.splitlines()[n - 1].strip()[:88])
                     for n, t in head_hits[:12])))

    # Device proof, state-independent: inject ONE unaccented French line in a copy of the
    # file. The detector must see it; the scanner's verdict and count must NOT move.
    injecte = "Ne pas merger sur dev et ne pas toucher au worktree des autres cartes."
    assert len(fr_tokens(injecte)) >= FR_THRESHOLD, fr_tokens(injecte)
    assert not any(c in ACCENTS for c in injecte), injecte

    root_clean = tmp_path / "clean"
    make_repo(root_clean, head)
    root_mute = tmp_path / "injecte"
    make_repo(root_mute, head + "\n" + injecte + "\n")

    p_clean = scan(cwd=root_clean)
    p_mute = scan(cwd=root_mute)
    assert p_mute.returncode == p_clean.returncode, (
        "the injected line carries no diacritic, so the scanner's verdict must not move "
        "(clean rc=%d, injected rc=%d) — if it moved, the injection was not the one this "
        "case describes" % (p_clean.returncode, p_mute.returncode))
    n_clean = len(named(output(p_clean)))
    n_mute = len(named(output(p_mute)))
    assert n_mute == n_clean, (
        "the scanner reported %d violation(s) before and %d after injecting an unaccented "
        "French line: the case must prove blindness, not a second defect" % (n_clean, n_mute))

    hits_mute = fr_lines(Path(root_mute, SLICE_REL).read_text(encoding="utf-8"))
    assert any(injecte.split()[0] in Path(root_mute, SLICE_REL).read_text(encoding="utf-8").splitlines()[n - 1]
               for n, _ in hits_mute), ("the detector must flag the injected line: %r" % hits_mute)
    print("witness blind spot: calibration 0 flag over %d lines of English; HEAD flags %d; "
          "scanner rc=%d/%d and %d/%d violations with and without an injected unaccented "
          "French line, while the detector flags %d line(s) there"
          % (calib_lines, len(head_hits), p_clean.returncode, p_mute.returncode,
             n_clean, n_mute, len(hits_mute)))


def test_limite_the_slice_file_is_tracked_so_the_corpus_scan_sees_it():
    """Limite — the scan enumerates the INDEX: an untracked file is invisible to it."""
    p = _run(["git", "-C", str(REPO), "ls-files", "--error-unmatch", "--", SLICE_REL])
    assert p.returncode == 0, (
        "%s is not tracked: `pj_lang_lint.py` without arguments enumerates `git ls-files`, "
        "so an untracked slice file would never be scanned (and the reference revision "
        "below could not resolve)" % SLICE_REL)


# 3. ERROR


def test_erreur_a_slice_file_left_french_is_named_with_rc_1(tmp_path):
    """Scénario erreur — 'the file was forgotten': rc 1, the file named, count recomputed.

    The mutation restores the EXACT French bytes of the reference revision on a throwaway
    copy. Its application is certified by sha256 in the same run, and the expected number
    of violations is computed by this bank from those bytes — never asserted as a literal.
    """
    ref, commit = reference_text()
    head = head_text()
    literals = frozen_literals()
    expected = expected_violations(ref, literals)
    assert expected, "the reference revision carries no violation: the mutation is empty"
    assert sha256(ref) != sha256(head), (
        "the reference revision and HEAD are byte-identical: there is nothing to restore, "
        "so this case would pass without measuring anything")

    root = tmp_path / "oublie"
    make_repo(root, ref)
    cible = Path(root, SLICE_REL)
    assert sha256(cible) == sha256(ref), "the mutation was not applied (sha256 differs)"
    assert sha256(cible) != sha256(head), "the copy was not replaced by the French source"

    p = scan(cwd=root)
    assert p.returncode == 1, resume(
        p, "a slice file left French: exit 1 (1 = violations; 2 would be a usage error)")
    trouves = [t for t in named(output(p)) if t[0].endswith(SLICE_REL)]
    assert trouves, (
        "the forgotten file must be NAMED with its path (and its lines):\n%s" % output(p))
    lignes = sorted({n for _, n, _ in trouves})
    assert len(lignes) == len(expected), (
        "%s: the scan reported %d line(s), this bank recomputes %d from the same bytes "
        "(reference %s). Reported lines: %r"
        % (SLICE_REL, len(lignes), len(expected), commit[:12], lignes))

    p_path = scan(args=[SLICE_REL], cwd=root)
    assert p_path.returncode == 1, resume(
        p_path, "same copy, scan restricted to the slice path: exit 1")
    print("witness error: %s restored from %s (sha256 %s != HEAD %s) -> rc=1, %d line(s) "
          "named, %d recomputed"
          % (SLICE_REL, commit[:12], sha256(ref)[:12], sha256(head)[:12], len(lignes),
             len(expected)))


def test_erreur_one_forgotten_sentence_is_enough(tmp_path):
    """Scénario erreur — a partially translated file is still a forgotten file.

    The fixture is built from VERSIONED bytes and does not depend on the state of the
    translation: the forgotten line is the reference revision's own first violating line,
    and every other line is replaced by an English placeholder. So the same case runs
    before AND after the translation, and what it proves is LINE granularity: exactly one
    line is reported, it is the French one, and its token is named.

    (A fixture built from HEAD could not do this: while HEAD is still French, reverting a
    single line adds nothing and the case would report the nominal failure instead.)
    """
    ref, commit = reference_text()
    literals = frozen_literals()

    expected = expected_violations(ref, literals)
    assert expected, "the reference revision carries no violation to keep"
    garde = expected[0]
    ref_lines = ref.splitlines()
    assert garde <= len(ref_lines)

    contenu = "\n".join(ref_lines[garde - 1] if i == garde - 1 else "[translated]"
                        for i in range(len(ref_lines))) + "\n"
    autres = [n for n in expected_violations(contenu, literals) if n != garde]
    assert not autres, (
        "the placeholders must be clean, otherwise the case cannot show granularity: %r"
        % autres)
    assert len(expected_violations(contenu, literals)) == 1, (
        "the fixture must carry exactly ONE French line: %r"
        % expected_violations(contenu, literals))

    root = tmp_path / "partiel"
    make_repo(root, contenu)
    cible = Path(root, SLICE_REL)
    assert sha256(cible) != sha256(ref) and sha256(cible) != sha256(head_text()), (
        "the fixture must differ from both the reference and HEAD (sha256 12-char: %s / "
        "%s / %s)" % (sha256(cible)[:12], sha256(ref)[:12], sha256(head_text())[:12]))

    p = scan(args=[SLICE_REL], cwd=root)
    assert p.returncode == 1, resume(p, "one French sentence among English lines: exit 1")
    trouves = [t for t in named(output(p)) if t[0].endswith(SLICE_REL)]
    assert [n for _, n, _ in trouves] == [garde], (
        "expected exactly line %d (kept from the reference revision %s), got %r:\n%s"
        % (garde, commit[:12], [n for _, n, _ in trouves], output(p)))

    ligne = ref_lines[garde - 1]
    fautif = [t for t in re.findall(r"\S+", residual(ligne, literals))
              if any(c in ACCENTS for c in t.strip("`*_\"'()[]{}.,;:!?«»…—–-"))]
    assert fautif, "the kept line must carry an accented token: %r" % ligne
    assert fautif[0].strip("`*_\"'()[]{}.,;:!?«»…—–-") in output(p), (
        "the report must cite the faulty token %r:\n%s" % (fautif[0], output(p)))
    print("witness partial: 1 kept French line (L%d from %s, sha256 %s) among %d English "
          "placeholders -> rc=1, line %d named, token %r cited"
          % (garde, commit[:12], sha256(contenu)[:12], len(ref_lines) - 1, garde,
             fautif[0].strip("`*_\"'()[]{}.,;:!?«»…—–-")))
