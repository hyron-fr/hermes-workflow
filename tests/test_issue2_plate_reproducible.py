"""Reproductibilité de la planche comparative de l'issue #2 (slice 1, volet RED).

Sujet : `docs/architecture/context/issue-2-plate.measure.py` (mesure) et
`docs/architecture/context/issue-2-plate.html` (planche).

Contrat d'interface exécuté par ce banc :

    python3 docs/architecture/context/issue-2-plate.measure.py [--root R] [--plate P] [--json]

- exit 0 = l'arbre et le registre de la planche concordent ;
- exit 1 = écart, une ligne par fichier/champ nommant `<chemin>` et les deux nombres ;
- exit 2 = erreur d'usage, ou fichier DÉCLARÉ par la planche absent de l'arbre
  (message contenant `MISSING <chemin>`).

`--root` accepte n'importe quel chemin DANS un checkout : la racine canonique est
résolue par `git rev-parse --show-toplevel` depuis `--root`. C'est ce qui rend le banc
possible : la preuve de reproductibilité se fait sur un CLONE JETABLE, jamais sur l'arbre
en cours d'écriture (une planche réécrite puis mesurée dans le même souffle ne prouve rien).

Le banc ne fait confiance à AUCUN des deux fichiers : il recalcule les totaux depuis
l'arbre avec sa propre définition de « ligne accentuée », puis confronte arbre ↔ registre
↔ prose de la planche.
"""
import hashlib
import html
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
PLATE_REL = "docs/architecture/context/issue-2-plate.html"
MEASURE_REL = "docs/architecture/context/issue-2-plate.measure.py"
PLATE = REPO / PLATE_REL
MEASURE = REPO / MEASURE_REL

# Classe de caractères du contrat : lettres à diacritique + ligatures latines,
# minuscules ET majuscules. Mesurée : reproduit exactement les 1 559 lignes accentuées.
ACCENTS = "àâäçéèêëîïôöùûüÿœæñÀÂÄÇÉÈÊËÎÏÔÖÙÛÜŸŒÆÑ"

# Libellés de gate — décision humaine du 20/09 : les deux jeux de titres sont acceptés
# (linter BILINGUE) ; seuls les 2 PROTOCOLES restent gelés, verbatim.
# Ce que le banc juge n'est pas le choix des titres mais l'ACCORD entre la planche,
# son registre machine et les lecteurs cités — d'où les deux jeux ci-dessous.
TITRES_FR = [
    "Contexte & Objectif",
    "Critères d'acceptation",
    "DoR & DoD",
    "Considérations techniques",
    "Hors-scope",
]
TITRES_EN = [
    "Context & Objective",
    "Acceptance criteria",
    "DoR & DoD",
    "Technical considerations",
    "Out of scope",
]

# Les 2 SEULS littéraux gelés (PROTOCOLES machine) et les lecteurs qui les portent
# VERBATIM. Le banc lit la ligne citée : citer un lecteur qui ne porte pas le
# littéral est un écart, pas une décoration.
PROTOCOLES_GELES = {
    "Importé depuis": [
        ("pipeline/pj_pipeline_deployer.py", 270),
        ("pipeline/gh_kanban_bridge.py", 308),
    ],
    "ROOM:": [
        ("pipeline/pj_room_keeper.py", 76),
    ],
}

# Classifications PÉRIMÉES par la décision du 20/09 : la planche ne doit plus les
# porter. Chaque motif est nommé pour que l'écart soit lisible, pas un booléen.
CLASSEMENTS_PERIMES = [
    (r"FR-only", "classe « FR-only » : l'anglais EST accepté depuis le 20/09"),
    (r"ne peut pas être traduit", "« ne peut pas être traduit » sur un titre de section"),
    (r"rendrait le pipeline entier infranchissable",
     "warnbox : le linter est bilingue, ce n'est plus infranchissable"),
]

# Slice 2 après l'amendement du 20/09, GELÉE depuis la source de vérité du graphe
# (`specs/2/slices.json`, board pj-hermes-workflow : slug + 4 fichiers). Le banc ne lit
# pas ce fichier (il vit hors du dépôt) : il gèle la valeur, comme SLICES ci-dessous.
SLICE2 = {"slug": "i18n-lint-bilingue", "files": 4}

# Ce porte la correction du linter. La planche doit le NOMMER : sinon le lecteur croit
# que le comportement bilingue est déjà dans l'arbre, alors que la copie versionnée
# `pipeline/pj_card_lint.py` refuse encore une carte anglaise (mesuré).
CORRECTEUR_LINTER = "i18n-lint-bilingue"

# Découpage déclaré par la spec (`specs/2/slices.json`) : GELÉ ici, jamais dérivé du
# registre de la planche — sinon le banc validerait le registre par lui-même.
SLICES = {
    3: ["README.md", "CONTRIBUTING.md", "workflows/templates/ticket.md"],
    4: ["agents/pj-master/SOUL.md"],
    5: ["agents/pj-dev/SOUL.md", "agents/pj-doc/SOUL.md", "agents/pj-test/SOUL.md"],
    6: [
        "skills/gh-kanban-bridge/SKILL.md",
        "skills/gh-kanban-bridge/references/SOUL-template.md",
        "skills/gh-kanban-bridge/references/setup.md",
    ],
    7: [
        "skills/hermes-kanban-multiagent-pipelines/SKILL.md",
        "skills/hermes-kanban-multiagent-pipelines/references/activating-kanban.md",
        "skills/kanban-gate/SKILL.md",
    ],
    8: ["skills/hermes-multi-agent-orchestration/SKILL.md"],
    9: [
        "skills/hermes-multi-agent-orchestration/references/hosted-rooms.md",
        "skills/hermes-multi-agent-orchestration/references/kanban-builtins.md",
        "skills/pj-pipeline/references/graph-manifest.md",
        "pipeline/README.md",
    ],
    10: ["skills/pj-pipeline/SKILL.md"],
    11: ["skills/hermes-multi-agent-orchestration/references/issue-pipeline.md"],
}

CORPUS_CIBLE = {"files": 20, "lines": 3052, "accented_lines": 1559}

LEDGER_RE = re.compile(
    r"<script[^>]*id=[\"']plate-ledger[\"'][^>]*>(?P<json>.*?)</script>", re.S | re.I
)


# --------------------------------------------------------------------------- outils


def _run(cmd, cwd=None):
    return subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)


