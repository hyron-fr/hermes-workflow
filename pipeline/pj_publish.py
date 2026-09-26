#!/usr/bin/env python3
"""pj_publish — publie la copie installée de `pj_escalate.py` et contrôle son identité.

POURQUOI CET OUTIL EXISTE (issue #4, arbitrage humain `2a`)
----------------------------------------------------------
`pj_escalate.py` s'exécute **depuis le profil** (`~/.hermes/profiles/<profil>/scripts/`,
déclenché par un cron `no_agent` toutes les 3 minutes), pas depuis le dépôt. Le modèle
des deux copies est **conservé** : ce qui manque n'est pas le repointage du wrapper mais
une **étape de publication** et un **contrôle d'identité** entre la copie versionnée et
la copie installée. L'écart cesse d'être une découverte tardive, il devient un contrôle
de livraison.

La copie versionnée est **assainie** : les identifiants Discord et le chemin personnel
sont devenus des variables d'environnement (slice 1). L'identité ne peut donc porter que
sur le fichier **tel qu'il s'exécute** — c'est-à-dire sur son contenu, accompagné du
contrôle des `export` du wrapper qui lui fournit ces variables. Un contenu identique avec
un wrapper qui n'exporte pas les requises est une livraison morte : le tick sortirait en
`rc=2`, bruyamment, sans plus aucune escalade.

LE GESTE HUMAIN — l'ordre est un garde-fou, pas une commodité
-------------------------------------------------------------
1. `python3 pipeline/pj_publish.py --check --wrapper <wrapper> --require-env PJ_ESCALATE_CHANNEL_ID,PJ_ESCALATE_USER_ID,PJ_ESCALATE_GUILD_ID`
   → constate l'écart **et** l'absence d'`export` ;
2. **l'humain** ajoute les `export` requis au wrapper (hors dépôt) ;
3. re-`--check` → prouve que la variable est vue (le contrôle la nomme si elle manque) ;
4. `--publish --target <copie installée>` → bascule la copie ;
5. exécution d'un tick → il doit rester **muet** (rc=0, 0 escalade parasite).

Basculer la copie **avant** les `export` tue le tick (`ConfigError`, rc=2, `KeyError`
dans la version d'avant) : c'est la raison d'être de l'étape 1-3. `--publish` refuse donc
de basculer si le contrôle des exports du wrapper échoue.

CODES DE SORTIE
---------------
`0` conforme — `1` écart livré (divergence, export manquant, fichier modifié sous le
seuil) — `2` erreur d'exécution (cible ou source absente/illisible, périmètre vide,
rapport qui n'instancie pas le fichier modifié, argument manquant). Priorité : 2 > 1 > 0.

Toutes les lignes de diagnostic vont sur **stdout** (l'humain les lit au terminal, un
agent les capture) ; les lignes de refus sont **aussi** écrites sur stderr, pour que le
« bruyant » ne dépende pas du flux qu'un lecteur choisit.

Aucune écriture en `--check` (ni fichier temporaire, ni `mkdir`) — et `--publish` est
**idempotent** : une cible déjà identique n'est pas réécrite.

Usage :
  pj_publish.py [--check | --publish] [--source S] [--target T ...]
                [--wrapper W --require-env V1,V2]
                [--coverage --coverage-json J --diff-base REF [--repo R] [--min 80]]
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import importlib.util
import json
import re
import shlex
import sys
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Iterable, Sequence

HERE = Path(__file__).resolve().parent

# Copie versionnée : le foyer canonique est `pipeline/` (README §4 : `cp pipeline/*.py
# ~/.hermes/profiles/pj-master/scripts/`). Résolu depuis l'emplacement du fichier —
# aucun chemin de machine.
DEFAULT_SOURCE = HERE / "pj_escalate.py"

# Profil dont le dossier `scripts/` est exécuté par le cron. Ce n'est pas un secret :
# c'est la cible de déploiement documentée (`README.md` §4), et elle se dérive du
# répertoire personnel.
PROFILE_NAME = "pj-master"
TOOL_NAME = "pj_escalate.py"

# Contrat de variables de la slice 1 (`pipeline/pj_escalate.py`, REQUIRED_VARS) — repli
# si la copie versionnée n'est pas importable. Les deux listes ne peuvent pas diverger :
# `required_env_names()` lit la première quand elle est là.
DEFAULT_REQUIRED = ("PJ_ESCALATE_CHANNEL_ID", "PJ_ESCALATE_USER_ID", "PJ_ESCALATE_GUILD_ID")

DEFAULT_MIN = 80.0

EXIT_OK = 0
EXIT_GAP = 1
EXIT_ERROR = 2


# --------------------------------------------------------------------------- pure ---

def digest_of(text: str) -> str:
    """`sha256` hexadécimal du contenu reçu. **Pur** : aucun accès disque, aucun réseau."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Comparison:
    """Verdict d'un contrôle d'identité entre une copie installée et une copie versionnée.

    **L'ordre des arguments de `compare_copies` est celui du banc** : `(installed_text,
    versioned_text)` — la copie *installée* (celle que le tick exécute) en premier, la
    copie *versionnée* (celle du dépôt) en second. C'est l'ordre du contrat de la slice 3,
    et il est figé.

    Accès par **attribut** (`cmp.identical`) et par **clé** (`cmp["identical"]`) : le
    verdict est consommé par un humain en CLI et par des bancs de test, les deux formes
    sont figées.

    `divergent_lines` apparie les lignes **par index** (rang), ce n'est pas une distance
    d'édition LCS : deux contenus décalés d'une ligne comptent `n - 1` divergences. Cette
    définition est volontairement la plus simple à énoncer, et c'est celle sous laquelle
    les deux définitions usuelles (« positions qui diffèrent » / « morceaux de diff »)
    s'accordent sur l'écart d'une ou de trois lignes isolées.
    """

    identical: bool
    installed_digest: str
    versioned_digest: str
    divergent_lines: int
    installed_lines: int
    versioned_lines: int

    # Alias de lecture : la copie versionnée est la « source » du geste de publication, la
    # copie installée sa « cible ». Conservés pour un lecteur du contrat publié.
    @property
    def source_digest(self) -> str:
        return self.versioned_digest

    @property
    def target_digest(self) -> str:
        return self.installed_digest

    @property
    def source_lines(self) -> int:
        return self.versioned_lines

    @property
    def target_lines(self) -> int:
        return self.installed_lines

    def keys(self) -> tuple:
        return tuple(f.name for f in fields(self))

    def __getitem__(self, key: str):
        if not hasattr(self, key) or key.startswith("_"):
            raise KeyError(key)
        return getattr(self, key)

    def get(self, key: str, default=None):
        return getattr(self, key, default)

    def to_dict(self) -> dict:
        return {k: self[k] for k in self.keys()}


