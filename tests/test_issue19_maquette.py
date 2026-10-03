"""RED — artefact de cadrage #19, slice 1 `preview-maquette-format-titre`.

Ce banc ouvre la slice 1. Il juge le couple **page HTML + script de mesure** qui
**matérialise** dans le dépôt la maquette du format de titre/description déjà **arbitré**
par l'humain (t3, fil Discord du ticket #19) — il n'en produit aucun nouveau et ne
redécide rien.

Périmètre de la slice (gelé par `specs/19/slices.json`, slug
`preview-maquette-format-titre`) :

    docs/architecture/context/issue-19-maquette.html        (la page, inerte)
    docs/architecture/context/issue-19-maquette.measure.py  (la mesure, pure)
    tests/test_issue19_maquette.py                          (ce banc, pj-test)

LA SOURCE DE VÉRITÉ DES TOTAUX EST DOUBLE, ET C'EST VOULU : le **registre machine** de la
page déclare l'attendu, le **script** recalcule le mesuré depuis le dispositif réel, et CE
BANC gèle les valeurs **ratifiées** (ci-dessous, `RATIFIES`). Sans ce troisième étage, un
registre réécrit pour « s'avouer cohérent » avec sa propre page passerait le script et
rendrait le scénario « un chiffre dérive » insatisfiable.

Contrat d'interface exécuté par ce banc (publié en `contrat-1` sur le blackboard) :

    python3 docs/architecture/context/issue-19-maquette.measure.py [--plate P] [--json]

Registre machine attendu dans la page (id EXACT — le script et le banc le cherchent) :

    <script type="application/json" id="issue19-ledger">{ … }</script>

    {
      "issue": 19,
      "repo": "hermes-workflow",
      "issue_number": 19,
      "issue_title": "Discord thread title and description update",
      "active_icon": "🎬",
      "icons": ["🎬", "⚙️", "⚠", "🛑"],          # les 4 états nommés par l'humain
      "prefix_len": 22,                          # len("🎬 hermes-workflow|#19|")
      "prefix_len_gear": 23,                     # len("⚙️ hermes-workflow|#19|")
      "title_budget": 78,                        # 100 - 22 (borne Discord)
      "current_name_len": 65,                    # 22 + len(titre de l'issue) = 22 + 43
      "title_max": 100,                          # borne Discord d'un nom de thread
      "readers": [                               # les 3 sites qui résolvent par NOM
        {"path": "pipeline/engine.py", "line": 77},
        {"path": "pipeline/pj_escalate.py", "line": 261},
        {"path": "plugins/pj-buttons/pj-buttons/__init__.py", "line": 35}
      ],
      "obsolete": [                              # ce que l'artefact ne doit PLUS porter
        {"token": "👆", "reason": "…"}, {"token": "1b", "reason": "…"},
        {"token": "1c", "reason": "…"}
      ]
    }

Ce que le SCRIPT recalcule (jamais recopié du registre ni de la page) :

  - `prefix_len` = len(active_icon + " " + repo + "|#" + issue_number + "|") ;
  - `prefix_len_gear` = len("⚙️ " + repo + "|#" + issue_number + "|") ;
  - `title_budget` = title_max - prefix_len ;
  - `current_name_len` = prefix_len + len(issue_title) ;
  - `states`  = len(icons) ET le nombre de lignes rendues portant une icône d'état ;
  - `readers` = le nombre de sites DÉCLARÉS qui existent réellement dans l'arbre ET
    portent un appel `re.` à la ligne citée (±2) — un lecteur cité ne se déduit pas ;
  - `obsolete` = les `token` du registre RÉELLEMENT présents dans la page hors registre ;
  - inertie = aucun `<script src>`, `<link>`, `<img>`, `<iframe>`, `@import`, `url(http`.

Le script confronte AUSSI les nombres ÉCRITS DANS LA PROSE (la page ratifiée les porte —
les supprimer rend le banc rouge, c'est voulu) :

    fait (<strong>N</strong>) car.                       -> prefix_len
    (N avec ⚙️)                                          -> prefix_len_gear
    (<strong>N</strong> caractères de titre)             -> title_budget
    nom de (N)                                           -> current_name_len
    (N états)                                            -> states (4)

Les chiffres de PROSE sont confrontés sur la page **registre et styles retirés** : le CSS
est l'endroit d'un faux positif de couleur (`#1b2a3c` contient « 1b »), pas d'un total.

Codes de sortie du script :

    0  concordance : totaux recalculés == registre == prose, 4 états rendus, 3 lecteurs
       vérifiés, 0 marqueur obsolète, page inerte ;
    1  écart : une ligne par champ divergent, NOMMANT le champ ET les deux nombres
       (déclaré/mesuré) — et une ligne par marqueur obsolète ou asset réseau trouvé,
       nommant le token/attribut fautif. Aucun verdict positif n'est écrit ;
    2  erreur d'usage : page introuvable, registre `issue19-ledger` absent ou illisible,
       registre d'une autre issue.

`--json` écrit sur stdout un objet :

    {"plate": …, "verdict": "concordance"|"ecart", "states": 4, "prefix_len": 22,
     "prefix_len_gear": 23, "title_budget": 78, "current_name_len": 65, "readers": 3,
     "title_max": 100, "obsolete": [], "ecarts": []}

Le script est **pur** : aucun réseau, aucun fichier écrit, aucune dépendance externe. La
page est **inerte** : aucun asset distant, aucune police, aucun CDN (un lien `<a href>`
vers l'issue est une ancre, pas un chargement — il reste licite).
"""
import html
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
CONTEXT = REPO / "docs" / "architecture" / "context"
PLATE = CONTEXT / "issue-19-maquette.html"
MEASURE = CONTEXT / "issue-19-maquette.measure.py"