def git(checkout, *args):
    p = _run(["git", "-C", str(checkout), *args])
    assert p.returncode == 0, "git %s a échoué : %s" % (" ".join(args), p.stderr)
    return p.stdout


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def tracked_md(checkout):
    """Enumeration canonique : `git ls-files '*.md'` (jamais os.walk : 65 .md)."""
    p = subprocess.run(
        ["git", "-C", str(checkout), "ls-files", "-z", "*.md"],
        capture_output=True,
    )
    assert p.returncode == 0, p.stderr.decode()
    return sorted(x.decode("utf-8") for x in p.stdout.split(b"\x00") if x)


def stats(checkout, rel):
    """(lignes, lignes accentuées) calculés PAR LE BANC, pas par le sujet."""
    lignes = (Path(checkout) / rel).read_text(encoding="utf-8").splitlines()
    return len(lignes), sum(1 for l in lignes if any(c in ACCENTS for c in l))


def tree_stats(checkout):
    return {rel: stats(checkout, rel) for rel in tracked_md(checkout)}


def measure(root, plate, script=None):
    """Lance le script de mesure contre une racine et une planche données.

    `script` est explicite : pour mesurer un CLONE, on utilise le script DU CLONE — le
    script vérifie sa propre racine et refuserait (à raison) un arbre étranger.
    """
    return _run([
        sys.executable, str(script or MEASURE),
        "--root", str(root), "--plate", str(plate),
    ])


def ledger_of(plate_path):
    txt = Path(plate_path).read_text(encoding="utf-8")
    m = LEDGER_RE.search(txt)
    assert m, (
        "aucun registre machine `<script type=\"application/json\" id=\"plate-ledger\">` "
        "dans %s : la planche ne porte pas les totaux que le script doit reproduire"
        % plate_path
    )
    try:
        return json.loads(m.group("json"))
    except json.JSONDecodeError as exc:
        pytest.fail("registre plate-ledger illisible (%s)" % exc)


def slices_of(ledger):
    """Normalise `slices` (liste d'objets ou mapping k -> objet) en {k: objet}."""
    raw = ledger.get("slices")
    assert raw, "le registre ne porte aucune entrée `slices`"
    out = {}
    if isinstance(raw, dict):
        for k, v in raw.items():
            out[int(k)] = v
    else:
        for v in raw:
            out[int(v["k"])] = v
    return out


def files_of(record):
    """Normalise les fichiers d'une slice : liste de chemins ou mapping chemin -> chiffres.

    Un mapping VIDE est légitime : une slice `kind: create` (la planche, l'outil de scan)
    ne traduit rien, donc elle ne déclare aucun fichier du corpus. C'est aux slices de
    traduction d'être non vides, et c'est `test_nominal_planche_registre_…` qui l'exige en
    comparant à la liste gelée de la spec — pas cette normalisation.
    """
    f = record.get("files")
    assert f is not None, "entrée de slice sans clé `files` (une slice sans fichiers doit porter {})"
    return list(f) if isinstance(f, (list, tuple)) else list(f.keys())


def per_file(record, rel):
    """Chiffres déclarés pour un fichier, si le registre les porte."""
    f = record.get("files")
    if isinstance(f, dict):
        entry = f.get(rel)
        if isinstance(entry, dict):
            return entry
    return None


def plate_totals(txt):
    """Totaux lus dans la PROSE de la planche (jamais dans le registre)."""
    norm = lambda s: int(re.sub(r"[\s\u00a0\u202f\u2009]", "", s))

    def find(pat, label):
        m = re.search(pat, txt, re.S)
        assert m, "la planche ne porte plus %s (motif %r)" % (label, pat)
        return norm(m.group(1))

    corpus = {
        "files": find(r"<b>(20)</b>", "le nombre de fichiers du corpus"),
        "lines": find(r"<b>(3\s*052)</b>", "le total de lignes du corpus"),
        "accented_lines": find(r"<b>(1\s*559)</b>", "le total de lignes accentuées"),
    }
    # les trois mêmes nombres dans l'en-tête de page (dont « 3 052 lignes à traduire »)
    entete = re.search(
        r"\((20)\s*<code>\.md</code>\s*/\s*(3\s*052)\s*[^)]*\)", txt, re.S
    )
    assert entete, "l'en-tête de la planche ne porte plus « (20 .md / 3 052 lignes …) »"
    header = {"files": norm(entete.group(1)), "lines": norm(entete.group(2)),
              "accented_lines": corpus["accented_lines"]}

    par_slice = {}
    for m in re.finditer(
        r"<tr><td class=['\"]k['\"]>(\d+)</td>"
        r".*?<td class=['\"]n['\"]>(\d+)</td>"
        r".*?<td class=['\"]n['\"]>(\d+)</td>"
        r".*?<td class=['\"]n['\"]>(\d+)</td>",
        txt, re.S,
    ):
        k = int(m.group(1))
        # colonnes de la section 4 : fichiers, lignes, dont accentuées
        par_slice[k] = {"files": int(m.group(2)), "lines": int(m.group(3)),
                        "accented_lines": int(m.group(4))}
    return {"corpus": corpus, "entete": header, "slices": par_slice}


# --------------------------------------------------------------------------- clones


@pytest.fixture(scope="module")
def clone_base(tmp_path_factory):
    """Clone jetable au commit qui porte la planche (preuve hors de l'arbre en écriture)."""
    if not PLATE.exists():
        pytest.fail("planche absente : %s" % PLATE)
    if not MEASURE.exists():
        pytest.fail("script de mesure absent : %s" % MEASURE)

    commit = git(REPO, "log", "-1", "--format=%H", "--", PLATE_REL).strip()
    assert commit, (
        "la planche n'est pas VERSIONNÉE : la reproductibilité ne se prouve que sur un "
        "clone, donc `docs/architecture/context/issue-2-plate.html` doit être committée"
    )
    d = tmp_path_factory.mktemp("plate") / "clone"
    p = _run(["git", "clone", "--no-hardlinks", "--quiet", str(REPO), str(d)])
    assert p.returncode == 0, "clone impossible : %s" % p.stderr
    p = _run(["git", "-C", str(d), "checkout", "--detach", commit])
    assert p.returncode == 0, "checkout %s impossible : %s" % (commit, p.stderr)
    return {"dir": d, "commit": commit, "plate": d / PLATE_REL,
            "script": d / MEASURE_REL}


@pytest.fixture
def clone(clone_base, tmp_path):
    """Copie jouable du clone : chaque test mute SA copie, jamais celle du voisin."""
    d = tmp_path / "clone"
    shutil.copytree(clone_base["dir"], d)
    plate = d / PLATE_REL
    ledger_of(plate)  # le clone doit porter la planche avec son registre
    return {"dir": d, "commit": clone_base["commit"], "plate": plate,
            "script": d / MEASURE_REL}


