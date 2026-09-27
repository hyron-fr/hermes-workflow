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
import sys
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


# ==========================================================================
# C. Durcissement du contrat (slice 4) — les cas ci-dessous ont été ajoutés
#    APRÈS mesure par mutation : 4 mutants du module survivaient au banc
#    (voir `red-4`), c'est-à-dire que le banc laissait passer une
#    implémentation que le Gherkin interdit. Aucun cas existant n'a été
#    retouché : ces cas ne font que fermer les faux verts mesurés.
# ==========================================================================

# Cartes d'un SECOND enfant du même ticket : elles ne doivent JAMAIS être
# touchées par la décision de l'enfant A. Présentes dans le contexte pour
# reproduire la production (l'appelant passe toutes les cartes lues), pas pour
# être ciblées : c'est exactement la « résolution par le fil » que la slice
# interdit.
def _ctx_sans_carte_de_enfant(**kw):
    """Ctx dont AUCUNE carte ne porte l'issue de l'enfant (fil non lié)."""
    return _ctx_decision(cartes=[{"task_id": "t_zzz", "board": BOARD,
                                  "status": "blocked", "issue": ENFANT_B}], **kw)


def test_cible_jamais_une_carte_d_un_autre_enfant(dm):
    """LIMITE — le ctx porte la carte d'un AUTRE enfant : aucune ne doit être visée.

    C'est la règle centrale du design ratifié (cible = l'enfant), et c'était un
    faux vert mesuré : viser `cards[0]` au lieu de filtrer sur l'issue de l'enfant
    laissait le banc entièrement vert. `test_deux_enfants_en_parallele…` ne le
    voyait pas parce que ses deux ctx ne portent qu'une carte chacun.
    """
    ctx = _ctx_decision(cartes=[
        {"task_id": "t_aaa", "board": BOARD, "status": "blocked", "issue": ENFANT_A},
        {"task_id": "t_bbb", "board": BOARD, "status": "blocked", "issue": ENFANT_B},
    ])
    d = dm.decision_from_comment(ctx, _c("/ok"))
    assert d["task_id"] == "t_aaa", "la décision doit viser la carte de CET enfant"
    assert d["task_id"] != "t_bbb", "jamais la carte d'un autre enfant (résolution par le fil)"

    d2 = dm.decision_from_comment(_ctx_sans_carte_de_enfant(), _c("/ok"))
    assert d2["effect"] == "comment", "aucune carte liée à l'enfant : rien à débloquer"
    assert d2["task_id"] is None, "ne jamais débloquer une carte d'un autre enfant"


def test_deux_cartes_bloquees_meme_enfant_ne_debloquent_rien(dm):
    """ERREUR — 2 cartes liées à la MÊME enfant : cible indéterminée, aucun unblock.

    Faux vert mesuré : retirer cette garde (débloquer la première) laissait le banc
    vert. Le contrat « une enfant par carte » ne doit donc pas se dégrader
    silencieusement en un choix arbitraire.
    """
    ctx = _ctx_decision(cartes=[
        {"task_id": "t_aaa", "board": BOARD, "status": "blocked", "issue": ENFANT_A},
        {"task_id": "t_ccc", "board": BOARD, "status": "blocked", "issue": ENFANT_A},
    ])
    d = dm.decision_from_comment(ctx, _c("/ok"))
    assert d["effect"] == "comment", "cible indéterminée : jamais un unblock arbitraire"
    assert d["task_id"] is None
    assert d["note"], "l'humain doit être informé (jamais silencieux)"


def test_la_decision_porte_acted_vrai_quand_elle_agit(dm):
    """LIMITE — `acted` distingue « décision calculée » de « effet à porter ».

    Faux vert mesuré : forcer `acted=False` sur le chemin nominal laissait le banc
    vert. Seul `test_commentaire_deja_traite_non_rejoue` lisait ce champ ; il ne
    contraint que le chemin `ignore`.
    """
    d = dm.decision_from_comment(_ctx_decision(), _c("/ok"))
    assert d["effect"] == "unblock"
    assert d["acted"] is True, "l'appelant doit pouvoir porter l'effet"

    d2 = dm.decision_from_comment(_ctx_decision(), _c("juste une remarque"))
    assert d2["effect"] == "ignore"
    assert d2["acted"] is False, "un ignore ne porte aucun effet"