LEDGER_ID = "issue19-ledger"
LEDGER_RE = re.compile(
    r"<script[^>]*id=[\"']" + LEDGER_ID + r"[\"'][^>]*>(?P<json>.*?)</script>", re.S | re.I
)

# --- valeurs RATIFIÉES par le cadrage #19 (gelées : jamais dérivées de la page) ---------
#
# 4 états : Q3 = d (🎬 démarrage / ⚙️ in progress / ⚠ bloqué / 🛑 terminé), nommés par
# l'humain — le 👆 des options a/b est PÉRIMÉ.
# 22  = len("🎬 hermes-workflow|#19|") ; 23 = la même chose avec ⚙️ (2 points de code).
# 78  = 100 - 22 (borne Discord d'un nom de thread : 1–100 car.).
# 65  = 22 + 43, le titre de l'issue #19 faisant 43 caractères.
# 3   = les 3 sites qui résolvent un thread par son NOM, mesurés sur le worktree.
RATIFIES = {
    "issue": 19,
    "repo": "hermes-workflow",
    "issue_number": 19,
    "issue_title": "Discord thread title and description update",
    "title_max": 100,
    "states": 4,
    "prefix_len": 22,
    "prefix_len_gear": 23,
    "title_budget": 78,
    "current_name_len": 65,
    "readers": 3,
}

PREFIX_ACTIF = "🎬 hermes-workflow|#19|"
IDENTITE = "hermes-workflow|#19|"

# Les 3 lecteurs cités par la page, avec la ligne où leur motif vit réellement.
LECTEURS_CITES = (
    ("pipeline/engine.py", 77),
    ("pipeline/pj_escalate.py", 261),
    ("plugins/pj-buttons/pj-buttons/__init__.py", 35),
)

# Marqueurs d'un format PÉRIMÉ : l'artefact ne doit plus les porter (arbitrage rendu).
OBSOLETES = ("👆", "1b", "1c")

# Motifs de la PROSE portant les totaux ratifiés (la page doit les écrire).
PROSE = {
    "prefix_len": re.compile(r"fait\s*<strong>(\d+)</strong>\s*car\."),
    "prefix_len_gear": re.compile(r"\((\d+)\s*avec\s*⚙️"),
    "title_budget": re.compile(r"<strong>(\d+)\s*caractères de titre</strong>"),
    "current_name_len": re.compile(r"nom de\s*(?:<strong>)?(\d+)"),
    "states": re.compile(r"\((\d+)\s*états\)"),
}


# --------------------------------------------------------------------------- outils

def _plate_text(path=None):
    """Texte de la page — échoue en NOMMANT le fichier absent (jamais un vert par défaut)."""
    p = Path(path) if path else PLATE
    if not p.is_file():
        pytest.fail(
            f"page de la maquette absente : {p} — le RED ne peut pas porter sur une page "
            f"qui n'existe pas. Si l'arbitrage retient un autre chemin, changer PLATE."
        )
    return p.read_text(encoding="utf-8")


