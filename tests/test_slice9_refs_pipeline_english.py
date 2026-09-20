"""Slice 9 (references + pipeline README) — banc de langue RED, carte t_8d085a87.

Sujets (les quatre documents que `dev-9` traduit, carte t_752da353) :

    skills/hermes-multi-agent-orchestration/references/hosted-rooms.md
    skills/hermes-multi-agent-orchestration/references/kanban-builtins.md
    skills/pj-pipeline/references/graph-manifest.md
    pipeline/README.md

Le banc ne fait que MESURER ces fichiers : il ne les édite jamais (`tests/**` est tout
le périmètre d'écriture de cette carte — `dev-9` possède les sources dans le MÊME
worktree).

Contrat exécuté ici (même forme que le banc de la slice 2 et les bancs frères) :

    python3 pipeline/pj_lang_lint.py [--exclusions F] [<path> ...]

- rc 0 = conforme ET muet (stdout et stderr vides) ;
- rc 1 = au moins une ligne portant un diacritique hors span gelé, chaque ligne nommant
  `path:line` ;
- rc 2 = erreur d'usage (jamais une violation, et réciproquement).

Ce que ce banc prouve, et ce qu'il NE prouve PAS
-----------------------------------------------

Le scan de diacritiques est NÉCESSAIRE mais pas SUFFISANT. Mesuré à `origin/dev` : les
quatre fichiers portent 389 lignes dont 161 accentuées — or de la prose française
survit à une traduction sans conserver un seul accent. Le banc porte donc aussi un
contrôle LEXICAL calibré par mesure (voir `test_limite_aucune_prose_...`) : une liste de
mots-outils français sans homographe anglais, seuil K = 2 tokens DISTINCTS par ligne,
0 faux positif mesuré sur les 202 lignes non accentuées de la zone que la planche
RATIFIÉE déclare déjà anglaise (`plate-ledger.outside_corpus`).

Rappel faible, dit explicitement : à K = 2 ce contrôle signale 5 des lignes non
accentuées de la slice (le fichier et la ligne sortent dans l'échec). C'est un garde
contre une demi-traduction, jamais une preuve de complétude ; la revue du diff reste
exigée en `conv-9`.

Corrections mesurées à la prose de la carte
-------------------------------------------

La carte annonce « 389 l., 161 accentuées » — reproduit exactement et par fichier :
136+55+95+103 = 389 lignes, 49+22+51+39 = 161 accentuées (ledger de la planche : mêmes
nombres). Le scénario limite « les littéraux gelés CITÉS PAR LA SLICE restent verbatim »
est, lui, précisé par la mesure : cette slice cite `ROOM:` **0 fois** et
`Importé depuis` **1 fois en lecture brute** / **2 fois en lecture repliée** (la
deuxième citation est coupée par un retour de ligne markdown, `pipeline/README.md` 101-102 :
`« Importé` / `depuis »`). Le compte est donc asserté en lecture REPLIÉE (insensible au
repli, que la traduction a le droit de refaire) et imprimé en lecture brute ; une
exigence de citation non nulle pour `ROOM:` serait rouge pour toujours.

Deux pièges de nommage, un seul correctif
-----------------------------------------

Le corpus contient QUATRE fichiers nommés `README.md` (`README.md`,
`pipeline/README.md`, `docs/architecture/README.md`, `docs/functional/README.md`) et la
slice en possède un. Toute comparaison ci-dessous se fait donc sur le CHEMIN RELATIF
EXACT (`rel == nom`, `set(SLICE)`), jamais sur un basename ni un suffixe : un banc qui
matche par suffixe impute à cette slice la violation d'un voisin et envoie un `dev-9`
correct en boucle de réécriture.

Pas d'horloge réelle, pas d'aléa : chaque décor est un dépôt git jetable construit par
ce banc à partir d'octets VERSIONNÉS (`git show origin/dev:<path>`), et chaque compte est
recalculé depuis les octets en main plutôt qu'asserté en littéral recopié.
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
    "skills/hermes-multi-agent-orchestration/references/hosted-rooms.md",
    "skills/hermes-multi-agent-orchestration/references/kanban-builtins.md",
    "skills/pj-pipeline/references/graph-manifest.md",
    "pipeline/README.md",
)

TOOL_REL = "pipeline/pj_lang_lint.py"
EXCLUSIONS_REL = "pipeline/pj_lang_lint.exclusions.yaml"
PLATE_REL = "docs/architecture/context/issue-2-plate.html"

TOOL = REPO / TOOL_REL
EXCLUSIONS = REPO / EXCLUSIONS_REL
PLATE = REPO / PLATE_REL

SLICE_K = 9
# Pré-état de la slice : la base de fusion de la branche contre `origin/dev`, c'est-à-dire
# les octets d'où part la traduction. Lus par `git show`, jamais depuis une copie gardée à
# côté du banc : la référence ne peut pas dériver avec l'arbre sous test.
REF_REF = "origin/dev"

# Classe de caractères du contrat, identique au banc de la slice 1, au scanner et au
# `character_class_chars` de la planche ratifiée. Redéclarée ici À DESSEIN : un banc qui
# importerait la classe depuis le sujet s'élargirait avec le sujet. Le cas nominal assert
# l'égalité avec la classe que la planche déclare.
ACCENTS = "àâäçéèêëîïôöùûüÿœæñÀÂÄÇÉÈÊËÎÏÔÖÙÛÜŸŒÆÑ"

# Les deux et seuls protocoles machine gelés. Cette slice cite le premier et jamais le
# second (mesuré) — l'assertion est donc un contrat de COMPTE (1==1 brut, 2==2 replié),
# imprimé comme tel pour qu'un 0==0 ne soit jamais pris pour un succès d'autre chose.
PROTOCOLES = ("Importé depuis", "ROOM:")

# Mots-outils français sans homographe anglais : même liste et même seuil que les bancs
# frères, RE-MESURÉS ici sur la zone déjà anglaise de CET arbre (voir le cas).
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
FENCE_BLOCK_RE = re.compile(r"^[ \t]*```.*?^[ \t]*```[ \t]*$", re.S | re.M)
STRICT_RE = re.compile(r"([\w./-]+\.md):(\d+)")
LEDGER_RE = re.compile(
    r"<script[^>]*id=[\"']plate-ledger[\"'][^>]*>(?P<json>.*?)</script>", re.S | re.I
)
HEADING_RE = re.compile(r"^#{1,6}\s")
FENCE_RE = re.compile(r"^\s*```")
TABLE_SEP_RE = re.compile(r"^\s*\|?[\s:|-]*-[\s:|-]*\|[\s:|-]*$")

# Un token backtické n'est un contrat machine que s'il porte une forme de CODE (point,
# slash, underscore, majuscule, accolades…) : le mot nu `` `gate` `` est de la prose citée
# et vaut mieux comme diagnostic que comme assertion (voir `machine_vocabulary`).
CODE_RE = re.compile(r"[./_:\-*<>{}=|\[\]]|[A-Z]")

ENGLISH_STUB = (
    "# Title\n\n"
    "All English prose, without a single diacritic.\n"
    "No machine contract is cited here.\n"
)

_READERS = None


# --------------------------------------------------------------------------- outils


def _run(cmd, cwd=None, env=None):
    return subprocess.run(cmd, cwd=str(cwd) if cwd else None, capture_output=True,
                          text=True, timeout=300, env=env)


def git(*args, cwd=REPO):
    p = _run(["git", "-C", str(cwd), *args])
    assert p.returncode == 0, "git %s failed: %s" % (" ".join(args), p.stderr)
    return p.stdout


def tracked(root=REPO):
    """Énumération canonique : l'INDEX, jamais un parcours de répertoire.

    Chaque `git worktree` sous `.worktrees/` porte une copie complète du corpus : un
    `os.walk` compterait l'arbre plusieurs fois.
    """
    p = _run(["git", "-C", str(root), "ls-files", "-z"])
    assert p.returncode == 0, p.stderr
    return sorted(x for x in p.stdout.split("\x00") if x)


def git_show(rel, ref=REF_REF):
    """Les octets versionnés de `rel` à `ref` — le pré-état de la traduction."""
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


# ------------------------------------------------------------------ lectures du texte


def strip_fences(text):
    """Le document sans ses blocs de code clôturés.

    Les délimiteurs ``` `` ``` portent un nombre IMPAIR de backticks : appariés sur place,
    ils fabriquent des spans fantômes (mesuré : `ou`, `) : le`, `request_changes`). Le
    contenu des blocs de code de cette slice ne cite aucun span ; les retirer laisse dans
    les quatre fichiers un nombre PAIR de backticks, donc des spans réels un à un.
    """
    return FENCE_BLOCK_RE.sub("\n", text)


def flatten(text):
    """Le texte replié : markdown coupe une citation inline sur un retour de ligne."""
    return re.sub(r"\s*\n\s*", " ", text)


def spans(text):
    """Spans backtickés d'un document, appariés en ORDRE de document.

    Lecture repliée : `` `Importé\\n  depuis »` `` est un span coupé par le repli
    markdown, invisible à un appariement ligne à ligne.
    """
    return [s.strip() for s in SPAN_RE.findall(flatten(strip_fences(text)))]


def literal_count(text, literal, flat=False):
    return (flatten(strip_fences(text)) if flat else text).count(literal)


# ------------------------------------------------------------------------ exclusions


def declared_exclusions():
    """(littéraux, texte brut) lus INDÉPENDAMMENT du scanner.

    Le banc ne demande pas au sujet quels littéraux il blanchit : il relit la déclaration
    versionnée, sinon une exemption AJOUTÉE par la slice passerait inaperçue — c'est
    précisément le contournement que le cas limite doit refuser.
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


