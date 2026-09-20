"""Portage de couverture de `pipeline/pj_escalate.py` (slice 2/3, #4) — exerce le tick par ses seams.

Portée : porter la couverture PAR FICHIER du module livré par la slice 1 au-dessus du seuil de 80 %
(`pj_coverage_gate.py`, périmètre `git diff --name-only origin/dev...HEAD`), sans toucher au banc gelé
de la slice 1 (`tests/test_pj_escalate_config.py`, sha256
`b5cdef9527a49014dfefae13217a472d7f5adcb7005ac664438441d76ed3a02a`) ni affaiblir le banc de la
slice 2 (`tests/test_pj_escalate_issue_state.py`).

Instrument de référence : la sonde jetable de `conv-1` (`/tmp/t_39930fa5/sonde_plafond.py`, hors
dépôt) mesurait 94,27 % (247/262) de plafond **par les seams**. Ce fichier est le portage VERSIONNÉ
de cette sonde : mêmes points d'injection, mais chaque pas porte une **assertion de comportement**
— un test qui se contente d'exécuter des lignes pour faire monter un pourcentage est tautologique et
serait rejeté en convergence.

Périmètre d'écriture de la carte `t_a5a03a96` : c'est le second et dernier fichier neuf autorisé.
Aucune source n'est modifiée (`pipeline/**`, `agents/**` hors périmètre). Aucune directive
d'exclusion de couverture (`pragma`, `.coveragerc`, `--ignore`), aucun abaissement du seuil de 80 %.

Nature des cas (1 nominal + 1 limite + 1 erreur au minimum) : nominal — tick complet sur une base
sqlite de test, résolution d'issue, parcours de thread, envoi, état ; limite — dédup, `--dry-run`,
issue inconnue, sortie illisible de `gh`, répertoire d'état non inscriptible ; erreur — refus de
configuration de `main()` (rc=2, rien muté), envoi en échec, racine de boards absente.

Aucune horloge réelle ni aléa : le temps et les sous-processus sont **injectés** (`runner`, `poster`,
`conn_factory`, et un helper Discord factice exécuté par le vrai chemin quand c'est lui qu'on juge).
"""
import importlib.util
import json
import os
import sqlite3
import stat
import sys
from pathlib import Path
from types import SimpleNamespace

REPO = Path(__file__).resolve().parents[1]

import pytest  # noqa: E402

# --------------------------------------------------------------- contrat pinné ---
# 1. module sous test : foyer canonique `pipeline/`
TARGET = (Path(os.environ["PJ_TARGET_COPY"]) if os.environ.get("PJ_TARGET_COPY")
          else REPO / "pipeline" / "pj_escalate.py")
# 2. racine des boards : constante module-level, surchargée ici (sémantique documentée du module)
KANBAN_ROOT_ATTR = "KANBAN_ROOT"
# 3. points d'injection du tick
SEAM_RUNNER, SEAM_POSTER, SEAM_CONN = "runner", "poster", "conn_factory"
# 4. variables requises / optionnelles
REQUIRED = ("PJ_ESCALATE_CHANNEL_ID", "PJ_ESCALATE_USER_ID", "PJ_ESCALATE_GUILD_ID")
BOARD = "pj-hermes-workflow"
# 5. valeurs synthétiques (aucun identifiant réel du dépôt public)
CHANNEL, USER, GUILD = "100000000000000001", "200000000000000002", "300000000000000003"


def _load(path, name="pj_escalate_seams_under_test"):
    if not path.exists():
        pytest.fail(f"module absent: {path}")
    spec = importlib.util.spec_from_file_location(name, str(path))
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    sys.path.insert(0, str(path.parent))
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.path.remove(str(path.parent))
    return mod


@pytest.fixture(scope="module")
def m():
    return _load(TARGET)


def _env(home, **over):
    env = {REQUIRED[0]: CHANNEL, REQUIRED[1]: USER, REQUIRED[2]: GUILD, "HOME": str(home)}
    env.update(over)
    return env


def _cfg(m, home, **over):
    """Configuration réelle, construite par la fabrique du module (jamais un faux config)."""
    kw = dict(PJ_ESCALATE_REPOS_ROOT=str(home / "pj-repos"),
              PJ_ESCALATE_STATE_DIR=str(home / "state"),
              PJ_ESCALATE_THREAD_HELPER=str(home / "thread_helper.py"),
              PJ_ESCALATE_GH_BIN="/bin/gh")
    kw.update(over)
    return m.escalation_config(_env(home, **kw))


class _CP:
    """Résultat de sous-processus, forme minimale lue par le module."""

    def __init__(self, rc=0, out="", err=""):
        self.returncode, self.stdout, self.stderr = rc, out, err


