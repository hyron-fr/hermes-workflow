"""Banc RED de la slice 1/3 (#4) : la configuration de l'outil d'escalade vient de l'environnement.

Dérivé de (R1) — ce n'est pas le corps de l'issue qui fait foi, c'est le contrat ratifié :

- contrat `contrat-1` annoncé par `dev-1` sur le blackboard de la racine `t_e41f9643` :
  `escalation_config(env)` rend un objet portant `channel_id`, `user_id`, `guild_id`,
  `repos_root`, `state_dir`, `thread_helper` ; le refus est un `ConfigError` ;
- Gherkin de la carte `t_c476989b` (nominal / limite / erreur) ;
- cadrage `docs/architecture/context/issue-4.md` + arbitrages D9/D10/D11/D15
  (validation des requises **une fois en tête de `main()`**, « vide » compte comme absent).

Module testé : le **canonique `pipeline/pj_escalate.py`** — ni `bridge/` (périmé sur `dev`), ni la
copie du profil : le contrat projet interdit tout chemin absolu de machine dans les tests, et
`pipeline/` est le seul foyer installable (`README.md` §4, `grep -c 'cp bridge' README.md` -> 0).

Aucun test ne lit le texte source du fichier testé (règle CONTRIBUTING : un test qui lit le texte
source est refusé) : l'absence de valeur codée en dur est pinnée **par le comportement** — deux
environnements distincts produisent deux configurations distinctes, et un `HOME` injecté déplace
les défauts. Les identifiants Discord de la copie live ne sont **pas** recopiés ici (dépôt public) :
les valeurs du banc sont synthétiques.

Nature des cas : nominal (env complet, valeurs d'env exposées, optionnelles utilisées), limite
(requise **présente mais vide**, optionnelles absentes -> défauts dérivés du `HOME`), erreur
(requise absente au niveau config, tick de production en sous-processus -> rc != 0, message
nommant la variable, aucun état de dédup, aucun envoi).
"""
import importlib.util
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

import pytest  # noqa: E402

# --------------------------------------------------------------- contrat pinné ---
# 1. module sous test : foyer canonique `pipeline/`. `PJ_TARGET_COPY` permet de rejouer le même
#    banc sur une autre copie (copie publiée de la slice 3) sans jamais coder de chemin machine.
TARGET = (Path(os.environ["PJ_TARGET_COPY"]) if os.environ.get("PJ_TARGET_COPY")
          else REPO / "pipeline" / "pj_escalate.py")
# 2. fabrique de configuration — nom figé par `dev-1`
CONFIG_FACTORY = "escalation_config"
# 3. refus de configuration — nom figé par `dev-1`
ERROR_TYPE = "ConfigError"
# 4. variables requises (présence ET non-vacuité)
REQUIRED = ("PJ_ESCALATE_CHANNEL_ID", "PJ_ESCALATE_USER_ID", "PJ_ESCALATE_GUILD_ID")
# 5. variables optionnelles (défaut dérivé du répertoire personnel)
OPTIONAL = ("PJ_ESCALATE_REPOS_ROOT", "PJ_ESCALATE_STATE_DIR", "PJ_ESCALATE_THREAD_HELPER")
# 6. champs exposés par la configuration (accès par ATTRIBUT, pas par clé de dict)
FIELDS = ("channel_id", "user_id", "guild_id", "repos_root", "state_dir", "thread_helper")
# 7. entrée de production : le cron exécute `exec python3 <chemin>` sans argument
TICK = [sys.executable, str(TARGET)]

# valeurs synthétiques : distinctes entre elles, donc discriminantes sur « lu dans l'env »
ENV_A = {"PJ_ESCALATE_CHANNEL_ID": "100000000000000001",
         "PJ_ESCALATE_USER_ID": "200000000000000002",
         "PJ_ESCALATE_GUILD_ID": "300000000000000003"}
ENV_B = {"PJ_ESCALATE_CHANNEL_ID": "400000000000000004",
         "PJ_ESCALATE_USER_ID": "500000000000000005",
         "PJ_ESCALATE_GUILD_ID": "600000000000000006"}


def _load(path, name="pj_escalate_under_test"):
    """Charge le module par chemin ; échoue en ERROR (pas en SKIP) s'il n'existe pas (R4)."""
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
def esc():
    return _load(TARGET)


def _env(home, **over):
    env = dict(ENV_A)
    env["HOME"] = str(home)
    env.update(over)
    return env


