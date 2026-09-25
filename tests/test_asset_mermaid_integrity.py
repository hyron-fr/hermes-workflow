#!/usr/bin/env python3
"""Banc d'intégrité de l'asset vendu `bridge/mermaid.min.js` (issue #7).

Le dépôt versionne un bundle esbuild (mermaid, 3 572 657 o) dans lequel un
sanitizer de secrets a substitué le littéral numérique `16666666666666666`
(fraction 1/6, rampe de teinte HSL) par le placeholder `${DISCORD_ID}` en
position de littéral numérique : `node --check` rc=1. Ce banc refuse toute
récidive : placeholder littéral, littéral numérique non conforme au `repr`
dérivé, ou rampe de teinte dont la valeur flottante a changé.

Trois natures de cas (marquées dans la docstring de chaque test) :

  nominal   — le blob versionné du worktree est l'artefact amont ;
  limite    — un littéral approximatif passe `node --check` mais le banc le
              refuse (M1 = même valeur flottante, littéral non conforme au
              `repr` ; M3 = valeur flottante réellement différente) ;
  erreur    — le blob cassé (placeholder présent) est refusé, fichier et
              raison nommés ;
  garde-fou — anti-tautologie : le banc ne peut pas être vert sur un asset
              corrompu, ne vendore aucune fixture, n'épingle aucun
              interpréteur ambient, ne résout jamais le chemin par la
              constante du renderer.

Le verdict est porté par `invariant()`, **fonction pure** rendant `(ok, motif)`
et n'utilisant que la bibliothèque standard ; pytest n'en est qu'un appelant,
et la fonction reste exécutable en mode CLI sous un interpréteur sans pytest :

    python3 tests/test_asset_mermaid_integrity.py [ASSET]

L'asset est résolu par `git ls-files '*.js'` depuis la racine du worktree —
jamais par la constante du consommateur `mermaid_render.py`, qui pointe hors
dépôt et masquerait le défaut. Les mutants M1/M3 et le témoin cassé sont
**dérivés par référence git** en mémoire (blob `c3922946`, immuable), jamais
versionnés comme fixture : un fichier de 3,5 Mo dans `tests/` violerait
CONTRIBUTING.
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional

try:  # le mode CLI doit tourner sous un interpréteur sans pytest
    import pytest
except ModuleNotFoundError:  # pragma: no cover - exercé en sous-processus
    pytest = None


# --------------------------------------------------------------- références ---

REPO = Path(__file__).resolve().parents[1]

#: nom du fichier attendu par `git ls-files '*.js'` (jamais la constante du renderer)
NOM_ASSET = "mermaid.min.js"
#: chemin relatif canonique de l'asset sur cette branche
CHEMIN_ASSET = Path("bridge") / "mermaid.min.js"

#: identité d'octets de l'artefact amont `mermaid@11.17.2` — l'oracle du banc,
#: déjà mesuré ; aucune dépendance réseau/npm n'est requise pour le rejouer.
SHA_AMONT = "581ed7d74bd9048d0e3a91363927d72ef22942d7722546b27f7cc29e35390eb8"
#: identité d'octets du blob cassé, l'état d'avant correction (blob `c3922946`)
SHA_CASSE = "ba67386c615929a28cd1323fae2f08851dfb677e35e23320da289a6ddb0e39af"
#: blob git immuable du bundle cassé — base de dérivation des mutants
BLOB_CASSE = "c39229467dc756b08e13755850dce6abff41c7d0"
#: ref où le blob cassé est versionné (repli si le blob a été élagué)
REF_CASSE = "origin/dev:bridge/mermaid.min.js"

#: le motif interdit est le placeholder LITTÉRAL injecté par le sanitizer.
#: Une jambe sur la *forme* `${...}` serait un faux positif massif : l'asset
#: amont en porte des milliers (template literals de la lib vendue).
PLACEHOLDER = b"${DISCORD_ID}"
#: offset octet du site substitué (identique dans le blob cassé et dans l'amont)
OFFSET_RAMPE_AMONT = 16137
#: offsets des deux autres sites numériques (constantes IEEE de l'amont)
OFFSETS_MAX_AMONT = (1055489, 2222556)


# ------------------------------------------------------------- dérivations ---
# Les littéraux attendus sont DÉRIVÉS du repr Python, jamais recopiés : le banc
# ne peut pas se tromper de valeur en même temps que l'asset.


def litteral_repr_1_6() -> str:
    """`repr(1/6)` = `0.16666666666666666` -> `16666666666666666`."""
    return repr(1 / 6).split(".")[1]


def litteral_max_float() -> str:
    """`repr(sys.float_info.max)` = `1.7976931348623157e+308` -> `17976931348623157`."""
    return repr(sys.float_info.max).split("e")[0].replace(".", "")


def rampe_snippet_attendu() -> bytes:
    """Le fragment de rampe de teinte, avec le littéral dérivé du `repr`."""
    return b"r<." + litteral_repr_1_6().encode("ascii") + b"?e+(t-e)*6*r"


def valeur_rampe_amont() -> Optional[str]:
    """Valeur flottante (hex) de la rampe amont, dérivée de `repr(1/6)`."""
    return float("0." + litteral_repr_1_6()).hex()


def census_attendu() -> dict:
    """Multiset EXACT attendu des littéraux de 17 à 19 chiffres de l'amont.

    Les clés sont dérivées (`repr(1/6)`, `repr(MAX_FLOAT)`) ; les occurrences
    (1 et 2) sont celles de l'artefact amont, dont le `sha256` ci-dessus est
    l'oracle d'octets. L'égalité doit être un **multiset**, jamais une
    inclusion : la forme « observé ⊆ attendu » accepte le blob cassé.
    """
    return {litteral_repr_1_6(): 1, litteral_max_float(): 2}


# ------------------------------------------------------------------ jambes ---

_MOTIF_LITTERAL = re.compile(rb"(?<![0-9])([0-9]{17,19})(?![0-9])")
_MOTIF_RAMPE = re.compile(rb"r<\.([0-9]+|\$\{[^}]*\})\?e\+\(t-e\)\*6\*r")


def census_litteraux(data: bytes) -> dict:
    """Multiset des littéraux de 17 à 19 chiffres, bornés à gauche et à droite."""
    out: dict = {}
    for m in _MOTIF_LITTERAL.finditer(data):
        cle = m.group(1).decode("ascii")
        out[cle] = out.get(cle, 0) + 1
    return out


def offsets_de(data: bytes, aiguille: bytes, limite: int = 5) -> list:
    """Offsets (jusqu'à `limite`) d'une occurrence, pour nommer le site fautif."""
    out, pos = [], 0
    while len(out) < limite:
        i = data.find(aiguille, pos)
        if i < 0:
            break
        out.append(i)
        pos = i + 1
    return out


def rampe_litteral(data: bytes) -> Optional[str]:
    """Littéral porté par la rampe de teinte, ou None si la structure est absente."""
    m = _MOTIF_RAMPE.search(data)
    return m.group(1).decode("utf-8", "replace") if m else None


def valeur_rampe(litteral: Optional[str]) -> Optional[str]:
    """Valeur flottante (hex) du littéral de rampe, None s'il est illisible."""
    if not litteral or not litteral.isdigit():
        return None
    try:
        return float("0." + litteral).hex()
    except ValueError:  # pragma: no cover - garde-fou de forme
        return None


def motif_census(observe: dict, attendu: dict) -> str:
    """Motif nommant le littéral fautif — et jamais « rampe faussée ».

    Un littéral voisin (`...665`) a la MÊME valeur flottante que la valeur
    saine : il doit donc être refusé comme « non conforme au repr », pas comme
    une rampe faussée. L'assertion de valeur est portée par la jambe rampe.
    """
    parts = []
    for cle, n in sorted(observe.items()):
        if cle not in attendu:
            parts.append(
                "littéral non conforme au repr: %s ×%d (repr(1/6)=%s, repr(MAX_FLOAT)=%s)"
                % (cle, n, litteral_repr_1_6(), litteral_max_float())
            )
        elif n != attendu[cle]:
            parts.append("occurrences de %s: %d ≠ %d attendues" % (cle, n, attendu[cle]))
    for cle, n in sorted(attendu.items()):
        if cle not in observe:
            parts.append("littéral attendu absent: %s ×%d" % (cle, n))
    return "census non conforme [%s] (observé %s)" % (
        "; ".join(parts) or "écart non nommé",
        dict(sorted(observe.items())),
    )


def echecs(data: bytes, sha_attendu: str = SHA_AMONT,
           node_rc: Optional[int] = None) -> list:
    """Liste des jambes en échec — cœur PUR du banc, ni I/O ni horloge ni aléa."""
    out = []

    n_ph = data.count(PLACEHOLDER)
    if n_ph:
        out.append(
            "placeholder ${DISCORD_ID} présent ×%d @offset %s"
            % (n_ph, offsets_de(data, PLACEHOLDER))
        )

    sha = hashlib.sha256(data).hexdigest()
    if sha != sha_attendu:
        out.append("sha256 %s… ≠ attendu %s…" % (sha[:16], sha_attendu[:16]))

    observe = census_litteraux(data)
    if observe != census_attendu():
        out.append(motif_census(observe, census_attendu()))

    litteral = rampe_litteral(data)
    if litteral is None:
        out.append("rampe: structure `r<.<littéral>?e+(t-e)*6*r` absente")
    else:
        valeur = valeur_rampe(litteral)
        if valeur is None:
            out.append(
                "rampe: littéral illisible %r (attendu %s, repr(1/6))"
                % (litteral, litteral_repr_1_6())
            )
        elif valeur != valeur_rampe_amont():
            out.append(
                "rampe: littéral %s → valeur %s ≠ %s (repr(1/6))"
                % (litteral, valeur, valeur_rampe_amont())
            )

    if node_rc is not None and node_rc != 0:
        out.append("node --check rc=%d" % node_rc)

    return out


def invariant(data: bytes, label: str, sha_attendu: str = SHA_AMONT,
              node_rc: Optional[int] = None):
    """Verdict PUR : `(ok, motif)`. `node_rc` est un renfort, jamais le verdict."""
    liste = echecs(data, sha_attendu=sha_attendu, node_rc=node_rc)
    if not liste:
        sha = hashlib.sha256(data).hexdigest()
        return True, "OK — %s est l'artefact amont (sha256 %s…)" % (label, sha[:16])
    return False, "%s REFUSÉ: %s" % (label, " | ".join(liste))


# ------------------------------------------------------------- interpréteurs ---
# Aucun interpréteur n'est épinglé : `PJ_NODE` / `PJ_PYTHON` surchargent, et le
# chemin RÉSOLU (donc réellement exécuté) est nommé dans la sortie.


def resoudre_node(env: Optional[dict] = None) -> Optional[str]:
    env = dict(os.environ) if env is None else env
    force = env.get("PJ_NODE")
    if force:
        return force if Path(force).exists() else None
    return shutil.which("node")


def node_check(chemin: Path, node: Optional[str] = None):
    """`(rc, note)` ; `rc` vaut None si node est absent (skip VISIBLE côté test)."""
    node = node or resoudre_node()
    if not node:
        return None, "node absent"
    r = subprocess.run([node, "--check", str(chemin)], capture_output=True, text=True)
    note = (r.stderr or "").strip().splitlines()
    return r.returncode, (note[0] if note else "")


def node_info(node: Optional[str] = None) -> str:
    node = node or resoudre_node()
    if not node:
        return "ABSENT (renfort indisponible, skip visible)"
    version = subprocess.run([node, "--version"], capture_output=True, text=True).stdout.strip()
    return "%s (%s)" % (Path(node).resolve(), version)


def resoudre_python(env: Optional[dict] = None) -> Optional[str]:
    env = dict(os.environ) if env is None else env
    force = env.get("PJ_PYTHON")
    if force:
        return force if Path(force).exists() else None
    if Path("/usr/bin/python3").exists():
        return "/usr/bin/python3"
    return sys.executable


def python_sans_pytest(env: Optional[dict] = None) -> Optional[str]:
    """Interpréteur capable de porter le verdict SANS pytest (preuve d'indépendance)."""
    py = resoudre_python(env)
    if not py:
        return None
    r = subprocess.run([py, "-c", "import pytest"], capture_output=True)
    return None if r.returncode == 0 else py


def python_info(env: Optional[dict] = None) -> str:
    py = resoudre_python(env)
    if not py:
        return "ABSENT"
    version = subprocess.run(
        [py, "-c", "import sys; print(sys.version.split()[0])"],
        capture_output=True, text=True,
    ).stdout.strip()
    return "%s (%s)" % (Path(py).resolve(), version)


# ------------------------------------------------- résolution & dérivation ---
# Le chemin vient de `git ls-files '*.js'` : la constante du consommateur
# `mermaid_render.py` pointe une copie hors dépôt, saine, qui masquerait le
# défaut (faux vert sur `dev`).


def git_js(repo: Path = REPO) -> list:
    r = subprocess.run(["git", "ls-files", "*.js"], cwd=str(repo),
                       capture_output=True, text=True)
    return [l.strip() for l in r.stdout.splitlines() if l.strip()] if r.returncode == 0 else []


def resoudre_asset(repo: Path = REPO, env: Optional[dict] = None) -> Optional[Path]:
    """Asset du worktree, résolu par `git ls-files '*.js'`.

    `PJ_MERMAID_ASSET` surcharge explicitement le chemin (banc paramétré par
    ref : c'est ce qui permet de rejouer le verdict contre l'état d'avant
    correction) — aucun chemin par défaut n'est épinglé pour autant.
    """
    env = dict(os.environ) if env is None else env
    force = env.get("PJ_MERMAID_ASSET")
    if force:
        chemin = Path(force)
        return chemin.resolve() if chemin.exists() else None
    candidats = [f for f in git_js(repo) if Path(f).name == NOM_ASSET]
    if len(candidats) != 1:
        return None
    return (repo / candidats[0]).resolve()


def blob_par_ref(ref: str, repo: Path = REPO) -> Optional[bytes]:
    for argv in (["cat-file", "blob", ref], ["show", ref]):
        r = subprocess.run(["git"] + argv, cwd=str(repo), capture_output=True)
        if r.returncode == 0 and r.stdout:
            return r.stdout
    return None


def blob_casse(repo: Path = REPO) -> Optional[bytes]:
    """Bytes du blob cassé, dérivés par référence git et vérifiés par son sha256.

    Le blob est immuable, donc la base de dérivation reste stable même après
    restauration sur la branche — c'est ce qui distingue l'état « avant
    correction » de l'asset livré.
    """
    for ref in (BLOB_CASSE, REF_CASSE):
        data = blob_par_ref(ref, repo)
        if data is not None and hashlib.sha256(data).hexdigest() == SHA_CASSE:
            return data
    return None


def derive(broken: bytes, litteral: str) -> bytes:
    """Remplace le SEUL placeholder par le littéral donné (dérivation en mémoire)."""
    return broken.replace(PLACEHOLDER, litteral.encode("ascii"))


def ecrire_tmp(blob: bytes, nom: str):
    """Écrit un blob dérivé HORS du dépôt (context manager de répertoire jetable)."""
    td = tempfile.TemporaryDirectory(prefix="pj-mermaid-")
    chemin = Path(td.name) / nom
    chemin.write_bytes(blob)
    return td, chemin


def rapport(data: bytes, label: str, node_rc: Optional[int] = None):
    """Sortie lisible : nomme l'asset, les jambes mesurées et le verdict.

    Rend `(texte, ok)` — le verdict est celui de la fonction pure `invariant`.
    """
    ok, motif = invariant(data, label, node_rc=node_rc)
    lignes = [
        "asset   : %s (%d o)" % (label, len(data)),
        "python  : %s" % python_info(),
        "node    : %s" % node_info(),
        "sha256  : %s" % hashlib.sha256(data).hexdigest(),
        "census  : %s" % dict(sorted(census_litteraux(data).items())),
        "rampe   : %s" % (rampe_litteral(data),),
        "VERDICT : %s" % motif,
    ]
    return "\n".join(lignes), ok


# --------------------------------------------------------------------- CLI ---

def main(argv: Optional[list] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    chemin = Path(argv[0]).resolve() if argv else resoudre_asset()
    if chemin is None or not chemin.exists():
        print("asset introuvable: %s" % chemin)
        return 2
    rc, _ = node_check(chemin)
    sortie, ok = rapport(chemin.read_bytes(), chemin.name, node_rc=rc)
    print(sortie)
    return 0 if ok else 1


# ============================================================== scénarios ====

# --------------------------------------------------------------- nominal ---

def test_nominal_le_blob_versionne_est_l_artefact_amont():
    """nominal : le blob versionné du worktree EST l'artefact amont — verdict OK."""
    asset = resoudre_asset()
    assert asset is not None, "asset non résolu par `git ls-files '*.js'`"
    data = asset.read_bytes()
    rc, note = node_check(asset)
    ok, motif = invariant(data, asset.name, node_rc=rc)
    assert ok, "%s (node: %s)" % (motif, note)


def test_nominal_sha256_identifie_l_artefact_amont():
    """nominal : l'identité d'octets du blob versionné est celle de l'amont."""
    asset = resoudre_asset()
    broken = blob_casse()
    assert asset is not None and broken is not None
    assert asset.read_bytes() == derive(broken, litteral_repr_1_6()), (
        "le blob versionné n'est pas la re-substitution exacte du blob cassé"
    )
    assert hashlib.sha256(asset.read_bytes()).hexdigest() == SHA_AMONT


def test_nominal_census_multiset_exact_et_offsets_de_l_amont():
    """nominal : census exact (multiset) et offsets du site de rampe/deux MAX."""
    asset = resoudre_asset()
    assert asset is not None
    data = asset.read_bytes()
    assert census_litteraux(data) == census_attendu()
    assert offsets_de(data, litteral_repr_1_6().encode()) == [OFFSET_RAMPE_AMONT]
    assert tuple(offsets_de(data, litteral_max_float().encode())) == OFFSETS_MAX_AMONT


def test_nominal_rampe_est_la_derivee_du_repr():
    """nominal : la rampe porte le littéral DÉRIVÉ du repr, valeur flottante incluse."""
    asset = resoudre_asset()
    assert asset is not None
    data = asset.read_bytes()
    assert rampe_snippet_attendu() in data
    assert rampe_litteral(data) == litteral_repr_1_6()
    assert valeur_rampe(rampe_litteral(data)) == valeur_rampe_amont()


def test_nominal_node_check_rc0_ou_skip_visible():
    """nominal : `node --check` rc=0 — renfort ; absent, skip VISIBLE et le
    verdict reste porté par le census dérivé + le sha256 (Python pur)."""
    asset = resoudre_asset()
    assert asset is not None
    rc, note = node_check(asset)
    if rc is None:
        if pytest is None:  # pragma: no cover - mode CLI
            return
        pytest.skip(
            "node absent (%s) — renfort indisponible, skip VISIBLE ; "
            "le verdict reste porté par le census dérivé + le sha256 (Python pur)"
            % node_info()
        )
    assert rc == 0, "node --check rc=%s sur %s (%s)" % (rc, asset.name, note)


def test_nominal_le_derive_sain_est_accepte_et_le_casse_refuse():
    """nominal : paire discriminante — la même fonction accepte le sain et
    refuse le cassé (le banc n'est pas constant)."""
    broken = blob_casse()
    assert broken is not None, "blob cassé introuvable par référence git"
    ok_sain, motif_sain = invariant(derive(broken, litteral_repr_1_6()), "derive-sain.js")
    ok_casse, motif_casse = invariant(broken, "blob-casse.js")
    assert ok_sain, motif_sain
    assert not ok_casse, "le blob cassé est accepté par le banc"


def test_nominal_le_derive_sain_est_octet_pour_octet_l_amont():
    """nominal : le témoin sain se DÉRIVE (aucune fixture vendorée) et son
    sha256 est celui de l'artefact amont."""
    broken = blob_casse()
    assert broken is not None
    sain = derive(broken, litteral_repr_1_6())
    assert len(sain) == 3572661
    assert hashlib.sha256(sain).hexdigest() == SHA_AMONT


# ---------------------------------------------------------------- limite ---

def test_limite_m1_passe_node_mais_est_refuse_sur_le_repr():
    """limite : M1 (`...665`) parse mais est refusé — motif « non conforme au
    repr », JAMAIS « rampe faussée » (valeur flottante identique)."""
    broken = blob_casse()
    assert broken is not None
    m1 = derive(broken, "16666666666666665")
    assert hashlib.sha256(m1).hexdigest() != SHA_AMONT
    assert len(m1) == len(derive(broken, litteral_repr_1_6())), "même taille attendue"

    ok, motif = invariant(m1, "m1.js")
    assert not ok, "M1 accepté par le banc"
    assert "littéral non conforme au repr" in motif, motif
    assert "rampe" not in motif, "M1 doit être refusé sur le repr, pas sur la rampe: %s" % motif

    td, chemin = ecrire_tmp(m1, "m1.js")
    try:
        rc, note = node_check(chemin)
        if rc is None:
            if pytest is None:  # pragma: no cover - mode CLI
                return
            pytest.skip("node absent (%s) — renfort indisponible" % node_info())
        assert rc == 0, "M1 doit passer node --check (rc=%s, %s)" % (rc, note)
    finally:
        td.cleanup()


def test_limite_m3_valeur_de_rampe_reellement_differente():
    """limite : M3 (littéral à 16 chiffres) parse mais sa valeur de rampe a
    réellement changé — c'est LUI qui porte l'assertion de valeur."""
    broken = blob_casse()
    assert broken is not None
    m3 = derive(broken, "1666666666666666")
    assert valeur_rampe(rampe_litteral(m3)) != valeur_rampe_amont()
    assert valeur_rampe(rampe_litteral(m3)) == float("0.1666666666666666").hex()

    ok, motif = invariant(m3, "m3.js")
    assert not ok, "M3 accepté par le banc"
    assert "rampe" in motif and "≠" in motif, motif

    td, chemin = ecrire_tmp(m3, "m3.js")
    try:
        rc, note = node_check(chemin)
        if rc is None:
            if pytest is None:  # pragma: no cover - mode CLI
                return
            pytest.skip("node absent (%s) — renfort indisponible" % node_info())
        assert rc == 0, "M3 doit passer node --check (rc=%s, %s)" % (rc, note)
    finally:
        td.cleanup()


def test_limite_m1_et_m3_ne_sont_pas_interchangeables():
    """limite : M1 garde la valeur saine, M3 ne la garde pas — les deux mutants
    couvrent deux assertions distinctes (conformité au repr / valeur)."""
    broken = blob_casse()
    assert broken is not None
    m1, m3 = derive(broken, "16666666666666665"), derive(broken, "1666666666666666")
    assert valeur_rampe(rampe_litteral(m1)) == valeur_rampe_amont()
    assert valeur_rampe(rampe_litteral(m3)) != valeur_rampe_amont()
    # le littéral voisin est NUMÉRIQUEMENT équivalent : seul le repr le sépare
    assert float("0.16666666666666665") == float("0." + litteral_repr_1_6())


# ----------------------------------------------------------------- erreur ---

def test_erreur_le_blob_casse_est_refuse_en_nommant_fichier_et_raison():
    """erreur : le blob cassé (placeholder @16137) est refusé, fichier + raison
    nommés — sha256 différent ET placeholder présent."""
    broken = blob_casse()
    assert broken is not None
    assert data_placeholder_offset(broken) == OFFSET_RAMPE_AMONT

    ok, motif = invariant(broken, "blob-casse.js")
    assert not ok
    assert "blob-casse.js" in motif
    assert "${DISCORD_ID}" in motif and "@offset [16137]" in motif, motif
    assert SHA_AMONT[:16] in motif and SHA_CASSE[:16] in motif, motif
    assert "census non conforme" in motif, motif


def test_erreur_le_cli_nomme_le_defaut_et_sort_en_rc1():
    """erreur : le banc lui-même (mode CLI) ÉCHOUE sur le blob cassé, rc=1,
    en nommant le fichier et la raison."""
    broken = blob_casse()
    assert broken is not None
    td, chemin = ecrire_tmp(broken, "blob-casse.js")
    try:
        r = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), str(chemin)],
            capture_output=True, text=True,
        )
        assert r.returncode == 1, r.stdout + r.stderr
        assert "VERDICT" in r.stdout and "REFUSÉ" in r.stdout, r.stdout
        assert "${DISCORD_ID}" in r.stdout, r.stdout
    finally:
        td.cleanup()


