"""RED — décision humaine sur carte bloquée (issue #5), **re-dérivé** après l'arbitrage.

Ce fichier REMPLACE la version précédente (design « boutons A/C » + Gherkin du corps de
l'issue, obsolètes). Le design ratifié par l'humain en 4 tours :

  - **une issue enfant par carte bloquée**, créée automatiquement au 1er blocage (0 LLM) ;
  - **décision = commentaire GitHub commençant par `/ok`** — jeton unique, pas de bouton,
    pas d'abandon, `/unblock` rejeté (deux grammaires = divergence garantie) ;
  - la **cible est l'enfant** : la décision est portée par l'objet qui représente la carte,
    donc aucune résolution par nom de fil ni par `#N` du ticket parent ;
  - fermeture sur décision ; re-blocage ⇒ la **même** enfant rouverte.

Conséquence sur la 3e branche du gate, qui n'est PAS « parent ⇒ bloqué » mais une
**exemption** : `overlaps = (refs | hits_titre) - {parent}`, bloqué si le reste est non vide.
Sinon l'enfant, qui recouvre son parent par construction, serait refusée à l'import.

Contrat de noms à confirmer (3 lignes, cf. `contrat-5`) : `DECISION_MODULE`, la clé
`ctx['parents']`, et `ctx['last_reopen_comment_id']` (marqueur de re-blocage).
"""
import importlib.util
import os
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]

# Quelle copie ce run valide-t-il ? Mesuré : `tests/test_bridge_coverage_gate.py`
# existe en deux exemplaires homonymes (hermes-workflow et hermes-experiment) qui
# ne diffèrent QUE par cette ligne — l'un importe `REPO/bridge`, l'autre
# `/home/elix/hermes-experiment/bridge` (la copie que les wrappers EXÉCUTENT).
# La convergence #5 doit produire les DEUX runs, sinon « tests verts » ≠ « pont réparé ».
BRIDGE = Path(os.environ["PJ_BRIDGE_COPY"]) if os.environ.get("PJ_BRIDGE_COPY") \
    else REPO / "bridge" / "gh_kanban_bridge.py"

# --------------------------------------------------------------------------
# NOMS À CONFIRMER (une ligne chacun, cf. contrat-5)
# --------------------------------------------------------------------------
DECISION_MODULE = REPO / "pipeline" / "pj_decision.py"
PARENTS_KEY = "parents"                 # {numéro d'issue: numéro du parent | None}
REOPEN_KEY = "last_reopen_comment_id"   # id du commentaire « re-blocage », None si 1er round
TOKEN = "/ok"                           # jeton UNIQUE (ratifié) — `/unblock` est rejeté

BOARD = "pj-hermes-workflow"
PARENT = 5          # le ticket (jamais la cible de la décision)
ENFANT_A = 40       # une enfant = un objet de décision
ENFANT_B = 41       # seconde enfant du MÊME ticket (décidée en parallèle)


def _load(path: Path, name: str):
    if not path.exists():
        pytest.fail(
            f"module versionné absent : {path} — le RED ne peut pas porter sur du "
            f"code non versionné. Si l'arbitrage retient un autre chemin, changer DECISION_MODULE."
        )
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def br():
    os.environ.setdefault("GH_REPO", "hyron-fr/hermes-workflow")
    os.environ.setdefault("KANBAN_BOARD", BOARD)
    return _load(BRIDGE, "br_issue5")


@pytest.fixture(scope="module")
def dm():
    os.environ.setdefault("KANBAN_BOARD", BOARD)
    return _load(DECISION_MODULE, "pj_decision_issue5")


# ==========================================================================
# A. coverage_verdict — 3e branche = EXEMPTION du parent (pas blocage)
# ==========================================================================

def _enfant(numero=ENFANT_A, parent=PARENT, corps=None):
    """Une enfant telle que `gh issue list` la renvoie (`parent` est un dict)."""
    return {
        "number": numero,
        "parent": {"number": parent},
        "title": "Décision — carte t_aaa bloquée : arbitrer le gate",
        "body": corps if corps is not None
        else f"Point à statuer sur la carte `t_aaa`.\n\nSous-issue de #{parent}.",
    }


def _ctx(**kw):
    base = {"open_pr_issues": set(), "graph_issues": {PARENT}, "titles": {}}
    base[PARENTS_KEY] = kw.pop("parents", {})
    base.update(kw)
    return base