def _measure_exists():
    if not MEASURE.is_file():
        pytest.fail(
            f"script de mesure absent : {MEASURE} — le banc exige un script VERSIONNÉ, pas "
            f"une commande reconstruite à la main. Si l'arbitrage retient un autre chemin, "
            f"changer MEASURE."
        )


def _run(*args, plate=None, json_out=False):
    """Exécute le script de mesure ; `plate` explicite pour mesurer des copies mutées."""
    _measure_exists()
    cmd = [sys.executable, str(MEASURE)]
    if plate is not None:
        cmd += ["--plate", str(plate)]
    if json_out:
        cmd += ["--json"]
    cmd += list(args)
    return subprocess.run(cmd, capture_output=True, text=True, cwd=str(REPO))


def _ledger_of(path=None):
    txt = _plate_text(path)
    m = LEDGER_RE.search(txt)
    assert m, (
        f"aucun registre machine `<script type=\"application/json\" id=\"{LEDGER_ID}\">` "
        f"dans {path or PLATE} : la page ne porte pas les totaux que le script doit "
        f"reproduire."
    )
    try:
        reg = json.loads(m.group("json"))
    except json.JSONDecodeError as exc:
        pytest.fail(f"registre {LEDGER_ID} illisible ({exc})")
    assert reg.get("issue") == 19, f"registre d'une autre issue : {reg.get('issue')!r}"
    return reg


def _corps_hors_registre(txt):
    """La page SANS son registre machine : seul endroit où un rendu se voit."""
    return LEDGER_RE.sub("", txt)


def _prose(txt):
    """La page telle que l'HUMAIN la lit, jugée hors blocs MACHINE.

    Deux retraits, chacun MESURÉ :
    1. le registre `issue19-ledger` — il déclare les totaux, il ne les rend pas : le lire
       pour vérifier un rendu serait tautologique ;
    2. les blocs `<style>` — c'est là que vit le faux positif de COULEUR : `#1b2a3c`
       contient « 1b » et ferait refuser une page pourtant saine. Les balises
       structurelles restent (les motifs de prose cherchent `<strong>`).
    """
    sans_machine = LEDGER_RE.sub(" ", txt)
    sans_style = re.sub(r"<style\b.*?</style>", " ", sans_machine, flags=re.S | re.I)
    sans_comment = re.sub(r"<!--.*?-->", " ", sans_style, flags=re.S)
    return html.unescape(sans_comment)


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


def _casse_registre(plate_path):
    """Rend le contenu du registre NON-JSON : la page est intègre, le registre est cassé."""
    txt = Path(plate_path).read_text(encoding="utf-8")
    m = LEDGER_RE.search(txt)
    assert m, "copie sans registre : casser le registre est impossible"
    Path(plate_path).write_text(
        txt[:m.start("json")] + "{ ceci n'est pas du JSON" + txt[m.end("json"):],
        encoding="utf-8")


def _report(res):
    """Rapport `--json`, ou échec nommant la sortie brute."""
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


def _totaux(reg):
    """Le sextuplet gelé d'un registre — comparé, jamais recopié champ à champ."""
    return (
        reg.get("states"),
        reg.get("prefix_len"),
        reg.get("prefix_len_gear"),
        reg.get("title_budget"),
        reg.get("current_name_len"),
        len(reg.get("readers") or []),
    )


GELES = (
    RATIFIES["states"],
    RATIFIES["prefix_len"],
    RATIFIES["prefix_len_gear"],
    RATIFIES["title_budget"],
    RATIFIES["current_name_len"],
    RATIFIES["readers"],
)


def _tronque(prefix, titre, borne=100):
    """La coupe documentée : l'identité `repo|#n` précède TOUJOURS le titre."""
    return (prefix + titre)[:borne]


# ==========================================================================
# A. NOMINAL — le banc reproduit la maquette soumise au gate humain
# ==========================================================================

