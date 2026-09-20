r"""Banc de la slice 3 « documents racine » (volet RED — issue #2, carte t_ae7c2da3).

Sujets (les fichiers de la slice, traduits par dev-3, carte t_6f1eaf1b) :

    README.md · CONTRIBUTING.md · workflows/templates/ticket.md

Vérificateur exécuté : `pipeline/pj_lang_lint.py` (livrable de la slice 2, carte
t_f2b6c1aa) et son fichier d'exclusion `pipeline/pj_lang_lint.exclusions.yaml`.
Le banc ne réimplémente pas le scan : il l'EXÉCUTE par sous-processus, et recalcule de
son côté la règle qu'il juge (span, jamais ligne) pour ne pas juger le sujet avec sa
propre implémentation.

Contrat d'interface exécuté (figé par cette carte, publié sous la clé blackboard
`contrat-3`) :

    python3 pipeline/pj_lang_lint.py [--exclusions F] [<chemin> ...]

- rc 0 = conforme ET MUET (stdout/stderr vides) ; rc 1 = au moins une violation, chaque
  ligne nommant `chemin:NN` et le littéral fautif ; rc 2 = erreur d'usage — jamais
  confondue avec une violation, et réciproquement ;
- la ligne est blanchie AU SPAN des littéraux gelés, jamais à la ligne entière.

Les trois natures de la slice (1 nominal + 1 limite + 1 erreur) :

- nominal — le scan sort 0 et ne nomme aucun des 3 fichiers, en appel « chemins
            explicites » ET en appel « tout le corpus suivi » ;
- limite  — les littéraux gelés restent verbatim : aucune citation DÉCATIE (une citation
            décaties = la forme sans accent du littéral, présentée dans la slice), et le
            fichier d'exclusion n'est PAS élargi pour blanchir du français restant ;
- erreur  — un fichier de la slice laissé entièrement français : le MÊME appel (les
            chemins de la slice) sort 1 en le nommant, et ne nomme aucun des fichiers
            traduits du même décor.

Aucune horloge réelle, aucun aléa : les décors jetables sont des dépôts git construits
par le banc, et l'énumération est celle de `git ls-files`.
"""
import os
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SLICE = ("README.md", "CONTRIBUTING.md", "workflows/templates/ticket.md")
SCAN_REL = "pipeline/pj_lang_lint.py"
EXCLUSIONS_REL = "pipeline/pj_lang_lint.exclusions.yaml"
SCAN = REPO / SCAN_REL
EXCLUSIONS = REPO / EXCLUSIONS_REL

# Classe de caractères du contrat (identique à la planche ratifiée et aux bancs des
# slices 1 et 2) : lettres latines à diacritique + ligatures, minuscules ET majuscules.
ACCENTS = "àâäçéèêëîïôöùûüÿœæñÀÂÄÇÉÈÊËÎÏÔÖÙÛÜŸŒÆÑ"

# Les 2 SEULS littéraux gelés (protocoles machine verbatim). Le banc les gèle ici : la
# slice 3 ne peut ni les traduire ni en ajouter d'autres au fichier d'exclusion.
PROTOCOLES = ("Importé depuis", "ROOM:")

CORPS_ANGLAIS = ("# Title\n\nAll English prose, without a single diacritic.\n"
                 "No protocol is cited on this line.\n")


# --------------------------------------------------------------------------- outils


def _require_outils():
    """Rouge explicite quand un livrable de la slice 2 manque (RED légitime)."""
    manquants = [rel for rel, p in ((SCAN_REL, SCAN), (EXCLUSIONS_REL, EXCLUSIONS))
                 if not p.is_file()]
    if manquants:
        pytest.fail(
            "vérificateur de la slice 2 absent de l'arbre : %s\n"
            "le banc de la slice 3 exécute le scan de la slice 2 : sans lui, il n'y a "
            "rien à exécuter." % ", ".join(manquants))


def tracked(repo):
    """Énumération canonique : `git ls-files '*.md'` — jamais un parcours de répertoire."""
    p = subprocess.run(["git", "-C", str(repo), "ls-files", "-z", "*.md"],
                       capture_output=True, timeout=120)
    assert p.returncode == 0, "git ls-files a échoué : %s" % p.stderr.decode()
    return sorted(x.decode("utf-8") for x in p.stdout.split(b"\x00") if x)


def lines_of(rel):
    """(numéro, ligne) de chaque ligne du fichier de la slice — numéros MESURÉS."""
    text = (REPO / rel).read_text(encoding="utf-8", errors="replace")
    return list(enumerate(text.splitlines(), 1))