def declared_readers():
    """[(littéral, chemin, ligne)] lus depuis le fichier d'exclusion, sans passer par lui."""
    doc = yaml.safe_load(EXCLUSIONS.read_text(encoding="utf-8"))
    out = []
    for entry in (doc.get("protocoles") or []):
        if not isinstance(entry, dict):
            continue
        lit = entry.get("litteral") or entry.get("literal")
        for key in ("lecteur", "aussi_lu_par"):
            val = entry.get(key)
            for cand in (val if isinstance(val, list) else [val]):
                if not isinstance(cand, str) or ":" not in cand:
                    continue
                rel, _, num = cand.rpartition(":")
                out.append((lit, rel, int(num)))
    return out


def residual(line, literals):
    """La ligne moins chaque span gelé — la granularité du scanner (span, pas ligne)."""
    for lit in literals:
        if lit:
            line = line.replace(lit, "")
    return line


def expected_violations(text, literals):
    """Numéros des lignes de `text` portant un diacritique HORS span gelé, selon CE banc.

    Vérifié identique au scanner sur les octets de `origin/dev` des quatre fichiers
    (49/22/51/39 lignes, même ensemble de numéros).
    """
    out = []
    for num, line in enumerate(text.splitlines(), 1):
        if any(c in ACCENTS for c in residual(line, literals)):
            out.append(num)
    return out


