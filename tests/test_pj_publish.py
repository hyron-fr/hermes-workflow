"""Banc RED de la slice 3/3 (#4) : la copie installée est publiée, et son identité est contrôlée.

Dérivé de (R1) — la source qui fait foi est l'artefact ratifié, pas le corps de l'issue :

- Gherkin de la carte `t_75f8497b` (nominal aligné / limite wrapper sans export / erreur paire
  divergente) et §4 « le contrat figé par `dev-3` : une fonction de comparaison PURE (deux contenus
  en entrée -> verdict + digest) et une fonction de vérification du wrapper (contenu de wrapper +
  liste de variables requises -> variables manquantes) » ;
- corps de la carte sœur `t_f1072d8c` (§4) pour l'interface en ligne de commande et le sens des
  codes de sortie : 0 = conforme, 1 = écart, 2 = erreur d'exécution, aucune écriture en `--check` ;
- arbitrages D9 (org optionnel), D10 (aucune écriture consommante sur une branche de doute),
  D12 (requise absente **ou vide** = absente), D15 (`pj_publish.py`, modes `--check` / `--publish`,
  la bascule est refusée tant que les REQUIS ne sont pas exportés) ;
- `docs/architecture/components/pj-escalate.md` (contrat de variables de la slice 1).

Nature des cas : nominal (paire alignée -> rc 0 + digest imprimé + zéro écriture ; la comparaison
pure juge l'identité ; le wrapper littéral passe le contrôle des exports), limite (wrapper sans
export refusé AVANT la bascule ; une seule variable manquante parmi trois est la seule nommée ; une
simple mention en commentaire ne vaut pas un export ; le wrapper versionné du dépôt n'est pas
refusé ; une cible divergente parmi deux refuse l'ensemble), erreur (cible absente ou non-fichier
-> rc 2 sans fausse identité ; paire divergente -> rc 1 avec les DEUX digests et le compte de lignes
divergentes ; la comparaison pure distingue identité et divergence).

Deux points de méthode, écrits ici parce qu'ils décident de la valeur du banc :

1. **Le discriminant de « le digest des DEUX fichiers » est le cas divergent.** Sur une paire
   alignée, les deux digests sont égaux : un outil qui n'en imprime qu'un seul passe l'assertion.
   Le cas d'erreur 2 est donc le seul qui juge la phrase « imprime les deux digest » — il compare
   deux empreintes distinctes.
2. **L'identité se mesure APRÈS injection des variables** (arbitrage `2a`, §4 de la carte dev) : la
   copie versionnée est assainie, donc un contrôle octet à octet sur les sources brutes serait faux.
   La paire alignée de ce banc représente déjà la copie *telle qu'elle s'exécute*.

Aucun test ne lit le texte source du module testé (règle CONTRIBUTING : un test qui lit le texte
source est refusé) : l'API est appelée, la sortie est capturée. Aucun chemin absolu de machine :
les fixtures vivent sous `tmp_path`, et le seul chemin de dépôt cité est relatif à `REPO`.
Aucune horloge réelle, aucun aléa, aucun accès réseau.

Module testé : `pipeline/pj_publish.py`, chargé **par chemin**, avec l'override `PJ_PUBLISH_COPY`
qui permet de rejouer ce banc sur une copie publiée (et de mesurer le RED sur un module absent).
"""
import hashlib
import importlib.util
import os
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

import pytest  # noqa: E402

# --------------------------------------------------------------- contrat pinné ---
# 1. module sous test : foyer canonique `pipeline/` (D1). `PJ_PUBLISH_COPY` rejoue le banc ailleurs.
TARGET = (Path(os.environ["PJ_PUBLISH_COPY"]) if os.environ.get("PJ_PUBLISH_COPY")
          else REPO / "pipeline" / "pj_publish.py")
