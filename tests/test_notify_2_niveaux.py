"""RED — notification 2 niveaux d'une décision ``/ok`` (issue #5, slice 5 `notify-2-niveaux`).

Ce banc est écrit AVANT le code : il gèle l'API de l'émetteur (contrat
``contrat-notify-5``, publié sur la carte racine ``t_b0c76049``) pour que la carte
sœur ``slice 5 — notify-2-niveaux — dev (GREEN)`` puisse l'implémenter.

CONTRAT — module versionné ``pipeline/pj_notify.py``
----------------------------------------------------

1. ``decision_key(decision: dict, ctx: dict) -> str``

   Clé de dédup d'une décision. Fonction PURE et DÉTERMINISTE du couple
   (carte, id du commentaire ``/ok``) — **jamais** l'horloge, jamais l'aléa.
   Le risque ratifié est une boucle de notifications ; la dédup doit donc porter
   sur la décision, jamais sur le tick.

2. ``notify_decision(decision: dict, ctx: dict, effects: dict) -> dict``

   Porte les DEUX notifications d'une décision **déjà appliquée**. Ne lève
   JAMAIS : la décision est acquise, un échec de notification ne la remet pas en
   cause — et n'est jamais silencieux (tracé sur la carte).

   ``decision`` : la sortie de ``pj_decision.decision_from_comment``
       (``{"effect", "task_id", "board", "note", "acted"}``). Seul
       ``effect == "unblock"`` notifie : ``comment``/``ignore`` n'ont débloqué
       aucune carte, ils n'émettent rien (``skipped``).
   ``ctx`` :
       ``{"card": {"task_id", "board", "title"},
          "child_issue": {"number": N},
          "parent_issue": {"number": M} | M | None,
          "decision_comment": {"id": CID, "body": "/ok", "url": ...},
          "notified": set()}``
       ``notified`` est LU puis MIS À JOUR par l'émetteur (dédup inter-ticks,
       l'état survit au tick suivant). La forme d'un parent est celle que le pont
       lit déjà (``_parent_number`` : dict ``{"number": M}`` ou entier).
   ``effects`` :
       ``{"comment": fn(issue: int, body: str) -> bool,   # False = échec
          "close":   fn(issue: int) -> bool,
          "trace":   fn(task_id: str, message: str) -> None}``
       Injectés : ce banc ne touche ni réseau, ni GitHub, ni horloge.

   Sortie :
       ``{"decision_key", "skipped", "child_notified", "child_closed",
          "parent_notified", "parent_issue", "errors", "traced"}``
       ``errors = [{"step": "child_notify"|"child_close"|"parent",
                    "issue": int|None, "reason": str}]``

   ORDRE : l'enfant est NOTIFIÉ avant d'être FERMÉ. Le parent n'est JAMAIS fermé
   (une décision de carte ne clôt pas le ticket). Les seuls fils touchés sont
   ceux du contexte : l'enfant de la décision et son parent.

Scénarios de la carte (Gherkin) : nominal (les deux côtés), limite (deux
décisions dans le même tick, aucun doublon), erreur (fil parent indisponible /
introuvable : la décision reste acquise, l'échec est tracé).
"""
import importlib.util
import os
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]

# --------------------------------------------------------------------------
# CONTRAT-NOTIFY-5 — chemins et formes gelés pour la carte sœur `dev`
# --------------------------------------------------------------------------
# `PJ_NOTIFY_COPY` permet de rejouer ce banc contre une AUTRE copie de l'émetteur
# (mutation, copie jetable), sans toucher à l'arbre partagé. Même mécanisme que
# `PJ_BRIDGE_COPY` du banc voisin (`test_decision_humaine.py`), pour la même
# raison : « tests verts » ≠ « la copie exécutée est réparée ».
_NOTIFY_ENV = os.environ.get("PJ_NOTIFY_COPY", "").strip()
NOTIFY_MODULE = Path(_NOTIFY_ENV).expanduser() if _NOTIFY_ENV \
    else REPO / "pipeline" / "pj_notify.py"
DECISION_MODULE = REPO / "pipeline" / "pj_decision.py"

BOARD = "pj-hermes-workflow"
TASK_A = "t_aaa"
TASK_B = "t_bbb"
ENFANT_A = 40       # une décision = une issue enfant
ENFANT_B = 41       # seconde enfant du MÊME ticket (décidée dans le même tick)
PARENT = 5          # le ticket — notifié, jamais fermé