def data_placeholder_offset(data: bytes) -> int:
    """Offset du placeholder, ou -1 — helper de lisibilité des assertions."""
    return data.find(PLACEHOLDER)


# -------------------------------------------------------------- garde-fous ---

def test_garde_fou_le_census_doit_etre_exact_pas_une_inclusion():
    """garde-fou : la forme « observé ⊆ attendu » ACCEPTE le blob cassé — la
    précision du multiset est donc nécessaire, le banc n'est pas tautologique."""
    broken = blob_casse()
    assert broken is not None
    observe, attendu = census_litteraux(broken), census_attendu()

    def inclusion(obs: dict, att: dict) -> bool:
        return all(cle in att and n <= att[cle] for cle, n in obs.items())

    assert inclusion(observe, attendu), "l'inclusion doit passer sur le blob cassé"
    assert observe != attendu, "l'égalité de multiset doit échouer sur le blob cassé"
    ok, _ = invariant(broken, "blob-casse.js")
    assert not ok


def test_limite_le_census_est_un_multiset_et_refuse_une_occurrence_en_trop():
    """limite : une OCCURRENCE EN TROP de la valeur saine est refusée.

    Un census lu comme « chaque littéral attendu est présent » accepterait un
    asset qui porte `16666666666666666` deux fois : les clés seraient les
    mêmes, seul le compte diffère. C'est le volet « multiset » de la revendication
    — il est exercé ici dans les deux sens (clé absente ET compte excédentaire).
    """
    broken = blob_casse()
    assert broken is not None
    sain = derive(broken, litteral_repr_1_6())

    doubler = sain.replace(
        b"r<." + litteral_repr_1_6().encode() + b"?",
        b"r<." + litteral_repr_1_6().encode() + b"?0,e+(t-e)*6*0:r<."
        + litteral_repr_1_6().encode() + b"?",
        1,
    )
    assert doubler != sain
    assert census_litteraux(doubler) == {litteral_repr_1_6(): 2, litteral_max_float(): 2}

    ok, motif = invariant(doubler, "occurrence-en-trop.js")
    assert not ok, "une occurrence excédentaire est acceptée par le banc"
    assert "occurrences de %s: 2 ≠ 1" % litteral_repr_1_6() in motif, motif

    # le pendant : clé attendue ABSENTE (volet déjà couvert par le bloc cassé)
    manquant = sain.replace(litteral_repr_1_6().encode(), b"", 1)
    ok_manquant, motif_manquant = invariant(manquant, "cle-absente.js")
    assert not ok_manquant and "littéral attendu absent" in motif_manquant, motif_manquant


