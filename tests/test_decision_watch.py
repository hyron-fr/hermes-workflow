"""Câblage `/ok` — le runner qui consomme `pj_decision` et `pj_notify` (issue #5).

Ce banc porte sur le **câblage**, pas sur la décision ni sur les notifications : les
contrats de `pj_decision` et `pj_notify` sont déjà pinnés par leurs propres bancs
(`test_decision_humaine.py`, `test_notify_2_niveaux.py`). Ici on vérifie ce qui
n'existait pas : un **consommateur de production**.

Tout est injecté — les deux modules sont chargés depuis le dépôt, `gh`/`kanban` sont
des doubles : le banc tourne hors ligne, sans board réel et sans réseau, donc il est
falsifiable (il échoue si le câblage cesse d'appeler ce qu'il prétend appeler).

Les trois natures exigées (nominal / limite / erreur) sont balisées par mot-clé.
"""
import importlib.util
import json
import os
import sys
from pathlib import Path

import re

import pytest

REPO = Path(__file__).resolve().parents[1]
WATCH_MODULE = REPO / "pipeline" / "pj_decision_watch.py"

BOARD = "pj-hermes-workflow"
CHILD = 40          # l'objet de décision (issue enfant)
PARENT = 5          # le ticket — jamais fermé par une décision de carte
TASK = "t_abc123"
OTHER_TASK = "t_def456"


def _load(path: Path, name: str):
    if not path.exists():
        pytest.fail(f"module absent : {path} — le câblage n'est pas versionné")
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def w():
    return _load(WATCH_MODULE, "pj_decision_watch")


@pytest.fixture
def cfg(w, tmp_path):
    return w.WatchConfig(org="hyron-fr", repos=["hermes-workflow"], board=BOARD,
                         gh_bin="/usr/bin/gh", hermes_bin="/usr/bin/hermes",
                         state_dir=str(tmp_path))


class FakeRun:
    """Double de `subprocess.run` : rend les sorties déclarées, enregistre les appels."""

    def __init__(self, *, comments=None, issues=None, gh_rc=0, kanban_rc=0):
        self.comments = comments or []
        self.issues = issues if issues is not None else [_child()]
        self.gh_rc = gh_rc
        self.kanban_rc = kanban_rc
        self.appels = []

    def __call__(self, cmd, **kw):
        joined = " ".join(cmd)
        self.appels.append(joined)

        class R:
            pass

        r = R()
        r.returncode = 0
        r.stderr = ""
        if "issue list" in joined:
            r.returncode = self.gh_rc
            r.stdout = json.dumps(self.issues)
        elif "issue view" in joined and "comments" in joined:
            r.returncode = self.gh_rc
            r.stdout = json.dumps({"comments": self.comments})
        elif "kanban" in joined:
            r.returncode = self.kanban_rc
            r.stdout = ""
        else:                                   # issue comment/close
            r.returncode = self.gh_rc
            r.stdout = ""
        return r

    # --- commodités de lecture du journal ---

    def kanban_calls(self, verb):
        return [c for c in self.appels if f"kanban --board {BOARD} {verb} " in c]

    def gh_calls(self, verb):
        return [c for c in self.appels if f"issue {verb} " in c]


def _child(body=None, parent=PARENT, number=CHILD, state="OPEN"):
    b = body if body is not None else f"Point à statuer.\n\ncarte: {BOARD}/{TASK}\n"
    d = {"number": number, "title": f"décision carte {TASK}", "body": b, "state": state,
         "url": f"https://github.com/hyron-fr/hermes-workflow/issues/{number}"}
    if parent is not None:
        d["parent"] = {"number": parent}
    return d


def _comment(cid=900, body="/ok"):
    return {"id": cid, "body": body,
            "url": f"https://github.com/hyron-fr/hermes-workflow/issues/{CHILD}#issuecomment-{cid}"}


def _patch_status(w, monkeypatch, status="blocked"):
    monkeypatch.setattr(w, "card_status", lambda board, task, cfg: status)


@pytest.fixture(autouse=True)
def _no_real_board(w, monkeypatch, tmp_path):
    """Hermétisme : la phase de PRODUCTION lit le board ; le banc ne doit jamais
    toucher la base réelle de la machine.

    On déplace la RACINE (et non la fonction) : les cas qui exercent réellement
    `blocked_cards` repointent `KANBAN_ROOT` vers leur base de test, et ceux qui ne
    s'y intéressent pas voient un board vide — jamais celui de production.
    """
    monkeypatch.setattr(w, "KANBAN_ROOT", tmp_path / "aucun-board")


# ----------------------------------------------------------------- nominal ---

def test_nominal_ok_debloque_la_carte_et_notifie_les_deux_fils(w, cfg, monkeypatch):
    """NOMINAL — un `/ok` débloque la carte désignée, puis notifie enfant PUIS parent."""
    _patch_status(w, monkeypatch)
    run = FakeRun(comments=[_comment()])
    st = w.watch_repo("hermes-workflow", cfg=cfg, runner=run)

    assert [u["task"] for u in st["unblocked"]] == [TASK]
    assert len(run.kanban_calls("unblock")) == 1
    assert len(run.kanban_calls("comment")) == 1, "le worker re-spawné doit trouver la décision"
    # l'enfant est commenté ET fermé ; le parent est commenté, jamais fermé
    assert str(CHILD) in " ".join(run.gh_calls("comment"))
    assert str(CHILD) in " ".join(run.gh_calls("close"))
    assert str(PARENT) in " ".join(run.gh_calls("comment"))
    assert str(PARENT) not in " ".join(run.gh_calls("close")), \
        "une décision de carte ne clôt pas le ticket"


