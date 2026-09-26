"""Banc RED de la slice 2/3 (#4) : la garde d'état d'issue est bruyante sur TOUS ses chemins de doute.

Dérivé de (R1) — la source qui fait foi est l'artefact ratifié, pas le corps de l'issue :

- contrat réellement implémenté par `dev-2`, publié sur le blackboard de la racine `t_e41f9643`
  (clé `green-2`, commentaires 404 et 406) : `escalation_allowed(state)` est la décision PURE
  (OPEN -> True, CLOSED -> False, chaîne vide/inconnue/None -> True, strip().upper()), `issue_is_closed`
  porte le seul point d'injection `runner` et écrit ses avertissements sur la sortie standard, et
  `_warn_once` déduplique **par message** — d'où QUATRE messages distincts ;
- `docs/architecture/components/pj-escalate.md` §« Chemins de doute — trois chemins, trois
  avertissements » (la table des quatre chemins de doute) ;
- Gherkin de la carte `t_a5a03a96` (nominal / limite / erreur) ;
- arbitrage `t_fa40c7e3` : QUATRE chemins de doute (gh introuvable, exception, rc != 0, sortie
  illisible), chacun avec SON message, **jamais** d'assertion sur un NOMBRE d'avertissements —
  un total (« exactement 3 avertissements ») échouerait sur le code livré et ferait rejeter une
  implémentation honnête.

Nature des cas : nominal (décision pure + binaire introuvable + états décidables muets), limite
(état vide/inconnu, `rc != 0`, sortie illisible, un message par chemin), erreur (exception du
sous-processus : avertit, ne se propage jamais).

Ce que ce banc épingle, en une phrase : **aucun chemin de doute ne retourne en silence**. Le retour
`False` seul ne suffit pas à distinguer « escalade par doute » de « escalade normale » — une garde
inerte qui avale son exception rend exactement le même `False`. L'assertion porte donc, pour chaque
chemin, sur la **sortie standard** en plus de la valeur de retour.

Module testé : le canonique `pipeline/pj_escalate.py`, chargé **par chemin** (`spec_from_file_location`)
avec l'override `PJ_TARGET_COPY` (R4) qui permet de rejouer ce banc sur une autre copie (copie publiée
de la slice 3, ou module d'avant correctif pour la preuve du RED). Aucun chemin machine n'est codé ici.

Aucun test ne lit le texte source du fichier testé : l'API est appelée, la sortie est capturée.
Les messages d'avertissement sont pinnés par un **jeu de marqueurs sémantiques** (et non par une
phrase figée) : ce qui est jugé, c'est (a) qu'un avertissement existe, (b) qu'il nomme SON chemin,
(c) que deux chemins différents ne partagent pas le même message. Une phrase exacte serait un test
de prose (R3) ; un marqueur vide serait un test tautologique.
"""
import contextlib
import importlib.util
import io
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

import pytest  # noqa: E402

# --------------------------------------------------------------- contrat pinné ---
# 1. module sous test : foyer canonique `pipeline/`. `PJ_TARGET_COPY` rejoue le banc sur une autre
#    copie (copie publiée de la slice 3 ; module d'avant le correctif pour la preuve du delta RED).
TARGET = (Path(os.environ["PJ_TARGET_COPY"]) if os.environ.get("PJ_TARGET_COPY")
          else REPO / "pipeline" / "pj_escalate.py")
# 2. décision PURE (aucune E/S) — nom figé par `dev-2`
DECISION = "escalation_allowed"
# 3. garde d'état d'issue (seul point d'injection : `runner`) — nom figé par `dev-2`
GUARD = "issue_is_closed"
# 4. résolution du binaire — contrat de retour ÉPINGLÉ : chaîne vide, jamais le nom nu
RESOLVE_BIN = "_resolve_bin"
# 5. dédup des avertissements (set process-local, vidé entre deux cas : cf. fixture)
WARNED = "_WARNED"
# 6. états DÉCIDABLES — les deux seuls muets
OPEN, CLOSED = "OPEN", "CLOSED"
# 7. politique : un état indéterminé ESCALADE (jamais de silence par erreur)
ESCALATE, SKIP = False, True          # retour de GUARD : False = escalade, True = carte traitée
# 8. identité utilisée sur les chemins de doute (le repo/issue n'est jamais deviné par la garde)
REPO_NAME, ISSUE = "hermes-workflow", 4

