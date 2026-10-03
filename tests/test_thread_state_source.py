"""RED — SOURCE d'état du titre #19, slice 3 `titre-4-etats-formateur-pur` (banc jumeau).

Ce banc gèle l'AUTRE moitié du contrat de la slice 3 : **d'où vient la table des 4 états**.
Le banc `tests/test_thread_title_format.py` juge le formateur pur ; celui-ci juge sa SOURCE et
son CONSOMMATEUR :

  1. les deux workflows (`workflows/spec.yaml`, `workflows/smoke.yaml`) ne portent plus le jeu
     historique `⚙️ running / ✅ done / ❌ fail / 🔁 retry` mais la **table arbitrée** (Q3 = d) ;
  2. `pipeline/engine.py` ne porte plus `DEFAULT_STATUS_LABELS` (une seule table, celle de
     l'arbitrage) : `_status_labels()` ne peut plus rendre un libellé historique par défaut ;
  3. `rename_thread()` n'écrit plus `{label} - issue {N} {title}` (l'ancienne composition) mais
     le nom du **formateur** : `repo|#N|` présent, aucun `- issue N`, aucune icône historique.

Périmètre gelé par `specs/19/slices.json` (slug `titre-4-etats-formateur-pur`) :

    workflows/spec.yaml, workflows/smoke.yaml   -> clé `status` = la table arbitrée
    pipeline/engine.py                          -> plus de DEFAULT_STATUS_LABELS ;
                                                   _status_labels() + rename_thread() sur la table
    tests/test_thread_state_source.py           -> ce banc (pj-test), jumeau du banc du formateur

Contrat d'interface exécuté par ce banc (publié en `contrat-3` sur le blackboard) :

    workflows/*.yaml  clé `status` : dict[str, str] état -> icône arbitrée, EXACTEMENT 4 entrées
    engine._status_labels(wf) -> dict            ne rend JAMAIS un libellé historique ;
                                                 une table absente/vide ne produit aucun libellé mort
    engine.rename_thread(ticket, step, outcome, dry_run, labels) -> None
                                                 écrit un nom au format arbitré (jamais `- issue N`)

Le banc est **pur** : il lit les deux YAML par leur chemin et injecte `sh`/`resolve_thread` pour
capturer le nom écrit — aucun réseau, aucune horloge, aucun sous-processus réel. Les deux YAML
sont jugés ENSEMBLE : c'est le risque nommé par la carte dev (« la clé `status` est lue par le
moteur — un banc qui ne juge que `spec.yaml` raterait `smoke.yaml` »).

Nature des cas (1 nominal + 1 limite + 1 erreur minimum) :
  - NOMINAL : les deux YAML portent les 4 états avec leurs icônes exactes ; `_status_labels`
    rend la même table pour les deux ; `rename_thread` écrit un nom porteur de `repo|#N|` ;
  - LIMITE  : `running`/`done` gardent leur sens humain (⚙️ in progress / 🛑 terminé) ; un
    workflow tiers portant la table arbitrée est accepté tel quel, sans dépendre des 2 fichiers ;
  - ERREUR  : un workflow sans table arbitrée ne produit AUCUN libellé historique (le défaut
    `⚙️ running`/`✅ done` d'aujourd'hui est mort) ; `DEFAULT_STATUS_LABELS` a disparu du module.
"""
import importlib.util
import re
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[1]
ENGINE = REPO / "pipeline" / "engine.py"
WORKFLOWS = (REPO / "workflows" / "spec.yaml", REPO / "workflows" / "smoke.yaml")

# ---------------------------------------------------------------- vocabulaire mesuré
PROJECT = "hermes-workflow"
TICKET = 19
TITLE = "Discord thread title and description update"
STARTUP, IN_PROGRESS, BLOCKED, DONE = "startup", "in_progress", "blocked", "done"
ICONES = {
    STARTUP: "\U0001f3ac",              # 🎬 démarrage
    IN_PROGRESS: "\u2699\ufe0f",        # ⚙️ in progress (U+2699 + VS16)
    BLOCKED: "\u26a0",                  # ⚠  bloqué (U+26A0 SANS VS16)
    DONE: "\U0001f6d1",                 # 🛑 terminé
}
# Le jeu historique (workflows/{spec,smoke}.yaml avant #19) : mort après l'arbitrage Q3 = d.
HISTORIQUES = ("\u2699\ufe0f running", "\u2705 done", "\u274c fail", "\U0001f501 retry")
OBSOLETE_TOKEN = "\U0001f446"           # 👆 — écarté par Q3 = d
# L'ancienne composition du moteur, remplacée par le formateur arbitré.
ANCIENNE_COMPOSITION = re.compile(r"-\s*issue\s+\d+")


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
def eng():
    return _load(ENGINE, "t3b_engine_under_test", extra_path=(REPO / "pipeline",))


