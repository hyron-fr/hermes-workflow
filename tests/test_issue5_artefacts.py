"""RED — page des artefacts de décision (issue #5, slice 1 `preview-artefacts-decision`).

Ce banc ouvre la slice 1. Il juge le couple **page HTML + script de mesure** qui
**matérialise** les deux artefacts déjà ratifiés par t3 — il n'en produit aucun nouveau.

RÈGLE CENTRALE DE CONCEPTION (elle vient d'une mutation survivante mesurée pendant
l'écriture de ce banc) : **l'artefact est mesuré là où il est RENDU, pas là où il est
déclaré.** Une première version comparait la charge utile déclarée dans le registre machine
à elle-même : toute retouche de la partie rendue passait inaperçue, c'est-à-dire que le
2e scénario (« un artefact retouché à la main fait échouer le banc ») était insatisfiable
en pratique. Le contrat est donc :

  - le **registre** déclare l'ATTENDU : `name`, `kind`, `sha256`, `bytes`, `anchor` ;
  - la **page rendue** porte le MESURÉ : `<img data-artefact="<name>" src="data:image/png;base64,…">`
    pour un PNG, `<pre data-artefact="<name>">…</pre>` pour un texte (contenu VERBATIM de
    l'artefact, sans newline ajouté) ;
  - le **script** confronte rendu ↔ déclaré, et refuse un rendu dont l'empreinte est
    déclarée obsolète ;
  - le **banc** (ici) confronte rendu ↔ empreintes RATIFIÉES par t3, gelées dans ce fichier.

Contrat d'interface exécuté par ce banc (publié en `contrat-1` sur le blackboard) :

    python3 docs/architecture/context/issue-5-decision-flow.measure.py [--plate P] [--json]

Codes de sortie du script :

    0  concordance : les 3 artefacts rendus reproduisent leurs empreintes déclarées, la page
       porte 3 phases rendues et 0 composant interactif ;
    1  écart : une ligne par artefact dérivé, nommant son `name` ET les deux empreintes
       (déclarée, mesurée sur le rendu) ; une ligne par composant interactif trouvé ; un
       artefact dont l'empreinte mesurée est déclarée obsolète est refusé en nommant sa
       provenance (le message Discord d'origine) ;
    2  erreur d'usage : page introuvable, registre `decision-flow-ledger` absent ou illisible,
       artefact déclaré sans son élément rendu (`data-artefact="<name>"`).

Le script est **pur** : aucun réseau, aucun fichier écrit — et « aucun fichier » veut dire
**nulle part** : ni dans le répertoire des artefacts, ni à la racine du dépôt, ni dans
`docs/architecture/`, ni dans `tests/`, ni sous `/tmp`. Le garde correspondant
(`test_nominal_le_banc_ne_touche_aucun_fichier`) mesure dans une **copie isolée** du dépôt,
sous une **sentinelle d'audit**, et compare à un **ensemble attendu** : un instantané d'UN
seul répertoire, pris après que cinq autres cas ont déjà lancé le script, ne pouvait pas
échouer — masqué par l'ordre de la suite (mesuré par conv-1, `t_c54e8624`).

Sources verbatim à copier **octet pour octet** (elles sont déjà ratifiées) :

    PNG  …/attachments/t_795807e0/diagramme-sequence-v2.png
    MD1  …/attachments/t_795807e0/maquette-v3-message-1-notification.md
    MD2  …/attachments/t_795807e0/maquette-v3-message-2-point-a-statuer.md

Les artefacts v1 sont **obsolètes et interdits comme état courant** : diagramme Discord
`1551168046050054157` (boutons « Débloquer / Abandonner », sha256 `910f286be343a458…`) et
maquette `1551167343504396362` (2 boutons `disabled`) : le design ratifié n'a **plus aucun**
bouton. La page les NOMME comme obsolètes, elle ne les rend jamais comme l'état courant.

LA PAGE EST INERTE : ni `<button>`, ni `<select>`, ni attribut `custom_id`, ni requête
réseau. Nommer `pj:unblock` en PROSE de narration est en revanche légitime (le 3e scénario
l'exige) : la garde porte sur la STRUCTURE, jamais sur le texte narratif.
"""
import base64
import hashlib
import html
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
CONTEXT = REPO / "docs" / "architecture" / "context"
PLATE = CONTEXT / "issue-5-decision-flow.html"
MEASURE = CONTEXT / "issue-5-decision-flow.measure.py"
LEDGER_ID = "decision-flow-ledger"
LEDGER_RE = re.compile(
    r"<script[^>]*id=[\"']" + LEDGER_ID + r"[\"'][^>]*>(?P<json>.*?)</script>", re.S | re.I)

# --- empreintes RATIFIÉES par t3 (gelées : jamais dérivées de la page) ----------------
RATIFIES = {
    "diagramme-sequence-v2": {
        "kind": "png",
        "sha256": "b311b966793227d640d3487a0c9b2f87e94711d763ad11837a93959f5d3d4436",
        "bytes": 93406,
    },
    "maquette-message-1-notification": {
        "kind": "md",
        "sha256": "a4b3ed538e16dfab9f0cf04eaffff27186cc8e4f21e6f9f7711f9664626bfda6",
        "bytes": 788,
    },
    "maquette-message-2-point-a-statuer": {
        "kind": "md",
        "sha256": "b5ca3d354af744c51fa91c278b249d95a84374bb93b19617ceb691871a834ac6",
        "bytes": 1437,
    },
}

