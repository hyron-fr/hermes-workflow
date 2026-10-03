"""RED — bloc Description épinglé du thread Discord, slice 5 `description-epinglee`.

Ce banc gèle le **contrat d'interface** de la moitié description de #19 (arbitrage
humain Q2 = 2b, carte t_0fa1c596 / dev pair t_d1d4eb41) : le fil d'une issue porte
un **message Description dédié ÉPINGLÉ** (jamais le champ `topic` — mesuré :
`PATCH {"topic": …}` rend 200 puis `topic = None`, jeté en silence), dont les trois
lignes se résolvent depuis des sources INJECTÉES et se **taissent proprement**
quand la valeur n'existe pas encore — une ligne non résolue est OMISE, jamais
remplacée par un placeholder.

Périmètre (slice 5, carte dev-5) : `pipeline/engine.py` + `pipeline/pj_room_keeper.py`
(porteur de l'écriture : lui seul sait lire l'état du board ET le plan de slices) ;
l'écriture du message + de l'épingle passe par le helper `discord_thread.py` — ce
banc ne l'appelle JAMAIS : les sources et l'adaptateur sont injectés, 0 réseau.

Contrat d'interface exécuté par ce banc (publié en `contrat-5` sur le blackboard) :

    DESCRIPTION_MARKER = "[description]"
        Marqueur de DÉDUPLICATION du bloc Description : la première ligne du bloc
        porte ce marqueur. Un fil ne porte qu'UN bloc Description — un second
        cycle MET À JOUR le bloc existant (édition), n'en crée pas un second.

    build_description_lines(issue_url, branch, pr_url, log=print) -> list[str]
        Composition PURE du bloc (la grammaire est le contrat, cf. Q2 = 2b) :
          ["[description]",
           "**Issue** : <issue_url>",
           "**Branche** : `<branch>`",
           "**PR** : <pr_url>"]
        Une valeur non résolue (None / chaîne vide) OMET sa ligne — jamais de
        placeholder, jamais de valeur inventée. L'Issue est l'ancre : elle est
        la seule ligne jamais présente.

    description_log_lines(lines) -> list[str]
        Journalisation (BRUYANTE, jamais muette) des sources absentes : une
        entrée par ligne omise, nommant source et cause
        ("branche: non resolue — specs/<n>/slices.json absent (clé 'branch')")
        ; [] si les trois lignes sont résolues.

    keeper.build_description_for_card(card, *, issue_url=None, branch=None,
                                      pr_url=None, log=None) -> dict | None
        Assemble les DEUX sources de la carte avant de composer :
          issue_url — absente dans `card` -> ancre de la ligne d'import du body
                      (`…/issues/N` de la carte racine, `Importé depuis …`),
                      repli `issue_url_lookup` (injectée) ;
          branch    — `specs/<n>/slices.json` clé `branch` (lecteur injecté) ;
          pr_url    — `gh pr list --repo <org>/<repo> --head <branche> --json url`
                      (lecteur injecté) ; aucune PR ouverte -> None -> ligne omise.
        Retour : {"lines": [...], "log": [...]} — ou None si aucune ligne ne se
        résout (jamais de bloc vide, jamais de placeholder).

    keeper.sync_description(cards, *, fetch_messages, write_message, log=None) -> list[dict]
        Écrivain du bloc (best-effort, NE LÈVE JAMAIS — un échec de lecture de
        source ne tue pas le cycle du keeper) :
          fetch_messages(thread_id) -> list[dict]   (messages du fil, dont "id",
                                                     "content", "pinned")
          write_message(thread_id, content, *, edit_id=None) -> dict
                                                     (succès ssi ok is True ;
                                                     edit_id non vide = MISE À JOUR
                                                      du bloc existant, jamais
                                                      un second message)
          card  = {"id", "title", "body", "status", "issue_number"?}
        Résout le fil par carte (ancre `Importé depuis …/issues/N` + lecteur
        injecté `thread_lookup`), compose le bloc, le poste (ou le MET À JOUR si
        un bloc existe déjà) et l'ÉPINGLE. Retour : un verdict par carte résolue,
        dans l'ordre :
          {"card_id", "thread_id", "action": "post"|"edit", "ok": bool,
           "pinned": bool}
        `action` = "edit" ssi le fil portait déjà le marqueur `[description]`
        (mise à jour du même message, jamais de doublon) ; "post" sinon.
        Une carte sans fil résolu est OMISE (verdict `thread_id=None, ok=None`).

    keeper.sync_all_descriptions(cards, *, fetch_messages, write_message,
                                 log=None, specs_reader=None, pr_reader=None,
                                 issue_url_lookup=None) -> list[dict]
        Câble `build_description_for_card` + `sync_description` ; best-effort :
        NE LÈVE JAMAIS (un lecteur de source qui lève ne tue pas le tick).

Le banc est **pur et déterministe** : 0 réseau, 0 sous-processus — `sh` et
`subprocess.run` du module chargé sont empoisonnés (tout appel levé), les sources
(slices.json, `gh pr list`, `gh issue view`) sont injectées.
"""
import importlib.util
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
KEEPER = REPO / "pipeline" / "pj_room_keeper.py"
ENGINE = REPO / "pipeline" / "engine.py"