def _wf(path):
    """Workflow chargé depuis son fichier, sans l'écrire ni le muter."""
    if not path.is_file():
        pytest.fail(f"workflow sous test absent : {path}")
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _api(eng_mod, nom):
    if not hasattr(eng_mod, nom):
        pytest.fail(
            f"API absente : engine.{nom} — le contrat `contrat-3` l'exige (la table des 4 états "
            f"est la SOURCE du formateur)"
        )
    return getattr(eng_mod, nom)


def _table(wf, path):
    """Table `status` du YAML, ou échec nommant le fichier et la clé absente."""
    table = wf.get("status")
    assert isinstance(table, dict) and table, (
        f"{path.name} : la clé `status` doit porter la table arbitrée (4 états) : {table!r}"
    )
    return table


def _capture_nom(eng_mod, outcome, labels):
    """Nom écrit par `rename_thread`, capturé par injections (`resolve_thread` + `sh`)."""
    if not hasattr(eng_mod, "rename_thread"):
        pytest.fail("API absente : engine.rename_thread — le formateur doit être son consommateur")
    ecrits = []
    eng_mod.resolve_thread = lambda n: "1470000000000000001"
    eng_mod.sh = lambda cmd, **k: (ecrits.append(cmd) or "")
    ticket = {"issue_number": TICKET, "title": TITLE, "repo": PROJECT}
    eng_mod.rename_thread(ticket, {}, outcome, False, labels)
    assert len(ecrits) == 1, (
        f"rename_thread(`{outcome}`) doit écrire UN nom (best-effort), écrit : {len(ecrits)}"
    )
    cmd = ecrits[-1]
    # `[sys.executable, helper, "rename", thread_id, name]` : le nom est le dernier argument.
    assert cmd[-3] == "rename", f"la sous-commande attendue est `rename` : {cmd!r}"
    return cmd[-1]


# ==========================================================================
# A. NOMINAL — la table arbitrée est dans les DEUX YAML, lue par le moteur
# ==========================================================================

def test_nominal_les_deux_workflows_portent_la_table_arbitree():
    """NOMINAL — `spec.yaml` ET `smoke.yaml` portent les 4 états et leurs icônes exactes."""
    for path in WORKFLOWS:
        table = _table(_wf(path), path)
        assert set(table) == set(ICONES), (
            f"{path.name} : la table `status` doit porter EXACTEMENT les 4 états arbitrés "
            f"(Q3 = d) : {sorted(table)!r}"
        )
        for state, icone in ICONES.items():
            valeur = str(table[state])
            assert valeur.split(" ", 1)[0] == icone, (
                f"{path.name} : état `{state}` -> {valeur!r} ; l'icône arbitrée est {icone!r}"
            )


def test_nominal_le_moteur_lit_la_meme_table_pour_les_deux_workflows(eng):
    """NOMINAL — `_status_labels()` rend la table arbitrée, identique pour les deux workflows."""
    labels_fn = _api(eng, "_status_labels")
    for path in WORKFLOWS:
        labels = labels_fn(_wf(path))
        assert isinstance(labels, dict), f"{path.name} : `_status_labels` doit rendre un dict"
        for state in ICONES:
            assert state in labels, (
                f"{path.name} : l'état arbitré `{state}` doit être lisible par le moteur : "
                f"{sorted(labels)!r}"
            )
            assert str(labels[state]).split(" ", 1)[0] == ICONES[state], (
                f"{path.name} : `_status_labels()[{state}]` = {labels[state]!r} "
                f"(icône attendue {ICONES[state]!r})"
            )


def test_nominal_rename_thread_ecrit_le_format_arbitre(eng):
    """NOMINAL — le nom écrit porte `repo|#N|` : le formateur est bien le consommateur."""
    labels = _api(eng, "_status_labels")(_wf(WORKFLOWS[0]))
    nom = _capture_nom(eng, "running", labels)
    assert f"{PROJECT}|#{TICKET}|" in nom, (
        f"rename_thread doit écrire un nom au format arbitré (`{PROJECT}|#{TICKET}|`) : {nom!r}"
    )
    icones_arbitrees = {" ".join(nom.split(" ", 1)[:1]): None}
    assert nom.split(" ", 1)[0] in set(ICONES.values()), (
        f"le nom doit commencer par l'une des 4 icônes arbitrées : {nom!r}"
    )
    assert not ANCIENNE_COMPOSITION.search(nom), (
        f"l'ancienne composition `- issue N` survit dans {nom!r}"
    )


