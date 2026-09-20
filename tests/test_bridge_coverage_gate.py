"""
Tests du gate de couverture du pont GitHub (renfo 1 + slice 2 de l'issue #5).

Règle : une issue qui recouvre du travail DÉJÀ en vol (PR ouverte, issue ouverte
avec graphe) ne doit PAS être importée en nouveau graphe — sinon 3 issues pour un
changement. La décision reste humaine, mais elle est POSÉE au lieu d'être contournée.

Slice 2 (#5) ajoute trois choses, et chaque section du fichier porte son défaut :
  · l'EXEMPTION du parent : `overlaps = (refs | titres) - {parent} - {self}` ;
  · l'ancre de `issues_with_graph()` : plus d'issue fantôme (#7 citée par un corps) ;
  · la TRAPPE corrigée : l'échappatoire proposée doit être RÉELLE.
"""
import contextlib
import importlib.util
import io
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]

# Quelle copie ce run valide-t-il ? Mesuré : ce fichier existe en deux exemplaires
# homonymes (hermes-workflow = copie versionnée, hermes-experiment = copie que les
# wrappers EXÉCUTENT) qui ne diffèrent que par cette ligne. Par défaut on juge la
# copie versionnée ; `PJ_BRIDGE_COPY=<chemin>` fait juger la copie runtime.
# « tests verts » ≠ « pont réparé » sans les DEUX runs.
PATH = str(Path(os.environ["PJ_BRIDGE_COPY"]) if os.environ.get("PJ_BRIDGE_COPY")
            else REPO / "bridge" / "gh_kanban_bridge.py")