# sortie du helper de threads : cinq tickets distincts, chacun avec SON thread — c'est ce qui rend
# une assertion « telle carte poste dans tel thread » discriminante (un index vide enverrait tout
# dans le canal de repli, la confusion serait invisible).
THREADS_OUT = ("111 hermes-workflow #4\n112 kerios #7\n113 hermes-workflow #5\n"
               "114 hermes-workflow #6\n115 ligne-sans-issue\n")


class _Runner:
    """Runner injecté : threads, état d'issue (OPEN/CLOSED), envoi. Journalise les appels."""

    def __init__(self, closed=(), broken=(), threads=THREADS_OUT, send_ok=True):
        self.closed, self.broken = set(str(c) for c in closed), set(str(b) for b in broken)
        self.threads, self.send_ok = threads, send_ok
        self.calls = []

    def __call__(self, args, **kw):
        self.calls.append([str(a) for a in args])
        if "threads" in args:
            return _CP(0, self.threads, "")
        if "view" in args:
            # `[binaire, "issue", "view", <numéro>, "--repo", …]` : le numéro est en position 3
            issue = str(args[3])
            if issue in self.broken:
                return _CP(1, "", "gh: not found")
            return _CP(0, "CLOSED\n" if issue in self.closed else "OPEN\n", "")
        return _CP(0, "sent ok" if self.send_ok else "", "" if self.send_ok else "refus")


def _make_board(root, board, tasks, events, links=()):
    """Base kanban de TEST (schéma réel) — on exerce le vrai store, pas un faux."""
    d = root / board
    d.mkdir(parents=True, exist_ok=True)
    db = d / "kanban.db"
    c = sqlite3.connect(db)
    c.executescript(
        "CREATE TABLE tasks(id TEXT PRIMARY KEY, title TEXT, body TEXT, assignee TEXT,"
        " status TEXT, idempotency_key TEXT);"
        "CREATE TABLE task_events(id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT,"
        " kind TEXT, payload TEXT);"
        "CREATE TABLE task_links(parent_id TEXT, child_id TEXT);")
    c.executemany("INSERT INTO tasks VALUES (?,?,?,?,?,?)", tasks)
    c.executemany("INSERT INTO task_events(task_id,kind,payload) VALUES (?,?,?)", events)
    c.executemany("INSERT INTO task_links VALUES (?,?)", links)
    c.commit()
    c.close()
    return db


def _repos(root):
    for name in ("hermes-workflow", "kerios"):
        (root / "pj-repos" / name).mkdir(parents=True, exist_ok=True)
    return root / "pj-repos"


# ============================================================ décision + garde ===

def test_nominal_decision_pure_and_documented_states(m):
    """S1 : la décision est pure, muette, et sa table de vérité est celle documentée."""
    assert m.escalation_allowed("OPEN") is True
    assert m.escalation_allowed("CLOSED") is False


def test_limit_garde_lisible_et_sortie_illisible_du_binaire(m, tmp_path, monkeypatch, capsys):
    """S2 : états décidables muets + les quatre chemins de doute du module (binaire vide, exception
    du runner, rc non nul, sortie illisible) : chacun escalade et avertit, aucun ne propage."""
    monkeypatch.setattr(m, "_WARNED", set())
    cfg = _cfg(m, tmp_path)
    empty_bin = _cfg(m, tmp_path, PJ_ESCALATE_GH_BIN="")
    cases = [
        (empty_bin, None, "introuvable"),
        (cfg, lambda *a, **k: _CP(1, "", "refus"), "rc=1"),
        (cfg, lambda *a, **k: (_ for _ in ()).throw(OSError("boom")), "OSError"),
        (cfg, lambda *a, **k: _CP(0, "ARCHIVED", ""), "ARCHIVED"),
    ]
    for cfg_i, runner, expected in cases:
        m._WARNED.clear()
        capsys.readouterr()
        out = m.issue_is_closed(cfg_i, "hermes-workflow", 4) if runner is None else \
            m.issue_is_closed(cfg_i, "hermes-workflow", 4, runner=runner)
        assert out is False, f"chemin {expected!r} : on escalade (reçu {out!r})"
        printed = capsys.readouterr().out
        assert printed.strip(), f"chemin {expected!r} : avertissement absent sur stdout"
        assert expected in printed, f"chemin {expected!r} : le message doit le nommer : {printed!r}"
    # états décidables : muets, et la valeur de retour est la décision
    m._WARNED.clear()
    capsys.readouterr()
    assert m.issue_is_closed(cfg, "hermes-workflow", 4,
                             runner=lambda *a, **k: _CP(0, "CLOSED\n", "")) is True
    assert m.issue_is_closed(cfg, "hermes-workflow", 4,
                             runner=lambda *a, **k: _CP(0, "OPEN\n", "")) is False
    assert capsys.readouterr().out == "", "états décidables : aucun avertissement attendu"