# ------------------------------------------------------------------------- provenance


def production_readers():
    """Fichiers exécutables suivis (`.py`/`.sh`) hors `tests/`, `docs/` et hors la slice.

    Un token backtické de la slice est traité comme contrat machine seulement quand un de
    ces fichiers le porte en forme de MOT : c'est la forme falsifiable de « ce littéral
    est gelé ». Correspondance sous-chaîne = machine à faux positifs (mesuré : `k` et `ou`
    « trouvés » dans un script shell) ; `CODE_RE` restreint en plus aux tokens en forme de
    code, un mot nu étant de la prose citée que la traduction peut reformuler.
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
            except OSError:  # pragma: no cover - fichier suivi illisible
                continue
        _READERS = out
    return _READERS


def _word_bounded(token, text):
    return re.search(r"(?<![\w`-])%s(?![\w-])" % re.escape(token), text) is not None


def machine_vocabulary():
    """{span: 'lecteur:ligne'} pour les tokens de CODE de la slice avec provenance PROUVÉE.

    Seuls les tokens écrits DANS un span backtické sont collectés : `` `message.user` `` est
    une citation d'état machine, tandis que le mot nu « ready » est de la prose qu'une
    traduction peut ajouter ou retirer à volonté.
    """
    vocab = {}
    for rel in SLICE:
        for span in spans(git_show(rel)):
            if not span or span in vocab or not CODE_RE.search(span):
                continue
            for r, txt in sorted(production_readers().items()):
                if _word_bounded(span, txt):
                    vocab[span] = "%s:%d" % (r, txt[:txt.find(span)].count("\n") + 1)
                    break
    return vocab


def cited_span(span):
    """La citation backtickée de `span` — la forme qu'un document écrit pour le citer."""
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
    """Couples `path:NN` de la forme de rapport du contrat, dédupliqués."""
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
    """Noms rapportés par le scan, gardés en CHEMINS RELATIFS EXACTS (jamais basenames).

    Le corpus porte quatre `README.md` et la slice en possède un : un test de suffixe
    imputerait à cette slice la violation d'un voisin.
    """
    return sorted({rel for rel, _, _ in reported(out)})


