r"""Banc du scan de langue `pipeline/pj_lang_lint.py` (slice 2, volet RED — issue #2).

Sujets :

- `pipeline/pj_lang_lint.py` — le scan (livrable de dev-k, carte t_f2b6c1aa) ;
- `pipeline/pj_lang_lint.exclusions.yaml` — son fichier d'exclusion versionné.

Contrat d'interface exécuté par ce banc (figé par la carte t_ea1ae788) :

    python3 pipeline/pj_lang_lint.py [--exclusions F] [<chemin> ...]

- **sans argument** : énumère les .md SUIVIS du dépôt de travail (`git ls-files '*.md'`,
  résolu par `git rev-parse --show-toplevel` quand le cwd est un sous-répertoire),
  JAMAIS un parcours de répertoire (`os.walk` compte les copies des worktrees) ;
  rc 0 et sortie MUETTE si aucun diacritique ne subsiste hors des spans gelés ;
- **`<chemin>` explicite** : restreint le scan à ce chemin ; demandé et introuvable -> rc 2 ;
- **rc 0** = conforme ; **rc 1** = au moins une violation, chaque ligne NOMMANT chemin +
  ligne + le littéral fautif ; **rc 2** = erreur d'usage (chemin demandé introuvable,
  fichier d'exclusion absent ou illisible, drapeau inconnu) — jamais confondue avec une
  violation, et réciproquement.

Sémantique figée — **span, jamais ligne entière** : les spans correspondant aux littéraux
gelés sont RETIRÉS de la ligne, puis la ligne est signalée s'il y subsiste un diacritique.
Une ligne de prose qui matche un détecteur par faux positif est un ÉCHEC de la traduction,
pas une exclusion.

Note de banc, mesurée sur le corpus : la phrase citée par la carte
(`the five headers (\`Hors-scope\` / \`Out of scope\`) are frozen`) ne porte AUCUN
diacritique (`Hors-scope` n'en a pas) — elle ne peut donc pas falsifier la règle du span.
Le cas « littéral gelé isolé » est ici porté par un littéral RÉELLEMENT accentué et
réellement gelé du corpus, `Importé depuis`, cité au milieu de prose anglaise comme le
fait l'arbre après traduction (`pipeline/README.md`, `SOUL-template.md`).

Aucune horloge réelle, aucun aléa : les répertoires de travail sont des dépôts git
jetables construits par le banc, et l'énumération est celle de `git ls-files`.
"""
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
TOOL_REL = "pipeline/pj_lang_lint.py"
EXCLUSIONS_REL = "pipeline/pj_lang_lint.exclusions.yaml"
TOOL = REPO / TOOL_REL
EXCLUSIONS = REPO / EXCLUSIONS_REL

# Classe de caractères du contrat (identique à celle de la planche ratifiée et du banc
# de la slice 1) : lettres latines à diacritique ou ligature, minuscules et majuscules.
ACCENTS = "àâäçéèêëîïôöùûüÿœæñÀÂÄÇÉÈÊËÎÏÔÖÙÛÜŸŒÆÑ"

# Les 2 SEULS littéraux gelés (protocoles machine verbatim). Les 5 titres de section et
# les messages du linter sont TRADUITS par la slice 2 (décision humaine du 20/09) : les
# mettre ici serait un classement périmé.
PROTOCOLES = ("Importé depuis", "ROOM:")

# Littéral accentué et gelé, cité par le corpus après traduction. C'est LUI qui porte la
# preuve du span : `Hors-scope` (l'exemple de la carte) n'a pas de diacritique.
GELÉ_ACCENTUE = "Importé depuis"

_CORPS_PROPRE = "# Title\n\nAll English prose, without a single diacritic.\n"


# --------------------------------------------------------------------------- outils


def _require_sujets():
    """Rouge explicite quand un livrable de dev-k manque encore (RED légitime)."""
    manquants = [rel for rel, p in ((TOOL_REL, TOOL), (EXCLUSIONS_REL, EXCLUSIONS))
                 if not p.is_file()]
    if manquants:
        pytest.fail(
            "livrable de la slice absent de l'arbre : %s\n"
            "le banc est écrit AVANT l'implémentation (peer programming test ∥ dev) : "
            "cet échec est le RED attendu." % ", ".join(manquants)
        )