# ================================================================== configuration ===

def test_nominal_configuration_lue_dans_le_mapping(m, tmp_path):
    """S1 : le mapping explicite fait foi, l'organisation retombe sur sa constante documentée, et
    « GH_BIN posé vide » reste un état légitime (jamais un repli silencieux)."""
    cfg = _cfg(m, tmp_path, PJ_ESCALATE_ORG="")
    assert (cfg.channel_id, cfg.user_id, cfg.guild_id) == (CHANNEL, USER, GUILD)
    assert cfg.org == m.DEFAULT_ORG, "ORG vide -> constante documentée"
    assert cfg.repos_root == tmp_path / "pj-repos"
    assert cfg.gh_bin == "/bin/gh"
    assert _cfg(m, tmp_path, PJ_ESCALATE_GH_BIN="").gh_bin == "", \
        "une valeur posée vide exprime « garde indisponible », elle n'est pas remplacée"
    # HOME absent du mapping : les défauts dérivent du répertoire personnel réel
    env = {k: v for k, v in _env(tmp_path).items() if k != "HOME"}
    assert str(m.escalation_config(env).state_dir)


@pytest.mark.parametrize("name", REQUIRED)
def test_erreur_configuration_requise_absente_nommee(m, tmp_path, name):
    """S3 (erreur) : chaque requise absente refuse la construction en NOMMANT la variable."""
    env = _env(tmp_path)
    del env[name]
    with pytest.raises(m.ConfigError) as exc:
        m.escalation_config(env)
    assert name in str(exc.value), f"le refus doit nommer {name} : {exc.value!r}"


def test_erreur_validate_config_repertoire_non_inscriptible(m, tmp_path):
    """S3 : la sonde d'écriture de `validate_config` déplace l'échec en TÊTE de tick, en nommant
    la variable — un état non inscriptible ne doit pas se découvrir après les premiers posts."""
    ro = tmp_path / "readonly"
    ro.mkdir()
    ro.chmod(stat.S_IRUSR | stat.S_IXUSR)
    try:
        cfg = _cfg(m, tmp_path, PJ_ESCALATE_STATE_DIR=str(ro / "sub"))
        with pytest.raises(m.ConfigError) as exc:
            m.validate_config(cfg)
        assert "PJ_ESCALATE_STATE_DIR" in str(exc.value), str(exc.value)
    finally:
        ro.chmod(0o755)


# =============================================================== résolution d'issue ===

def test_nominal_resolution_issue_par_tous_les_chemins(m, tmp_path):
    """S1 : clé d'idempotence, URL dans le corps, clé avec tiret, remontée des parents, repli
    board + `#N`, et l'absence de réponse (`None`) quand rien ne désigne l'issue — l'escalade
    signalera « issue inconnue » au lieu de deviner."""
    root = tmp_path / "boards"
    repos_root = _repos(tmp_path)
    db = _make_board(
        root, BOARD,
        [("t_key", "Titre clé", "corps", "pj-dev", "blocked", "pj-dev-1-hermes-workflow-4"),
         ("t_url", "Titre url", "https://github.com/hyron-fr/kerios/issues/9", "pj-dev", "blocked", None),
         ("t_dash", "Titre dash", "corps", "pj-dev", "blocked", "x-kerios-7"),
         ("t_parent", "Titre parent", "corps", "pj-dev", "blocked", None),
         ("t_none", "Titre sans rien #12", "corps", "pj-dev", "blocked", None),
         ("t_orphan", "Titre orphelin", "corps", "pj-dev", "blocked", None)],
        [], [("t_key", "t_parent")])
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    cfg = _cfg(m, tmp_path, PJ_ESCALATE_REPOS_ROOT=str(repos_root))
    repos = m.known_repos(cfg)
    kwargs = {"board": BOARD}
    assert m.resolve_issue(conn, "t_key", repos, **kwargs) == ("hermes-workflow", 4)
    assert m.resolve_issue(conn, "t_url", repos, **kwargs) == ("kerios", 9)
    assert m.resolve_issue(conn, "t_dash", repos, **kwargs) == ("kerios", 7)
    assert m.resolve_issue(conn, "t_parent", repos, **kwargs) == ("hermes-workflow", 4)
    assert m.resolve_issue(conn, "t_none", repos, **kwargs) == ("hermes-workflow", 12), \
        "dernier recours : repo du board + #N dans le titre"
    assert m.resolve_issue(conn, "t_orphan", repos, board="z") is None, \
        "rien ne désigne l'issue -> None (jamais devinée en silence)"
    assert m.resolve_issue(conn, "absent", repos, board="") is None
    conn.close()

    # la racine des repos est OPTIONNELLE : absente, `known_repos` rend la liste de convention
    assert m.known_repos(_cfg(m, tmp_path, PJ_ESCALATE_REPOS_ROOT=str(tmp_path / "nope"))) \
        == sorted(set(m.KNOWN_REPO_NAMES), key=len, reverse=True)
    # tri du plus long au plus court : c'est ce qui fait qu'une clé `x-hermes-experiment-3` ne peut
    # pas être lue comme `hermes-…` — assert sur la PROPRIÉTÉ, jamais sur un nom en position 0.
    longs = m.known_repos(cfg)
    assert longs == sorted(longs, key=len, reverse=True), f"tri attendu : {longs}"
    assert "hermes-workflow" in longs and "kerios" in longs, longs