def test_nominal_la_carte_est_designee_par_la_ligne_canonique(w, cfg, monkeypatch):
    """La cible vient de `carte: <board>/<task>`, jamais d'une résolution par fil."""
    _patch_status(w, monkeypatch)
    run = FakeRun(comments=[_comment()], issues=[_child(body=f"blabla\ncarte: {BOARD}/{OTHER_TASK}\n")])
    st = w.watch_repo("hermes-workflow", cfg=cfg, runner=run)
    assert [u["task"] for u in st["unblocked"]] == [OTHER_TASK]
    assert f"comment {OTHER_TASK}" in " ".join(run.kanban_calls("comment"))


# ------------------------------------------------------------------ limite ---

def test_limite_jeton_cite_au_milieu_nest_pas_un_acte(w, cfg, monkeypatch):
    """LIMITE — « je pense qu'il faut /ok » n'est pas un `/ok` : rien ne bouge."""
    _patch_status(w, monkeypatch)
    run = FakeRun(comments=[_comment(cid=901, body="il faudrait un /ok ici ?")])
    st = w.watch_repo("hermes-workflow", cfg=cfg, runner=run)
    assert st["unblocked"] == []
    assert run.kanban_calls("unblock") == []
    assert st["ignored"] == 1


def test_limite_jeton_anterieur_au_reblocage_est_perime(w, cfg, monkeypatch):
    """LIMITE — un `/ok` du round précédent ne re-débloque pas une enfant rouverte.

    Sans cette péremption, le jeton déjà présent dans le fil refermerait l'enfant
    rouverte immédiatement (défaut décrit par le design ratifié).
    """
    _patch_status(w, monkeypatch)
    decision = _load(REPO / "pipeline" / "pj_decision.py", "pj_decision_lim")
    ctx = {"issue": {"number": CHILD, "state": "OPEN"},
           "cards": [{"task_id": TASK, "board": BOARD, "status": "blocked", "issue": CHILD}],
           "seen_comment_ids": set(), "last_reopen_comment_id": 950}
    out = decision.decision_from_comment(ctx, _comment(cid=900))
    assert out["effect"] == "ignore" and out["acted"] is False


def test_limite_dry_run_napplique_rien(w, cfg, monkeypatch):
    """LIMITE — `--dry-run` : aucune écriture, ni kanban ni GitHub."""
    _patch_status(w, monkeypatch)
    run = FakeRun(comments=[_comment()])
    st = w.watch_repo("hermes-workflow", cfg=cfg, dry=True, runner=run)
    assert st["unblocked"] == []
    assert run.kanban_calls("unblock") == [] and run.gh_calls("comment") == []


def test_limite_second_tick_ne_rejoue_pas_la_meme_decision(w, cfg, monkeypatch):
    """LIMITE — l'état inter-ticks rend le rejeu muet (anti-reboucle)."""
    _patch_status(w, monkeypatch)
    run1 = FakeRun(comments=[_comment(cid=910)])
    assert len(w.watch_repo("hermes-workflow", cfg=cfg, runner=run1)["unblocked"]) == 1
    run2 = FakeRun(comments=[_comment(cid=910)])
    st2 = w.watch_repo("hermes-workflow", cfg=cfg, runner=run2)
    assert st2["unblocked"] == [] and run2.kanban_calls("unblock") == []


# ------------------------------------------------------------------- erreur ---

def test_erreur_le_jeton_anticipe_est_ecrit_mais_ne_debloque_pas(w, cfg, monkeypatch):
    """ERREUR — `/ok` reçu alors que la carte n'est plus bloquée : trace, pas silence."""
    _patch_status(w, monkeypatch, status="running")
    run = FakeRun(comments=[_comment()])
    st = w.watch_repo("hermes-workflow", cfg=cfg, runner=run)
    assert st["unblocked"] == [] and run.kanban_calls("unblock") == []
    assert st["commented"], "une décision sans effet doit être TRACÉE, jamais silencieuse"
    assert len(run.kanban_calls("comment")) == 1


def test_erreur_grammaire_refusee_ne_debloque_pas(w, cfg, monkeypatch):
    """ERREUR — `/unblock` est une grammaire refusée : jamais une décision."""
    _patch_status(w, monkeypatch)
    run = FakeRun(comments=[_comment(cid=902, body="/unblock")])
    st = w.watch_repo("hermes-workflow", cfg=cfg, runner=run)
    assert st["unblocked"] == [] and run.kanban_calls("unblock") == []


def test_erreur_gh_indisponible_est_bruyant_et_ne_leve_pas(w, cfg, monkeypatch):
    """ERREUR — sans `gh`, le tick ne tombe pas : il avertit et ne fait rien."""
    run = FakeRun(issues=[])
    cfg.gh_bin = ""
    st = w.watch_repo("hermes-workflow", cfg=cfg, runner=run)
    assert st["unblocked"] == []


def test_erreur_unblock_refuse_nest_pas_silencieux(w, cfg, monkeypatch):
    """ERREUR — un `unblock` refusé est rapporté, pas avalé."""
    _patch_status(w, monkeypatch)
    run = FakeRun(comments=[_comment()], kanban_rc=1)
    st = w.watch_repo("hermes-workflow", cfg=cfg, runner=run)
    assert st["unblocked"] == []
    assert st["errors"] and st["errors"][0]["issue"] == CHILD