def _tick_env(home, state_dir, **over):
    """Environnement d'un tick réel : pas de `PJ_ESCALATE_*` hérité, `HOME` neutralisé."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("PJ_ESCALATE_")}
    env["HOME"] = str(home)
    env["PJ_ESCALATE_STATE_DIR"] = str(state_dir)
    env.update(over)
    return env


class _Recorder:
    """Témoin d'envoi : le helper Discord est remplacé par un script qui journalise son appel."""

    def __init__(self, root):
        self.log = root / "helper_calls.log"
        self.path = root / "fake_thread_helper.py"
        self.path.write_text(
            "import os, sys\n"
            f"open({str(self.log)!r}, 'a').write(' '.join(sys.argv) + '\\n')\n"
        )
        self.path.chmod(0o755)

    @property
    def called(self):
        return self.log.exists()

    @property
    def calls(self):
        return self.log.read_text() if self.log.exists() else ""


def _files_under(path):
    return sorted(p for p in Path(path).rglob("*") if p.is_file())


# ----------------------------------------------------------------------- nominal ---

def test_nominal_required_vars_reach_the_config(esc, tmp_path, monkeypatch):
    """S1 : un environnement complet produit une configuration exploitable."""
    monkeypatch.setenv("HOME", str(tmp_path))
    cfg = getattr(esc, CONFIG_FACTORY)(_env(tmp_path))
    for field in FIELDS:
        assert hasattr(cfg, field), f"la configuration doit porter l'attribut {field!r}"
    assert cfg.channel_id == ENV_A["PJ_ESCALATE_CHANNEL_ID"]
    assert cfg.user_id == ENV_A["PJ_ESCALATE_USER_ID"]
    assert cfg.guild_id == ENV_A["PJ_ESCALATE_GUILD_ID"]


def test_nominal_config_follows_the_environment_not_a_constant(esc, tmp_path, monkeypatch):
    """S1, « aucune valeur n'est codée en dur » pinné par le comportement (sans lire la source)."""
    monkeypatch.setenv("HOME", str(tmp_path))
    a = getattr(esc, CONFIG_FACTORY)(_env(tmp_path, **ENV_A))
    b = getattr(esc, CONFIG_FACTORY)(_env(tmp_path, **ENV_B))
    assert (a.channel_id, a.user_id, a.guild_id) == tuple(ENV_A[k] for k in REQUIRED)
    assert (b.channel_id, b.user_id, b.guild_id) == tuple(ENV_B[k] for k in REQUIRED)
    assert a.channel_id != b.channel_id and a.user_id != b.user_id and a.guild_id != b.guild_id


def test_nominal_optional_vars_present_are_used(esc, tmp_path, monkeypatch):
    """Les optionnelles posées sont lues telles quelles (aucun défaut ne les écrase)."""
    monkeypatch.setenv("HOME", str(tmp_path))
    over = {"PJ_ESCALATE_REPOS_ROOT": str(tmp_path / "repos"),
            "PJ_ESCALATE_STATE_DIR": str(tmp_path / "state"),
            "PJ_ESCALATE_THREAD_HELPER": str(tmp_path / "helper.py")}
    cfg = getattr(esc, CONFIG_FACTORY)(_env(tmp_path, **over))
    for var, field in zip(OPTIONAL, ("repos_root", "state_dir", "thread_helper")):
        assert str(getattr(cfg, field)) == over[var], f"{field} doit valoir {var}"


# ------------------------------------------------------------------------ limite ---

@pytest.mark.parametrize("var", REQUIRED)
def test_limit_empty_required_var_is_treated_as_absent(esc, tmp_path, monkeypatch, var):
    """S2 : présente mais VIDE -> refus nommant la variable. Un contrôle de seule PRÉSENCE
    (`if var not in env`) rendrait ici un objet au champ vide : ce test le rejette."""
    monkeypatch.setenv("HOME", str(tmp_path))
    env = _env(tmp_path)
    env[var] = ""
    with pytest.raises(getattr(esc, ERROR_TYPE)) as exc:
        getattr(esc, CONFIG_FACTORY)(env)
    assert var in str(exc.value), f"le refus doit nommer {var} : {str(exc.value)!r}"


def test_limit_empty_var_never_silently_becomes_an_identifier(esc, tmp_path, monkeypatch):
    """S2 : « aucun repli silencieux » — un refus explicite, jamais un `KeyError` brut ni un
    objet dont le champ identifiant serait la chaîne vide."""
    monkeypatch.setenv("HOME", str(tmp_path))
    env = _env(tmp_path)
    env[REQUIRED[1]] = ""
    try:
        cfg = getattr(esc, CONFIG_FACTORY)(env)
    except getattr(esc, ERROR_TYPE) as exc:
        assert REQUIRED[1] in str(exc), str(exc)
        assert str(exc).strip(), "le refus doit porter un message, pas une chaîne vide"
    else:
        pytest.fail(f"repli silencieux interdit : {CONFIG_FACTORY} a rendu {cfg!r} "
                    f"avec {REQUIRED[1]} vide -> {getattr(cfg, 'user_id')!r}")