# 2. fonction de comparaison PURE : deux contenus en entrée -> verdict
COMPARE_FN = "compare_copies"
# 3. champs du verdict rendu par COMPARE_FN (accès par ATTRIBUT ou par clé, les deux acceptés)
V_IDENTICAL = "identical"           # bool : les deux contenus sont identiques
V_INSTALLED = "installed_digest"    # empreinte de la copie installée (hexadécimal)
V_VERSIONED = "versioned_digest"    # empreinte de la copie versionnée (hexadécimal)
V_LINES = "divergent_lines"         # int : nombre de lignes divergentes (0 si identiques)
# 4. algorithme d'empreinte (64 caractères hexadécimaux minuscules)
DIGEST_ALGO = "sha256"
# 5. fonction de vérification du wrapper : (contenu, liste de requises) -> variables manquantes
MISSING_FN = "missing_exports"
# 6. interface en ligne de commande du mode contrôle / publication
CLI_SOURCE, CLI_TARGET = "--source", "--target"
CLI_WRAPPER, CLI_REQUIRE_ENV = "--wrapper", "--require-env"
CLI_CHECK, CLI_PUBLISH = "--check", "--publish"
# 7. séparateur de la liste passée à `--require-env` (une seule occurrence du drapeau)
REQUIRE_ENV_SEPARATOR = ","
# 8. codes de sortie : conforme / écart / erreur d'exécution
EXIT_OK, EXIT_GAP, EXIT_ERROR = 0, 1, 2
# 9. variables requises du contrat de la slice 1 (les noms seuls : aucune valeur n'est dans le dépôt)
REQUIRED = ("PJ_ESCALATE_CHANNEL_ID", "PJ_ESCALATE_USER_ID", "PJ_ESCALATE_GUILD_ID")
REQUIRE_ENV_VALUE = REQUIRE_ENV_SEPARATOR.join(REQUIRED)
# 10. wrapper versionné du dépôt — la cible du geste humain, créée par la slice 1
WRAPPER_VERSIONNE = REPO / "agents" / "pj-master" / "scripts" / "pj_escalate_all.sh"

# ------------------------------------------------------------------ fixtures ---
# Copie versionnée ASSAINIE (mise en forme réduite : le sujet ici est l'identité, pas le code).
VERSIONED = "".join(f"ligne {i:02d}\n" for i in range(1, 11))


def _with_lines(changed):
    """Copie versionnée dont certaines lignes (1-indexées) sont remplacées."""
    lines = VERSIONED.splitlines(keepends=True)
    for idx, repl in changed.items():
        lines[idx - 1] = repl + "\n"
    return "".join(lines)


# une seule ligne divergente : les définitions « positions qui diffèrent » et « morceaux de diff »
# s'accordent sur 1 — le compte est donc non ambigu
DIVERGENT_1 = _with_lines({7: "ligne 07 — divergente"})
# trois lignes divergentes, non contiguës : les deux définitions s'accordent encore (3)
DIVERGENT_3 = _with_lines({3: "ligne 03 — divergente", 5: "ligne 05 — divergente",
                           7: "ligne 07 — divergente"})

# Wrapper conforme : trois `export` LITTÉRAUX, avec repli non vide (une valeur vide compte comme
# absente — D12 —, donc un wrapper conforme doit fournir une valeur).
W_LITERAL = (
    "#!/usr/bin/env bash\n"
    "set -u\n"
    'export PJ_ESCALATE_CHANNEL_ID="${PJ_ESCALATE_CHANNEL_ID:-100000000000000001}"\n'
    'export PJ_ESCALATE_USER_ID="${PJ_ESCALATE_USER_ID:-200000000000000002}"\n'
    'export PJ_ESCALATE_GUILD_ID="${PJ_ESCALATE_GUILD_ID:-300000000000000003}"\n'
    'exec python3 "$HOME/.hermes/profiles/pj-master/scripts/pj_escalate.py" "$@"\n'
)
# Wrapper fautif : la forme que la slice 3 combat — il n'exporte RIEN (aucune mention des requises).
W_BARE = (
    "#!/usr/bin/env bash\n"
    "# Cron pj-escalate.\n"
    'exec python3 "$HOME/.hermes/profiles/pj-master/scripts/pj_escalate.py"\n'
)
# Wrapper partiel : deux exports sur trois — seule la troisième doit être nommée.
W_PARTIAL = (
    "#!/usr/bin/env bash\n"
    "set -u\n"
    'export PJ_ESCALATE_CHANNEL_ID="${PJ_ESCALATE_CHANNEL_ID:-100000000000000001}"\n'
    'export PJ_ESCALATE_USER_ID="${PJ_ESCALATE_USER_ID:-200000000000000002}"\n'
    'exec python3 "$HOME/.hermes/profiles/pj-master/scripts/pj_escalate.py" "$@"\n'
)
# Wrapper dont les trois `export` sont COMMENTÉS — la forme la plus dangereuse : elle ressemble au
# livrable (les noms y sont, la ligne `export` y est) mais elle n'exporte rien. C'est le faux positif
# que le contrôle doit refuser, et il est atteignable en une frappe (l'humain commente la ligne).
W_COMMENT_ONLY = (
    "#!/usr/bin/env bash\n"
    "# REQUISES      PJ_ESCALATE_CHANNEL_ID, PJ_ESCALATE_USER_ID, PJ_ESCALATE_GUILD_ID\n"
    "# export PJ_ESCALATE_CHANNEL_ID=\"100000000000000001\"\n"
    "# export PJ_ESCALATE_USER_ID=\"200000000000000002\"\n"
    "# export PJ_ESCALATE_GUILD_ID=\"300000000000000003\"\n"
    'exec python3 "$HOME/.hermes/profiles/pj-master/scripts/pj_escalate.py"\n'
)
# Wrapper dont l'affectation n'est PAS exportée (`VAR=…` sans `export`) : la variable est définie
# pour le shell mais n'entre PAS dans l'environnement du tick — le défaut visé par le contrat.
W_ASSIGN_ONLY = (
    "#!/usr/bin/env bash\n"
    "PJ_ESCALATE_CHANNEL_ID=\"100000000000000001\"\n"
    "PJ_ESCALATE_USER_ID=\"200000000000000002\"\n"
    "PJ_ESCALATE_GUILD_ID=\"300000000000000003\"\n"
    'exec python3 "$HOME/.hermes/profiles/pj-master/scripts/pj_escalate.py"\n'
)