# ------------------------------------------------------- config & intégrité ---

def test_config_refusee_si_variable_requise_absente(w, monkeypatch):
    """ERREUR — variable requise absente ⇒ ConfigError nommée (rc=2 en production)."""
    monkeypatch.delenv("PJ_WATCH_ORG", raising=False)
    with pytest.raises(w.ConfigError) as e:
        w.validate_config(w.decision_config(env={}))
    assert "PJ_WATCH_ORG" in str(e.value)


def test_config_refusee_si_repos_vide(w, monkeypatch):
    """ERREUR — org présent mais aucun dépôt ⇒ refus (jamais un tick fantôme)."""
    with pytest.raises(w.ConfigError):
        w.validate_config(w.decision_config(
            env={"PJ_WATCH_ORG": "hyron-fr", "PJ_WATCH_REPOS": ""}))


def test_le_cablage_appelle_bien_les_deux_modules_versionnes(w, cfg, monkeypatch):
    """GARDE-FOU — le câblage sans ses modules ne sert à rien : il les appelle vraiment.

    On remplace les modules par des espions : si le runner cessait de les appeler
    (réimplémentation locale de la grammaire, par exemple), ce test tombe.
    """
    _patch_status(w, monkeypatch)
    appels = {"decision": 0, "notify": 0}

    real = _load(REPO / "pipeline" / "pj_decision.py", "pj_decision_spy")

    class SpyDecision:
        @staticmethod
        def decision_from_comment(ctx, comment):
            appels["decision"] += 1
            return real.decision_from_comment(ctx, comment)

    notify = _load(REPO / "pipeline" / "pj_notify.py", "pj_notify_spy")

    class SpyNotify:
        @staticmethod
        def notify_decision(decision, ctx, effects):
            appels["notify"] += 1
            return notify.notify_decision(decision, ctx, effects)

    run = FakeRun(comments=[_comment()])
    w.watch_repo("hermes-workflow", cfg=cfg, runner=run,
                 decision_mod=SpyDecision, notify_mod=SpyNotify)
    assert appels["decision"] >= 1, "la décision doit venir du module versionné"
    assert appels["notify"] == 1, "un déblocage doit notifier via pj_notify"


def test_card_lines_grammaire(w):
    """La ligne canonique : lue quand elle est seule sur sa ligne, ignorée sinon."""
    assert w.canonical_card(f"carte: {BOARD}/{TASK}") == (BOARD, TASK)
    assert w.canonical_card(f"  carte :  {BOARD} / {TASK}  ") == (BOARD, TASK)
    assert w.canonical_card(f"on lit carte: {BOARD}/{TASK} dans le corps") is None
    assert w.canonical_card("rien du tout") is None

# =============================================================== producteur =====
# Le maillon ratifié par l'Option 1 : « /ok devient le consentement ET autorise la
# pose ». Sans lui il n'existe AUCUN endroit où écrire /ok — mesuré :
# `gh issue list --label decision` → `[]`, et le design attribue la création de
# l'enfant à cette slice de câblage.

class FakeProd:
    """Runner du producteur ET du consommateur : label, liste, create, reopen,
    commentaire, lecture des commentaires, kanban. Journalise tout."""

    def __init__(self, *, children=None, comments=None, label_rc=0, label_err="",
                 create_out="", create_rc=0, reopen_rc=0, kanban_rc=0):
        self.children = children if children is not None else []
        self.comments = comments if comments is not None else []
        self.label_rc, self.label_err = label_rc, label_err
        self.create_out, self.create_rc = create_out, create_rc
        self.reopen_rc, self.kanban_rc = reopen_rc, kanban_rc
        self.appels = []

    def __call__(self, cmd, **kw):
        j = " ".join(cmd)
        self.appels.append(j)

        class R:
            pass

        r = R()
        r.returncode, r.stdout, r.stderr = 0, "", ""
        if "label create" in j:
            r.returncode, r.stderr = self.label_rc, self.label_err
        elif "issue list" in j:
            r.stdout = json.dumps(self.children)
        elif "issue view" in j and "comments" in j:
            r.stdout = json.dumps({"comments": self.comments})
        elif "issue create" in j:
            r.returncode, r.stdout = self.create_rc, self.create_out
            # Réalisme : un enfant créé au tick courant est VISIBLE des lectures
            # suivantes du même tick (c'est ce que ferait l'API réelle).
            if self.create_rc == 0:
                m = re.search(r"/issues/(\d+)", self.create_out or "")
                if m:
                    self.children.append({"number": int(m.group(1)), "title": "créée",
                                          "body": f"carte: {BOARD}/{TASK}\n", "url": "",
                                          "parent": {"number": PARENT}})
        elif "issue reopen" in j:
            r.returncode = self.reopen_rc
        elif "kanban" in j:
            r.returncode = self.kanban_rc
            if "kanban --board" in j and ("unblock" in j or "comment" in j):
                pass
        return r

    def create_calls(self):
        return [c for c in self.appels if "issue create" in c]

    def reopen_calls(self):
        return [c for c in self.appels if "issue reopen" in c]

    def gh_comment_calls(self):
        return [c for c in self.appels if "issue comment" in c]

    def kanban_calls(self, verb):
        return [c for c in self.appels if f"kanban --board {BOARD} {verb} " in c]