# --------------------------------------------------------------------------- décors


def build_tree(root, files):
    """Dépôt git jetable : `files` = {chemin relatif: contenu}, tous indexés."""
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
    """Précondition nominale/limite : la slice EST traduite — sinon c'est le RED attendu.

    L'échec NOMME le fichier et la ligne de chaque ligne accentuée restante hors span gelé,
    pour que le RED soit actionnable et pas un booléen.
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
            "slice 9 NOT translated: %d accented line(s), of which %d outside a frozen "
            "span.\n  - %s\n(this bank is written BEFORE the translation: this failure "
            "IS the expected RED)"
            % (total, len(restes), "\n  - ".join(restes[:10])))


def frozen_literals():
    lits, _ = declared_exclusions()
    assert lits, "%s declares no frozen literal" % EXCLUSIONS_REL
    return lits


def skeleton(text):
    """Le SQUELETTE du document : ce qu'une traduction ne doit pas réécrire, seulement
    reformuler (compte de titres, de délimiteurs de bloc, de séparateurs de tableau,
    clés de frontmatter)."""
    fm = None
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if m:
        fm = yaml.safe_load(m.group(1)) or {}
    lines = text.splitlines()
    return {
        "frontmatter_keys": sorted(fm) if isinstance(fm, dict) else None,
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


def offenders(text):
    """[(ligne, tokens, texte)] pour les lignes françaises SANS diacritique du document."""
    hits = []
    for n, line in enumerate(text.splitlines(), 1):
        if any(c in ACCENTS for c in line):
            continue  # le scan les rapporte déjà ; ce contrôle juge le reste
        toks = sorted({m.group(1).lower() for m in MOT_FR.finditer(line)})
        if len(toks) >= SEUIL_LEXICAL:
            hits.append((n, toks, line.strip()))
    return hits


# -------------------------------------------------------------------------- nominal


def test_nominal_le_scan_sort_0_et_muet_sur_les_quatre_fichiers_de_la_slice():
    """Nominal : rc 0 et silence sur les quatre documents de la slice.

    `rc == 0` et le silence sont les deux moitiés du contrat : un scan qui imprime un
    rapport tout en retournant 0 n'est pas conforme.
    """
    precondition_translated()
    p = scan(SLICE)
    assert p.returncode == 0, resume(
        p, "scan of the four translated documents: exit 0 expected")
    assert out_of(p).strip() == "", (
        "a compliant corpus must be SILENT (stdout AND stderr empty); obtained:\n%r"
        % out_of(p))
    print("witness nominal: %d files of the slice -> rc=0, silent" % len(SLICE))


def test_nominal_le_scan_sans_argument_ne_nomme_plus_la_slice_dans_tout_le_corpus(tmp_path):
    """Nominal, branche d'énumération : la forme sans argument prend un autre chemin de
    code (`git ls-files` sur tout le corpus) et ne doit nommer AUCUN des quatre fichiers.

    L'assertion porte sur les NOMS, pas sur rc : tant que le reste du corpus est encore
    français (slices sœurs en vol) le scan d'arbre rend légitimement 1, et ce que ce cas
    isole est la contribution propre de la slice.

    Discriminant de suffixe EXÉCUTÉ dans le même cas : un décor jetable porte un
    `README.md` VOISIN français hors slice. Le corpus compte quatre fichiers de ce nom et
    la slice en possède un — un banc qui matcherait par basename ou suffixe lirait la
    violation du voisin comme celle de la slice et enverrait un `dev-9` correct en
    réécriture. Le voisin DOIT sortir nommé, la slice NON.
    """
    precondition_translated()
    p = scan()
    noms = set(named_exact(out_of(p)))
    fautifs = sorted(noms & set(SLICE))
    assert not fautifs, (
        "the whole-tree scan still NAMES files of this slice: %r\n%s"
        % (fautifs, out_of(p)))

    voisin, homonyme = "docs/architecture/README.md", "pipeline/README.md"
    fichiers = {rel: ENGLISH_STUB for rel in SLICE}
    fichiers[voisin] = git_show(homonyme)        # octets français, nom identique
    root = build_tree(tmp_path / "homonyme", fichiers)
    q = scan((), cwd=root)
    nommes = set(named_exact(out_of(q)))
    assert voisin in nommes, (
        "the French homonym neighbour %s must be named; it was not, so this decor does "
        "not exercise the discrimination it claims\n%s" % (voisin, out_of(q)))
    assert homonyme not in nommes, (
        "the slice's own %s is an English stub but was NAMED: the comparison matched the "
        "neighbour by suffix instead of the EXACT relative path — this is the defect that "
        "sends a correct dev-9 into a rewrite loop\n%s" % (homonyme, out_of(q)))
    print("witness whole corpus: %d tracked .md, %d file(s) named elsewhere, 0 on the slice; "
          "homonym decor: neighbour named=%s, slice's own README named=%s"
          % (len([r for r in tracked() if r.endswith(".md")]), len(noms),
             voisin in nommes, homonyme in nommes))


def test_nominal_le_perimetre_et_le_squelette_des_documents_sont_ceux_de_la_planche():
    """Nominal : le périmètre et la classe de caractères sont ceux RATIFIÉS, et le
    SQUELETTE des documents survit à la traduction.

    Trois sources indépendantes sont fermées l'une sur l'autre : le ledger de la planche
    (chemins et comptes par fichier), la classe de caractères qu'elle déclare, et l'arbre.
    """
    rec = ledger_slice(SLICE_K)
    assert rec.get("kind") == "translate", (
        "slice %d is declared %r in the plate ledger; this bank judges a translation"
        % (SLICE_K, rec.get("kind")))
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
    total_l = total_a = 0
    for rel in SLICE:
        entry = files.get(rel) if isinstance(files, dict) else None
        ref = git_show(rel)
        n_ref = len(ref.splitlines())
        acc_ref = len(expected_violations(ref, ()))
        total_l += n_ref
        total_a += acc_ref
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
    assert (rec.get("lines"), rec.get("accented_lines")) == (total_l, total_a), (
        "the plate's slice %d totals say %r, the reference revision measures %r"
        % (SLICE_K, (rec.get("lines"), rec.get("accented_lines")), (total_l, total_a)))
    print("witness perimeter: slice %d = %r, character class %r, %d lines / %d accented"
          % (SLICE_K, declare, classe, total_l, total_a))


# --------------------------------------------------------------------------- limite


def test_limite_les_litteraux_geles_declares_restent_verbatim_et_le_fichier_ne_s_elargit_pas():
    """Limite : le fichier d'exemption n'est pas élargi, chaque littéral gelé garde son
    compte exact d'occurrences référence -> HEAD, et chaque lecteur déclaré le porte
    toujours à la ligne déclarée.

    Mesuré : cette slice cite `Importé depuis` 1 fois en lecture brute et 2 fois en lecture
    repliée (la seconde citation est coupée par un repli markdown), et `ROOM:` 0 fois — le
    compte est imprimé pour qu'un 0 == 0 ne passe pas pour un succès d'autre chose. Ce que
    ce cas interdit, c'est le contournement : blanchir du français encore dans le corpus,
    ou perdre la forme exacte du littéral que lit le pipeline.
    """
    precondition_translated()
    lits, _ = declared_exclusions()
    assert sorted(lits) == sorted(PROTOCOLES), (
        "the exemption file declares %r; EXACTLY %r is expected — widening the exemptions "
        "is the bypass this case refuses (a translation does not blanch the French that "
        "is left), and the 5 section titles + the linter's labels are TRANSLATED by "
        "slice 2 (human decision of 2026-09-20)" % (sorted(lits), sorted(PROTOCOLES)))

    # fermeture sur le registre machine de la planche ratifiée : exclusions == planche
    registre = sorted({r.get("literal") for r in (ledger().get("frozen_literals") or [])
                       if r.get("literal")})
    assert registre == sorted(lits), (
        "the exclusions file declares %r, the ratified plate's `frozen_literals` declares "
        "%r — the tree and the register disagree" % (sorted(lits), registre))

    ecarts, vus = [], []
    for lit in lits:
        n_raw = sum(git_show(rel).count(lit) for rel in SLICE)
        n_flat = sum(literal_count(git_show(rel), lit, flat=True) for rel in SLICE)
        h_raw = sum(head_text(rel).count(lit) for rel in SLICE)
        h_flat = sum(literal_count(head_text(rel), lit, flat=True) for rel in SLICE)
        # Le compte BRUT est un DIAGNOSTIC, jamais une assertion : markdown coupe une
        # citation inline sur un retour de ligne (`pipeline/README.md` 101-102), et une
        # traduction a le DROIT de replier autrement — juger le brut enverrait un `dev-9`
        # correct en réécriture pour une remise en forme. Le contrat est le compte REPLIÉ.
        vus.append((lit, n_raw, n_flat, h_raw, h_flat))
        if n_flat != h_flat:
            ecarts.append("frozen literal %r: %d citation(s) repliée(s) at %s -> %d at HEAD "
                          "(the reader of that literal goes silent, with no error)"
                          % (lit, n_flat, REF_REF, h_flat))
        if h_flat < n_flat:
            ecarts.append("frozen literal %r: %d citation(s) LOST (brut %d -> %d, replié "
                          "%d -> %d)" % (lit, n_flat - h_flat, n_raw, h_raw, n_flat, h_flat))
    assert not ecarts, ("the frozen literals of this slice are not preserved:\n  - "
                        + "\n  - ".join(ecarts))

    # variante DÉSACCENTUÉE du littéral : c'est la traduction réelle du protocole (le
    # lecteur cherche la forme accentuée), donc elle doit être absente des quatre fichiers.
    variantes = {"Importé depuis": "Importe depuis", "ROOM:": "Room:"}
    desaccent = [(rel, variantes[lit]) for lit in lits if lit in variantes
                 for rel in SLICE if variantes[lit] in head_text(rel)]
    assert not desaccent, (
        "a DE-ACCENTED variant of a frozen literal is present, which translates the "
        "machine protocol without any error at the reader: %r" % desaccent)

    # chaque lecteur déclaré porte toujours le littéral à la ligne déclarée
    lecteurs, absents = declared_readers(), []
    for lit, rel, num in lecteurs:
        f = REPO / rel
        if not f.is_file():
            absents.append("%s (declared by %r) does not exist" % (rel, lit))
            continue
        lignes = f.read_text(encoding="utf-8").splitlines()
        if num > len(lignes) or lit not in lignes[num - 1]:
            absents.append("%s:%d no longer carries %r (declared reader of that literal)"
                           % (rel, num, lit))
    assert lecteurs, "the exclusions file declares no reader for its frozen literals"
    assert not absents, ("declared readers are not carrying their literal:\n  - "
                         + "\n  - ".join(absents))
    print("witness frozen literals: %r ; citations (brut, replié) référence -> HEAD %r ; "
          "%d reader line(s) verified" % (lits, vus, len(lecteurs)))


def test_limite_le_vocabulaire_machine_cite_par_la_slice_est_preserve_verbatim():
    """Limite — le contrat que cette slice porte réellement : les tokens de code qu'elle
    enseigne.

    Chaque token backtické de la slice en forme de code dont un lecteur est un fichier de
    PRODUCTION suivi (`pipeline/`, `plugins/`, `agents/*/scripts/`…) doit garder le même
    nombre de citations référence -> HEAD, en lecture repliée (un repli de ligne n'est pas
    une perte de contrat). Un token sans lecteur suivi est de la prose ou une API d'un
    autre paquet, et n'est délibérément PAS jugé ; le vocabulaire et sa provenance sont
    imprimés, donc un rouge est diagnosticable.
    """
    precondition_translated()
    ref_flat = {rel: flatten(strip_fences(git_show(rel))) for rel in SLICE}
    head_flat = {rel: flatten(strip_fences(head_text(rel))) for rel in SLICE}

    vocab = machine_vocabulary()
    assert len(vocab) >= 25, (
        "only %d machine token(s) of this slice have a proven reader in the tree: the "
        "provenance scan is broken, or the tokens moved — %r" % (len(vocab), sorted(vocab)))

    ecarts = []
    for span, prov in sorted(vocab.items()):
        cite = cited_span(span)
        n_ref = sum(ref_flat[r].count(cite) for r in SLICE)
        n_head = sum(head_flat[r].count(cite) for r in SLICE)
        if n_ref != n_head:
            ecarts.append("%s (read by %s): %d citation(s) -> %d"
                          % (cite, prov, n_ref, n_head))
    assert not ecarts, (
        "machine contracts of the slice were damaged by the translation:\n  - "
        + "\n  - ".join(ecarts)
        + "\nvocabulary with provenance: %r" % vocab)

    # Falsifiabilité, même fonction, même forme d'appel : renommer un token dans une copie.
    temoin = sorted(vocab)[0]
    mutant_ecarts = []
    for r in SLICE:
        mutant_ecarts.append(head_flat[r].replace(cited_span(temoin), "`%s-ALT`" % temoin))
    assert sum(m.count(cited_span(temoin)) for m in mutant_ecarts) != \
        sum(head_flat[r].count(cited_span(temoin)) for r in SLICE), (
        "the mutation was not applied: the case cannot falsify the assertion it proves")

    print("witness machine vocabulary: %d code token(s) with provenance -> 0 discrepancy; "
          "mutation of %r drops its citation count" % (len(vocab), temoin))
    for span, prov in sorted(vocab.items()):
        print("    %-44r <- %s" % (span[:44], prov))


def test_limite_aucune_prose_francaise_sans_diacritique_ne_subsiste():
    """Limite — l'angle mort du scan de diacritiques, rendu exécutable.

    Cette slice porte 161 lignes accentuées et 228 lignes NON accentuées à la référence :
    de la prose française peut survivre à une traduction sur plusieurs lignes sans perdre
    un accent, et le scanner y est structurellement aveugle. Deux choses sont mesurées dans
    le même run :

    1. le détecteur est CALIBRÉ ici : il ne signale AUCUNE ligne non accentuée des fichiers
       que la planche ratifiée déclare déjà anglais (`plate-ledger.outside_corpus`) — un
       seuil qui tire sur de l'anglais réel serait une machine à faux positifs ;
    2. la slice n'en signale AUCUNE à HEAD ; les lignes fautives sortent dans l'échec,
       fichier et ligne.
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
        faux += [(rel, n, t) for n, _, t in offenders(text)]
    assert n_lignes >= 30, (
        "calibration zone too small to prove anything (%d accent-free lines over %d "
        "files): %r" % (n_lignes, len(zone), zone))
    assert not faux, (
        "the detector fires on prose the plate declares already English (%d false "
        "positive(s) over %d accent-free lines): the control is not discriminant\n  "
        % (len(faux), n_lignes) + "\n  ".join("%s:%d %s" % f for f in faux[:10]))

    # contrôle positif, même détecteur : une ligne française SANS accent doit être vue.
    temoin = "les cartes dans le worktree sont decoupees sans accents"
    toks = sorted({m.group(1).lower() for m in MOT_FR.finditer(temoin)})
    assert len(toks) >= SEUIL_LEXICAL, (
        "positive control FAILED: the detector no longer sees French prose at all (%d "
        "token(s) on %r) — the zero above is vacuous" % (len(toks), temoin))

    ecarts = []
    for rel in SLICE:
        for n, tks, txt in offenders(head_text(rel)):
            ecarts.append("%s:%d  [%s]  %s" % (rel, n, ",".join(tks), txt[:150]))
    assert not ecarts, (
        "French prose WITHOUT any diacritic still survives in the slice (threshold K>=%d "
        "distinct French-only words per line, 0 false positive measured over the %d "
        "accent-free lines of the plate's already-English zone):\n  "
        % (SEUIL_LEXICAL, n_lignes) + "\n  ".join(ecarts))
    print("witness blind spot: calibration zone %r = %d accent-free lines, 0 false "
          "positive; positive control %r -> %r; slice 9 flags %d"
          % (zone, n_lignes, temoin, toks, len(ecarts)))


