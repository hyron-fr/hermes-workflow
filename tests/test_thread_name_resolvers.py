"""RED — lecteurs du nom de thread #19, slice 2 `lecteurs-nom-deux-formats`.

Ce banc gèle le **contrat d'interface** de l'élargissement (arbitrage humain `1a`) : les
trois lecteurs qui résolvent un fil Discord par son NOM doivent accepter le **nouveau**
format `🎬/⚙️/⚠/🛑 <repo>|#<n>|<titre>` **ET** leur ancien format, sans en résoudre d'autre.

Périmètre gelé par `specs/19/slices.json` (slug `lecteurs-nom-deux-formats`) — 3 motifs + ce banc :

    pipeline/pj_escalate.py                    -> thread_index()      (lecteur 1)
    plugins/pj-buttons/pj-buttons/__init__.py  -> THREAD_NAME_RE      (lecteur 2)
    pipeline/engine.py                         -> resolve_thread()    (lecteur 3)
    tests/test_thread_name_resolvers.py        -> ce banc (pj-test)

Les trois lecteurs NE servent PAS le même vocabulaire : `pj_escalate` et `pj-buttons`
lisent le format « pj » (`hermes-workflow #N · …`), `engine` lit la forme « issue N » /
« Issue #N ». La rétro-compatibilité porte donc sur **l'ancien format de chaque lecteur**,
pas sur un format unique — les remplacer serait une migration, ce que la slice interdit.

Contrat d'interface exécuté par ce banc (à publier en `contrat-2` sur le blackboard) :

    pj_escalate.thread_index(cfg, *, runner=…) -> dict[(repo, issue_int), thread_id]
        · « 🎬 hermes-workflow|#19|… » -> {("hermes-workflow", 19): tid}
        · « hermes-workflow #19 · … »  -> idem (ancien format conservé)
        · « 🎬 hermes-experiment|#19|… » -> {("hermes-experiment", 19): tid}
          (l'attribution suit le repo ÉCRIT, jamais un repo étranger)

    pj_buttons.THREAD_NAME_RE.match(name) -> Match | None, groupes (repo, n)
        · conservée, mêmes groupes qu'avant l'élargissement.

    engine.resolve_thread(n) -> thread_id | None, scopé au repo ÉCRIT (`GH_REPO`)
        · « 🎬 hermes-workflow|#19|… » -> tid pour 19
        · « 🎫 Issue #19 — … »         -> tid (ancien format conservé)
        · « 🎬 hermes-experiment|#19|… » -> None quand on cherche hermes-workflow

Le banc est **pur** : aucun réseau. Chaque lecteur reçoit sa sortie de listage par son
point d'injection (`runner` pour `pj_escalate`, `sh` pour `engine`) ; `pj-buttons` est jugé
sur sa regex publique (la fonction qui l'utilise lance un sous-processus `hermes kanban`,
hors périmètre de ce banc).

Nature des cas (1 nominal + 1 limite + 1 erreur minimum) :
  - NOMINAL  : le nouveau format est résolu par les 3 lecteurs ;
  - LIMITE   : l'ancien format reste résolu à l'identique ; les deux formats COEXISTENT
    dans un même listage ; le numéro voisin 19↔194 n'est pas confondu ; un repo étranger
    n'est pas attribué au repo écouté ;
  - ERREUR   : un numéro inconnu (#9999) ne résout jamais l'issue 19 et aucun lecteur
    n'invente de numéro ; un nom sans ancre d'identité ne résout rien.
"""
import importlib.util
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
PLUGIN = REPO / "plugins" / "pj-buttons" / "pj-buttons" / "__init__.py"
ESCALATE = REPO / "pipeline" / "pj_escalate.py"
ENGINE = REPO / "pipeline" / "engine.py"

# ---------------------------------------------------------------- vocabulaire mesuré
REPO_NAME = "hermes-workflow"
ETRANGER_REPO = "hermes-experiment"
N = 19
VOISIN = 194