def _load(path: Path, name: str):
    """Charge un module versionné, ou échoue en le NOMMANT (jamais un import muet)."""
    if not path.exists():
        pytest.fail(
            f"module versionné absent : {path} — le RED ne peut pas porter sur du "
            f"code non versionné. Le contrat-notify-5 fixe ce chemin."
        )
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def nt():
    os.environ.setdefault("KANBAN_BOARD", BOARD)
    return _load(NOTIFY_MODULE, "pj_notify_issue5")


@pytest.fixture(scope="module")
def dm():
    os.environ.setdefault("KANBAN_BOARD", BOARD)
    return _load(DECISION_MODULE, "pj_decision_issue5")


# --------------------------------------------------------------------------
# Effets INJECTÉS — aucun réseau, aucune horloge, aucune dépendance au dépôt
# --------------------------------------------------------------------------
class _Fx:
    """Journal d'effets : enregistre l'ordre, et peut faire échouer un fil donné."""

    def __init__(self, fail_comment=(), fail_close=()):
        self.appels = []                 # [(kind, issue, body)] dans l'ORDRE réel
        self.traces = []                 # [(task_id, message)]
        self.fail_comment = set(fail_comment)
        self.fail_close = set(fail_close)

    def comment(self, issue, body):
        self.appels.append(("comment", issue, body))
        return issue not in self.fail_comment

    def close(self, issue):
        self.appels.append(("close", issue, ""))
        return issue not in self.fail_close

    def trace(self, task_id, message):
        self.traces.append((task_id, message))

    def as_dict(self):
        return {"comment": self.comment, "close": self.close, "trace": self.trace}

    def issues_touchees(self):
        return {i for _, i, _ in self.appels}

    def corps(self, kind, issue):
        return [b for k, i, b in self.appels if k == kind and i == issue]


class _FxQuiLeve(_Fx):
    """Effets qui LÈVENT : la décision est acquise, l'émetteur ne doit pas tomber."""

    def comment(self, issue, body):
        self.appels.append(("comment", issue, body))
        raise RuntimeError("fil indisponible")

    def close(self, issue):
        self.appels.append(("close", issue, ""))
        raise RuntimeError("fil indisponible")

    def trace(self, task_id, message):
        self.traces.append((task_id, message))
        raise RuntimeError("carte indisponible")


def _comment(cid=900, enfant=ENFANT_A):
    return {"id": cid, "body": "/ok",
            "url": f"https://github.com/hyron-fr/hermes-workflow/issues/{enfant}"
                   f"#issuecomment-{cid}"}


def _ctx(task=TASK_A, enfant=ENFANT_A, parent=PARENT, cid=900, notified=None):
    return {
        "card": {"task_id": task, "board": BOARD, "title": f"carte {task}"},
        "child_issue": {"number": enfant},
        "parent_issue": {"number": parent} if parent is not None else None,
        "decision_comment": _comment(cid, enfant),
        "notified": set() if notified is None else notified,
    }


def _decision(task=TASK_A, effect="unblock"):
    return {"effect": effect, "task_id": task, "board": BOARD,
            "note": f"décision /ok : débloquer la carte", "acted": effect != "ignore"}


# ==========================================================================
# 0. Le module versionné existe — l'échec le plus net (le mur mesuré)
# ==========================================================================
def test_garde_fou_le_module_notify_est_versionne():
    """GARDE-FOU structurel — l'émetteur doit être un module VERSIONNÉ.

    Sans lui, le RED porterait sur du code non versionné (règle héritée de la
    slice 4) : le banc serait vert sur un dépôt qui n'a rien livré.
    """
    assert NOTIFY_MODULE.exists(), (
        f"émetteur absent : {NOTIFY_MODULE} — l'émetteur de notification doit être un "
        f"module VERSIONNÉ (contrat-notify-5), sinon les 3 scénarios ne sont pas jugeables."
    )


# ==========================================================================
# A. NOMINAL — la décision est visible des deux côtés
# ==========================================================================
def test_nominal_l_enfant_est_notifie_puis_ferme(nt):
    """NOMINAL — « l'issue enfant reçoit la notification puis est fermée ».

    L'ORDRE est contractuel : fermer avant de notifier ferait disparaître la
    trace de la décision pour l'humain qui a répondu.
    """
    fx = _Fx()
    r = nt.notify_decision(_decision(), _ctx(), fx.as_dict())
    assert r["child_notified"] is True
    assert r["child_closed"] is True
    kinds = [k for k, i, _ in fx.appels if i == ENFANT_A]
    assert kinds == ["comment", "close"], (
        f"l'enfant doit être NOTIFIÉ puis FERMÉ, mesuré : {kinds}"
    )