def compare_copies(installed_text: str, versioned_text: str) -> Comparison:
    """Compare la copie installée à la copie versionnée. **Pur**, sans E/S.

    Ordre du contrat : `(installed_text, versioned_text)`.
    """
    inst_lines = installed_text.splitlines()
    vers_lines = versioned_text.splitlines()
    divergent = sum(1 for a, b in zip(inst_lines, vers_lines) if a != b)
    divergent += abs(len(inst_lines) - len(vers_lines))
    return Comparison(
        identical=installed_text == versioned_text,
        installed_digest=digest_of(installed_text),
        versioned_digest=digest_of(versioned_text),
        divergent_lines=divergent,
        installed_lines=len(inst_lines),
        versioned_lines=len(vers_lines),
    )


# Alias de tolérance de nom : même implémentation, noms alternatifs acceptés par le
# contrat (`contrat-3`, §alias_de_tolerance_de_nom).
compare_contents = compare_copies
compare_identity = compare_copies


def _strip_comment(line: str) -> str:
    """Retire un commentaire `#` hors guillemets (un `#` en début ou précédé d'espace)."""
    out = []
    quote = None
    for i, ch in enumerate(line):
        if quote:
            out.append(ch)
            if ch == quote:
                quote = None
            continue
        if ch in "\"'":
            quote = ch
            out.append(ch)
            continue
        if ch == "#" and (i == 0 or line[i - 1].isspace()):
            break
        out.append(ch)
    return "".join(out)