# Nouveau format (arbitrage 1a) — les 4 icônes d'état, l'une suffit ici.
NOUVEAU = "🎬 hermes-workflow|#19|Discord thread title and description update"
NOUVEAU_GEAR = "⚙️ hermes-workflow|#19|Discord thread title and description update"
# Anciens formats, PAR lecteur.
ANCIEN_PJ = "hermes-workflow #19 · Discord thread title and description update"
ANCIEN_ENGINE = "🎫 Issue #19 — Discord thread title and description update"
# Cas limites / erreurs.
VOISIN_NOM = "🎬 hermes-workflow|#194|ticket voisin"
ETRANGER_NOM = "🎬 hermes-experiment|#19|ticket d'un autre dépôt"
INCONNU_NOM = "🎬 hermes-workflow|#9999|ticket inconnu"
SANS_IDENTITE = "#19 sans repo ni icône"
LIGNE_SANS_ISSUE = "ligne sans aucune issue"


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
def esc():
    return _load(ESCALATE, "t2_escalate_under_test")


@pytest.fixture(scope="module")
def but():
    return _load(PLUGIN, "t2_pj_buttons_under_test")


@pytest.fixture(scope="module")
def eng():
    # `engine.py` importe `backends` (voisin de `pipeline/`) : le dossier doit être sur sys.path.
    return _load(ENGINE, "t2_engine_under_test", extra_path=(REPO / "pipeline",))


class _CP:
    """Résultat de sous-processus, forme minimale lue par `pj_escalate`."""

    def __init__(self, rc=0, out="", err=""):
        self.returncode, self.stdout, self.stderr = rc, out, err


def _threads(out):
    """Runner injecté : le listage des threads, sans aucun appel réseau."""
    return lambda *a, **k: _CP(0, out, "")


def _cfg(esc_mod, tmp_path, **over):
    """Configuration réelle, construite par la fabrique du module (jamais un faux config)."""
    for name in (REPO_NAME, ETRANGER_REPO):
        (tmp_path / "pj-repos" / name).mkdir(parents=True, exist_ok=True)
    env = {
        "PJ_ESCALATE_CHANNEL_ID": "100000000000000001",
        "PJ_ESCALATE_USER_ID": "200000000000000002",
        "PJ_ESCALATE_GUILD_ID": "300000000000000003",
        "PJ_ESCALATE_REPOS_ROOT": str(tmp_path / "pj-repos"),
        "PJ_ESCALATE_STATE_DIR": str(tmp_path / "state"),
        "PJ_ESCALATE_THREAD_HELPER": str(tmp_path / "thread_helper.py"),
        "PJ_ESCALATE_GH_BIN": "/bin/gh",
    }
    env.update(over)
    return esc_mod.escalation_config(env)


def _index(esc_mod, tmp_path, listing, **over):
    """Index (repo, issue) -> thread bâti depuis un listage injecté."""
    return esc_mod.thread_index(_cfg(esc_mod, tmp_path, **over), runner=_threads(listing))


def _match(but_mod, nom):
    """Match du lecteur 2 sur un nom de fil (None = fil non résolu)."""
    return but_mod.THREAD_NAME_RE.match(nom or "")


def _engine_tid(eng_mod, nom, issue, repo=REPO_NAME):
    """thread_id rendu par le lecteur 3 pour un listage réduit à `nom` ; cache remis à zéro."""
    eng_mod.ISSUE_CHANNEL = "100000000000000001"
    eng_mod.DISCORD_GUILD = "300000000000000003"
    eng_mod.GH_REPO = repo
    eng_mod.sh = lambda *a, **k: f"111 {nom}\n"
    eng_mod._THREAD_CACHE.clear()
    try:
        return eng_mod.resolve_thread(issue)
    finally:
        eng_mod._THREAD_CACHE.clear()


# ==========================================================================
# A. NOMINAL — le nouveau format est résolu par les 3 lecteurs
# ==========================================================================