def scan(args=(), cwd=REPO, exclusions=None, env=None):
    """Lance le scan. Retourne le CompletedProcess (rc = contrat)."""
    cmd = [sys.executable, str(TOOL)]
    if exclusions is not None:
        cmd += ["--exclusions", str(exclusions)]
    cmd += [str(a) for a in args]
    return subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True,
                          timeout=180, env=env)


def body(sections):
    """Corps de .md + le NUMÉRO DE LIGNE de chaque section, MESURÉ.

    Le banc ne code jamais un numéro de ligne en dur : un décalage d'une ligne dans le
    décor ferait échouer le sujet à juste titre et le banc le lui imputerait (défaut
    mesuré sur la première version de ce fichier : le décor plaçait la prose en ligne 3,
    le cas attendait la ligne 4). `sections` est une liste de blocs séparés par une
    ligne vide ; le numéro retourné est celui du PREMIER caractère du bloc.
    """
    lines, nums = [], []
    for bloc in sections:
        if lines:
            lines.append("")
        nums.append(len(lines) + 1)
        lines.extend(bloc.split("\n"))
    return "\n".join(lines) + "\n", nums


def git(repo, *args, env=None):
    p = subprocess.run(["git", "-C", str(repo), *args], capture_output=True,
                       text=True, env=env)
    assert p.returncode == 0, "git %s a échoué : %s" % (" ".join(args), p.stderr)
    return p.stdout


def tracked_md(repo):
    """Énumération canonique du banc : `git ls-files '*.md'` (le sujet, lui, doit la
    produire seul — le banc l'utilise pour MONTRER que son décor discrimine)."""
    return sorted(x for x in git(repo, "ls-files", "-z", "*.md").split("\x00") if x)


def walk_md(repo):
    """Ce qu'un `os.walk('.')` verrait : le contre-exemple, mesuré dans le même run."""
    return sorted(str(p.relative_to(repo)) for p in Path(repo).rglob("*.md")
                  if ".git" not in p.parts)


def build_tree(root, files, tracked):
    """Dépôt git jetable : `files` = {chemin: contenu}, `tracked` = chemins indexés.

    Le fichier d'exclusion est recopié au chemin CANONIQUE dans le fixture : ainsi un
    scan « sans argument » trouve ses exclusions, qu'il les résolve relativement au cwd
    ou relativement au script — le banc ne fige pas ce détail-là.
    """
    env = dict(os.environ)
    env.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1",
               GIT_TERMINAL_PROMPT="0", HOME=str(root))
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    git(root, "init", "-q", env=env)
    for rel, txt in files.items():
        cible = root / rel
        cible.parent.mkdir(parents=True, exist_ok=True)
        cible.write_text(txt, encoding="utf-8")
    ex = root / EXCLUSIONS_REL
    ex.parent.mkdir(parents=True, exist_ok=True)
    ex.write_text(EXCLUSIONS.read_text(encoding="utf-8"), encoding="utf-8")
    git(root, "add", "--", *(list(tracked) + [EXCLUSIONS_REL]), env=env)
    return env


def out_of(p):
    return p.stdout + p.stderr


def _lines(p):
    return [l for l in out_of(p).splitlines() if l.strip()]


STRICT_RE = re.compile(r"([\w./\-]+\.md):(\d+)")
LOOSE_RE = re.compile(r"([\w./\-]+\.md)\D{0,12}?(\d+)")


def reported(out):
    """Violations imprimées, lues sous la forme stricte `chemin:NN`.

    La forme stricte est celle que le contrat nomme (« chemin, ligne »). La forme lâche
    (`chemin … NN`) n'est essayée que si AUCUNE forme stricte n'apparaît : sans cette
    priorité, une ligne de synthèse comme « 20 .md suivis, 3 052 lignes » fabriquerait
    des violations fantômes sur le chemin « .md », et le banc imputerait au sujet une
    erreur de son propre lecteur.
    """
    strict = {}
    for l in out.splitlines():
        for m in STRICT_RE.finditer(l):
            cle = (m.group(1), int(m.group(2)))
            strict.setdefault(cle, l.strip())
    if strict:
        return [(rel, num, l) for (rel, num), l in sorted(strict.items())]

    vus, uniq = set(), []
    for l in out.splitlines():
        for m in LOOSE_RE.finditer(l):
            cle = (m.group(1), int(m.group(2)))
            if cle in vus:
                continue
            vus.add(cle)
            uniq.append((cle[0], cle[1], l.strip()))
    return uniq


