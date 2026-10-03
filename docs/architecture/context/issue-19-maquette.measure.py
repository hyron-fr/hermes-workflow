#!/usr/bin/env python3
"""issue-19-maquette.measure.py — recalcule les totaux de la maquette #19.

Le sujet mesuré est la **page de cadrage** `issue-19-maquette.html`, voisine de ce
script. Elle **matérialise** dans le dépôt le format de titre/description déjà
**arbitré** par l'humain (fil Discord du ticket #19, arbitrage Q1=1a / Q2=2b / Q3=d) :
elle n'en produit aucun nouveau et ne redécide rien.

Règle centrale de la mesure : **un total annoncé est recalculé depuis le dispositif
réel, jamais recopié de la page.** Le **registre machine** de la page
(`<script type="application/json" id="issue19-ledger">`) déclare l'attendu ; le script
recalcule le mesuré et confronte les deux, y compris les nombres ÉCRITS DANS LA PROSE.

Ce que le script recalcule :

  - `prefix_len`       = len(active_icon + " " + repo + "|#" + issue + "|") ;
  - `prefix_len_gear`  = len("⚙️ " + repo + "|#" + issue + "|") ;
  - `title_budget`     = title_max - prefix_len (borne Discord d'un nom : 1–100) ;
  - `current_name_len` = prefix_len + len(issue_title) ;
  - `states`           = len(icons) ET le nombre d'états RENDUS dans la page ;
  - `readers`          = les sites DÉCLARÉS qui existent dans l'arbre ET portent un
                         appel `re.` à la ligne citée (±2) — un lecteur cité ne se
                         déduit pas, il se vérifie ;
  - `obsolete`         = les `token` du registre RÉELLEMENT présents dans la page
                         hors registre ;
  - inertie            = aucun `<script src>`, `<link>`, `<img>`, `<iframe>`,
                         `@import`, `url(http` — la page ne charge rien du réseau.

Usage :
    issue-19-maquette.measure.py [--plate PATH] [--json]

Codes de sortie :
    0  concordance : totaux recalculés == registre == prose, 4 états rendus, 3 lecteurs
       vérifiés, 0 marqueur obsolète, page inerte ;
    1  écart : une ligne par champ divergent NOMMANT le champ ET les deux nombres
       (déclaré/mesuré), une ligne par marqueur obsolète ou asset réseau trouvé ;
    2  erreur d'usage : page introuvable, registre `issue19-ledger` absent ou
       illisible, registre d'une autre issue.

Le script est **pur** : aucun accès réseau, aucun fichier écrit, aucun asset externe.
"""
import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_PLATE = HERE / "issue-19-maquette.html"
REPO_ROOT = HERE.parents[2]

LEDGER_ID = "issue19-ledger"
LEDGER_RE = re.compile(
    r"<script[^>]*id=[\"']" + LEDGER_ID + r"[\"'][^>]*>(?P<json>.*?)</script>", re.S | re.I
)
EXPECTED_ISSUE = 19
TITLE_MAX_DEFAULT = 100
GEAR = "\u2699\ufe0f"

# Les nombres ÉCRITS DANS LA PROSE — la page ratifiée les porte ; les supprimer rend la
# mesure rouge, c'est voulu (un chiffre non écrit ne se mesure pas).
PROSE = {
    "prefix_len": re.compile(r"fait\s*<strong>(\d+)</strong>\s*car\."),
    "prefix_len_gear": re.compile(r"\((\d+)\s*avec\s*" + GEAR),
    "title_budget": re.compile(r"<strong>(\d+)\s*caractères de titre</strong>"),
    "current_name_len": re.compile(r"nom de\s*>?\s*(\d+)"),
    "states": re.compile(r"\((\d+)\s*états\)"),
}

# Motifs d'un chargement réseau / d'un composant exécutable : la page est INERTE.
INERTIE = (
    ("<link", re.compile(r"<\s*link\b", re.I)),
    ("<img", re.compile(r"<\s*img\b", re.I)),
    ("<iframe", re.compile(r"<\s*iframe\b", re.I)),
    ("@import", re.compile(r"@import", re.I)),
    ("url(http", re.compile(r"url\(\s*['\"]?https?:", re.I)),
    ("<script src", re.compile(r"<\s*script\b[^>]*\bsrc\s*=", re.I)),
)