# ----------------------------------------------------------------- nominal ---

def test_production_cree_lenfant_du_premier_blocage(w, cfg):
    """NOMINAL — une carte bloquée obtient SON enfant, rattachée au ticket et labellisée."""
    run = FakeProd(create_out="https://github.com/hyron-fr/hermes-workflow/issues/77\n")
    res = w.ensure_decision_child(cfg, "hermes-workflow", parent=PARENT, board=BOARD,
                                  task_id=TASK, title="titre", reason="motif", runner=run)
    assert res["effect"] == "created" and res["child"] == 77
    cree = " ".join(run.create_calls())
    assert "--parent 5" in cree, "l'enfant est rattachée au ticket : le parent ne se devine pas"
    assert f"--label {w.DECISION_LABEL}" in cree
    assert f"carte: {BOARD}/{TASK}" in cree, "la ligne canonique est posée par le PRODUCTEUR"


def test_production_label_absent_est_cree_avant_lenfant(w, cfg):
    """NOMINAL — `decision` est absent du dépôt (mesuré) : le label est créé d'abord.

    Sans ce geste, `gh issue create --label decision` échoue et le message d'escalade
    proposerait un `/ok` sans issue où l'écrire — la trappe qui ment.
    """
    run = FakeProd(label_rc=0)
    assert w.ensure_decision_label(cfg, "hermes-workflow", runner=run) is True
    assert any("label create" in c for c in run.appels)


def test_production_label_deja_present_nest_pas_une_erreur(w, cfg):
    """LIMITE — `already exists` est le cas NORMAL d'un tick suivant : idempotent."""
    run = FakeProd(label_rc=1, label_err="HTTP 422: Validation Failed (already exists)")
    assert w.ensure_decision_label(cfg, "hermes-workflow", runner=run) is True


# ------------------------------------------------------------------ limite ---

def test_production_reblocage_rouvre_la_meme_enfant_jamais_dupliquee(w, cfg):
    """LIMITE — re-blocage : la MÊME enfant est rouverte et le marqueur est posté.

    L'ordre importe : GitHub refuse `reopen` sur une issue ouverte ; et c'est le
    commentaire neuf qui porte le nouveau `last_reopen_comment_id`.
    """
    run = FakeProd(children=[_child(body=f"carte: {BOARD}/{TASK}\n", state="CLOSED")])
    res = w.ensure_decision_child(cfg, "hermes-workflow", parent=PARENT, board=BOARD,
                                  task_id=TASK, title="titre", reason="re-blocage", runner=run)
    assert res["effect"] == "reopened" and res["child"] == CHILD
    assert run.create_calls() == [], "un re-blocage ne DUPLIQUE jamais l'enfant"
    assert run.reopen_calls(), "la même enfant est rouverte"
    assert run.gh_comment_calls(), "le marqueur de re-blocage est posté"
    assert w.REOPEN_MARKER in " ".join(run.gh_comment_calls())


def test_production_jeton_anterieur_au_marqueur_est_perime(w, cfg, monkeypatch):
    """LIMITE — un `/ok` antérieur au marqueur ne débloque pas ; le marqueur est RELU.

    C'est cette relecture qui rend la péremption effective : sans elle
    `last_reopen_comment_id` resterait None et le jeton du round précédent
    refermerait l'enfant rouverte — le blocage deviendrait définitif.
    """
    _patch_status(w, monkeypatch)
    precedent = _comment(cid=900, body="/ok")
    marqueur = _comment(cid=9400, body=f"{w.REOPEN_MARKER} — la carte est bloquée de nouveau.")
    run = FakeProd(children=[_child()], comments=[precedent, marqueur])
    st = w.watch_repo("hermes-workflow", cfg=cfg, runner=run)
    assert st["unblocked"] == [], "le /ok antérieur au re-blocage ne débloque pas"
    assert run.kanban_calls("unblock") == []


def test_production_jeton_du_nouveau_round_debloque(w, cfg, monkeypatch):
    """LIMITE — symétrique : le `/ok` POSTÉRIEUR au marqueur débloque normalement."""
    _patch_status(w, monkeypatch)
    marqueur = _comment(cid=9400, body=f"{w.REOPEN_MARKER} — la carte est bloquée de nouveau.")
    nouveau = _comment(cid=9500, body="/ok")
    run = FakeProd(children=[_child()], comments=[marqueur, nouveau])
    st = w.watch_repo("hermes-workflow", cfg=cfg, runner=run)
    assert [u["task"] for u in st["unblocked"]] == [TASK]


# ------------------------------------------------------------------- erreur ---

def test_production_echec_de_creation_est_rapporte_jamais_invente(w, cfg):
    """ERREUR — création refusée ⇒ `failed` nommé, jamais un faux succès."""
    run = FakeProd(create_rc=1)
    res = w.ensure_decision_child(cfg, "hermes-workflow", parent=PARENT, board=BOARD,
                                  task_id=TASK, title="titre", reason="motif", runner=run)
    assert res["effect"] == "failed" and res["child"] is None and res["why"]


def test_production_label_indisponible_arrete_le_producteur(w, cfg):
    """ERREUR — label impossédable : on ne crée pas un enfant qu'on ne peut ni lier
    ni relire (le pont l'importerait comme une tâche)."""
    run = FakeProd(label_rc=1, label_err="HTTP 403: Forbidden")
    res = w.ensure_decision_child(cfg, "hermes-workflow", parent=PARENT, board=BOARD,
                                  task_id=TASK, title="t", reason="", runner=run)
    assert res["effect"] == "failed" and run.create_calls() == []