def resume(p, quoi):
    return ("%s : rc=%d attendu\n--- stdout ---\n%s\n--- stderr ---\n%s"
            % (quoi, p.returncode, p.stdout, p.stderr))


def _load_exclusions():
    """Charge le fichier d'exclusion en objet Python (YAML si possible)."""
    txt = EXCLUSIONS.read_text(encoding="utf-8")
    try:
        import yaml
    except ImportError:  # pragma: no cover - pyyaml est présent dans cet environnement
        return None, txt
    try:
        return yaml.safe_load(txt), txt
    except Exception:
        return None, txt


def _strings(node):
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for v in node.values():
            yield from _strings(v)
    elif isinstance(node, (list, tuple)):
        for v in node:
            yield from _strings(v)


def _dicts(node):
    if isinstance(node, dict):
        yield node
        for v in node.values():
            yield from _dicts(v)
    elif isinstance(node, (list, tuple)):
        for v in node:
            yield from _dicts(v)


REF_RE = re.compile(r"^([\w./\-]+\.py):(\d+)$")


def _split_ref(ref):
    """Décompose `script.py:NN` — lève si la forme n'est pas celle du contrat."""
    m = REF_RE.match(ref)
    if not m:
        raise ValueError("référence de lecteur invalide : %r" % ref)
    return m.group(1), int(m.group(2))


def _direct_strings(d):
    """Chaînes portées par CE nœud (pas par ses sous-conteneurs)."""
    return [v.strip() for v in d.values() if isinstance(v, str) and v.strip()]


def _entries_with_reader(doc):
    """Entrées MINIMALES qui citent un lecteur `script.py:NN`.

    Minimale = le nœud porte lui-même la référence et aucun de ses descendants n'en
    porte : un nœud parent ne doit pas croiser le littéral de ses enfants avec la
    référence d'un autre.
    """
    out = []
    for d in _dicts(doc):
        direct = _direct_strings(d)
        refs = [s for s in direct if REF_RE.match(s)]
        if not refs:
            continue
        enfants = [v for v in d.values() if isinstance(v, (dict, list, tuple))]
        if any(REF_RE.match(s) for v in enfants for s in _strings(v)):
            continue  # un descendant porte aussi une référence : ce nœud n'est pas minimal
        lits = [s for s in direct if s not in refs
                and (any(c in ACCENTS for c in s) or s in PROTOCOLES)]
        out.append((refs, lits))
    return out


# --------------------------------------------------------------------------- cas


def test_nominal_un_corpus_propre_sort_exit_0_et_ne_parle_pas(tmp_path):
    """Scénario nominal — un répertoire de travail sans diacritique hors span gelé.

    `pj_lang_lint.py` exécuté SANS ARGUMENT depuis ce répertoire : l'énumération est
    celle de `git ls-files`, la sortie est vide et le code de retour est 0.
    """
    _require_sujets()
    root = tmp_path / "propre"
    fichiers = {
        "README.md": _CORPS_PROPRE,
        "docs/guide.md": "# Guide\n\nNested English file, still clean.\n",
        "docs/deep/fr.md": "# Deep\n\nNothing accented here either.\n",
    }
    build_tree(root, fichiers, list(fichiers))

    suivi = tracked_md(root)
    assert len(suivi) == len(fichiers), (
        "le décor du banc doit indexer exactement ses .md : %r" % suivi)

    p = scan(cwd=root)
    assert p.returncode == 0, resume(
        p, "corpus propre, scan sans argument : exit 0")
    assert out_of(p).strip() == "", (
        "un corpus propre doit être MUET (aucun point signalé) ; sortie obtenue :\n%r"
        % out_of(p))
    print("witness corpus propre : %d .md suivis, rc=0, sortie vide" % len(suivi))