# marqueurs sémantiques par chemin : le message doit NOMMER son chemin, sans figer sa phrase.
# Volontairement larges (plusieurs formulations acceptées) : le jugé est la présence + l'identité
# du message, pas sa rédaction. Le silence, lui, n'est jamais accepté.
ABSENT_MARKERS = ("introuvable", "indisponible", "absent", "gh")
RC_MARKERS = ("rc", "3", "retour", "code")
EXC_MARKERS = ("oserror", "levé", "leve", "exception", "illisible", "indéterminé", "indetermine")
UNREADABLE_MARKERS = ("archived",)          # la sortie REÇUE doit être nommée (Gherkin)


def _load(path, name="pj_escalate_issue_state_under_test"):
    """Charge le module par chemin ; échoue en ERROR (pas en SKIP) s'il n'existe pas."""
    if not path.exists():
        pytest.fail(f"module absent: {path}")
    spec = importlib.util.spec_from_file_location(name, str(path))
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    # `spec_from_file_location` ne met PAS le dossier du module sur sys.path : ses imports frères
    # (helper Discord) échoueraient ici alors qu'ils passent au lancement par chemin.
    sys.path.insert(0, str(path.parent))
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.path.remove(str(path.parent))
    return mod


@pytest.fixture(scope="module")
def m():
    return _load(TARGET)


@pytest.fixture(autouse=True)
def _fresh_warnings(m):
    """Vide la dédup AVANT chaque cas : un avertissement déjà émis par un autre cas rendrait muet
    le chemin jugé ici, et le banc dépendrait de l'ORDRE de collecte (le piège mesuré sur #5)."""
    warned = getattr(m, WARNED, None)
    if warned is not None:
        warned.clear()
    yield


def _cfg(m, **over):
    """Configuration réelle du module (le dataclass de production, pas un faux)."""
    kw = dict(channel_id="100000000000000001", user_id="200000000000000002",
              guild_id="300000000000000003", repos_root=Path("/nonexistent-repos"),
              state_dir=Path("/tmp/pj-escalate-issue-state-state"),
              thread_helper=Path("/nonexistent-helper.py"), org="hyron-fr", gh_bin="/bin/gh")
    kw.update(over)
    return m.EscalationConfig(**kw)


class _Proc:
    """Résultat de sous-processus, forme minimale lue par la garde."""

    def __init__(self, rc=0, out="", err=""):
        self.returncode, self.stdout, self.stderr = rc, out, err


def _runner(proc=None, exc=None, calls=None):
    def run(args, **kw):
        if calls is not None:
            calls.append(list(args))
        if exc is not None:
            raise exc
        return proc
    return run


def _call(m, cfg, runner=None):
    """Appelle la garde en capturant stdout/stderr ; rend (retour, exception, out, err)."""
    kwargs = {} if runner is None else {"runner": runner}
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            ret = getattr(m, GUARD)(cfg, REPO_NAME, ISSUE, **kwargs)
        except BaseException as e:                       # noqa: BLE001 — une fuite est un verdict
            return "<levé>", e, out.getvalue(), err.getvalue()
    return ret, None, out.getvalue(), err.getvalue()


def _decision(m):
    fn = getattr(m, DECISION, None)
    assert fn is not None, (
        f"{DECISION}() est absente du module : la décision d'escalade doit être une fonction PURE "
        f"appelable directement, sans configuration et sans E/S")
    return fn


def _warnings(stdout):
    return [l for l in stdout.splitlines() if l.strip()]


# ----------------------------------------------------------------------- nominal ---

def test_nominal_decision_is_a_pure_function_of_the_state(m, monkeypatch):
    """S1 : OPEN -> escalade (True), CLOSED -> carte traitée (False), comparaison insensible à la
    casse et aux blancs. PURE : aucun sous-processus, et MUETTE (l'avertissement appartient à
    l'appelante, seule à pouvoir nommer l'entité concernée)."""
    def _boom(*a, **k):
        raise AssertionError("la décision pure ne doit lancer AUCUN sous-processus")
    monkeypatch.setattr(m.subprocess, "run", _boom)
    decide = _decision(m)
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        assert decide(OPEN) is True, "OPEN laisse partir l'escalade"
        assert decide(CLOSED) is False, "CLOSED n'attend plus de décision humaine"
        assert decide(f"  {OPEN.lower()}\n") is True, "casse et blancs de bord indifférents"
        assert decide(f" {CLOSED.lower()} ") is False, "casse et blancs de bord indifférents"
    assert out.getvalue() == "", (
        f"la décision pure est muette : les avertissements sont émis par la garde appelante, "
        f"reçu {out.getvalue()!r}")


