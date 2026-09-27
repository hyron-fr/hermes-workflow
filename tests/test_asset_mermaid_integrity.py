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

**Mode par défaut du verdict : le blob VERSIONNÉ.** Les octets analysés
(sha256, census multiset, offsets, rampe) sont ceux que le dépôt PUBLIE, lus
par `git cat-file blob HEAD:bridge/mermaid.min.js` ; le libellé du verdict
nomme le chemin, l'oid du blob et le commit lus. Le fichier du worktree n'est
qu'une **seconde jambe, plus faible** (`git diff --quiet HEAD -- <chemin>`) :
un correctif présent seulement dans le worktree, ou un commit qui recasse
l'asset, ne peut donc pas blanchir le banc. `PJ_MERMAID_ASSET` reste une
surcharge **explicite** (jambe paramétrée, légitime pour rejouer le RED) :
elle s'ajoute au verdict, elle ne le remplace jamais.

L'asset est résolu par `git ls-files '*.js'` depuis la racine du worktree —
jamais par la constante du consommateur `mermaid_render.py`, qui pointe hors
dépôt et masquerait le défaut. Les mutants M1/M3, le témoin cassé et le
montage « HEAD cassé + worktree sain non committé » sont **dérivés par
référence git** en mémoire (blob `c3922946`, immuable) et matérialisés HORS
dépôt (`tempfile`), jamais versionnés comme fixture : un fichier de 3,5 Mo
dans `tests/` violerait CONTRIBUTING.

**Anti-récursion.** Un cas de montage ne peut pas relancer `pytest` sur la
copie du banc : cette copie contient les cas de montage eux-mêmes, la relance
se rejouerait donc SANS BORNE. Mesure faite avant correctif : 9 processus
`pytest` à t+8 s, 14 à t+16 s, sortie `EXIT=137` (SIGKILL) — c'est la cause
des OOM des runs précédents. Les montages passent donc par le **MODE CLI**
(`python3 <copie>` — le point d'entrée dont l'AC exige le `rc`), et le
sous-processus reçoit `PJ_BANC_INTERNE=1`, qui rend tout montage résiduel
`skip` VISIBLE : la récursion est structurellement impossible, même si une
relance `pytest` était réintroduite dans le lanceur.