def test_nominal_l_enfant_recoit_la_decision_enregistree(nt):
    """NOMINAL — le message porté par l'enfant dit que la décision est enregistrée."""
    fx = _Fx()
    nt.notify_decision(_decision(), _ctx(), fx.as_dict())
    corps = fx.corps("comment", ENFANT_A)
    assert corps, "aucune notification sur l'issue enfant"
    assert "décision enregistrée" in corps[0].lower(), corps[0][:200]


def test_nominal_le_parent_recoit_l_avancement_qui_cite_la_carte(nt):
    """NOMINAL — « l'issue parent reçoit une notification d'avancement citant la carte »."""
    fx = _Fx()
    r = nt.notify_decision(_decision(), _ctx(), fx.as_dict())
    assert r["parent_notified"] is True
    corps = fx.corps("comment", PARENT)
    assert corps, "aucune notification d'avancement sur le parent"
    assert TASK_A in corps[0], f"la carte débloquée doit être citée : {corps[0][:200]}"


def test_nominal_le_parent_renvoie_a_l_ancre_exacte_du_ok(nt):
    """NOMINAL — la notification d'avancement renvoie au commentaire /ok (son ancre)."""
    fx = _Fx()
    nt.notify_decision(_decision(), _ctx(cid=900), fx.as_dict())
    corps = fx.corps("comment", PARENT)[0]
    assert "#issuecomment-900" in corps, (
        f"le parent doit pointer l'ancre EXACTE du /ok : {corps[:300]}"
    )


def test_nominal_le_parent_n_est_jamais_ferme(nt):
    """GARDE-FOU du nominal — une décision de carte ne clôt pas le ticket."""
    fx = _Fx()
    nt.notify_decision(_decision(), _ctx(), fx.as_dict())
    assert not fx.corps("close", PARENT), "le ticket parent ne se ferme pas sur une décision"


def test_nominal_une_vraie_decision_du_core_pur_declenche_les_deux_notifications(nt, dm):
    """NOMINAL/intégration — la sortie RÉELLE de ``pj_decision`` pilote l'émetteur.

    Les deux slices doivent s'emboîter sans adaptation : c'est le contrat d'entrée
    de la slice 5 (mesure : aucun appelant de production n'existe encore).
    """
    ctx_decision = {
        "issue": {"number": ENFANT_A, "state": "OPEN", "parent": {"number": PARENT}},
        "cards": [{"task_id": TASK_A, "board": BOARD, "status": "blocked",
                   "issue": ENFANT_A}],
        "seen_comment_ids": set(),
    }
    d = dm.decision_from_comment(ctx_decision, {"id": 900, "body": "/ok"})
    assert d["effect"] == "unblock" and d["task_id"] == TASK_A

    fx = _Fx()
    r = nt.notify_decision(d, _ctx(), fx.as_dict())
    assert (r["child_notified"], r["child_closed"], r["parent_notified"]) == (True, True, True)


# ==========================================================================
# B. LIMITE — deux décisions dans le même tick / aucun doublon
# ==========================================================================
def test_limite_deux_decisions_du_meme_tick_une_notification_parent_par_carte(nt):
    """LIMITE — le parent reçoit UNE notification par carte débloquée, et pas une seule."""
    notified = set()
    fx = _Fx()
    rA = nt.notify_decision(_decision(TASK_A), _ctx(TASK_A, ENFANT_A, PARENT, 900, notified),
                            fx.as_dict())
    rB = nt.notify_decision(_decision(TASK_B), _ctx(TASK_B, ENFANT_B, PARENT, 901, notified),
                            fx.as_dict())
    assert (rA["parent_notified"], rB["parent_notified"]) == (True, True)
    parents = fx.corps("comment", PARENT)
    assert len(parents) == 2, f"une notification par carte débloquée, mesuré : {len(parents)}"
    assert TASK_A in parents[0] and TASK_B in parents[1], parents
    assert parents[0] != parents[1], "les deux notifications ne peuvent pas être identiques"
    assert sorted(fx.corps("close", ENFANT_A) + fx.corps("close", ENFANT_B)) == ["", ""]