def test_production_enfant_non_rattache_ne_devine_pas_de_parent(w, cfg):
    """ERREUR — sans `parent` lisible, le parent reste None : jamais deviné."""
    assert w._parent_of({"number": 40}) is None
    assert w._parent_of({"number": 40, "parent": {"number": 5}}) == 5
    assert w._parent_of({"number": 40, "parent": None}) is None


# ------------------------------------------------------------- intégration ---

def test_production_le_meme_tick_produit_puis_consomme(w, cfg, monkeypatch):
    """INTÉGRATION — boucle complète d'Option 1, en un seul tick, sans intervention.

    Le producteur fait exister l'objet de décision, le consommateur lit le jeton,
    débloque la carte et notifie les deux fils.
    """
    _patch_status(w, monkeypatch)
    cards = [{"board": BOARD, "task_id": TASK, "title": "t", "issue": PARENT, "reason": ""}]
    monkeypatch.setattr(w, "blocked_cards", lambda cfg, board=None: cards)
    # children=[] au départ : au 1er blocage, l'enfant N'EXISTE PAS encore — c'est
    # tout le maillon manquant. Le /ok n'a de sens qu'après la création.
    run = FakeProd(children=[], comments=[_comment()],
                   create_out=f"https://github.com/hyron-fr/hermes-workflow/issues/{CHILD}\n")
    st = w.watch_repo("hermes-workflow", cfg=cfg, runner=run)
    assert st["children"] and st["children"][0]["effect"] == "created",         f"le tick fait exister l'objet de décision : {st.get('children')}"
    assert [u["task"] for u in st["unblocked"]] == [TASK],         f"le même tick consomme le /ok : {st['unblocked']}"
    assert run.create_calls(), "l'enfant a été créée"
    assert run.kanban_calls("unblock"), "la carte est réellement débloquée"


# =============================================== couverture des chemins réels =====
# Portage de couverture (seuil du dépôt : >80 % PAR FICHIER, périmètre
# `git diff --name-only origin/dev...HEAD`). Chaque cas ci-dessous porte une
# ASSERTION de comportement : un test qui ne fait qu'exécuter des lignes serait
# rejeté en convergence.

def test_couverture_blocked_cards_lit_le_board(tmp_path, w, monkeypatch):
    """La lecture du board : cartes bloquées/triage, issue RÉSOLUE, motif extrait."""
    import sqlite3
    root = tmp_path / "boards"
    board_dir = root / BOARD
    board_dir.mkdir(parents=True)
    c = sqlite3.connect(board_dir / "kanban.db")
    c.executescript(
        "CREATE TABLE tasks(id TEXT PRIMARY KEY, title TEXT, body TEXT, assignee TEXT,"
        " status TEXT, idempotency_key TEXT);"
        "CREATE TABLE task_events(id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT,"
        " kind TEXT, payload TEXT);"
        "CREATE TABLE task_links(parent_id TEXT, child_id TEXT);")
    c.executemany("INSERT INTO tasks VALUES (?,?,?,?,?,?)", [
        ("t_k", "Carte clée", "corps", "pj-dev", "blocked", "pj-dev-1-hermes-workflow-5"),
        ("t_p", "Racine", "Importé depuis https://github.com/hyron-fr/hermes-workflow/issues/7\n",
         "pj-master", "blocked", None),
        ("t_l", "Enfant liée", "corps", "pj-dev", "triage", None),
        ("t_n", "Sans issue", "corps", "pj-dev", "blocked", None),
        ("t_done", "Finie", "corps", "pj-dev", "done", "pj-dev-9-hermes-workflow-9"),
    ])
    c.execute("INSERT INTO task_events(task_id,kind,payload) VALUES ('t_k','blocked',?)",
              ('{"kind":"needs_input","reason":"il faut trancher"}',))
    c.execute("INSERT INTO task_events(task_id,kind,payload) VALUES ('t_l','blocked','{{corrompu')")
    c.execute("INSERT INTO task_links VALUES ('t_p','t_l')")
    c.commit()
    c.close()
    monkeypatch.setattr(w, "KANBAN_ROOT", root)

    cards = {x["task_id"]: x for x in w.blocked_cards(cfg_of(w, tmp_path))}
    assert set(cards) == {"t_k", "t_p", "t_l"}, f"done exclue, sans-issue écartée : {cards}"
    assert cards["t_k"]["issue"] == 5, "la clé d'idempotence porte l'issue"
    assert cards["t_k"]["reason"] == "il faut trancher", "le motif du blocage est remonté"
    assert cards["t_p"]["issue"] == 7, "le corps porte l'URL d'issue"
    assert cards["t_l"]["issue"] == 7, "la remontée par les liens parents résout l'issue"
    assert cards["t_l"]["reason"] == "", "un payload corrompu ne lève pas : il rend vide"


def cfg_of(w, tmp_path):
    return w.WatchConfig(org="hyron-fr", repos=["hermes-workflow"], board=BOARD,
                         gh_bin="/usr/bin/gh", hermes_bin="/usr/bin/hermes",
                         state_dir=str(tmp_path))