**Portée de la preuve.** Le montage « HEAD cassé + fichier de travail sain non
committé » est reconstitué par **dépôt git jetable** (`git init` + alternat
d'objets), et son blob cassé est produit par **commit** : il porte donc un
`HEAD` réel que `git hash-object`/`git cat-file` désignent. C'est la classe de
défaut mesurée par conv-1 : un fichier sain non committé masquait un blob
versionné cassé. Le banc ne prétend pas rejouer littéralement un
`git clone --shared`, geste que je n'ai pas reproduit ici ; il prouve que le
verdict ne se laisse plus blanchir par l'état du seul fichier de travail.
"""

from __future__ import annotations

import atexit
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
#: ref dont les octets font le verdict — `HEAD`, jamais l'index ni le worktree :
#: c'est ce que le dépôt PUBLIE (un `git clone` d'une autre machine le lit).
#: Le commit réellement lu est nommé dans chaque verdict (non ambiguïté en cas
#: de re-spawn du banc sur un autre tip).
REF_VERDICT = "HEAD"
#: ref de repli pour monter un dépôt d'essai quand `dev` n'est pas local
REF_PARENT = "dev"

#: identité d'octets de l'artefact amont `mermaid@11.17.2` — l'oracle du banc,
#: déjà mesuré ; aucune dépendance réseau/npm n'est requise pour le rejouer.
SHA_AMONT = "581ed7d74bd9048d0e3a91363927d72ef22942d7722546b27f7cc29e35390eb8"
#: identité d'octets du blob cassé, l'état d'avant correction (blob `c3922946`)
SHA_CASSE = "ba67386c615929a28cd1323fae2f08851dfb677e35e23320da289a6ddb0e39af"
#: blob git immuable du bundle cassé — base de dérivation des mutants
BLOB_CASSE = "c39229467dc756b08e13755850dce6abff41c7d0"
#: OID du blob SAIN tel que versionné au tip de la branche (objet `bridge/mermaid.min.js`
#: dans l'arbre de HEAD) — nommé dans le verdict, il rend le banc non ambigu.
OID_AMONT = "79b89d7cb19a8e89a1fffa1d10c2e5987afd5481"
#: ref où le blob cassé est versionné (repli si le blob a été élagué)
REF_CASSE = "origin/dev:bridge/mermaid.min.js"

#: Marqueur de RELANCE INTERNE : positionné par `lancer_le_banc()` dans le
#: environnement du sous-processus, il rend les cas de montage `skip` VISIBLE.
#: Il ferme la récursion par construction : une copie du banc relancée en
#: pytest ne peut plus remonter sa propre chaîne de sous-processus (mesuré
#: avant correctif : 9 pytest à t+8 s, 14 à t+16 s, EXIT=137).
MARQUEUR_INTERNE = "PJ_BANC_INTERNE"

#: Marqueur de la jambe PARAMÉTRÉE de surcharge, toujours nommée dans le motif :
#: une jambe active ne peut pas être silencieuse (la surcharge s'ajoute au
#: verdict du blob versionné, elle ne le remplace jamais).
MARQUEUR_SURCHARGE = "SURCHARGE"

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


def git_js(repo: Path = REPO, ref: Optional[str] = None) -> list:
    """Fichiers `*.js` du dépôt — index par défaut, arbre de `ref` si fourni."""
    argv = ["git", "ls-files", "*.js"] if ref is None else ["git", "ls-tree", "-r",
                                                           "--name-only", ref]
    r = subprocess.run(argv, cwd=str(repo), capture_output=True, text=True)
    if r.returncode != 0:
        return []
    lignes = [l.strip() for l in r.stdout.splitlines() if l.strip()]
    if ref is not None:
        lignes = [l for l in lignes if l.endswith(".js")]
    return lignes


def resoudre_asset(repo: Path = REPO, env: Optional[dict] = None) -> Optional[Path]:
    """Chemin de l'asset du WORKTREE, résolu par `git ls-files '*.js'`.

    Jambe faible : sert uniquement à établir que le fichier de travail est
    aligné sur le blob versionné (`git diff --quiet`). Le verdict des octets,
    lui, ne passe jamais par ce chemin — il lit `git cat-file blob HEAD:…`.
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


def chemin_versionne(repo: Path = REPO) -> Optional[str]:
    """Chemin de l'asset dans l'ARBRE de `HEAD` — source du verdict.

    Résolu depuis l'arbre, jamais depuis `git ls-files` : ce chemin nomme le
    blob publié, pas le fichier de travail d'un correctif non committé.
    """
    candidats = [f for f in git_js(repo, ref=REF_VERDICT) if Path(f).name == NOM_ASSET]
    return candidats[0] if len(candidats) == 1 else None


def ref_oid(ref: str, repo: Path = REPO) -> Optional[str]:
    """OID du commit/objet désigné par `ref`, ou None."""
    r = subprocess.run(["git", "rev-parse", "--verify", "--quiet", ref],
                       cwd=str(repo), capture_output=True, text=True)
    return r.stdout.strip() or None


def oid_blob(chemin: str, repo: Path = REPO, ref: Optional[str] = None) -> Optional[str]:
    """OID du blob porté par `chemin` dans `ref` (HEAD par défaut)."""
    ref = REF_VERDICT if ref is None else ref
    r = subprocess.run(["git", "rev-parse", "--verify", "--quiet", "%s:%s" % (ref, chemin)],
                       cwd=str(repo), capture_output=True, text=True)
    return r.stdout.strip() or None


def blob_versionne(chemin: Optional[str] = None, repo: Path = REPO,
                   ref: Optional[str] = None) -> Optional[bytes]:
    """Octets du blob VERSIONNÉ — le mode par défaut du verdict.

    `git cat-file blob <ref>:<chemin>` (repli `git show`). Renvoie None si le
    chemin n'existe pas dans l'arbre : le banc refuse alors, il ne retombe
    JAMAIS sur le fichier du worktree.
    """
    ref = REF_VERDICT if ref is None else ref
    chemin = chemin or chemin_versionne(repo)
    if chemin is None:
        return None
    data = blob_par_ref("%s:%s" % (ref, chemin), repo)
    if data is None:
        data = blob_par_ref(oid_blob(chemin, repo, ref) or "", repo)
    return data


def libelle_versionne(chemin: Optional[str] = None, repo: Path = REPO,
                      ref: Optional[str] = None) -> str:
    """Libellé du verdict : chemin + oid du blob + commit LUS (non ambigu)."""
    ref = REF_VERDICT if ref is None else ref
    chemin = chemin or chemin_versionne(repo)
    commit = (ref_oid(ref, repo) or "?")[:12]
    oid = oid_blob(chemin, repo, ref) if chemin else None
    return "blob %s:%s (%s, commit %s)" % (
        ref, chemin or "?", (oid or "?")[:12], commit,
    )


def worktree_aligne_sur_blob(chemin, repo: Path = REPO, ref: Optional[str] = None):
    """Jambe faible : `git diff --quiet <ref> -- <chemin>` -> `(aligne, motif)`.

    Un correctif présent seulement dans le worktree (ou un commit qui recasse
    l'asset) rompt cette jambe : elle ne peut donc pas blanchir le banc.
    """
    ref = REF_VERDICT if ref is None else ref
    chemin = Path(chemin)
    rel = str(chemin.relative_to(repo)) if chemin.is_absolute() else str(chemin)
    r = subprocess.run(["git", "diff", "--quiet", ref, "--", rel],
                       cwd=str(repo), capture_output=True)
    if r.returncode == 0:
        return True, "fichier du worktree == blob %s:%s" % (ref, rel)
    return False, ("fichier du worktree ≠ blob %s:%s (correctif non committé, "
                   "ou asset recassé dans le commit lu)" % (ref, rel))


def verdict(repo: Path = REPO, env: Optional[dict] = None, node_rc: Optional[int] = None):
    """Verdict NON pur : octets du blob VERSIONNÉ + jambe worktree, sans I/O hors dépôt.

    Rend `(ok, motif, data)` ; `data` est None si le blob versionné est
    introuvable (refus, jamais de repli sur le fichier de travail).
    """
    chemin = chemin_versionne(repo)
    libelle = libelle_versionne(chemin, repo)
    data = blob_versionne(chemin, repo)
    if data is None:
        return False, "%s REFUSÉ: asset absent de l'arbre versionné (%s)" % (
            libelle, REF_VERDICT), None
    ok, motif = invariant(data, libelle, node_rc=node_rc)
    if ok:
        chemin_wt = resoudre_asset(repo, {})
        if chemin_wt is None:
            return False, "%s REFUSÉ: chemin du worktree non résolu par " \
                          "`git ls-files '*.js'`" % libelle, data
        aligne, motif_wt = worktree_aligne_sur_blob(chemin_wt, repo)
        if not aligne:
            return False, "%s REFUSÉ: %s" % (libelle, motif_wt), data
        ok, motif = True, "%s — %s" % (motif, motif_wt)
    if env is not None and env.get("PJ_MERMAID_ASSET"):
        # jambe PARAMÉTRÉE : la surcharge s'AJOUTE au verdict, elle ne le
        # remplace jamais (sinon un asset non versionné blanchirait le dépôt).
        # Elle est TOUJOURS nommée dans le motif — une jambe active ne peut
        # pas être silencieuse.
        force = env.get("PJ_MERMAID_ASSET")
        chemin_force = resoudre_asset(repo, env)
        if chemin_force is None or not chemin_force.exists():
            return False, "%s REFUSÉ: %s introuvable (%s)" % (
                libelle, MARQUEUR_SURCHARGE, force), data
        # hériter du rc du blob versionné ferait refuser une surcharge saine dès
        # que le blob versionné est cassé (et inversement), ce qui confondrait
        # les deux jambes.
        rc_force = node_check(chemin_force)[0] if node_rc is not None else None
        okf, motif_force = invariant(chemin_force.read_bytes(),
                                     "surcharge %s" % chemin_force, node_rc=rc_force)
        if not okf:
            return False, "%s REFUSÉ: %s" % (libelle, motif_force), data
        motif = "%s ; %s: %s" % (motif, MARQUEUR_SURCHARGE, motif_force)
    return ok, motif, data


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


def ecrire_tmp_durable(blob: bytes, nom: str):
    """Écrit un blob HORS du dépôt et le nettoie à la sortie du processus.

    Sert aux jambes qui doivent matérialiser des octets versionnés pour un
    outil externe (`node --check`) sans passer par le fichier du worktree.
    """
    td = tempfile.mkdtemp(prefix="pj-mermaid-verdict-")
    chemin = Path(td) / nom
    chemin.write_bytes(blob)
    atexit.register(shutil.rmtree, td, True)
    return chemin


def _chemin_tmp(data: bytes, nom: str = "asset.js") -> Path:
    """Alias interne : matérialise le blob versionné hors dépôt pour `node`."""
    return ecrire_tmp_durable(data, nom)


# ------------------------------------------------------- montages jetables ---
# Le montage « HEAD cassé + fichier de travail sain mais non committé » se
# reconstitue dans un dépôt JETABLE hors du dépôt de travail : jamais dans
# `tests/`, jamais dans le worktree partagé.


def git_dispo() -> bool:
    return shutil.which("git") is not None


def objets_dir(repo: Path) -> Optional[Path]:
    """Répertoire d'objets EFFECTIF du dépôt (résout les worktrees liés)."""
    r = subprocess.run(["git", "rev-parse", "--path-format=absolute",
                        "--git-path", "objects"],
                       cwd=str(repo), capture_output=True, text=True)
    return Path(r.stdout.strip()) if r.returncode == 0 and r.stdout.strip() else None


def creer_depot_jetable(racine, avec_dev: bool = True, parent: Optional[str] = None):
    """Dépôt git jetable hors dépôt, portant un `bridge/mermaid.min.js` à 2 lignes.

    `parent` (chemin de worktree réel) permet de dériver le témoin cassé par
    référence git : le blob `c3922946` est alors lu depuis l'objet partagé d'un
    alternat, sans réseau ni copie de 3,5 Mo.
    """
    racine = Path(racine)
    depot = racine / "depot"
    depot.mkdir(parents=True, exist_ok=True)

    def git(*a, **kw):
        return subprocess.run(
            ["git", "-c", "user.name=pj-test", "-c", "user.email=pj-test@local"] + list(a),
            cwd=str(depot), capture_output=True, text=True, **kw,
        )

    git("init", "-q", "-b", "dev")
    if parent is not None:
        alternat = objets_dir(Path(parent))
        if alternat is not None and alternat.exists():
            (depot / ".git" / "objects" / "info").mkdir(parents=True, exist_ok=True)
            (depot / ".git" / "objects" / "info" / "alternates").write_text(
                str(alternat) + "\n"
            )
    (depot / "bridge").mkdir(parents=True, exist_ok=True)

    casse = blob_casse(Path(parent) if parent is not None else REPO)
    if casse is not None:
        (depot / "bridge" / NOM_ASSET).write_bytes(casse)
        git("add", "-A")
        git("commit", "-qm", "asset casse (blob %s)" % BLOB_CASSE[:8])
        if avec_dev:
            git("branch", "-M", "dev")
    else:  # pragma: no cover - repli si le blob cassé est introuvable
        (depot / "bridge" / NOM_ASSET).write_bytes(b"placeholder ${DISCORD_ID} nope\n")
        git("add", "-A")
        git("commit", "-qm", "asset casse synthetique")
    return depot


def remplacer_hors_commit(depot: Path, blob: bytes) -> None:
    """Écrase le fichier de travail du dépôt jetable SANS committer."""
    (Path(depot) / CHEMIN_ASSET).write_bytes(blob)


def copie_du_banc(depot: Path) -> Path:
    """Copie le banc dans <depot>/tests/ — hors du dépôt de travail."""
    dossier = Path(depot) / "tests"
    dossier.mkdir(parents=True, exist_ok=True)
    cible = dossier / Path(__file__).name
    shutil.copyfile(str(Path(__file__).resolve()), str(cible))
    return cible


def interpreter_python_du_worktree() -> Optional[str]:
    """Interpréteur qui SAIT importer pytest (les jambes jumelles l'exigent)."""
    for cand in (sys.executable, resoudre_python(), shutil.which("python3")):
        if not cand or not Path(cand).exists():
            continue
        r = subprocess.run([cand, "-c", "import pytest"], capture_output=True)
        if r.returncode == 0:
            return cand
    return None


def rapport(data: bytes, label: str, node_rc: Optional[int] = None,
            extra: str = "", verdict_final=None):
    """Sortie lisible : nomme le blob versionné, les jambes mesurées, le verdict.

    Rend `(texte, ok)`. Sans `verdict_final`, le verdict est celui de la
    fonction pure `invariant` ; avec, c'est celui — plus complet — rendu par
    `verdict()`, afin qu'il n'existe qu'UN SEUL chemin de verdict (le CLI ne
    peut pas diverger du banc).
    """
    ok, motif = (invariant(data, label, node_rc=node_rc) if verdict_final is None
                 else verdict_final)
    lignes = [
        "asset   : %s (%d o)" % (label, len(data)),
        "commit  : %s" % (ref_oid(REF_VERDICT) or "?"),
        "python  : %s" % python_info(),
        "node    : %s" % node_info(),
        "sha256  : %s" % hashlib.sha256(data).hexdigest(),
        "census  : %s" % dict(sorted(census_litteraux(data).items())),
        "rampe   : %s" % (rampe_litteral(data),),
        "VERDICT : %s" % motif,
    ]
    if extra:
        lignes.insert(4, "worktree: %s" % extra)
    return "\n".join(lignes), ok


# --------------------------------------------------------------------- CLI ---

def main(argv: Optional[list] = None) -> int:
    """Verdict CLI : par défaut sur le blob VERSIONNÉ ; argument = surcharge.

    Sans argument, le verdict lit `git cat-file blob HEAD:<chemin>`. Un chemin
    passé en argument (ou `PJ_MERMAID_ASSET`) est une jambe PARAMÉTRÉE qui
    s'ajoute au verdict du blob versionné — elle ne le remplace jamais.

    Le CLI appelle `verdict()`, donc le CLI et le banc ne peuvent pas diverger :
    un seul chemin de verdict.
    """
    argv = list(sys.argv[1:] if argv is None else argv)
    env = dict(os.environ)
    if argv:
        env["PJ_MERMAID_ASSET"] = argv[0]
    chemin = chemin_versionne()
    libelle = libelle_versionne(chemin)
    data = blob_versionne(chemin)
    if data is None:
        print("%s REFUSÉ: asset absent de l'arbre versionné (%s)" % (libelle, REF_VERDICT))
        return 1
    rc = node_check(_chemin_tmp(data), node=None)[0]
    ok, motif, _ = verdict(env=env, node_rc=rc)
    extra = ""
    chemin_wt = resoudre_asset(env={})
    if chemin_wt is not None:
        extra = worktree_aligne_sur_blob(chemin_wt)[1]
    sortie, _ = rapport(data, libelle, node_rc=rc, extra=extra,
                        verdict_final=(ok, motif))
    print(sortie)
    return 0 if ok else 1


# ============================================================== scénarios ====

# --------------------------------------------------------------- nominal ---


def test_nominal_le_blob_versionne_est_l_artefact_amont():
    """nominal : le blob VERSIONNÉ de HEAD EST l'artefact amont — verdict OK.

    Le verdict ne porte pas sur le fichier du worktree : il lit
    `git cat-file blob HEAD:<chemin>` et nomme le blob + le commit lus.
    """
    data = blob_versionne()
    assert data is not None, "blob versionné introuvable dans %s" % REF_VERDICT
    libelle = libelle_versionne()
    chemin = _chemin_tmp(data)
    rc, note = node_check(chemin)
    ok, motif = invariant(data, libelle, node_rc=rc)
    assert ok, "%s (node: %s)" % (motif, note)
    assert oid_blob(chemin_versionne()) == OID_AMONT, oid_blob(chemin_versionne())
    assert (ref_oid(REF_VERDICT) or "")[:12] in libelle, libelle


def test_nominal_le_verdict_nomme_le_blob_versionne_et_le_commit():
    """nominal : le libellé du verdict porte le chemin, l'oid du blob et le
    commit LUS — le banc reste non ambigu si la branche est rejouée sur un
    autre tip."""
    chemin = chemin_versionne()
    assert chemin == str(CHEMIN_ASSET), chemin
    oid = oid_blob(chemin)
    assert oid == OID_AMONT, oid
    libelle = libelle_versionne(chemin)
    assert "blob %s:%s" % (REF_VERDICT, chemin) in libelle, libelle
    assert oid[:12] in libelle, libelle
    assert (ref_oid(REF_VERDICT) or "")[:12] in libelle, libelle

    ok, motif, data = verdict()
    assert ok, motif
    assert data is not None and hashlib.sha256(data).hexdigest() == SHA_AMONT


def test_nominal_sha256_identifie_l_artefact_amont():
    """nominal : l'identité d'octets du blob VERSIONNÉ est celle de l'amont."""
    data = blob_versionne()
    broken = blob_casse()
    assert data is not None and broken is not None
    assert data == derive(broken, litteral_repr_1_6()), (
        "le blob versionné n'est pas la re-substitution exacte du blob cassé"
    )
    assert hashlib.sha256(data).hexdigest() == SHA_AMONT


def test_nominal_census_multiset_exact_et_offsets_de_l_amont():
    """nominal : census exact (multiset) et offsets du site de rampe/deux MAX,
    mesurés sur le blob VERSIONNÉ."""
    data = blob_versionne()
    assert data is not None
    assert census_litteraux(data) == census_attendu()
    assert offsets_de(data, litteral_repr_1_6().encode()) == [OFFSET_RAMPE_AMONT]
    assert tuple(offsets_de(data, litteral_max_float().encode())) == OFFSETS_MAX_AMONT


def test_nominal_rampe_est_la_derivee_du_repr():
    """nominal : la rampe du blob VERSIONNÉ porte le littéral DÉRIVÉ du repr,
    valeur flottante incluse."""
    data = blob_versionne()
    assert data is not None
    assert rampe_snippet_attendu() in data
    assert rampe_litteral(data) == litteral_repr_1_6()
    assert valeur_rampe(rampe_litteral(data)) == valeur_rampe_amont()


def test_nominal_node_check_rc0_ou_skip_visible():
    """nominal : `node --check` rc=0 sur les octets du blob VERSIONNÉ —
    renfort ; absent, skip VISIBLE et le verdict reste porté par le census
    dérivé + le sha256 (Python pur)."""
    data = blob_versionne()
    assert data is not None
    chemin = _chemin_tmp(data)
    rc, note = node_check(chemin)
    if rc is None:
        if pytest is None:  # pragma: no cover - mode CLI
            return
        pytest.skip(
            "node absent (%s) — renfort indisponible, skip VISIBLE ; "
            "le verdict reste porté par le census dérivé + le sha256 (Python pur)"
            % node_info()
        )
    assert rc == 0, "node --check rc=%s sur le blob versionné (%s)" % (rc, note)


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


def test_nominal_le_worktree_est_aligne_sur_le_blob_versionne():
    """nominal : le fichier du worktree est EXACTEMENT le blob versionné
    (`git diff --quiet HEAD -- <chemin>`) — seconde jambe, plus faible."""
    chemin_wt = resoudre_asset(env={})
    assert chemin_wt is not None and chemin_wt.exists()
    aligne, motif = worktree_aligne_sur_blob(chemin_wt)
    assert aligne, motif
    assert chemin_wt.read_bytes() == blob_versionne()


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
# (les cas d'erreur sur le blob VERSIONNÉ sont plus bas, avec les montages
#  jetables : ils ne dépendent ni du fichier du worktree ni d'une surcharge)

def data_placeholder_offset(data: bytes) -> int:
    """Offset du placeholder, ou -1 — helper de lisibilité des assertions."""
    return data.find(PLACEHOLDER)


def lancer_le_banc(depot: Path, env: Optional[dict] = None, py: Optional[str] = None):
    """Exécute la copie du banc dans <depot> en MODE CLI et rend `(rc, sortie)`.

    Anti-récursion : la copie est lancée par son **point d'entrée CLI**
    (`python3 <copie>`, celui dont l'AC exige le `rc`), JAMAIS par `pytest`.
    Une relance `pytest` sur la copie rejouerait les cas de montage — donc
    elle-même — sans borne (mesuré : 9 processus à t+8 s, 14 à t+16 s,
    EXIT=137). Le sous-processus reçoit en outre `PJ_BANC_INTERNE=1`, qui
    rend tout montage résiduel `skip` VISIBLE.

    `PJ_MERMAID_ASSET` est retiré : un montage ne peut pas hériter de la
    surcharge du lanceur, la surcharge est un paramètre EXPLICITE.
    """
    py = py or interpreter_python_du_worktree()
    assert py is not None, "aucun interpréteur capable d'importer pytest"
    banc = Path(depot) / "tests" / Path(__file__).name
    assert banc.exists(), "copie du banc absente de %s" % depot
    environ = dict(os.environ)
    environ.pop("PJ_MERMAID_ASSET", None)
    environ.pop("PYTEST_ADDOPTS", None)
    environ.pop("PYTEST_CURRENT_TEST", None)
    environ[MARQUEUR_INTERNE] = "1"
    if env:
        environ.update(env)
    r = subprocess.run(
        [py, str(banc)], cwd=str(depot), capture_output=True, text=True, env=environ,
    )
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def _skip_si_git_absent():
    if pytest is None:  # pragma: no cover - mode CLI sans pytest
        return True
    if os.environ.get(MARQUEUR_INTERNE):
        # relance interne (une copie du banc exécutée par un cas de montage) :
        # le montage NE se rejoue PAS ici — sinon récursion sans borne.
        pytest.skip(
            "relance interne (%s=1) — montage non rejoué, récursion fermée"
            % MARQUEUR_INTERNE
        )
    if not git_dispo():  # pragma: no cover - environnement sans git
        pytest.skip("git absent — montage de dépôt jetable non mesurable")
    return False


def test_limite_un_fichier_sain_non_committe_ne_blanchit_pas_le_depot():
    """limite : montage « HEAD cassé + fichier de travail sain NON COMMITTÉ »

    Dans un dépôt jetable HORS du dépôt de travail, le montage de l'expérience
    de conv-1 est reconstitué par référence git : le banc y ÉCHOUE (rc≠0) en
    nommant le blob VERSIONNÉ fautif — il n'est plus vert sur un dépôt dont
    l'asset publié ne parse pas.
    """
    if _skip_si_git_absent():
        return
    sain = blob_versionne()
    assert sain is not None
    with tempfile.TemporaryDirectory(prefix="pj-mermaid-montage-") as racine:
        depot = creer_depot_jetable(racine, parent=str(REPO))
        assert ref_oid(REF_VERDICT, depot) is not None
        assert oid_blob(str(CHEMIN_ASSET), depot) == BLOB_CASSE
        copie_du_banc(depot)

        rc_avant, sortie_avant = lancer_le_banc(depot)
        assert rc_avant != 0, "le banc est VERT sur un dépôt dont l'asset versionné est cassé"

        # le fichier de travail est écrasé par les octets sains, SANS commit :
        # c'est exactement le contournement mesuré par conv-1.
        remplacer_hors_commit(depot, sain)
        r = subprocess.run(["git", "status", "--short"], cwd=str(depot),
                           capture_output=True, text=True)
        assert "M bridge/%s" % NOM_ASSET in r.stdout, r.stdout
        assert oid_blob(str(CHEMIN_ASSET), depot) == BLOB_CASSE

        rc_apres, sortie_apres = lancer_le_banc(depot)
        assert rc_apres != 0, (
            "un fichier sain NON COMMITTÉ blanchit le dépôt — le banc ne prouve "
            "pas le blob versionné:\n%s" % sortie_apres
        )
        assert "worktree ≠ blob" in sortie_apres.splitlines()[-1] or \
            (not worktree_aligne_sur_blob(depot / CHEMIN_ASSET, depot)[0]), sortie_apres
        assert SHA_CASSE[:16] in sortie_apres or "${DISCORD_ID}" in sortie_apres, sortie_apres


def test_limite_la_surcharge_ne_remplace_jamais_le_verdict_du_blob():
    """limite : `PJ_MERMAID_ASSET` pointant un fichier NON versionné (sain)
    ne peut pas verdir un dépôt dont le blob versionné est cassé — la
    surcharge est une jambe paramétrée, jamais le mode par défaut du verdict."""
    if _skip_si_git_absent():
        return
    sain = blob_versionne()
    assert sain is not None
    with tempfile.TemporaryDirectory(prefix="pj-mermaid-surcharge-") as racine:
        depot = creer_depot_jetable(racine, parent=str(REPO))
        copie_du_banc(depot)
        hors_depot = Path(racine) / "hors-depot.js"
        hors_depot.write_bytes(sain)
        assert not str(hors_depot).startswith(str(depot))

        rc_defaut, sortie_defaut = lancer_le_banc(depot)
        rc_surcharge, sortie_surcharge = lancer_le_banc(
            depot, env={"PJ_MERMAID_ASSET": str(hors_depot)}
        )
        assert rc_defaut != 0, sortie_defaut
        assert rc_surcharge != 0, (
            "la surcharge PJ_MERMAID_ASSET a blanchi le blob versionné cassé:\n%s"
            % sortie_surcharge
        )
        assert "SURCHARGE" not in sortie_surcharge or "REFUSÉ" in sortie_surcharge, \
            sortie_surcharge

        # et sur le dépôt sain, la surcharge s'AJOUTE au verdict (jambe active)
        assert SHA_AMONT[:16] in sortie_surcharge

    # pendant positif, mesuré sur l'arbre SAIN du worktree : la jambe de
    # surcharge est ACTIVE et NOMMÉE (elle ne disparaît pas silencieusement
    # quand elle est saine — sinon la jambe paramétrée serait indistinguable
    # d'une jambe absente).
    sain_ici = blob_versionne()
    assert sain_ici is not None
    td, chemin_hors = ecrire_tmp(sain_ici, "surcharge-saine.js")
    try:
        ok_sans, motif_sans, _ = verdict()
        ok_avec, motif_avec, _ = verdict(env={"PJ_MERMAID_ASSET": str(chemin_hors)})
        assert ok_sans and ok_avec, motif_avec
        assert MARQUEUR_SURCHARGE not in motif_sans, motif_sans
        assert MARQUEUR_SURCHARGE in motif_avec, motif_avec
        assert sain_ici == Path(chemin_hors).read_bytes()
    finally:
        td.cleanup()


def test_erreur_le_blob_versionne_casse_est_refuse_meme_worktree_sain():
    """erreur : HEAD porte le blob cassé `c3922946` et un fichier de worktree
    sain — le banc ÉCHOUE (rc≠0), nomme `bridge/mermaid.min.js` ET l'identité
    du blob versionné, et liste le motif du refus (placeholder / census)."""
    if _skip_si_git_absent():
        return
    sain = blob_versionne()
    assert sain is not None
    with tempfile.TemporaryDirectory(prefix="pj-mermaid-erreur-") as racine:
        depot = creer_depot_jetable(racine, parent=str(REPO))
        # le montage du scénario : worktree sain, blob versionné cassé
        remplacer_hors_commit(depot, sain)
        copie_du_banc(depot)

        rc, sortie = lancer_le_banc(depot)
        assert rc != 0, sortie
        assert "bridge/%s" % NOM_ASSET in sortie, sortie
        assert BLOB_CASSE[:12] in sortie, sortie
        assert REF_VERDICT in sortie, sortie
        assert "${DISCORD_ID}" in sortie or "census non conforme" in sortie, sortie


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
    """erreur : le banc lui-même (mode CLI) ÉCHOUE (rc≠0) sur un blob cassé
    PASSÉ EN SURCHARGE, en nommant le fichier et la raison."""
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


def test_erreur_le_cli_sans_argument_juge_le_blob_versionne():
    """erreur : sans argument, le mode CLI lit le blob VERSIONNÉ — il nomme le
    chemin versionné, l'oid et le commit, et sort rc=0 sur l'arbre sain."""
    r = subprocess.run([sys.executable, str(Path(__file__).resolve())],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "blob %s:%s" % (REF_VERDICT, CHEMIN_ASSET) in r.stdout, r.stdout
    assert OID_AMONT[:12] in r.stdout, r.stdout
    assert (ref_oid(REF_VERDICT) or "")[:12] in r.stdout, r.stdout
    assert SHA_AMONT in r.stdout, r.stdout

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


def test_garde_fou_un_montage_ne_relance_jamais_pytest_sur_la_copie():
    """garde-fou ANTI-RÉCURSION : un cas de montage ne relance pas pytest.

    Défaut mesuré AVANT ce garde-fou : `lancer_le_banc()` relançait `pytest`
    sur la copie du banc, laquelle contient les cas de montage — la chaîne de
    sous-processus n'était pas bornée (9 processus `pytest` à t+8 s, 14 à
    t+16 s, sortie `EXIT=137` SIGKILL ; c'est la cause des OOM des runs
    précédents). Deux jambes indépendantes ferment la récursion :

      1. statique — `lancer_le_banc()` ne porte plus de relance `pytest` sur la
         copie : le littéral du geste est reconstruit par concaténation (une
         aiguille littérale se trouverait elle-même), et le point d'entrée CLI
         est exigé ;
      2. dynamique — sous `PJ_BANC_INTERNE=1`, `_skip_si_git_absent()` rend
         tout montage `skip`, donc une relance résiduelle serait inerte.
    """
    source = Path(__file__).read_text()
    aiguille = "-m " + "pytest"
    assert aiguille not in source, (
        "un `%s` subsiste dans le banc : la relance pytest d'un montage sur la "
        "copie du banc rejouerait les montages eux-mêmes, sans borne "
        "(mesuré : EXIT=137 par OOM)" % aiguille
    )
    assert 'subprocess.run(\n        [py, str(banc)]' in source, \
        "lancer_le_banc() doit passer par le point d'entrée CLI de la copie"
    assert "MARQUEUR_INTERNE" in source and "PJ_BANC_INTERNE" in source

    # jambe dynamique : le marqueur de relance interne rend le montage inerte
    env = dict(os.environ)
    env[MARQUEUR_INTERNE] = "1"
    r = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-rs", "-p", "no:cacheprovider",
         "-k", "non_committe", str(Path(__file__).resolve())],
        cwd=str(REPO), capture_output=True, text=True, env=env, timeout=300,
    )
    assert "skipped" in r.stdout, r.stdout
    assert "relance interne" in r.stdout, r.stdout
    assert r.returncode == 0, r.stdout + r.stderr


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