def test_limite_aucune_notification_deux_fois_pour_la_meme_decision(nt):
    """LIMITE — rejouer la MÊME décision (même commentaire /ok) ne réémet rien.

    C'est la garde anti-boucle ratifiée : elle porte sur l'id du commentaire, et
    l'état de dédup survit au tick (``ctx['notified']``).
    """
    notified = set()
    fx = _Fx()
    r1 = nt.notify_decision(_decision(), _ctx(cid=900, notified=notified), fx.as_dict())
    apres_1 = len(fx.appels)
    r2 = nt.notify_decision(_decision(), _ctx(cid=900, notified=notified), fx.as_dict())
    assert r1["skipped"] is False
    assert r2["skipped"] is True, "la même décision ne notifie qu'une fois"
    assert len(fx.appels) == apres_1, f"aucun effet réémis, mesuré : {fx.appels[apres_1:]}"
    assert r2["child_notified"] is False and r2["parent_notified"] is False
    assert r2["traced"] is False, "un rejeu n'est pas un échec à tracer"


def test_limite_un_reblocage_est_une_nouvelle_decision(nt):
    """LIMITE — la dédup porte sur LA décision, pas sur la carte.

    Un re-blocage produit un NOUVEAU commentaire ``/ok`` : la nouvelle décision
    doit être notifiée (sinon la 2ᵉ itération devient invisible) et son ancre est
    celle du nouveau commentaire.
    """
    notified = set()
    fx = _Fx()
    nt.notify_decision(_decision(), _ctx(cid=900, notified=notified), fx.as_dict())
    r2 = nt.notify_decision(_decision(), _ctx(cid=901, notified=notified), fx.as_dict())
    assert r2["skipped"] is False, "une nouvelle décision ne peut pas être dédupliquée"
    parents = fx.corps("comment", PARENT)
    assert len(parents) == 2
    assert "#issuecomment-901" in parents[1]
    assert "#issuecomment-900" not in parents[1], "l'ancre doit être celle du nouveau /ok"


def test_limite_aucune_ecriture_dans_le_fil_d_un_autre_ticket(nt):
    """LIMITE — l'émetteur n'écrit QUE dans les fils du contexte (enfant + parent)."""
    fx = _Fx()
    nt.notify_decision(_decision(), _ctx(), fx.as_dict())
    assert fx.issues_touchees() == {ENFANT_A, PARENT}, (
        f"fils touchés : {sorted(fx.issues_touchees())} — jamais un autre ticket"
    )


def test_limite_la_cle_de_dedup_porte_sur_la_decision_pas_sur_l_horloge(nt):
    """LIMITE — la clé est déterministe et discriminante (jamais un horodatage)."""
    k1 = nt.decision_key(_decision(), _ctx(cid=900))
    k2 = nt.decision_key(_decision(), _ctx(cid=900))
    assert k1 == k2, "la clé doit être une fonction pure de (carte, commentaire)"
    assert str(900) in k1, f"la clé porte l'id du commentaire /ok : {k1!r}"
    assert k1 != nt.decision_key(_decision(), _ctx(cid=901)), "deux décisions ⇒ deux clés"
    assert k1 != nt.decision_key(_decision(TASK_B), _ctx(TASK_B, ENFANT_B, PARENT, 900)), \
        "deux cartes ⇒ deux clés"
    assert k1 != nt.decision_key(_decision(), _ctx(TASK_A, ENFANT_B, PARENT, 900)), \
        "deux issues enfant ⇒ deux clés"


def test_limite_le_parent_peut_etre_passe_comme_entier(nt):
    """LIMITE — ``gh`` renvoie ``parent`` en dict, le pont peut passer l'entier.

    La forme tolérante est celle déjà écrite par le pont (``_parent_number``) : les
    deux doivent notifier le parent, aucune ne doit être silencieusement perdue.
    """
    ctx_dict = _ctx()
    ctx_dict["parent_issue"] = {"number": PARENT}
    ctx_int = _ctx()
    ctx_int["parent_issue"] = PARENT          # forme déjà tolérée par le pont
    fx1, fx2 = _Fx(), _Fx()
    r1 = nt.notify_decision(_decision(), ctx_dict, fx1.as_dict())
    r2 = nt.notify_decision(_decision(), ctx_int, fx2.as_dict())
    assert (r1["parent_notified"], r2["parent_notified"]) == (True, True), \
        f"dict -> {r1['parent_notified']}, int -> {r2['parent_notified']}"
    assert r1["parent_issue"] == PARENT and r2["parent_issue"] == PARENT
    assert not r1["errors"] and not r2["errors"]