# ---------------------------------------------------------------- vocabulaire gelé
MARKER = "[description]"
ISSUE_URL = "https://github.com/hyron-fr/hermes-workflow/issues/19"
BRANCHE = "wt/issue-19-discord-thread-title-description"
PR_URL = "https://github.com/hyron-fr/hermes-workflow/pull/19"
PROJECT = "hermes-workflow"
TICKET = 19


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
    """Le keeper de production (`pipeline/pj_room_keeper.py`) — porteur de l'écriture du bloc."""
    return _load(KEEPER, "t5_keeper_under_test")


@pytest.fixture(scope="module")
def eng():
    """Le moteur (`pipeline/engine.py`) — formateur pur de la slice 3, chargé avec `pipeline/` sur sys.path."""
    return _load(ENGINE, "t5_engine_under_test", extra_path=(REPO / "pipeline",))


@pytest.fixture(autouse=True)
def _empoisonne_reseau(monkeypatch, kpp, eng):
    """0 réseau / 0 sous-processus : tout appel externe levé (le banc ne doit JAMAIS y passer)."""
    for mod in {id(kpp): kpp, id(eng): eng}.values():
        sp = getattr(mod, "subprocess", None)
        if sp is not None:
            monkeypatch.setattr(sp, "run", _boom, raising=False)
        sh = getattr(mod, "sh", None)
        if callable(sh):
            monkeypatch.setattr(mod, "sh", _boom, raising=False)


def _boom(*_a, **_k):
    raise AssertionError("le banc ne doit JAMAIS appeler de sous-processus ni de réseau")


def _api(mod, nom, message):
    """Attribut du contrat, ou échec NOMMANT l'attribut absent (jamais un AttributeError nu)."""
    if not hasattr(mod, nom):
        pytest.fail(message)
    return getattr(mod, nom)


def _card(import_url=ISSUE_URL, number=19, status="running"):
    return {
        "id": "t_cart",
        "title": "Discord thread title and description update",
        "body": f"Spec du ticket.\n\n—\nImporté depuis {import_url}",
        "status": status,
        "issue_number": number,
    }


def _verdicts_out(v):
    return [v if isinstance(v, dict) else (v or {}) for v in (v if isinstance(v, list) else [v])]


# ==========================================================================
# A. NOMINAL — le bloc porte l'issue, la branche et la PR quand elles existent
# ==========================================================================

def test_nominal_le_bloc_porte_les_trois_lignes(kpp, eng):
    """NOMINAL — trois valeurs résolues -> les trois lignes sont présentes, dans l'ordre."""
    f = _api(eng, "build_description_lines",
             "API absente : engine.build_description_lines(issue_url, branch, pr_url, log=…) — "
             "le contrat `contrat-5` l'exige (composant PUR du bloc Description, arbitrage 2b)")
    lines = f(ISSUE_URL, BRANCHE, PR_URL)
    assert isinstance(lines, list) and len(lines) == 4, f"bloc attendu : 4 lignes (marqueur + 3 lignes), obtenu {lines!r}"
    assert lines[0] == MARKER, f"la première ligne porte le marqueur {MARKER!r} (déduplication), obtenu {lines[0]!r}"
    assert ISSUE_URL in lines[1], f"la ligne Issue porte l'URL réelle : {lines[1]!r}"
    assert BRANCHE in lines[2], f"la ligne Branche porte la branche DCLARÉE PAR LE PLAN : {lines[2]!r}"
    assert PR_URL in lines[3], f"la ligne PR porte l'URL réelle : {lines[3]!r}"
    labels = [l.split("**")[1] for l in lines[1:]]
    assert labels == ["Issue", "Branche", "PR"], f"ordre et libellés : {labels!r}"


