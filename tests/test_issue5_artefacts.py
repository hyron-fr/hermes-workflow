"""RED — page des artefacts de décision (issue #5, slice 1 `preview-artefacts-decision`).

Ce banc ouvre la slice 1. Il juge le couple **page HTML + script de mesure** qui
**matérialise** les deux artefacts déjà ratifiés par t3 — il n'en produit aucun nouveau.

Contrat d'interface exécuté par ce banc (publié en `contrat-1` sur le blackboard) :

    python3 docs/architecture/context/issue-5-decision-flow.measure.py [--plate P] [--json]

Codes de sortie du script :

    0  concordance : les 3 artefacts déclarés sont reproduits à l'identique, la page porte
       3 phases et 0 composant interactif ;
    1  écart : une ligne par artefact dérivé, nommant son `name` ET les deux empreintes
       (attendue, mesurée) ; une ligne par composant interactif trouvé ; un artefact dont
       l'empreinte est déclarée obsolète est refusé en nommant sa provenance (le message
       Discord d'origine) ;
    2  erreur d'usage : page introuvable, registre `decision-flow-ledger` absent ou illisible,
       artefact déclaré sans charge utile.

Le script est **pur** : aucun réseau, aucun fichier écrit.

Le registre machine de la page — bloc `<script type="application/json" id="decision-flow-ledger">`
— porte, et c'est ce que ce banc lit :

    {"issue": 5,
     "artefacts": [{"name": ..., "kind": "png"|"md", "sha256": ..., "bytes": ...,
                    "data": "data:image/png;base64,…" | "text": "…"}, …3…],
     "phases": [{"id": "creation"|"decision"|"re-blocage", "title": …}, …3…],
     "components": 0,
     "obsolete": [{"name": …, "discord_message": …, "sha256": …}, …]}

Empreintes RATIFIÉES par t3 (gelées ici : elles viennent de la ratification, pas de l'arbre,
sinon le banc se validerait par lui-même). Sources verbatim à copier **octet pour octet** :

    PNG  /home/elix/.hermes/kanban/boards/pj-hermes-workflow/attachments/t_795807e0/diagramme-sequence-v2.png
    MD1  /home/elix/.hermes/kanban/boards/pj-hermes-workflow/attachments/t_795807e0/maquette-v3-message-1-notification.md
    MD2  /home/elix/.hermes/kanban/boards/pj-hermes-workflow/attachments/t_795807e0/maquette-v3-message-2-point-a-statuer.md

Les artefacts v1 sont **obsolètes et interdits comme état courant** : diagramme Discord
`1551168046050054157` (boutons « Débloquer / Abandonner », sha256 `910f286be343a458…`) et
maquette `1551167343504396362` (2 boutons `disabled`) : le design ratifié n'a **plus aucun**
bouton. La page les NOMME comme obsolètes, elle ne les présente jamais comme l'état courant.
"""
import base64
import hashlib
import json
import re
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

# --- provenances OBSOLÈTES (v1) que la page doit nommer, jamais exposer -----------------
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


def _artefacts(reg):
    out = {}
    for rec in reg.get("artefacts") or []:
        out[rec["name"]] = rec
    return out


def _copy_plate(tmp_path, name="copie.html"):
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
    new = "<script type=\"application/json\" id=\"%s\">%s</script>" % (
        LEDGER_ID, json.dumps(reg, ensure_ascii=False))
    Path(plate_path).write_text(txt[:m.start()] + new + txt[m.end():], encoding="utf-8")


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
    """NOMINAL — 1er scénario (suite) : la page décrit 3 phases et 0 composant interactif."""
    rep = _report(_run(json_out=True))
    assert rep.get("verdict") == "concordance", f"verdict attendu « concordance » : {rep}"
    assert rep.get("phases") == 3, f"3 phases attendues, mesuré {rep.get('phases')!r}"
    assert rep.get("components") == 0, (
        f"0 composant interactif attendu, mesuré {rep.get('components')!r}"
    )
    assert not rep.get("ecarts"), f"aucun écart attendu, obtenu {rep.get('ecarts')}"


