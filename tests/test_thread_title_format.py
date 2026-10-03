"""RED — formateur pur du titre #19, slice 3 `titre-4-etats-formateur-pur`.

Ce banc gèle le **contrat d'interface** du formateur arbitré (Q1 = 1a, Q3 = d) : une table
d'états fermée (4 états, bijection état → icône) et une fonction pure qui compose
`<icône> <repo>|#<n>|<titre>` — sans réseau, sans horloge, sans aléa.

Périmètre gelé par `specs/19/slices.json` (slug `titre-4-etats-formateur-pur`) — 3 motifs
couvrants + ce banc :

    pipeline/engine.py                 -> format_title() / title_icon() / TITLE_ICONS
    workflows/spec.yaml                -> clé `status` = la table arbitrée
    workflows/smoke.yaml               -> clé `status` = la table arbitrée
    tests/test_thread_title_format.py  -> ce banc (pj-test)
    tests/test_thread_state_source.py  -> le banc jumeau de la SOURCE d'état

Contrat d'interface exécuté par ce banc (publié en `contrat-3` sur le blackboard) :

    engine.TITLE_ICONS : dict[str, str]            # la table, UNE seule, 4 entrées
        {"startup": "🎬", "in_progress": "⚙️", "blocked": "⚠", "done": "🛑"}

    engine.title_icon(state) -> str                # bijection ; refuse un état inconnu
    engine.format_title(project, ticket, title, state) -> str
        -> "<icône> <project>|#<ticket>|<titre>"
        · l'identité `project|#ticket|` est FIXE d'un état à l'autre : seule l'icône change ;
        · le nom complet reste borné à 100 caractères (borne Discord) et la coupe porte sur
          la FIN du titre : `project|#ticket|` n'est JAMAIS tronqué ;
        · un `|` déjà présent dans le titre d'origine est CONSERVÉ (aucun échappement) :
          `project` et `#ticket` restent les deux premiers segments.

Les codepoints sont ceux écrits par l'humain (relus au GET sur le msg d'arbitrage) :
🎬 U+1F3AC · ⚙️ U+2699 + VS16 (U+FE0F) · ⚠ U+26A0 **sans** VS16 · 🛑 U+1F6D1.
Un banc qui asserterait `⚠️` (avec VS16) verrouillerait un glyphe non conforme : ce banc
asserte les séquences exactes.

Le banc est **pur** : il charge `engine.py` par chemin (avec `pipeline/` sur `sys.path` pour
son import de `backends`) et n'appelle que les fonctions pures. Le sous-processus
(`engine.sh`) est **empoisonné** : si le formateur touchait au réseau ou à l'horloge, le test
échouerait au lieu de passer.

Nature des cas (1 nominal + 1 limite + 1 erreur au minimum) :
  - NOMINAL : les 4 états produisent le format arbitré ; l'identité est fixe d'un état à
    l'autre ; les codepoints sont ceux arbitrés ;
  - LIMITE  : un titre porteur de `|` ne casse pas la grammaire ; un titre long est borné à
    100 car. sans jamais couper l'identité ; un titre vide reste un nom valide (pas de
    placeholder) ;
  - ERREUR  : un état hors table refuse bruyamment (aucune 5ᵉ icône, aucun titre partiel) ;
    l'état « intervention humaine » obsolète (`👆`) n'est jamais produit ; un ticket non
    numérique est refusé.
"""
import importlib.util
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
ENGINE = REPO / "pipeline" / "engine.py"

# ---------------------------------------------------------------- vocabulaire mesuré
PROJECT = "hermes-workflow"
TICKET = 19
TITLE = "Discord thread title and description update"   # titre de l'issue #19 (43 car.)

# La table arbitrée (Q3 = d) — les codepoints exacts écrits par l'humain.
STARTUP, IN_PROGRESS, BLOCKED, DONE = "startup", "in_progress", "blocked", "done"
ICONES = {
    STARTUP: "\U0001f3ac",              # 🎬 démarrage
    IN_PROGRESS: "\u2699\ufe0f",        # ⚙️ in progress (U+2699 + VS16)
    BLOCKED: "\u26a0",                  # ⚠  bloqué (U+26A0 SANS VS16)
    DONE: "\U0001f6d1",                 # 🛑 terminé
}
# Étiquettes humaines (maquette t5) — interdites dès qu'elles portent l'ancien jeu.
LEGACY_LABELS = ("\u2705 done", "\u274c fail", "\U0001f501 retry", "\u2699\ufe0f running")
OBSOLETE_TOKEN = "\U0001f446"           # 👆 — remplacé par ⚠ (Q3 = d), déclaré mort
NAME_MAX = 100                          # borne d'un nom de thread Discord


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
    # `engine.py` importe `backends` (voisin de `pipeline/`) : le dossier doit être sur sys.path.
    return _load(ENGINE, "t3_engine_under_test", extra_path=(REPO / "pipeline",))