def test_couverture_kanban_et_unblock_reels(w, tmp_path, monkeypatch):
    """Les effets kanban : commande construite, board explicite, ordre comment→unblock."""
    cfg = cfg_of(w, tmp_path)
    seen = []

    class R:
        returncode = 1
        stdout = ""
        stderr = "refus"

    def runner(cmd, **kw):
        seen.append(" ".join(cmd))
        return R()

    assert w.unblock_card(BOARD, TASK, "note", cfg=cfg, runner=runner) is False
    assert f"kanban --board {BOARD} comment {TASK} note" in seen[0], "le commentaire passe d'abord"
    assert f"kanban --board {BOARD} unblock {TASK}" in seen[1], "puis le déblocage"
    assert w.trace_card(BOARD, TASK, "msg", cfg=cfg, runner=runner) is False


def test_couverture_kanban_sans_binaire_refuse(w, tmp_path):
    """ERREUR — sans `hermes`, les effets kanban refusent au lieu d'appeler `None`."""
    cfg = cfg_of(w, tmp_path)
    cfg.hermes_bin = ""
    assert w.trace_card(BOARD, TASK, "m", cfg=cfg) is False
    assert w.unblock_card(BOARD, TASK, "m", cfg=cfg) is False


def test_couverture_lectures_github_en_doute(w, tmp_path):
    """ERREUR — gh absent/rc≠0/JSON invalide : `[]`/False, jamais une exception."""
    cfg = cfg_of(w, tmp_path)
    cfg.gh_bin = ""
    assert w.list_decision_children(cfg, "hermes-workflow") == []
    assert w.read_comments(cfg, "hermes-workflow", 1) == []
    assert w.gh_comment(cfg, "hermes-workflow", 1, "b") is False
    assert w.gh_close(cfg, "hermes-workflow", 1) is False
    assert w.ensure_decision_label(cfg, "hermes-workflow") is False
    assert w.create_decision_child(cfg, "hermes-workflow", 5, BOARD, TASK, "t", "r") is None
    assert w.reopen_decision_child(cfg, "hermes-workflow", 1, TASK, "r") is False

    cfg.gh_bin = "/usr/bin/gh"

    class Bad:
        returncode = 1
        stdout = "{pas du json"
        stderr = "boom"

    assert w.list_decision_children(cfg, "hermes-workflow", runner=lambda c, **k: Bad()) == []
    assert w.read_comments(cfg, "hermes-workflow", 1, runner=lambda c, **k: Bad()) == []

    class Boom:
        def __call__(self, *a, **k):
            raise OSError("réseau mort")

    assert w.list_decision_children(cfg, "hermes-workflow", runner=Boom()) == []
    assert w.read_comments(cfg, "hermes-workflow", 1, runner=Boom()) == []


def test_couverture_config_env_complet(w, tmp_path, monkeypatch):
    """La configuration complète : toutes les optionnelles lues, défauts sinon."""
    cfg = w.decision_config(env={"PJ_WATCH_ORG": "hyron-fr", "PJ_WATCH_REPOS": "a,b",
                                 "PJ_WATCH_BOARD": BOARD, "PJ_WATCH_STATE_DIR": str(tmp_path),
                                 "PJ_WATCH_GH_BIN": "/bin/gh", "PJ_WATCH_HERMES_BIN": "/bin/h"})
    assert (cfg.org, cfg.repos, cfg.board) == ("hyron-fr", ["a", "b"], BOARD)
    assert cfg.gh_bin == "/bin/gh" and cfg.hermes_bin == "/bin/h"
    w.validate_config(cfg)


def test_couverture_etat_lisible_et_illisible(w, tmp_path):
    """L'état : écrit puis relu ; un état corrompu est traité comme vide."""
    cfg = cfg_of(w, tmp_path)
    w.save_state(cfg, "hermes-workflow", {"40": {"seen": [1], "notified": []}})
    assert w.load_state(cfg, "hermes-workflow") == {"40": {"seen": [1], "notified": []}}
    w.state_path(cfg, "hermes-workflow").write_text("{corrompu")
    assert w.load_state(cfg, "hermes-workflow") == {}
    assert "hermes-workflow" in str(w.state_path(cfg, "hermes-workflow"))


def test_couverture_main_refus_et_dry_run(w, tmp_path, monkeypatch, capsys):
    """main() : rc=2 sur configuration refusée, et un dry-run qui annonce sans muter."""
    monkeypatch.delenv("PJ_WATCH_ORG", raising=False)
    assert w.main([]) == 2
    assert "refus" in capsys.readouterr().err

    monkeypatch.setenv("PJ_WATCH_ORG", "hyron-fr")
    monkeypatch.setenv("PJ_WATCH_REPOS", "hermes-workflow")
    monkeypatch.setenv("PJ_WATCH_BOARD", BOARD)
    monkeypatch.setattr(w, "blocked_cards", lambda cfg, board=None: [])
    monkeypatch.setattr(w, "list_decision_children", lambda cfg, repo, runner=None: [])
    assert w.main(["--dry-run", "--verbose"]) == 0
    out = capsys.readouterr().out
    assert "DRY-RUN" in out


def test_couverture_main_repo_unique(w, monkeypatch, capsys):
    """main() : `--repo` restreint le tick à un dépôt."""
    monkeypatch.setenv("PJ_WATCH_ORG", "hyron-fr")
    monkeypatch.setenv("PJ_WATCH_REPOS", "un,autre")
    monkeypatch.setenv("PJ_WATCH_BOARD", BOARD)
    vus = []
    monkeypatch.setattr(w, "watch_repo", lambda repo, **kw: (vus.append(repo) or
                                                             {"unblocked": [], "commented": [],
                                                              "ignored": 0, "errors": []}))
    assert w.main(["--repo", "un"]) == 0
    assert vus == ["un"]