def test_nominal_index_des_threads_et_ses_deux_doutes(m, tmp_path, capsys):
    """S1/S2 : l'index (repo, issue) -> thread est bâti depuis la sortie du helper ; un helper qui
    échoue (rc non nul) ou qui lève rend un index VIDE et l'annonce, sans jamais casser le tick."""
    cfg = _cfg(m, tmp_path)
    idx = m.thread_index(cfg, runner=lambda *a, **k: _CP(0, THREADS_OUT, ""))
    assert idx == {("hermes-workflow", 4): "111", ("kerios", 7): "112",
                   ("hermes-workflow", 5): "113", ("hermes-workflow", 6): "114"}, \
        f"l'index doit retenir les 4 tickets et ignorer la ligne sans issue : {idx}"

    capsys.readouterr()
    assert m.thread_index(cfg, runner=lambda *a, **k: _CP(2, "", "aide")) == {}
    assert "rc=2" in capsys.readouterr().out, "un helper en échec s'annonce"
    assert m.thread_index(cfg, runner=lambda *a, **k: (_ for _ in ()).throw(OSError("x"))) == {}


def test_limit_etat_de_dedup_par_board(m, tmp_path):
    """S2 : l'état est PAR BOARD (un tick global ne doit pas republier un board déjà escaladé) ;
    un état absent ou corrompu ne fait pas tomber le tick — il repart de zéro."""
    cfg = _cfg(m, tmp_path)
    assert m.load_state(cfg, BOARD) == {}, "état absent"
    m.save_state(cfg, BOARD, {"a": 1})
    assert m.load_state(cfg, BOARD) == {"a": 1}
    assert m.state_path(cfg, BOARD).name == f"pj_escalate_{BOARD}.json"
    assert m.state_path(cfg, "pj-kerios") != m.state_path(cfg, BOARD), "un fichier par board"
    m.state_path(cfg, "pj-casse").write_text("{ pas du json")
    assert m.load_state(cfg, "pj-casse") == {}, "état corrompu -> vide, jamais une exception"


def test_limit_dernier_blocage_et_son_payload(m, tmp_path):
    """S2 : le dernier blocage est celui de plus fort id, son motif est lu dans le payload, et un
    payload illisible ou vide ne fait pas échouer la lecture (motif vide, kind de l'événement)."""
    root = tmp_path / "boards"
    db = _make_board(
        root, BOARD,
        [("t_key", "T", "", "pj-dev", "blocked", None), ("t_noev", "T", "", "pj-dev", "blocked", None),
         ("t_bad", "T", "", "pj-dev", "blocked", None), ("t_empty", "T", "", "pj-dev", "blocked", None)],
        [("t_key", "blocked", '{"kind":"needs_input","reason":"r"}'),
         ("t_key", "block_loop_detected", '{"reason":"plus recent"}'),
         ("t_bad", "blocked", "{{pas du json"),
         ("t_empty", "blocked", "{}")])
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    ev = m.last_block_event(conn, "t_key")
    assert ev[1] == "block_loop_detected" and ev[2] == "plus recent", f"le plus récent fait foi : {ev}"
    assert m.last_block_event(conn, "t_bad")[2] == "", "payload illisible -> motif vide"
    assert m.last_block_event(conn, "t_empty")[1] == "blocked", "kind de l'événement en repli"
    assert m.last_block_event(conn, "t_noev") is None, "aucun blocage -> la carte est sautée"
    conn.close()


# ================================================================ envoi / message ===