def test_nominal_thread_index_resout_le_nouveau_format(esc, tmp_path):
    """NOMINAL — lecteur 1 : la forme `repo|#n|` alimente l'index (repo, issue) -> thread."""
    idx = _index(esc, tmp_path, f"111 {NOUVEAU}\n")
    assert idx.get((REPO_NAME, N)) == "111", (
        f"« {NOUVEAU} » doit être résolu en (hermes-workflow, 19) -> « 111 » ; obtenu {idx}"
    )


def test_nominal_pj_buttons_resout_le_nouveau_format(but):
    """NOMINAL — lecteur 2 : la regex rend (repo, n) sur la forme `repo|#n|`."""
    m = _match(but, NOUVEAU)
    assert m is not None, (
        f"THREAD_NAME_RE ne résout pas « {NOUVEAU} » : les boutons de décision d'un fil au "
        f"nouveau format resteraient sans carte cible"
    )
    assert m.group(1) == REPO_NAME, f"repo attendu {REPO_NAME!r} : {m.group(1)!r}"
    assert m.group(2) == str(N), f"numéro d'issue attendu {N} : {m.group(2)!r}"


def test_nominal_engine_resout_le_nouveau_format(eng):
    """NOMINAL — lecteur 3 : `resolve_thread(19)` retrouve le fil au nouveau format."""
    assert _engine_tid(eng, NOUVEAU, N) == "111", (
        f"resolve_thread(19) ne retrouve pas « {NOUVEAU} » : l'étape du pipeline retomberait "
        f"silencieusement sur le canal"
    )


# ==========================================================================
# B. LIMITE — ancien format, coexistence, voisin, repo étranger
# ==========================================================================

def test_limite_l_ancien_format_reste_resolu_par_les_3_lecteurs(esc, tmp_path, but, eng):
    """LIMITE — non-régression : les 18 fils vivants portent l'ANCIEN format de chaque lecteur."""
    idx = _index(esc, tmp_path, f"111 {ANCIEN_PJ}\n")
    assert idx.get((REPO_NAME, N)) == "111", (
        f"l'ancien format « {ANCIEN_PJ} » n'est plus résolu par thread_index : {idx}"
    )

    m = _match(but, ANCIEN_PJ)
    assert m is not None and m.group(1) == REPO_NAME and m.group(2) == str(N), (
        f"l'ancien format n'est plus résolu par THREAD_NAME_RE : "
        f"{m.groups() if m else None}"
    )

    assert _engine_tid(eng, ANCIEN_ENGINE, N) == "111", (
        f"l'ancien format « {ANCIEN_ENGINE} » n'est plus résolu par resolve_thread"
    )


def test_limite_les_deux_formats_coexistent_dans_un_meme_listage(esc, tmp_path):
    """LIMITE — coexistence, pas migration : un listage portant les deux formats rend les deux."""
    idx = _index(esc, tmp_path, f"111 {NOUVEAU}\n112 hermes-workflow #7 · ancien fil\n")
    assert idx.get((REPO_NAME, N)) == "111", f"le nouveau format doit être indexé : {idx}"
    assert idx.get((REPO_NAME, 7)) == "112", (
        f"l'ancien format doit rester indexé en parallèle (18 fils vivants) : {idx}"
    )


def test_limite_le_numero_voisin_194_n_est_pas_confondu_avec_19(esc, tmp_path, but, eng):
    """LIMITE — 19 vs 194 : le motif ne doit pas mordre un chiffre plus long (surdimension)."""
    idx = _index(esc, tmp_path, f"111 {VOISIN_NOM}\n")
    assert idx.get((REPO_NAME, N)) is None, (
        f"« {VOISIN_NOM} » (issue 194) ne doit PAS alimenter l'entrée issue 19 : {idx}"
    )
    assert idx.get((REPO_NAME, VOISIN)) == "111", (
        f"« {VOISIN_NOM} » doit alimenter l'entrée issue 194 : {idx}"
    )

    m = _match(but, VOISIN_NOM)
    assert m is not None and m.group(2) == str(VOISIN), (
        f"THREAD_NAME_RE doit lire 194, jamais 19 : {m.groups() if m else None}"
    )

    assert _engine_tid(eng, VOISIN_NOM, N) is None, (
        "resolve_thread(19) ne doit pas confondre le fil #194 avec l'issue 19"
    )
    assert _engine_tid(eng, VOISIN_NOM, VOISIN) == "111", (
        "resolve_thread(194) doit retrouver le fil #194"
    )