def accented(rel):
    return [(n, l) for n, l in lines_of(rel) if any(c in ACCENTS for c in l)]


def sans_accent(txt):
    """Forme sans diacritique : ce que deviendrait une citation « décaties »."""
    decomposed = unicodedata.normalize("NFD", txt)
    return "".join(c for c in decomposed if unicodedata.category(c) != "Mn")


def litteraux_geles():
    """Littéraux gelés DÉCLARÉS par le fichier d'exclusion (lecture indépendante).

    Le banc ne demande pas au scan quels littéraux il blanchit : il les relit lui-même,
    sinon une exemption ajoutée par la slice passerait inaperçue — et c'est
    précisément le contournement que le cas limite doit refuser.
    """
    txt = EXCLUSIONS.read_text(encoding="utf-8")
    lits = re.findall(r"""litteral\s*:\s*["']([^"']+)["']""", txt)
    lits += re.findall(r"""^\s*-\s*["']([^"']+)["']\s*$""", txt, re.M)
    return list(dict.fromkeys(lits))


def residual(line, literals):
    """La ligne moins chaque span gelé : ce qui reste est la prose jugée."""
    for lit in literals:
        if lit:
            line = line.replace(lit, "")
    return line


def scan(args=(), cwd=REPO, exclusions=None):
    cmd = [sys.executable, str(SCAN)]
    if exclusions is not None:
        cmd += ["--exclusions", str(exclusions)]
    cmd += [str(a) for a in args]
    return subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True,
                          timeout=180)


def out_of(p):
    return p.stdout + p.stderr


def resume(p, quoi):
    return ("%s : rc=%d\n--- stdout ---\n%s\n--- stderr ---\n%s"
            % (quoi, p.returncode, p.stdout, p.stderr))


STRICT_RE = re.compile(r"([\w./\-]+\.md):(\d+)")


def reported(out):
    """Violations imprimées, lues sous la forme stricte `chemin:NN` du contrat.

    La forme stricte est celle que la carte prescrit (« il sort exit 1 et le fichier
    oublié est nommé ») : sans elle, la ligne de synthèse du scan (« N line(s) in M
    file(s) — K tracked .md scanned ») fabriquerait des violations fantômes.
    """
    vus, uniq = set(), []
    for ligne in out.splitlines():
        for m in STRICT_RE.finditer(ligne):
            cle = (m.group(1), int(m.group(2)))
            if cle in vus:
                continue
            vus.add(cle)
            uniq.append((cle[0], cle[1], ligne.strip()))
    return uniq


def corps_francais():
    """Contenu « resté français » du décor + le NUMÉRO DE LIGNE de chaque bloc (MESURÉ).

    Le banc ne code aucun numéro de ligne en dur : un décalage d'une ligne dans le décor
    ferait échouer le sujet à juste titre et le banc le lui imputerait.
    """
    blocs = [
        "# Contributing",
        "Merci de l'intérêt : ce dépôt est un pipeline d'agents.",
        "Toute modification non triviale commence par une issue, avec la commande exacte.",
    ]
    lignes, nums = [], []
    for bloc in blocs:
        if lignes:
            lignes.append("")
        nums.append(len(lignes) + 1)
        lignes.extend(bloc.split("\n"))
    return "\n".join(lignes) + "\n", nums


def git(repo, *args, env=None):
    p = subprocess.run(["git", "-C", str(repo), *args], capture_output=True,
                       text=True, env=env)
    assert p.returncode == 0, "git %s a échoué : %s" % (" ".join(args), p.stderr)
    return p.stdout