def _load(path, name="pj_publish_under_test"):
    """Charge le module par chemin ; échoue en ERROR (pas en SKIP) s'il n'existe pas (R4)."""
    if not path.exists():
        pytest.fail(f"module absent: {path}")
    spec = importlib.util.spec_from_file_location(name, str(path))
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    # `spec_from_file_location` ne met PAS le dossier du module sur sys.path : ses imports frères
    # échoueraient ici alors qu'ils passent au lancement par chemin.
    sys.path.insert(0, str(path.parent))
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.path.remove(str(path.parent))
    return mod


@pytest.fixture(scope="module")
def pub():
    return _load(TARGET)


@pytest.fixture(autouse=True)
def _module_attendu():
    """Garde-fou de la preuve : sans le module, l'échec doit être « module absent » — jamais un
    sous-processus qui rend 2 parce que `python3` n'a pas trouvé le fichier."""
    if not TARGET.exists():
        pytest.fail(f"module absent: {TARGET}")


def _field(verdict, name):
    """Lit un champ du verdict, par ATTRIBUT (dataclass) ou par CLÉ (mapping)."""
    if hasattr(verdict, name):
        return getattr(verdict, name)
    try:
        return verdict[name]
    except TypeError:
        raise AssertionError(f"le verdict {verdict!r} ne porte pas le champ {name!r}")


def _sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _run(args, cwd, home):
    """Lance l'outil : environnement neutralisé (`PJ_ESCALATE_*` retiré), `HOME` confiné."""
    env = {k: v for k, v in os.environ.items()
           if not k.startswith("PJ_ESCALATE_") and k != "PJ_PUBLISH_COPY"}
    env["HOME"] = str(home)
    return subprocess.run([sys.executable, str(TARGET), *args], cwd=str(cwd), env=env,
                          capture_output=True, text=True, timeout=60)


def _files_under(path):
    root = Path(path)
    if not root.exists():
        return []
    return sorted(p for p in root.rglob("*") if p.is_file())


def _snapshot(root):
    """État absolu du bac à sable : {chemin relatif -> empreinte}. Toute écriture, y compris un
    fichier NEUF, fait échouer la comparaison (un simple « rien n'a été modifié » ne voit pas une
    création)."""
    root = Path(root)
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in _files_under(root)}


def _count_reported(text, expected, noise=()):
    """Le compte de lignes divergentes est cherché parmi les entiers des lignes qui PARLENT de
    divergence : les chiffres noyés dans une empreinte hexadécimale ou dans un chemin de fixture
    ne comptent pas (un `1` dans `/tmp/pytest-12/test_x1/` serait un faux positif)."""
    found = []
    for line in text.splitlines():
        if "diverg" not in line.lower():
            continue
        clean = re.sub(r"[0-9a-f]{32,}", " ", line)
        for token in noise:
            clean = clean.replace(str(token), " ")
        found.extend(int(n) for n in re.findall(r"(?<![\w./-])(\d+)(?![\w./-])", clean))
    return expected in found, found


class _Bac:
    """Bac à sable : copie versionnée, copie installée, wrapper — sous `tmp_path`."""

    def __init__(self, tmp_path):
        self.root = Path(tmp_path)
        self.home = self.root / "home"
        self.home.mkdir()
        self.source = self.root / "versionnee.py"
        self.target = self.root / "installee.py"
        self.wrapper = self.root / "pj_escalate_all.sh"

    def write(self, versioned, installed, wrapper=W_LITERAL):
        self.source.write_text(versioned, encoding="utf-8")
        self.target.write_text(installed, encoding="utf-8")
        self.wrapper.write_text(wrapper, encoding="utf-8")
        return self

    def args(self, *extra, check=True):
        flags = [CLI_CHECK] if check else []
        return [*flags, CLI_SOURCE, str(self.source), CLI_TARGET, str(self.target),
                CLI_WRAPPER, str(self.wrapper), CLI_REQUIRE_ENV, REQUIRE_ENV_VALUE, *extra]

    def run(self, *extra, check=True):
        return _run(self.args(*extra, check=check), self.root, self.home)

    @property
    def target_sha(self):
        return hashlib.sha256(self.target.read_bytes()).hexdigest()