def test_garde_fou_node_absent_ne_rend_jamais_vert_un_asset_casse():
    """garde-fou : sans node (renfort indisponible), le cassé reste ROUGE et le
    sain reste VERT — le verdict ne dépend pas de l'outil externe."""
    broken = blob_casse()
    assert broken is not None
    ok_casse, _ = invariant(broken, "blob-casse.js", node_rc=None)
    ok_sain, _ = invariant(derive(broken, litteral_repr_1_6()), "derive-sain.js", node_rc=None)
    assert not ok_casse
    assert ok_sain


def test_garde_fou_le_chemin_ne_vient_jamais_de_la_constante_du_renderer():
    """garde-fou : l'asset est résolu par `git ls-files '*.js'` dans le
    worktree ; la constante du consommateur pointe HORS dépôt (faux vert).

    Mesuré sans surcharge (`env={}`) : la surcharge `PJ_MERMAID_ASSET` est un
    paramètre explicite du banc, jamais un chemin par défaut.
    """
    candidats = [f for f in git_js() if Path(f).name == NOM_ASSET]
    assert candidats == [str(CHEMIN_ASSET)], candidats
    asset = resoudre_asset(env={})
    assert asset is not None and REPO in asset.parents
    assert asset == (REPO / CHEMIN_ASSET).resolve()

    renderer = REPO / "skills" / "gh-kanban-bridge" / "scripts" / "mermaid_render.py"
    trace = "hermes" + "-experiment"
    assert trace in renderer.read_text(), "la trace hors dépôt du renderer a disparu"
    assert trace not in Path(__file__).read_text(), "le banc ne doit pas s'y référer"


