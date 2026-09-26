"""Portage de couverture de `pipeline/pj_publish.py` (slice 3/3, #4) — exerce le module EN PROCESSUS.

POURQUOI CE FICHIER EXISTE
--------------------------
Le banc de la slice 3 (`tests/test_pj_publish.py`) juge la **CLI par exécution** (`subprocess.run`) :
c'est le bon banc pour les codes de sortie et la lecture seule, mais `coverage` **ne suit pas les
sous-processus** — les cas CLI y comptent 0 ligne et le gate mesure 36,7 % (rc=1) sur un fichier
neuf pourtant jugé. Le portage consiste donc à ré-exercer le module **en appelant `main([...])` dans
le processus du banc**, sur des fixtures temporaires. Le banc gelé de la slice 3 n'est **pas**
touché (sa preuve de non-affaiblissement reste lisible) ; le fichier gelé de la slice 1 et le
portage de la slice 2 ne le sont pas non plus.

Aucune exclusion, aucun `# pragma: no cover`, aucun seuil abaissé. Les branches défensives sont
**exercées** par des fixtures qui les atteignent réellement (mesuré : `spec_from_file_location` rend
`None` sur une extension inconnue, `.read_text()` sur un dossier lève `IsADirectoryError`, un
`mkdir(parents=True)` dont le parent est un FICHIER lève `NotADirectoryError`, un `export` à
guillemet non fermé fait lever `shlex`). Une branche restée inatteignable est DITE dans le handoff
avec son compte, jamais masquée par un pragma.

NATURE DES CAS (1 nominal + 1 limite + 1 erreur, et de fait bien davantage)
---------------------------------------------------------------------------
- nominal : contrôle d'une paire alignée -> rc 0 avec les deux digests et zéro écriture ; cibles par
  défaut résolues sous un `HOME` **injecté** ; publication d'une cible absente puis idempotence
  vérifiée par horodatage ; accès au verdict pur (attribut ET clé) ; contrat de variables lu sur la
  copie versionnée ; exports du wrapper conformes.
- limite : le motif glob du wrapper versionné du dépôt est accepté (et un `export` commenté ou une
  affectation non exportée sont refusés) ; un `export` à guillemet non fermé est lu en repli ; un
  `--target` vide retombe sur les cibles par défaut ; un écart qui ne porte pas sur les lignes (fin
  de fichier) reste un ÉCART ; un périmètre sans fichier de code n'annonce pas de conformité de
  couverture ; le seuil est configurable et un fichier au-dessus passe.
- erreur : source illisible dans les deux modes ; wrapper illisible sans bascule (chemin en DOSSIER
  et chemin ABSENT, cause nommée) ; cible en 0444 -> l'`except OSError` de l'écriture est atteint ;
  `--publish` sans cible explicite ; écriture impossible (parent fichier) ; module non chargeable ;
  `--coverage` sans rapport ni base, rapport illisible ou périmètre inexploitable ; périmètre vide ;
  rapport muet.

Aucune horloge réelle, aucun aléa, aucun réseau. Aucun chemin absolu de machine (tout vit sous
`tmp_path` ; les seuls chemins de dépôt sont dérivés de `REPO`). Aucun test ne lit le texte source
du module testé : l'API est appelée, la sortie est capturée.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

import pytest  # noqa: E402

# --------------------------------------------------------------- contrat pinné ---
TARGET = (Path(os.environ["PJ_PUBLISH_SEAMS_COPY"]) if os.environ.get("PJ_PUBLISH_SEAMS_COPY")
          else REPO / "pipeline" / "pj_publish.py")   # foyer canonique du module livré (D1)
ESCAPE = REPO / "pipeline" / "pj_escalate.py"         # copie versionnée que `pj_publish` publie
WRAPPER_DEPOT = REPO / "agents" / "pj-master" / "scripts" / "pj_escalate_all.sh"
REQUIRED = ("PJ_ESCALATE_CHANNEL_ID", "PJ_ESCALATE_USER_ID", "PJ_ESCALATE_GUILD_ID")
REQUIRE_ENV_VALUE = ",".join(REQUIRED)
PROFIL_EXECUTE = ("pj-master", "pj_escalate.py")      # profil que le cron exécute (README §4)
EXIT_OK, EXIT_GAP, EXIT_ERROR = 0, 1, 2

VERSIONED = "".join(f"ligne {i:02d}\n" for i in range(1, 11))
DIVERGENT_1 = VERSIONED.replace("ligne 07\n", "ligne 07 — divergente\n")
# Écart de FIN DE FICHIER : les lignes sont identiques une à une, seul le contenu total diffère.
DIVERGENTE_FIN = VERSIONED.rstrip("\n")
# Wrapper fautif de la slice 3 : il n'exporte RIEN (le défaut que le contrôle existe pour voir).
W_BARE = ('#!/usr/bin/env bash\n# Cron pj-escalate.\n'
          'exec python3 "$HOME/.hermes/profiles/pj-master/scripts/pj_escalate.py"\n')
# Toutes les requises présentes, mais uniquement en COMMENTAIRE : forme la plus dangereuse.
W_COMMENT_ONLY = "".join(
    ["#!/usr/bin/env bash\n"]
    + [f'# export {n}="1"\n' for n in REQUIRED]
    + ['exec python3 "$HOME/.hermes/profiles/pj-master/scripts/pj_escalate.py"\n'])


def _load(path, name="pj_publish_seams_under_test"):
    """Charge le module par chemin ; échoue en ERROR (pas en SKIP) s'il est absent."""
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
def pub():
    return _load(TARGET)


def _snapshot(root):
    """{chemin relatif -> empreinte} de tout le bac : une CRÉATION fait échouer la comparaison."""
    root = Path(root)
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file()}