def test_couverture_watch_repo_erreurs_de_decision(w, cfg, monkeypatch):
    """ERREUR — unbloc refusé et cible absente sont rapportés dans `errors`."""
    _patch_status(w, monkeypatch)
    run = FakeProd(children=[_child()], comments=[_comment()], kanban_rc=1)
    st = w.watch_repo("hermes-workflow", cfg=cfg, runner=run)
    assert st["errors"] and st["errors"][0]["why"] == "unblock refusé"

    # Enfant sans ligne canonique ⇒ AUCUNE carte liée : `pj_decision` rend `comment`
    # (COMMENT_NO_CARD, conforme au design) — donc ni déblocage, ni succès inventé,
    # et la décision est comptée comme tracée.
    # Commentaire NEUF (id distinct) : l'état inter-ticks a déjà consommé le
    # précédent — réutiliser le même id testerait la dédup, pas le cas visé.
    run2 = FakeProd(children=[_child(body="aucune ligne ici\n")], comments=[_comment(cid=999)])
    monkeypatch.setattr(w, "card_status", lambda b, t, cfg: "blocked")
    st2 = w.watch_repo("hermes-workflow", cfg=cfg, runner=run2)
    assert st2["unblocked"] == [] and run2.kanban_calls("unblock") == []
    assert st2["commented"], "une décision sans cible est comptée, jamais silencieuse"


def test_couverture_discord_et_notified(w, cfg, monkeypatch):
    """Le post Discord est déclenché sur un déblocage effectif, une seule fois."""
    _patch_status(w, monkeypatch)
    posts = []
    # second tick : la décision est déjà notifiée ⇒ aucun second post (anti-reboucle)
    run = FakeProd(children=[_child()], comments=[_comment(cid=930)])
    st = w.watch_repo("hermes-workflow", cfg=cfg, runner=run,
                      post_discord=lambda b, t, i, c: posts.append((b, t, i, c)))
    assert len(posts) == 1 and posts[0][1] == TASK
    run2 = FakeProd(children=[_child()], comments=[_comment(cid=930)])
    st2 = w.watch_repo("hermes-workflow", cfg=cfg, runner=run2,
                       post_discord=lambda *a: posts.append(a))
    assert st2["unblocked"] == [] and len(posts) == 1, "l'état inter-ticks coupe la re-boucle"


def test_couverture_trace_dune_decision_sans_effet(w, cfg, monkeypatch):
    """L'effet `comment` est TRACÉ sur la carte (jamais silencieux), sans notifier."""
    _patch_status(w, monkeypatch, status="running")
    run = FakeProd(children=[_child()], comments=[_comment(cid=940)])
    st = w.watch_repo("hermes-workflow", cfg=cfg, runner=run)
    assert st["commented"] and run.kanban_calls("comment")
    assert not run.kanban_calls("unblock")


def test_couverture_main_repo_sans_org_mais_var_presente(w, tmp_path, monkeypatch, capsys):
    """ERREUR — org présente mais repos vide ⇒ refus nommé (aucun tick fantôme)."""
    monkeypatch.setenv("PJ_WATCH_ORG", "hyron-fr")
    monkeypatch.setenv("PJ_WATCH_REPOS", "   ")
    assert w.main([]) == 2
    assert "REPOS" in capsys.readouterr().err


def test_production_dry_run_ne_cree_rien(w, cfg, monkeypatch):
    """LIMITE — `--dry-run` n'écrit NI carte NI issue : il annonce ce qu'il ferait.

    Une production non gardée ferait du dry-run un mode destructeur — l'inverse de
    sa promesse : il créerait de vraies issues GitHub en prétendant « ne rien faire ».
    """
    cards = [{"board": BOARD, "task_id": TASK, "title": "t", "issue": PARENT, "reason": "r"}]
    monkeypatch.setattr(w, "blocked_cards", lambda cfg, board=None: cards)
    run = FakeProd(children=[], comments=[], create_out="")
    st = w.watch_repo("hermes-workflow", cfg=cfg, dry=True, runner=run)
    assert run.create_calls() == [], "le dry-run ne crée AUCUNE issue"
    assert run.reopen_calls() == [], "le dry-run ne rouvre AUCUNE issue"
    assert run.gh_comment_calls() == [], "le dry-run ne commente AUCUNE issue"
    assert st["children"] == [{"task": TASK, "child": None, "effect": "would_create"}]

    # une enfant OUVERTE qui attend déjà : le dry-run le DIT, et n'annonce rien à faire
    run2 = FakeProd(children=[_child(body=f"carte: {BOARD}/{TASK}\n")], comments=[])
    st2 = w.watch_repo("hermes-workflow", cfg=cfg, dry=True, runner=run2)
    assert run2.reopen_calls() == []
    assert st2["children"] == [{"task": TASK, "child": CHILD, "effect": "waiting"}]

    # une enfant FERMÉE avec la carte toujours bloquée : il ANNONCE la réouverture
    run3 = FakeProd(children=[_child(body=f"carte: {BOARD}/{TASK}\n", state="CLOSED")],
                    comments=[])
    st3 = w.watch_repo("hermes-workflow", cfg=cfg, dry=True, runner=run3)
    assert run3.reopen_calls() == [], "le dry-run ne rouvre rien"
    assert st3["children"] == [{"task": TASK, "child": CHILD, "effect": "would_reopen"}]