def test_nominal_un_fichier_suivi_accentue_est_signale_chemin_ligne_et_litteral(tmp_path):
    """Nominal (non-vacuité) — le scan ne peut pas être un outil qui sort toujours 0.

    Un seul .md indexé porte une ligne accentuée, dans un SOUS-RÉPERTOIRE : il doit être
    signalé, avec son chemin, son numéro de ligne ET le texte fautif.
    """
    _require_sujets()
    root = tmp_path / "sale"
    faute = "The déployé prose is not English, and this line carries the diacritic."
    contenu, nums = body(["# Note", faute])
    ligne_faute = nums[1]
    fichiers = {
        "README.md": _CORPS_PROPRE,
        "docs/sub/note.md": contenu,
        "docs/sub/clean.md": "# Clean\n\nEnglish only.\n",
    }
    build_tree(root, fichiers, list(fichiers))

    p = scan(cwd=root)
    attendu = "docs/sub/note.md"
    assert p.returncode == 1, resume(p, "un .md suivi accentué : exit 1")
    trouves = reported(out_of(p))
    assert trouves, ("la sortie doit nommer la violation sous la forme chemin + ligne ;\n"
                     "%s" % resume(p, "message de violation"))
    assert any(attendu in rel for rel, _, _ in trouves), (
        "le chemin fautif %r doit être nommé ; violations lues : %r"
        % (attendu, [(r, n) for r, n, _ in trouves]))
    assert any(n == ligne_faute for rel, n, _ in trouves if attendu in rel), (
        "la LIGNE fautive (%d, MESURÉE dans le décor) doit être nommée ; "
        "violations lues : %r" % (ligne_faute, [(r, n) for r, n, _ in trouves]))
    assert "déployé" in out_of(p), (
        "le littéral fautif doit être cité dans le message (la carte dev exige "
        "« chemin, ligne et littéral fautif ») :\n%s" % out_of(p))
    print("witness violation : %s" % [(r, n) for r, n, _ in trouves])


def test_limite_un_diacritique_dans_un_span_gele_n_est_pas_signale(tmp_path):
    """Scénario limite (1re moitié) — « littéral gelé isolé » : blanchi AU SPAN.

    Prose anglaise citant le protocole gelé verbatim, entre backticks, comme l'arbre le
    fait après traduction. Le diacritique vit DANS le span gelé : rien à signaler.
    """
    _require_sujets()
    root = tmp_path / "gele"
    ligne = "The deployer reads `%s` to find the issue number." % GELÉ_ACCENTUE
    contenu, nums = body(["# Pipeline", ligne])
    fichiers = {
        "pipeline/README.md": contenu,
        "README.md": _CORPS_PROPRE,
    }
    build_tree(root, fichiers, list(fichiers))
    assert any(c in ACCENTS for c in ligne), "le décor doit porter un diacritique réel"
    # L'exemple de la carte (`Hors-scope` / `Out of scope`) n'est PAS utilisable ici :
    # mesuré, `Hors-scope` ne porte aucun diacritique, donc la ligne ne peut pas
    # falsifier la règle du span. Le banc mesure donc l'absence de diacritique hors span.
    assert not any(c in ACCENTS for c in ligne.replace(GELÉ_ACCENTUE, "")), (
        "le décor doit n'avoir de diacritique QUE dans le span gelé : %r" % ligne)

    p = scan(cwd=root)
    assert p.returncode == 0, resume(
        p, "diacritique entièrement contenu dans un span gelé : exit 0")
    assert out_of(p).strip() == "", (
        "un span gelé blanchi au SPAN (pas à la ligne) ne laisse aucun point à "
        "signaler :\n%r" % out_of(p))
    print("witness span gelé : %r -> rc=0" % ligne)


def test_limite_la_prose_francaise_hors_du_span_gele_est_signalee(tmp_path):
    """Scénario limite (2de moitié) — la MÊME ligne, un mot accentué hors du span.

    C'est la moitié qui falsifie « blanchi à la ligne » : un outil qui retirerait toute
    la ligne dès qu'elle porte un littéral gelé sortirait 0 ici. `déployé` est hors du
    span, donc la ligne est un ÉCHEC de traduction.
    """
    _require_sujets()
    root = tmp_path / "hors_span"
    ligne = "The déployé reads `%s` to find the issue number." % GELÉ_ACCENTUE
    contenu, nums = body(["# Pipeline", ligne])
    ligne_faute = nums[1]
    fichiers = {"pipeline/README.md": contenu}
    build_tree(root, fichiers, list(fichiers))

    p = scan(cwd=root)
    assert p.returncode == 1, resume(
        p, "prose française hors du span gelé, sur la même ligne : exit 1")
    trouves = reported(out_of(p))
    assert any("pipeline/README.md" in rel and n == ligne_faute for rel, n, _ in trouves), (
        "la ligne %d (MESURÉE dans le décor) doit être nommée ; violations lues : %r\n%s"
        % (ligne_faute, [(r, n) for r, n, _ in trouves], out_of(p)))
    assert "déployé" in out_of(p), (
        "le message doit citer le littéral fautif (hors span) :\n%s" % out_of(p))
    print("witness hors span : %r -> rc=1 %s"
          % (ligne, [(r, n) for r, n, _ in trouves]))