def test_nominal_envoi_et_message(m, tmp_path, capsys):
    """S1 : l'envoi n'est réputé réussi que sur rc=0 ET « sent » dans la sortie ; un échec
    s'annonce. Le message nomme le destinataire, la carte, le motif, et signale l'escalade dans le
    canal quand aucun thread dédié n'a été trouvé."""
    cfg = _cfg(m, tmp_path)
    assert m.post(cfg, "T", "m", runner=lambda *a, **k: _CP(0, "sent ok", "")) is True
    assert m.post(cfg, "T", "m", runner=lambda *a, **k: _CP(0, "aucune confirmation", "")) is False, \
        "rc=0 sans confirmation d'envoi n'est pas un succès"
    capsys.readouterr()
    assert m.post(cfg, "T", "m", runner=lambda *a, **k: _CP(3, "", "refus")) is False
    assert "envoi échoué" in capsys.readouterr().out, "un envoi raté s'annonce"

    task = {"id": "t_x", "title": "Titre", "assignee": "pj-dev"}
    dedie = m.build_message(cfg, BOARD, task, "needs_input", "motif", "111")
    assert f"<@{USER}>" in dedie and "t_x" in dedie and "motif" in dedie
    assert "Pas de thread dédié" not in dedie, "thread trouvé : aucun avertissement de repli"
    repli = m.build_message(cfg, BOARD, task, "blocked", "", None)
    assert "Pas de thread dédié" in repli, "sans thread, le message le DIT (jamais deviné en silence)"
    assert "Motif type" in repli, "un motif vide reste annoncé comme tel"


def test_limit_resolution_de_binaire_jamais_le_nom_nu(m, tmp_path):
    """S2 : la résolution rend la chaîne vide quand rien ne passe (jamais le nom nu), et un
    candidat VÉRIFIÉ est retenu — la contre-épreuve interdit une fonction qui rendrait toujours vide."""
    assert m._resolve_bin("zorglub-xyz-inexistant", "/nope/nope") == ""
    assert m._resolve_bin("sh")
    assert m._resolve_bin("zorglub-xyz-inexistant", sys.executable) == sys.executable


# ==================================================================== tick complet ===

def _tick_fixture(m, tmp_path, monkeypatch):
    """Base de test du tick : cinq cartes à trancher couvrant les CHEMINS de résolution d'issue
    (clé, clé d'un autre repo, repli board + `#N`, triage, clé sans thread connu) et les deux
    formes de payload de blocage (JSON exploitable, JSON corrompu)."""
    root = tmp_path / "boards"
    _repos(tmp_path)
    tasks = [
        ("t_a", "Carte A", "corps", "pj-dev", "blocked", "pj-dev-1-hermes-workflow-4"),
        ("t_b", "Carte B", "corps", "pj-dev", "blocked", "pj-dev-2-kerios-7"),
        ("t_c", "Carte C — suite du #5", "corps", "pj-dev", "blocked", None),
        ("t_d", "Carte D", "corps", "pj-dev", "triage", "pj-dev-3-hermes-workflow-6"),
        ("t_e", "Carte E", "corps", "pj-dev", "blocked", "pj-dev-5-hermes-workflow-9"),
    ]
    events = [
        ("t_a", "blocked", '{"kind":"needs_input","reason":"r1"}'),
        ("t_b", "blocked", '{"reason":"r2"}'),
        ("t_c", "blocked", '{"reason":"r3"}'),
        ("t_d", "block_loop_detected", '{"reason":"r4"}'),
        ("t_e", "blocked", "{{pas du json"),
    ]
    _make_board(root, BOARD, tasks, events)
    monkeypatch.setattr(m, KANBAN_ROOT_ATTR, root)
    cfg = _cfg(m, tmp_path, PJ_ESCALATE_REPOS_ROOT=str(tmp_path / "pj-repos"),
               PJ_ESCALATE_STATE_DIR=str(tmp_path / "state"))
    return root, cfg


# thread attendu par carte, calculé par le module (repo, issue) : c'est la table que les cas
# ci-dessous épinglent. Une carte sans thread connu tombe dans le canal configuré.
ATTENDU = {"t_a": "111", "t_b": "112", "t_c": "113", "t_d": "114", "t_e": CHANNEL}