def test_nominal_gh_binary_absent_warns_and_still_escalates(m):
    """S3 : exécutable introuvable -> escalade inchangée (False) ET avertissement visible nommant
    l'indisponibilité. C'est le seul chemin déjà bruyant avant la slice : il ancre le contrat et
    interdit qu'une correction des trois autres chemins supprime celui-ci."""
    ret, exc, out, err = _call(m, _cfg(m, gh_bin=""))
    assert exc is None, f"aucune exception attendue : {exc!r}"
    assert ret is ESCALATE, "gh introuvable : on escalade quand même"
    lines = _warnings(out)
    assert lines, ("garde inerte et MUETTE : l'indisponibilité de gh doit être annoncée sur la "
                   "sortie standard")
    joined = " ".join(lines).lower()
    assert any(mk in joined for mk in ABSENT_MARKERS), \
        f"l'avertissement doit nommer l'indisponibilité : {out!r}"


def test_nominal_decidable_states_are_silent_and_read_the_documented_argv(m):
    """S1/S3 : OPEN et CLOSED restent MUETS (le nominal bruyant n'est jamais un état décidable) et
    la garde interroge `gh` avec l'identité reçue — binaire, repo/organisation et numéro d'issue
    doivent venir des arguments, pas d'une valeur codée."""
    calls = []
    ret_open, exc, out_open, _ = _call(m, _cfg(m), _runner(_Proc(0, f"{OPEN}\n"), calls=calls))
    assert exc is None and ret_open is ESCALATE, f"OPEN -> escalade, reçu {ret_open!r}"
    assert _warnings(out_open) == [], f"état décidable muet attendu, reçu {out_open!r}"
    assert len(calls) == 1, f"un seul appel attendu, reçu {calls}"
    argv = calls[0]
    assert argv[0] == "/bin/gh", f"le binaire vient de la configuration : {argv}"
    assert "issue" in argv and "view" in argv, f"forme d'appel gh inattendue : {argv}"
    assert str(ISSUE) in argv, f"le numéro d'issue doit être celui reçu : {argv}"
    assert f"hyron-fr/{REPO_NAME}" in argv, f"repo/organisation doivent venir de la configuration : {argv}"

    calls.clear()
    ret_closed, exc, out_closed, _ = _call(m, _cfg(m), _runner(_Proc(0, f"{CLOSED}\n"), calls=calls))
    assert exc is None and ret_closed is SKIP, f"CLOSED -> carte traitée, reçu {ret_closed!r}"
    assert _warnings(out_closed) == [], f"état décidable muet attendu, reçu {out_closed!r}"


# ------------------------------------------------------------------------ limite ---

@pytest.mark.parametrize("state", ["", "   ", None, "ARCHIVED", "UNKNOWN", "open/closed"])
def test_limit_unknown_state_still_escalates(m, state):
    """S2 : chaîne vide ou état inconnu -> ESCALADE (True). La règle est écrite dans le corps de la
    carte, pas déduite : un doute ne doit jamais rendre une carte muette *par erreur*. Une
    implémentation à deux états (`state == "CLOSED"`) satisfait les deux valeurs nominales et se
    fait rejeter ici."""
    decide = _decision(m)
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        assert decide(state) is True, f"état indéterminé {state!r} : on escalade"
    assert out.getvalue() == "", "la décision indéterminée reste muette (l'appelante avertit)"


def test_limit_nonzero_returncode_warns(m):
    """S4 : `gh` sort en code non nul sur un ticket inexistant -> escalade inchangée ET
    avertissement. AVANT la slice 2 ce chemin était TOTALEMENT muet (mesuré) : le retour False
    seul ne distinguait pas ce cas du nominal."""
    ret, exc, out, err = _call(m, _cfg(m), _runner(_Proc(3, "", "not found")))
    assert exc is None, f"aucune exception attendue : {exc!r}"
    assert ret is ESCALATE, "un code de retour non nul n'empêche pas l'escalade"
    lines = _warnings(out)
    assert lines, ("garde inerte et MUETTE : un `gh` en échec doit être annoncé sur la sortie "
                   "standard (défaut mesuré avant la slice 2 : silence total)")
    joined = " ".join(lines).lower()
    assert any(mk in joined for mk in RC_MARKERS), \
        f"l'avertissement doit nommer le code de retour : {out!r}"


def test_limit_unreadable_output_warns(m):
    """S6 : code 0 mais texte ni OPEN ni CLOSED (ex. `ARCHIVED`) -> escalade inchangée ET
    avertissement NOMMANT LA SORTIE REÇUE. Aujourd'hui : silence total, et la garde passait pour
    active (elle retournait False « comme prévu »)."""
    ret, exc, out, err = _call(m, _cfg(m), _runner(_Proc(0, "ARCHIVED\n", "")))
    assert exc is None, f"aucune exception attendue : {exc!r}"
    assert ret is ESCALATE, "une sortie illisible n'empêche pas l'escalade"
    joined = " ".join(_warnings(out)).lower()
    assert joined, ("garde inerte et MUETTE : une sortie illisible doit être annoncée sur la "
                    "sortie standard")
    assert any(mk in joined for mk in UNREADABLE_MARKERS), \
        f"l'avertissement doit nommer la sortie reçue : {out!r}"