# --------------------------------------------------------------------------- tests


def test_nominal_la_mesure_regenere_les_totaux_de_la_planche():
    """Scénario nominal : exit 0 et les totaux sont ceux inscrits dans la planche."""
    assert MEASURE.exists(), "script de mesure absent : %s" % MEASURE
    p = measure(REPO, PLATE)
    assert p.returncode == 0, (
        "la mesure doit sortir exit 0 sur l'arbre de la branche\n"
        "--- stdout ---\n%s\n--- stderr ---\n%s" % (p.stdout, p.stderr)
    )


def test_nominal_le_registre_de_la_planche_concorde_avec_l_arbre():
    """Le registre machine est confronté à l'arbre, fichier par fichier."""
    ledger = ledger_of(PLATE)
    assert ledger.get("issue") == 2, (
        "le registre doit porter son identité (`issue: 2`) : %r" % ledger.get("issue")
    )
    corpus = ledger.get("corpus") or {}
    for champ, attendu in CORPUS_CIBLE.items():
        assert corpus.get(champ) == attendu, (
            "registre.corpus.%s = %r, attendu %r" % (champ, corpus.get(champ), attendu)
        )

    arbre = tree_stats(REPO)
    mesures = {rel: v for rel, v in arbre.items() if not rel.startswith("docs/")}
    assert len(mesures) == CORPUS_CIBLE["files"], (
        "l'arbre porte %d .md hors vault, attendu %d : %s"
        % (len(mesures), CORPUS_CIBLE["files"], sorted(mesures))
    )
    assert sum(v[0] for v in mesures.values()) == CORPUS_CIBLE["lines"]

    declarees = {}
    for k, rec in slices_of(ledger).items():
        for rel in files_of(rec):
            declarees[rel] = (rec, per_file(rec, rel))

    ecarts = []
    for rel, (lignes, acc) in sorted(mesures.items()):
        if rel not in declarees:
            continue  # non assigné : avertissement, jamais un échec (contrat)
        rec, entry = declarees[rel]
        if entry is not None:
            if entry.get("lines") != lignes:
                ecarts.append("%s: lignes déclarées %r, mesurées %d"
                              % (rel, entry.get("lines"), lignes))
            if entry.get("accented_lines") != acc:
                ecarts.append("%s: lignes accentuées déclarées %r, mesurées %d"
                              % (rel, entry.get("accented_lines"), acc))
    assert not ecarts, "registre de planche en écart avec l'arbre :\n  " + "\n  ".join(ecarts)


def test_nominal_planche_registre_et_arbre_concordent_par_slice():
    """Clôture arbre ↔ registre ↔ prose de la planche, par slice puis corpus."""
    ledger = ledger_of(PLATE)
    pro = plate_totals(PLATE.read_text(encoding="utf-8"))
    recs = slices_of(ledger)

    assert pro["corpus"] == CORPUS_CIBLE, (
        "prose de la planche = %r, attendu %r" % (pro["corpus"], CORPUS_CIBLE)
    )
    assert pro["entete"] == pro["corpus"], (
        "la planche se contredit : en-tête %r vs tableau %r"
        % (pro["entete"], pro["corpus"])
    )

    ecarts = []
    for k, fichier_attendu in sorted(SLICES.items()):
        rec = recs.get(k)
        if rec is None:
            ecarts.append("slice %d absente du registre" % k)
            continue
        if sorted(files_of(rec)) != sorted(fichier_attendu):
            ecarts.append("slice %d : fichiers %r, attendus %r"
                          % (k, sorted(files_of(rec)), sorted(fichier_attendu)))
            continue
        lignes = sum(stats(REPO, f)[0] for f in fichier_attendu)
        acc = sum(stats(REPO, f)[1] for f in fichier_attendu)
        if rec.get("lines") != lignes:
            ecarts.append("slice %d : lignes registre %r, arbre %d"
                          % (k, rec.get("lines"), lignes))
        if rec.get("accented_lines") != acc:
            ecarts.append("slice %d : accentuées registre %r, arbre %d"
                          % (k, rec.get("accented_lines"), acc))
        attendu_prose = pro["slices"].get(k)
        if attendu_prose is None:
            ecarts.append("slice %d absente du tableau d'impact de la planche" % k)
        else:
            if attendu_prose["lines"] != lignes:
                ecarts.append("slice %d : prose planche %d lignes, arbre %d"
                              % (k, attendu_prose["lines"], lignes))
            if attendu_prose["accented_lines"] != acc:
                ecarts.append("slice %d : prose planche %d accentuées, arbre %d"
                              % (k, attendu_prose["accented_lines"], acc))
    assert not ecarts, "planche, registre et arbre divergent :\n  " + "\n  ".join(ecarts)


def test_nominal_la_planche_et_le_script_mesures_sont_ceux_du_commit(clone_base):
    """Le sujet mesuré est bien l'artefact VERSIONNÉ, pas un état de travail local.

    Sans ce cas, le banc pouvait être vert sur une planche réécrite dans le working tree
    et un commit portant autre chose : deux états, deux verts, aucune convergence
    possible. `conv-1` exige des commits sur la branche — donc les deux fichiers que le
    banc mesure doivent être ce que la branche porte réellement.
    """
    ecarts = []
    for rel in (PLATE_REL, MEASURE_REL):
        local = (REPO / rel)
        contenu_commit = subprocess.run(
            ["git", "-C", str(REPO), "show", "%s:%s" % (clone_base["commit"], rel)],
            capture_output=True,
        )
        if contenu_commit.returncode != 0:
            ecarts.append("%s : absent du commit %s" % (rel, clone_base["commit"][:10]))
            continue
        h_local = hashlib.sha256(local.read_bytes()).hexdigest()
        h_commit = hashlib.sha256(contenu_commit.stdout).hexdigest()
        if h_local != h_commit:
            ecarts.append(
                "%s : le fichier du working tree (sha256 %s) diffère de celui du commit "
                "%s (sha256 %s) — commit non à jour"
                % (rel, h_local[:12], clone_base["commit"][:10], h_commit[:12])
            )
    assert not ecarts, (
        "le banc mesure un état qui n'est pas celui de la branche :\n  "
        + "\n  ".join(ecarts)
    )