def test_nominal_le_registre_porte_les_empreintes_ratifiees():
    """NOMINAL — les 3 artefacts déclarés portent les empreintes ratifiées par t3."""
    decl = _artefacts(_ledger_of())
    assert set(decl) == set(RATIFIES), (
        f"artefacts déclarés {sorted(decl)} ≠ attendus {sorted(RATIFIES)}"
    )
    for name, attendu in RATIFIES.items():
        rec = decl[name]
        assert rec.get("sha256") == attendu["sha256"], (
            f"{name} : empreinte déclarée ≠ empreinte ratifiée par t3"
        )
        assert rec.get("bytes") == attendu["bytes"], (
            f"{name} : taille déclarée {rec.get('bytes')!r} ≠ {attendu['bytes']} octets ratifiés"
        )
        assert rec.get("kind") == attendu["kind"], f"{name} : kind {rec.get('kind')!r}"
        charge = rec.get("data") if attendu["kind"] == "png" else rec.get("text")
        assert charge, f"{name} : la page ne porte pas la charge utile ({attendu['kind']})"
        # La charge utile DÉCLARÉE doit bien hacher l'empreinte ratifiée : sans cela, la
        # page déclarerait un nombre sans porter l'artefact (le banc serait tautologique).
        brut = (base64.b64decode(charge.split(",", 1)[1]) if attendu["kind"] == "png"
                else charge.encode("utf-8"))
        assert _sha256_bytes(brut) == attendu["sha256"], (
            f"{name} : la charge utile portée par la page ne reproduit PAS l'empreinte "
            f"ratifiée (mesuré {_sha256_bytes(brut)[:16]}…)"
        )


def test_nominal_la_page_decrit_les_3_phases():
    """NOMINAL — 1er scénario (suite) : les 3 phases du flux sont écrites dans la page."""
    txt = _plate_text()
    phases = _ledger_of().get("phases") or []
    assert [p.get("id") for p in phases] == PHASES_IDS, (
        f"phases attendues {PHASES_IDS}, déclarées {[p.get('id') for p in phases]}"
    )
    for p in phases:
        titre = (p.get("title") or "").strip()
        assert titre, f"phase {p.get('id')} : titre vide"
        assert titre in txt, f"le titre de la phase {p.get('id')} n'apparaît pas dans la page"


def test_nominal_la_page_est_inerte_et_hors_reseau():
    """NOMINAL — la page ne présente aucun composant et ne charge rien du réseau."""
    txt = _plate_text()
    assert "<button" not in txt.lower(), "la page ne doit porter aucun `<button>`"
    assert "custom_id" not in txt, "la page ne doit porter aucun `custom_id`"
    assert "<select" not in txt.lower(), "la page ne doit porter aucun `<select>`"
    for motif in ('src="http', "src='http", 'href="http', "href='http", "@import url(http"):
        assert motif not in txt, f"aucun rendu hors réseau : {motif} trouvé dans la page"
    if "mermaid" in txt.lower():
        assert "mermaid.min.js" in txt, (
            "la page rend le flux avec mermaid : elle doit charger le `mermaid.min.js` "
            "DÉJÀ VERSIONNÉ (bridge/mermaid.min.js), jamais un CDN"
        )


def test_nominal_le_banc_ne_touche_aucun_fichier():
    """NOMINAL — le script MESURE : il n'écrit aucun fichier, même en cas d'écart."""
    avant = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True,
                           cwd=str(REPO)).stdout
    res = _run()
    apres = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True,
                           cwd=str(REPO)).stdout
    assert res.returncode == 0
    assert avant == apres, (
        f"le script de mesure a modifié l'arbre (il doit être en lecture seule) :\n"
        f"avant:\n{avant}\naprès:\n{apres}"
    )


# ==========================================================================
# B. LIMITE — un artefact retouché à la main fait échouer le banc
# ==========================================================================