# ----------------------------------------------------------------------- nominal ---

def test_nominal_le_controle_d_une_paire_alignee_sort_0_et_imprime_le_digest(tmp_path):
    """S1 : paire alignée -> code 0, l'empreinte du contenu est imprimée, et RIEN n'est écrit."""
    bac = _Bac(tmp_path).write(VERSIONED, VERSIONED)
    avant = _snapshot(tmp_path)
    proc = bac.run()
    sortie = proc.stdout + proc.stderr
    assert proc.returncode == EXIT_OK, (
        f"paire alignée : rc={proc.returncode}\nstdout={proc.stdout}\nstderr={proc.stderr}")
    assert _sha(VERSIONED) in sortie, (
        f"le contrôle doit imprimer l'empreinte de la copie comparée\n{sortie}")
    assert "Traceback (most recent call last)" not in proc.stderr, proc.stderr
    assert _snapshot(tmp_path) == avant, (
        "le mode contrôle est en LECTURE SEULE : aucune écriture, aucun fichier neuf")
    assert _files_under(bac.home) == [], "aucune écriture sous HOME attendue"


def test_nominal_le_mode_controle_est_le_defaut(tmp_path):
    """S1 : sans `--check`, l'outil ne bascule pas — le défaut est le mode lecture seule."""
    bac = _Bac(tmp_path).write(VERSIONED, VERSIONED)
    avant = _snapshot(tmp_path)
    proc = bac.run(check=False)
    assert proc.returncode == EXIT_OK, (
        f"mode par défaut : rc={proc.returncode}\nstdout={proc.stdout}\nstderr={proc.stderr}")
    assert _snapshot(tmp_path) == avant, "le mode par défaut ne doit rien basculer"


def test_nominal_le_controle_n_ecrit_rien_meme_a_cote_de_son_propre_module(tmp_path):
    """S1 : « il n'écrit rien sur disque » — y compris à côté de SON PROPRE module.

    Mesuré : un mutant qui écrit `Path(__file__).parent / "pj_publish_check.log"` SURVIT au banc
    qui ne surveillait que le bac à sable — la garde regardait un seul répertoire. Ici le module
    sous test est **exécuté depuis une copie placée dans le bac à sable** : son `__file__` y est, et
    l'instantané global (fichiers du bac + fichiers du dossier du module) voit l'écriture. Aucun
    répertoire partagé n'est surveillé : la mesure reste déterministe malgré le pair.
    """
    outil = tmp_path / "outil"
    outil.mkdir()
    (outil / "pj_publish.py").write_bytes(TARGET.read_bytes())
    bac = _Bac(tmp_path).write(VERSIONED, VERSIONED)
    avant = _snapshot(tmp_path)
    env = {k: v for k, v in os.environ.items()
           if not k.startswith("PJ_ESCALATE_") and k != "PJ_PUBLISH_COPY"}
    env["HOME"] = str(bac.home)
    proc = subprocess.run([sys.executable, str(outil / "pj_publish.py"), *bac.args()],
                          cwd=str(tmp_path), env=env, capture_output=True, text=True, timeout=60)
    assert proc.returncode == EXIT_OK, (
        f"contrôle sur une copie du module dans le bac : rc={proc.returncode}\n"
        f"stdout={proc.stdout}\nstderr={proc.stderr}")
    assert _snapshot(tmp_path) == avant, (
        "le mode contrôle écrit quelque chose : "
        f"{sorted(set(_snapshot(tmp_path)) - set(avant))}")


def test_nominal_la_comparaison_pure_juge_l_identite_sans_ecrire(pub, tmp_path):
    """S1, au niveau de la fonction : deux contenus identiques -> verdict d'identité, 0 divergente."""
    avant = _snapshot(tmp_path)
    verdict = getattr(pub, COMPARE_FN)(VERSIONED, VERSIONED)
    assert _field(verdict, V_IDENTICAL) is True, f"verdict={verdict!r}"
    assert _sha(VERSIONED) in str(_field(verdict, V_INSTALLED)), f"verdict={verdict!r}"
    assert _sha(VERSIONED) in str(_field(verdict, V_VERSIONED)), f"verdict={verdict!r}"
    assert int(_field(verdict, V_LINES)) == 0, f"verdict={verdict!r}"
    assert _snapshot(tmp_path) == avant, "la comparaison est PURE : aucune écriture"


def test_nominal_la_verification_du_wrapper_accepte_les_exports_litteraux(pub, tmp_path):
    """S1 : un wrapper qui porte les trois exports littéraux n'a aucune variable manquante."""
    manquantes = tuple(getattr(pub, MISSING_FN)(W_LITERAL, REQUIRED))
    assert manquantes == (), f"variables signalées à tort : {manquantes!r}"