# --- provenances OBSOLÈTES (v1) que la page doit nommer, jamais rendre -----------------
DIAGRAMME_V1_MSG = "1551168046050054157"
MAQUETTE_V1_MSG = "1551167343504396362"
DIAGRAMME_V1_SHA = "910f286be343a458bb843af1960138ead48c96ca919a57045832e46eba4311d1"

PHASES_IDS = ["creation", "decision", "re-blocage"]


# --------------------------------------------------------------------------- outils

def _plate_text(path=None):
    """Texte de la page — échoue en NOMMANT le fichier absent (jamais un vert par défaut)."""
    p = Path(path) if path else PLATE
    if not p.is_file():
        pytest.fail(
            f"page des artefacts absente : {p} — le RED ne peut pas porter sur une page "
            f"qui n'existe pas. Si l'arbitrage retient un autre chemin, changer PLATE."
        )
    return p.read_text(encoding="utf-8")


def _measure_exists():
    if not MEASURE.is_file():
        pytest.fail(
            f"script de mesure absent : {MEASURE} — le banc exige un script VERSIONNÉ, "
            f"pas une commande reconstruite à la main. Si l'arbitrage retient un autre "
            f"chemin, changer MEASURE."
        )


def _run(*args, plate=None, json_out=False, cwd=None):
    """Exécute le script de mesure. `plate` explicite : on mesure des copies mutées."""
    _measure_exists()
    cmd = [sys.executable, str(MEASURE)]
    if plate is not None:
        cmd += ["--plate", str(plate)]
    if json_out:
        cmd += ["--json"]
    cmd += list(args)
    return subprocess.run(cmd, capture_output=True, text=True, cwd=str(cwd or REPO))


def _ledger_of(path=None):
    txt = _plate_text(path)
    m = LEDGER_RE.search(txt)
    assert m, (
        f"aucun registre machine `<script type=\"application/json\" id=\"{LEDGER_ID}\">` "
        f"dans {path or PLATE} : la page ne porte pas les artefacts que le script doit "
        f"reproduire."
    )
    try:
        reg = json.loads(m.group("json"))
    except json.JSONDecodeError as exc:
        pytest.fail(f"registre {LEDGER_ID} illisible ({exc})")
    assert reg.get("issue") == 5, f"registre d'une autre issue : {reg.get('issue')!r}"
    return reg


def _declares(reg):
    return {rec["name"]: rec for rec in reg.get("artefacts") or []}


def _copie(tmp_path, name="copie.html"):
    dest = tmp_path / name
    dest.write_text(_plate_text(), encoding="utf-8")
    return dest


def _rewrite_ledger(plate_path, mutate):
    """Applique `mutate(registre)` puis réécrit la page — copie jetable, jamais l'originale."""
    txt = Path(plate_path).read_text(encoding="utf-8")
    m = LEDGER_RE.search(txt)
    assert m, "copie sans registre : muter le registre est impossible"
    reg = json.loads(m.group("json"))
    mutate(reg)
    new = ("<script type=\"application/json\" id=\"%s\">%s</script>"
           % (LEDGER_ID, json.dumps(reg, ensure_ascii=False)))
    Path(plate_path).write_text(txt[:m.start()] + new + txt[m.end():], encoding="utf-8")


def _corps_hors_registre(txt):
    """La page SANS son registre machine : le seul endroit où un composant RENDU se voit.

    Indispensable pour que « 0 composant » et « nommer les v1 » soient compatibles : le
    motif `custom_id` apparaît LÉGITIMEMENT dans le JSON du registre (provenance obsolète).
    Juger le texte brut entier rendrait le 3e scénario impossible à satisfaire.
    """
    return LEDGER_RE.sub("", txt)


def _rendu(txt, name, kind):
    """Octets de l'artefact **rendu** dans la page, sous `data-artefact="<name>"`.

    C'est LE mesuré : l'absence de l'élément est un échec nommé plutôt qu'un défaut. Le
    contrat de payload est exactement celui que le script de mesure doit appliquer :
      - `kind="png"` : `<img data-artefact="<name>" … src="data:image/png;base64,…">` ;
      - `kind="md"`  : `<pre data-artefact="<name>">…</pre>`, contenu VERBATIM (texte de
        l'artefact échappé en HTML, sans newline ajouté).
    """
    if kind == "png":
        m = re.search(r'<img\b[^>]*\bdata-artefact="%s"[^>]*>' % re.escape(name), txt, re.I)
        assert m, (
            f"artefact `{name}` non rendu : aucun `<img data-artefact=\"{name}\">` dans la "
            f"page. Un artefact seulement déclaré au registre n'est pas reproduit."
        )
        s = re.search(r'\bsrc="(data:image/[a-z]+;base64,[^"]*)"', m.group(0), re.I)
        assert s, f"`{name}` : `<img data-artefact=...>` sans `src` data:image/base64"
        try:
            return base64.b64decode(s.group(1).split(",", 1)[1])
        except Exception as exc:                                   # noqa: BLE001
            pytest.fail(f"`{name}` : charge base64 illisible ({exc})")
    m = re.search(
        r'<pre\b[^>]*\bdata-artefact="%s"[^>]*>(?P<inner>.*?)</pre>' % re.escape(name),
        txt, re.S | re.I)
    assert m, (
        f"artefact `{name}` non rendu : aucun `<pre data-artefact=\"{name}\">` dans la "
        f"page. Un artefact seulement déclaré au registre n'est pas reproduit."
    )
    return html.unescape(m.group("inner")).encode("utf-8")