def test_le_core_est_pur_a_l_execution(dm):
    """ERREUR — la pureté est prouvée par EXÉCUTION, pas par lecture du texte.

    `test_le_core_de_decision_reste_pur` lit des noms (`hasattr`) : il attrape les
    `import x` littéraux et RIEN d'autre. Mesuré : un core appelant
    `__import__("socket").gethostbyname(...)` — donc non pur, donc un RED
    infalsifiable hors ligne — le laissait entièrement vert.

    Ici la sentinelle est un MÉTA-CHEMIN D'IMPORT installé AVANT l'appel : toute
    résolution (`__import__`, `importlib.import_module`, y compris en appel
    littéral) et tout chargement de module passent par `sys.meta_path` ou
    `builtins.__import__`, et sont donc consignés puis refusés. Le contrôle
    négatif (`test_sentinelle_de_purete_rejette_l_impur`) prouve que la
    sentinelle mord réellement.
    """
    journal = _purity_harness(lambda: dm.decision_from_comment(_ctx_decision(), _c("/ok")))
    assert not journal, (
        "le core a résolu un module d'effet pendant la décision : "
        f"{sorted(set(journal))} — un core impur rend le RED infalsifiable"
    )
    assert journal.result["effect"] == "unblock"


def test_sentinelle_de_purete_rejette_l_impur():
    """CONTRÔLE NÉGATIF — la sentinelle doit mordre sur un core impur connu.

    Sans ce cas, la sentinelle ci-dessus est un toujours-vert déguisé : elle
    passerait aussi bien si elle ne détectait rien. On lui donne un sujet
    franchement impur (résolution dynamique + lecture d'attribut) et on exige
    qu'elle le nomme.
    """
    def impur():
        return __import__("socket").gethostbyname("localhost")

    journal = _purity_harness(impur)
    assert journal, "la sentinelle n'a pas vu une résolution dynamique : elle ne prouve rien"
    assert any("socket" in e for e in journal), journal


class _Journal:
    """Journal de pureté : les modules d'effet résolus pendant l'appel."""

    def __init__(self):
        self.entrees = []
        self.result = {}
        self.modules_charges = []

    def __bool__(self):
        return bool(self.entrees)

    def __iter__(self):
        return iter(self.entrees)


def _purity_harness(fn):
    """Exécute `fn` en consignant TOUTE résolution de module d'effet.

    Trois surfaces couvertes, car aucune ne suffit seule :
      - `sys.meta_path` (imports en instruction, résolution littérale) ;
      - `builtins.__import__` (la fonction réellement appelée par `__import__`) ;
      - un témoin `sys.modules` (un module déjà chargé et lu par attribut).
    """
    import builtins
    import importlib.abc

    racines = {"socket", "subprocess", "urllib", "requests", "sqlite3", "http", "os"}
    journal = _Journal()

    def consigne(name):
        if str(name).split(".")[0] in racines:
            journal.entrees.append(str(name))

    class _Probe(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            consigne(fullname)
            raise ImportError(f"core impur : import de {fullname} interdit")

    probe = _Probe()
    vrai_import = builtins.__import__

    def garde(name, *a, **k):
        consigne(name)
        return vrai_import(name, *a, **k)

    avant_modules = set(sys.modules)
    sys.meta_path.insert(0, probe)
    builtins.__import__ = garde
    try:
        journal.result = fn()
    except AssertionError:
        raise
    except Exception as exc:  # un core impur échoue : c'est le signal recherché
        journal.entrees.append(f"exception:{type(exc).__name__}")
    finally:
        sys.meta_path.remove(probe)
        builtins.__import__ = vrai_import
        journal.modules_charges = sorted(
            m for m in set(sys.modules) - avant_modules if m.split(".")[0] in racines)
    journal.entrees.extend(journal.modules_charges)
    return journal