def test_limite_un_document_change_de_taille_apres_redaction_de_la_planche(clone):
    """Scénario limite : l'écart est nommé fichier par fichier et le test échoue."""
    cible = clone["dir"] / "skills/kanban-gate/SKILL.md"
    avant_l, avant_a = stats(clone["dir"], "skills/kanban-gate/SKILL.md")
    avant = sha256(cible)
    with cible.open("a", encoding="utf-8") as fh:
        fh.write("\nUne ligne accentuée ajoutée par le banc (mutation).\n")
    apres = sha256(cible)
    assert avant != apres, "mutation NON appliquée (témoin de hash) : %s" % avant
    # les deux nombres attendus sont MESURÉS après mutation, jamais recopiés
    apres_l, apres_a = stats(clone["dir"], "skills/kanban-gate/SKILL.md")
    assert (apres_l, apres_a) != (avant_l, avant_a), "la mutation n'a rien changé de mesurable"

    p = measure(clone["dir"], clone["plate"], clone["script"])
    sortie = p.stdout + p.stderr
    assert p.returncode == 1, (
        "un total de planche qui ne correspond plus doit sortir exit 1 (obtenu %d)\n%s"
        % (p.returncode, sortie)
    )
    lignes = [l for l in sortie.splitlines() if "skills/kanban-gate/SKILL.md" in l]
    assert lignes, (
        "l'écart doit être nommé fichier par fichier : aucun message ne cite "
        "skills/kanban-gate/SKILL.md\n%s" % sortie
    )
    assert any(re.search(r"\b%d\b" % avant_l, l) and re.search(r"\b%d\b" % apres_l, l)
               for l in lignes), (
        "la ligne d'écart doit porter les DEUX nombres (attendu %d / mesuré %d) : %r"
        % (avant_l, apres_l, lignes)
    )
    assert any("skills/kanban-gate/SKILL.md" in l and re.search(r"\b%d\b" % apres_a, l)
               for l in lignes), (
        "la ligne d'écart doit aussi porter les lignes accentuées (attendu %d / mesuré %d) : %r"
        % (avant_a, apres_a, lignes)
    )


def test_erreur_un_document_du_corpus_est_absent_de_l_arbre(clone):
    """Scénario erreur : fichier déclaré par la planche, supprimé du worktree."""
    cible = clone["dir"] / "skills/kanban-gate/SKILL.md"
    avant = sha256(cible)
    cible.unlink()
    # témoins d'application de la mutation, imprimés par le banc lui-même
    print("witness: skills/kanban-gate/SKILL.md sha256 %s -> absent=%s"
          % (avant, not cible.exists()))
    assert not cible.exists()

    p = measure(clone["dir"], clone["plate"], clone["script"])
    sortie = p.stdout + p.stderr
    assert p.returncode == 2, (
        "fichier déclaré absent : erreur explicite attendue (exit 2), obtenu %d\n%s"
        % (p.returncode, sortie)
    )
    assert "MISSING" in sortie and "skills/kanban-gate/SKILL.md" in sortie, (
        "le message doit nommer le fichier manquant (MISSING <chemin>) :\n%s" % sortie
    )


def test_limite_racine_dans_un_sous_repertoire_mesure_le_checkout_entier(clone):
    """Une racine qui EST un checkout mesurée à la racine canonique, pas un sous-arbre vide.

    Deux passes sur la MÊME forme d'appel : arbre propre -> exit 0, puis mutation d'un
    fichier du corpus -> exit 1. Le couple est ce qui interdit un vert vide (un scanner
    qui n'énumère que `docs/` sortirait 0 dans les deux cas).
    """
    racine = clone["dir"] / "docs"
    assert racine.is_dir(), "le clone porte docs/ : %s" % racine

    p = measure(racine, clone["plate"], clone["script"])
    assert p.returncode == 0, (
        "--root <sous-répertoire d'un checkout> doit résoudre la racine canonique "
        "(git rev-parse --show-toplevel) et sortir exit 0\n--- stdout ---\n%s\n"
        "--- stderr ---\n%s" % (p.stdout, p.stderr)
    )

    cible = clone["dir"] / "pipeline/README.md"
    avant = sha256(cible)
    with cible.open("a", encoding="utf-8") as fh:
        fh.write("\nUne ligne ajoutée par le banc de test (mutation).\n")
    print("witness: pipeline/README.md sha256 %s -> %s" % (avant, sha256(cible)))
    assert sha256(cible) != avant

    p2 = measure(racine, clone["plate"], clone["script"])
    assert p2.returncode == 1, (
        "même racine, un document du corpus modifié : exit 1 attendu, obtenu %d\n%s"
        % (p2.returncode, p2.stdout + p2.stderr)
    )


# --------------------------------------------------- décision humaine du 20/09
#
# Les 3 cas ci-dessous pincent la règle BILINGUE sur la planche elle-même. Ils sont
# indépendants du script de mesure : c'est la planche qui est jugée, dans le fichier
# versionné que le commit porte. Le gate humain porte sur le RENDU, donc un banc qui
# ne juge que les comptes laisse passer exactement le défaut qui a fait renvoyer la
# planche (un §3 « littéraux gelés » devenu faux).


def _plate_text():
    return PLATE.read_text(encoding="utf-8")


def _prose(plate_txt):
    """Le texte de la planche tel que l'HUMAIN le lit, prêt à être jugé.

    Deux retraits, chacun mesuré sur ce banc :

    1. le bloc `<script id="plate-ledger">` — c'est la zone MACHINE, invisible au PNG
       donc jamais jugée par l'humain. Sans ce retrait, la note d'historique du registre
       (« la §3 classait 5 titres en FR-only ») matche le contrôle qui cherche le
       classement périmé : le contrôle devient rouge sur sa propre justification. Le
       registre est jugé par ses CHAMPS (`slices`, `frozen_literals`), jamais par sa prose.
    2. le dé-encodage des entités : sans lui, `Context &amp; Objective` ne matche pas
       `Context & Objective`, et tout contrôle sur les deux jeux de titres est muet.
    """
    sans_machine = re.sub(r"<script\b.*?</script>", " ", plate_txt, flags=re.S | re.I)
    sans_style = re.sub(r"<style\b.*?</style>", " ", sans_machine, flags=re.S | re.I)
    return html.unescape(re.sub(r"<[^>]+>", " ", sans_style))