# --------------------------------------------------------------------------- erreur


def test_erreur_un_fichier_oublie_est_nomme_avec_sa_ligne_par_le_meme_appel(tmp_path):
    """Erreur : un des fichiers de la slice est laissé entièrement français.

    La paire est mesurée dans le MÊME run : la slice vivante trie 0 (moitié positive — le
    RED de cette carte tant que la slice est française), puis un dépôt jetable où un
    fichier porte les octets FRANÇAIS EXACTS de la révision de référence trie 1 et le
    NOMME, avec les numéros de ligne recalculés depuis ces octets — et ne nomme aucun
    fichier traduit du même décor.
    """
    precondition_translated()
    p = scan(SLICE)
    assert p.returncode == 0, resume(
        p, "positive half of the pair: the translated slice must sort 0")

    oublie = SLICE[0]
    francais = git_show(oublie)
    literals = frozen_literals()
    attendu = expected_violations(francais, literals)
    assert attendu, ("the reference revision of %s carries no violation: the decor would "
                     "measure nothing" % oublie)

    fichiers = {rel: ENGLISH_STUB for rel in SLICE}
    fichiers[oublie] = francais
    root = build_tree(tmp_path / "oublie", fichiers)
    assert sha256_bytes(root.joinpath(oublie).read_text(encoding="utf-8")) == \
        sha256_bytes(francais), "the forgotten file of the decor is not the reference bytes"
    suivis = [r for r in tracked(root) if r.endswith(".md")]
    assert sorted(suivis) == sorted(SLICE), (
        "the decor must track exactly the four paths of the slice: %r -> %r"
        % (sorted(SLICE), sorted(suivis)))

    q = scan(SLICE, cwd=root)
    assert q.returncode == 1, resume(
        q, "a file of the slice left entirely French: exit 1 expected")
    trouves = reported(out_of(q))
    noms = sorted({rel for rel, _, _ in trouves})
    assert noms == [oublie], (
        "only the forgotten file must produce a violation, compared on the EXACT relative "
        "path (the corpus carries four README.md); named: %r\n%s" % (noms, out_of(q)))
    lignes = sorted({n for rel, n, _ in trouves if rel == oublie})
    assert lignes == attendu, (
        "%s: the scan reported line(s) %r, this bank recomputes %r from the same bytes (%s)"
        % (oublie, lignes, attendu, REF_REF))

    # discrimination du même appel, fichier par fichier : les stubs anglais trient 0
    for i, rel in enumerate(SLICE):
        if rel == oublie:
            continue
        s = scan([rel], cwd=root)
        assert s.returncode == 0, resume(s, "a translated file of the same decor: exit 0")
        assert out_of(s).strip() == "", (
            "the translated file must be silent:\n%r" % out_of(s))
    print("witness forgotten file: %s (bytes of %s) -> rc=1, %d line(s) named, %d "
          "recomputed; the 3 English stubs alone -> rc=0 silent"
          % (oublie, REF_REF, len(lignes), len(attendu)))