def test_limit_optional_vars_absent_derive_from_the_injected_home(esc, tmp_path, monkeypatch):
    """S2 (limite) : optionnelles absentes -> défauts dérivés du répertoire personnel, sans
    erreur ; un chemin machine en dur (ex. /home/<user>) échoue ici, car HOME est déplacé."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    cfg = getattr(esc, CONFIG_FACTORY)(_env(home))
    assert str(home) in str(cfg.repos_root), \
        f"repos_root doit dériver du HOME injecté : {cfg.repos_root!r}"
    assert str(home) in str(cfg.state_dir), \
        f"state_dir doit dériver du HOME injecté : {cfg.state_dir!r}"
    assert str(cfg.thread_helper).strip(), "thread_helper doit être non vide"


# ------------------------------------------------------------------------- erreur ---

@pytest.mark.parametrize("var", REQUIRED)
def test_error_absent_required_var_refuses_at_construction(esc, tmp_path, monkeypatch, var):
    """S3 (au niveau config) : absente -> construction refusée, variable nommée."""
    monkeypatch.setenv("HOME", str(tmp_path))
    env = _env(tmp_path)
    del env[var]
    with pytest.raises(getattr(esc, ERROR_TYPE)) as exc:
        getattr(esc, CONFIG_FACTORY)(env)
    assert var in str(exc.value), f"le refus doit nommer {var} : {str(exc.value)!r}"


def test_error_tick_without_channel_id_exits_nonzero_and_sends_nothing(tmp_path):
    """S3 : le tick s'exécute, sort en rc != 0 avec un message explicite sur stderr, n'écrit
    aucun état de dédup et n'appelle pas le helper Discord. `HOME` est neutralisé : un outil qui
    scannerait les boards AVANT de valider sa configuration laisserait une trace ou un rc nul."""
    home = tmp_path / "home"
    (home / ".hermes").mkdir(parents=True)
    state = tmp_path / "state"
    rec = _Recorder(tmp_path)
    env = _tick_env(home, state, PJ_ESCALATE_USER_ID=ENV_A["PJ_ESCALATE_USER_ID"],
                    PJ_ESCALATE_GUILD_ID=ENV_A["PJ_ESCALATE_GUILD_ID"],
                    PJ_ESCALATE_THREAD_HELPER=str(rec.path))
    proc = subprocess.run(TICK, env=env, capture_output=True, text=True, timeout=60)
    assert proc.returncode != 0, f"tick sans canal : rc={proc.returncode}\nstdout={proc.stdout}"
    assert "PJ_ESCALATE_CHANNEL_ID" in proc.stderr, \
        f"stderr doit nommer la variable fautive : {proc.stderr!r}"
    assert "Traceback (most recent call last)" not in proc.stderr, \
        f"refus attendu explicite, pas une trace d'exception : {proc.stderr!r}"
    assert not rec.called, f"aucun envoi attendu, helper appelé : {rec.calls!r}"
    assert _files_under(state) == [], f"aucun état de dédup attendu : {_files_under(state)}"
    assert _files_under(home / ".hermes") == [], "aucune écriture sous HOME attendue"


def test_error_tick_with_empty_required_var_exits_nonzero(tmp_path):
    """S3, variante LIMITE au niveau du tick : la variable est POSÉE mais vide — elle doit
    arrêter le tick comme si elle était absente (vide ne crash pas : c'est le cas qui boucle)."""
    home = tmp_path / "home"
    (home / ".hermes").mkdir(parents=True)
    state = tmp_path / "state"
    rec = _Recorder(tmp_path)
    env = _tick_env(home, state, PJ_ESCALATE_CHANNEL_ID="", PJ_ESCALATE_GUILD_ID=ENV_A["PJ_ESCALATE_GUILD_ID"],
                    PJ_ESCALATE_THREAD_HELPER=str(rec.path))
    proc = subprocess.run(TICK, env=env, capture_output=True, text=True, timeout=60)
    assert proc.returncode != 0, f"canal vide : rc={proc.returncode}\nstdout={proc.stdout}"
    assert "PJ_ESCALATE_CHANNEL_ID" in proc.stderr, \
        f"stderr doit nommer la variable fautive : {proc.stderr!r}"
    assert "Traceback (most recent call last)" not in proc.stderr, \
        f"refus attendu explicite : {proc.stderr!r}"
    assert not rec.called, f"aucun envoi attendu, helper appelé : {rec.calls!r}"
    assert _files_under(state) == [], f"aucun état de dédup attendu : {_files_under(state)}"