def test_nominal_la_planche_porte_la_regle_bilingue_et_ne_classe_plus_les_titres_fr_only():
    """Nominal — la planche dit la règle du 20/09 : deux jeux acceptés, 2 protocols gelés.

    Une planche conforme doit NOMMER les deux jeux de titres (sinon elle ne documente
    pas la règle) ET ne plus porter les classements périmés. Les deux ensemble : une
    planche qui n'écrirait plus rien sur les titres satisferait le seul négatif.
    """
    txt = _plate_text()
    prose = _prose(txt)

    manquants = [t for t in TITRES_EN if t not in prose]
    assert not manquants, (
        "la planche ne nomme pas les titres de section ANGLAIS désormais acceptés "
        "(linter bilingue, décision du 20/09) : %r\n"
        "les deux jeux doivent être cités : FR %r / EN %r"
        % (manquants, TITRES_FR, TITRES_EN)
    )

    perimes = [raison for motif, raison in CLASSEMENTS_PERIMES if re.search(motif, prose, re.I)]
    assert not perimes, (
        "la planche porte encore un classement PÉRIMÉ par la décision du 20/09 :\n  - "
        + "\n  - ".join(perimes)
        + "\nLe linter est bilingue : ces titres SONT traduits par la slice 2."
    )


def test_nominal_les_deux_protocoles_geles_sont_presents_et_leurs_lecteurs_les_portent():
    """Nominal — les 2 SEULS littéraux gelés, et chaque lecteur cité les porte.

    Le banc ouvre le fichier cité à la LIGNE citée : citer un lecteur qui ne porte pas
    le littéral (ou une ligne déplacée) est un écart. Le gel se prouve par qui le lit.
    """
    txt = _plate_text()
    ecarts = []
    for litteral, lecteurs in PROTOCOLES_GELES.items():
        if litteral not in txt:
            ecarts.append("la planche ne porte plus le protocole gelé %r" % litteral)
            continue
        for rel, ligne in lecteurs:
            f = REPO / rel
            if not f.is_file():
                ecarts.append("%s n'existe pas dans l'arbre" % rel)
                continue
            lignes = f.read_text(encoding="utf-8").splitlines()
            if ligne > len(lignes) or litteral not in lignes[ligne - 1]:
                trouve = [i + 1 for i, l in enumerate(lignes) if litteral in l]
                ecarts.append(
                    "%s:%d ne porte pas %r (lignes qui le portent : %r)"
                    % (rel, ligne, litteral, trouve[:5])
                )
    assert not ecarts, (
        "les 2 protocoles verbatim ne sont pas prouvés par leurs lecteurs :\n  - "
        + "\n  - ".join(ecarts)
    )


def test_limite_un_titre_de_section_encore_classe_fr_only_est_nomme(clone):
    """Limite — le linter est bilingue, mais une planche peut encore dire le contraire.

    Mutation sur la COPIE : on réintroduit la phrase périmée et on exige que le banc
    la nomme. Témoin d'application par sha256 dans le même run.
    """
    avant = sha256(clone["plate"])
    txt = clone["plate"].read_text(encoding="utf-8")
    phrase = ("<p class=\"note\">Les 5 titres de section sont FR-only : "
              "le linter ne connaît pas <code>Context &amp; Objective</code>.</p>")
    remplace = txt.replace("</body>", "</body>") if "</body>" in txt else None
    del remplace
    assert "</html>" in txt, "la planche du clone doit être un document HTML complet"
    clone["plate"].write_text(txt.replace("</html>", phrase + "\n</html>"), encoding="utf-8")
    apres = sha256(clone["plate"])
    print("witness: %s sha256 %s -> %s" % (PLATE_REL, avant[:12], apres[:12]))
    assert avant != apres, "mutation NON appliquée (témoin de hash)"

    prose = _prose(clone["plate"].read_text(encoding="utf-8"))
    perimes = [raison for motif, raison in CLASSEMENTS_PERIMES if re.search(motif, prose, re.I)]
    assert perimes, (
        "le banc laisse passer une planche qui reclasse les titres en FR-only : "
        "aucun motif périmé détecté après mutation"
    )


def test_erreur_un_lecteur_cite_par_la_planche_ne_porte_plus_le_protocole(clone):
    """Erreur — la planche cite un lecteur du protocole gelé ; sa copie ne le porte plus.

    Le protocole est un contrat MACHINE : le gel n'est pas une opinion sur le titre mais
    le fait que ce lecteur précis cherche cette chaîne. Mutation sur la copie, témoin
    sha256, puis l'écart doit nommer fichier ET littéral.
    """
    rel = "pipeline/pj_room_keeper.py"
    cible = clone["dir"] / rel
    avant = sha256(cible)
    lignes = cible.read_text(encoding="utf-8").splitlines(keepends=True)
    assert lignes[75].strip().startswith("m = re.search"), (
        "ligne 76 inattendue dans le clone : %r" % lignes[75]
    )
    lignes[75] = lignes[75].replace("ROOM:", "ROOM-ALT:")
    cible.write_text("".join(lignes), encoding="utf-8")
    apres = sha256(cible)
    print("witness: %s sha256 %s -> %s" % (rel, avant[:12], apres[:12]))
    assert avant != apres, "mutation NON appliquée (témoin de hash)"

    txt = clone["plate"].read_text(encoding="utf-8")
    trouves = []
    for litteral, lecteurs in PROTOCOLES_GELES.items():
        if litteral not in txt:
            continue
        for lrel, ligne in lecteurs:
            f = clone["dir"] / lrel
            if not f.is_file():
                continue
            src = f.read_text(encoding="utf-8").splitlines()
            if ligne <= len(src) and litteral not in src[ligne - 1]:
                trouves.append("%s:%d ne porte plus %r" % (lrel, ligne, litteral))
    assert trouves, (
        "un protocole gelé dont le lecteur ne le porte plus doit être NOMMÉ "
        "(fichier + littéral) ; détecté : %r" % trouves
    )
    assert any(rel in t for t in trouves), (
        "l'écart doit nommer le fichier muté %s : %r" % (rel, trouves)
    )


def test_nominal_le_registre_de_la_planche_suit_la_spec_amendee_de_la_slice_2():
    """Nominal — la planche documente le graphe RÉEL : slug et périmètre de la slice 2.

    Le 20/09 la slice 2 a été renommée `lang-lint-outil` → `i18n-lint-bilingue` et son
    périmètre élargi au linter lui-même (4 fichiers). Le registre de la planche est un
    artefact MACHINE : s'il garde l'ancien slug, toute relecture du registre documente
    un graphe qui n'existe plus.
    """
    ledger = ledger_of(PLATE)
    rec = slices_of(ledger).get(2)
    assert rec is not None, "la slice 2 est absente du registre de la planche"
    ecarts = []
    if rec.get("slug") != SLICE2["slug"]:
        ecarts.append("registre slice 2 : slug %r, attendu %r (specs/2/slices.json)"
                      % (rec.get("slug"), SLICE2["slug"]))
    if rec.get("kind") == "create":
        pass  # une slice de création ne traduit rien : son mapping de fichiers est vide
    prose = _prose(_plate_text())
    if SLICE2["slug"] not in prose:
        ecarts.append("la planche ne nomme pas la slice 2 %r dans sa prose"
                      % SLICE2["slug"])
    if CORRECTEUR_LINTER not in prose:
        ecarts.append("la planche ne dit pas QUELLE slice porte la correction du linter : "
                      "%r absent" % CORRECTEUR_LINTER)
    if re.search(r"lang-lint-outil", prose):
        ecarts.append("la planche porte encore l'ancien slug 'lang-lint-outil'")
    assert not ecarts, ("le registre/la prose de la planche ne suivent pas la spec "
                        "amendée du 20/09 :\n  - " + "\n  - ".join(ecarts))