def test_erreur_le_scan_de_tout_le_corpus_nomme_aussi_le_fichier_oublie(tmp_path):
    """Erreur, branche d'énumération : la forme sans argument doit nommer aussi le fichier
    oublié.

    Même décor, mêmes octets, un chemin de code différent (`git ls-files` sur tout le
    corpus) : un défaut que seule une des deux formes voit est un défaut que le gate
    rapporte de façon incohérente. Le décor porte EN PLUS un `README.md` voisin français :
    le corpus compte quatre fichiers de ce nom et la slice en possède un, donc l'assertion
    est faite sur le CHEMIN RELATIF EXACT — un banc qui matche par suffixe accuserait la
    slice des lignes du voisin (et le lui reprocherait à elle).
    """
    precondition_translated()
    voisin = "docs/architecture/README.md"
    for oublie in (SLICE[1], SLICE[3]):
        fichiers = {rel: ENGLISH_STUB for rel in SLICE}
        fichiers[oublie] = git_show(oublie)
        fichiers[voisin] = git_show(oublie)          # un homonyme français, hors slice
        root = build_tree(tmp_path / ("corpus_%d" % SLICE.index(oublie)), fichiers)

        q = scan((), cwd=root)
        assert q.returncode == 1, resume(
            q, "whole-corpus scan of a decor holding one French file: exit 1 expected")
        noms = named_exact(out_of(q))
        assert oublie in noms, (
            "the whole-corpus scan must NAME the forgotten file %s; it named %r\n%s"
            % (oublie, noms, out_of(q)))
        assert voisin in noms, (
            "the homonym neighbour %s carries the same French bytes and must be named too: "
            "if it is not, this decor does not exercise the suffix discrimination it "
            "claims\n%s" % (voisin, out_of(q)))
        autres = [rel for rel in SLICE if rel != oublie and rel in noms]
        assert not autres, (
            "the English stubs of the SAME slice must not be named (the corpus carries "
            "four README.md: matching by basename or suffix imputes the neighbour's "
            "violation to this slice): %r\n%s" % (autres, out_of(q)))
        assert len([r for r in tracked(root) if r.endswith(".md")]) == len(SLICE) + 1, (
            "the decor must track the four slice paths plus one homonym neighbour")
        print("witness whole corpus in the decor: %s -> rc=%d, named %r (the neighbour %s "
              "is named, the translated stubs are not)" % (oublie, q.returncode, noms, voisin))


def sha256(path_or_bytes):
    if isinstance(path_or_bytes, bytes):
        return hashlib.sha256(path_or_bytes).hexdigest()
    return hashlib.sha256(Path(path_or_bytes).read_bytes()).hexdigest()


def sha256_bytes(data):
    return hashlib.sha256(data.encode("utf-8") if isinstance(data, str) else data).hexdigest()