_WORD_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_GLOB_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*[*?][A-Za-z0-9_*?]*")


def _exported_names(wrapper_text: str) -> tuple[set, list]:
    """Noms exportés **littéralement** et **motifs** (`export PJ_ESCALATE_*`).

    Reconnaît `export VAR=…`, `export VAR`, `export VAR1 VAR2`, et une couverture par
    **motif** (`export PJ_ESCALATE_*`, ou un `case` avec motif glob suivi de
    `export "$name=$value"`, forme du wrapper versionné). Une **affectation non
    exportée** (`VAR=…`) ne compte pas : c'est précisément le défaut que ce contrôle
    existe pour voir.
    """
    names: set = set()
    patterns: list = []
    for raw in wrapper_text.splitlines():
        line = _strip_comment(raw).strip()
        if not line:
            continue
        for pat in _GLOB_RE.findall(line):
            if "*" in pat or "?" in pat:
                if pat not in patterns:
                    patterns.append(pat)
        m = re.search(r"(?:^|[;&|(]|\s)export\s+(.+)$", line)
        if not m:
            continue
        try:
            words = shlex.split(m.group(1))
        except ValueError:
            words = m.group(1).split()
        for word in words:
            if word.startswith("-"):
                continue
            name = word.split("=", 1)[0]
            if _WORD_RE.match(name):
                names.add(name)
    return names, patterns


def missing_exports(wrapper_text: str, required: Sequence[str]) -> list:
    """Noms de `required` **absents** des exports du wrapper, dans l'ordre de `required`.

    **Pur** : prend le contenu du wrapper, jamais un chemin — le banc de test n'a donc
    aucun accès disque à faire.
    """
    names, patterns = _exported_names(wrapper_text)
    out = []
    for want in required:
        if want in names:
            continue
        if any(fnmatch.fnmatchcase(want, pat) for pat in patterns):
            continue
        out.append(want)
    return out


missing_required_exports = missing_exports
wrapper_missing_vars = missing_exports


def resolve_targets(targets: Iterable[str] = (), home=None) -> list:
    """Copies installées à contrôler : celles reçues, sinon les deux copies connues.

    Les deux copies installées connues sont `<HOME>/.hermes/profiles/<profil>/scripts/
    <outil>` (celle que le cron exécute) et `<HOME>/.hermes/scripts/<outil>` (la copie
    que la skill d'escalade désigne comme « là où vit le correctif »). `HOME` est
    injectable : aucun chemin de machine n'est codé.
    """
    given = [t for t in targets if t]
    if given:
        return [Path(t).expanduser() for t in given]
    root = Path(home) if home else Path.home()
    return [
        root / ".hermes" / "profiles" / PROFILE_NAME / "scripts" / TOOL_NAME,
        root / ".hermes" / "scripts" / TOOL_NAME,
    ]


def required_env_names(source: Path) -> tuple:
    """Liste des variables requises : lue sur la copie versionnée, sinon le contrat figé.

    Lecture par **import** (comportement), pas par lecture de texte : la liste ne peut
    pas dériver de celle que le module exécute.
    """
    try:
        mod = _load_module_by_path(source, "pj_publish_subject")
        names = tuple(getattr(mod, "REQUIRED_VARS"))
        if names:
            return names
    except Exception:  # noqa: BLE001 — la copie peut être absente ou non importable
        pass
    return DEFAULT_REQUIRED


# ------------------------------------------------------------------------ entrées ---