def test_nominal_le_geste_humain_rejoue_sur_fixtures_etablit_l_identite(tmp_path):
    """S1 (geste complet, sur fixtures) : `--publish` bascule, puis le contrôle rend 0.

    L'ordre du geste est un garde-fou : (1) `--check`, (2) les `export` requis, (3) re-contrôle,
    (4) publication. Ici la copie installée DIVERGE avant la bascule — c'est ce qui rend
    l'assertion discriminante : un outil qui ne bascule pas laisse un écart, et le re-contrôle
    le dit."""
    bac = _Bac(tmp_path).write(VERSIONED, DIVERGENT_1)
    assert bac.target_sha != _sha(VERSIONED), "ancre : la copie installée doit diverger AVANT"
    pub_proc = bac.run(CLI_PUBLISH, check=False)
    assert pub_proc.returncode == EXIT_OK, (
        f"publication refusée sur un wrapper conforme : rc={pub_proc.returncode}\n"
        f"stdout={pub_proc.stdout}\nstderr={pub_proc.stderr}")
    assert bac.target_sha == _sha(VERSIONED), (
        "après `--publish`, la copie installée doit porter les octets de la copie versionnée")
    check_proc = bac.run()
    assert check_proc.returncode == EXIT_OK, (
        f"re-contrôle après publication : rc={check_proc.returncode}\n"
        f"stdout={check_proc.stdout}\nstderr={check_proc.stderr}")


# ------------------------------------------------------------------------ limite ---

def test_limit_un_wrapper_sans_export_est_refuse_AVANT_la_bascule(tmp_path):
    """S2 : le wrapper n'exporte pas les requises -> refus nommé, et la cible n'est PAS écrasée.

    La cible diverge avant l'appel : une implémentation qui copierait PUIS vérifierait laisse une
    trace, et ce cas la refuse."""
    bac = _Bac(tmp_path).write(VERSIONED, DIVERGENT_1, wrapper=W_BARE)
    avant = bac.target_sha
    proc = bac.run(CLI_PUBLISH, check=False)
    sortie = proc.stdout + proc.stderr
    assert proc.returncode != EXIT_OK, (
        f"un wrapper sans export doit refuser la bascule : rc={proc.returncode}\n{sortie}")
    assert proc.returncode in (EXIT_GAP, EXIT_ERROR), (
        f"rc inattendu (écart attendu, ou erreur d'exécution) : {proc.returncode}\n{sortie}")
    assert "Traceback (most recent call last)" not in proc.stderr, (
        f"refus attendu explicite, pas une trace d'exception : {proc.stderr!r}")
    assert REQUIRED[0] in sortie, f"le refus doit NOMMER la variable manquante : {sortie!r}"
    assert str(bac.wrapper) in sortie, (
        f"le refus doit nommer le fichier de wrapper : {sortie!r}")
    assert bac.target_sha == avant, "la copie installée ne doit pas être modifiée"


def test_limit_la_verification_nomme_les_SEULES_variables_manquantes(pub, tmp_path):
    """S2 : deux exports sur trois -> une seule manquante, et c'est la bonne."""
    manquantes = tuple(getattr(pub, MISSING_FN)(W_PARTIAL, REQUIRED))
    assert set(manquantes) == {REQUIRED[2]}, (
        f"attendu {{{REQUIRED[2]!r}}}, obtenu {manquantes!r}")
    assert len(manquantes) == 1, f"une seule manquante : {manquantes!r}"


def test_limit_une_mention_en_commentaire_ne_vaut_pas_un_export(pub, tmp_path):
    """S2 : le contrôle juge des EXPORTS, pas des sous-chaînes.

    Les trois `export` sont ici COMMENTÉS : la ligne `export PJ_ESCALATE_…` est bien présente dans le
    texte, seule la lecture du fichier change. Un contrôle par sous-chaîne, ou un `_strip_comment`
    neutralisé, serait vert — c'est exactement le faux positif que ce cas refuse. Le risque est réel
    et atteignable en une frappe : commenter une ligne suffit à tuer le tick (D5/D6)."""
    manquantes = tuple(getattr(pub, MISSING_FN)(W_COMMENT_ONLY, REQUIRED))
    assert set(manquantes) == set(REQUIRED), (
        f"aucune requise n'est exportée (les trois sont commentées) : les {len(REQUIRED)} doivent "
        f"être signalées, obtenu {manquantes!r}")


def test_limit_une_affectation_non_exportee_ne_vaut_pas_un_export(pub, tmp_path):
    """S2 : `VAR=…` sans `export` n'entre pas dans l'environnement du tick.

    C'est le défaut nommé par le contrat (« une affectation non exportée ne compte PAS : c'est
    précisément le défaut que ce contrôle existe pour voir »)."""
    manquantes = tuple(getattr(pub, MISSING_FN)(W_ASSIGN_ONLY, REQUIRED))
    assert set(manquantes) == set(REQUIRED), (
        f"trois affectations non exportées : les {len(REQUIRED)} doivent être signalées, "
        f"obtenu {manquantes!r}")