# ==========================================================================
# C. ERREUR — la décision acquise le reste, et l'échec n'est pas muet
# ==========================================================================
def test_erreur_parent_introuvable_la_decision_reste_acquise_et_est_tracee(nt):
    """ERREUR — « un fil parent introuvable » : la décision est appliquée quand même.

    L'enfant est notifié et fermé comme en nominal ; l'absence de parent est
    TRACÉE sur la carte (``errors`` nomme l'étape et ``trace`` a été appelé).
    """
    fx = _Fx()
    r = nt.notify_decision(_decision(), _ctx(parent=None), fx.as_dict())
    assert r["child_notified"] is True and r["child_closed"] is True
    assert r["parent_notified"] is False
    err = [e for e in r["errors"] if e["step"] == "parent"]
    assert err, f"le fil parent introuvable doit être rapporté : {r['errors']}"
    assert r["traced"] is True, "jamais silencieux"
    assert fx.traces and fx.traces[0][0] == TASK_A
    assert fx.traces[0][1].strip(), "le tracé ne peut pas être vide"


def test_erreur_parent_indisponible_l_echec_est_trace_jamais_silencieux(nt):
    """ERREUR — le commentaire parent échoue (rend ``False``) : rien n'est avalé."""
    fx = _Fx(fail_comment={PARENT})
    r = nt.notify_decision(_decision(), _ctx(), fx.as_dict())
    assert r["child_notified"] is True and r["child_closed"] is True, \
        "la décision reste acquise, enfant fermée comme en nominal"
    assert r["parent_notified"] is False
    err = [e for e in r["errors"] if e["step"] == "parent"]
    assert err and err[0]["issue"] == PARENT, r["errors"]
    assert r["traced"] is True


def test_erreur_le_tick_ne_leve_jamais_meme_quand_tout_echoue(nt):
    """ERREUR — effets qui LÈVENT : l'émetteur retourne un verdict, il ne tombe pas.

    Un échec de notification ne doit jamais emporter le tick (le déblocage et la
    fermeture de l'enfant sont déjà acquis).
    """
    fx = _FxQuiLeve()
    r = nt.notify_decision(_decision(), _ctx(), fx.as_dict())
    assert isinstance(r, dict), "l'émetteur doit retourner un verdict, pas lever"
    assert r["errors"], "les échecs doivent être rapportés"
    assert r["child_notified"] is False and r["child_closed"] is False


def test_erreur_enfant_indisponible_l_echec_est_trace(nt):
    """ERREUR — la notification de l'enfant échoue : tracée, jamais silencieuse."""
    fx = _Fx(fail_comment={ENFANT_A})
    r = nt.notify_decision(_decision(), _ctx(), fx.as_dict())
    assert [e for e in r["errors"] if e["step"] == "child_notify"], r["errors"]
    assert r["traced"] is True
    assert r["child_notified"] is False


def test_erreur_une_decision_qui_n_a_pas_debloque_n_emet_rien(nt):
    """ERREUR — ``effect == "comment"`` (carte déjà active) : aucune notification.

    Sans cette garde, un câblage qui appelle l'émetteur pour TOUTE décision
    notifierait le parent d'un déblocage qui n'a pas eu lieu.
    """
    fx = _Fx()
    r = nt.notify_decision(_decision(effect="comment"), _ctx(), fx.as_dict())
    assert fx.appels == [], f"aucun effet attendu, mesuré : {fx.appels}"
    assert fx.traces == [], "rien à tracer : rien n'a échoué"
    assert r["skipped"] is True
    assert r["child_notified"] is False and r["parent_notified"] is False


def test_erreur_une_decision_ignoree_n_emet_rien(nt):
    """ERREUR — ``effect == "ignore"`` (jeton périmé, anti-rejeu) : rien non plus.

    Le chemin le plus fréquent d'un tick est un ``ignore`` (corps sans jeton en
    tête, commentaire déjà consommé). S'il notifiait, chaque tick bavarderait dans
    le fil du ticket.
    """
    fx = _Fx()
    r = nt.notify_decision(_decision(effect="ignore"), _ctx(), fx.as_dict())
    assert fx.appels == [], f"aucun effet attendu, mesuré : {fx.appels}"
    assert r["skipped"] is True
    assert r["traced"] is False