def _restaure_ledger(txt, reg):
    """Réécrit le registre dans un texte de page donné (conservé hors de `_rewrite_ledger`)."""
    m = LEDGER_RE.search(txt)
    assert m
    return (txt[:m.start()]
            + "<script type=\"application/json\" id=\"%s\">%s</script>"
            % (LEDGER_ID, json.dumps(reg, ensure_ascii=False))
            + txt[m.end():])


def _sha256_bytes(payload):
    return hashlib.sha256(payload).hexdigest()


def _report(res):
    """Rapport `--json` du script, ou échec nommant la sortie brute."""
    try:
        return json.loads(res.stdout)
    except json.JSONDecodeError:
        pytest.fail(
            "le mode `--json` doit écrire un objet JSON sur stdout ; obtenu "
            f"rc={res.returncode}\nstdout:\n{res.stdout}\nstderr:\n{res.stderr}"
        )


def _assert_nomme(res, *aiguilles):
    """La sortie doit NOMMER ce qu'elle refuse — un code de sortie seul ne suffit pas."""
    blob = (res.stdout or "") + (res.stderr or "")
    manquants = [a for a in aiguilles if a not in blob]
    assert not manquants, (
        f"sortie du script sans {manquants} ; rc={res.returncode}\nstdout:\n{res.stdout}\n"
        f"stderr:\n{res.stderr}"
    )


# --- outils de mesure du garde d'écriture ----------------------------------------------
#
# Le garde « le script n'écrit rien » a été mesuré FAUX par conv-1 (`t_c54e8624`) sous deux
# angles, et ces outils ferment les deux :
#
#   A. ORDRE : la version précédente comparait un instantané du seul répertoire des artefacts,
#      pris après que 5 cas avaient déjà lancé le script — son propre mutant survivait donc à
#      la SUITE ENTIÈRE (`rc=0, 20 passed`) alors que le cas cible seul rougissait (`rc=1`).
#      Ici la référence est l'ensemble ATTENDU des fichiers, et la mesure se fait dans une
#      COPIE ISOLÉE du dépôt : le résultat ne dépend d'aucun autre cas.
#   B. PORTÉE : l'instantané d'un seul répertoire laissait vertes les écritures à la racine du
#      dépôt, dans `docs/architecture/`, dans `tests/` et sous `/tmp`. Ici (1) toute écriture
#      DANS la copie est un écart (l'arbre entier est comparé), et (2) la SENTINELLE journalise
#      les écritures qui ne touchent pas la copie (chemins absolus, `/tmp`, dépôt partagé).

SENTINELLE = '''\
import os
import sys

_log = os.environ.get("PJ_WRITE_SENTINEL_LOG")
if _log:
    _fd = os.open(_log, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    _EVENEMENTS = ("os.remove", "os.rename", "os.mkdir", "os.rmdir", "os.link",
                   "os.symlink", "os.truncate", "os.chmod", "os.chown",
                   "shutil.copyfile", "shutil.copymode", "shutil.copystat",
                   "shutil.move", "shutil.rmtree", "tempfile.mkstemp", "tempfile.mkdtemp")

    def _journalise(event, args):
        """Toute ouverture en ÉCRITURE, toute création : journalisée, où qu'elle aille."""
        try:
            if event == "open":
                chemin, mode, flags = args
                ecrit = isinstance(mode, str) and any(c in mode for c in "wax+")
                if not ecrit and isinstance(flags, int):
                    ecrit = bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT
                                          | os.O_APPEND | os.O_TRUNC))
                if ecrit:
                    os.write(_fd, ("open %r mode=%r flags=%r\\n"
                                   % (str(chemin), mode, flags)).encode("utf-8"))
            elif event in _EVENEMENTS:
                os.write(_fd, ("%s %r\\n" % (event, args)).encode("utf-8"))
        except Exception:                                     # noqa: BLE001
            pass

    sys.addaudithook(_journalise)
'''

IGNORE_ARBRE = (".git", "__pycache__")


def _copie_isolee_du_depot(dest):
    """Copie le dépôt SOUS `dest` et renvoie le chemin du script de mesure de la copie.

    Le script est lancé DEPUIS la copie : `HERE` y pointe, donc une écriture « relative au
    script » aboutit dans la copie et non dans le worktree partagé — et le garde juge l'arbre
    entier, pas un seul répertoire. Les `.git` (0 octet ici : worktree) et `__pycache__` sont
    écartés pour que la copie reste petite et stable.
    """
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copytree(REPO, dest, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns(*IGNORE_ARBRE), symlinks=True)
    return dest / "docs" / "architecture" / "context" / MEASURE.name


def _arbre(racine):
    """Ensemble ATTENDU des fichiers de `racine` : chemin relatif -> sha256 (ou None : lien).

    C'est l'ensemble de référence explicite. Un instantané pris APRÈS qu'un autre cas a lancé
    le script contiendrait déjà l'intrus : c'est exactement le masque que ce garde ferme.
    """
    vus = {}
    for p in sorted(Path(racine).rglob("*")):
        rel = p.relative_to(racine)
        if any(partie in IGNORE_ARBRE for partie in rel.parts):
            continue
        if p.is_symlink():
            vus[str(rel)] = None
        elif p.is_file():
            vus[str(rel)] = hashlib.sha256(p.read_bytes()).hexdigest()
    return vus