def _sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class _Bac:
    """Bac à sable : copie versionnée, copie(s) installée(s), wrapper — sous `tmp_path`."""

    def __init__(self, tmp_path):
        self.root = Path(tmp_path)
        self.home = self.root / "home"
        self.home.mkdir(exist_ok=True)
        self.source = self.root / "versionnee.py"
        self.target = self.root / "installee.py"
        self.wrapper = self.root / "pj_escalate_all.sh"

    def write(self, versioned=VERSIONED, installed=VERSIONED, wrapper=None):
        self.source.write_text(versioned, encoding="utf-8")
        self.target.write_text(installed, encoding="utf-8")
        self.wrapper.write_text(wrapper if wrapper is not None else _wrapper_litteral(),
                                encoding="utf-8")
        return self

    def argv(self, *extra, mode="--check"):
        """ARGV du mode contrôle : `--home` est TOUJOURS injecté (jamais le HOME réel)."""
        flags = [mode] if mode else []
        return [*flags, "--source", str(self.source), "--target", str(self.target),
                "--wrapper", str(self.wrapper), "--require-env", REQUIRE_ENV_VALUE,
                "--home", str(self.home), *extra]

    @property
    def target_sha(self):
        return hashlib.sha256(self.target.read_bytes()).hexdigest()

    @property
    def target_mtime(self):
        return self.target.stat().st_mtime_ns


def _wrapper_litteral():
    return ("#!/usr/bin/env bash\nset -u\n"
            + "".join(f'export {n}="${{{n}:-1}}"\n' for n in REQUIRED)
            + 'exec python3 "$HOME/.hermes/profiles/pj-master/scripts/pj_escalate.py" "$@"\n')


def _run(pub, capsys, argv):
    """Appelle `main(argv)` DANS le processus du banc ; rend (rc, stdout, stderr)."""
    capsys.readouterr()
    rc = pub.main(list(argv))
    cap = capsys.readouterr()
    return rc, cap.out, cap.err