def test_limite_un_md_non_suivi_n_est_jamais_signale(tmp_path):
    """Limite — l'énumération est celle de l'INDEX, jamais un parcours de répertoire.

    Deux .md accentués NON SUIVIS (dont une copie de corpus sous `.worktrees/`, ce que
    `os.walk` verrait) et un .md suivi propre : la sortie doit être muette. Le même run
    imprime les deux comptages, pour que « muet » ne soit pas un vert vide.
    """
    _require_sujets()
    root = tmp_path / "non_suivi"
    fichiers = {
        "README.md": _CORPS_PROPRE,
        "untracked-note.md": "# Non suivi\n\nLigne accentuée, hors index.\n",
        ".worktrees/t_other/README.md": "# Copie de worktree\n\nélevé, accentué.\n",
    }
    build_tree(root, fichiers, ["README.md"])

    suivi, vus = tracked_md(root), walk_md(root)
    assert suivi == ["README.md"], "index attendu : %r" % suivi
    assert len(vus) == 3, (
        "le décor doit discriminer : %d .md marchés vs %d indexés" % (len(vus), len(suivi)))
    print("witness énumération : git ls-files -> %r · os.walk -> %r" % (suivi, vus))

    p = scan(cwd=root)
    assert p.returncode == 0, resume(
        p, "aucun .md accentué SUIVI : exit 0 (les non suivis ne sont pas du corpus)")
    assert out_of(p).strip() == "", (
        "les .md non suivis ne doivent rien produire :\n%r" % out_of(p))


def test_limite_un_chemin_explicite_restreint_le_scan_a_ce_chemin(tmp_path):
    """Limite — un chemin demandé est SCANNÉ, et lui seul.

    Deux .md indexés accentués : demander `a.md` doit signaler `a.md` et NE PAS signaler
    `b.md`. Un scan qui ignorerait l'argument positionnel nommerait les deux — et
    passerait pourtant les cas « un seul fichier accentué » plus haut.
    """
    _require_sujets()
    root = tmp_path / "explicite"
    fichiers = {
        "a.md": "# A\n\nThe déployé text of a.\n",
        "b.md": "# B\n\nLe protocole est gelé.\n",
        "c.md": _CORPS_PROPRE,
    }
    build_tree(root, fichiers, list(fichiers))

    p = scan(args=["a.md"], cwd=root)
    assert p.returncode == 1, resume(p, "scan de a.md (accentué) : exit 1")
    noms = [rel for rel, _, _ in reported(out_of(p))]
    assert any("a.md" in n for n in noms), (
        "a.md doit être nommé ; violations lues : %r" % noms)
    assert not any(n.endswith("b.md") for n in noms), (
        "b.md n'était PAS demandé : le scan doit se restreindre au chemin donné ; "
        "violations lues : %r\n%s" % (noms, out_of(p)))

    p2 = scan(args=["c.md"], cwd=root)
    assert p2.returncode == 0, resume(p2, "scan de c.md (propre) : exit 0")
    assert out_of(p2).strip() == "", (
        "c.md est propre : la sortie doit être muette ; obtenu %r" % out_of(p2))
    print("witness restriction : a.md -> %r · c.md -> rc=0 muet" % noms)