def test_limit_le_wrapper_versionne_du_depot_n_est_pas_refuse(pub, tmp_path):
    """S2 : le wrapper livré par le dépôt porte ses exports — le contrôle ne refuse pas le
    livrable.

    Mesuré : `agents/pj-master/scripts/pj_escalate_all.sh` exporte les requises par un motif
    (`case "$name" in PJ_ESCALATE_*) export "$name=$value"`, pas par trois lignes littérales. Un
    contrôle qui n'accepte que la forme littérale refuse le wrapper du dépôt : le geste humain ne
    peut alors jamais aboutir (le mode `--publish` resterait fermé), la slice serait inerte."""
    if not WRAPPER_VERSIONNE.exists():
        pytest.fail(f"wrapper versionné absent: {WRAPPER_VERSIONNE}")
    texte = WRAPPER_VERSIONNE.read_text(encoding="utf-8")
    manquantes = tuple(getattr(pub, MISSING_FN)(texte, REQUIRED))
    assert manquantes == (), (
        f"le wrapper versionné du dépôt est refusé à tort : {manquantes!r}")


def test_limit_une_cible_divergente_parmi_deux_refuse_l_ensemble(pub, tmp_path):
    """S2 : deux cibles, la seconde diverge -> l'ensemble est refusé et l'écart est chiffré.

    Une implémentation qui s'arrête à la première cible (alignée) rendrait 0 : la seconde cible
    n'est donc pas décorative."""
    bac = _Bac(tmp_path).write(VERSIONED, VERSIONED)
    seconde = tmp_path / "installee_bis.py"
    seconde.write_text(DIVERGENT_1, encoding="utf-8")
    proc = _run([CLI_CHECK, CLI_SOURCE, str(bac.source), CLI_TARGET, str(bac.target),
                 CLI_TARGET, str(seconde), CLI_WRAPPER, str(bac.wrapper),
                 CLI_REQUIRE_ENV, REQUIRE_ENV_VALUE], tmp_path, bac.home)
    sortie = proc.stdout + proc.stderr
    assert proc.returncode == EXIT_GAP, (
        f"une cible divergente doit faire sortir en écart (1) : rc={proc.returncode}\n{sortie}")
    compte, trouves = _count_reported(sortie, 1)
    assert compte, f"le nombre de lignes divergentes (1) doit être imprimé : {sortie!r} ({trouves})"


def test_limit_un_ecart_de_trois_lignes_est_compte_trois_fois(pub, tmp_path):
    """S2 : le compte suit la divergence — 1 ligne, 3 lignes, 0 ligne : trois verdicts distincts."""
    une = getattr(pub, COMPARE_FN)(DIVERGENT_1, VERSIONED)
    trois = getattr(pub, COMPARE_FN)(DIVERGENT_3, VERSIONED)
    assert int(_field(une, V_LINES)) == 1, f"un écart d'une ligne : {une!r}"
    assert int(_field(trois, V_LINES)) == 3, f"un écart de trois lignes : {trois!r}"
    assert _field(une, V_IDENTICAL) is False and _field(trois, V_IDENTICAL) is False


# ------------------------------------------------------------------------- erreur ---

def test_erreur_une_cible_absente_sort_2_sans_annoncer_d_identite(tmp_path):
    """S3 : cible inexistante -> rc 2 (erreur d'exécution), message nommant le chemin, et aucune
    identité annoncée. Le module, lui, existe (fixture autouse) : on ne mesure pas un fichier
    introuvable par accident."""
    bac = _Bac(tmp_path).write(VERSIONED, VERSIONED)
    absente = tmp_path / "copie_absente.py"
    proc = _run([CLI_CHECK, CLI_SOURCE, str(bac.source), CLI_TARGET, str(absente),
                 CLI_WRAPPER, str(bac.wrapper), CLI_REQUIRE_ENV, REQUIRE_ENV_VALUE],
                tmp_path, bac.home)
    sortie = proc.stdout + proc.stderr
    assert proc.returncode == EXIT_ERROR, (
        f"cible absente : rc attendu {EXIT_ERROR}, obtenu {proc.returncode}\n{sortie}")
    assert str(absente) in sortie, f"le message doit nommer la cible absente : {sortie!r}"
    assert "Traceback (most recent call last)" not in proc.stderr, (
        f"message explicite attendu, pas une trace : {proc.stderr!r}")