def test_nominal_tick_complet_sur_base_de_test(m, tmp_path, monkeypatch, capsys):
    """S1 : le tick complet, tous seams injectés — un POST par carte à trancher, CHACUNE dans le
    thread de SON ticket, l'état avance, et un tick sans doute ne parle pas. Aucun réseau, aucun
    Discord, aucun `gh` réel."""
    _root, cfg = _tick_fixture(m, tmp_path, monkeypatch)
    runner, posts = _Runner(), []

    def poster(thread_id, message):
        posts.append((thread_id, message))
        return True

    stats = m.run(BOARD, cfg=cfg, runner=runner, poster=poster)
    assert sorted(p["task"] for p in stats["escalated"]) == ["t_a", "t_b", "t_c", "t_d", "t_e"]
    assert stats["errors"] == [] and stats["skipped"] == 0
    par_carte = {t: None for t in ATTENDU}
    for tid, message in posts:
        for task_id in ATTENDU:
            if f"`{task_id}`" in message:
                par_carte[task_id] = tid
    assert par_carte == ATTENDU, f"chaque carte poste dans le thread de SON ticket : {par_carte}"
    assert "issue inconnue" not in " ".join(msg for _, msg in posts), \
        "les cinq cartes désignent une issue : aucune ne doit retomber sur « issue inconnue »"
    assert par_carte["t_e"] == CHANNEL and "Pas de thread dédié" in \
        [msg for tid, msg in posts if tid == CHANNEL][0], \
        "ticket ouvert mais sans thread actif : repli sur le canal, et le message LE DIT"
    state = m.load_state(cfg, BOARD)
    assert sorted(state) == [f"{BOARD}:{t}" for t in ATTENDU], f"état attendu par carte : {state}"
    assert capsys.readouterr().out == "", "un tick nominal sans doute ne parle pas (pas de bruit)"


def test_limit_dedup_et_dry_run_ne_republient_pas(m, tmp_path, monkeypatch, capsys):
    """S2 : deux invariants de non-nuisance — un second tick ne republie rien (dédup par carte et
    par dernier événement), et `--dry-run` n'envoie RIEN tout en ANNONÇANT ce qu'il aurait envoyé."""
    _root, cfg = _tick_fixture(m, tmp_path, monkeypatch)
    posts = []

    def poster(thread_id, message):
        posts.append(thread_id)
        return True

    first = m.run(BOARD, cfg=cfg, runner=_Runner(), poster=poster)
    assert len(first["escalated"]) == 5
    n_after_first = len(posts)
    second = m.run(BOARD, cfg=cfg, runner=_Runner(), poster=poster)
    assert second["escalated"] == [], "un second tick ne republie aucune carte déjà escaladée"
    assert len(posts) == n_after_first, f"aucun post supplémentaire attendu : {posts}"

    m.save_state(cfg, BOARD, {})
    capsys.readouterr()
    stats = m.run(BOARD, dry=True, verbose=True, cfg=cfg, runner=_Runner(), poster=poster)
    out = capsys.readouterr().out
    assert stats["escalated"] == [], "en dry-run rien n'est escaladé"
    assert len(posts) == n_after_first, "en dry-run aucun post n'est émis"
    assert "thread" in out and "ev=" in out, f"le dry-run annonce sa décision : {out!r}"
    assert m.load_state(cfg, BOARD) == {}, "le dry-run n'écrit pas d'état de dédup"


def test_nominal_ticket_clos_et_absence_de_base(m, tmp_path, monkeypatch, capsys):
    """S1 : un ticket CLOS ne réveille plus l'humain — les cartes de #4 et #7 sont marquées
    TRAITÉES sans aucun post dans leurs threads, pendant que les tickets ouverts escaladent
    toujours ; et un board sans base est sauté proprement, sans exception."""
    _root, cfg = _tick_fixture(m, tmp_path, monkeypatch)
    posts = []

    def poster(thread_id, message):
        posts.append((thread_id, message))
        return True

    stats = m.run(BOARD, cfg=cfg, runner=_Runner(closed={"4", "7"}), poster=poster)
    assert sorted(e["task"] for e in stats["escalated"]) == ["t_c", "t_d", "t_e"], \
        f"seules les cartes des tickets OUVERTS escaladent : {stats['escalated']}"
    assert sorted(e["issue"] for e in stats["closed_issue"]) == ["hermes-workflow #4", "kerios #7"]
    assert sorted(tid for tid, _ in posts) == sorted(["113", "114", CHANNEL]), \
        f"aucun post dans le thread d'un ticket clos : {posts}"
    state = m.load_state(cfg, BOARD)
    for task_id in ("t_a", "t_b"):
        assert f"{BOARD}:{task_id}" in state, \
            "une carte à ticket clos est marquée TRAITÉE (jamais repostée au tick suivant)"
    assert m.run("pj-inexistant", cfg=cfg, runner=_Runner(), poster=poster) == \
        {"board": "pj-inexistant", "skipped": "no db"}


def test_erreur_envoi_rate_navance_pas_letat(m, tmp_path, monkeypatch):
    """S3 : un envoi refusé est compté en ERREUR et l'état de dédup n'avance pas — la carte sera
    retentée au tick suivant au lieu d'être perdue en silence."""
    _root, cfg = _tick_fixture(m, tmp_path, monkeypatch)
    stats = m.run(BOARD, cfg=cfg, runner=_Runner(send_ok=False),
                  poster=lambda thread_id, message: False)
    assert sorted(stats["errors"]) == ["t_a", "t_b", "t_c", "t_d", "t_e"], stats
    assert stats["escalated"] == [], "un envoi refusé n'est pas une escalade"
    assert m.load_state(cfg, BOARD) == {}, "état non avancé : la carte sera retentée"