def test_nominal_le_script_sort_exit_0_et_les_totaux_sont_ceux_du_cadrage():
    """NOMINAL — 1er scénario : le script sort 0 et reproduit les 4 totaux ratifiés.

    Les valeurs attendues sont GELÉES ici (cadrage #19), jamais lues dans la page : un
    registre réécrit pour se déclarer cohérent avec sa propre page ne peut pas faire
    passer ce cas.
    """
    res = _run()
    assert res.returncode == 0, (
        f"le script de mesure doit sortir 0 sur la page du dépôt ; rc={res.returncode}\n"
        f"stdout:\n{res.stdout}\nstderr:\n{res.stderr}"
    )
    _assert_nomme(res, "concordance")
    rep = _report(_run(json_out=True))
    assert rep.get("verdict") == "concordance", f"verdict attendu « concordance » : {rep}"
    mesure = (
        rep.get("states"),
        rep.get("prefix_len"),
        rep.get("prefix_len_gear"),
        rep.get("title_budget"),
        rep.get("current_name_len"),
        rep.get("readers"),
    )
    assert mesure == GELES, (
        f"totaux mesurés {mesure} ≠ ratifiés {GELES} "
        f"(états, préfixe, préfixe ⚙️, budget de titre, nom actuel, lecteurs)"
    )
    assert rep.get("title_max") == RATIFIES["title_max"], (
        f"borne Discord attendue {RATIFIES['title_max']} : {rep.get('title_max')!r}"
    )
    assert not rep.get("ecarts"), f"aucun écart attendu : {rep.get('ecarts')}"


def test_nominal_la_page_porte_les_4_etats_au_format_arbitre():
    """NOMINAL — la page rend les 4 états de Q3, l'identité en tête et le budget de titre."""
    corps = _corps_hors_registre(_plate_text())
    prose = _prose(_plate_text())
    reg = _ledger_of()

    # (1) le registre déclare EXACTEMENT les totaux ratifiés
    assert _totaux(reg) == GELES, (
        f"registre {_totaux(reg)} ≠ ratifiés {GELES} : le registre documente un autre format"
    )
    assert reg.get("icons") == ["🎬", "⚙️", "⚠", "🛑"], (
        f"les 4 états nommés par l'humain (Q3 = d) doivent être déclarés : {reg.get('icons')!r}"
    )
    assert reg.get("active_icon") == "🎬", (
        f"l'état de création du fil est 🎬 : {reg.get('active_icon')!r}"
    )

    # (2) les 4 icônes sont RENDUES hors registre, avec l'identité `repo|#n|`
    for icone in ("🎬", "⚙️", "⚠", "🛑"):
        assert f"{icone} {IDENTITE}" in corps, (
            f"l'état {icone} n'est pas RENDU sous la forme « {icone} {IDENTITE}<titre> » "
            f"dans la page (un état seulement déclaré au registre n'est pas reproduit)"
        )

    # (3) les longueurs ratifiées sont MESURABLES, jamais recopiées du registre
    for icone, attendu in (("🎬", RATIFIES["prefix_len"]),
                           ("⚙️", RATIFIES["prefix_len_gear"])):
        mesure = len(f"{icone} {IDENTITE}")
        assert mesure == attendu, (
            f"préfixe « {icone} {IDENTITE} » : {mesure} caractères, {attendu} ratifiés"
        )
    assert RATIFIES["title_budget"] == RATIFIES["title_max"] - RATIFIES["prefix_len"], (
        "le budget de titre ratifié doit valoir borne Discord - longueur du préfixe"
    )
    assert len(RATIFIES["issue_title"]) + RATIFIES["prefix_len"] == RATIFIES["current_name_len"], (
        "le nom actuel ratifié doit valoir préfixe + titre de l'issue"
    )
    assert RATIFIES["issue_title"] in corps, (
        "la page doit RENDRE le titre de l'issue (#19) sous son nom actuel"
    )

    # (4) la prose porte les totaux (`<strong>22</strong> car.`, `(78 caractères de titre)`…)
    for champ, motif in PROSE.items():
        m = motif.search(prose)
        assert m, (
            f"la page ne porte plus le total « {champ} » dans sa prose (motif "
            f"{motif.pattern!r}) — un chiffre non écrit ne se mesure pas"
        )
        assert int(m.group(1)) == RATIFIES[champ], (
            f"prose {champ} = {m.group(1)}, ratifié {RATIFIES[champ]}"
        )


