"""RED — écrivain d'état du titre #19, slice 4 `keeper-ecrivain-unique-titre`.

Ce banc gèle le **contrat d'interface** de la nouvelle responsabilité du keeper : le keeper
devient l'**écrivain UNIQUE** du nom de thread, et **coalesce** ses renommages (Discord
plafonne à ~3 `PATCH name` par fenêtre : la 3ᵉ rend 429, `retry_after` ≈ 600 s).

Périmètre gelé par `specs/19/slices.json` (slug `keeper-ecrivain-unique-titre`) :

    pipeline/pj_room_keeper.py            -> carte d'état + coalescence + écrivain
    tests/test_pj_room_keeper.py          -> le cycle du keeper (extensions niveau cycle)
    tests/test_thread_state_writer.py     -> ce banc (pj-test)

Ce que le banc juge (3 natures : 1 nominal + 1 limite + 1 erreur minimum) :

  NOMINAL : le STATUT de la carte choisit l'icône (via la table arbitrée de la slice 3) ;
            au plus UN renommage par fil et par fenêtre, même sur plusieurs cycles ;
            la priorité `⚠ > 🛑 > ⚙️ > 🎬` départage deux états d'un même fil ;
            le livre de coalescence est PERSISTANT (round-trip fichier) ;
            une carte en attente humaine (`block_kind`) porte l'état bloqué.
  LIMITE  : deux états contradictoires dans la même fenêtre -> renommage DIFFÉRÉ et état
            mémorisé, qui part au cycle suivant ; deux ticks muets n'oublient pas la
            fenêtre ; un fil non résolu (absent du board) n'est JAMAIS renommé ; un nom
            vide n'est pas écrit (aucun placeholder).
  ERREUR  : un refus d'écriture (429) ne tue pas le tick, est tracé (fil + `retry_after`)
            et n'a PAS consommé la fenêtre (reprise au tick suivant) ; un adaptateur qui
            LÈVE ne tue pas le tick ; un statut de carte inconnu n'écrit aucun titre.

Contrat d'interface exécuté par ce banc (publié en `contrat-4` sur le blackboard) :

    STATES = ("startup", "in_progress", "blocked", "done")   # les 4 états de la slice 3
    TITLE_PRIORITY = ("blocked", "done", "in_progress", "startup")   # index 0 = max
    TITLE_WINDOW = 600          # secondes : ≥ 1 renommage par fil et par fenêtre

    keeper.card_title_state(card: dict) -> str | None
        "blocked"       si `status == "blocked"` OU `block_kind` ∈ {needs_input, capability}
        "done"          si `status` ∈ {done, archived}
        "in_progress"   si `status` ∈ {running, ready}
        "startup"       si `status == "todo"`
        None            sinon (aucun titre écrit : jamais d'icône inventée)

    keeper.best_title_state(states) -> str | None      # le plus prioritaire ; None si vide
    keeper.load_title_book(path=None) -> dict          # {} si absent ; ne lève jamais
    keeper.save_title_book(book, path=None) -> None    # écrit le livre (JSON)
    keeper.sync_titles(tickets, write, book, now, dry=False, window=TITLE_WINDOW) -> list[dict]
        tickets : [{"thread_id": str, "state": str, "name": str}]
        write   : adaptateur INJECTÉ `write(thread_id, name) -> dict`
                  succès ssi `result.get("ok") is True` ; un refus porte
                  `retry_after` (float) et `detail` (str).
        book    : {thread_id: {"ts": float, "state": str, "pending": str | None,
                               "failures": [ ... ]}} — muté en place, ts = date du dernier
                  SUCCÈS ; `pending` = état différé le plus prioritaire.
        retour  : un verdict par ticket, dans l'ordre :
                  {"thread_id", "action": "skip"|"defer"|"rename", "state",
                   "ok": bool | None, "retry_after": float | None, "detail": str | None}
        `sync_titles` NE LÈVE JAMAIS : un refus (ou une exception) d'écriture est tracé.

Le banc est **pur et déterministe** : `now` est injecté, l'adaptateur d'écriture est injecté,
et `sh` (sous-processus) est empoisonné — le banc n'appelle JAMAIS Discord.
"""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
KEEPER = REPO / "pipeline" / "pj_room_keeper.py"
ENGINE = REPO / "pipeline" / "engine.py"