def _site_sentinelle(tmp_path):
    """Écrit le `sitecustomize.py` de la sentinelle et renvoie son répertoire."""
    site = tmp_path / "sentinel-site"
    site.mkdir(parents=True, exist_ok=True)
    (site / "sitecustomize.py").write_text(SENTINELLE, encoding="utf-8")
    r = subprocess.run([sys.executable, "-m", "sitecustomize"], capture_output=True,
                       text=True, cwd=str(site))
    assert r.returncode == 0, (
        "la sentinelle ne doit pas casser le démarrage de Python (c'est la garde qui doit\n"
        f"échouer sur une écriture, pas l'instrumentation) :\n{r.stderr}"
    )
    return site


def _run_sentinelle(measure, copie, site, journal, plate=None):
    """Lance le script DE LA COPIE, sentinelle active, `cwd` dans la copie, sans écriture .pyc."""
    env = dict(os.environ)
    env["PJ_WRITE_SENTINEL_LOG"] = str(journal)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    ancien = env.get("PYTHONPATH")
    env["PYTHONPATH"] = str(site) + (os.pathsep + ancien if ancien else "")
    cmd = [sys.executable, "-B", str(measure)]
    if plate is not None:
        cmd += ["--plate", str(plate)]
    return subprocess.run(cmd, capture_output=True, text=True, cwd=str(copie), env=env)


def _journal(journal):
    """Lignes du journal de la sentinelle (chemin ABSOLU de `sys.executable` et de la copie
    exclus : le script réel peut relire sa page via `pathlib`, et `.pyc` désactivé)."""
    if not Path(journal).is_file():
        return []
    interdits = {"open %r mode='r'" % str(sys.executable), "open %r mode='rb'" % str(sys.executable)}
    lignes = []
    for brute in Path(journal).read_text(encoding="utf-8", errors="replace").splitlines():
        if brute in interdits:
            continue
        lignes.append(brute)
    return lignes


def _assert_aucune_ecriture(copie, attendu, journal, chemin):
    """Deux gardes indépendants : rien écrit DANS la copie, rien ouvert en écriture du tout.

    L'assertion est l'INVERSE de la mutation : elle nomme le fichier intrus, sa provenance et
    le journal brut, pour qu'un rouge soit lisible sans relance.
    """
    apres = _arbre(copie)
    if apres != attendu:
        ajoutes = sorted(set(apres) - set(attendu))
        disparus = sorted(set(attendu) - set(apres))
        modifies = sorted(k for k in set(apres) & set(attendu) if apres[k] != attendu[k])
        pytest.fail(
            f"chemin {chemin} : le script de mesure a ÉCRIT dans la copie du dépôt.\n"
            f"  fichiers introduits : {ajoutes or '—'}\n"
            f"  fichiers modifiés   : {modifies or '—'}\n"
            f"  fichiers supprimés  : {disparus or '—'}\n"
            f"  journal de la sentinelle :\n    " + "\n    ".join(_journal(journal))
        )
    intrus = _journal(journal)
    assert not intrus, (
        f"chemin {chemin} : le script de mesure a OUVERT EN ÉCRITURE un fichier hors de la "
        f"portée surveillée — la promesse est « aucune écriture », sans qualification de "
        f"répertoire :\n    " + "\n    ".join(intrus)
    )


# ==========================================================================
# A. NOMINAL — le banc reproduit les deux artefacts ratifiés
# ==========================================================================

def test_nominal_le_script_reproduit_les_trois_artefacts():
    """NOMINAL — 1er scénario : le script sort 0 et NOMME les deux sources."""
    res = _run()
    assert res.returncode == 0, (
        f"le script de mesure doit sortir 0 sur la page du dépôt ; rc={res.returncode}\n"
        f"stdout:\n{res.stdout}\nstderr:\n{res.stderr}"
    )
    _assert_nomme(res, "diagramme-sequence-v2", "maquette-message-1-notification",
                  "maquette-message-2-point-a-statuer")


def test_nominal_le_rapport_json_dit_3_phases_et_0_composant():
    """NOMINAL — 1er scénario (suite) : la page rend 3 phases et 0 composant interactif."""
    rep = _report(_run(json_out=True))
    assert rep.get("verdict") == "concordance", f"verdict attendu « concordance » : {rep}"
    assert rep.get("phases") == 3, f"3 phases attendues, mesuré {rep.get('phases')!r}"
    assert rep.get("components") == 0, (
        f"0 composant interactif attendu, mesuré {rep.get('components')!r}"
    )
    assert not rep.get("ecarts"), f"aucun écart attendu, obtenu {rep.get('ecarts')}"


def test_nominal_le_rendu_reproduit_les_empreintes_ratifiees():
    """NOMINAL — l'artefact RENDU hache l'empreinte ratifiée par t3 (mesuré, pas déclaré).

    C'est le cas qui rend le 2e scénario satisfiable : si la mesure portait sur le registre
    au lieu du rendu, retoucher la page ne changerait rien.
    """
    txt = _plate_text()
    decl = _declares(_ledger_of())
    assert set(decl) == set(RATIFIES), (
        f"artefacts déclarés {sorted(decl)} ≠ attendus {sorted(RATIFIES)}"
    )
    for name, attendu in RATIFIES.items():
        rec = decl[name]
        assert rec.get("kind") == attendu["kind"], f"{name} : kind {rec.get('kind')!r}"
        assert rec.get("sha256") == attendu["sha256"], (
            f"{name} : empreinte DÉCLARÉE ≠ empreinte ratifiée par t3"
        )
        assert rec.get("bytes") == attendu["bytes"], (
            f"{name} : taille déclarée {rec.get('bytes')!r} ≠ {attendu['bytes']} octets ratifiés"
        )
        brut = _rendu(txt, name, attendu["kind"])
        assert len(brut) == attendu["bytes"], (
            f"{name} : le rendu fait {len(brut)} octets, {attendu['bytes']} attendus"
        )
        assert _sha256_bytes(brut) == attendu["sha256"], (
            f"{name} : le RENDU ne reproduit PAS l'empreinte ratifiée par t3 "
            f"(mesuré {_sha256_bytes(brut)}…)"
        )