# ==================================== idempotence de la PRODUCTION (régressions) =====
# Bug MESURÉ en production : le premier déploiement repostait un marqueur de re-blocage
# à CHAQUE tick (4 doublons en 4 minutes sur #11/#12/#13) parce qu'il rouvrait une
# enfant déjà OUVERTE. La clé est l'ÉTAT DE L'ENFANT (créée / ouverte / fermée), lu
# côté GitHub — une seule source de vérité, partagée par tous les ticks.

def _cards(task=TASK):
    return [{"board": BOARD, "task_id": task, "title": "t", "issue": PARENT, "reason": "r"}]


def test_idem_enfant_ouverte_ne_se_signale_pas_deux_fois(w, cfg, monkeypatch):
    """LIMITE — enfant OUVERTE qui attend sa décision : le tick ne poste RIEN.

    C'est la régression exacte observée en production. Elle est reprise par le
    modèle : une enfant ouverte n'est pas un objet à signaler, c'est l'état normal
    jusqu'à ce que l'humain réponde.
    """
    monkeypatch.setattr(w, "blocked_cards", lambda cfg, board=None: _cards())
    open_child = _child(body=f"carte: {BOARD}/{TASK}\n")          # OPEN
    run = FakeProd(children=[open_child])
    st = w.watch_repo("hermes-workflow", cfg=cfg, runner=run)
    assert st["children"] == [], "rien à signaler : l'enfant attend déjà"
    assert run.reopen_calls() == [] and run.gh_comment_calls() == []
    assert run.create_calls() == []


def test_idem_aucun_marqueur_poste_deux_ticks_de_suite(w, cfg, monkeypatch):
    """LIMITE — deux ticks consécutifs, enfant ouverte : aucun marqueur, jamais deux."""
    monkeypatch.setattr(w, "blocked_cards", lambda cfg, board=None: _cards())
    for i in (1, 2):
        run = FakeProd(children=[_child(body=f"carte: {BOARD}/{TASK}\n")])
        st = w.watch_repo("hermes-workflow", cfg=cfg, runner=run)
        assert run.gh_comment_calls() == [], f"tick {i} : aucun marqueur"
        assert st["children"] == []


def test_idem_enfant_fermee_est_rouverte_une_fois(w, cfg, monkeypatch):
    """LIMITE — enfant FERMÉE (décision consommée) + carte bloquée ⇒ rouverte, 1 seule fois."""
    monkeypatch.setattr(w, "blocked_cards", lambda cfg, board=None: _cards())
    closed_child = _child(body=f"carte: {BOARD}/{TASK}\n", state="CLOSED")
    run = FakeProd(children=[closed_child])
    st = w.watch_repo("hermes-workflow", cfg=cfg, runner=run)
    assert [c["effect"] for c in st["children"]] == ["reopened"]
    assert len(run.reopen_calls()) == 1
    assert len(run.gh_comment_calls()) == 1, "le marqueur est posté une seule fois"
    assert run.create_calls() == [], "jamais de doublon d'issue"


def test_idem_lenfant_cree_est_reconnu_au_tick_suivant(w, cfg, monkeypatch):
    """LIMITE — après création, le tick suivant lit l'enfant OUVERTE et se tait.

    La boucle complète : premier tick `created`, second tick muet — c'est ce qui
    rend l'idempotence vraie entre deux process distincts (le cron ne garde rien
    en mémoire).
    """
    monkeypatch.setattr(w, "blocked_cards", lambda cfg, board=None: _cards())
    run1 = FakeProd(children=[], create_out=f"https://github.com/hyron-fr/hermes-workflow/issues/{CHILD}\n")
    st1 = w.watch_repo("hermes-workflow", cfg=cfg, runner=run1)
    assert [c["effect"] for c in st1["children"]] == ["created"]
    run2 = FakeProd(children=[_child(body=f"carte: {BOARD}/{TASK}\n")])   # devenue ouverte
    st2 = w.watch_repo("hermes-workflow", cfg=cfg, runner=run2)
    assert st2["children"] == [], "le tick suivant constate et se tait"
    assert run2.gh_comment_calls() == []


def test_idem_echec_de_creation_est_rapporte_et_reaessaye(w, cfg, monkeypatch):
    """ERREUR — un échec de création est rapporté, et le tick suivant réessaie."""
    monkeypatch.setattr(w, "blocked_cards", lambda cfg, board=None: _cards())
    run = FakeProd(children=[], create_rc=1)
    st = w.watch_repo("hermes-workflow", cfg=cfg, runner=run)
    assert st["errors"] and st["children"] == []
    run2 = FakeProd(children=[], create_out="https://github.com/hyron-fr/hermes-workflow/issues/9\n")
    st2 = w.watch_repo("hermes-workflow", cfg=cfg, runner=run2)
    assert [c["effect"] for c in st2["children"]] == ["created"], "il réessaie et réussit"


def test_idem_enfant_non_rattachee_reste_sans_parent(w, cfg):
    """ERREUR — un enfant sans `parent` lisible n'invente pas de ticket."""
    assert w._parent_of({"number": 1}) is None
    assert w._parent_of({"number": 1, "parent": {"number": 5}}) == 5