# ---------------------------------------------------------------- vocabulaire mesuré
PROJECT = "hermes-workflow"
TICKET = 19
TITLE = "Discord thread title and description update"
STARTUP, IN_PROGRESS, BLOCKED, DONE = "startup", "in_progress", "blocked", "done"
ICONES = {
    STARTUP: "\U0001f3ac",              # 🎬 démarrage
    IN_PROGRESS: "\u2699\ufe0f",        # ⚙️ in progress
    BLOCKED: "\u26a0",                  # ⚠  bloqué
    DONE: "\U0001f6d1",                 # 🛑 terminé
}
PRIORITE = ("blocked", "done", "in_progress", "startup")   # ⚠ > 🛑 > ⚙️ > 🎬
WINDOW = 600.0                                             # 10 min


# --------------------------------------------------------------------------- outils
def _load(path, name, extra_path=()):
    """Charge un module sous test ; échoue en NOMMANT le fichier absent (jamais un vert)."""
    if not path.is_file():
        pytest.fail(f"module sous test absent : {path}")
    for p in extra_path:
        sys.path.insert(0, str(p))
    spec = importlib.util.spec_from_file_location(name, str(path))
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    try:
        spec.loader.exec_module(mod)
    finally:
        for p in extra_path:
            sys.path.remove(str(p))
    return mod


@pytest.fixture(scope="module")
def kpp():
    """Le keeper de production (`pipeline/pj_room_keeper.py`) — l'écrivain unique du titre."""
    return _load(KEEPER, "t4_keeper_under_test")


@pytest.fixture(scope="module")
def eng():
    """Le formateur pur de la slice 3 (chargé avec `pipeline/` sur sys.path)."""
    return _load(ENGINE, "t4_engine_under_test", extra_path=(REPO / "pipeline",))


def _api(mod, nom):
    """Attribut du contrat, ou échec NOMMANT l'attribut absent (jamais un AttributeError nu)."""
    if not hasattr(mod, nom):
        pytest.fail(
            f"API absente : pipeline/pj_room_keeper.py::{nom} — le contrat `contrat-4` l'exige "
            f"(le keeper devient l'écrivain unique du titre, coalescé par fenêtre)"
        )
    return getattr(mod, nom)


def _recorder(ok=True, retry_after=None, detail=""):
    """Adaptateur d'écriture injecté : enregistre les appels, rend un verdict dict."""
    calls = []

    def write(thread_id, name):
        calls.append((thread_id, name))
        return {"ok": ok, "retry_after": retry_after, "detail": detail}

    return write, calls


def _ticket(thread_id="T1", state=IN_PROGRESS, name="nom-1"):
    return {"thread_id": thread_id, "state": state, "name": name}


# ==========================================================================
# A. NOMINAL — le statut choisit l'icône, un seul renommage par fil et par fenêtre
# ==========================================================================

def test_nominal_le_statut_de_la_carte_choisit_l_etat_et_l_icone(kpp, eng):
    """NOMINAL — `card_title_state` traduit le statut, et l'icône suit la table arbitrée (slice 3)."""
    f = _api(kpp, "card_title_state")
    cas = [
        ({"id": "t", "status": "todo"}, STARTUP, ICONES[STARTUP]),
        ({"id": "t", "status": "running"}, IN_PROGRESS, ICONES[IN_PROGRESS]),
        ({"id": "t", "status": "ready"}, IN_PROGRESS, ICONES[IN_PROGRESS]),
        ({"id": "t", "status": "blocked"}, BLOCKED, ICONES[BLOCKED]),
        ({"id": "t", "status": "done"}, DONE, ICONES[DONE]),
        ({"id": "t", "status": "archived"}, DONE, ICONES[DONE]),
    ]
    for card, etat, icone in cas:
        obtenu = f(card)
        assert obtenu == etat, (
            f"statut {card.get('status')!r} -> état {obtenu!r} ; attendu {etat!r}"
        )
        nom = eng.format_title(PROJECT, TICKET, TITLE, obtenu)
        assert nom.split(" ", 1)[0] == icone, (
            f"l'état {etat!r} doit porter l'icône arbitrée {icone!r} : {nom!r}"
        )
        assert f"{PROJECT}|#{TICKET}|" in nom, f"l'identité doit rester : {nom!r}"