def test_enfant_du_ticket_est_importable(br):
    """NOMINAL — la raison d'être de la 3e branche.

    L'enfant cite son parent (ici `#5`) et le parent est en vol : sans exemption il
    serait refusé à l'import, ce qui rend la 2e itération impossible (mesuré).
    """
    e = _enfant()
    assert PARENT in br.issue_refs(e["body"])           # la prémisse : l'enfant cite #5
    v = br.coverage_verdict(e, _ctx(parents={ENFANT_A: PARENT}))
    assert v["blocked"] is False
    assert v["overlaps"] == []


def test_parent_soustrait_mais_vrai_chevauchement_conserve(br):
    """LIMITE — l'exemption du parent ne doit pas blanchir un vrai recouvrement.

    Enfant citant `#5` (parent) ET `#7` (travail en vol non parent) ⇒ bloquée sur [7]
    seulement. C'est le cas que « parent ⇒ non bloqué » ratait.
    """
    e = _enfant(ENFANT_A, corps="Sous-issue de #5, qui dépend de #7.")
    v = br.coverage_verdict(e, _ctx(parents={ENFANT_A: PARENT}, graph_issues={PARENT, 7}))
    assert v["blocked"] is True
    assert v["overlaps"] == [7]
    assert PARENT not in v["overlaps"]


def test_parent_hors_vol_ne_change_rien(br):
    """LIMITE — un parent ni en PR ni en graphe n'est pas un recouvrement à soustraire."""
    v = br.coverage_verdict(_enfant(), _ctx(parents={ENFANT_A: PARENT}, graph_issues=set()))
    assert v["blocked"] is False


def test_ctx_sans_cle_parents_reste_compatible(br):
    """LIMITE — rétrocompatibilité : ctx sans la clé + issue SANS parent = comportement actuel.

    Un appelant ancien (ou une passe partielle) ne doit pas casser le pull : la clé
    absente n'exempte rien et le verdict reste celui d'aujourd'hui.
    """
    ctx = {"open_pr_issues": set(), "graph_issues": {PARENT}, "titles": {}}
    racine = {"number": 9, "parent": None, "title": "Racine", "body": "corrige #5"}
    assert br.coverage_verdict(racine, ctx)["blocked"] is True


def test_repli_sur_issue_parent(br):
    """ERREUR — sans clé `parents`, le repli sur `issue['parent']` suffit.

    `parent` est un dict `{number: N}` côté `gh issue list --json …,parent` : le lire
    comme un entier donnerait `None` et l'exemption serait silencieusement perdue.
    """
    ctx = {"open_pr_issues": set(), "graph_issues": {PARENT}, "titles": {}}
    v = br.coverage_verdict(_enfant(), ctx)          # ctx sans 'parents' ⇒ repli
    assert v["blocked"] is False, "issue['parent'] doit être lu comme un dict, pas un int"


def test_parent_absent_ne_soustrait_rien(br):
    """ERREUR — `parent: None` (issue racine) : aucune exemption, verdict inchangé."""
    i = {"number": 9, "parent": None, "title": "Racine", "body": "corrige #5"}
    v = br.coverage_verdict(i, _ctx(parents={9: None}))
    assert v["blocked"] is True and v["overlaps"] == [5]


# ==========================================================================
# B. module versionné de décision `/ok` — cible = l'ENFANT
# ==========================================================================

def _ctx_decision(enfant=ENFANT_A, cartes=None, **kw):
    ctx = {
        "issue": {"number": enfant, "state": "OPEN", "parent": {"number": PARENT}},
        "cards": cartes if cartes is not None
        else [{"task_id": "t_aaa", "board": BOARD, "status": "blocked", "issue": enfant}],
        "seen_comment_ids": set(),
    }
    ctx[REOPEN_KEY] = kw.pop("reopen", None)
    ctx.update(kw)
    return ctx


def _c(body, cid=900):
    return {"id": cid, "body": body}


def test_ok_nominal_debloque_la_carte_de_l_enfant(dm):
    """NOMINAL — `/ok` sur l'enfant débloque la carte que CET enfant représente."""
    d = dm.decision_from_comment(_ctx_decision(), _c("/ok"))
    assert d["effect"] == "unblock"
    assert d["task_id"] == "t_aaa"
    assert d["board"] == BOARD


def test_deux_enfants_en_parallele_chacune_sur_sa_carte(dm):
    """LIMITE (cas re-dérivé) — deux enfants du même ticket, décidées en parallèle.

    Chaque décision n'agit que sur la carte de SON enfant : aucune résolution par nom
    de fil, aucun `#N` du ticket.
    """
    ctxA = _ctx_decision(ENFANT_A, [{"task_id": "t_aaa", "board": BOARD,
                                     "status": "blocked", "issue": ENFANT_A}])
    ctxB = _ctx_decision(ENFANT_B, [{"task_id": "t_bbb", "board": BOARD,
                                     "status": "blocked", "issue": ENFANT_B}])
    dA = dm.decision_from_comment(ctxA, _c("/ok", 900))
    dB = dm.decision_from_comment(ctxB, _c("/ok", 901))
    assert (dA["task_id"], dB["task_id"]) == ("t_aaa", "t_bbb")