def test_nominal_la_page_rend_les_3_phases():
    """NOMINAL — 1er scénario (suite) : les 3 phases sont RENDUES dans la page.

    Le titre est cherché dans la page **hors registre machine** : le chercher dans le texte
    entier serait tautologique (le titre apparaît toujours dans le JSON qui le déclare).
    Un titre déclaré mais non rendu est un ÉCART (couvert par un cas limite dédié).
    """
    corps = _corps_hors_registre(_plate_text())
    phases = _ledger_of().get("phases") or []
    assert [p.get("id") for p in phases] == PHASES_IDS, (
        f"phases attendues {PHASES_IDS}, déclarées {[p.get('id') for p in phases]}"
    )
    for p in phases:
        titre = (p.get("title") or "").strip()
        assert titre, f"phase {p.get('id')} : titre vide"
        assert titre in corps, (
            f"le titre de la phase {p.get('id')} est déclaré au registre mais n'est PAS "
            f"rendu dans la page : {titre!r}"
        )


def test_nominal_la_page_est_inerte_et_hors_reseau():
    """NOMINAL — la page ne présente aucun composant et ne charge rien du réseau."""
    corps = _corps_hors_registre(_plate_text())
    assert "<button" not in corps.lower(), "la page ne doit porter aucun `<button>`"
    assert "<select" not in corps.lower(), "la page ne doit porter aucun `<select>`"
    assert not re.search(r"""\bcustom_id\s*=\s*["']""", corps), (
        "la page ne doit porter aucun ATTRIBUT `custom_id` (composant Discord)"
    )
    for motif in ('src="http', "src='http", 'href="http', "href='http", "@import url(http"):
        assert motif not in corps, f"aucun rendu hors réseau : {motif} trouvé dans la page"
    if "mermaid" in corps.lower():
        assert "mermaid.min.js" in corps, (
            "la page rend le flux avec mermaid : elle doit charger le `mermaid.min.js` "
            "DÉJÀ VERSIONNÉ (bridge/mermaid.min.js), jamais un CDN"
        )


def test_nominal_le_banc_ne_touche_aucun_fichier(tmp_path):
    """NOMINAL — le script MESURE : il n'écrit rien, NI ICI NI AILLEURS.

    Masque mesuré par conv-1 (`t_c54e8624`, comment 363) sur la version précédente : elle
    comparait l'instantané du SEUL répertoire des artefacts, pris APRÈS que cinq autres cas
    avaient déjà lancé le script — elle laissait donc passer son propre mutant sur la suite
    ENTIÈRE (`rc=0, 20 passed`) alors que le cas cible seul rougissait, et elle ne voyait ni
    la racine du dépôt, ni `docs/architecture/`, ni `tests/`, ni `/tmp` (4 mutations vertes).

    Deux mesures INDÉPENDANTES de l'ordre de la suite :

      1. **copie isolée** du dépôt, comparée à l'arbre ATTENDU (jamais à un instantané pris
         après qu'un autre cas a tourné) : toute écriture dans la copie se voit, où qu'elle
         soit dans l'arbre ;
      2. **sentinelle d'audit** (PEP 578) posée chez le processus enfant : toute ouverture en
         écriture (mode `w`/`a`/`x`/`+` ou `O_WRONLY`/`O_RDWR`/`O_CREAT`/`O_APPEND`/
         `O_TRUNC`) et toute création `os.*`/`shutil.*`/`tempfile.*` est journalisée, y compris
         vers `/tmp` ou vers le dépôt partagé.

    Le banc ne juge JAMAIS le site d'installation de `pathlib` du processus du BANC : ce
    fichier s'écrit légitimement (`pathlib.py` → `.pyc`) à chaque exécution ; seul le journal
    du processus ENFANT est jugé, et lui ne s'écrit que dans ce répertoire temporaire.
    """
    copie = tmp_path / "copie"
    measure = _copie_isolee_du_depot(copie)
    site = _site_sentinelle(tmp_path)
    journal = tmp_path / "sentinelle.log"

    # (0) la mesure porte sur la COPIE — jamais sur l'arbre partagé avec la carte dev. Aucune
    # assertion n'est faite sur l'état du worktree partagé : il bouge légitimement pendant que
    # ce banc tourne (`docs/architecture/context/**` est le domaine de `pj-dev`), une
    # comparaison y produirait des rouges étrangers au script. Le sujet est la copie.
    assert str(measure).startswith(str(copie)), (
        f"le banc doit mesurer le script de SA copie isolée, pas {measure}"
    )

    # (1) l'ARBRE ATTENDU — l'ensemble explicite des fichiers, pas un instantané tardif.
    attendu = _arbre(copie)
    for requis in ("docs/architecture/context/issue-5-decision-flow.html",
                   "docs/architecture/context/issue-5-decision-flow.measure.py",
                   "tests/test_issue5_artefacts.py"):
        assert requis in attendu, f"copie isolée incomplète : {requis} absent de {copie}"

    # (2) CONCORDANCE — chemin nominal.
    res = _run_sentinelle(measure, copie, site, journal)
    assert res.returncode == 0, (
        f"le script de mesure doit sortir 0 sur la copie isolée ; rc={res.returncode}\n"
        f"stdout:\n{res.stdout}\nstderr:\n{res.stderr}"
    )
    _assert_aucune_ecriture(copie, attendu, journal, "concordance")

    # (3) ÉCART — le chemin où un script bavard écrit volontiers un rapport.
    plate_ecart = copie / "en-ecart.html"
    txt = _plate_text().replace("Posté dans", "Posté danS", 1)
    assert "Posté danS" in txt, "la mutation du cas doit porter sur la page de référence"
    plate_ecart.write_text(txt, encoding="utf-8")
    attendu_ecart = _arbre(copie)              # l'arbre attendu, mutation COMPRISE
    journal.unlink(missing_ok=True)
    res = _run_sentinelle(measure, copie, site, journal, plate=plate_ecart)
    assert res.returncode == 1, (
        f"la page en écart doit faire sortir 1 ; rc={res.returncode}\n{res.stdout}\n{res.stderr}"
    )
    _assert_aucune_ecriture(copie, attendu_ecart, journal, "écart")

    # (4) ERREUR D'USAGE — le 3e chemin de sortie, lui aussi sans écriture.
    journal.unlink(missing_ok=True)
    absente = copie / "docs" / "architecture" / "context" / "absente.html"
    res = _run_sentinelle(measure, copie, site, journal, plate=absente)
    assert res.returncode == 2, (
        f"page introuvable = erreur d'usage (2) sur la copie ; rc={res.returncode}\n"
        f"{res.stdout}\n{res.stderr}"
    )
    _assert_aucune_ecriture(copie, attendu_ecart, journal, "erreur d'usage")