def test_nominal_la_carte_en_attente_humaine_porte_l_etat_bloque(kpp):
    """NOMINAL — le marqueur d'attente humaine (`block_kind`) est la SOURCE de l'état ⚠."""
    f = _api(kpp, "card_title_state")
    assert f({"status": "blocked"}) == BLOCKED, (
        "une carte `blocked` attend une décision humaine -> ⚠"
    )
    assert f({"status": "running", "block_kind": "needs_input"}) == BLOCKED, (
        "`needs_input` est un marqueur d'attente humaine -> ⚠, quel que soit le statut"
    )
    assert f({"status": "todo", "block_kind": "capability"}) == BLOCKED, (
        "`capability` (mur dur) est une attente humaine -> ⚠"
    )
    assert f({"status": "running", "block_kind": "dependency"}) == IN_PROGRESS, (
        "`dependency` n'attend PAS l'humain (elle repart seule) : pas d'état ⚠ abusif"
    )


def test_nominal_au_plus_un_renommage_par_fil_et_par_fenetre(kpp):
    """NOMINAL — deux fils, un cycle : 2 écritures ; rejouer le cycle dans la fenêtre : 0."""
    book = {}
    write, calls = _recorder()
    tix = [_ticket("T1", IN_PROGRESS, "n1"), _ticket("T2", BLOCKED, "n2")]
    out1 = _api(kpp, "sync_titles")(tix, write, book, now=1000.0)
    assert [c[0] for c in calls] == ["T1", "T2"], (
        f"chaque fil doit recevoir SON nom, une fois : {calls!r}"
    )
    assert [o["action"] for o in out1] == ["rename", "rename"], f"{out1!r}"
    out2 = _api(kpp, "sync_titles")(tix, write, book, now=1000.0 + 60.0)
    assert len(calls) == 2, (
        f"un second cycle dans la même fenêtre ne doit RIEN réécrire : {calls!r}"
    )
    assert [o["action"] for o in out2] == ["skip", "skip"], f"{out2!r}"


def test_nominal_la_priorite_arbitree_departage_les_etats_d_un_fil(kpp):
    """NOMINAL — la priorité `⚠ > 🛑 > ⚙️ > 🎬` (arbitrage t3) est respectée."""
    f = _api(kpp, "best_title_state")
    assert f([DONE, BLOCKED, IN_PROGRESS]) == BLOCKED, "⚠ gagne sur 🛑 et ⚙️"
    assert f([STARTUP, DONE, IN_PROGRESS]) == DONE, "🛑 gagne sur ⚙️ et 🎬"
    assert f({STARTUP, IN_PROGRESS}) == IN_PROGRESS, "⚙️ gagne sur 🎬"
    assert f(["startup"]) == STARTUP
    assert f([]) is None, "aucun état -> aucun titre (pas de 🎬 par défaut)"
    assert f(None) is None


def test_nominal_le_livre_de_coalescence_est_persistant(kpp, tmp_path):
    """NOMINAL — le livre survit à un redémarrage : la fenêtre n'est pas remise à zéro."""
    p = tmp_path / "titles.json"
    book = {}
    write, calls = _recorder()
    _api(kpp, "sync_titles")([_ticket("T1", IN_PROGRESS, "n1")], write, book, now=1000.0)
    _api(kpp, "save_title_book")(book, p)
    assert p.is_file(), f"le livre doit être écrit sur disque : {p}"
    relu = _api(kpp, "load_title_book")(p)
    assert isinstance(relu, dict) and "T1" in relu, f"livre relu inexploitable : {relu!r}"
    assert relu["T1"]["state"] == IN_PROGRESS
    assert float(relu["T1"]["ts"]) == 1000.0, (
        f"la date du dernier succès doit survivre : {relu['T1']!r}"
    )
    # « redémarrage » : un livre relu interdit encore le renommage dans la fenêtre.
    write2, calls2 = _recorder()
    out = _api(kpp, "sync_titles")([_ticket("T1", BLOCKED, "n2")], write2, relu, now=1100.0)
    assert calls2 == [], f"le redémarrage a oublié la fenêtre : {calls2!r}"
    assert out[0]["action"] == "defer", f"{out!r}"
    assert json.loads(p.read_text(encoding="utf-8")), "le livre doit rester un JSON lisible"


# ==========================================================================
# B. LIMITE — états contradictoires, ticks muets, fil absent, nom vide
# ==========================================================================