def test_argument_supplementaire_ne_retargette_pas(dm):
    """LIMITE — `/ok t_bbb` : la cible reste l'enfant, l'argument est inerte.

    La grammaire ratifiée est `/ok` seul ; un `task_id` dans le commentaire ne doit pas
    pouvoir désigner une autre carte (sinon la décision redevient une propriété du ticket).
    """
    d = dm.decision_from_comment(_ctx_decision(), _c("/ok t_bbb"))
    assert d["task_id"] == "t_aaa"


@pytest.mark.parametrize("corps", ("/OK", "/Ok", "/oK"))
def test_jeton_casse_indifferente(dm, corps):
    """LIMITE — « /ok » et « /OK » sont la même décision."""
    assert dm.decision_from_comment(_ctx_decision(), _c(corps))["effect"] == "unblock"


def test_jeton_hors_tete_ignore(dm):
    """LIMITE — un jeton cité n'est pas un acte de décision."""
    d = dm.decision_from_comment(_ctx_decision(),
                                 _c("est-ce que /ok est le bon jeton ?"))
    assert d["effect"] == "ignore"


def test_unblock_rejete(dm):
    """ERREUR — grammaire unique : `/unblock` n'est plus une décision, il est ignoré."""
    d = dm.decision_from_comment(_ctx_decision(), _c("/unblock"))
    assert d["effect"] == "ignore"


def test_commentaire_deja_traite_non_rejoue(dm):
    """ERREUR — anti-rejeu dans le même round : le même commentaire ne débloque pas deux fois."""
    d = dm.decision_from_comment(_ctx_decision(seen_comment_ids={900}), _c("/ok", 900))
    assert d["effect"] == "ignore" and d["acted"] is False


def test_ok_anterieur_au_reblocage_est_perime(dm):
    """ERREUR — re-blocage ⇒ même enfant rouverte : l'ancien `/ok` ne vaut plus.

    Sans cette règle, l'enfant rouverte est immédiatement re-fermée au tick suivant par
    le `/ok` du round précédent, toujours présent dans le fil : la décision humaine serait
    consommée sans humain. Le marqueur de re-blocage borne la validité du jeton.
    """
    d = dm.decision_from_comment(_ctx_decision(reopen=950), _c("/ok", 900))
    assert d["effect"] == "ignore"

    d2 = dm.decision_from_comment(_ctx_decision(reopen=950), _c("/ok", 960))
    assert d2["effect"] == "unblock"


def test_ok_hors_blocage_commentaire_sans_unblock(dm):
    """ERREUR — jeton valide, carte déjà active : décision écrite, rien débloqué, humain informé."""
    ctx = _ctx_decision(cartes=[{"task_id": "t_aaa", "board": BOARD,
                                 "status": "running", "issue": ENFANT_A}])
    d = dm.decision_from_comment(ctx, _c("/ok"))
    assert d["effect"] == "comment" and d["task_id"] is None and d["note"]


def test_enfant_fermee_ignore(dm):
    """ERREUR — enfant CLOSED : aucune décision, aucune action (pas d'erreur silencieuse)."""
    d = dm.decision_from_comment(
        _ctx_decision(issue={"number": ENFANT_A, "state": "CLOSED"}), _c("/ok"))
    assert d["effect"] == "ignore"


def test_corps_vide_ou_non_jeton_ignore(dm):
    """ERREUR — corps vide / None / quelconque : jamais de crash, jamais d'effet."""
    for body in ("", "   ", "\n", "juste une remarque"):
        assert dm.decision_from_comment(_ctx_decision(), _c(body))["effect"] == "ignore"


def test_le_core_de_decision_reste_pur(dm, monkeypatch):
    """Garde-fou hexagonal : le core ne porte AUCUN effet (sinon le RED n'est pas falsifiable)."""
    import subprocess

    for name in ("subprocess", "requests", "urllib", "socket", "sqlite3"):
        assert not hasattr(dm, name), f"{name} ne doit pas être importé dans le core"

    def _boom(*a, **k):
        raise AssertionError("le core pur ne doit pas appeler subprocess")

    monkeypatch.setattr(subprocess, "run", _boom)
    assert dm.decision_from_comment(_ctx_decision(), _c("/ok"))["effect"] == "unblock"