def test_limite_la_planche_n_affirme_pas_que_le_linter_de_l_arbre_est_deja_bilingue(clone):
    """Limite — la correction est un LIVRABLE, pas un état.

    Mesuré : la copie VERSIONNÉE `pipeline/pj_card_lint.py` refuse encore une carte
    anglaise (4 sections « manquantes » sur 5) et son GUARDRAIL ignore `never`/`do not`.
    Une planche qui laisserait croire le contraire induirait un lecteur en erreur — c'est
    exactement le défaut qui a fait renvoyer la version précédente.

    Le cas est MESURÉ, pas rédigé : le banc charge le linter de l'arbre par son chemin
    canonique et exige que le comportement observé soit celui que la planche décrit.
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "lint_arbre", REPO / "pipeline/pj_card_lint.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    carte_en = (
        "## 1. Context & Objective\nGoal.\n\n"
        "## 2. Acceptance criteria\n```gherkin\nFeature: x\n  Scenario: nominal\n"
        "    Given a\n    When b\n    Then c\n  Scenario: edge\n    Given d\n"
        "    When e\n    Then f\n```\n\n"
        "## 3. DoR & DoD\nDoR: nothing. DoD: all.\n\n"
        "## 4. Technical considerations\nNever touch the anchor.\n\n"
        "## 5. Out of scope\nNothing.\n"
    )
    constat = mod.lint({"body": carte_en, "title": "x"})
    print("witness: linter de l'arbre %s -> %r" % (REPO / "pipeline/pj_card_lint.py", constat))
    assert constat, (
        "le linter VERSIONNÉ accepte déjà une carte anglaise : ce cas n'a plus de sujet, "
        "il faut le retirer plutôt que le laisser passer — la planche n'aurait plus à "
        "renvoyer la correction à la slice 2"
    )
    assert any("section" in i for i in constat), (
        "l'attendu est le refus des titres anglais ; obtenu %r" % constat
    )

    prose = _prose(_plate_text())
    assert re.search(r"linter est d[ée]sormais bilingue|BILINGUE|rendu \\*?\\*?bilingue",
                     prose, re.I), (
        "la planche doit dire que la correction EST PORTÉE (par la slice 2), pas que "
        "l'arbre est déjà conforme"
    )
    assert CORRECTEUR_LINTER in prose, (
        "la planche doit NOMMER la slice qui porte la correction du linter"
    )


# --------------------------------------------------- branches du contrat non couvertes
#
# Mesure (couverture des sous-processus, 4 copies du sujet fusionnées) : sans les cas
# ci-dessous le script sortait à 74,87 % de statements et 20 branches non couvertes —
# toutes sur des branches de CONTRAT que le banc n'exerçait pas (repli os.walk, garde
# d'auto-racine, racine introuvable, sortie JSON, planche d'une autre issue, registre
# cassé). Le seuil de 80 % par fichier porte sur ce fichier : ces chemins se testent,
# ils ne se déclarent pas hors sujet.


def test_nominal_la_sortie_json_porte_le_verdict_et_le_code_de_sortie_suit():
    """`--json` : la branche machine du contrat, avec son code de sortie.

    Deux appels sur la MÊME forme : `--json` sur un arbre concordant -> rc 0 et
    `verdict == "concordance"` ; puis sur un clone muté -> rc 1 et `verdict == "ecart"`.
    Un rapport qui ne bascule pas avec l'etat n'est pas un rapport.
    """
    p = _run([sys.executable, str(MEASURE), "--root", str(REPO),
              "--plate", str(PLATE), "--json"])
    assert p.returncode == 0, "mesure --json sur l'arbre : rc=%d\n%s" % (p.returncode, p.stderr)
    rapport = json.loads(p.stdout)
    assert rapport["verdict"] == "concordance", rapport["verdict"]
    assert rapport["declared_md"] == CORPUS_CIBLE["files"]
    assert rapport["unassigned_md"], (
        "le rapport doit lister les .md non déclarés (hors corpus) : %r"
        % rapport["unassigned_md"]
    )
    print("witness --json concordance : declared=%d unassigned=%d"
          % (rapport["declared_md"], len(rapport["unassigned_md"])))


def test_limite_la_sortie_json_suit_l_ecart(clone):
    """Limite — la seconde moitié du contrat `--json` : verdict `ecart` et rc 1."""
    cible = clone["dir"] / "pipeline/README.md"
    avant = sha256(cible)
    with cible.open("a", encoding="utf-8") as fh:
        fh.write("\nLigne ajoutée par le banc (mutation --json).\n")
    print("witness: pipeline/README.md sha256 %s -> %s" % (avant[:12], sha256(cible)[:12]))
    assert sha256(cible) != avant

    p = _run([sys.executable, str(clone["script"]), "--root", str(clone["dir"]),
              "--plate", str(clone["plate"]), "--json"])
    assert p.returncode == 1, "rc attendu 1, obtenu %d\n%s" % (p.returncode, p.stderr)
    rapport = json.loads(p.stdout)
    assert rapport["verdict"] == "ecart", rapport["verdict"]
    assert rapport["ecarts"], "un écart doit être listé, pas seulement compté"
    print("witness --json ecart : %d ecart(s), premier = %s"
          % (len(rapport["ecarts"]), rapport["ecarts"][0]))


def test_erreur_la_planche_d_une_autre_issue_est_refusee():
    """Erreur — le script refuse de mesurer une planche qui n'est pas la sienne."""
    import tempfile
    autre = Path(tempfile.mkdtemp(prefix="conv1_other_")) / "plate.html"
    autre.write_text(MEASURE.read_text(encoding="utf-8").replace(
        "EXPECTED_ISSUE = 2", "EXPECTED_ISSUE = 99"), encoding="utf-8")
    # on falsifie le REGISTRE, pas le script : une planche d'issue 3
    txt = PLATE.read_text(encoding="utf-8")
    autre.write_text(re.sub(r'"issue":\s*2', '"issue": 3', txt, count=1), encoding="utf-8")
    p = _run([sys.executable, str(MEASURE), "--plate", str(autre)])
    assert p.returncode == 2, (
        "une planche d'une autre issue doit sortir 2 (erreur d'usage), obtenu %d\n%s"
        % (p.returncode, p.stdout + p.stderr)
    )
    assert "autre issue" in (p.stdout + p.stderr), p.stdout + p.stderr