def test_limite_deux_etats_contradictoires_dans_la_fenetre(kpp):
    """LIMITE — renommé il y a 9 min puis carte bloquée : différé, ⚠ mémorisé, part au suivant."""
    book = {}
    write, calls = _recorder()
    _api(kpp, "sync_titles")([_ticket("T1", IN_PROGRESS, "n1")], write, book, now=1000.0)
    assert len(calls) == 1
    out = _api(kpp, "sync_titles")([_ticket("T1", BLOCKED, "n2")], write, book, now=1000.0 + 540.0)
    assert len(calls) == 1, f"9 min après, la fenêtre interdit encore l'écriture : {calls!r}"
    assert out[0]["action"] == "defer", f"{out!r}"
    assert book["T1"]["pending"] == BLOCKED, (
        f"l'état ⚠ doit être MÉMORISÉ pendant le report : {book['T1']!r}"
    )
    out2 = _api(kpp, "sync_titles")([_ticket("T1", BLOCKED, "n2")], write, book,
                                    now=1000.0 + WINDOW)
    assert len(calls) == 2 and calls[-1][1] == "n2", (
        f"au cycle suivant (fenêtre écoulée), ⚠ doit partir : {calls!r}"
    )
    assert out2[0]["action"] == "rename", f"{out2!r}"
    assert not book["T1"].get("pending"), (
        f"le report doit être soldé une fois l'état écrit : {book['T1']!r}"
    )


def test_limite_deux_ticks_muets_n_oublient_pas_la_fenetre(kpp):
    """LIMITE — deux cycles sans changement puis une transition : la fenêtre tient toujours."""
    book = {}
    write, calls = _recorder()
    _api(kpp, "sync_titles")([_ticket("T1", IN_PROGRESS, "n1")], write, book, now=1000.0)
    for t in (1200.0, 1400.0):                      # cycles muets : état inchangé
        out = _api(kpp, "sync_titles")([_ticket("T1", IN_PROGRESS, "n1")], write, book, now=t)
        assert out[0]["action"] == "skip", f"tick muet @{t} -> {out!r}"
    assert len(calls) == 1, f"les ticks muets ne doivent rien écrire : {calls!r}"
    # 3ᵉ cycle : une transition, mais la fenêtre court encore (fin à 1600).
    out = _api(kpp, "sync_titles")([_ticket("T1", BLOCKED, "n2")], write, book, now=1500.0)
    assert out[0]["action"] == "defer" and len(calls) == 1, f"{out!r} / {calls!r}"
    out = _api(kpp, "sync_titles")([_ticket("T1", BLOCKED, "n2")], write, book, now=1600.0)
    assert out[0]["action"] == "rename" and calls[-1][1] == "n2", f"{out!r} / {calls!r}"


def test_limite_un_fil_non_resolu_n_est_jamais_renomme(kpp):
    """LIMITE — un fil absent du board (id vide/None) n'est jamais renommé."""
    book = {}
    write, calls = _recorder()
    out = _api(kpp, "sync_titles")(
        [_ticket("", BLOCKED, "n0"), _ticket(None, BLOCKED, "n1"), _ticket("T1", BLOCKED, "n2")],
        write, book, now=1000.0)
    assert [c[0] for c in calls] == ["T1"], (
        f"seul le fil résolu est écrit (jamais un fil absent/étranger) : {calls!r}"
    )
    assert [o["action"] for o in out] == ["skip", "skip", "rename"], f"{out!r}"


def test_limite_un_nom_vide_n_est_pas_ecrit(kpp):
    """LIMITE — un nom vide est OMIS (jamais un placeholder à la place du titre)."""
    book = {}
    write, calls = _recorder()
    out = _api(kpp, "sync_titles")([_ticket("T1", DONE, "")], write, book, now=1000.0)
    assert calls == [], f"un nom vide ne doit pas partir sur le fil : {calls!r}"
    assert out[0]["action"] == "skip", f"{out!r}"
    assert "T1" not in book or not book["T1"].get("ts"), (
        f"un nom vide ne consomme pas la fenêtre : {book.get('T1')!r}"
    )


# ==========================================================================
# C. ERREUR — refus 429, adaptateur qui lève, statut inconnu
# ==========================================================================

def test_erreur_un_429_ne_tue_pas_le_tick(kpp):
    """ERREUR — un fil refusé (429) n'empêche pas les autres ; l'échec est tracé."""
    book = {}

    def write(thread_id, name):
        if thread_id == "T1":
            return {"ok": False, "retry_after": 600.0, "detail": "429 rate limited"}
        return {"ok": True}

    out = _api(kpp, "sync_titles")(
        [_ticket("T1", BLOCKED, "n1"), _ticket("T2", IN_PROGRESS, "n2")],
        write, book, now=1000.0)
    par_fil = {o["thread_id"]: o for o in out}
    assert set(par_fil) == {"T1", "T2"}, f"{out!r}"
    assert par_fil["T1"]["ok"] is False, (
        f"le refus doit être un ÉCHEC nommé, pas un succès silencieux : {par_fil['T1']!r}"
    )
    assert par_fil["T2"]["ok"] is True, f"T2 doit continuer d'être servi : {par_fil['T2']!r}"
    assert par_fil["T1"]["retry_after"] == 600.0, (
        f"le `retry_after` observé doit être rapporté : {par_fil['T1']!r}"
    )
    assert book["T1"].get("failures"), (
        f"l'échec doit être inscrit au livre (trace persistante) : {book['T1']!r}"
    )