def test_limit_each_doubt_path_has_its_own_message(m):
    """S7 : les quatre conditions de doute, exercées l'une après l'autre DANS LE MÊME PROCESSUS,
    produisent chacune un message DISTINCT, et les deux états décidables restent muets.

    Aucune assertion ne porte sur un NOMBRE d'avertissements (trancher « exactement 3 » ferait
    rejeter le code livré, qui en porte quatre — arbitrage `t_fa40c7e3`). Ce qui est jugé : quatre
    messages non vides, deux à deux DIFFÉRENTS. Une implémentation qui réutiliserait une seule
    chaîne pour deux chemins laisserait la dédup `_warn_once` (par message) avaler le second, et
    ce cas le prouve. Le témoin négatif est le couple OPEN/CLOSED : muet."""
    seen = {}
    seen["gh introuvable"] = _call(m, _cfg(m, gh_bin=""))[2]
    seen["rc != 0"] = _call(m, _cfg(m), _runner(_Proc(3, "", "boom")))[2]
    seen["exception"] = _call(m, _cfg(m), _runner(exc=OSError("boom")))[2]
    seen["sortie illisible"] = _call(m, _cfg(m), _runner(_Proc(0, "ARCHIVED", "")))[2]

    messages = {}
    for label, stdout in seen.items():
        lines = _warnings(stdout)
        assert lines, f"chemin « {label} » muet : la garde doit avertir, jamais en silence"
        messages[label] = " ".join(lines).strip()

    distinct = set(messages.values())
    assert len(distinct) == len(messages), (
        "deux chemins de doute partagent le MÊME message, donc le second est avalé par la dédup "
        f"par message : {messages}")

    # états décidables : muets, et l'absence d'avertissement n'est pas un chemin de doute
    for label, proc, expected in ((OPEN, _Proc(0, f"{OPEN}\n", ""), ESCALATE),
                                  (CLOSED, _Proc(0, f"{CLOSED}\n", ""), SKIP)):
        ret, exc, out, err = _call(m, _cfg(m), _runner(proc))
        assert (ret, exc) == (expected, None), f"{label} : reçu {ret!r} / {exc!r}"
        assert _warnings(out) == [], f"{label} est un état décidable : muet, reçu {out!r}"


def test_limit_resolve_bin_returns_empty_and_never_the_bare_name(m):
    """S3, racine du doute n° 1 : la résolution rend la CHAÎNE VIDE quand rien ne passe — jamais le
    nom nu. Le nom nu rendrait le binaire *truthy*, l'avertissement ne partirait pas, puis le
    `FileNotFoundError` serait avalé par le `except Exception` de la garde : inerte ET muette.
    Contre-épreuve dans le même cas : un binaire présent est bien résolu (le test n'est pas
    satisfait par une fonction qui rendrait toujours vide)."""
    resolve = getattr(m, RESOLVE_BIN, None)
    assert resolve is not None, f"{RESOLVE_BIN}() absente"
    assert resolve("zorglub-xyz-inexistant", "/nope/nope") == "", \
        "un binaire introuvable doit rendre la chaîne vide, jamais le nom nu"
    assert resolve("sh"), "un binaire présent doit être résolu (contre-épreuve)"


# ------------------------------------------------------------------------- erreur ---

def test_error_exception_of_the_subprocess_warns_and_never_propagates(m):
    """S5 : le sous-processus ne peut pas être lancé -> la garde retourne False SANS propager
    l'exception (une fuite ferait tomber le tick entier, donc toutes les cartes suivantes) ET
    avertit. AVANT la slice 2 : exception avalée en silence — le pire des deux mondes."""
    ret, exc, out, err = _call(m, _cfg(m), _runner(exc=OSError("cannot execute")))
    assert exc is None, (f"l'exception ne doit JAMAIS se propager (elle tue les cartes suivantes "
                         f"du tick) : reçu {exc!r}")
    assert ret is ESCALATE, "une exception sur l'état du ticket : on escalade quand même"
    lines = _warnings(out)
    assert lines, ("garde inerte et MUETTE : une exception du sous-processus doit être annoncée sur "
                   "la sortie standard (défaut mesuré avant la slice 2 : silence total)")
    joined = " ".join(lines).lower()
    assert any(mk in joined for mk in EXC_MARKERS), \
        f"l'avertissement doit nommer le chemin (type d'exception ou état indéterminé) : {out!r}"
    assert "Traceback (most recent call last)" not in err, \
        f"avertissement attendu, pas une trace d'exception : {err!r}"