def test_erreur_un_registre_illisible_ou_absent_est_refuse():
    """Erreur — deux degradations du registre, memes garanties : rc 2 nomme la cause."""
    import tempfile
    d = Path(tempfile.mkdtemp(prefix="conv1_led_"))
    txt = PLATE.read_text(encoding="utf-8")

    sans = d / "sans.html"
    sans.write_text(re.sub(r'<script type="application/json" id="plate-ledger">.*?</script>',
                           "", txt, flags=re.S), encoding="utf-8")
    p1 = _run([sys.executable, str(MEASURE), "--plate", str(sans)])
    assert p1.returncode == 2, "registre absent : rc=2 attendu, obtenu %d" % p1.returncode
    assert "plate-ledger" in (p1.stdout + p1.stderr)

    casse = d / "casse.html"
    casse.write_text(re.sub(r'(id="plate-ledger">\s*)\{',
                            r'\1{ "oops":', txt, count=1), encoding="utf-8")
    p2 = _run([sys.executable, str(MEASURE), "--plate", str(casse)])
    assert p2.returncode == 2, "registre illisible : rc=2 attendu, obtenu %d" % p2.returncode
    assert "illisible" in (p2.stdout + p2.stderr), p2.stdout + p2.stderr

    absente = d / "nexistepas.html"
    p3 = _run([sys.executable, str(MEASURE), "--plate", str(absente)])
    assert p3.returncode == 2, "planche introuvable : rc=2 attendu, obtenu %d" % p3.returncode
    assert "introuvable" in (p3.stdout + p3.stderr)
    print("witness registre : absente=%d absent=%d casse=%d (%s)"
          % (p3.returncode, p1.returncode, p2.returncode, "tous rc=2"))


def test_limite_le_repli_os_walk_mesure_un_arbre_sans_git(clone):
    """Limite — le repli `os.walk` pruné, sur un arbre RECOPIÉ sans `.git`.

    La branche est le repli : `git ls-files` indisponible. On la force en retirant
    `.git` de la copie (pas en la simulant) et on exige que le script le DISE, puis que
    la mesure reste celle de l'arbre — un repli qui inventerait un total serait pire
    que pas de repli.
    """
    recopie = clone["dir"].parent / "sans_git"
    shutil.copytree(clone["dir"], recopie, ignore=shutil.ignore_patterns(".git"))
    assert not (recopie / ".git").exists(), "la copie doit etre SANS .git"

    script = recopie / MEASURE_REL
    plate = recopie / PLATE_REL
    p = _run([sys.executable, str(script), "--root", str(recopie), "--plate", str(plate)])
    sortie = p.stdout + p.stderr
    assert p.returncode == 0, (
        "sur un arbre recopie sans .git, le repli doit sortir 0 : rc=%d\n%s"
        % (p.returncode, sortie)
    )
    assert "os.walk" in sortie, (
        "le repli doit etre IMPRIME (sinon on ne sait pas quelle enumeration a parle) :\n%s"
        % sortie
    )
    assert "concordance" in sortie, sortie
    print("witness repli : %s" % [l for l in sortie.splitlines() if "numération" in l])


def test_erreur_une_racine_introuvable_ou_un_arbre_etranger_sont_refuses():
    """Erreur — les deux gardes de racine : chemin absent, et arbre qui n'est pas le sien.

    `--root` sur un checkout ETRANGER est le cas qui protege la preuve : sans lui, un
    vert peut venir de n'importe quel arbre.
    """
    p1 = _run([sys.executable, str(MEASURE), "--root", "/tmp/conv1-racine-absente-xyz"])
    assert p1.returncode == 2, "racine introuvable : rc=2 attendu, obtenu %d" % p1.returncode
    assert "introuvable" in (p1.stdout + p1.stderr)

    anchor = Path("/home/elix/pj-repos/hermes-workflow")
    if anchor.is_dir() and (anchor / ".git").exists():
        p2 = _run([sys.executable, str(MEASURE), "--root", str(anchor)])
        assert p2.returncode == 2, (
            "arbre etranger (l'anchor) : rc=2 attendu, obtenu %d\n%s"
            % (p2.returncode, p2.stdout + p2.stderr)
        )
        assert "étranger" in (p2.stdout + p2.stderr), p2.stdout + p2.stderr
        print("witness arbre etranger : rc=%d %r" % (p2.returncode,
                                                     (p2.stdout + p2.stderr).strip()[:80]))

    p3 = _run([sys.executable, str(MEASURE), "--nope"])
    assert p3.returncode == 2, "usage invalide : rc=2 attendu, obtenu %d" % p3.returncode
    print("witness usage invalide : rc=%d" % p3.returncode)


def test_limite_un_md_non_declare_est_un_avertissement_pas_un_echec(clone):
    """Limite — l'assignation du corpus est la propriété de la PLAN CHE, pas du scan.

    Un `.md` de plus dans l'arbre (hors corpus déclaré) doit sortir 0 AVEC un
    avertissement qui le nomme. Le contraire ferait échouer la mesure sur un fichier que
    la planche n'a jamais prétendu couvrir.
    """
    nouveau = clone["dir"] / "docs/architecture/context/hors-corpus-sonde.md"
    nouveau.write_text("# hors corpus\n\nUne ligne.\n", encoding="utf-8")
    # le sujet enumere `git ls-files '*.md'` — un fichier NON SUIVI n'existe pas pour
    # lui. Ma premiere version de ce cas creait un fichier non suivi et exigeait
    # l'avertissement : le banc etait faux, le sujet avait raison (mesure).
    git(clone["dir"], "add", "docs/architecture/context/hors-corpus-sonde.md")
    assert "hors-corpus-sonde.md" in git(clone["dir"], "ls-files", "*.md"), (
        "la sonde doit etre SUIVIE pour que l'enumeration canonique la voie"
    )
    print("witness: %s cree puis suivi (git add)" % nouveau.name)

    p = _run([sys.executable, str(clone["script"]), "--root", str(clone["dir"]),
              "--plate", str(clone["plate"])])
    sortie = p.stdout + p.stderr
    assert p.returncode == 0, (
        "un .md non declare ne doit PAS faire echouer la mesure : rc=%d\n%s"
        % (p.returncode, sortie)
    )
    assert "avertissement" in sortie and "hors-corpus-sonde.md" in sortie, (
        "l'avertissement doit NOMMER le fichier non assigne :\n%s" % sortie
    )
    print("witness avertissement : %s"
          % [l for l in sortie.splitlines() if "avertissement" in l])