def _api(eng_mod, nom):
    """Attribut du contrat, ou échec NOMMANT l'attribut absent (jamais un AttributeError nu)."""
    if not hasattr(eng_mod, nom):
        pytest.fail(
            f"API absente : engine.{nom} — le contrat `contrat-3` l'exige (formateur pur du "
            f"titre : table TITLE_ICONS + title_icon() + format_title())"
        )
    return getattr(eng_mod, nom)


def _table(eng_mod):
    """La table des 4 états, ou échec nommant l'écart (une seule table, 4 entrées)."""
    t = _api(eng_mod, "TITLE_ICONS")
    assert isinstance(t, dict), f"engine.TITLE_ICONS doit être un dict : {type(t).__name__}"
    return t


def _format(eng_mod, state, title=TITLE, project=PROJECT, ticket=TICKET):
    return _api(eng_mod, "format_title")(project, ticket, title, state)


def _identite(project=PROJECT, ticket=TICKET):
    return f"{project}|#{ticket}|"


# ==========================================================================
# A. NOMINAL — les 4 états produisent le format arbitré, l'identité est fixe
# ==========================================================================

def test_nominal_les_4_etats_produisent_le_format_arbitre(eng):
    """NOMINAL — pour chacun des 4 états : `<icône> hermes-workflow|#19|<titre>`, rien d'autre."""
    table = _table(eng)
    assert len(table) == 4, (
        f"la table doit porter EXACTEMENT les 4 états arbitrés (Q3 = d) : {table!r}"
    )
    for state, icone in ICONES.items():
        attendu = f"{icone} {PROJECT}|#{TICKET}|{TITLE}"
        obtenu = _format(eng, state)
        assert obtenu == attendu, (
            f"état `{state}` : attendu {attendu!r}, obtenu {obtenu!r}"
        )
    # Le format de la maquette validée au gate t5, à la lettre.
    assert _format(eng, STARTUP) == (
        "\U0001f3ac hermes-workflow|#19|Discord thread title and description update"
    )


def test_nominal_l_identite_est_fixe_d_un_etat_a_l_autre(eng):
    """NOMINAL — « seule l'icône change » : l'identité `repo|#19|` est identique pour les 4."""
    noms = [_format(eng, state) for state in ICONES]
    identites = {nom.split(" ", 1)[1] for nom in noms}
    assert len(identites) == 1, (
        f"l'identité doit être FIXE d'un état à l'autre (Q1 = 1a) : {sorted(identites)!r}"
    )
    assert identites.pop() == f"{_identite()}{TITLE}"
    icones_vues = [nom.split(" ", 1)[0] for nom in noms]
    assert set(icones_vues) == set(ICONES.values()), (
        f"les 4 icônes doivent apparaître, une par état : {icones_vues!r}"
    )
    assert len(set(icones_vues)) == 4, "bijection : une icône par état, jamais deux fois la même"
    # L'ancien jeu de libellés n'a plus cours (une seule table, celle de Q3 = d).
    for nom in noms:
        for legacy in LEGACY_LABELS:
            assert legacy not in nom, (
                f"l'ancien libellé {legacy!r} survit dans {nom!r} : la table arbitrée le remplace"
            )


def test_nominal_les_codepoints_sont_ceux_arbitres(eng):
    """NOMINAL — ⚠ sans VS16, ⚙️ avec VS16 : ce sont les codepoints écrits par l'humain."""
    assert _api(eng, "title_icon")(BLOCKED) == "\u26a0", (
        "l'état « bloqué » doit porter U+26A0 SANS VS16 (le VS16 verrouillerait un glyphe "
        "non conforme à l'arbitrage Q3 = d)"
    )
    assert "\ufe0f" not in _api(eng, "title_icon")(BLOCKED), "⚠ ne porte pas de VS16"
    assert _api(eng, "title_icon")(IN_PROGRESS) == "\u2699\ufe0f", (
        "l'état « in progress » doit porter U+2699 + VS16 (U+FE0F)"
    )
    assert _api(eng, "title_icon")(STARTUP) == "\U0001f3ac"
    assert _api(eng, "title_icon")(DONE) == "\U0001f6d1"
    # Le formateur est DÉTERMINISTE et PUR : deux appels rendent le même nom, et le
    # sous-processus du module (réseau/helper Discord) n'est jamais touché.
    def _interdit(*a, **k):
        raise AssertionError("le formateur pur ne doit toucher ni au réseau ni à un sous-processus")
    eng.sh = _interdit
    eng.resolve_thread = _interdit
    premiers = [_format(eng, state) for state in ICONES]
    seconds = [_format(eng, state) for state in ICONES]
    assert premiers == seconds, "le formateur doit être déterministe (0 horloge, 0 aléa)"


# ==========================================================================
# B. LIMITE — `|` dans le titre, borne de 100, titre vide
# ==========================================================================