def test_erreur_runner_qui_leve_narrete_pas_le_tick(m, tmp_path, monkeypatch):
    """S3 : un doute sur l'état d'un ticket (exception du runner) n'interrompt PAS le tick — les
    cartes suivantes doivent encore escalader, c'est tout l'enjeu du `except` non propageant."""
    _root, cfg = _tick_fixture(m, tmp_path, monkeypatch)
    posts = []

    def runner(args, **kw):
        if "threads" in args:
            return _CP(0, THREADS_OUT, "")
        if "view" in args:
            raise TimeoutError("gh ne répond pas")
        return _CP(0, "sent ok", "")

    stats = m.run(BOARD, cfg=cfg, runner=runner,
                  poster=lambda t, msg: (posts.append(t), True)[1])
    assert len(stats["escalated"]) == 5, f"le tick continue malgré le doute : {stats}"
    assert len(posts) == 5


def test_limit_seam_conn_factory_et_board_unique(m, tmp_path, monkeypatch):
    """S2 : le seam `conn_factory` est bien celui qui ouvre la base (une fabrique traçante le
    prouve), et le tick n'ouvre qu'une seule connexion."""
    _root, cfg = _tick_fixture(m, tmp_path, monkeypatch)
    opened = []

    def factory(path):
        opened.append(str(path))
        return sqlite3.connect(path)

    stats = m.run(BOARD, cfg=cfg, runner=_Runner(), poster=lambda t, msg: True,
                  conn_factory=factory)
    assert len(opened) == 1, f"une seule connexion par tick : {opened}"
    assert opened[0].endswith(f"{BOARD}/kanban.db")
    assert len(stats["escalated"]) == 5


# ========================================================================== main() ===

def _main_env(tmp_path, **over):
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(("PJ_ESCALATE_", "PJ_BOARD"))}
    env.update({REQUIRED[0]: CHANNEL, REQUIRED[1]: USER, REQUIRED[2]: GUILD,
                "HOME": str(tmp_path / "home"),
                "PJ_ESCALATE_STATE_DIR": str(tmp_path / "state"),
                "PJ_ESCALATE_REPOS_ROOT": str(tmp_path / "pj-repos"),
                "PJ_ESCALATE_THREAD_HELPER": str(tmp_path / "helper.py"),
                "PJ_ESCALATE_GH_BIN": ""})
    env.update(over)
    return env