def test_erreur_une_cible_qui_n_est_pas_un_fichier_ne_produit_pas_de_faux_succes(tmp_path):
    """S3 : une cible illisible (ici un dossier) -> rc 2, jamais un succès muet."""
    bac = _Bac(tmp_path).write(VERSIONED, VERSIONED)
    dossier = tmp_path / "copie_dossier"
    dossier.mkdir()
    proc = _run([CLI_CHECK, CLI_SOURCE, str(bac.source), CLI_TARGET, str(dossier),
                 CLI_WRAPPER, str(bac.wrapper), CLI_REQUIRE_ENV, REQUIRE_ENV_VALUE],
                tmp_path, bac.home)
    sortie = proc.stdout + proc.stderr
    assert proc.returncode == EXIT_ERROR, (
        f"cible illisible : rc attendu {EXIT_ERROR}, obtenu {proc.returncode}\n{sortie}")
    assert str(dossier) in sortie, f"le message doit nommer la cible : {sortie!r}"


def test_erreur_une_paire_divergente_sort_1_avec_les_DEUX_digests_et_le_compte(tmp_path):
    """S3 : copie installée divergente -> rc 1, les DEUX empreintes (distinctes) et le compte.

    C'est le seul cas qui juge la phrase « imprime le digest des deux fichiers » : sur une paire
    alignée les deux empreintes sont égales, un outil qui n'en imprime qu'une passerait."""
    bac = _Bac(tmp_path).write(VERSIONED, DIVERGENT_1)
    avant = _snapshot(tmp_path)
    proc = bac.run()
    sortie = proc.stdout + proc.stderr
    assert proc.returncode == EXIT_GAP, (
        f"paire divergente : rc attendu {EXIT_GAP}, obtenu {proc.returncode}\n{sortie}")
    assert _sha(VERSIONED) in sortie, f"empreinte de la copie versionnée absente : {sortie!r}"
    assert _sha(DIVERGENT_1) in sortie, f"empreinte de la copie installée absente : {sortie!r}"
    compte, trouves = _count_reported(sortie, 1)
    assert compte, f"le nombre de lignes divergentes (1) doit être imprimé : {trouves}"
    assert _snapshot(tmp_path) == avant, "un écart en mode contrôle n'est jamais publié"


def test_erreur_la_comparaison_pure_distingue_identite_et_divergence(pub, tmp_path):
    """Contre-épreuve : un verdict CONSTANT (toujours identique, ou toujours divergent) meurt ici.

    Sans cette paire, un `identical` codé en dur passe le nominal et un `divergent_lines` codé en
    dur passe l'erreur : c'est la paire qui juge."""
    identique = getattr(pub, COMPARE_FN)(VERSIONED, VERSIONED)
    divergent = getattr(pub, COMPARE_FN)(DIVERGENT_1, VERSIONED)
    assert _field(identique, V_IDENTICAL) is True
    assert _field(divergent, V_IDENTICAL) is False
    assert str(_field(identique, V_INSTALLED)) != str(_field(divergent, V_INSTALLED)), (
        "l'empreinte doit suivre le contenu, pas être constante")
    assert int(_field(identique, V_LINES)) != int(_field(divergent, V_LINES)), (
        "le compte doit suivre la divergence, pas être constant")


# ------------------------------------------------------- mode périmètre (couverture) ---
# Le 4e scénario du Gherkin de la carte sœur `t_f1072d8c` : « le contrôle exige un périmètre NON
# VIDE (un vert vide ne prouve rien) ». Il porte sur le mode `--coverage` annoncé au contrat
# publié (`contrat-3`, §cli §mode_perimetre). Fixtures : un dépôt git jetable sous `tmp_path` —
# aucun dépôt réel, aucun chemin machine, aucun accès réseau.