def test_limite_un_repo_etranger_n_est_pas_attribue_au_repo_ecoute(esc, tmp_path, eng):
    """LIMITE — l'attribution suit le repo ÉCRIT : le canal d'issue héberge plusieurs dépôts.

    Mesuré : 18 fils vivants d'au moins deux repos partagent le canal. Un motif élargi sans
    ancre d'identité attribuerait le fil d'un autre dépôt au dépôt écouté — ici hermes-workflow.
    """
    idx = _index(esc, tmp_path, f"111 {ETRANGER_NOM}\n")
    assert idx.get((REPO_NAME, N)) is None, (
        f"« {ETRANGER_NOM} » appartient à {ETRANGER_REPO}, pas à {REPO_NAME} : {idx}"
    )
    assert idx.get((ETRANGER_REPO, N)) == "111", (
        f"« {ETRANGER_NOM} » doit alimenter l'entrée ({ETRANGER_REPO}, 19) : {idx}"
    )

    assert _engine_tid(eng, ETRANGER_NOM, N, repo=REPO_NAME) is None, (
        f"resolve_thread est scopé à GH_REPO={REPO_NAME} : le fil {ETRANGER_REPO} #19 n'est "
        f"pas son fil"
    )


# ==========================================================================
# C. ERREUR — un numéro inconnu ne résout rien, un nom sans identité non plus
# ==========================================================================

def test_erreur_un_numero_inconnu_ne_resout_rien(esc, tmp_path, but, eng):
    """ERREUR — #9999 : aucun lecteur ne le lit comme l'issue 19 et n'invente de numéro."""
    idx = _index(esc, tmp_path, f"111 {INCONNU_NOM}\n")
    assert idx.get((REPO_NAME, N)) is None, (
        f"un fil #9999 ne doit pas alimenter l'entrée issue 19 : {idx}"
    )

    m = _match(but, INCONNU_NOM)
    assert m is not None and m.group(2) == "9999", (
        f"THREAD_NAME_RE doit lire le numéro ÉCRIT (9999), sans en fabriquer un : "
        f"{m.groups() if m else None}"
    )

    assert _engine_tid(eng, INCONNU_NOM, N) is None, (
        "aucun fil ne porte l'issue 19 dans un listage réduit à « #9999 »"
    )


def test_erreur_un_nom_sans_ancre_d_identite_ne_resout_rien(esc, tmp_path, but, eng):
    """ERREUR — garde-fou anti-surdimension : sans `repo|#n|` ni ancien format, rien ne résout."""
    idx = _index(esc, tmp_path, f"111 {SANS_IDENTITE}\n112 {LIGNE_SANS_ISSUE}\n")
    assert (REPO_NAME, N) not in idx, (
        f"« {SANS_IDENTITE} » n'a pas d'ancre d'identité : il ne doit pas alimenter "
        f"(hermes-workflow, 19) : {idx}"
    )
    assert _match(but, SANS_IDENTITE) is None, (
        f"THREAD_NAME_RE ne doit pas mordre un `#19` sans repo : {_match(but, SANS_IDENTITE)}"
    )
    assert _match(but, LIGNE_SANS_ISSUE) is None, "une ligne sans issue reste non résolue"
    assert _engine_tid(eng, SANS_IDENTITE, N) is None, (
        "resolve_thread ne doit pas résoudre un `#19` sans forme d'identité"
    )