def corps_hors_registre(txt):
    """La page SANS son registre machine : seul endroit où un marqueur RENDU se voit."""
    return LEDGER_RE.sub("", txt)


def _champ(ecarts, nom, declare, mesure, source):
    """Ajoute une ligne d'écart NOMMANT le champ ET les deux nombres — ou rien."""
    if declare != mesure:
        ecarts.append(
            "champ `%s` : déclaré %r (%s) ≠ mesuré %r"
            % (nom, declare, source, mesure)
        )


def _prose(corps, champ, motif):
    """Valeur entière écrite dans la prose, ou None si le motif a disparu."""
    m = motif.search(corps)
    return int(m.group(1)) if m else None


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="issue-19-maquette.measure.py",
        description="Recalcule les totaux de la maquette #19 depuis le dispositif réel.")
    ap.add_argument("--plate", default=str(DEFAULT_PLATE),
                    help="page HTML portant le registre `%s`" % LEDGER_ID)
    ap.add_argument("--json", action="store_true", help="rapport machine-lisible sur stdout")
    try:
        args = ap.parse_args(argv)
    except SystemExit as exc:                       # argparse sort 2 sur usage invalide
        return int(exc.code or 0)

    plate = Path(args.plate).expanduser()
    if not plate.is_file():
        print("page introuvable : %s" % plate)
        return 2
    txt = plate.read_text(encoding="utf-8")

    m = LEDGER_RE.search(txt)
    if not m:
        print("aucun registre `%s` dans %s" % (LEDGER_ID, plate))
        return 2
    try:
        reg = json.loads(m.group("json"))
    except json.JSONDecodeError as exc:
        print("registre `%s` illisible dans %s : %s" % (LEDGER_ID, plate, exc))
        return 2
    if reg.get("issue") != EXPECTED_ISSUE:
        print("registre d'une autre issue dans %s : issue=%r, attendu %r"
              % (plate, reg.get("issue"), EXPECTED_ISSUE))
        return 2

    corps = corps_hors_registre(txt)

    # --- RECALCUL depuis les ingrédients déclarés (jamais depuis les totaux déclarés) ---
    active_icon = reg.get("active_icon") or ""
    icons = [i for i in (reg.get("icons") or []) if isinstance(i, str)]
    repo = reg.get("repo") or ""
    issue_number = reg.get("issue_number")
    issue_title = reg.get("issue_title") or ""
    title_max = reg.get("title_max")
    if not isinstance(title_max, int):
        title_max = TITLE_MAX_DEFAULT

    identite = "%s|#%s|" % (repo, issue_number)
    prefix_len = len("%s %s" % (active_icon, identite))
    prefix_len_gear = len("%s %s" % (GEAR, identite))
    title_budget = title_max - prefix_len
    current_name_len = prefix_len + len(issue_title)
    states = len(icons)

    ecarts = []

    # --- totaux du REGISTRE confrontés au recalcul ------------------------------------
    _champ(ecarts, "states", reg.get("states"), states, "registre")
    _champ(ecarts, "prefix_len", reg.get("prefix_len"), prefix_len, "registre")
    _champ(ecarts, "prefix_len_gear", reg.get("prefix_len_gear"), prefix_len_gear, "registre")
    _champ(ecarts, "title_budget", reg.get("title_budget"), title_budget, "registre")
    _champ(ecarts, "current_name_len", reg.get("current_name_len"), current_name_len, "registre")
    _champ(ecarts, "title_max", title_max, TITLE_MAX_DEFAULT, "registre")

    # --- totaux de la PROSE confrontés au recalcul ------------------------------------
    for champ, motif in PROSE.items():
        ecrit = _prose(corps, champ, motif)
        mesure = {"prefix_len": prefix_len, "prefix_len_gear": prefix_len_gear,
                  "title_budget": title_budget, "current_name_len": current_name_len,
                  "states": states}[champ]
        if ecrit is None:
            ecarts.append("champ `%s` : total absent de la prose (un chiffre non écrit "
                          "ne se mesure pas ; mesuré %r)" % (champ, mesure))
        elif ecrit != mesure:
            ecarts.append("champ `%s` : écrit %d dans la prose ≠ mesuré %d"
                          % (champ, ecrit, mesure))

    # --- les 4 états sont RENDUS, l'identité en tête ----------------------------------
    for icone in icons:
        if "%s %s" % (icone, identite) not in corps:
            ecarts.append("l'état `%s` n'est pas RENDU sous la forme « %s %s<titre> » "
                          "dans la page (déclaré au registre ≠ reproduit)"
                          % (icone, icone, identite))
    if not icons:
        ecarts.append("le registre ne déclare aucun état : rien à reproduire")

    # --- les lecteurs DÉCLARÉS existent et portent leur appel `re.` --------------------
    lecteurs = [r for r in (reg.get("readers") or []) if isinstance(r, dict)]
    verifies = 0
    for rec in lecteurs:
        chemin, ligne = rec.get("path"), rec.get("line")
        f = REPO_ROOT / str(chemin)
        if not f.is_file():
            ecarts.append("lecteur `%s` déclaré mais absent de l'arbre" % chemin)
            continue
        lignes = f.read_text(encoding="utf-8", errors="replace").splitlines()
        if not isinstance(ligne, int) or not (1 <= ligne <= len(lignes)):
            ecarts.append("lecteur `%s` : ligne %r hors bornes (1..%d)"
                          % (chemin, ligne, len(lignes)))
            continue
        fenetre = lignes[max(0, ligne - 3):ligne + 2]
        if any("re." in l for l in fenetre):
            verifies += 1
        else:
            ecarts.append("lecteur `%s`:%d ne porte plus d'appel `re.` dans les lignes "
                          "%d..%d" % (chemin, ligne, max(1, ligne - 2), ligne + 2))
    if not lecteurs:
        ecarts.append("le registre ne déclare aucun lecteur du nom")

    # --- marqueurs OBSOLÈTES rendus (hors registre) ------------------------------------
    trouves = []
    for o in (reg.get("obsolete") or []):
        token = (o or {}).get("token")
        if not token:
            continue
        # Un token alphanumérique se juge en frontière de mot (`1b` ≠ `11b`) ; un
        # emoji n'a pas de frontière de mot : il se cherche en sous-chaîne littérale.
        if token.isascii() and token.isalnum():
            vu = bool(re.search(r"(?<![0-9a-f])%s\b" % re.escape(token), corps))
        else:
            vu = token in corps
        if vu:
            trouves.append(token)
            ecarts.append("marqueur OBSOLÈTE `%s` rendu dans la page (%s) — l'arbitrage "
                          "est rendu, ce format est mort"
                          % (token, (o.get("reason") or "périmé")))
    if not reg.get("obsolete"):
        ecarts.append("le registre ne déclare aucun marqueur obsolète")

    # --- INERTIE : aucun asset réseau, aucun script exécutable -------------------------
    for libelle, motif in INERTIE:
        if motif.search(corps):
            ecarts.append("asset réseau « %s » présent dans la page : la maquette est "
                          "INERTE (aucun CDN, aucune police, aucun chargement distant)"
                          % libelle)
    for mm in re.finditer(r"<script\b[^>]*>", corps, re.I):
        if "application/json" not in mm.group(0).lower():
            ecarts.append("script exécutable `%s` dans la page : le seul `<script>` "
                          "licite est le registre JSON" % mm.group(0).strip())

    report = {
        "plate": str(plate),
        "verdict": "ecart" if ecarts else "concordance",
        "states": states,
        "prefix_len": prefix_len,
        "prefix_len_gear": prefix_len_gear,
        "title_budget": title_budget,
        "current_name_len": current_name_len,
        "readers": verifies,
        "title_max": title_max,
        "obsolete": trouves,
        "ecarts": ecarts,
    }

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 1 if ecarts else 0

    print("page : %s" % plate)
    print("  états rendus : %d (%s) · préfixe %d car. (%d avec %s) · budget de titre %d · "
          "nom actuel %d" % (states, ", ".join(icons), prefix_len, prefix_len_gear, GEAR,
                             title_budget, current_name_len))
    print("  lecteurs du nom vérifiés : %d/%d · marqueurs obsolètes rendus : %d"
          % (verifies, len(lecteurs), len(trouves)))
    if ecarts:
        for ecart in ecarts:
            print("  " + ecart)
        print("%d écart(s) entre les totaux annoncés et le dispositif réel — aucun verdict "
              "positif" % len(ecarts))
        return 1
    print("  concordance : %d états rendus / %d lecteurs vérifiés / %d marqueur obsolète / "
          "page inerte" % (states, verifies, len(trouves)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