# ==========================================================================
# B. LIMITE — un artefact retouché à la main fait échouer le banc
# ==========================================================================

def test_limite_un_caractere_retouche_dans_le_rendu_fait_echouer_le_banc(tmp_path):
    """LIMITE — 2e scénario : la maquette RENDUE modifiée d'UN caractère sort en erreur.

    La retouche porte sur la page RENDUE (le `<pre>`), pas sur le registre : c'est le cas
    réel d'un artefact retouché à la main dans le fichier versionné.
    """
    copie = _copie(tmp_path)
    txt = copie.read_text(encoding="utf-8")
    marqueur = "Posté dans"
    assert txt.count(marqueur) >= 1, "la référence doit porter le marqueur du cas"
    copie.write_text(txt.replace(marqueur, "Posté danS", 1), encoding="utf-8")

    res = _run(plate=copie)
    assert res.returncode == 1, (
        f"un artefact rendu retouché d'un caractère doit faire sortir 1 ; rc={res.returncode}\n"
        f"stdout:\n{res.stdout}\nstderr:\n{res.stderr}"
    )
    _assert_nomme(res, "maquette-message-1-notification")
    blob = (res.stdout or "") + (res.stderr or "")
    assert RATIFIES["maquette-message-1-notification"]["sha256"][:16] in blob, (
        "l'écart doit nommer l'empreinte ATTENDUE (celle ratifiée par t3)"
    )
    assert "concordance" not in blob, "aucun verdict positif ne doit être écrit en cas d'écart"


def test_limite_deux_artefacts_derives_sont_nommes_tous_les_deux(tmp_path):
    """LIMITE — deux dérives simultanées : le script les nomme TOUTES, pas seulement la 1re."""
    copie = _copie(tmp_path, "copie2.html")
    txt = copie.read_text(encoding="utf-8")
    n1 = txt.count("Posté dans")
    n2 = txt.count("Point à statuer")
    assert n1 and n2, "les deux marqueurs doivent exister pour que la mutation soit fidèle"
    txt = txt.replace("Posté dans", "Posté danS", 1).replace("Point à statuer", "Point à statuerX", 1)
    copie.write_text(txt, encoding="utf-8")

    res = _run(plate=copie)
    assert res.returncode == 1, f"rc={res.returncode}\n{res.stdout}\n{res.stderr}"
    _assert_nomme(res, "maquette-message-1-notification", "maquette-message-2-point-a-statuer")


def test_limite_declaration_coherente_mais_rendu_retouche(tmp_path):
    """LIMITE — le registre est RÉÉCRIT pour « avouer » la retouche : le banc rougit quand même.

    C'est la garde anti-tautologie : un registre peut toujours se déclarer cohérent avec sa
    propre page. Seule la comparaison au **ratifié par t3** (gelé dans ce fichier) tranche.
    Le script doit alors sortir 0 (il juge la cohérence interne page ↔ registre) et c'est CE
    BANC qui refuse — c'est exactement la raison d'être du gel des empreintes ici.
    """
    copie = _copie(tmp_path, "auto-coherent.html")
    txt = copie.read_text(encoding="utf-8")
    retouche = txt.replace("Posté dans", "Posté danS", 1)
    m = re.search(
        r'<pre\b[^>]*\bdata-artefact="maquette-message-1-notification"[^>]*>(?P<inner>.*?)</pre>',
        retouche, re.S | re.I)
    assert m, "la page de référence doit rendre la maquette 1 dans un `<pre data-artefact=…>`"
    brut = html.unescape(m.group("inner")).encode("utf-8")
    reg = json.loads(LEDGER_RE.search(retouche).group("json"))
    for rec in reg["artefacts"]:
        if rec["name"] == "maquette-message-1-notification":
            rec["sha256"] = _sha256_bytes(brut)
            rec["bytes"] = len(brut)
    copie.write_text(_restaure_ledger(retouche, reg), encoding="utf-8")

    # (1) le script voit un couple page/registre cohérent : c'est NORMAL, il ne connaît pas t3.
    res = _run(plate=copie)
    assert res.returncode == 0, (
        f"le script juge la cohérence interne, pas la ratification ; rc={res.returncode}\n"
        f"stdout:\n{res.stdout}\nstderr:\n{res.stderr}"
    )
    # (2) et c'est CE BANC qui refuse, parce que son empreinte attendue est GELÉE (t3).
    attendu = RATIFIES["maquette-message-1-notification"]
    mesure = _sha256_bytes(brut)
    assert mesure != attendu["sha256"], (
        "la mutation de ce cas doit avoir réellement changé le rendu de la maquette 1"
    )
    assert _sha256_bytes(brut) != attendu["sha256"], (
        f"maquette-message-1-notification : le rendu ne reproduit pas l'empreinte ratifiée "
        f"par t3 (mesuré {mesure[:16]}…, ratifié {attendu['sha256'][:16]}…)"
    )