def test_nominal_la_page_est_inerte_et_cite_les_3_lecteurs_du_nom():
    """NOMINAL — page inerte (0 asset distant) et les 3 lecteurs cités existent vraiment."""
    corps = _corps_hors_registre(_plate_text())
    reg = _ledger_of()

    # (1) inertie : aucun chargement réseau, aucun composant exécutable
    for motif in ("<link", "<img", "<iframe", "@import", "url(http", "url('http"):
        assert motif not in corps, f"page inerte exigée : « {motif} » trouvé dans la page"
    assert not re.search(r"<script\b[^>]*\bsrc\s*=", corps, re.I), (
        "aucun `<script src=…>` : la page ne charge rien du réseau"
    )
    executables = [
        m.group(0) for m in re.finditer(r"<script\b[^>]*>", corps, re.I)
        if "application/json" not in m.group(0).lower()
    ]
    assert not executables, (
        f"la page ne doit porter AUCUN script exécutable (le registre JSON est le seul "
        f"`<script>` licite) : {executables}"
    )

    # (2) les 3 lecteurs sont cités ET vérifiés sur l'arbre
    lecteurs = reg.get("readers") or []
    assert len(lecteurs) == RATIFIES["readers"], (
        f"{RATIFIES['readers']} lecteurs attendus au registre : {lecteurs!r}"
    )
    for path, ligne in LECTEURS_CITES:
        assert path in corps, (
            f"le lecteur {path} n'est pas NOMMÉ dans la page (§3, non-régression)"
        )
        assert any((r.get("path") == path) for r in lecteurs), (
            f"le lecteur {path} n'est pas déclaré au registre"
        )
        f = REPO / path
        assert f.is_file(), f"lecteur cité par la page mais absent de l'arbre : {path}"
        lignes = f.read_text(encoding="utf-8").splitlines()
        fenetre = lignes[max(0, ligne - 3):ligne + 2]
        assert any("re." in l for l in fenetre), (
            f"{path}:{ligne} ne porte plus l'appel de résolution attendu dans les lignes "
            f"{max(1, ligne - 2)}..{ligne + 2} : {fenetre}"
        )


def test_nominal_la_page_ne_porte_aucun_format_obsolete():
    """NOMINAL — l'artefact ne remet en scène NI la comparaison 1a/1b/1c NI l'état 👆."""
    prose = _prose(_plate_text())
    trouves = []
    for tok in OBSOLETES:
        if re.search(r"(?<![0-9A-Za-z])" + re.escape(tok) + r"(?![0-9A-Za-z])", prose):
            trouves.append(tok)
    assert not trouves, (
        f"la page porte encore un format PÉRIMÉ : {trouves} — l'arbitrage est rendu "
        f"(Q3 = d), la comparaison des formats candidats est morte et 👆 est remplacé par ⚠"
    )
    reg = _ledger_of()
    tokens = {o.get("token") for o in reg.get("obsolete") or []}
    for tok in OBSOLETES:
        assert tok in tokens, (
            f"le registre doit déclarer {tok!r} comme obsolète (c'est ce qui rend le refus "
            f"mésurable) : déclarés {sorted(t for t in tokens if t)}"
        )


# ==========================================================================
# B. LIMITE — un chiffre qui dérive est nommé, aucun verdict positif
# ==========================================================================

def test_limite_un_chiffre_du_registre_derive_est_nomme(tmp_path):
    """LIMITE — 2e scénario : un total du registre qui ne correspond plus fait échouer."""
    copie = _copie(tmp_path, "registre-derive.html")
    _rewrite_ledger(copie, lambda r: r.__setitem__("prefix_len", 21))

    res = _run(plate=copie)
    blob = (res.stdout or "") + (res.stderr or "")
    assert res.returncode == 1, (
        f"un total de registre qui ne correspond plus doit sortir 1 ; rc={res.returncode}\n"
        f"stdout:\n{res.stdout}\nstderr:\n{res.stderr}"
    )
    _assert_nomme(res, "prefix_len")
    assert "21" in blob and "22" in blob, (
        "la ligne d'écart doit porter les DEUX nombres (déclaré 21 / mesuré 22) :\n" + blob
    )
    assert "concordance" not in blob, "aucun verdict positif ne doit être écrit en écart"