def test_garde_fou_aucun_epinlage_d_interpreteur():
    """garde-fou : aucun interpréteur épinglé ; PJ_NODE / PJ_PYTHON surchargent,
    et un chemin forcé inexistant rend l'interpréteur ABSENT (skip visible).

    Le verdict ne dépend donc pas de l'ambient du lanceur : une surcharge
    cassée produit un skip visible, jamais un rouge imputé à l'asset.
    """
    source = Path(__file__).read_text()
    # aiguille reconstruite : une aiguille littérale se trouverait elle-même
    epingle = "/.local" + "/bin/node"
    assert epingle not in source
    assert "PJ_NODE" in source and "PJ_PYTHON" in source
    assert resoudre_node({"PJ_NODE": "/inexistant/node"}) is None
    assert resoudre_python({"PJ_PYTHON": "/inexistant/python"}) is None
    # et l'invariant reste concluant SANS renfort : le sain passe, le cassé non
    broken = blob_casse()
    assert broken is not None
    ok_sain, _ = invariant(derive(broken, litteral_repr_1_6()), "sain.js", node_rc=None)
    ok_casse, _ = invariant(broken, "casse.js", node_rc=None)
    assert ok_sain and not ok_casse


def test_garde_fou_le_verdict_ne_depend_pas_de_l_interpreteur_ambient():
    """garde-fou : la fonction pure rend le même verdict sous un interpréteur
    SANS pytest (le banc nomme l'interpréteur résolu et sa version)."""
    py = python_sans_pytest()
    if py is None:
        if pytest is None:  # pragma: no cover - mode CLI
            return
        pytest.skip("aucun interpréteur sans pytest — indépendance non mesurable ici")

    broken = blob_casse()
    assert broken is not None
    for blob, attendu_ok in ((broken, False), (derive(broken, litteral_repr_1_6()), True)):
        td, chemin = ecrire_tmp(blob, "asset.js")
        try:
            r = subprocess.run([py, str(Path(__file__).resolve()), str(chemin)],
                               capture_output=True, text=True)
            assert "VERDICT" in r.stdout, r.stdout + r.stderr
            assert r.stdout.count("python  : %s" % Path(py).resolve()) == 1, r.stdout
            assert (r.returncode == 0) is attendu_ok, r.stdout
        finally:
            td.cleanup()


def test_garde_fou_le_banc_ne_vendore_aucune_fixture():
    """garde-fou : aucune fixture de 3,5 Mo dans tests/ — les mutants et le
    témoin cassé sont dérivés par référence git, en mémoire."""
    for p in (REPO / "tests").rglob("*"):
        if p.is_file() and "__pycache__" not in p.parts:
            assert p.stat().st_size < 200_000, "%s est une fixture trop lourde" % p
            assert not p.name.endswith(NOM_ASSET), "%s vendore l'asset" % p


def test_garde_fou_le_verdict_nomme_l_asset():
    """garde-fou : le motif est exploitable — il nomme toujours le fichier."""
    broken = blob_casse()
    assert broken is not None
    _, motif = invariant(broken, "bridge/mermaid.min.js")
    assert motif.startswith("bridge/mermaid.min.js REFUSÉ: "), motif


if __name__ == "__main__":
    raise SystemExit(main())