def test_erreur_l_emetteur_ne_lit_aucune_horloge(nt, monkeypatch):
    """ERREUR — déterminisme : l'émetteur travaille horloge poisonée.

    Le risque ratifié est une dédup par l'horloge (boucle de notifications). Une
    implémentation qui lit ``time`` tombe ici, en pleine exécution.
    """
    import time as _time

    def _boom(*a, **k):
        raise AssertionError("l'émetteur a lu l'horloge : la dédup doit porter sur la décision")

    for nom in ("time", "monotonic", "perf_counter", "localtime", "gmtime", "strftime"):
        monkeypatch.setattr(_time, nom, _boom, raising=False)

    notified = set()
    fx = _Fx()
    r1 = nt.notify_decision(_decision(), _ctx(cid=900, notified=notified), fx.as_dict())
    r2 = nt.notify_decision(_decision(), _ctx(cid=900, notified=notified), fx.as_dict())
    assert (r1["child_notified"], r1["child_closed"], r1["parent_notified"]) == (True, True, True)
    assert r2["skipped"] is True, "la dédup doit tenir sans horloge"
    assert nt.decision_key(_decision(), _ctx(cid=900)) == \
        nt.decision_key(_decision(), _ctx(cid=900))


# ==========================================================================
# D. GARDE-FOUS — pas de réseau, pas de LLM, pas d'effet hors injection
# ==========================================================================
_FORBIDDEN = ("socket", "requests", "urllib", "http", "subprocess", "sqlite3",
              "openai", "anthropic", "litellm")


def test_garde_fou_l_emetteur_ne_charge_aucune_brique_reseau_ni_llm(nt):
    """GARDE-FOU hexagonal — les effets sont INJECTÉS, rien n'est chargé en dur."""
    for name in _FORBIDDEN:
        assert not hasattr(nt, name), (
            f"{name} ne doit pas être importé par l'émetteur : les effets passent par "
            f"`effects` (déterminisme + banc hors ligne)"
        )


def test_garde_fou_l_emetteur_n_importe_rien_pendant_l_execution(nt):
    """GARDE-FOU — mesuré par EXÉCUTION (une lecture de noms ne suffit pas).

    Un import résolu dynamiquement (`__import__("socket")`) doit être attrapé :
    c'est la leçon mesurée de la slice 4, appliquée ici.
    """
    fx = _Fx()
    journal, r = _harness(lambda: nt.notify_decision(_decision(), _ctx(), fx.as_dict()))
    assert not journal, f"résolution de module interdite pendant la décision : {journal}"
    assert r["parent_notified"] is True


def test_garde_fou_le_sondage_import_mord_sur_un_sujet_impur():
    """CONTRÔLE NÉGATIF — sans lui, le garde-fou ci-dessus est un toujours-vert déguisé."""
    journal, _ = _harness(lambda: __import__("socket").gethostname())
    assert journal, "le sondage n'a rien vu : il ne prouve rien"
    assert any("socket" in e for e in journal), journal


def _harness(fn):
    """Exécute ``fn`` en REFUSANT toute résolution de brique réseau/LLM.

    Trois surfaces, car aucune ne suffit seule : ``builtins.__import__`` (ce que
    `import x` appelle réellement, y compris pour un module déjà chargé) et
    ``sys.meta_path`` (résolution littérale). Retourne (journal, résultat).
    """
    import builtins
    import importlib.abc

    journal = []

    def consigne(name):
        racine = str(name).split(".")[0]
        if racine in _FORBIDDEN:
            journal.append(str(name))

    class _Probe(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if str(fullname).split(".")[0] in _FORBIDDEN:
                consigne(fullname)
                raise ImportError(f"émetteur impur : import de {fullname} interdit")
            return None

    probe = _Probe()
    vrai_import = builtins.__import__

    def garde(name, *a, **k):
        consigne(name)
        if str(name).split(".")[0] in _FORBIDDEN:
            raise ImportError(f"émetteur impur : import de {name} interdit")
        return vrai_import(name, *a, **k)

    sys.meta_path.insert(0, probe)
    builtins.__import__ = garde
    try:
        result = fn()
    except AssertionError:
        raise
    except Exception as exc:      # un import interdit : c'est le signal recherché
        journal.append(f"exception:{type(exc).__name__}")
        result = {"child_notified": False, "child_closed": False,
                  "parent_notified": False, "errors": [], "traced": False,
                  "skipped": False}
    finally:
        sys.meta_path.remove(probe)
        builtins.__import__ = vrai_import
    return journal, result