def test_nominal_la_carte_rejoint_ses_sources_et_poste_le_bloc(kpp, eng, monkeypatch):
    """NOMINAL — carte sans URL d'import explicite : l'ancre du body + le plan de slices + la PR résolue."""
    b = _api(kpp, "build_description_for_card",
             "API absente : keeper.build_description_for_card(card, *, issue_url=None, branch=None, "
             "pr_url=None, log=None, specs_reader=None, pr_reader=None, issue_url_lookup=None) — le contrat "
             "`contrat-5` l'exige (assemblage des sources de la carte)")
    monkeypatch.setattr(kpp, "thread_lookup", lambda n: "TH-19", raising=False)
    out = b(_card(import_url=""), issue_url=None, branch=BRANCHE, pr_url=PR_URL,
            pr_reader=lambda b: PR_URL, issue_url_lookup=lambda n: ISSUE_URL)
    assert out is not None, "une carte avec ancre d'import ET plan de slices ET PR ouverte doit produire un bloc"
    assert out["lines"][1].rstrip().endswith(str(TICKET)), f"l'ancre de la ligne d'import (…/issues/{TICKET}) résout l'URL de l'issue : {out['lines'][1]!r}"
    assert ISSUE_URL in out["lines"][1], f"l'URL d'issue réelle : {out['lines'][1]!r}"
    assert BRANCHE in out["lines"][2], f"la branche du plan de slices : {out['lines'][2]!r}"
    assert PR_URL in out["lines"][3], f"la PR ouverte (filtre --head <branche>) : {out['lines'][3]!r}"
    assert out["log"] == [], f"les trois sources sont résolues -> aucune journalisation d'absence : {out['log']!r}"


def test_nominal_un_seul_message_epingle_mis_a_jour_pas_duplique(kpp, monkeypatch):
    """NOMINAL — premier cycle : le bloc est posté et épinglé, l'accueil reste intact ;
    cycle suivant : le message EXISTANT est mis à jour, jamais un second message."""
    s = _api(kpp, "sync_description",
             "API absente : keeper.sync_description(cards, *, fetch_messages, write_message, log=None) — "
             "le contrat `contrat-5` l'exige (écrivain best-effort du bloc épinglé)")
    state = {"messages": [{"id": "m-welcome", "content": "🎫 Issue #19 — accueil du fil"}],
             "edits": 0, "posts": 0, "pins": []}

    def fetch_messages(tid):
        assert tid == "TH-19"
        return [dict(m) for m in state["messages"]]

    def write_message(tid, content, *, edit_id=None):
        if edit_id is None:
            state["posts"] += 1
            mid = f"m-desc-{state['posts']}"
            state["messages"].append({"id": mid, "content": content})
        else:
            state["edits"] += 1
            for m in state["messages"]:
                if m["id"] == edit_id:
                    m["content"] = content
        return {"ok": True, "id": edit_id or f"m-desc-{state['posts']}"}

    out1 = s([_card()], fetch_messages=fetch_messages, write_message=write_message)
    v1 = _verdicts_out(out1)[0]
    assert v1.get("thread_id") == "TH-19", f"le fil de la carte doit être résolu : {v1!r}"
    assert v1.get("action") == "post", f"premier cycle -> création du message dédié : {v1!r}"
    assert state["posts"] == 1 and state["edits"] == 0, f"un seul message créé : {state!r}"
    bloc = [m for m in state["messages"] if MARKER in m["content"]]
    assert len(bloc) == 1, f"un UNIQUE message Description (marqueur {MARKER!r}) : {state['messages']!r}"
    assert bloc[0]["content"].count(MARKER) == 1, "le marqueur figure UNE fois dans le bloc"
    assert "m-welcome" not in bloc[0]["content"], f"le message d'accueil reste INTACT (arbitrage 2b) : {bloc[0]['content']!r}"
    assert state["messages"][0]["content"].startswith("🎫 Issue #19"), "l'accueil du fil n'est jamais réécrit"
    assert v1.get("ok") is True, f"l'écriture réussit : {v1!r}"

    # Cycle suivant : le fil porte déjà le marqueur -> MISE À JOUR, jamais de doublon.
    out2 = s([_card()], fetch_messages=fetch_messages, write_message=write_message)
    v2 = _verdicts_out(out2)[0]
    assert v2.get("action") == "edit", f"le bloc existant est mis à jour, pas dupliqué : {v2!r}"
    assert state["posts"] == 1, f"AUCUN second message Description créé : posts={state['posts']}, edits={state['edits']}"
    assert state["edits"] == 1, f"le message existant est édité : {state!r}"
    assert len([m for m in state["messages"] if MARKER in m["content"]]) == 1, "toujours un UNIQUE bloc après le second cycle"


# ==========================================================================
# B. LIMITE — une ligne non résolue est omise, jamais remplacée
# ==========================================================================