def test_limite_page_introuvable_est_erreur_d_usage(tmp_path):
    """LIMITE — page absente : code 2, message nommant le chemin, aucun fichier écrit."""
    res = _run(plate=tmp_path / "absente.html")
    assert res.returncode == 2, (
        f"page introuvable = erreur d'usage (2) ; rc={res.returncode}\n{res.stdout}\n{res.stderr}"
    )
    _assert_nomme(res, "absente.html")


def test_limite_registre_absent_est_erreur_d_usage(tmp_path):
    """LIMITE — page sans registre machine : code 2, registre nommé (jamais un vert)."""
    copie = _copie(tmp_path, "sans-registre.html")
    txt = copie.read_text(encoding="utf-8")
    copie.write_text(LEDGER_RE.sub("", txt), encoding="utf-8")
    res = _run(plate=copie)
    assert res.returncode == 2, f"rc={res.returncode}\n{res.stdout}\n{res.stderr}"
    _assert_nomme(res, LEDGER_ID)


def test_limite_artefact_non_rendu_est_erreur_d_usage(tmp_path):
    """LIMITE — un artefact déclaré mais NON RENDU : code 2, l'artefact est nommé.

    Déclarer une empreinte sans rendre la chose mesurée ne doit pas produire un vert : c'est
    exactement le mode de défaillance que ce banc existe pour fermer.
    """
    copie = _copie(tmp_path, "non-rendu.html")
    txt = copie.read_text(encoding="utf-8")
    txt = re.sub(
        r'<pre\b[^>]*\bdata-artefact="maquette-message-2-point-a-statuer"[^>]*>.*?</pre>',
        "", txt, flags=re.S | re.I)
    copie.write_text(txt, encoding="utf-8")

    res = _run(plate=copie)
    assert res.returncode == 2, (
        f"artefact déclaré non rendu = erreur d'usage (2) ; rc={res.returncode}\n"
        f"stdout:\n{res.stdout}\nstderr:\n{res.stderr}"
    )
    _assert_nomme(res, "maquette-message-2-point-a-statuer")


def test_limite_titre_de_phase_non_rendu_est_un_ecart(tmp_path):
    """LIMITE — un titre de phase déclaré mais NON RENDU est un écart.

    Sans ce cas, `test_nominal_la_page_rend_les_3_phases` serait tautologique : le titre
    apparaît toujours dans le JSON qui le déclare.
    """
    copie = _copie(tmp_path, "titre-non-rendu.html")
    txt = copie.read_text(encoding="utf-8")
    titre = "3. Re-blocage \u2014 la même issue enfant est rouverte"
    assert titre in txt, "la référence doit porter le titre attendu pour que la mutation soit fidèle"
    copie.write_text(txt.replace(titre, "3. Re-blocage (titre modifie)", 1), encoding="utf-8")

    res = _run(plate=copie)
    assert res.returncode == 1, f"rc={res.returncode}\n{res.stdout}\n{res.stderr}"
    _assert_nomme(res, "re-blocage")


# ==========================================================================
# C. ERREUR — les artefacts v1 obsolètes sont refusés
# ==========================================================================

def test_erreur_artefact_obsolete_refuse_en_nommant_sa_provenance(tmp_path):
    """ERREUR — 3e scénario : un artefact rendu dont l'empreinte est obsolète est refusé.

    Le rendu injecté EST l'artefact v1 (boutons « Débloquer / Abandonner ») ; sa provenance
    (message Discord d'origine) est déclarée au registre : le script doit la nommer. Sans
    cette règle, l'ancien design rentrerait par la porte de derrière.
    """
    copie = _copie(tmp_path, "obsolete.html")
    txt = copie.read_text(encoding="utf-8")
    v1 = b"boutons Debloquer / Abandonner (design v1, retire au 3e tour)"

    ancien = _rendu(txt, "diagramme-sequence-v2", "png")
    assert ancien != v1
    txt = txt.replace(
        "data:image/png;base64," + base64.b64encode(ancien).decode(),
        "data:image/png;base64," + base64.b64encode(v1).decode(), 1)
    # le registre s'aligne : l'écart n'est pas de cohérence, il est d'OBSOLESCENCE
    reg = json.loads(LEDGER_RE.search(txt).group("json"))
    for rec in reg["artefacts"]:
        if rec["name"] == "diagramme-sequence-v2":
            rec["sha256"] = _sha256_bytes(v1)
            rec["bytes"] = len(v1)
    for rec in reg["obsolete"]:
        if rec.get("discord_message") == DIAGRAMME_V1_MSG:
            rec["sha256"] = _sha256_bytes(v1)
    copie.write_text(_restaure_ledger(txt, reg), encoding="utf-8")

    res = _run(plate=copie)
    assert res.returncode == 1, (
        f"un artefact obsolète doit être refusé (1) ; rc={res.returncode}\n"
        f"stdout:\n{res.stdout}\nstderr:\n{res.stderr}"
    )
    _assert_nomme(res, DIAGRAMME_V1_MSG)