def test_nominal_le_fichier_d_exclusion_porte_les_deux_protocoles_et_sa_provenance():
    """Nominal — le fichier d'exclusion est un ARTEFACT VÉRIFIABLE, pas une déclaration.

    Deux exigences : les 2 protocoles gelés y sont déclarés (dont le seul accentué,
    `Importé depuis`, que le corpus cite après traduction), et chaque entrée qui cite un
    lecteur `script.py:NN` cite une ligne qui porte RÉELLEMENT l'un des littéraux de CETTE
    entrée.

    PORTÉE DU CONTRÔLE, mesurée et déclarée : cette vérification porte sur la LIGNE citée,
    pas sur l'identité « cette ligne est la seule / la bonne » à porter le littéral. Un
    lecteur qui définit le littéral sur une autre ligne légitime (`pj_room_keeper.py:38`,
    `ROOM_MARKER = "ROOM:"`) et cite `:76` (la regex qui l'ANCRE dans le body) est
    conforme ; citer `:38` le serait aussi. Ce que le banc refuse, c'est citer une ligne
    qui ne porte pas le littéral du tout. Conséquence assumée : la mutation qui déplace la
    citation vers une AUTRE ligne légitime ne mord pas — c'est une portée, pas un trou.
    """
    _require_sujets()
    doc, txt = _load_exclusions()
    assert txt.strip(), "le fichier d'exclusion est vide"
    for lit in PROTOCOLES:
        assert lit in txt, (
            "le protocole gelé %r doit être déclaré dans %s (le corpus le cite verbatim "
            "après traduction : sans exclusion, le scan signale une traduction "
            "CORRECTE)" % (lit, EXCLUSIONS_REL))

    assert doc is not None, (
        "%s doit être du YAML lisible — le fichier est en .yaml précisément pour sortir "
        "du périmètre .md du scan" % EXCLUSIONS_REL)

    entrees = _entries_with_reader(doc)
    ecarts, verifies = [], 0
    for refs, lits in entrees:
        for ref in refs:
            rel, num = _split_ref(ref)
            f = REPO / rel
            if not f.is_file():
                ecarts.append("%s : le fichier cité n'existe pas" % ref)
                continue
            src = f.read_text(encoding="utf-8").splitlines()
            if num > len(src):
                ecarts.append("%s : ligne hors du fichier (%d lignes)" % (ref, len(src)))
                continue
            if not lits:
                verifies += 1
                continue
            # comparaison insensible à la casse : `pj_card_lint` lit le body en .lower()
            if not any(lit.lower() in src[num - 1].lower() for lit in lits):
                ecarts.append(
                    "%s ne porte aucun des littéraux déclarés %r (ligne : %r)"
                    % (ref, lits, src[num - 1].strip()[:90]))
            verifies += 1
    assert entrees, ("aucune entrée du fichier d'exclusion ne cite un lecteur "
                     "`script.py:NN` : la provenance est déclarative, donc invérifiable")
    assert not ecarts, (
        "provenance du fichier d'exclusion FAUSSE (chaque entrée doit être relue par le "
        "script cité) :\n  - " + "\n  - ".join(ecarts))
    print("witness exclusions : %d entrée(s) avec lecteur, %d référence(s) vérifiée(s)"
          % (len(entrees), verifies))


def test_nominal_sur_l_arbre_de_la_branche_chaque_violation_imprimee_est_reelle():
    """Nominal — sur l'arbre RÉEL, chaque violation imprimée est re-vérifiée par le banc.

    Assertion stable pendant tout l'issue : l'arbre est encore français aujourd'hui et
    le sera moins demain, donc le banc ne fige PAS le nombre de violations (ce serait un
    test qui se retourne tout seul). Il exige la propriété qui, elle, ne bouge pas :
    tout ce qui est signalé porte un diacritique hors des spans gelés — et la ligne est
    re-testée indépendamment, avec sa propre définition du span.
    """
    _require_sujets()
    p = scan(cwd=REPO)
    assert p.returncode in (0, 1), resume(
        p, "scan de l'arbre de la branche : 0 (conforme) ou 1 (violations)")
    out = out_of(p)
    trouves = reported(out)
    if p.returncode == 0:
        assert not trouves, ("rc=0 avec des violations imprimées : %r" % trouves)
        print("witness arbre : rc=0, aucune violation")
        return

    assert trouves, ("rc=1 sans aucune violation nommée `chemin:ligne` : le message ne "
                     "permet pas de corriger\n%s" % out)
    doc, _txt = _load_exclusions()
    literals = set(PROTOCOLES)
    if doc is not None:
        literals |= {s.strip() for s in _strings(doc)
                     if any(c in ACCENTS for c in s) and len(s.strip()) > 2}
    faux = []
    for rel, num, ligne in trouves:
        f = REPO / rel
        if not f.is_file():
            f = REPO / rel.lstrip("./")
        if not f.is_file():
            faux.append("%s : chemin signalé introuvable dans l'arbre" % rel)
            continue
        src = f.read_text(encoding="utf-8", errors="replace").splitlines()
        if num > len(src):
            faux.append("%s:%d : ligne hors du fichier (%d lignes)" % (rel, num, len(src)))
            continue
        reste = src[num - 1]
        for lit in literals:
            reste = reste.replace(lit, "")
        # tolérance d'espaces : un littéral gelé est verbatim, mais un scan peut
        # normaliser les runs d'espaces autour de lui.
        reste = re.sub(r"\s+", " ", reste)
        if not any(c in ACCENTS for c in reste):
            faux.append("%s:%d signalé à tort (aucun diacritique hors span gelé) : %r"
                        % (rel, num, src[num - 1].strip()[:90]))
    assert not faux, ("le scan signale des lignes qui ne portent aucun diacritique hors "
                      "span gelé :\n  - " + "\n  - ".join(faux))
    print("witness arbre réel : rc=1, %d violation(s) nommée(s), toutes re-vérifiées "
          "(première : %s:%d)" % (len(trouves), trouves[0][0], trouves[0][1]))