def test_erreur_le_refus_est_trace_avec_le_fil_et_le_retry_after(kpp):
    """ERREUR — le refus apparaît avec le fil concerné ET le `retry_after` observé."""
    book = {}

    def write(thread_id, name):
        return {"ok": False, "retry_after": 612.5, "detail": "HTTP 429 Too Many Requests"}

    out = _api(kpp, "sync_titles")([_ticket("T-REFUS", BLOCKED, "n")], write, book, now=2000.0)
    verdict = out[0]
    assert verdict["thread_id"] == "T-REFUS", f"{verdict!r}"
    assert verdict["retry_after"] == 612.5, f"{verdict!r}"
    assert verdict["action"] == "rename" and verdict["ok"] is False, f"{verdict!r}"
    trace = json.dumps(book, ensure_ascii=False)
    assert "T-REFUS" in trace, f"le fil concerné doit figurer dans la trace : {trace[:300]}"
    assert "612.5" in trace, f"le `retry_after` doit figurer dans la trace : {trace[:300]}"


def test_erreur_la_reprise_a_lieu_au_tick_suivant(kpp):
    """ERREUR — un refus ne consomme PAS la fenêtre : le tick suivant réessaie et réussit."""
    book = {}
    etat = {"refus": True}

    def write(thread_id, name):
        if etat["refus"]:
            return {"ok": False, "retry_after": 600.0, "detail": "429"}
        return {"ok": True}

    _api(kpp, "sync_titles")([_ticket("T1", BLOCKED, "n1")], write, book, now=1000.0)
    assert book["T1"].get("ts") in (None, 0), (
        f"un refus ne doit pas dater un SUCCÈS (sinon la reprise attend 10 min) : {book['T1']!r}"
    )
    etat["refus"] = False
    out = _api(kpp, "sync_titles")([_ticket("T1", BLOCKED, "n1")], write, book, now=1000.0 + 5.0)
    assert out[0]["action"] == "rename" and out[0]["ok"] is True, (
        f"la reprise doit avoir lieu dès le tick suivant : {out!r}"
    )


def test_erreur_un_adaptateur_qui_leve_ne_tue_pas_le_tick(kpp):
    """ERREUR — une exception de l'adaptateur est rattrapée et tracée, le reste du tick passe."""
    book = {}
    servis = []

    def write(thread_id, name):
        if thread_id == "T1":
            raise RuntimeError("réseau coupé")
        servis.append(thread_id)
        return {"ok": True}

    out = _api(kpp, "sync_titles")(
        [_ticket("T1", BLOCKED, "n1"), _ticket("T2", DONE, "n2")], write, book, now=1000.0)
    assert servis == ["T2"], f"le fil sain doit être servi malgré l'exception : {servis!r}"
    assert out[0]["ok"] is False and "réseau" in (out[0]["detail"] or ""), f"{out[0]!r}"
    assert book["T1"].get("failures"), f"l'exception doit rester tracée : {book['T1']!r}"


def test_erreur_un_statut_de_carte_inconnu_n_ecrit_aucun_titre(kpp):
    """ERREUR — un statut hors nomenclature n'a pas d'icône : refus silencieux, jamais inventée."""
    f = _api(kpp, "card_title_state")
    for card in ({"status": "weird"}, {}, {"status": ""}, {"status": "archived_x"},
                 {"status": None}, {"status": "pending"}):
        assert f(card) is None, f"statut inconnu {card!r} -> None attendu, obtenu {f(card)!r}"
    # Un état inconnu ne fait pas écrire non plus au niveau du cycle.
    book = {}
    write, calls = _recorder()
    out = _api(kpp, "sync_titles")([_ticket("T1", "etat_inconnu", "n1")], write, book, now=1000.0)
    assert calls == [], f"un état inconnu ne doit pas atteindre l'écriture : {calls!r}"
    assert out[0]["action"] == "skip", f"{out!r}"