@pytest.fixture(scope="module")
def br():
    os.environ.setdefault("GH_REPO", "hyron-fr/dino-game")
    os.environ.setdefault("KANBAN_BOARD", "pj-dino-game")
    spec = importlib.util.spec_from_file_location("br", PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# --------------------------------------------------------------- références ---

def test_refs_extracts_hash_numbers(br):
    assert br.issue_refs("corrige #4 et aussi #9.") == {4, 9}


def test_refs_ignores_bare_numbers(br):
    """« 600 » ou « x=848 » ne sont pas des références d'issue."""
    assert br.issue_refs("Q2 600, sprite x=848 y=2, 26x50") == set()


def test_refs_ignores_url_refs(br):
    """Une URL d'import complète n'est pas une référence de chevauchement."""
    assert br.issue_refs("Importé depuis https://github.com/hyron-fr/dino-game/issues/4") == set()


def test_refs_handles_empty(br):
    assert br.issue_refs("") == set()
    assert br.issue_refs(None) == set()


# ------------------------------------------------------------------ titres ----

def test_title_tokens_normalizes(br):
    t = br.title_tokens("Refonte graphique des acteurs (dino, cactus, ptérosaure)")
    assert "graphique" in t and "acteurs" in t
    assert "refonte" in t
    # les mots vides et la ponctuation disparaissent
    assert "des" not in t and "(" not in " ".join(t)


def test_title_overlap_detects_related_issues(br):
    """Le cas VÉCU : #9 « Refonte graphique des acteurs » vs #4 « Améliorer l'UX »
    ne se recouvrent PAS par le titre — c'est la référence #4 dans le body qui
    révèle le chevauchement."""
    a = br.title_tokens("Refonte graphique des acteurs (dino, cactus, ptérosaure)")
    b = br.title_tokens("Améliorer l'UX")
    assert br.title_overlap(a, b) < 0.34


def test_title_overlap_same_subject(br):
    a = br.title_tokens("Refonte graphique des acteurs dino")
    b = br.title_tokens("Refonte graphique des acteurs (dino, cactus)")
    assert br.title_overlap(a, b) >= 0.5


# ------------------------------------------------------------------- gate -----

def test_gate_blocks_issue_referencing_open_pr(br):
    """Une issue qui cite une issue déjà en vol est SUSPECTE (décision humaine)."""
    issue = {"number": 9, "title": "Refonte graphique", "body": "suite de #4"}
    ctx = {"open_issues": {4}, "open_pr_issues": {4}, "graph_issues": {4}}
    v = br.coverage_verdict(issue, ctx)
    assert v["blocked"] is True
    assert 4 in v["overlaps"]


def test_gate_blocks_issue_covered_by_open_pr_without_ref(br):
    """Pas de référence explicite, mais recouvrement de titre → suspect aussi."""
    issue = {"number": 11, "title": "Refonte graphique des acteurs dino",
             "body": "silhouettes à revoir"}
    ctx = {"open_issues": {4},
           "open_pr_issues": {4},
           "graph_issues": {4},
           "titles": {4: "Refonte graphique des acteurs (dino, cactus)"}}
    v = br.coverage_verdict(issue, ctx)
    assert v["blocked"] is True
    assert 4 in v["overlaps"]


def test_gate_allows_genuinely_new_issue(br):
    """Une issue réellement neuve passe : le gate n'est pas un blocage systématique."""
    issue = {"number": 12, "title": "Ajouter un compteur de parties",
             "body": "nouvelle fonctionnalité de statistiques"}
    ctx = {"open_issues": {4}, "open_pr_issues": {4}, "graph_issues": {4},
           "titles": {4: "Refonte graphique des acteurs"}}
    v = br.coverage_verdict(issue, ctx)
    assert v["blocked"] is False
    assert v["overlaps"] == []


def test_gate_does_not_block_on_itself(br):
    """Une issue ne se référence pas elle-même (réédition, note de suivi)."""
    issue = {"number": 4, "title": "Améliorer l'UX", "body": "voir #4"}
    ctx = {"open_issues": {4}, "open_pr_issues": {4}, "graph_issues": {4},
           "titles": {4: "Améliorer l'UX"}}
    v = br.coverage_verdict(issue, ctx)
    assert v["blocked"] is False


def test_gate_reports_why(br):
    """Le verdict doit être explicable à l'humain (c'est lui qui décide)."""
    issue = {"number": 9, "title": "Refonte graphique", "body": "suite de #4"}
    ctx = {"open_issues": {4}, "open_pr_issues": {4}, "graph_issues": {4}}
    v = br.coverage_verdict(issue, ctx)
    assert v["reason"]
    assert "#4" in v["reason"]


# ------------------------------------------------------- lien PR -> issue ------

def test_closes_line_format(br):
    """t6 doit écrire une ligne de fermeture NATIVE — sinon GitHub ne lie pas la PR."""
    assert br.closes_line(7) == "Closes #7"
    assert "7" in br.closes_line(7)


# =========================================================================
# slice 2 (#5) — EXEMPTION DU PARENT, ANCRE DES GRAPHES, TRAPPE HONNÊTE
#
# Trois défauts mesurés, un seul fichier :
#  1. l'enfant de décision cite son parent PAR CONSTRUCTION : sans exemption il
#     est refusé à l'import, donc la 2ᵉ itération de la boucle est impossible ;
#     la règle est une SOUSTRACTION (parent ET soi), jamais « parent ⇒ rien » ;
#  2. `issues_with_graph()` ramassait TOUS les `#N` des corps de cartes : une
#     carte citant « la PR #7 de dino-game » faisait entrer une issue FANTÔME ;
#  3. le commentaire du gate proposait « poser le label `kanban` » alors que
#     `pull()` fait `continue` dessus : l'échappatoire proposée EMPÊCHAIT l'import.
# =========================================================================

# ------------------------------------------------------- harnais hors ligne ----
# Le banc ne doit toucher ni GitHub ni un board réel : les deux binaires du pont
# sont remplacés par de faux exécutables qui journalisent leurs arguments et
# rendent un état JSON. Rejouable hors ligne, déterministe, aucune horloge.

FAKE_REPO = "hyron-fr/fake-pont"

_GH_FAKE = '''#!__PY__
import json, os, sys
here = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(here, "gh_calls.log"), "a") as fh:
    fh.write(json.dumps(sys.argv[1:]) + "\\n")
state = json.load(open(os.path.join(here, "gh_state.json")))
argv = sys.argv[1:]
def emit(x):
    print(json.dumps(x, ensure_ascii=False))
    sys.exit(0)
if argv[:2] == ["issue", "list"]:
    emit(state.get("issues", []))
if argv[:2] == ["pr", "list"]:
    emit(state.get("prs", []))
if argv[:2] == ["issue", "view"]:
    emit({"comments": (state.get("comments") or {}).get(argv[2], [])})
emit({})
'''

_HERMES_FAKE = '''#!__PY__
import json, os, sys
here = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(here, "kanban_calls.log"), "a") as fh:
    fh.write(json.dumps(sys.argv[1:]) + "\\n")
state = json.load(open(os.path.join(here, "kanban_state.json")))
argv = sys.argv[1:]
if "list" in argv and "--json" in argv:
    print(state.get("tasks_raw", json.dumps(state.get("tasks", []), ensure_ascii=False)))
    sys.exit(0)
if "create" in argv:
    print(json.dumps({"id": state.get("next_task_id", "t_fake")}, ensure_ascii=False))
    sys.exit(0)
print("")
'''

VARIABLES_DU_PONT = ("DRY_RUN", "PJ_IMPORT_TRIAGE", "BRIDGE_VERBOSE")


def _faux_binaires(tmp_path):
    d = Path(tmp_path)
    for nom, gabarit in (("gh", _GH_FAKE), ("hermes", _HERMES_FAKE)):
        p = d / nom
        p.write_text(gabarit.replace("__PY__", sys.executable))
        p.chmod(0o755)
    return d


@pytest.fixture
def pont(tmp_path, monkeypatch):
    """Le pont chargé avec de FAUX binaires `gh` et `hermes` (jamais les vrais)."""
    d = _faux_binaires(tmp_path)
    monkeypatch.setenv("GH_REPO", FAKE_REPO)
    monkeypatch.setenv("KANBAN_BOARD", "pj-fake-pont")
    for var in VARIABLES_DU_PONT:
        monkeypatch.delenv(var, raising=False)
    spec = importlib.util.spec_from_file_location("br_slice2", PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.GH_BIN = str(d / "gh")
    mod.HERMES_BIN = str(d / "hermes")
    return mod, d


def _tick(pont, gh_state, kanban_state, action="pull"):
    """Un tick du pont sur un état donné ; rend (appels gh, appels kanban)."""
    mod, d = pont
    (d / "gh_state.json").write_text(json.dumps(gh_state, ensure_ascii=False))
    (d / "kanban_state.json").write_text(json.dumps(kanban_state, ensure_ascii=False))
    for f in ("gh_calls.log", "kanban_calls.log"):
        (d / f).write_text("")
    if action == "pull":
        mod.pull()
    elif action == "new":
        mod.cmd_new()
    gh_calls = [json.loads(l) for l in (d / "gh_calls.log").read_text().splitlines() if l]
    kb_calls = [json.loads(l) for l in (d / "kanban_calls.log").read_text().splitlines() if l]
    return gh_calls, kb_calls


def _issue(numero, titre, corps="", labels=(), parent=None):
    """Une issue telle que `gh issue list` la rend (`parent` est un DICT)."""
    i = {"number": numero, "title": titre, "body": corps,
         "url": f"https://github.com/{FAKE_REPO}/issues/{numero}",
         "labels": [{"name": l} for l in labels],
         "createdAt": "2020-01-01T00:00:00Z"}       # toujours plus vieille que la grâce
    if parent is not None:
        i["parent"] = {"number": parent}
    return i


def _carte_racine(numero, task_id="t_racine", titre=None):
    """La carte racine d'un graphe : elle porte la ligne écrite par `pull()`."""
    return {"id": task_id, "title": titre or f"Racine #{numero}", "status": "todo",
            "body": f"corps de l'issue\n\n—\nImporté depuis "
                    f"https://github.com/{FAKE_REPO}/issues/{numero}"}


def _creees(kb_calls):
    """Titres des cartes que le pont a réellement créées sur ce tick."""
    return [c[4] for c in kb_calls if len(c) > 4 and c[3] == "create"]


GATE_MARKER = "<!-- pj-coverage-gate -->"


def _motifs_gate(gh_calls):
    """Corps des SEULS commentaires du gate de couverture (marqueur), pas les
    avis d'import — sinon « le gate a bloqué » ne serait pas mesurable."""
    return [c[6] for c in gh_calls
            if c[:2] == ["issue", "comment"] and len(c) > 6 and GATE_MARKER in c[6]]


def _lectures(gh_calls):
    """Appels de LECTURE à `gh` (ceux qui coûtent un aller-retour réseau)."""
    return [c[:2] for c in gh_calls if c[0] in ("issue", "pr", "label")]


# ------------------------------------------ A. exemption du parent (unitaire) --

def test_parent_en_vol_ne_compte_plus_comme_recouvrement(br):
    """NOMINAL — la raison d'être de la slice : un enfant cite son parent.

    Sans exemption, l'issue enfant de décision (qui cite `#5` par construction)
    est refusée à l'import : la 2ᵉ itération de la boucle devient impossible.
    """
    enfant = {"number": 40, "parent": {"number": 5}, "title": "Décision — carte bloquée",
              "body": "Sous-issue de #5.\n\nPoint à statuer sur la carte `t_aaa`."}
    assert 5 in br.issue_refs(enfant["body"])          # la prémisse
    ctx = {"open_pr_issues": set(), "graph_issues": {5}, "titles": {},
           "parents": {40: 5}}
    v = br.coverage_verdict(enfant, ctx)
    assert v["blocked"] is False
    assert v["overlaps"] == []


def test_parent_soustrait_mais_vrai_chevauchement_conserve(br):
    """LIMITE — l'exemption du parent ne doit pas blanchir un vrai recouvrement.

    Enfant citant `#5` (parent) ET `#7` (travail en vol non parent) ⇒ bloquée sur
    `[7]` SEULEMENT. Une règle « parent ⇒ non bloqué » laisserait passer ce doublon.
    """
    enfant = {"number": 40, "parent": {"number": 5}, "title": "Décision",
              "body": "Sous-issue de #5, qui dépend de #7."}
    ctx = {"open_pr_issues": set(), "graph_issues": {5, 7}, "titles": {},
           "parents": {40: 5}}
    v = br.coverage_verdict(enfant, ctx)
    assert v["overlaps"] == [7]
    assert v["blocked"] is True
    assert 5 not in v["overlaps"]


def test_exemption_appliquee_avant_la_passe_de_titre(br):
    """LIMITE — l'exemption vaut AUSSI pour le recouvrement de titre.

    Le titre de l'enfant ressemble à celui du parent par construction ; si la
    soustraction n'est faite qu'après la passe de titre, le parent revient par la
    porte de derrière (mesuré : Jaccard 0,8 ≥ 0,34).
    """
    enfant = {"number": 40, "parent": {"number": 5},
              "title": "Refonte graphique des acteurs dino", "body": "Sous-issue de #5."}
    ctx = {"open_pr_issues": set(), "graph_issues": {5},
           "titles": {5: "Refonte graphique des acteurs (dino, cactus)"},
           "parents": {40: 5}}
    assert br.title_overlap(br.title_tokens(enfant["title"]),
                            br.title_tokens(ctx["titles"][5])) >= 0.34   # la prémisse
    v = br.coverage_verdict(enfant, ctx)
    assert v["blocked"] is False, "le parent est revenu par la passe de titre"
    assert v["overlaps"] == []


def test_repli_sur_le_parent_rendu_par_gh(br):
    """ERREUR — `parent` est un DICT `{"number": N}` côté `gh`, pas un entier.

    Lu naïvement, l'exemption est SILENCIEUSEMENT perdue : ce cas mesure le repli
    sur `issue['parent']` quand `ctx['parents']` n'est pas fourni.
    """
    enfant = {"number": 40, "parent": {"number": 5}, "title": "Décision",
              "body": "Sous-issue de #5."}
    ctx = {"open_pr_issues": set(), "graph_issues": {5}, "titles": {}}
    v = br.coverage_verdict(enfant, ctx)
    assert v["blocked"] is False, "un parent en dict a été lu comme absent"


def test_ctx_parents_en_dict_ne_perd_pas_l_exemption(br):
    """ERREUR — la carte `ctx['parents']` peut elle-même porter un dict (forme `gh`)."""
    enfant = {"number": 40, "parent": {"number": 5}, "title": "Décision",
              "body": "Sous-issue de #5."}
    ctx = {"open_pr_issues": set(), "graph_issues": {5}, "titles": {},
           "parents": {40: {"number": 5}}}
    assert br.coverage_verdict(enfant, ctx)["blocked"] is False


def test_parent_rendu_comme_entier_nu_reste_lu(br):
    """ERREUR — certaines sources rendent `parent` comme un entier nu.

    La lecture doit accepter les DEUX formes (dict `gh` et entier) : une lecture
    qui ne gère que le dict perdrait l'exemption sur un appelant qui normalise.
    """
    dict_ = {"number": 40, "parent": {"number": 5}, "title": "Décision",
             "body": "Sous-issue de #5."}
    entier = {"number": 40, "parent": 5, "title": "Décision", "body": "Sous-issue de #5."}
    ctx = {"open_pr_issues": set(), "graph_issues": {5}, "titles": {}}
    assert br.coverage_verdict(dict_, ctx)["blocked"] is False
    assert br.coverage_verdict(entier, ctx)["blocked"] is False
    ctx_table = {"open_pr_issues": set(), "graph_issues": {5}, "titles": {},
                 "parents": {40: 5}}
    assert br.coverage_verdict(entier, ctx_table)["blocked"] is False


def test_parent_absent_ne_soustrait_rien(br):
    """ERREUR — `parent: None` (issue racine) : aucune exemption, verdict inchangé."""
    racine = {"number": 9, "parent": None, "title": "Racine", "body": "corrige #5"}
    ctx = {"open_pr_issues": set(), "graph_issues": {5}, "titles": {}, "parents": {9: None}}
    v = br.coverage_verdict(racine, ctx)
    assert v["blocked"] is True and v["overlaps"] == [5]


def test_la_table_des_parents_lit_les_trois_formes(br):
    """ERREUR — la table `parents` se construit depuis la MÊME liste d'issues.

    Trois formes rencontrées : `{"number": N}` (sortie `gh`), entier nu (appelant
    qui normalise), et absence (`parent: None`). Une seule forme gérée = exemption
    perdue en silence sur les autres.
    """
    issues = [
        {"number": 40, "parent": {"number": 5}},
        {"number": 41, "parent": 5},
        {"number": 42, "parent": None},
        {"number": 43},
    ]
    assert br.issue_parents(issues) == {40: 5, 41: 5, 42: None, 43: None}


def test_ctx_sans_cle_parents_reste_compatible(br):
    """LIMITE — rétrocompatibilité ET anti-« exemption universelle ».

    Un appelant ancien (ctx sans la clé) et une issue sans parent doivent garder
    le verdict d'aujourd'hui : si l'exemption devenait inconditionnelle, ce cas
    passerait au vert en blanchissant un vrai doublon.
    """
    ctx = {"open_pr_issues": set(), "graph_issues": {5}, "titles": {}}
    racine = {"number": 9, "parent": None, "title": "Racine", "body": "corrige #5"}
    assert br.coverage_verdict(racine, ctx)["blocked"] is True


# ------------------------------------------- B. ancre de issues_with_graph ----

_BOARD_REEL = [
    _carte_racine(1, "t_r1"),
    _carte_racine(2, "t_r2", titre="Rewrite in english"),
    _carte_racine(4, "t_r4", titre="Versionner pj_escalate.py"),
    _carte_racine(5, "t_r5", titre="Interface de décision humaine"),
    # les cartes de graphe : titre `t<n> … #<n>` (ancre de titre, pas de ligne d'import)
    {"id": "t1", "title": "t6 submitted #1", "status": "todo", "body": "producteur #1"},
    {"id": "t2", "title": "t6 submitted #2", "status": "todo",
     "body": "Le corps de la PR porte `Closes #2` : sans cette ligne GitHub ne "
             "rattache pas la PR (constaté sur la PR #7 de dino-game)."},
    {"id": "t3", "title": "t6 submitted #4", "status": "todo", "body": "issue #6 distincte"},
    {"id": "t4", "title": "t6 submitted #5", "status": "todo", "body": "cite #4 et #7"},
]


def test_graph_liste_ignore_les_hash_libres_des_corps(br, monkeypatch):
    """ERREUR — plus d'issue fantôme : `#7` d'un corps n'est pas un graphe.

    Mesuré sur le board réel : la carte `t6 submitted #2` cite « la PR #7 de
    dino-game » ; `gh issue view 7` répond « Could not resolve ». Compter ce `#7`
    ferait refuser une vraie issue sur un chevauchement IMAGINAIRE.
    """
    monkeypatch.setattr(br, "kanban", lambda *a, **k: json.dumps(_BOARD_REEL))
    trouve = br.issues_with_graph()
    assert 7 not in trouve
    assert 6 not in trouve
    assert 9 not in trouve


def test_graph_liste_est_exactement_la_verite_du_board(br, monkeypatch):
    """NOMINAL — la règle ancrée rend EXACTEMENT {1,2,4,5} sur la forme du board réel.

    Deux ancres seulement : la ligne `Importé depuis …/issues/<n>` et le titre
    `t<n> … #<n>`. Mesuré sur le board réel : 0 manque, 0 faux positif.
    """
    monkeypatch.setattr(br, "kanban", lambda *a, **k: json.dumps(_BOARD_REEL))
    assert br.issues_with_graph() == {1, 2, 4, 5}


def test_graph_liste_retient_le_titre_et_ignore_le_corps(br, monkeypatch):
    """LIMITE — une carte dont le titre porte `t3 grill-me #5` et le corps `#9`.

    Le titre fait foi (5 est retenu), le corps est ignoré (9 ne l'est pas).
    """
    board = [{"id": "t5", "title": "t3 grill-me #5", "status": "done",
              "body": "cette carte mentionne #9 et rien d'autre"}]
    monkeypatch.setattr(br, "kanban", lambda *a, **k: json.dumps(board))
    trouve = br.issues_with_graph()
    assert 5 in trouve
    assert 9 not in trouve


def test_graph_liste_ne_se_vide_pas(br, monkeypatch):
    """LIMITE anti-tautologie — le correctif ne doit pas rendre un ensemble vide.

    Un `return set()` satisferait tous les cas de faux positif : ce cas l'interdit.
    """
    monkeypatch.setattr(br, "kanban", lambda *a, **k: json.dumps(_BOARD_REEL))
    assert br.issues_with_graph() != set()


# --------------------------------- C+D. objet de décision et trappe honnête ----

def test_le_label_de_decision_est_le_nom_gele(br):
    """NOMINAL (interface) — `decision` est le nom gelé de l'objet de décision.

    Surtout PAS `kanban` (« déjà miroir d'une carte » : réutiliser ce nom
    réécrirait la trappe sous un autre motif) et pas `triage`.
    """
    assert hasattr(br, "DECISION_LABEL"), "la constante DECISION_LABEL doit exister"
    assert br.DECISION_LABEL == "decision"
    assert br.DECISION_LABEL != br.MIRROR_LABEL
    assert br.DECISION_LABEL != br.TRIAGE_LABEL


def test_un_objet_de_decision_n_est_jamais_importe(pont):
    """NOMINAL — une issue portant le label de décision est écartée de `pull()`.

    Un objet de décision n'est pas une tâche : mesuré, l'importer déclenche un
    graphe complet (6 cartes + 11 liens + une room) sous une carte de décision.
    """
    mod, _ = pont
    decision = _issue(60, "Décision — carte t_aaa", "Point à statuer sur `t_aaa`.",
                      labels=["decision"], parent=5)
    normale = _issue(61, "Ajouter un compteur de parties", "nouvelle fonctionnalité")
    gh, kb = _tick(pont, {"issues": [decision, normale], "prs": []},
                   {"tasks": [], "next_task_id": "t_cree"})
    assert _creees(kb) == ["Ajouter un compteur de parties"]
    for appel in gh:
        assert "60" not in appel, f"l'objet de décision a été touché : {appel}"


def test_objet_de_decision_coute_zero_appel_de_gate(pont):
    """LIMITE — exclusion par le prédicat de labels, AVANT tout travail de gate.

    Mesure différentielle : le tick portant l'objet de décision a exactement le
    même nombre d'appels que le même tick sans lui.
    """
    mod, _ = pont
    commune = {"issues": [_issue(61, "Ajouter un compteur de parties", "neuf")], "prs": []}
    board = {"tasks": [], "next_task_id": "t_cree"}
    sans, _ = _tick(pont, commune, board)
    avec, _ = _tick(pont, {"issues": commune["issues"] + [
        _issue(60, "Décision — carte t_aaa", "Point à statuer sur `t_aaa`.",
               labels=["decision"], parent=5)], "prs": []}, board)
    assert len(avec) == len(sans), f"{len(avec)} appels avec l'objet contre {len(sans)} sans"
    assert [c[:2] for c in avec] == [c[:2] for c in sans]


def test_l_objet_de_decision_n_est_pas_candidat_au_drill(pont):
    """ERREUR — `cmd_new()` l'exclut aussi, sinon le bot le drillerait."""
    mod, _ = pont
    decision = _issue(60, "Décision — carte t_aaa", "Point à statuer.",
                      labels=["decision"], parent=5)
    normale = _issue(61, "Ajouter un compteur de parties", "neuf")
    _tick(pont, {"issues": [decision, normale], "prs": []}, {"tasks": []}, action="prep")
    (Path(mod.GH_BIN).parent / "gh_state.json").write_text(
        json.dumps({"issues": [decision, normale], "prs": []}))
    (Path(mod.GH_BIN).parent / "gh_calls.log").write_text("")
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        mod.cmd_new()
    candidats = json.loads(buf.getvalue())
    assert [c["number"] for c in candidats] == [61]


def test_le_gate_ne_propose_plus_de_poser_le_label_kanban(pont):
    """ERREUR — la trappe cesse de mentir (elle proposait un geste qui bloque).

    Le commentaire posté sur une issue bloquée ne doit plus contenir la phrase
    « poser le label `kanban` » : c'est l'échappatoire qui EMPÊCHE l'import.
    """
    mod, _ = pont
    bloquee = _issue(70, "Refonte graphique des acteurs", "suite de #5")
    gh, _ = _tick(pont, {"issues": [bloquee], "prs": []},
                  {"tasks": [_carte_racine(5)]})
    corps = _motifs_gate(gh)
    assert corps, "aucun commentaire de gate posté : la prémisse du test est fausse"
    assert "poser le label `kanban`" not in corps[0]


def test_l_echappatoire_proposee_par_le_gate_fonctionne(pont):
    """LIMITE — l'échappatoire nommée par le gate doit être RÉELLE (bypass respecté).

    L'issue candidate est CONSTRUITE POUR ÊTRE REFUSÉE sans le label : elle cite `#5`,
    qui est en vol. Deux mesures dans le même cas — contrôle négatif (sans le label,
    elle est bloquée) puis mesure (avec le label, elle passe) — sinon un import qui
    réussit par le chemin normal ferait croire le bypass respecté.
    """
    mod, _ = pont
    bloquee = _issue(70, "Refonte graphique des acteurs", "suite de #5")
    gh, _ = _tick(pont, {"issues": [bloquee], "prs": []},
                  {"tasks": [_carte_racine(5)]})
    corps = _motifs_gate(gh)
    assert corps, "aucun commentaire de gate posté : la prémisse du test est fausse"
    labels = re.findall(r"label\s+`([^`]+)`", corps[0])
    assert labels, "le gate ne nomme AUCUNE échappatoire : l'humain n'a pas d'issue"
    propose = labels[-1]
    assert propose not in (mod.MIRROR_LABEL, mod.TRIAGE_LABEL), (
        f"le gate propose `{propose}`, que `pull()` écarte : la trappe ment toujours")

    board = {"tasks": [_carte_racine(5)], "next_task_id": "t_bypass"}
    # contrôle négatif : la MÊME issue, sans le label, est refusée par le gate
    _, kb_sans = _tick(pont, {"issues": [
        _issue(71, "Ajouter un compteur de parties", "suite de #5")], "prs": []}, board)
    assert _creees(kb_sans) == [], "la candidate n'est pas en chevauchement : mesure vide"
    # mesure : le label proposé par le gate ouvre bien l'import
    _, kb_avec = _tick(pont, {"issues": [
        _issue(71, "Ajouter un compteur de parties", "suite de #5",
               labels=[propose])], "prs": []}, board)
    assert _creees(kb_avec) == ["Ajouter un compteur de parties"], (
        f"le label proposé (`{propose}`) n'ouvre pas l'import : la trappe ment")


def test_le_label_d_echappatoire_est_cree_avant_d_etre_propose(pont):
    """ERREUR — un label proposé qui n'existe pas n'est pas posable par l'humain.

    Le pont crée le label miroir avant d'importer ; l'échappatoire doit suivre la
    même règle, sinon « poser le label X » est un geste impossible à exécuter.
    """
    mod, _ = pont
    normale = _issue(61, "Ajouter un compteur de parties", "neuf")
    gh, _ = _tick(pont, {"issues": [normale], "prs": []},
                  {"tasks": [], "next_task_id": "t_cree"})
    crees = {c[2] for c in gh if c[:2] == ["label", "create"] and len(c) > 2}
    assert mod.IMPORT_OVERRIDE_LABEL in crees, (
        f"l'échappatoire `{mod.IMPORT_OVERRIDE_LABEL}` n'est jamais créée : {crees}")


def test_une_creation_de_label_ratee_est_bruyante(pont):
    """ERREUR — un échec de création de label remonte, il n'est pas avalé.

    Sans cette garde, la trappe proposerait un label que le pont n'a jamais réussi
    à créer : l'humain tenterait un geste impossible, sans diagnostic.
    """
    mod, d = pont
    for nom in ("gh", "hermes"):
        script = (d / nom).read_text().replace(
            'state = json.load(open(os.path.join(here, "gh_state.json")))',
            'if sys.argv[1:2] == ["label"]:\n'
            '    sys.stderr.write("boom: label create refuse\\n")\n'
            '    sys.exit(1)\n'
            'state = json.load(open(os.path.join(here, "gh_state.json")))')
        (d / nom).write_text(script)
    (d / "gh_state.json").write_text(json.dumps({"issues": [], "prs": []}))
    with pytest.raises(Exception) as exc:
        mod.ensure_label("pj-import", "0e8a16", "Import forcé")
    assert "boom" in str(exc.value) or "label" in str(exc.value).lower(), (
        f"l'échec n'est pas diagnostiquable : {exc.value}")


# ------------------------------------ E. le parent n'est plus en vol (pull() ---

def test_pull_importe_l_enfant_qui_cite_son_parent(pont):
    """NOMINAL (intégration) — le cas réel : l'enfant #40 cite son parent #5 en vol.

    Mesure le comportement là où il compte : la carte est réellement créée.
    """
    mod, _ = pont
    enfant = _issue(40, "Décision — carte t_aaa bloquée",
                    "Sous-issue de #5.\n\nPoint à statuer sur la carte `t_aaa`.", parent=5)
    gh, kb = _tick(pont, {"issues": [enfant], "prs": []}, {"tasks": [_carte_racine(5)]})
    assert _creees(kb) == ["Décision — carte t_aaa bloquée"], (
        "l'enfant de décision n'est pas importable : la boucle ne peut pas démarrer")
    assert not _motifs_gate(gh), "le gate a bloqué un enfant exempté"


def test_pull_bloque_encore_l_enfant_qui_cite_une_autre_issue(pont):
    """LIMITE (intégration) — parent exempté, mais un AUTRE en vol subsiste.

    Le motif posté ne doit nommer QUE le vrai chevauchement (`#7`), jamais le
    parent `#5` : un motif qui cite le parent rend la décision humaine illisible.
    """
    mod, _ = pont
    enfant = _issue(40, "Décision — carte t_aaa bloquée",
                    "Sous-issue de #5, qui dépend de #7.", parent=5)
    gh, kb = _tick(pont, {"issues": [enfant], "prs": []},
                   {"tasks": [_carte_racine(5), _carte_racine(7)]})
    assert _creees(kb) == []
    corps = _motifs_gate(gh)
    assert corps, "le vrai chevauchement #7 n'a pas été signalé"
    assert "#7" in corps[0]
    assert "#5" not in corps[0], "le parent exempté est compté comme recouvrement"


def test_pull_ne_voit_plus_l_issue_fantome_du_board(pont):
    """ERREUR (intégration) — une carte citant « la PR #7 de dino-game » ne fait
    plus bloquer une issue qui cite #7 ; et une vraie couverture bloque toujours.
    """
    mod, _ = pont
    board = [_carte_racine(5),
             {"id": "t6", "title": "t6 submitted #2", "status": "todo",
              "body": "le corps de la PR porte `Closes #2` (constaté sur la PR #7 de dino-game)"}]
    qui_cite_le_fantome = _issue(12, "Ajouter un compteur de parties", "suite de #7")
    qui_cite_un_vrai = _issue(13, "Refonte graphique", "suite de #5")
    _, kb = _tick(pont, {"issues": [qui_cite_le_fantome, qui_cite_un_vrai], "prs": []},
                  {"tasks": board})
    assert _creees(kb) == ["Ajouter un compteur de parties"], (
        "une issue fantôme bloque encore un import légitime")


def test_pull_ne_fait_aucune_passe_reseau_supplementaire(pont):
    """LIMITE — l'exemption du parent ne coûte AUCUNE passe réseau de plus.

    Deux ticks IMPORTABLES (donc le même chemin) : avec et sans parent. Les
    lectures (`--json`) doivent être identiques — `parent` vient du `gh issue list`
    DÉJÀ fait, jamais d'un `gh issue view <n> --json parent` par issue en vol.
    """
    mod, _ = pont
    board = {"tasks": [_carte_racine(5)], "next_task_id": "t_cree"}
    avec_parent, _ = _tick(pont, {"issues": [
        _issue(40, "Décision — carte t_aaa", "Sous-issue de #5.", parent=5)], "prs": []}, board)
    sans_parent, _ = _tick(pont, {"issues": [
        _issue(40, "Décision — carte t_aaa", "Point à statuer.")], "prs": []}, board)

    def lectures(appels):
        return [c[:2] for c in appels if "--json" in c]

    assert lectures(avec_parent) == lectures(sans_parent), (
        f"{lectures(avec_parent)} contre {lectures(sans_parent)}")
    assert lectures(avec_parent) == [["issue", "list"], ["pr", "list"]], (
        f"lectures inattendues : {lectures(avec_parent)}")
    listes = [c for c in avec_parent if c[:2] == ["issue", "list"]]
    champs = [a for c in listes for a in c if a.startswith("number,title,body")]
    assert champs and "parent" in champs[0], (
        f"`gh issue list` ne demande pas `parent` : {champs}")


def test_pull_survit_a_un_board_illisible(pont):
    """Garde-fou — un board illisible rend le gate indisponible, jamais bloquant.

    Comportement mesuré du pont (le gate est dans un `try`), et condition pour que
    l'ancrage des graphes ne devienne pas un point de panne du pull.
    """
    mod, _ = pont
    normale = _issue(61, "Ajouter un compteur de parties", "neuf")
    gh, kb = _tick(pont, {"issues": [normale], "prs": []},
                   {"tasks": [], "tasks_raw": "{ceci n'est pas du JSON", "next_task_id": "t_x"})
    assert _creees(kb) == ["Ajouter un compteur de parties"]


# -------------------------------------------------- copies versionnées --------

def test_les_deux_copies_versionnees_du_pont_sont_identiques():
    """ERREUR — `bridge/` et `pipeline/` sont le MÊME fichier, en deux emplacements.

    Mesuré à la base : `sha256 fe7009bc…` sur les trois chemins. Si une seule copie
    est corrigée, un run « vert » ne dit rien du chemin réellement exécuté — c'est
    exactement le piège « tests verts ≠ pont réparé » relevé au contrat.
    """
    autres = sorted(p for p in (REPO / "bridge" / "gh_kanban_bridge.py",
                                REPO / "pipeline" / "gh_kanban_bridge.py") if p.exists())
    assert len(autres) == 2, f"copies attendues absentes : {autres}"
    premier = autres[0].read_bytes()
    for p in autres[1:]:
        assert p.read_bytes() == premier, f"{p} a divergé de {autres[0]}"


# =========================================================================
# slice 3 (#5) — `issue_number_of()` ANCREE SUR LA LIGNE D'IMPORT
#
# Défaut mesuré sur les cartes RÉELLES du board : `issue_number_of()` prend le
# PREMIER `/issues/<n>` trouvé n'importe où dans le corps. `push()` ferme donc
# l'issue de toute carte `done` qui **cite** une URL, pas seulement de la carte
# racine que `pull()` a écrite. Deux porteurs réels, lus en base :
#
#   · `t_6333de16` « t6 submitted #1 » — `done` le 2026-09-19T23:38:27Z, sa 1re
#     ligne est « Issue GitHub : …/issues/1 ». Cette URL n'est pas un détail :
#     `pj_graphwatch` apparie la carte à l'issue avec elle, elle est donc là
#     PAR CONSTRUCTION et ne peut pas être retirée. L'issue #1 a été fermée
#     2 min plus tard, PR #3 encore ouverte (mergée +7 h), puis rouverte à la
#     main — et re-fermée une 2ᵉ fois le même soir.
#   · la carte racine de #5 elle-même, dans son corps du 15:34Z : l'URL de #4
#     apparaissait à l'offset 7737, la ligne d'import de #5 à 8099 — la règle
#     brute rendait **4**.
#
# La règle est celle ratifiée par la décision humaine (carte `t_a20cbfe1`) :
# ancrer la LIGNE DE PROTOCOLE que `pull()` écrit elle-même — `Importé depuis
# <url>` en début de ligne, `^…$` en multi-ligne. Jamais le test de
# sous-chaîne : mesuré, `"Importé depuis" in body` retient 49 cartes sur
# `pj-hermes-workflow` dont 47 ne sont que des cartes `slice k` citant le
# littéral machine en prose (la spec le gèle verbatim).
#
# RISQUE de l'ancre stricte, mesuré AVANT d'écrire ces cas — 6 boards,
# 130 cartes `done` : **0 carte légitime perdue** en passant de « la ligne
# CONTIENT le marqueur » à « la ligne COMMENCE par le marqueur ». Les seules
# formes écartées sont 6 cartes `archived` de smoke-test d'un autre board,
# écrites à la main (jamais par `pull()`), donc jamais éligibles à `push()`.
# =========================================================================

SLICE3_MARQUEUR = "Importé depuis"
CORPS_DEFAUT = "corps de l'issue"

# Les 5 numéros réellement portés par une ligne de protocole sur le board
# (cartes à clé `gh-issue-*`), mesurés : 1, 2, 4, 5, 7.
CANONIQUES = (1, 2, 4, 5, 7)


def _url(numero, repo=FAKE_REPO):
    """L'URL d'issue telle que `pull()` l'écrit (`issue['url']`)."""
    return f"https://github.com/{repo}/issues/{numero}"


def _corps_canonique(numero, entete=CORPS_DEFAUT):
    """Le corps EXACT produit par `pull()` : le body de l'issue, puis un
    séparateur `\\n\\n—\\n`, puis « Importé depuis <url> » (ligne 500 du pont)."""
    return f"{entete}\n\n—\n{SLICE3_MARQUEUR} {_url(numero)}"


def _carte_slice3(task_id, statut, corps, titre="carte"):
    """Une carte telle que `kanban list --json` la rend."""
    return {"id": task_id, "status": statut, "title": titre, "body": corps}


@pytest.fixture(scope="module")
def br3():
    """Le pont chargé AVEC le dépôt `FAKE_REPO` — celui de ce harnais.

    Le fixture `br` (slice 1/2) est partagé et tourne sur `hyron-fr/dino-game` :
    l'utiliser ici ferait rendre `None` aux fixtures en `FAKE_REPO`, c'est-à-dire
    rougir POUR LA MAUVAISE RAISON. `GH_REPO` est posé sur le module lui-même,
    pas seulement dans l'environnement, pour que le dépôt configuré soit univoque.
    """
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("GH_REPO", FAKE_REPO)
    monkeypatch.setenv("KANBAN_BOARD", "pj-fake-pont")
    for var in VARIABLES_DU_PONT:
        monkeypatch.delenv(var, raising=False)
    spec = importlib.util.spec_from_file_location("br_slice3", PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.GH_REPO = FAKE_REPO
    yield mod
    monkeypatch.undo()


@pytest.fixture
def push_pont(tmp_path, monkeypatch):
    """Le pont chargé avec `gh` et `kanban` REMPLACÉS par des enregistreurs.

    `push()` ne fait aucun aller-retour réseau dans ce harnais : on observe
    exactement quels numéros d'issue il ferme, ce qui est le contrat de la slice.
    """
    monkeypatch.setenv("GH_REPO", FAKE_REPO)
    monkeypatch.setenv("KANBAN_BOARD", "pj-fake-pont")
    for var in VARIABLES_DU_PONT:
        monkeypatch.delenv(var, raising=False)
    spec = importlib.util.spec_from_file_location("br_slice3_push", PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.GH_REPO = FAKE_REPO

    appels = {"tasks": [], "closed": [], "comment": []}

    def faux_gh(*args):
        if tuple(args[:2]) == ("issue", "view"):
            return json.dumps({"state": "OPEN", "number": int(args[2])})
        if tuple(args[:2]) == ("issue", "close"):
            appels["closed"].append(int(args[2]))
            return ""
        return ""

    def faux_kanban(*args):
        if args and args[0] == "list":
            return json.dumps(appels["tasks"], ensure_ascii=False)
        if args and args[0] == "runs":
            return "[]"
        if args and args[0] == "comment":
            appels["comment"].append(args)
        return "{}"

    monkeypatch.setattr(mod, "gh", faux_gh)
    monkeypatch.setattr(mod, "kanban", faux_kanban)
    return mod, appels


# ---------------------------------------------------------------- NOMINAL ---

def test_slice3_nominal_le_corps_de_l_issue_ne_detourne_pas_la_ligne_d_import(br3):
    """NOMINAL — un corps qui cite une AUTRE issue par son URL AVANT la ligne
    d'import : la règle rend le numéro de la ligne écrite par `pull()`.

    Fixture calquée sur le corps réel de la racine de #5 (version 15:34Z), où
    l'URL de #4 précédait la ligne d'import de #5.
    """
    corps = (f"## 5. Hors-scope\n\n"
             f"- **Non** : le versionnement de l'autre issue — déjà traité par\n"
             f"  {_url(4)} — cette issue-ci ne le redouble pas.\n"
             f"- **Non** : les décisions du pipeline lui-même.\n"
             f"\n—\n{SLICE3_MARQUEUR} {_url(5)}")
    # PRÉMISSE : la fixture exerce bien le défaut — la 1re URL du corps est une
    # AUTRE issue. Sans elle, un corps mal construit rendrait le cas vert.
    premiere = re.search(r"/issues/(\d+)", corps)
    assert premiere and premiere.group(1) == "4", (
        f"fixture non discriminante : 1re URL = {premiere and premiere.group(1)}")
    assert br3.issue_number_of(_carte_slice3("t_racine", "done", corps)) == 5


@pytest.mark.parametrize("numero", CANONIQUES)
def test_slice3_nominal_la_forme_canonique_de_pull_est_reconnue(br3, numero):
    """NOMINAL anti-régression — la ligne exacte écrite par `pull()` reste lue,
    pour les 5 numéros réellement présents sur le board.

    L'ancre ne doit perdre AUCUNE carte légitime : c'est le risque nommé par la
    carte (« une ancre trop stricte ferait perdre une carte légitime »).
    """
    assert br3.issue_number_of(
        _carte_slice3(f"t_racine_{numero}", "done", _corps_canonique(numero))) == numero


# ----------------------------------------------------------------- LIMITE ---

def test_slice3_limite_le_marqueur_cite_en_prose_ne_detourne_pas(br3):
    """LIMITE — le corps MENTIONNE le marqueur en prose, et la ligne suivante
    porte l'URL d'une autre issue.

    Forme réelle : 15 cartes du board portent cette phrase (elles citent le
    littéral machine que la spec gèle verbatim), et la même tournure a produit
    47 faux positifs sur le test de sous-chaîne.
    Règle interdite tuée : « première URL APRÈS la première occurrence du
    marqueur » — mesurée à 4 sur cette fixture.
    """
    corps = (f"- interdit de traduire les deux PROTOCOLES verbatim — "
             f"`{SLICE3_MARQUEUR}` et `ROOM:`.\n"
             f"  Voir {_url(4)} pour l'historique.\n"
             f"\n—\n{SLICE3_MARQUEUR} {_url(5)}")
    assert br3.issue_number_of(_carte_slice3("t", "done", corps)) == 5


def test_slice3_limite_l_url_apres_la_ligne_d_import_ne_gagne_pas(br3):
    """LIMITE — une URL d'autre issue apparaît APRÈS la ligne d'import.

    Règle interdite tuée : « prendre la DERNIÈRE URL du corps ».
    """
    corps = (f"corps\n\n—\n{SLICE3_MARQUEUR} {_url(5)}\n\n"
             f"Le suivi de {_url(4)} est hors périmètre.")
    assert br3.issue_number_of(_carte_slice3("t", "done", corps)) == 5


def test_slice3_limite_le_marqueur_au_milieu_de_ligne_n_est_pas_la_protocole(br3):
    """LIMITE — le marqueur cité AU MILIEU d'une ligne, cette ligne portant une
    URL, n'est pas la ligne de protocole.

    `pull()` écrit toujours la sienne en DÉBUT de ligne (le corps de l'issue,
    puis un séparateur, puis la ligne d'import) : une mention au milieu est une
    citation, pas un ancrage. Mesuré sur 6 boards / 130 cartes `done` :
    0 carte perdue par cette exigence.
    Règle interdite tuée : « la ligne CONTIENT le marqueur » — mesurée à 4 ici.
    """
    corps = (f"- rappel : la ligne « {SLICE3_MARQUEUR} {_url(4)} » "
             f"n'est écrite que par `pull()`.\n"
             f"\n—\n{SLICE3_MARQUEUR} {_url(5)}")
    assert br3.issue_number_of(_carte_slice3("t", "done", corps)) == 5


def test_slice3_limite_une_ligne_d_import_d_un_autre_depot_ne_compte_pas(br3):
    """LIMITE — le pont est UN fichier pour 4 dépôts : une ligne de protocole
    d'un autre dépôt ne désigne aucune issue de `GH_REPO`.
    """
    autre = "hyron-fr/autre-depot"
    assert autre != br3.GH_REPO, "fixture non discriminante : même dépôt"
    corps = f"corps\n\n—\n{SLICE3_MARQUEUR} {_url(9, repo=autre)}"
    assert br3.issue_number_of(_carte_slice3("t", "done", corps)) is None


def test_slice3_limite_l_espace_de_fin_de_ligne_est_tolere(br3):
    """LIMITE — tolérance `\\s*$` du motif ratifié (carte `t_a20cbfe1`) : une
    ligne de protocole suivie d'espaces reste la ligne de protocole.

    Un `$` nu la perdrait et `push()` ne fermerait plus jamais cette issue.
    """
    corps = f"corps\n\n—\n{SLICE3_MARQUEUR} {_url(5)}   \n"
    assert br3.issue_number_of(_carte_slice3("t", "done", corps)) == 5


# ----------------------------------------------------------------- ERREUR ---

def test_slice3_erreur_une_carte_qui_cite_l_url_ne_ferme_rien(push_pont):
    """ERREUR — une carte `done` qui CITE l'URL sans porter la ligne de
    protocole ne fait fermer AUCUNE issue.

    Forme réelle : `t6 submitted #N`, dont la 1re ligne est « Issue GitHub :
    <url> ». `pj_graphwatch` se sert de cette URL pour apparier la carte à
    l'issue : elle est présente PAR CONSTRUCTION.
    """
    mod, appels = push_pont
    appels["tasks"] = [_carte_slice3(
        "t_t6", "done", f"Issue GitHub : {_url(4)}\n\n⚠️ CETTE CARTE OUVRE LA PR.",
        titre="t6 submitted #4")]
    mod.push()
    assert appels["closed"] == [], (
        f"le pont a fermé {appels['closed']} sur une carte qui ne fait que citer l'URL")


def test_slice3_erreur_l_incident_mesure_ne_se_reproduit_pas(push_pont):
    """ERREUR — reconstitution de l'incident mesuré sur le board.

    `t_6333de16` « t6 submitted #1 » est passée `done` à 23:38:27Z ; le pont a
    fermé l'issue #1 à 23:40:42Z, la PR #3 n'a été mergée que 7 h plus tard.
    Ici la racine est encore `todo` : SEULE la carte `t6` est `done`, donc rien
    ne doit être fermé.
    """
    mod, appels = push_pont
    appels["tasks"] = [
        _carte_slice3("t_racine5", "todo", _corps_canonique(5), titre="Racine #5"),
        _carte_slice3("t_t6_4", "done",
                      f"Issue GitHub : {_url(4)}\n\n⚠️ CETTE CARTE OUVRE LA PR.",
                      titre="t6 submitted #4"),
    ]
    mod.push()
    assert appels["closed"] == [], (
        f"l'incident se reproduit : {appels['closed']} fermée(s) par une carte t6")


def test_slice3_erreur_la_fermeture_ne_porte_que_sur_la_carte_racine(push_pont):
    """ERREUR — board mixte : la racine de #5 (`done`, ligne de protocole) et
    `t6 submitted #4` (`done`, cite l'URL) sont toutes deux `done`.

    Exactement UNE fermeture, sur #5. Un `[4, 5]` mesure la règle brute ; un
    `[]` mesure un retour vide — ce cas sépare les deux échecs.
    """
    mod, appels = push_pont
    appels["tasks"] = [
        _carte_slice3("t_racine5", "done", _corps_canonique(5), titre="Racine #5"),
        _carte_slice3("t_t6_4", "done",
                      f"Issue GitHub : {_url(4)}\n\n⚠️ CETTE CARTE OUVRE LA PR.",
                      titre="t6 submitted #4"),
    ]
    mod.push()
    assert appels["closed"] == [5], (
        f"fermetures attendues exactement [#5] par la racine ; mesuré {appels['closed']}")


def test_slice3_erreur_un_corps_sans_ligne_d_import_ne_leve_pas(br):
    """ERREUR — corps absent, vide, ou sans ligne de protocole : aucun numéro
    et AUCUNE exception (une carte non issue du pont ne doit pas casser un tick).
    """
    for corps in (None, "", "corps sans ligne de protocole", "voir #4", "—\n—"):
        assert br.issue_number_of(_carte_slice3("t", "done", corps)) is None, (
            f"corps {corps!r} : un numéro a été inventé")