def test_erreur_la_page_nomme_les_deux_provenances_v1_obsoletes():
    """ERREUR — 3e scénario (suite) : la page nomme les DEUX v1 comme obsolètes."""
    reg = _ledger_of()
    obs = reg.get("obsolete") or []
    msgs = {o.get("discord_message") for o in obs}
    assert {DIAGRAMME_V1_MSG, MAQUETTE_V1_MSG} <= msgs, (
        f"les deux provenances v1 doivent être déclarées obsolètes ; déclarées : {sorted(msgs)}"
    )
    assert DIAGRAMME_V1_SHA in json.dumps(obs), (
        "l'empreinte du diagramme v1 (910f286be343a458…) doit être déclarée : c'est elle qui "
        "rend le refus vérifiable"
    )
    decl = {rec.get("sha256") for rec in reg.get("artefacts") or []}
    assert DIAGRAMME_V1_SHA not in decl, "un artefact v1 ne doit JAMAIS être déclaré courant"
    corps = _corps_hors_registre(_plate_text())
    assert DIAGRAMME_V1_MSG in corps and MAQUETTE_V1_MSG in corps, (
        "la page NOMME les deux provenances v1 dans sa partie rendue (le lecteur doit "
        "pouvoir vérifier ce qui a été écarté)"
    )


def test_erreur_un_bouton_dans_la_page_est_refuse(tmp_path):
    """ERREUR — 3e scénario (suite) : un bouton ajouté à la page rendue fait refuser le banc."""
    copie = _copie(tmp_path, "avec-bouton.html")
    txt = copie.read_text(encoding="utf-8")
    copie.write_text(txt.replace("</body>", "<button>Débloquer</button></body>", 1),
                     encoding="utf-8")
    res = _run(plate=copie)
    assert res.returncode == 1, (
        f"un composant interactif doit faire échouer le banc ; rc={res.returncode}\n"
        f"stdout:\n{res.stdout}\nstderr:\n{res.stderr}"
    )
    _assert_nomme(res, "composant")


def test_erreur_un_custom_id_dans_la_page_est_refuse(tmp_path):
    """ERREUR — un ATTRIBUT `custom_id` (composant Discord du design v1) est refusé.

    C'est l'attribut STRUCTUREL qui est jugé — pas la narration. Nommer `pj:unblock` en
    prose d'obsolescence reste légitime et est couvert par
    `test_limite_la_narration_des_obsoletes_n_est_pas_un_composant` : un banc qui
    refuserait tout `pj:` dans le texte rendrait le 3e scénario insatisfaisable.
    """
    copie = _copie(tmp_path, "avec-custom-id.html")
    txt = copie.read_text(encoding="utf-8")
    copie.write_text(txt.replace(
        "</body>",
        '<code>custom_id="pj:unblock:pj-hermes-workflow/t_aaa"</code></body>', 1),
        encoding="utf-8")
    res = _run(plate=copie)
    assert res.returncode == 1, f"rc={res.returncode}\n{res.stdout}\n{res.stderr}"
    _assert_nomme(res, "custom_id")


def test_limite_la_narration_des_obsoletes_n_est_pas_un_composant(tmp_path):
    """LIMITE (protection inverse) — nommer `pj:unblock` en PROSE n'est pas un composant.

    Le 3e scénario exige que la page nomme les v1 (boutons « Débloquer / Abandonner » et
    `pj:unblock` / `pj:drop`) : un script qui refuserait toute occurrence de ces chaînes
    rendrait le scénario impossible à satisfaire. La garde doit viser l'attribut
    `custom_id`, l'élément `<button>` et l'élément `<select>` — jamais le texte narratif.
    """
    copie = _copie(tmp_path, "narration.html")
    txt = copie.read_text(encoding="utf-8")
    copie.write_text(txt.replace(
        "</body>",
        "<p>Le design v1 portait des boutons `pj:unblock` / `pj:drop` : retirés.</p></body>",
        1), encoding="utf-8")
    res = _run(plate=copie)
    assert res.returncode == 0, (
        f"la narration d'une provenance obsolète ne doit PAS faire échouer le banc ; "
        f"rc={res.returncode}\nstdout:\n{res.stdout}\nstderr:\n{res.stderr}"
    )


def test_limite_un_select_dans_la_page_est_refuse(tmp_path):
    """LIMITE — un `<select>` (menu déroulant du repli >5 cartes, v1) est un composant."""
    copie = _copie(tmp_path, "avec-select.html")
    txt = copie.read_text(encoding="utf-8")
    copie.write_text(txt.replace("</body>", "<select></select></body>", 1), encoding="utf-8")
    res = _run(plate=copie)
    assert res.returncode == 1, f"rc={res.returncode}\n{res.stdout}\n{res.stderr}"
    _assert_nomme(res, "composant")


def test_erreur_le_banc_est_pur_aucun_reseau():
    """ERREUR — garde-fou : le script de mesure ne doit ouvrir aucun accès réseau."""
    _measure_exists()
    src = MEASURE.read_text(encoding="utf-8")
    for interdit in ("import requests", "import urllib", "from urllib", "import socket",
                     "http.client", "import httpx"):
        assert interdit not in src, (
            f"le banc est PUR (aucun réseau) : `{interdit}` trouvé dans {MEASURE.name}"
        )