def test_limite_le_registre_peut_declarer_ses_fichiers_en_LISTE(clone):
    """Limite — le registre accepte `files` en LISTE, pas seulement en mapping.

    `declared()` a deux branches (mapping chemin->chiffres, et liste de chemins sans
    chiffres). Un registre qui déclare ses fichiers en liste doit être mesuré de la même
    façon, sans les totaux par fichier. C'est une forme du contrat que le registre du
    dépôt n'utilise pas : elle se teste sur une COPIE.
    """
    import tempfile
    txt = clone["plate"].read_text(encoding="utf-8")
    # slice 3 (translate) : passer le mapping en liste de chemins
    variante = re.sub(
        r'"files": \{\s*"README\.md": \{[^}]*\},\s*"CONTRIBUTING\.md": \{[^}]*\},'
        r'\s*"workflows/templates/ticket\.md": \{[^}]*\}\s*\}',
        '"files": ["README.md", "CONTRIBUTING.md", "workflows/templates/ticket.md"]',
        txt, count=1, flags=re.S)
    assert variante != txt, "la substitution du registre a echoue (motif non trouve)"
    plate = Path(tempfile.mkdtemp(prefix="conv1_list_")) / "plate.html"
    plate.write_text(variante, encoding="utf-8")
    print("witness: registre de la slice 3 passe en LISTE")

    p = _run([sys.executable, str(clone["script"]), "--root", str(clone["dir"]),
              "--plate", str(plate)])
    sortie = p.stdout + p.stderr
    assert p.returncode == 0, (
        "`files` en LISTE doit etre mesure sans ecart : rc=%d\n%s" % (p.returncode, sortie)
    )
    assert "concordance" in sortie, sortie
    print("witness: %s" % [l for l in sortie.splitlines() if "concordance" in l])


def test_erreur_sans_git_sur_le_PATH_le_script_le_DIT_au_lieu_d_inventer(clone):
    """Erreur — `git` absent du PATH : le repli doit s'annoncer, jamais mentir.

    Le repli `os.walk` est le filet du contrat. Deux exigences en une : il doit sortir un
    resultat (pas planter sur `FileNotFoundError`) ET dire quelle enumeration a parle.
    Un repli silencieux rendrait deux mesures indistinguables.
    """
    import tempfile
    recopie = Path(tempfile.mkdtemp(prefix="conv1_nogit_")) / "arbre"
    shutil.copytree(clone["dir"], recopie)
    script = recopie / MEASURE_REL
    plate = recopie / PLATE_REL

    # PATH sans `git`, mais l'environnement est HERITÉ (COVERAGE_PROCESS_START compris) :
    # construit a neuf, ce sous-processus ne publiait aucune donnee de couverture et
    # faisait passer pour non couverte la seule branche qu'il exerce (`except OSError`
    # de `sh()`). Un cas qui cache sa propre couverture est un trou de MESURE.
    env = dict(os.environ)
    env["PATH"] = "/nonexistent"
    p = subprocess.run([sys.executable, str(script), "--root", str(recopie),
                        "--plate", str(plate)],
                       capture_output=True, text=True, env=env)
    sortie = p.stdout + p.stderr
    assert "Traceback" not in sortie, (
        "sans `git` sur le PATH le script ne doit pas planter :\n%s" % sortie
    )
    assert p.returncode in (0, 1), (
        "sans git, le repli doit produire une MESURE (0 ou 1), obtenu %d\n%s"
        % (p.returncode, sortie)
    )
    assert "os.walk" in sortie, (
        "le repli doit s'ANNONCER dans sa sortie :\n%s" % sortie
    )
    print("witness PATH sans git : rc=%d · %s"
          % (p.returncode, [l for l in sortie.splitlines() if "numération" in l]))


def test_limite_un_arbre_qui_ne_porte_QUE_le_corpus_ne_produit_aucun_avertissement(clone):
    """Limite — la branche inverse de l'avertissement : `unassigned` VIDE.

    Le sujet a un `if unassigned:` (avertissement nommant les .md hors corpus). Exercer
    seulement la branche vraie laissait la fausse non couverte. On retire du clone les
    3 notes que la planche ne déclare pas : l'arbre ne porte alors QUE le corpus, la
    liste `non déclarés` est vide, et la sortie ne doit porter AUCUN avertissement —
    sans pour autant cesser d'être une concordance.
    """
    hors_corpus = ["docs/architecture/README.md", "docs/functional/README.md",
                   "docs/architecture/context/issue-2.md"]
    for rel in hors_corpus:
        cible = clone["dir"] / rel
        assert cible.is_file(), "le clone doit porter %s" % rel
        # `git rm --cached` : le fichier disparait de l'INDEX *et* du disque. Un simple
        # `unlink()` le laisse SUIVI — `git ls-files` le rend toujours, donc l'arbre
        # n'est pas « le corpus seul » et l'enumeration canonique le voit encore.
        git(clone["dir"], "rm", "--cached", "--quiet", rel)
        cible.unlink()
    print("witness: %d .md hors corpus RETIRES DE L'INDEX -> arbre == corpus declare"
          % len(hors_corpus))
    assert len(git(clone["dir"], "ls-files", "*.md").splitlines()) == CORPUS_CIBLE["files"], (
        "apres retrait, l'arbre doit porter exactement le corpus declare"
    )

    p = _run([sys.executable, str(clone["script"]), "--root", str(clone["dir"]),
              "--plate", str(clone["plate"])])
    sortie = p.stdout + p.stderr
    assert p.returncode == 0, "arbre == corpus declare : rc=0 attendu, obtenu %d\n%s" % (
        p.returncode, sortie)
    assert "avertissement" not in sortie, (
        "sans fichier non déclaré, la sortie ne doit porter AUCUN avertissement :\n%s"
        % sortie
    )
    assert "concordance" in sortie, sortie
    assert "%d .md suivis, %d déclarés" % (CORPUS_CIBLE["files"],
                                           CORPUS_CIBLE["files"]) in sortie, sortie
    print("witness sans avertissement : %s"
          % [l for l in sortie.splitlines() if "numération" in l])