def test_limite_un_chiffre_de_la_prose_derive_est_nomme(tmp_path):
    """LIMITE — la dérive porte sur la PROSE : le script la confronte aussi, et la nomme."""
    copie = _copie(tmp_path, "prose-derive.html")
    txt = copie.read_text(encoding="utf-8")
    assert "<strong>78 caractères de titre</strong>" in txt, (
        "la page de référence doit porter le budget de titre en prose pour que la mutation "
        "soit fidèle"
    )
    copie.write_text(txt.replace("<strong>78 caractères de titre</strong>",
                                 "<strong>79 caractères de titre</strong>", 1),
                     encoding="utf-8")

    res = _run(plate=copie)
    blob = (res.stdout or "") + (res.stderr or "")
    assert res.returncode == 1, (
        f"un total de prose qui ne correspond plus doit sortir 1 ; rc={res.returncode}\n"
        f"stdout:\n{res.stdout}\nstderr:\n{res.stderr}"
    )
    _assert_nomme(res, "title_budget")
    assert "79" in blob and "78" in blob, (
        "la ligne d'écart doit porter les DEUX nombres (écrit 79 / mesuré 78) :\n" + blob
    )
    assert "concordance" not in blob, "aucun verdict positif ne doit être écrit en écart"


def test_limite_un_titre_a_la_borne_ne_coupe_jamais_l_identite():
    """LIMITE — 3e scénario : un titre à la borne Discord (100 car.) ne coupe pas `repo|#n`.

    La coupe éventuelle porte sur la FIN DU TITRE : l'identité `hermes-workflow|#19|` reste
    en tête, sinon la résolution du thread (3 lecteurs de §3) serait cassée par le nom
    lui-même. La page doit ÉCRIRE la règle (« jamais le préfixe »), pas seulement la
    respecter.
    """
    prose = _prose(_plate_text())
    assert "jamais le préfixe" in prose, (
        "la page doit ÉCRIRE la règle de coupe : ce qui est tronqué n'est jamais le préfixe"
    )
    assert RATIFIES["prefix_len"] + RATIFIES["title_budget"] == RATIFIES["title_max"], (
        "le budget de titre doit couvrir exactement la place laissée par le préfixe"
    )

    # mesure pure : un titre qui DÉBORDE la borne donne un nom de 100 caractères dont
    # l'identité est intacte, et dont la coupe n'a mordu que la fin du titre.
    titre_long = "Discord thread title and description update " + "x" * 120
    nom = _tronque(PREFIX_ACTIF, titre_long, RATIFIES["title_max"])
    assert len(nom) == RATIFIES["title_max"], f"le nom doit être coupé à 100 : {len(nom)}"
    assert nom.startswith(PREFIX_ACTIF), (
        f"l'identité doit rester en TÊTE du nom tronqué : {nom[:40]!r}"
    )
    assert nom[len(PREFIX_ACTIF):] == titre_long[:RATIFIES["title_budget"]], (
        "la coupe doit porter sur la FIN du titre, jamais déplacer l'identité"
    )
    assert len(nom) > RATIFIES["prefix_len"], "un nom tronqué reste plus long que son préfixe"


# ==========================================================================
# C. ERREUR — une maquette montrant un format obsolète est refusée
# ==========================================================================

def test_erreur_la_comparaison_des_3_formats_candidats_est_refusee(tmp_path):
    """ERREUR — 3e scénario : remettre la comparaison 1a/1b/1c fait refuser le banc."""
    copie = _copie(tmp_path, "comparaison-obsolete.html")
    txt = copie.read_text(encoding="utf-8")
    bloc = (
        "<section><h2>Comparaison des formats candidats</h2>"
        "<table><tr><td>1a</td><td>format retenu</td></tr>"
        "<tr><td>1b</td><td>hermes-workflow #19 · titre</td></tr>"
        "<tr><td>1c</td><td>running - issue 19 titre</td></tr></table></section>"
    )
    assert "</body>" in txt or "</html>" in txt, "la page doit être un document HTML complet"
    ancre = "</body>" if "</body>" in txt else "</html>"
    copie.write_text(txt.replace(ancre, bloc + ancre, 1), encoding="utf-8")

    res = _run(plate=copie)
    blob = (res.stdout or "") + (res.stderr or "")
    assert res.returncode != 0, (
        f"un format obsolète doit être REFUSÉ ; rc={res.returncode}\n{blob}"
    )
    _assert_nomme(res, "1b", "1c")
    assert "obsolète" in blob or "obsolete" in blob, (
        "le refus doit nommer la NATURE du défaut (format obsolète) :\n" + blob
    )
    assert "concordance" not in blob, "aucun verdict positif ne doit être écrit en refus"