def _git(repo, *args):
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(GIT_AUTHOR_NAME="banc", GIT_AUTHOR_EMAIL="banc@example.invalid",
               GIT_COMMITTER_NAME="banc", GIT_COMMITTER_EMAIL="banc@example.invalid")
    proc = subprocess.run(["git", "-C", str(repo), *args], env=env,
                          capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, f"git {args} a échoué : {proc.stderr}"
    return proc


def _depot(tmp_path, touche=None, contenu="x = 1\n", message="ajoute"):
    """Dépôt jetable : commit `base`, puis (si `touche`) un commit qui crée ce chemin."""
    repo = tmp_path / "depot"
    repo.mkdir(parents=True)
    _git(repo, "init", "-q", "-b", "main")
    (repo / "README.md").write_text("base\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "base")
    if touche:
        f = repo / touche
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(contenu, encoding="utf-8")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", message)
    return repo


def _rapport(tmp_path, contenu, nom="cov.json"):
    chemin = tmp_path / nom
    chemin.write_text(json.dumps({"files": contenu}), encoding="utf-8")
    return chemin


def _couverture(pub, capsys, tmp_path, repo, base, contenu, *extra):
    """Mode périmètre en processus : rapport jetable + dépôt jetable, `--home` injecté."""
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    rapport = _rapport(tmp_path, contenu)
    return _run(pub, capsys, ["--coverage", "--coverage-json", str(rapport),
                              "--diff-base", base, "--repo", str(repo),
                              "--home", str(home), *extra])


# ----------------------------------------------------------------------- nominal ---

def test_nominal_controle_d_une_paire_alignee_rend_0_et_nomme_les_deux_copies(pub, tmp_path,
                                                                             capsys):
    """S1 : paire alignée -> rc 0, les DEUX copies sont nommées et empreintées, rien n'est écrit.

    Le mode par défaut est le contrôle : aucun `--check` n'est passé, ce qui juge aussi la branche
    `_check` de `main` et la lecture seule du mode par défaut."""
    bac = _Bac(tmp_path).write()
    avant = _snapshot(tmp_path)
    rc, out, err = _run(pub, capsys, bac.argv(mode=None))
    assert rc == EXIT_OK, f"paire alignée : rc={rc}\nstdout={out}\nstderr={err}"
    for label in ("versionnée", "installée"):
        assert label in out, f"le contrôle doit nommer la copie {label!r} : {out!r}"
    assert _sha(VERSIONED) in out, f"empreinte absente de la sortie : {out!r}"
    assert "conforme" in out, f"le verdict conforme doit être prononcé : {out!r}"
    assert err == "", f"aucun refus attendu sur stderr : {err!r}"
    assert _snapshot(tmp_path) == avant, "le mode contrôle écrit quelque chose"


def test_nominal_les_cibles_par_defaut_sont_resolues_sous_le_home_injecte(pub, tmp_path,
                                                                         capsys):
    """S1 : sans `--target`, les deux copies installées connues sont résolues sous le `HOME` reçu.

    Le `HOME` est INJECTÉ : le test ne lit ni n'écrit jamais le répertoire personnel réel. Un outil
    qui ignorerait `--home` irait chercher les copies réelles et sortirait en écart (rc 1) — le cas
    est donc discriminant, pas décoratif."""
    bac = _Bac(tmp_path).write()
    profils = bac.home / ".hermes" / "profiles" / PROFIL_EXECUTE[0] / "scripts"
    profils.mkdir(parents=True)
    seconde = bac.home / ".hermes" / "scripts"
    seconde.mkdir(parents=True)
    for d in (profils, seconde):
        (d / PROFIL_EXECUTE[1]).write_text(VERSIONED, encoding="utf-8")
    rc, out, err = _run(pub, capsys, ["--source", str(bac.source), "--wrapper", str(bac.wrapper),
                                      "--require-env", REQUIRE_ENV_VALUE,
                                      "--home", str(bac.home)])
    assert rc == EXIT_OK, f"cibles par défaut alignées : rc={rc}\nstdout={out}\nstderr={err}"
    assert str(profils / PROFIL_EXECUTE[1]) in out, f"la copie du profil doit être contrôlée : {out!r}"
    assert str(seconde / PROFIL_EXECUTE[1]) in out, f"la seconde copie doit être contrôlée : {out!r}"


def test_nominal_la_publication_cree_la_cible_puis_ne_la_reecrit_plus(pub, tmp_path, capsys):
    """S1 : `--publish` crée une cible absente, et un second passage est IDEMPOTENT (horodatage).

    L'idempotence se juge sur `st_mtime_ns` : une réécriture à contenu identique laisse un
    horodatage plus récent et serait invisible sur le contenu seul."""
    bac = _Bac(tmp_path).write(installed=DIVERGENT_1)
    absente = tmp_path / "sous_dossier" / "installee.py"
    rc, out, err = _run(pub, capsys, ["--publish", "--source", str(bac.source),
                                      "--target", str(absente), "--wrapper", str(bac.wrapper),
                                      "--require-env", REQUIRE_ENV_VALUE, "--home", str(bac.home)])
    assert rc == EXIT_OK, f"publication sur une cible absente : rc={rc}\nstdout={out}\nstderr={err}"
    assert absente.read_text(encoding="utf-8") == VERSIONED, "la cible créée doit porter la source"
    assert "créée" in out, f"l'état de la cible créée doit être dit : {out!r}"
    premier = absente.stat().st_mtime_ns
    rc2, out2, _ = _run(pub, capsys, ["--publish", "--source", str(bac.source),
                                      "--target", str(absente), "--wrapper", str(bac.wrapper),
                                      "--require-env", REQUIRE_ENV_VALUE, "--home", str(bac.home)])
    assert rc2 == EXIT_OK, f"seconde publication : rc={rc2}\nstdout={out2}"
    assert "déjà identique" in out2, f"une cible conforme ne doit pas être réécrite : {out2!r}"
    assert absente.stat().st_mtime_ns == premier, \
        "la cible a été réécrite : l'outil n'est pas idempotent"


def test_nominal_le_verdict_pur_est_lisible_par_attribut_et_par_cle(pub, tmp_path):
    """S1 : le verdict est consommé par un humain (attribut) ET par un banc (clé), et ses alias de
    lecture désignent bien la même mesure que le contrat publié."""
    avant = _snapshot(tmp_path)
    cmp = pub.compare_copies(DIVERGENT_1, VERSIONED)
    assert cmp.identical is False and cmp["identical"] is False, f"verdict={cmp!r}"
    assert cmp.get("nope", "repli") == "repli", "un champ absent rend le repli, jamais une levée"
    with pytest.raises(KeyError):
        cmp["nope"]
    assert set(cmp.keys()) == {"identical", "installed_digest", "versioned_digest",
                               "divergent_lines", "installed_lines", "versioned_lines"}, cmp.keys()
    assert (cmp.source_digest, cmp.target_digest) == (cmp.versioned_digest, cmp.installed_digest)
    assert (cmp.source_lines, cmp.target_lines) == (cmp.versioned_lines, cmp.installed_lines)
    assert sorted(cmp.to_dict()) == sorted(cmp.keys()), cmp.to_dict()
    assert cmp.to_dict()["identical"] is False, cmp.to_dict()
    assert _snapshot(tmp_path) == avant, "la comparaison est PURE : aucune écriture"


def test_nominal_le_contrat_de_variables_est_lu_sur_la_copie_versionnee(pub, tmp_path):
    """S1 : `REQUIRED_VARS` de la copie versionnée fait foi ; à défaut, le contrat figé s'applique.

    Contre-épreuve : une copie qui déclare d'AUTRES noms doit rendre CES noms — un outil qui rendrait
    toujours la constante figée passerait le cas « absent » et meurt ici."""
    propre = tmp_path / "copie_propre.py"
    propre.write_text('REQUIRED_VARS = ("A_X", "B_Y")\n', encoding="utf-8")
    assert tuple(pub.required_env_names(propre)) == ("A_X", "B_Y"), \
        "les noms de la copie versionnée doivent faire foi"
    for nom, texte in (("absente.py", None), ("leve.py", "raise RuntimeError('boom')\n")):
        p = tmp_path / nom
        if texte is not None:
            p.write_text(texte, encoding="utf-8")
        assert tuple(pub.required_env_names(p)) == tuple(pub.DEFAULT_REQUIRED), \
            f"repli attendu sur le contrat figé pour {nom}"
    # ancre : la constante figée EST le contrat de la copie versionnée du dépôt (les deux ne
    # peuvent pas diverger sans que ce cas le dise)
    verite = _load(ESCAPE, "pj_publish_subject_ancre")
    assert tuple(verite.REQUIRED_VARS) == tuple(pub.DEFAULT_REQUIRED), \
        "le repli figé a dérivé du contrat de la copie versionnée"
    assert tuple(pub.required_env_names(ESCAPE)) == REQUIRED


def test_nominal_un_wrapper_conforme_est_accepte_et_compte(pub, tmp_path, capsys):
    """S1 : le contrôle des exports dit ce qu'il a VU (nombre de requises) — pas seulement « ok »."""
    bac = _Bac(tmp_path).write()
    rc, out, _ = _run(pub, capsys, bac.argv())
    assert rc == EXIT_OK, f"wrapper conforme : rc={rc}\n{out}"
    assert str(bac.wrapper) in out and "conforme" in out, f"le wrapper doit être nommé : {out!r}"
    assert f"{len(REQUIRED)} variable(s) requise(s) vue(s)" in out, \
        f"le contrôle doit dire combien de requises il a vues : {out!r}"


def test_nominal_une_cible_non_inscriptible_dit_ecriture_impossible(pub, tmp_path, capsys):
    """S1 : publier par-dessus une copie installée NON inscriptible (mode 0444) échoue à l'écriture.

    C'est le chemin RÉEL du geste humain : republier par-dessus une copie installée que le compte
    ne peut pas réécrire. Le refus d'écriture doit être PRONONCÉ (rc 2, la cible et la cause
    nommées), la cible rester intacte, et aucun succès ne doit être annoncé.

    Le mode est posé sur la CIBLE elle-même (jamais sur le parent du bac), dans un bac jetable
    sous `tmp_path` : rien n'est écrit hors du bac, et le mode est rendu en sortie de cas pour que
    le nettoyage de pytest ne bute pas sur un fichier non inscriptible.

    Ce cas est DISCRIMINANT par construction : un outil qui avalerait l'échec d'écriture, ou qui
    annoncerait « publication établie » sans relire, rougit ici — et il est le seul à exécuter le
    `except OSError` de l'écriture (le cas du parent-FICHIER sort plus tôt, sur la lecture)."""
    assert os.geteuid() != 0, \
        "mesure invalide sous root : le mode 0444 n'y empêche pas l'écriture"
    bac = _Bac(tmp_path).write(installed=DIVERGENT_1)
    os.chmod(bac.target, 0o444)
    avant = bac.target_sha
    try:
        assert not os.access(bac.target, os.W_OK), "ancre : la cible doit être réellement fermée"
        rc, out, err = _run(pub, capsys, ["--publish", "--source", str(bac.source),
                                          "--target", str(bac.target), "--wrapper", str(bac.wrapper),
                                          "--require-env", REQUIRE_ENV_VALUE,
                                          "--home", str(bac.home)])
    finally:
        os.chmod(bac.target, 0o644)
    assert rc == EXIT_ERROR, f"cible en 0444 : rc={rc}\nstdout={out}\nstderr={err}"
    assert "ERREUR écriture impossible" in out, f"le refus doit dire l'échec d'écriture : {out!r}"
    assert str(bac.target) in out, f"le refus doit nommer la cible : {out!r}"
    assert "PermissionError" in out, f"le refus doit nommer la cause réelle : {out!r}"
    assert "publication établie" not in out, f"aucun faux succès : {out!r}"
    assert err.strip(), f"le refus doit être bruyant sur stderr : {err!r}"
    assert bac.target_sha == avant, "la cible non inscriptible doit rester intacte"


# ------------------------------------------------------------------------ limite ---

def test_limit_un_wrapper_au_chemin_absent_refuse_avant_toute_cible(pub, tmp_path, capsys):
    """S2 : un `--wrapper` dont le chemin est ABSENT refuse AVANT toute cible, dans les deux modes.

    Forme limite de la garde wrapper : le chemin n'existe pas (`FileNotFoundError`), là où le cas
    de lecture du wrapper en dossier levait `IsADirectoryError`. La conséquence doit être la même —
    rc 2, le chemin du wrapper nommé, la cause nommée — et la cible, absente ou divergente, doit
    rester telle quelle : le refus précède la résolution des cibles, pas seulement l'écriture.

    Le témoin d'inexistence est explicite : la cible passée en `--publish` n'existe pas avant, et
    doit encore ne pas exister après."""
    bac = _Bac(tmp_path).write(installed=DIVERGENT_1)
    absent = tmp_path / "wrapper_absent.sh"
    assert not absent.exists(), "ancre : le chemin du wrapper doit être absent"
    cible_absente = tmp_path / "installee_absente.py"
    avant = bac.target_sha
    for mode in ("--check", "--publish"):
        rc, out, err = _run(pub, capsys, [mode, "--source", str(bac.source),
                                          "--target", str(cible_absente), "--wrapper", str(absent),
                                          "--require-env", REQUIRE_ENV_VALUE,
                                          "--home", str(bac.home)])
        assert rc == EXIT_ERROR, f"{mode} wrapper absent : rc={rc}\nstdout={out}\nstderr={err}"
        assert "wrapper illisible" in out, f"{mode} : le refus doit dire l'illisible : {out!r}"
        assert str(absent) in out, f"{mode} : le refus doit nommer le chemin du wrapper : {out!r}"
        assert "FileNotFoundError" in out, f"{mode} : la cause réelle doit être nommée : {out!r}"
        assert str(cible_absente) not in out, \
            f"{mode} : le refus doit précéder toute cible (aucune cible n'est atteinte) : {out!r}"
        assert err.strip(), f"{mode} : le refus doit être bruyant sur stderr : {err!r}"
    assert not cible_absente.exists(), "le refus doit précéder toute écriture (cible jamais créée)"
    assert bac.target_sha == avant, "la copie installée divergente doit rester intacte"


def test_limit_le_home_vide_retombe_sur_le_repertoire_personnel_du_processus(pub, tmp_path,
                                                                            capsys, monkeypatch):
    """S2 : `--home ""` n'est pas un chemin : la branche `ns.home = None` de `main` s'exécute et la
    résolution retombe sur `Path.home()` DU PROCESSUS.

    Le répertoire personnel est **injecté** ici (`HOME` du processus, sous `tmp_path`) : aucun test
    ne lit ni n'écrit le répertoire personnel réel. Sans cette injection, `--home ""` irait
    chercher les copies installées réelles et la mesure dépendrait de la machine."""
    maison = tmp_path / "maison"
    profils = maison / ".hermes" / "profiles" / PROFIL_EXECUTE[0] / "scripts"
    seconde = maison / ".hermes" / "scripts"
    for d in (profils, seconde):
        d.mkdir(parents=True)
        (d / PROFIL_EXECUTE[1]).write_text(VERSIONED, encoding="utf-8")
    monkeypatch.setenv("HOME", str(maison))
    bac = _Bac(tmp_path).write()
    rc, out, err = _run(pub, capsys, ["--check", "--source", str(bac.source),
                                      "--target", "", "--wrapper", str(bac.wrapper),
                                      "--require-env", REQUIRE_ENV_VALUE, "--home", ""])
    assert rc == EXIT_OK, f"--home vide -> Path.home() du processus : rc={rc}\nstdout={out}\n{err}"
    for d in (profils, seconde):
        assert str(d / PROFIL_EXECUTE[1]) in out, \
            f"la copie résolue sous le HOME du processus doit être contrôlée : {out!r}"


def test_limit_le_contrat_de_variables_est_lu_par_defaut_quand_require_env_est_omis(pub, tmp_path,
                                                                                    capsys):
    """S2 : sans `--require-env`, le contrôle lit le contrat de la COPIE VERSIONNÉE (branche
    `required_env_names`) et le dit : il a vu le nombre de requises annoncé par le module.

    Contre-épreuve : la source est remplacée par une copie qui déclare UN SEUL nom — le message doit
    annoncer « 1 variable(s) requise(s) », ce qui prouve que la liste vient bien de la copie reçue
    et non de la constante figée (qui en compte trois)."""
    bac = _Bac(tmp_path).write(wrapper='# wrapper du contrat propre\nexport UNIQUE_VAR=1\n')
    # la copie versionnée déclare UN SEUL nom : la liste doit donc venir d'elle, pas du repli figé
    bac.source.write_text('REQUIRED_VARS = ("UNIQUE_VAR",)\n', encoding="utf-8")
    bac.target.write_text('REQUIRED_VARS = ("UNIQUE_VAR",)\n', encoding="utf-8")
    rc, out, err = _run(pub, capsys, ["--check", "--source", str(bac.source),
                                      "--target", str(bac.target), "--wrapper", str(bac.wrapper),
                                      "--home", str(bac.home)])
    assert rc == EXIT_OK, f"contrat lu par défaut : rc={rc}\nstdout={out}\nstderr={err}"
    assert "1 variable(s) requise(s) vue(s)" in out, \
        f"la liste doit venir de la copie versionnée (1 nom), pas du repli figé (3) : {out!r}"


def test_limit_le_motif_du_wrapper_du_depot_est_accepte_et_le_commentaire_refuse(pub, tmp_path,
                                                                                 capsys):
    """S2 : le wrapper versionné du dépôt exporte par MOTIF et doit passer ; les formes qui
    ressemblent à un export sans en être un (commentaire, affectation non exportée) sont refusées.

    Un contrôle qui n'accepterait que trois littéraux refuserait le wrapper du dépôt : le geste
    humain n'aboutirait jamais et la slice serait inerte. C'est la contre-épreuve de ce cas."""
    if not WRAPPER_DEPOT.exists():
        pytest.fail(f"wrapper versionné absent: {WRAPPER_DEPOT}")
    depot = pub.missing_exports(WRAPPER_DEPOT.read_text(encoding="utf-8"), REQUIRED)
    assert tuple(depot) == (), f"le wrapper du dépôt est refusé à tort : {depot!r}"

    bac = _Bac(tmp_path).write(wrapper=W_COMMENT_ONLY)
    rc, out, err = _run(pub, capsys, bac.argv())
    assert rc == EXIT_GAP, f"un wrapper sans export réel doit sortir en écart : rc={rc}\n{out}"
    for nom in REQUIRED:
        assert nom in out, f"le refus doit nommer {nom} : {out!r}"
    assert str(bac.wrapper) in out, f"le refus doit nommer le wrapper : {out!r}"
    assert "bascule est refusée" in out, f"le refus doit dire la conséquence : {out!r}"
    # un refus est BRUYANT sur les deux flux (un lecteur qui ne lit que stderr doit le voir)
    assert out.strip() and err.strip(), f"refus muet sur un flux : out={out!r} err={err!r}"


def test_limit_un_ecart_de_wrapper_seul_suffit_a_refuser_une_paire_alignee(pub, tmp_path, capsys):
    """S2 : l'écart ne vient PAS de l'identité — les deux copies sont identiques et le contrôle
    sort pourtant en 1, à cause du seul wrapper. Un outil qui ne regarderait que les fichiers
    rendrait 0 ici."""
    bac = _Bac(tmp_path).write(wrapper=W_BARE)
    avant = _snapshot(tmp_path)
    rc, out, _ = _run(pub, capsys, bac.argv())
    assert rc == EXIT_GAP, f"wrapper fautif + paire alignée : rc={rc}\n{out}"
    assert "ÉCART" in out, f"l'écart doit être prononcé : {out!r}"
    assert _snapshot(tmp_path) == avant, "un refus en mode contrôle ne doit rien écrire"


def test_limit_un_export_a_guillemet_non_ferme_est_lu_en_repli(pub, tmp_path):
    """S2 : un `export` que `shlex` ne peut pas découper (guillemet non fermé) est lu en repli.

    Sans le repli, la lecture lève et le contrôle tombe : le cas juge le comportement observable
    (la variable EST vue), pas le texte du module."""
    texte = ('#!/usr/bin/env bash\n'
             + "export PJ_ESCALATE_CHANNEL_ID='${X:-1}\n"          # guillemet non fermé
             + "\n".join(f"export {n}=1" for n in REQUIRED[1:]) + "\n"
             + "export -p PJ_ESCALATE_* # option ignorée, motif retenu\n")
    assert tuple(pub.missing_exports(texte, REQUIRED)) == (), \
        "la forme à guillemet non fermé doit être lue, pas faire échouer la lecture"
    # un motif glob n'est pas un nom : il couvre par correspondance, jamais par littéral
    noms, motifs = pub._exported_names("export PJ_ESCALATE_*\n")
    assert noms == set() and motifs == ["PJ_ESCALATE_*"], (noms, motifs)
    assert tuple(pub.missing_exports("export PJ_ESCALATE_*\n", REQUIRED)) == ()


def test_limit_un_target_vide_retombe_sur_les_copies_par_defaut(pub, tmp_path, capsys):
    """S2 : `--target ""` est traité comme ABSENT (jamais comme un chemin vide) : la résolution
    retombe sur les copies par défaut, sous le `HOME` injecté."""
    bac = _Bac(tmp_path).write()
    (bac.home / ".hermes" / "scripts").mkdir(parents=True)
    for p in (bac.home / ".hermes" / "profiles" / PROFIL_EXECUTE[0] / "scripts",
              bac.home / ".hermes" / "scripts"):
        p.mkdir(parents=True, exist_ok=True)
        (p / PROFIL_EXECUTE[1]).write_text(VERSIONED, encoding="utf-8")
    rc, out, err = _run(pub, capsys, ["--check", "--source", str(bac.source),
                                      "--target", "", "--wrapper", str(bac.wrapper),
                                      "--require-env", REQUIRE_ENV_VALUE, "--home", str(bac.home)])
    assert rc == EXIT_OK, f"cible vide -> cibles par défaut : rc={rc}\nstdout={out}\nstderr={err}"
    assert str(bac.home / ".hermes" / "scripts" / PROFIL_EXECUTE[1]) in out, out


def test_limit_la_resolution_des_cibles_n_est_jamais_vide(pub, tmp_path):
    """S2 : la garde « aucune cible à contrôler » de `_check` est DÉFENSIVE — elle est inatteignable
    par l'interface, et ce cas le mesure au lieu de le croire.

    `resolve_targets` rend soit les cibles reçues non vides, soit les deux copies par défaut : ni un
    `--target` vide, ni un `HOME` vide, ni une liste vide ne produisent un périmètre nul. La garde
    reste donc non couverte (2 statements + sa prise) et cela est DIT dans le handoff, sans pragma."""
    vides = [(), ("",), ("", ""), (None,), ("", None)]
    for entree in vides:
        assert pub.resolve_targets(entree, home=tmp_path), f"résolution vide pour {entree!r}"
    assert pub.resolve_targets(home=""), "un HOME vide ne vide pas la résolution"
    defauts = pub.resolve_targets(home=tmp_path)
    assert len(defauts) == 2 and all(str(p).startswith(str(tmp_path)) for p in defauts), defauts


def test_limit_un_ecart_de_fin_de_fichier_reste_un_ecart(pub, tmp_path, capsys):
    """S2 : la frontière de la définition documentée — deux contenus qui diffèrent par la fin de
    fichier ne sont PAS identiques, et comptent pourtant 0 ligne divergente (les lignes appariées
    sont égales, seule la longueur totale diffère).

    Une comparaison qui n'apparierait que les lignes crierait « identique » : ce cas la refuse."""
    cmp = pub.compare_copies(DIVERGENTE_FIN, VERSIONED)
    assert cmp.identical is False, f"fin de fichier différente = contenu différent : {cmp!r}"
    assert cmp.divergent_lines == 0 and cmp.installed_lines == cmp.versioned_lines, cmp
    bac = _Bac(tmp_path).write(installed=DIVERGENTE_FIN)
    rc, out, _ = _run(pub, capsys, bac.argv())
    assert rc == EXIT_GAP, f"un écart de fin de fichier doit sortir en 1 : rc={rc}\n{out}"
    assert _sha(DIVERGENTE_FIN) in out and _sha(VERSIONED) in out, \
        f"les deux empreintes (distinctes) doivent être imprimées : {out!r}"


def test_limit_un_perimetre_sans_fichier_de_code_n_annonce_pas_de_conformite(pub, tmp_path,
                                                                             capsys):
    """S2 : un diff qui ne touche que de la documentation laisse le mode périmètre sans rien à
    mesurer : rc 0, mais la sortie ne doit pas annoncer une conformité de couverture qu'aucune
    mesure n'appuie (« un vert vide ne prouve rien »)."""
    repo = _depot(tmp_path)
    (repo / "README.md").write_text("base\n\nune ligne de doc\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "doc")
    rc, out, err = _couverture(pub, capsys, tmp_path, repo, "HEAD~1", {})
    assert rc == EXIT_OK, f"un diff sans code n'est pas un écart de couverture : rc={rc}\n{out}"
    assert "aucun fichier de code" in out, f"le mode doit dire qu'il n'a rien mesuré : {out!r}"
    assert "conforme — tous les fichiers" not in out, \
        f"aucune conformité de couverture ne peut être annoncée sans mesure : {out!r}"


def test_limit_le_seuil_est_configurable_et_juge_le_fichier_du_perimetre(pub, tmp_path, capsys):
    """S2 : le fichier modifié EST nommé au rapport ; à 85 % il passe le seuil de 80 et échoue
    celui de 90. Le seuil n'est pas une constante cachée : il est reçu."""
    repo = _depot(tmp_path, touche="pipeline/outil.py", contenu="x = 1\n")
    contenu = {"pipeline/outil.py": {"summary": {"percent_covered": 85.0}}}
    rc, out, _ = _couverture(pub, capsys, tmp_path, repo, "HEAD~1", contenu)
    assert rc == EXIT_OK, f"85 % > 80 % : rc={rc}\n{out}"
    assert "pipeline/outil.py: 85.0%" in out, f"le fichier mesuré doit être nommé : {out!r}"
    rc2, out2, _ = _couverture(pub, capsys, tmp_path, repo, "HEAD~1", contenu, "--min", "90")
    assert rc2 == EXIT_GAP, f"85 % < 90 % : rc={rc2}\n{out2}"
    assert "ÉCART" in out2 and "85.0% < 90.0%" in out2, \
        f"l'écart doit nommer le fichier et les deux seuils : {out2!r}"


# ------------------------------------------------------------------------- erreur ---

def test_erreur_une_source_illisible_est_nommee_dans_les_deux_modes(pub, tmp_path, capsys):
    """S3 : `--source` qui n'est pas un fichier (ici un dossier) -> rc 2 nommant le chemin, et
    JAMAIS une trace d'exception. Le même refus vaut pour `--publish` (rien n'est écrit)."""
    bac = _Bac(tmp_path).write()
    dossier = tmp_path / "source_dossier"
    dossier.mkdir()
    avant = _snapshot(tmp_path)
    for mode in ("--check", "--publish"):
        rc, out, err = _run(pub, capsys, ["--source", str(dossier), "--target", str(bac.target),
                                          "--wrapper", str(bac.wrapper),
                                          "--require-env", REQUIRE_ENV_VALUE,
                                          "--home", str(bac.home), mode])
        assert rc == EXIT_ERROR, f"{mode} source illisible : rc={rc}\nstdout={out}\nstderr={err}"
        assert str(dossier) in out, f"{mode} : le refus doit nommer la source : {out!r}"
        assert "Traceback" not in err, f"{mode} : refus explicite attendu, pas une trace : {err!r}"
        assert err.strip(), f"{mode} : le refus doit être bruyant sur stderr : {err!r}"
    assert _snapshot(tmp_path) == avant, "une source illisible n'écrit rien"


def test_erreur_un_wrapper_fautif_refuse_la_publication_sans_rien_ecrire(pub, tmp_path, capsys):
    """S3 : `--publish` avec un wrapper qui n'exporte pas les requises -> rc 1 (écart), message
    « publication REFUSÉE », et la copie installée divergente reste INTACTE.

    C'est la moitié « publication » du cas limite de la slice 3 : le contrôle en `--check` ne suffit
    pas, c'est `--publish` qui écrit — et il doit refuser AVANT d'écrire (branches 435-438)."""
    bac = _Bac(tmp_path).write(installed=DIVERGENT_1, wrapper=W_BARE)
    avant = bac.target_sha
    rc, out, err = _run(pub, capsys, ["--publish", "--source", str(bac.source),
                                      "--target", str(bac.target), "--wrapper", str(bac.wrapper),
                                      "--require-env", REQUIRE_ENV_VALUE, "--home", str(bac.home)])
    assert rc == EXIT_GAP, f"wrapper fautif en publication : rc={rc}\nstdout={out}\nstderr={err}"
    assert "publication REFUSÉE" in out and "aucun fichier n'a été écrit" in out, \
        f"le refus doit dire sa conséquence : {out!r}"
    assert REQUIRED[0] in out, f"le refus doit nommer la variable manquante : {out!r}"
    assert bac.target_sha == avant, \
        "la copie installée divergente a été modifiée : le refus doit précéder toute écriture"


def test_erreur_une_ecriture_silencieusement_incomplete_est_detectee(pub, tmp_path, capsys,
                                                                     monkeypatch):
    """S3 : l'identité est re-vérifiée APRÈS écriture — un disque qui tronquerait l'écriture ne doit
    pas produire un « publication établie ».

    Le défaut est injecté par le seam des E/S : `_read_text` est détourné pour rendre une copie
    TRONQUÉE quand on relit la cible (jamais quand on lit la source ou le wrapper). Un outil qui
    publierait sans relire annoncerait une publication qui n'a pas eu lieu."""
    bac = _Bac(tmp_path).write(installed=DIVERGENT_1)
    vrai_read = pub._read_text
    cible = str(bac.target)

    def _read_tronque(path):
        texte = vrai_read(path)
        return texte[:-5] if str(path) == cible else texte

    monkeypatch.setattr(pub, "_read_text", _read_tronque)
    rc, out, err = _run(pub, capsys, ["--publish", "--source", str(bac.source),
                                      "--target", str(bac.target), "--wrapper", str(bac.wrapper),
                                      "--require-env", REQUIRE_ENV_VALUE, "--home", str(bac.home)])
    assert rc == EXIT_ERROR, f"copie écrite non identique : rc={rc}\nstdout={out}\nstderr={err}"
    assert "publication NON établie" in out, f"le refus doit dire l'échec : {out!r}"
    assert "publication établie" not in out, f"aucun faux succès : {out!r}"
    assert str(bac.target) in out, f"le refus doit nommer la cible : {out!r}"


def test_erreur_un_wrapper_illisible_refuse_avant_toute_bascule(pub, tmp_path, capsys):
    """S3 : un wrapper illisible (dossier) -> rc 2, et la copie installée n'est pas touchée."""
    bac = _Bac(tmp_path).write(installed=DIVERGENT_1)
    dossier = tmp_path / "wrapper_dossier"
    dossier.mkdir()
    avant = bac.target_sha
    rc, out, err = _run(pub, capsys, ["--publish", "--source", str(bac.source),
                                      "--target", str(bac.target), "--wrapper", str(dossier),
                                      "--require-env", REQUIRE_ENV_VALUE, "--home", str(bac.home)])
    assert rc == EXIT_ERROR, f"wrapper illisible : rc={rc}\nstdout={out}\nstderr={err}"
    assert str(dossier) in out, f"le refus doit nommer le wrapper : {out!r}"
    assert bac.target_sha == avant, "aucune bascule ne doit avoir lieu"


def test_erreur_publish_exige_une_cible_explicite(pub, tmp_path, capsys):
    """S3 : `--publish` sans cible — ou avec une cible vide — refuse au lieu de retomber sur un
    chemin par défaut. Une bascule sur un chemin deviné serait le pire des succès."""
    bac = _Bac(tmp_path).write()
    avant = _snapshot(tmp_path)
    for cibles in ([], ["--target", ""]):
        rc, out, err = _run(pub, capsys, ["--publish", "--source", str(bac.source), *cibles,
                                          "--wrapper", str(bac.wrapper),
                                          "--require-env", REQUIRE_ENV_VALUE,
                                          "--home", str(bac.home)])
        assert rc == EXIT_ERROR, f"cibles={cibles!r} : rc={rc}\nstdout={out}\nstderr={err}"
        assert "au moins un --target explicite" in out, f"le refus doit dire la règle : {out!r}"
    assert _snapshot(tmp_path) == avant, "un refus ne doit rien écrire"


def test_erreur_une_cible_qui_n_est_pas_un_fichier_est_nommee(pub, tmp_path, capsys):
    """S3 : une cible qui n'est pas un fichier (dossier) est ILLISIBLE : rc 2, chemin nommé, et le
    message dit que l'identité n'est PAS vérifiée — aucun succès n'est annoncé."""
    bac = _Bac(tmp_path).write()
    dossier = tmp_path / "cible_dossier"
    dossier.mkdir()
    rc, out, err = _run(pub, capsys, ["--check", "--source", str(bac.source),
                                      "--target", str(dossier), "--wrapper", str(bac.wrapper),
                                      "--require-env", REQUIRE_ENV_VALUE, "--home", str(bac.home)])
    assert rc == EXIT_ERROR, f"cible illisible : rc={rc}\nstdout={out}\nstderr={err}"
    assert str(dossier) in out, f"le refus doit nommer la cible : {out!r}"
    assert "identité NON vérifiée" in out, f"le refus doit dire ce qui n'est pas établi : {out!r}"
    assert "verdict" not in out, f"aucun verdict ne doit être prononcé sur une cible illisible : {out!r}"


def test_erreur_une_ecriture_impossible_n_est_pas_un_succes(pub, tmp_path, capsys):
    """S3 : la cible est sous un parent qui est un FICHIER -> l'écriture échoue (rc 2) en nommant
    la cible. Un outil qui avalerait l'échec d'écriture annoncerait une publication qui n'a pas eu
    lieu."""
    bac = _Bac(tmp_path).write()
    parent = tmp_path / "un_fichier"
    parent.write_text("occupé\n", encoding="utf-8")
    cible = parent / "sub" / "installee.py"
    rc, out, err = _run(pub, capsys, ["--publish", "--source", str(bac.source),
                                      "--target", str(cible), "--wrapper", str(bac.wrapper),
                                      "--require-env", REQUIRE_ENV_VALUE, "--home", str(bac.home)])
    assert rc == EXIT_ERROR, f"écriture impossible : rc={rc}\nstdout={out}\nstderr={err}"
    assert str(cible) in out, f"le refus doit nommer la cible : {out!r}"
    assert not cible.exists(), "aucune cible ne doit exister après un échec d'écriture"
    assert parent.read_text(encoding="utf-8") == "occupé\n", "le parent fichier est intact"


def test_erreur_un_module_non_chargeable_est_nomme(pub, tmp_path):
    """S3 : `_load_module_by_path` refuse en NOMMANT le chemin quand la spécification n'est pas
    constructible (extension inconnue). C'est la branche défensive : elle est atteinte, pas
    supposée inatteignable."""
    inconnu = tmp_path / "chargeable.xyz"
    inconnu.write_text("x = 1\n", encoding="utf-8")
    assert importlib.util.spec_from_file_location("n", str(inconnu)) is None, \
        "ancre : cette extension ne produit bien aucune spécification"
    with pytest.raises(ImportError) as exc:
        pub._load_module_by_path(inconnu, "n")
    assert str(inconnu) in str(exc.value), str(exc.value)


def test_erreur_le_mode_perimetre_exige_le_rapport_et_la_base(pub, tmp_path, capsys):
    """S3 : `--coverage` sans `--coverage-json` ou sans `--diff-base` refuse (rc 2) en nommant les
    deux options — sans jamais tenter un diff."""
    bac = _Bac(tmp_path).write()
    for argv in (["--coverage", "--diff-base", "HEAD"],
                 ["--coverage", "--coverage-json", str(tmp_path / "cov.json")]):
        rc, out, err = _run(pub, capsys, [*argv, "--home", str(bac.home)])
        assert rc == EXIT_ERROR, f"{argv} : rc={rc}\nstdout={out}\nstderr={err}"
        assert "--coverage-json" in out and "--diff-base" in out, \
            f"le refus doit nommer les deux options : {out!r}"


def test_erreur_un_rapport_illisible_et_un_perimetre_inexploitable_sont_nommes(pub, tmp_path,
                                                                              capsys):
    """S3 : deux erreurs d'exécution distinctes — le rapport n'est pas un fichier (OSError) et la
    référence de diff n'existe pas dans le dépôt (git en échec) — chacune en rc 2."""
    repo = _depot(tmp_path, touche="pipeline/outil.py", contenu="x = 1\n")
    dossier = tmp_path / "rapport_dossier"
    dossier.mkdir()
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    rc, out, err = _run(pub, capsys, ["--coverage", "--coverage-json", str(dossier),
                                      "--diff-base", "HEAD~1", "--repo", str(repo),
                                      "--home", str(home)])
    assert rc == EXIT_ERROR, f"rapport illisible : rc={rc}\nstdout={out}\nstderr={err}"
    assert str(dossier) in out, f"le refus doit nommer le rapport : {out!r}"
    rapport = _rapport(tmp_path, {"pipeline/outil.py": {"summary": {"percent_covered": 99.0}}})
    rc2, out2, _ = _run(pub, capsys, ["--coverage", "--coverage-json", str(rapport),
                                      "--diff-base", "refs/inexistante", "--repo", str(repo),
                                      "--home", str(home)])
    assert rc2 == EXIT_ERROR, f"périmètre inexploitable : rc={rc2}\nstdout={out2}"
    assert "inexploitable" in out2, f"le refus doit dire l'inexploitable : {out2!r}"


def test_erreur_un_perimetre_vide_et_un_rapport_muet_ne_sont_pas_des_verts(pub, tmp_path, capsys):
    """S3 : les deux vacuités que le mode périmètre existe pour refuser — un diff sans fichier
    modifié et un rapport qui n'instancie pas le fichier du diff — sortent en rc 2 en le disant."""
    repo = _depot(tmp_path)
    rc, out, _ = _couverture(pub, capsys, tmp_path, repo, "HEAD", {})
    assert rc == EXIT_ERROR, f"périmètre vide : rc={rc}\n{out}"
    assert "vide" in out.lower(), f"le message doit dire le périmètre vide : {out!r}"
    repo2 = _depot(tmp_path / "bis", touche="pipeline/outil.py", contenu="x = 1\n")
    rc2, out2, _ = _couverture(pub, capsys, tmp_path, repo2, "HEAD~1",
                               {"pipeline/autre.py": {"summary": {"percent_covered": 95.0}}})
    assert rc2 == EXIT_ERROR, f"rapport muet : rc={rc2}\n{out2}"
    assert "pipeline/outil.py" in out2 and "muet" in out2, \
        f"le refus doit nommer le fichier non mesuré : {out2!r}"