# ==========================================================================
# B. LIMITE — le sens humain de running/done, et un workflow tiers
# ==========================================================================

def test_limite_running_et_done_gardent_leur_sens_humain(eng):
    """LIMITE — Q3 = d : « in progress (dév en cours) » = running ; « terminé » = done."""
    labels = _api(eng, "_status_labels")(_wf(WORKFLOWS[0]))
    nom_running = _capture_nom(eng, "running", labels)
    nom_done = _capture_nom(eng, "done", labels)
    assert nom_running.split(" ", 1)[0] == ICONES[IN_PROGRESS], (
        f"l'étape en cours doit porter ⚙️ in progress : {nom_running!r}"
    )
    assert nom_done.split(" ", 1)[0] == ICONES[DONE], (
        f"l'étape terminée doit porter 🛑 terminé : {nom_done!r}"
    )
    assert nom_running != nom_done, "deux états distincts ne peuvent pas produire le même nom"


def test_limite_un_workflow_tiers_portant_la_table_arbitree_est_accepte(eng):
    """LIMITE — la table est une DONNÉE : un 3ᵉ workflow la porte et est lu SANS pollution.

    Un workflow tiers (hors des 2 fichiers de la slice) qui déclare les 4 états arbitrés doit
    être lu tel quel : le moteur ne doit pas y ré-injecter un jeu de libellés historique.
    """
    tiers = {"status": dict(ICONES), "steps": [{"id": "x", "type": "deterministic",
                                                "command": "true"}]}
    labels = _api(eng, "_status_labels")(tiers)
    for state, icone in ICONES.items():
        assert str(labels[state]).split(" ", 1)[0] == icone, (
            f"un workflow tiers portant la table arbitrée doit être lu tel quel : "
            f"{labels.get(state)!r}"
        )
    assert set(labels) == set(ICONES), (
        f"un workflow tiers portant les 4 états ne doit pas être pollué par un jeu hérité : "
        f"{sorted(labels)!r}"
    )


# ==========================================================================
# C. ERREUR — plus de table historique par défaut, plus de DEFAULT_STATUS_LABELS
# ==========================================================================

def test_erreur_un_workflow_sans_table_ne_produit_aucun_libelle_historique(eng):
    """ERREUR — le défaut historique (`⚙️ running`/`✅ done`) est mort : jamais de repli silencieux."""
    labels_fn = _api(eng, "_status_labels")
    try:
        labels = labels_fn({}) or {}
    except (ValueError, KeyError) as exc:
        # Un refus bruyant est conforme, à condition qu'il soit exploitable.
        assert str(exc), f"le refus d'une table absente doit être explicite : {exc!r}"
        return
    assert isinstance(labels, dict), f"`_status_labels({{}})` doit rendre un dict : {labels!r}"
    for legacy in HISTORIQUES:
        assert legacy not in labels.values(), (
            f"une table absente rend le libellé historique {legacy!r} : l'ancien jeu doit être "
            f"supprimé, pas laissé en repli (arbitrage Q3 = d)"
        )


def test_erreur_le_jeu_historique_du_moteur_a_disparu(eng):
    """ERREUR — `DEFAULT_STATUS_LABELS` (⚙️ running / ✅ done / ❌ fail / 🔁 retry) n'existe plus."""
    assert not hasattr(eng, "DEFAULT_STATUS_LABELS"), (
        "engine.DEFAULT_STATUS_LABELS survit : une SEULE table doit rester, celle de Q3 = d "
        f"({getattr(eng, 'DEFAULT_STATUS_LABELS', None)!r})"
    )
    for path in WORKFLOWS:
        table = _table(_wf(path), path)
        for legacy in HISTORIQUES:
            assert legacy not in {str(v) for v in table.values()}, (
                f"{path.name} : le libellé historique {legacy!r} survit dans la table `status`"
            )
        assert OBSOLETE_TOKEN not in {str(v) for v in table.values()}, (
            f"{path.name} : le marqueur obsolète 👆 figure dans la table (écarté par Q3 = d)"
        )