def _git(repo, *args):
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(GIT_AUTHOR_NAME="banc", GIT_AUTHOR_EMAIL="banc@example.invalid",
               GIT_COMMITTER_NAME="banc", GIT_COMMITTER_EMAIL="banc@example.invalid")
    proc = subprocess.run(["git", "-C", str(repo), *args], env=env,
                          capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, f"git {args} a échoué : {proc.stderr}"
    return proc


def _depot(tmp_path):
    """Dépôt jetable : commit initial `base`, puis (optionnel) un commit qui touche `chemin`."""
    repo = tmp_path / "depot"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    (repo / "README.md").write_text("base\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "base")
    return repo


def _rapport(tmp_path, nom, contenu):
    """Rapport de couverture minimal, au format lu par `parse_coverage_json`."""
    import json
    chemin = tmp_path / nom
    chemin.write_text(json.dumps({"files": contenu}), encoding="utf-8")
    return chemin


def _rapport_pour(chemin, pct):
    import json
    return {str(chemin): {"summary": {"percent_covered": pct}}}


def test_erreur_un_perimetre_vide_ne_rend_pas_un_succes_muet(tmp_path):
    """4e scénario : aucun commit d'avance sur la base -> rc 2, et le message dit que le périmètre
    est vide. Un rapport `{}` suffit à rendre un « conforme » muet : c'est ce que ce cas refuse."""
    repo = _depot(tmp_path)
    rapport = _rapport(tmp_path, "cov.json", {})
    proc = _run(["--coverage", "--coverage-json", str(rapport), "--diff-base", "HEAD",
                 "--repo", str(repo)], tmp_path, tmp_path / "home")
    sortie = proc.stdout + proc.stderr
    assert proc.returncode == EXIT_ERROR, (
        f"périmètre vide : rc attendu {EXIT_ERROR}, obtenu {proc.returncode}\n{sortie}")
    assert "vide" in sortie.lower(), f"le message doit dire le périmètre vide : {sortie!r}"


def test_nominal_un_perimetre_non_vide_dont_le_rapport_nomme_le_fichier_sort_0(tmp_path):
    """4e scénario, versant conforme : le fichier modifié du diff EST nommé au rapport -> rc 0, et
    son nom apparaît dans la sortie (le rapport n'est pas cru sur parole)."""
    import json
    repo = _depot(tmp_path)
    fichier = repo / "pipeline" / "outil.py"
    fichier.parent.mkdir()
    fichier.write_text("x = 1\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "ajoute outil.py")
    rapport = _rapport(tmp_path, "cov.json", _rapport_pour("pipeline/outil.py", 95.0))
    home = tmp_path / "home"
    home.mkdir()
    proc = _run(["--coverage", "--coverage-json", str(rapport), "--diff-base", "HEAD~1",
                 "--repo", str(repo)], tmp_path, home)
    sortie = proc.stdout + proc.stderr
    assert proc.returncode == EXIT_OK, (
        f"périmètre mesuré et conforme : rc attendu {EXIT_OK}, obtenu {proc.returncode}\n{sortie}")
    assert "pipeline/outil.py" in sortie, (
        f"le rapport doit NOMMER le fichier modifié : {sortie!r}")
    assert json.loads(rapport.read_text())["files"], "ancre : le rapport porte bien une mesure"


def test_erreur_un_rapport_muet_sur_un_fichier_du_perimetre_sort_2_en_le_nommant(tmp_path):
    """4e scénario, versant erreur : le fichier modifié est ABSENT du rapport -> rc 2 en le nommant.

    Un gate qui ne mesure pas le fichier du diff et rend 0 est vert par vacuité — c'est le piège
    que ce cas refuse (le seuil ne serait jamais évalué)."""
    repo = _depot(tmp_path)
    fichier = repo / "pipeline" / "outil.py"
    fichier.parent.mkdir()
    fichier.write_text("x = 1\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "ajoute outil.py")
    rapport = _rapport(tmp_path, "cov.json", _rapport_pour("pipeline/autre.py", 95.0))
    home = tmp_path / "home"
    home.mkdir()
    proc = _run(["--coverage", "--coverage-json", str(rapport), "--diff-base", "HEAD~1",
                 "--repo", str(repo)], tmp_path, home)
    sortie = proc.stdout + proc.stderr
    assert proc.returncode == EXIT_ERROR, (
        f"rapport muet sur le fichier du périmètre : rc attendu {EXIT_ERROR}, "
        f"obtenu {proc.returncode}\n{sortie}")
    assert "pipeline/outil.py" in sortie, (
        f"le message doit nommer le fichier non mesuré : {sortie!r}")


def test_limite_un_perimetre_sans_fichier_de_code_ne_prononce_pas_de_conformite(tmp_path):
    """4e scénario, cas LIMITE : un diff qui ne touche que de la documentation laisse le gate sans
    rien à mesurer.

    Le cas ne juge pas un code de sortie, il juge une PRÉTENTION : la sortie ne doit pas annoncer
    une conformité de couverture qu'aucune mesure n'appuie (« un vert vide ne prouve rien », D5 des
    pièges du gate)."""
    repo = _depot(tmp_path)
    (repo / "README.md").write_text("base\n\nune ligne de doc\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "doc")
    rapport = _rapport(tmp_path, "cov.json", {})
    home = tmp_path / "home"
    home.mkdir()
    proc = _run(["--coverage", "--coverage-json", str(rapport), "--diff-base", "HEAD~1",
                 "--repo", str(repo)], tmp_path, home)
    sortie = (proc.stdout + proc.stderr).lower()
    assert proc.returncode == EXIT_OK, (
        f"un diff sans fichier de code n'est pas un écart de couverture : "
        f"rc={proc.returncode}\n{sortie}")
    assert "conforme" not in sortie or "rien" in sortie, (
        f"aucune conformité de couverture ne peut être annoncée sans mesure : {sortie!r}")