def test_limite_pr_absente_la_ligne_est_omise_jamais_placeholder(kpp, eng):
    """LIMITE — aucune PR ouverte : la ligne PR disparaît, aucun placeholder ne la remplace."""
    f = _api(eng, "build_description_lines",
             "API absente : engine.build_description_lines — contrat `contrat-5`")
    log = []
    lines = f(ISSUE_URL, BRANCHE, None, log=log.append)
    assert isinstance(lines, list) and len(lines) == 3, f"3 lignes (marqueur + 2) : {lines!r}"
    assert lines[0] == MARKER
    assert ISSUE_URL in lines[1] and BRANCHE in lines[2]
    assert lines[2].split("**")[1] == "Branche", f"la ligne PR EST ABSENTE (pas 'PR : en attente') : {lines[2]!r}"
    assert all("PR" != l.split("**")[1] for l in lines[1:]), f"aucune ligne PR : {lines!r}"
    assert "placeholder" not in " ".join(lines).lower() and "n/a" not in " ".join(lines).lower(), (
        f"aucun placeholder inventé : {lines!r}")
    assert log, f"l'absence de source de la PR est JOURNALISÉE (bruyante) : {log!r}"
    assert "PR" in " ".join(log), f"la journalisation nomme la ligne absente : {log!r}"


def test_limite_sans_plan_de_slices_la_ligne_branche_est_omise(kpp, eng, monkeypatch):
    """LIMITE — specs/<n>/slices.json absent (clé branch) : la ligne Branche est omise et journalisée."""
    f = _api(eng, "build_description_lines",
             "API absente : engine.build_description_lines — contrat `contrat-5`")
    log = []
    lines = f(ISSUE_URL, None, None, log=log.append)
    assert len(lines) == 2, f"marqueur + Issue seule (branche ET PR omises) : {lines!r}"
    assert ISSUE_URL in lines[1]
    assert not any("Branche" in l or "PR" in l for l in lines[1:]), f"aucune ligne omise remplacée : {lines!r}"
    assert len(log) == 2, f"les deux absences sont journalisées : {log!r}"
    assert "branche" in " ".join(log).lower() and "PR" in " ".join(log), f"{log!r}"
    # Aucune valeur n'est INVENTÉE : ni branche ni PR ne doivent ressembler aux vraies valeurs.
    assert BRANCHE not in " ".join(lines) and PR_URL not in " ".join(lines), f"valeurs non résolues jamais inventées : {lines!r}"


def test_limite_le_fil_omis_quand_riene_ne_se_resout(kpp, monkeypatch):
    """LIMITE — carte sans ancre d'import et sans URL d'issue : aucun bloc, aucun verdict écrit."""
    b = _api(kpp, "build_description_for_card",
             "API absente : keeper.build_description_for_card — contrat `contrat-5`")
    out = b(_card(import_url=""))
    assert out is None, f"aucune source résolue -> aucune ligne -> aucun bloc (pas de placeholder) : {out!r}"
    s = _api(kpp, "sync_description",
             "API absente : keeper.sync_description — contrat `contrat-5`")

    def fetch_messages(tid):
        raise AssertionError("un fil non résolu ne doit jamais être lu")

    def write_message(tid, content, *, edit_id=None):
        raise AssertionError("aucune écriture sans bloc")

    out2 = s([_card(import_url="")], fetch_messages=fetch_messages, write_message=write_message)
    v = _verdicts_out(out2)[0]
    assert not v.get("thread_id") and not v.get("ok"), f"la carte sans fil résolu est omise : {v!r}"


# ==========================================================================
# C. ERREUR — une lecture de gh qui échoue est bruyante, le bloc tient
# ==========================================================================

def test_erreur_gh_pr_list_en_erreur_ligne_omise_tracee_pas_exception(kpp, monkeypatch):
    """ERREUR — le lecteur PR lève (binaire gh absent / en erreur) : la ligne est omise,
    l'échec est tracé, la construction ne lève PAS."""
    b = _api(kpp, "build_description_for_card",
             "API absente : keeper.build_description_for_card — contrat `contrat-5`")

    def fake_issue_url(n):
        return ISSUE_URL

    monkeypatch.setattr(kpp, "issue_url_lookup", fake_issue_url, raising=False)

    def pr_reader_fail(branch):
        raise RuntimeError("gh introuvable (PATH + candidats) — `gh pr list` indisponible")

    out = b(_card(), issue_url=None, branch=BRANCHE, pr_reader=pr_reader_fail)
    assert out is not None, "un échec de lecture de source ne doit PAS faire échouer la construction du bloc"
    assert ISSUE_URL in out["lines"][1], f"la ligne Issue (ancre) reste présente : {out['lines']!r}"
    assert BRANCHE in out["lines"][2], f"la ligne Branche reste présente : {out['lines']!r}"
    assert not any("PR" in l for l in out["lines"][1:]), f"la ligne PR est omise (jamais inventée) : {out['lines']!r}"
    assert out["log"], f"l'échec de `gh pr list` est JOURNALISÉ (bruyant, jamais silencieux) : {out['log']!r}"
    assert "gh" in " ".join(out["log"]).lower(), f"la journalisation nomme la source (gh) en échec : {out['log']!r}"