def _load_module_by_path(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, str(path))
    if spec is None or spec.loader is None:  # pragma: no cover - garde défensive
        raise ImportError(f"module non chargeable : {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _read_text(path: Path) -> str:
    """Lit un fichier texte. Toute illisibilité remonte en `OSError` (jamais un `""`)."""
    return Path(path).read_text(encoding="utf-8")


def _emit(line: str, *, error: bool = False) -> None:
    """Un diagnostic : toujours sur stdout ; les refus aussi sur stderr."""
    print(line)
    if error:
        print(line, file=sys.stderr)


def _digest_lines(label: str, path, digest: str, lines: int) -> None:
    _emit(f"[pj-publish] {label}: {path}")
    _emit(f"[pj-publish]     sha256={digest} lignes={lines}")


def _report(cmp: Comparison, source, target) -> None:
    """Décrit l'écart : le digest des DEUX copies et le nombre de lignes divergentes.

    `source` est la copie **versionnée** (le dépôt), `target` la copie **installée** (celle
    que le tick exécute). Les deux digests sont **toujours** imprimés, y compris identiques :
    c'est la seule façon de vérifier qu'un contrôle a bien lu les deux fichiers.
    """
    _digest_lines("versionnée", source, cmp.versioned_digest, cmp.versioned_lines)
    _digest_lines("installée ", target, cmp.installed_digest, cmp.installed_lines)
    _emit(f"[pj-publish]     lignes divergentes: {cmp.divergent_lines}")
    if cmp.identical:
        _emit(f"[pj-publish] verdict: les deux copies sont identiques ({target})")
    else:
        _emit(f"[pj-publish] verdict: divergence — {cmp.divergent_lines} ligne(s) "
              f"divergente(s) entre {source} et {target}")


# --------------------------------------------------------------------------- modes ---

def _check(ns, source: Path) -> int:
    """Contrôle d'identité (lecture seule) + contrôle des exports du wrapper."""
    try:
        source_text = _read_text(source)
    except OSError as exc:
        _emit(f"[pj-publish] ERREUR source illisible: {source} ({exc.__class__.__name__}: "
              f"{exc})", error=True)
        return EXIT_ERROR

    gap = False

    # Le contrôle des exports vient EN PREMIER : inutile de décrire une identité que le
    # wrapper ne rendrait pas exécutable — et c'est lui qui décide du refus de bascule.
    if ns.wrapper:
        rc = _check_wrapper(ns, source)
        if rc == EXIT_ERROR:
            return EXIT_ERROR
        gap = gap or rc == EXIT_GAP

    targets = resolve_targets(ns.target, home=ns.home)
    if not targets:
        _emit("[pj-publish] ERREUR aucune cible à contrôler (--target)", error=True)
        return EXIT_ERROR

    for target in targets:
        target = Path(target)
        try:
            target_text = _read_text(target)
        except OSError as exc:
            _emit(f"[pj-publish] ERREUR cible illisible: {target} "
                  f"({exc.__class__.__name__}: {exc}) — identité NON vérifiée "
                  f"(aucun succès n'est annoncé)", error=True)
            return EXIT_ERROR
        cmp = compare_copies(target_text, source_text)
        _report(cmp, source, target)
        gap = gap or not cmp.identical

    if gap:
        _emit("[pj-publish] ÉCART — la copie installée n'est pas conforme à la copie "
              "versionnée", error=True)
        return EXIT_GAP
    _emit("[pj-publish] conforme — identité établie")
    return EXIT_OK


def _check_wrapper(ns, source: Path) -> int:
    """Contrôle des `export` du wrapper. Rend `EXIT_OK`, `EXIT_GAP` ou `EXIT_ERROR`."""
    wrapper = Path(ns.wrapper)
    try:
        wrapper_text = _read_text(wrapper)
    except OSError as exc:
        _emit(f"[pj-publish] ERREUR wrapper illisible: {wrapper} "
              f"({exc.__class__.__name__}: {exc})", error=True)
        return EXIT_ERROR

    required = ns.require_env
    if required is None:
        required = list(required_env_names(source))
    missing = missing_exports(wrapper_text, required)
    if missing:
        for name in missing:
            _emit(f"[pj-publish] export manquant: {name} — absent du wrapper {wrapper}",
                  error=True)
        _emit(f"[pj-publish] le wrapper {wrapper} n'exporte pas {len(missing)} variable(s) "
              f"requise(s) : la bascule est refusée", error=True)
        return EXIT_GAP
    _emit(f"[pj-publish] exports du wrapper {wrapper}: conformes "
          f"({len(required)} variable(s) requise(s) vue(s))")
    return EXIT_OK


def _publish(ns, source: Path) -> int:
    """Bascule la copie installée. Refuse avant toute écriture si le wrapper est fautif."""
    try:
        source_text = _read_text(source)
    except OSError as exc:
        _emit(f"[pj-publish] ERREUR source illisible: {source} "
              f"({exc.__class__.__name__}: {exc})", error=True)
        return EXIT_ERROR

    if not [t for t in (ns.target or []) if t]:
        _emit("[pj-publish] ERREUR --publish exige au moins un --target explicite "
              "(aucune écriture dans un chemin par défaut)", error=True)
        return EXIT_ERROR

    wrapper_rc = EXIT_OK
    if ns.wrapper:
        wrapper_rc = _check_wrapper(ns, source)
        if wrapper_rc == EXIT_ERROR:
            return EXIT_ERROR
    if wrapper_rc == EXIT_GAP:
        _emit("[pj-publish] publication REFUSÉE : le wrapper n'exporte pas les variables "
              "requises — aucun fichier n'a été écrit", error=True)
        return EXIT_GAP

    for target in resolve_targets(ns.target, home=ns.home):
        target = Path(target)
        try:
            before = _read_text(target)
        except FileNotFoundError:
            before = None
        except OSError as exc:
            _emit(f"[pj-publish] ERREUR cible illisible: {target} "
                  f"({exc.__class__.__name__}: {exc})", error=True)
            return EXIT_ERROR

        if before is not None and compare_copies(before, source_text).identical:
            # Idempotence : l'outil peut tourner pendant la bascule, une cible déjà
            # conforme n'est pas réécrite (et son horodatage ne bouge pas).
            _emit(f"[pj-publish] {target}: déjà identique, non réécrite")
            _report(compare_copies(before, source_text), source, target)
            continue

        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(source_text, encoding="utf-8")
            after = _read_text(target)
        except OSError as exc:
            _emit(f"[pj-publish] ERREUR écriture impossible: {target} "
                  f"({exc.__class__.__name__}: {exc})", error=True)
            return EXIT_ERROR

        cmp = compare_copies(after, source_text)
        if not cmp.identical:
            _emit(f"[pj-publish] ERREUR la copie écrite {target} n'est pas identique à la "
                  f"source — publication NON établie", error=True)
            return EXIT_ERROR
        state = "corrigée" if before is not None else "créée"
        _emit(f"[pj-publish] {target}: {state} (identité vérifiée après écriture)")
        _report(cmp, source, target)

    _emit("[pj-publish] publication établie — toutes les cibles sont identiques à la "
          "copie versionnée")
    return EXIT_OK


def _load_gate():
    """Charge `pj_coverage_gate.py` **par chemin** (ses sémantiques ne sont pas dupliquées).

    La clé du rapport est relative au répertoire où le reporter a tourné : c'est le
    `--repo`/le `git diff` qui fixe le référentiel, pas ce module.
    """
    return _load_module_by_path(HERE / "pj_coverage_gate.py", "pj_publish_gate")


def _check_coverage(ns) -> int:
    """Mode périmètre : un vert vide ne prouve rien, un rapport muet non plus.

    Les sémantiques (`is_code_file`, `changed_files`, `violations`, `parse_coverage_json`)
    sont **celles du gate**, importé par chemin : ce mode n'ajoute que les deux
    non-vacuités que le gate ne sait pas refuser (périmètre vide, clé absente du rapport).
    """
    if not ns.coverage_json or not ns.diff_base:
        _emit("[pj-publish] ERREUR --coverage exige --coverage-json et --diff-base",
              error=True)
        return EXIT_ERROR

    report_path = Path(ns.coverage_json)
    gate = _load_gate()
    try:
        changed = gate.changed_files(ns.repo, ns.diff_base)
        pct = gate.parse_coverage_json(json.loads(report_path.read_text(encoding="utf-8")))
    except OSError as exc:
        _emit(f"[pj-publish] ERREUR rapport de couverture illisible: {report_path} "
              f"({exc.__class__.__name__}: {exc})", error=True)
        return EXIT_ERROR
    except Exception as exc:  # noqa: BLE001 — json invalide, git en échec
        _emit(f"[pj-publish] ERREUR périmètre ou rapport inexploitable "
              f"({exc.__class__.__name__}: {exc})", error=True)
        return EXIT_ERROR

    _emit(f"[pj-publish] périmètre: {len(changed)} fichier(s) modifié(s) depuis "
          f"{ns.diff_base}")
    if not changed:
        _emit(f"[pj-publish] ERREUR PÉRIMÈTRE VIDE — aucun fichier modifié depuis "
              f"{ns.diff_base} : un vert vide ne prouve rien (aucun succès annoncé)",
              error=True)
        return EXIT_ERROR

    code_files = sorted(f for f in changed if gate.is_code_file(f))
    if not code_files:
        _emit("[pj-publish] aucun fichier de code dans le périmètre du diff — rien à "
              "mesurer (les fichiers de test et de documentation sont hors du gate)")
        return EXIT_OK

    mutes = [f for f in code_files if f not in pct]
    for f in mutes:
        _emit(f"[pj-publish] ERREUR le rapport de couverture ne mesure pas {f} — "
              f"un rapport muet n'est pas un vert", error=True)
    if mutes:
        return EXIT_ERROR

    for f in code_files:
        _emit(f"[pj-publish] {f}: {pct[f]}% (seuil {ns.min}%)")
    bad = [(f, v) for f, v in gate.violations(pct, ns.min, scope=set(code_files))]
    for f, v in bad:
        _emit(f"[pj-publish] {f}: {v}% < {ns.min}%")
    if bad:
        _emit(f"[pj-publish] ÉCART — {len(bad)} fichier(s) de code du périmètre sous le "
              f"seuil de {ns.min}%", error=True)
        return EXIT_GAP
    _emit("[pj-publish] conforme — tous les fichiers de code du périmètre sont nommés au "
          "rapport et au-dessus du seuil")
    return EXIT_OK


# ----------------------------------------------------------------------------- CLI ---

def _parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="pj_publish.py",
        description="Publie la copie installée de pj_escalate.py et contrôle son "
                    "identité avec la copie versionnée.",
    )
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true",
                      help="contrôle seul, lecture seule (défaut)")
    mode.add_argument("--publish", action="store_true",
                      help="bascule la copie installée (exige --target)")
    ap.add_argument("--source", default="", help="copie versionnée (défaut: pipeline/)")
    ap.add_argument("--target", action="append", default=[],
                    help="copie installée à contrôler/basculer (répétable)")
    ap.add_argument("--wrapper", default="", help="wrapper cron à contrôler")
    ap.add_argument("--require-env", default=None,
                    help="variables requises, séparées par des virgules (défaut: le "
                         "contrat de la copie versionnée)")
    ap.add_argument("--home", default="", help="répertoire personnel (défaut: HOME)")
    ap.add_argument("--coverage", action="store_true", help="mode périmètre de couverture")
    ap.add_argument("--coverage-json", default="", help="rapport JSON de couverture")
    ap.add_argument("--diff-base", default="", help="référence du diff (ex. origin/dev)")
    ap.add_argument("--repo", default=".", help="racine du dépôt pour le diff")
    ap.add_argument("--min", type=float, default=DEFAULT_MIN, help="seuil par fichier")
    return ap


def _parse_required(raw):
    if raw is None:
        return None
    names = []
    for chunk in raw.replace(" ", ",").split(","):
        chunk = chunk.strip()
        if chunk and chunk not in names:
            names.append(chunk)
    return names


def main(argv=None) -> int:
    """Entrée du programme : **rend** le code de sortie (ne fait pas `sys.exit`)."""
    ns = _parser().parse_args(list(sys.argv[1:] if argv is None else argv))
    ns.require_env = _parse_required(ns.require_env)
    if not ns.home:
        ns.home = None

    source = Path(ns.source) if ns.source else DEFAULT_SOURCE
    if ns.coverage:
        return _check_coverage(ns)
    if ns.publish:
        return _publish(ns, source)
    return _check(ns, source)


if __name__ == "__main__":
    sys.exit(main())