def test_erreur_un_chemin_demande_introuvable_sort_2_et_pas_1(tmp_path):
    """Scénario erreur — un chemin explicite introuvable est une ERREUR, pas une violation.

    Le code de retour doit dire « je n'ai pas pu lire ce que tu m'as demandé » (2), sans
    se confondre avec « le corpus n'est pas conforme » (1) ni avec « tout va bien » (0).
    """
    _require_sujets()
    root = tmp_path / "introuvable"
    fichiers = {"README.md": _CORPS_PROPRE}
    build_tree(root, fichiers, ["README.md"])

    absent = root / "docs" / "nexistepas.md"
    p = scan(args=[str(absent)], cwd=root)
    assert p.returncode == 2, resume(
        p, "chemin demandé introuvable (rc 2, jamais 1 : l'erreur n'est pas une violation)")
    assert out_of(p).strip(), "un chemin introuvable doit produire un message d'usage"
    assert "nexistepas.md" in out_of(p), (
        "le message doit nommer le chemin demandé :\n%s" % out_of(p))
    print("witness chemin introuvable : rc=%d %r"
          % (p.returncode, out_of(p).strip().splitlines()[0][:100]))


def test_erreur_un_drapeau_inconnu_sort_2(tmp_path):
    """Erreur — un drapeau inconnu est une erreur d'usage, pas un scan silencieux."""
    _require_sujets()
    root = tmp_path / "drapeau"
    fichiers = {"README.md": _CORPS_PROPRE}
    build_tree(root, fichiers, ["README.md"])

    p = scan(args=["--nope"], cwd=root)
    assert p.returncode == 2, resume(p, "drapeau inconnu : exit 2")
    print("witness drapeau inconnu : rc=%d" % p.returncode)


def test_erreur_un_fichier_d_exclusion_introuvable_sort_2(tmp_path):
    """Erreur — `--exclusions` introuvable : refus explicite, jamais un scan sans
    exclusions qui signalerait des traductions correctes."""
    _require_sujets()
    root = tmp_path / "excl_absente"
    ligne = "The deployer reads `%s` to find the issue number." % GELÉ_ACCENTUE
    fichiers = {"pipeline/README.md": "# Pipeline\n\n%s\n" % ligne}
    build_tree(root, fichiers, list(fichiers))

    p = scan(cwd=root, exclusions=root / "docs" / "jamais.yaml")
    assert p.returncode == 2, resume(
        p, "fichier d'exclusion demandé et introuvable : exit 2")
    print("witness exclusions introuvables : rc=%d" % p.returncode)


def test_erreur_un_fichier_d_exclusion_illisible_sort_2(tmp_path):
    """Erreur — un fichier d'exclusion illisible ne se rattrape pas en silence."""
    _require_sujets()
    root = tmp_path / "excl_cassee"
    fichiers = {
        "README.md": _CORPS_PROPRE,
        "pipeline/cassee.yaml": "litteraux: [ceci: n'est pas du yaml\n",
    }
    build_tree(root, fichiers, ["README.md"])

    p = scan(cwd=root, exclusions=root / "pipeline" / "cassee.yaml")
    assert p.returncode == 2, resume(
        p, "fichier d'exclusion illisible : exit 2")
    print("witness exclusions illisibles : rc=%d" % p.returncode)