def test_erreur_la_source_branche_illisible_est_journalisee_non_silencieuse(kpp, eng, monkeypatch):
    """ERREUR — le lecteur de slices.json lève : la ligne est omise, la cause est NOMMÉE dans le log."""
    f = _api(eng, "build_description_lines",
             "API absente : engine.build_description_lines — contrat `contrat-5`")
    log = []
    try:
        lines = f(ISSUE_URL, None, PR_URL, log=log.append)
    except Exception as e:
        pytest.fail(f"la composition du bloc ne doit JAMAIS lever sur une source absente : {e}")
    assert len(lines) == 3, f"marqueur + Issue + PR (Branche omise) : {lines!r}"
    assert PR_URL in lines[2], f"la PR résolue reste présente : {lines[2]!r}"
    assert log and "branche" in " ".join(log).lower(), f"l'absence de branche est journalisée en nommant la cause : {log!r}"


def test_erreur_un_verdict_par_carte_et_omission_des_non_resolues(kpp, monkeypatch):
    """ERREUR — le verdict est un verdict PAR CARTE (pas une liste de messages) ;
    une carte sans fil est omise ; le fil est résolu par l'ancre d'import de la carte."""
    s = _api(kpp, "sync_description",
             "API absente : keeper.sync_description — contrat `contrat-5`")
    monkeypatch.setattr(kpp, "thread_lookup", lambda n: "TH-19" if n == 19 else None, raising=False)
    monkeypatch.setattr(kpp, "issue_url_lookup", lambda n: ISSUE_URL, raising=False)
    carte_morte = _card(number=999, import_url="https://github.com/hyron-fr/hermes-workflow/issues/999")
    out = s([_card(), carte_morte],
            fetch_messages=lambda tid: [{"id": "m1", "content": "🎫 Issue #19 — accueil"}],
            write_message=lambda tid, content, *, edit_id=None: {"ok": True, "id": "m-d"})
    v = _verdicts_out(out)
    assert len(v) == 2, f"un verdict par carte (2), pas par message : {v!r}"
    assert v[0].get("thread_id") == "TH-19" and v[0].get("ok") is True, f"la carte résolue est servie : {v[0]!r}"
    assert not v[1].get("thread_id") and not v[1].get("ok"), f"la carte sans fil est omise (jamais écrite à l'aveugle) : {v[1]!r}"


def test_erreur_le_reader_de_source_qui_leve_ne_tue_pas_le_tick(kpp, monkeypatch):
    """ERREUR — `sync_all_descriptions` : un lecteur de source qui lève est capturé, tracé,
    le tick suivant continue (best-effort, NE LÈVE JAMAIS)."""
    a = _api(kpp, "sync_all_descriptions",
             "API absente : keeper.sync_all_descriptions(cards, *, fetch_messages, write_message, log=None, "
             "specs_reader=None, pr_reader=None, issue_url_lookup=None) — contrat `contrat-5` (câblage best-effort)")

    def specs_reader_boom(n):
        raise RuntimeError("specs/19/slices.json introuvable")

    ecrits = []

    def write_message(tid, content, *, edit_id=None):
        ecrits.append(content)
        return {"ok": True, "id": "m"}

    out = a([_card()], fetch_messages=lambda tid: [{"id": "m-w", "content": "accueil"}],
            write_message=write_message, specs_reader=specs_reader_boom,
            pr_reader=lambda b: PR_URL, issue_url_lookup=lambda n: ISSUE_URL)
    assert isinstance(out, list), f"retour = liste de verdicts : {out!r}"
    assert len(ecrits) == 1, f"le bloc tient sans la branche (ligne omise, tracee) : {ecrits!r}"
    assert MARKER in ecrits[0] and ISSUE_URL in ecrits[0], f"l'ancre Issue reste dans le bloc : {ecrits[0]!r}"
    assert BRANCHE not in ecrits[0], f"la source absente n'est JAMAIS inventée : {ecrits[0]!r}"