def test_limite_un_caractere_retouche_fait_echouer_le_banc(tmp_path):
    """LIMITE — 2e scénario : la maquette modifiée d'UN caractère sort en erreur, nommée."""
    copie = _copy_plate(tmp_path)

    def muter(reg):
        for rec in reg["artefacts"]:
            if rec["name"] == "maquette-message-1-notification":
                rec["text"] = rec["text"].replace("Posté dans", "Posté danS", 1)

    _rewrite_ledger(copie, muter)
    res = _run(plate=copie)
    assert res.returncode == 1, (
        f"un artefact retouché d'un caractère doit faire sortir 1 ; rc={res.returncode}\n"
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
    copie = _copy_plate(tmp_path, "copie2.html")

    def muter(reg):
        for rec in reg["artefacts"]:
            if rec["kind"] == "md":
                rec["text"] = rec["text"] + "x"     # un caractère en trop

    _rewrite_ledger(copie, muter)
    res = _run(plate=copie)
    assert res.returncode == 1, f"rc={res.returncode}\n{res.stdout}\n{res.stderr}"
    _assert_nomme(res, "maquette-message-1-notification", "maquette-message-2-point-a-statuer")


def test_limite_page_introuvable_est_erreur_d_usage(tmp_path):
    """LIMITE — page absente : code 2, message nommant le chemin, aucun fichier écrit."""
    res = _run(plate=tmp_path / "absente.html")
    assert res.returncode == 2, (
        f"page introuvable = erreur d'usage (2) ; rc={res.returncode}\n{res.stdout}\n{res.stderr}"
    )
    _assert_nomme(res, "absente.html")


def test_limite_registre_absent_est_erreur_d_usage(tmp_path):
    """LIMITE — page sans registre machine : code 2, registre nommé (jamais un vert)."""
    copie = _copy_plate(tmp_path, "sans-registre.html")
    txt = copie.read_text(encoding="utf-8")
    copie.write_text(LEDGER_RE.sub("", txt), encoding="utf-8")
    res = _run(plate=copie)
    assert res.returncode == 2, f"rc={res.returncode}\n{res.stdout}\n{res.stderr}"
    _assert_nomme(res, LEDGER_ID)


# ==========================================================================
# C. ERREUR — les artefacts v1 obsolètes sont refusés
# ==========================================================================

def test_erreur_artefact_obsolete_refuse_en_nommant_sa_provenance(tmp_path):
    """ERREUR — 3e scénario : un artefact dont l'empreinte est obsolète est refusé, nommé.

    La charge utile injectée EST l'artefact v1 (boutons « Débloquer / Abandonner ») ; sa
    provenance (message Discord d'origine) est déclarée au registre : le script doit la
    nommer. Sans cette règle, l'ancien design rentrerait par la porte de derrière.
    """
    copie = _copy_plate(tmp_path, "obsolete.html")
    v1 = b"boutons Debloquer / Abandonner (design v1, retire au 3e tour)"

    def muter(reg):
        for rec in reg["artefacts"]:
            if rec["name"] == "diagramme-sequence-v2":
                rec["data"] = "data:image/png;base64," + base64.b64encode(v1).decode()
                rec["sha256"] = _sha256_bytes(v1)
                rec["bytes"] = len(v1)
        for rec in reg["obsolete"]:
            if rec.get("discord_message") == DIAGRAMME_V1_MSG:
                rec["sha256"] = _sha256_bytes(v1)

    _rewrite_ledger(copie, muter)
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


def test_erreur_un_bouton_dans_la_page_est_refuse(tmp_path):
    """ERREUR — 3e scénario (suite) : un bouton ajouté à la page fait refuser le banc."""
    copie = _copy_plate(tmp_path, "avec-bouton.html")
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
    """ERREUR — un `custom_id` (trace du design à boutons) fait refuser le banc."""
    copie = _copy_plate(tmp_path, "avec-custom-id.html")
    txt = copie.read_text(encoding="utf-8")
    copie.write_text(txt.replace("</body>",
                                 '<code>pj:unblock:pj-hermes-workflow/t_aaa</code></body>', 1),
                     encoding="utf-8")
    res = _run(plate=copie)
    assert res.returncode == 1, f"rc={res.returncode}\n{res.stdout}\n{res.stderr}"
    _assert_nomme(res, "custom_id")


def test_erreur_le_banc_est_pur_aucun_reseau():
    """ERREUR — garde-fou : le script de mesure ne doit ouvrir aucun accès réseau."""
    _measure_exists()
    src = MEASURE.read_text(encoding="utf-8")
    for interdit in ("import requests", "import urllib", "from urllib", "import socket",
                     "http.client", "import httpx"):
        assert interdit not in src, (
            f"le banc est PUR (aucun réseau) : `{interdit}` trouvé dans {MEASURE.name}"
        )