def build_tree(root, files, tracked_paths):
    """Dépôt git jetable : `files` = {chemin: contenu}, `tracked_paths` = index.

    Le fichier d'exclusion est recopié au chemin CANONIQUE dans le décor : un scan « sans
    argument » y trouve ses exclusions, qu'il les résolve depuis la racine git, depuis le
    cwd ou depuis le script — le banc ne fige pas ce détail-là.
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
    git(root, "add", "--", *(list(tracked_paths) + [EXCLUSIONS_REL]), env=env)
    return env


def _etat_traduit():
    """Précondition des scénarios nominal et limite : la slice EST traduite.

    Le banc est écrit AVANT la traduction (peer programming test ∥ dev, même worktree) :
    tant que dev-3 n'a pas livré, cet échec EST le RED attendu — et il NOMME le fichier,
    la ligne et le littéral fautif, pour que le RED soit actionnable et pas un booléen.
    """
    _require_outils()
    absents = [rel for rel in SLICE
               if not (REPO / rel).is_file() or rel not in tracked(REPO)]
    if absents:
        pytest.fail("fichier(s) de la slice absent(s) du disque ou de l'index : %s\n"
                    "corpus suivi : %r" % (", ".join(absents), tracked(REPO)))

    lits = litteraux_geles()
    restes, total = [], 0
    for rel in SLICE:
        for num, ligne in lines_of(rel):
            if not any(c in ACCENTS for c in ligne):
                continue
            total += 1
            reste = residual(ligne, lits)
            if any(c in ACCENTS for c in reste):
                restes.append("%s:%d — %s" % (rel, num, reste.strip()[:70]))
    if restes:
        pytest.fail(
            "slice 3 NON traduite : %d ligne(s) accentuée(s) dont %d hors span gelé.\n"
            "  - %s\n"
            "(le banc est écrit AVANT la traduction : cet échec est le RED attendu)"
            % (total, len(restes), "\n  - ".join(restes[:8])))


# --------------------------------------------------------------------------- cas


def test_nominal_le_scan_sort_0_et_ne_nomme_aucun_fichier_de_la_slice():
    """Scénario nominal — les 3 fichiers de la slice ne portent plus de diacritique hors
    span gelé : le scan sort 0, muet, en appel « chemins explicites » ET en appel « tout
    le corpus suivi ».
    """
    _etat_traduit()

    p = scan(list(SLICE), cwd=REPO)
    assert p.returncode == 0, resume(
        p, "scan des 3 fichiers de la slice traduits : exit 0 attendu")
    assert out_of(p).strip() == "", (
        "un corpus conforme doit être MUET ; sortie obtenue :\n%r" % out_of(p))

    # LE MÊME contrat, en appel « tout le corpus suivi » : la slice ne doit plus y figurer,
    # quel que soit l'état des autres slices (le banc ne fige donc jamais un total global).
    q = scan((), cwd=REPO)
    assert q.returncode in (0, 1), resume(
        q, "scan de tout le corpus suivi : 0 (conforme) ou 1 (violations ailleurs)")
    noms = {rel for rel, _, _ in reported(out_of(q))}
    # Comparaison sur le CHEMIN RELATIF EXACT, jamais sur un suffixe : `pipeline/README.md`
    # et `docs/architecture/README.md` sont d'autres fichiers du corpus, et un test qui
    # matcherait sur le basename les imputerait à la slice (faux positif mesuré : le
    # premier jet de ce banc refusait ainsi une traduction correcte).
    fautifs = sorted(noms & set(SLICE))
    assert not fautifs, (
        "fichier(s) de la slice ENCORE nommé(s) par le scan global : %r\n%s"
        % (fautifs, out_of(q)))
    print("witness slice traduite : %d .md suivis, %d violation(s) hors slice, 0 sur la slice"
          % (len(tracked(REPO)), len(noms)))


def test_limite_les_litteraux_geles_restent_verbatim_et_le_gel_n_est_pas_elargi():
    """Scénario limite — les littéraux gelés cités par la slice restent verbatim.

    Deux moitiés, parce que le contournement a deux formes :

    1. le fichier d'exclusion déclare EXACTEMENT les 2 protocoles machine : élargir les
       exemptions pour blanchir du français restant est refusé (le gel ne se lève pas, et
       il ne s'élargit pas) ;
    2. aucune citation DÉCATIE d'un littéral gelé dans la slice : la forme sans accent
       (`Importe depuis` au lieu de `Importé depuis`) est un écart nommé `fichier:NN`.
    """
    _etat_traduit()
    lits = litteraux_geles()

    for prot in PROTOCOLES:
        assert prot in lits, (
            "le protocole gelé %r n'est plus déclaré dans %s : sans lui, une citation "
            "correcte du corpus serait signalée comme du français" % (prot, EXCLUSIONS_REL))
    assert sorted(lits) == sorted(PROTOCOLES), (
        "le fichier d'exclusion déclare %r ; attendu EXACTEMENT %r — élargir les "
        "exemptions est le contournement que ce cas refuse (une traduction ne blanchit "
        "pas le français qui reste)" % (sorted(lits), sorted(PROTOCOLES)))

    ecarts, lignes_vues = [], 0
    for rel in SLICE:
        for num, ligne in lines_of(rel):
            lignes_vues += 1
            for lit in lits:
                if lit in ligne:
                    continue
                if sans_accent(lit) in sans_accent(ligne):
                    ecarts.append("%s:%d — citation décaties de %r : %r"
                                  % (rel, num, lit, ligne.strip()[:90]))
    assert not ecarts, (
        "littéral gelé cité sous une forme DÉCATIE (diacritique perdu) :\n  - "
        + "\n  - ".join(ecarts))
    print("witness littéraux gelés : %r déclaré(s), %d ligne(s) de slice balayée(s)"
          % (lits, lignes_vues))


def test_erreur_un_fichier_oublie_est_nomme_par_le_meme_appel_qui_sort_0_sur_la_slice(tmp_path):
    """Scénario erreur — un des fichiers listés encore entièrement français.

    Le couple est mesuré dans le MÊME appel : la slice traduite sort 0 (moitié positive),
    puis le décor où un fichier de la slice est resté français sort 1 en le nommant
    (moitié négative) — et ne nomme pas les fichiers traduits du même décor.
    """
    _etat_traduit()
    p = scan(list(SLICE), cwd=REPO)
    assert p.returncode == 0, resume(
        p, "moitié positive du couple : la slice traduite doit sortir 0")

    oublie = "CONTRIBUTING.md"
    contenu, nums = corps_francais()
    ligne_faute = nums[1]
    fichiers = {
        "README.md": CORPS_ANGLAIS,
        oublie: contenu,
        "workflows/templates/ticket.md": CORPS_ANGLAIS,
    }
    root = tmp_path / "oublie"
    build_tree(root, fichiers, list(fichiers))
    assert [r for r in tracked(root) if r.endswith(".md")] == sorted(fichiers), (
        "le décor doit indexer exactement les 3 chemins de la slice : %r"
        % tracked(root))

    q = scan(list(SLICE), cwd=root)
    assert q.returncode == 1, resume(
        q, "un fichier de la slice resté entièrement français : exit 1 attendu")
    trouves = reported(out_of(q))
    noms = sorted({rel for rel, _, _ in trouves})
    assert any(rel == oublie and num == ligne_faute for rel, num, _ in trouves), (
        "le fichier oublié doit être nommé À SA LIGNE (%s:%d, MESURÉE dans le décor) ; "
        "violations lues : %r\n%s"
        % (oublie, ligne_faute, [(r, n) for r, n, _ in trouves], out_of(q)))
    assert len(noms) == 1, (
        "seul le fichier oublié doit produire une violation ; nommés : %r" % noms)
    assert "intérêt" in out_of(q) or "dépôt" in out_of(q), (
        "le littéral fautif doit être cité dans le message :\n%s" % out_of(q))

    # discrimination du même appel, fichier par fichier :
    r = scan([oublie], cwd=root)
    assert r.returncode == 1, resume(r, "le seul fichier oublié : exit 1")
    s = scan(["README.md"], cwd=root)
    assert s.returncode == 0, resume(s, "le seul fichier traduit : exit 0")
    assert out_of(s).strip() == "", (
        "le fichier traduit doit être muet :\n%r" % out_of(s))
    print("witness fichier oublié : %s:%d nommé, rc=1 ; README.md seul -> rc=0 muet"
          % (oublie, ligne_faute))


def test_nominal_le_fichier_d_exclusion_reste_le_seul_verificateur_de_la_slice_3():
    """Nominal (non-vacuité du dispositif) — le décor du banc est celui de l'arbre réel.

    Le banc exécute le scan VERSIONNÉ de l'arbre, depuis l'arbre : si le scan ou son
    fichier d'exclusion n'étaient pas ceux du dépôt, ce cas le dirait (chemin, existence,
    index). Il imprime aussi le nombre de lignes de la slice, pour que « muet » ne soit
    jamais un vert sur un corpus vide.
    """
    _require_outils()
    for rel, p in ((SCAN_REL, SCAN), (EXCLUSIONS_REL, EXCLUSIONS)):
        assert p.is_file(), "%s absent : %s" % (rel, p)
        assert rel in subprocess.run(
            ["git", "-C", str(REPO), "ls-files", "--", rel],
            capture_output=True, text=True).stdout, (
            "%s n'est pas SUIVI par l'index : le banc exécuterait un fichier que la "
            "branche ne porte pas" % rel)

    lits = litteraux_geles()
    assert len(lits) == len(PROTOCOLES), (
        "le fichier d'exclusion doit déclarer les 2 protocoles, lu %r" % lits)

    total = sum(len(lines_of(rel)) for rel in SLICE)
    acc = sum(len(accented(rel)) for rel in SLICE)
    assert total > 0, "la slice ne porte aucune ligne : décor vide"
    print("witness dispositif : %s suivi, %d ligne(s) de slice dont %d accentuée(s) "
          "à l'instant de la mesure" % (SCAN_REL, total, acc))