def test_erreur_l_etat_obsolete_humain_requis_est_refuse(tmp_path):
    """ERREUR — l'état 👆 des options a/b est PÉRIMÉ : sa présence fait refuser la page."""
    copie = _copie(tmp_path, "etat-obsolete.html")
    txt = copie.read_text(encoding="utf-8")
    ancre = "</body>" if "</body>" in txt else "</html>"
    copie.write_text(txt.replace(
        ancre,
        '<div class="row">👆 hermes-workflow|#19|en attente de l\'humain</div>' + ancre, 1),
        encoding="utf-8")

    res = _run(plate=copie)
    blob = (res.stdout or "") + (res.stderr or "")
    assert res.returncode != 0, f"un état obsolète doit être refusé ; rc={res.returncode}\n{blob}"
    _assert_nomme(res, "👆")
    assert "concordance" not in blob, "aucun verdict positif ne doit être écrit en refus"


def test_erreur_un_asset_reseau_dans_la_page_est_refuse(tmp_path):
    """ERREUR — charger un asset distant casse l'inertie exigée : la page est refusée."""
    copie = _copie(tmp_path, "avec-asset.html")
    txt = copie.read_text(encoding="utf-8")
    ancre = "</head>" if "</head>" in txt else "</html>"
    copie.write_text(txt.replace(
        ancre, '<link rel="stylesheet" href="https://cdn.example/x.css">' + ancre, 1),
        encoding="utf-8")

    res = _run(plate=copie)
    blob = (res.stdout or "") + (res.stderr or "")
    assert res.returncode == 1, (
        f"un asset réseau doit faire échouer la mesure (1) ; rc={res.returncode}\n{blob}"
    )
    _assert_nomme(res, "<link")
    assert "concordance" not in blob, "aucun verdict positif ne doit être écrit en refus"


def test_erreur_les_degradations_d_usage_sortent_2_en_nommant_la_cause(tmp_path):
    """ERREUR — page introuvable, registre absent, registre illisible, registre d'une autre
    issue : quatre erreurs d'usage, quatre messages qui NOMMENT la cause (jamais un vert)."""
    # (1) page introuvable
    res = _run(plate=tmp_path / "introuvable.html")
    assert res.returncode == 2, f"page introuvable : rc=2 attendu, obtenu {res.returncode}"
    _assert_nomme(res, "introuvable")

    # (2) page sans registre
    sans = _copie(tmp_path, "sans-registre.html")
    sans.write_text(LEDGER_RE.sub("", sans.read_text(encoding="utf-8")), encoding="utf-8")
    res = _run(plate=sans)
    assert res.returncode == 2, f"registre absent : rc=2 attendu, obtenu {res.returncode}"
    _assert_nomme(res, LEDGER_ID)

    # (3) registre illisible
    casse = _copie(tmp_path, "registre-casse.html")
    _casse_registre(casse)
    res = _run(plate=casse)
    assert res.returncode == 2, f"registre illisible : rc=2 attendu, obtenu {res.returncode}"
    _assert_nomme(res, "illisible")

    # (4) registre d'une autre issue
    autre = _copie(tmp_path, "autre-issue.html")
    _rewrite_ledger(autre, lambda r: r.__setitem__("issue", 3))
    res = _run(plate=autre)
    assert res.returncode == 2, f"autre issue : rc=2 attendu, obtenu {res.returncode}"
    _assert_nomme(res, "autre issue")


# ==========================================================================
# D. Garde-fous du banc lui-même
# ==========================================================================

def test_erreur_la_mesure_est_pure_aucun_reseau():
    """ERREUR — garde-fou : le script de mesure ne doit ouvrir aucun accès réseau."""
    _measure_exists()
    src = MEASURE.read_text(encoding="utf-8")
    for interdit in ("import requests", "import urllib", "from urllib", "import socket",
                     "http.client", "import httpx"):
        assert interdit not in src, (
            f"la mesure est PURE (aucun réseau) : `{interdit}` trouvé dans {MEASURE.name}"
        )