def test_erreur_main_refus_de_configuration_rc2_sans_effet(m, tmp_path, monkeypatch, capsys):
    """S3 : la configuration refusée arrête le tick AVANT tout scan — rc=2, message nommant la
    variable sur la sortie d'erreur, aucune trace d'exception, aucun état écrit."""
    for k in ("PJ_ESCALATE_CHANNEL_ID", "PJ_ESCALATE_USER_ID", "PJ_ESCALATE_GUILD_ID"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("PJ_ESCALATE_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setattr(m, KANBAN_ROOT_ATTR, tmp_path / "boards-absents")
    capsys.readouterr()
    rc = m.main(["pj_escalate.py"])
    captured = capsys.readouterr()
    assert rc == 2, f"configuration refusée -> rc=2, reçu {rc}"
    assert "PJ_ESCALATE_CHANNEL_ID" in captured.err, captured.err
    assert "Traceback (most recent call last)" not in captured.err, captured.err
    assert not list((tmp_path / "state").rglob("*")) if (tmp_path / "state").exists() else True


def test_nominal_main_board_explicite_et_pj_board(m, tmp_path, monkeypatch, capsys):
    """S1 : `main()` sur un board explicite puis par `PJ_BOARD`, avec un helper Discord factice
    exécuté par le VRAI chemin de sous-processus ; le journal de la base prouve qu'un scan a bien
    eu lieu et que le mode `--dry-run` n'a rien envoyé."""
    _tick_fixture(m, tmp_path, monkeypatch)
    log = tmp_path / "helper.log"
    helper = tmp_path / "helper.py"
    helper.write_text("import sys\n"
                      f"open({str(log)!r}, 'a').write(' '.join(sys.argv[1:]) + '\\n')\n"
                      "print('sent ok' if 'send' in sys.argv[1:] else '')\n")
    env = _main_env(tmp_path, PJ_ESCALATE_THREAD_HELPER=str(helper))
    for k, v in env.items():
        monkeypatch.setenv(k, v)

    capsys.readouterr()
    assert m.main(["pj_escalate.py", "--board", BOARD, "--dry-run", "--verbose"]) == 0
    out = capsys.readouterr().out
    assert "DRY-RUN" in out and "escalade(s) auraient été postées" in out, out
    assert log.read_text().count("threads") >= 1, "le helper de threads a bien été interrogé"
    assert "send" not in log.read_text(), "aucun envoi en dry-run"

    log.write_text("")
    monkeypatch.setenv("PJ_BOARD", BOARD)
    capsys.readouterr()
    assert m.main(["--verbose"]) == 0
    out2 = capsys.readouterr().out
    assert "escalade(s)" in out2, out2


def test_limit_main_scan_des_boards_et_racine_absente(m, tmp_path, monkeypatch, capsys):
    """S2 : sans `--board` ni `PJ_BOARD`, le tick ÉNUMÈRE les boards `pj-*` de la racine (le
    préfixe de convention décide), et une racine absente rend une liste vide — rc=0, silence."""
    root = tmp_path / "boards"
    _repos(tmp_path)
    _make_board(root, BOARD, [("t_a", "Carte A", "", "pj-dev", "blocked", "pj-dev-1-hermes-workflow-4")],
                [("t_a", "blocked", '{"reason":"r"}')])
    (root / "pas-un-board").mkdir(parents=True, exist_ok=True)
    _make_board(root, "pj-kerios", [("t_z", "Carte Z", "", "pj-dev", "blocked", "pj-dev-1-kerios-7")],
                [("t_z", "blocked", '{"reason":"r"}')])
    monkeypatch.setattr(m, KANBAN_ROOT_ATTR, root)
    # helper Discord factice exécuté par le VRAI chemin : il rend l'index des threads (donc un thread
    # par ticket) et confirme ses envois — c'est ce qui rend « telle carte poste dans tel thread »
    # observable sans toucher au réseau.
    helper = tmp_path / "helper.py"
    helper.write_text("import sys\n"
                      "if sys.argv[1:2] == ['threads']:\n"
                      f"    print({THREADS_OUT!r})\n"
                      "elif sys.argv[1:2] == ['send']:\n"
                      "    print('sent ok')\n")
    for k, v in _main_env(tmp_path, PJ_ESCALATE_THREAD_HELPER=str(helper)).items():
        monkeypatch.setenv(k, v)

    posts = []
    monkeypatch.setattr(m, "post", lambda cfg, tid, msg, **kw: (posts.append(tid), True)[1])
    capsys.readouterr()
    assert m.main(["pj_escalate.py", "--verbose"]) == 0
    out = capsys.readouterr().out
    assert f"{BOARD}:" in out and "pj-kerios:" in out, f"les deux boards pj-* sont scannés : {out!r}"
    assert "pas-un-board" not in out, "le préfixe de convention filtre l'énumération"
    assert sorted(posts) == ["111", "112"], \
        f"un post par board, dans le thread de son ticket : {posts}"
    state = m.load_state(m.escalation_config(_main_env(tmp_path)), BOARD)
    assert state, "l'état de dédup est écrit par board"

    monkeypatch.setattr(m, KANBAN_ROOT_ATTR, tmp_path / "aucun-board")
    posts.clear()
    capsys.readouterr()
    assert m.main(["pj_escalate.py"]) == 0
    assert capsys.readouterr().out == "", "racine de boards absente : aucun bruit, rc=0"
    assert posts == [], "aucun board -> aucun post"


def test_erreur_main_helper_de_threads_en_echec_ne_perd_pas_la_decision(m, tmp_path, monkeypatch, capsys):
    """S3 : un helper de threads indisponible n'annule pas l'escalade — les cartes partent dans le
    canal de repli, avec l'avertissement, et le tick sort en rc=0."""
    root = tmp_path / "boards"
    _repos(tmp_path)
    _make_board(root, BOARD, [("t_a", "Carte A", "", "pj-dev", "blocked", "pj-dev-1-hermes-workflow-4")],
                [("t_a", "blocked", '{"reason":"r"}')])
    monkeypatch.setattr(m, KANBAN_ROOT_ATTR, root)
    helper = tmp_path / "helper.py"
    helper.write_text("import sys\nsys.exit(4)\n")
    for k, v in _main_env(tmp_path, PJ_ESCALATE_THREAD_HELPER=str(helper)).items():
        monkeypatch.setenv(k, v)
    posts = []
    monkeypatch.setattr(m, "post", lambda cfg, tid, msg, **kw: (posts.append(tid), True)[1])
    capsys.readouterr()
    assert m.main(["pj_escalate.py", "--verbose"]) == 0
    out = capsys.readouterr().out
    assert posts == [CHANNEL], f"un thread illisible -> repli sur le canal configuré : {posts}"
    assert "rc=4" in out, f"le doute est annoncé : {out!r}"