def test_limite_un_titre_porteur_de_pipe_ne_casse_pas_la_grammaire(eng):
    """LIMITE — un `|` dans le titre d'origine est conservé : repo et #n restent 1ᵉʳˢ segments."""
    titre = "bridge|mermaid.min.js ne parse pas|à trancher"
    for state, icone in ICONES.items():
        nom = _format(eng, state, title=titre)
        segments = nom.split("|")
        assert segments[0] == f"{icone} {PROJECT}", (
            f"le 1ᵉʳ segment doit être « {{icône}} {{repo}} » : {segments[0]!r}"
        )
        assert segments[1] == f"#{TICKET}", f"le 2ᵉ segment doit être « #19 » : {segments[1]!r}"
        assert "|".join(segments[2:]) == titre, (
            f"le titre doit CONSERVER ses `|` (aucun échappement) : "
            f"{'|'.join(segments[2:])!r} ≠ {titre!r}"
        )


def test_limite_le_nom_reste_sous_la_borne_et_la_coupe_ne_touche_jamais_l_identite(eng):
    """LIMITE — nom borné à 100 car. ; la coupe porte sur la fin du titre, jamais sur l'identité."""
    titre = "T" * 300
    for state, icone in ICONES.items():
        prefixe = f"{icone} {PROJECT}|#{TICKET}|"
        budget = NAME_MAX - len(prefixe)
        nom = _format(eng, state, title=titre)
        assert len(nom) <= NAME_MAX, (
            f"état `{state}` : nom de {len(nom)} car. > borne Discord {NAME_MAX}"
        )
        assert nom.startswith(prefixe), (
            f"l'identité doit rester EN TÊTE et intacte : {nom[:len(prefixe) + 5]!r}"
        )
        assert nom == prefixe + titre[:budget], (
            f"état `{state}` : la coupe doit porter sur la fin du titre "
            f"(attendu {len(prefixe) + budget} car., obtenu {len(nom)})"
        )


def test_limite_un_titre_vide_donne_un_nom_valide_sans_placeholder(eng):
    """LIMITE — titre vide : l'identité reste, rien n'est inventé (aucun placeholder)."""
    for state, icone in ICONES.items():
        nom = _format(eng, state, title="")
        assert nom == f"{icone} {PROJECT}|#{TICKET}|", (
            f"état `{state}` : titre vide -> {icone} {PROJECT}|#{TICKET}| (pas de placeholder)"
        )
    # Un titre vide reste RÉSOLVABLE par l'ancre d'identité posée par la slice 2.
    assert f"{PROJECT}|#{TICKET}|" in _format(eng, STARTUP, title="")


# ==========================================================================
# C. ERREUR — état hors table, état obsolète, ticket non numérique
# ==========================================================================

def test_erreur_un_etat_inconnu_refuse_bruyamment_sans_titre_partiel(eng):
    """ERREUR — un état hors des 4 fait échouer, en nommant l'état, sans icône inventée."""
    for inconnu in ("retry", "fail", "running", "termin\u00e9", "\U0001f446"):
        with pytest.raises((ValueError, KeyError)) as exc:
            _format(eng, inconnu)
        assert inconnu in str(exc.value), (
            f"le refus doit NOMMER l'état refusé (`{inconnu}`) : {exc.value!r}"
        )
        with pytest.raises((ValueError, KeyError)):
            _api(eng, "title_icon")(inconnu)
    # Aucune 5ᵉ icône : la table est fermée par l'arbitrage humain.
    table = _table(eng)
    assert set(table) == set(ICONES), f"la table doit être exactement les 4 états : {table!r}"
    assert set(table.values()) == set(ICONES.values()), (
        f"les valeurs doivent être exactement les 4 icônes arbitrées : {table!r}"
    )


def test_erreur_l_etat_obsolete_humain_requis_n_est_jamais_produit(eng):
    """ERREUR — `👆` (option a/b écartée par Q3 = d) ne doit être produit par AUCUN état."""
    table = _table(eng)
    for state in table:
        nom = _format(eng, state)
        assert OBSOLETE_TOKEN not in nom, (
            f"l'état `{state}` produit le marqueur obsolète 👆 : l'arbitrage Q3 = d est rendu, "
            f"ce glyphe est mort"
        )
    assert OBSOLETE_TOKEN not in set(table.values()), (
        f"👆 figure dans la table d'icônes : il est déclaré obsolète par Q3 = d"
    )
    for legacy in LEGACY_LABELS:
        assert legacy not in set(table.values()), (
            f"l'ancien libellé {legacy!r} figure dans la table : une seule table, celle de Q3 = d"
        )


def test_erreur_un_ticket_non_numerique_est_refuse(eng):
    """ERREUR — un ticket non numérique n'a pas d'ancre `repo|#n` : refus, jamais `#abc`."""
    for mauvais in ("abc", "", None, 19.5):
        with pytest.raises((ValueError, TypeError, KeyError)) as exc:
            _api(eng, "format_title")(PROJECT, mauvais, TITLE, STARTUP)
        assert str(mauvais) in str(exc.value) or repr(mauvais) in str(exc.value), (
            f"le refus doit NOMMER le ticket refusé ({mauvais!r}) : {exc.value!r}"
        )
