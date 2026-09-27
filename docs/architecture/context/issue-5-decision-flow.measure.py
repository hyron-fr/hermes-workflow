#!/usr/bin/env python3
"""issue-5-decision-flow.measure.py — reproduit les empreintes des artefacts ratifiés (#5).

Le sujet mesuré est la **page des artefacts** `issue-5-decision-flow.html`, voisine de ce
script. Elle **matérialise** les artefacts déjà ratifiés par t3 — diagramme de séquence V2 +
maquette de texte inerte en 2 messages — elle n'en produit aucun nouveau.

Règle centrale de la mesure : **l'artefact est mesuré là où il est RENDU, jamais là où il est
déclaré.** Le **registre machine** de la page (`<script type="application/json"
id="decision-flow-ledger">`) déclare l'attendu ; la page rendue porte le mesuré :

    PNG  <img data-artefact="<name>" … src="data:image/png;base64,…">
    texte <pre data-artefact="<name>">…</pre>   (contenu verbatim de l'artefact, échappé HTML)

Le script confronte rendu ↔ déclaré. S'il comparait la charge déclarée à elle-même, une
retouche de la partie rendue passerait inaperçue : c'est exactement le 2ᵉ scénario du contrat
(« un artefact retouché à la main fait échouer le banc »), qui doit rester satisfiable.

Usage :
    issue-5-decision-flow.measure.py [--plate PATH] [--json]

Codes de sortie :
    0  concordance : les 3 artefacts rendus reproduisent leurs empreintes déclarées, la page
       porte 3 phases rendues et 0 composant interactif ;
    1  écart : une ligne par artefact dérivé (nommant son `name`, l'empreinte déclarée ET
       l'empreinte mesurée), une ligne par composant interactif trouvé, et le refus d'un
       artefact rendu dont l'empreinte est déclarée **obsolète** — en nommant sa provenance
       (le message Discord d'origine) ;
    2  erreur d'usage : page introuvable, registre `decision-flow-ledger` absent ou illisible,
       artefact déclaré non RENDU dans la page.

Le script est **pur** : aucun accès réseau, aucun fichier écrit (il mesure, il ne produit rien).

Les artefacts **v1** sont obsolètes et interdits comme état courant : le diagramme Discord
`1551168046050054157` (boutons « Débloquer / Abandonner ») et la maquette
`1551167343504396362` (2 boutons désactivés). Le design ratifié n'a **plus aucun** bouton.
"""
import argparse
import base64
import hashlib
import html
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_PLATE = HERE / "issue-5-decision-flow.html"

EXPECTED_ISSUE = 5
LEDGER_ID = "decision-flow-ledger"
LEDGER_RE = re.compile(
    r"<script[^>]*id=[\"']" + LEDGER_ID + r"[\"'][^>]*>(?P<json>.*?)</script>", re.S | re.I)

PHASES_IDS = ["creation", "decision", "re-blocage"]

# Composants interactifs interdits : le design ratifié n'a plus aucune interaction par
# bouton. Chaque motif est nommé pour que l'écart soit lisible, pas un booléen. La garde
# porte sur la STRUCTURE (élément ou attribut), jamais sur la prose : nommer `pj:unblock`
# dans la narration d'une provenance obsolète est légitime — le 3ᵉ scénario l'exige.
INTERACTIFS = (
    (re.compile(r"<\s*button\b", re.I), "composant interactif `<button>`"),
    (re.compile(r"<\s*select\b", re.I), "composant interactif `<select>`"),
    (re.compile(r"\bcustom_id\s*=\s*[\"']", re.I), "composant interactif `custom_id`"),
)


def sha256(payload):
    return hashlib.sha256(payload).hexdigest()


def corps_hors_registre(txt):
    """La page SANS le registre machine : seul endroit où un composant RENDU se voit."""
    return LEDGER_RE.sub("", txt)


def rendu(txt, name, kind):
    """Octets de l'artefact RENDU sous `data-artefact="<name>"`, ou None s'il n'est pas rendu."""
    if kind == "png":
        m = re.search(r"<img\b[^>]*\bdata-artefact=\"%s\"[^>]*>" % re.escape(name), txt, re.I)
        if not m:
            return None
        s = re.search(r"\bsrc=\"(data:image/[a-z]+;base64,[^\"]*)\"", m.group(0), re.I)
        if not s:
            return None
        try:
            return base64.b64decode(s.group(1).split(",", 1)[1])
        except Exception:                                       # base64 tronqué
            return None
    m = re.search(
        r"<pre\b[^>]*\bdata-artefact=\"%s\"[^>]*>(?P<inner>.*?)</pre>" % re.escape(name),
        txt, re.S | re.I)
    if not m:
        return None
    return html.unescape(m.group("inner")).encode("utf-8")


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="issue-5-decision-flow.measure.py",
        description="Reproduit les empreintes des artefacts rendus par la page (#5).")
    ap.add_argument("--plate", default=str(DEFAULT_PLATE),
                    help="page HTML portant le registre `%s`" % LEDGER_ID)
    ap.add_argument("--json", action="store_true", help="rapport machine-lisible sur stdout")
    try:
        args = ap.parse_args(argv)
    except SystemExit as exc:                       # argparse sort 2 sur usage invalide
        return int(exc.code or 0)

    # --- la page et son registre ------------------------------------------------------
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
        print("page d'une autre issue : registre issue=%r, attendu %r"
              % (reg.get("issue"), EXPECTED_ISSUE))
        return 2

    declares = [r for r in (reg.get("artefacts") or []) if isinstance(r, dict)]
    if not declares:
        print("registre `%s` sans artefact déclaré : rien à reproduire" % LEDGER_ID)
        return 2

    obsolete = [o for o in (reg.get("obsolete") or []) if isinstance(o, dict)]
    provenance = {}
    for o in obsolete:
        sha = (o.get("sha256") or "").strip().lower()
        if sha:
            provenance.setdefault(sha, o)

    # --- mesure du RENDU ---------------------------------------------------------------
    ecarts = []
    lignes = []
    non_rendus = []

    for rec in declares:
        name = rec.get("name")
        kind = rec.get("kind")
        brut = rendu(txt, name, kind)
        if brut is None:
            non_rendus.append(name)
            continue
        mesure = sha256(brut)
        declare = (rec.get("sha256") or "").strip().lower()

        o = provenance.get(mesure) or provenance.get(declare)
        if o:
            ecarts.append(
                "artefact `%s` REFUSÉ : son empreinte %s est déclarée OBSOLÈTE "
                "(provenance Discord %s — %s)"
                % (name, mesure[:16], o.get("discord_message"),
                   o.get("reason") or o.get("raison") or "design v1"))
        if declare != mesure:
            ecarts.append("artefact `%s` : empreinte déclarée %s ≠ empreinte mesurée sur le "
                          "rendu %s (la page a dérivé de ce qu'elle déclare)"
                          % (name, declare[:16] or "absente", mesure[:16]))
        if rec.get("bytes") != len(brut):
            ecarts.append("artefact `%s` : taille déclarée %r ≠ %d octets rendus"
                          % (name, rec.get("bytes"), len(brut)))
        lignes.append("artefact `%s` (%s, %s) : %d octets, sha256 %s — source %s"
                      % (name, kind, "conforme" if declare == mesure else "DÉRIVÉ",
                         len(brut), mesure, rec.get("source") or rec.get("anchor") or "?"))

    if non_rendus:
        for name in non_rendus:
            print("MISSING %s : artefact déclaré au registre mais NON RENDU dans la page "
                  "(le mesuré est le rendu, pas la déclaration)" % name)
        print("%d artefact(s) déclaré(s) non rendu(s) — rien à mesurer" % len(non_rendus))
        return 2

    # --- phases du flux : déclarées ET rendues (hors registre) --------------------------
    corps = corps_hors_registre(txt)
    phases = [p for p in (reg.get("phases") or []) if isinstance(p, dict)]
    ids = [p.get("id") for p in phases]
    if ids != PHASES_IDS:
        ecarts.append("phases %r ≠ %r attendues" % (ids, PHASES_IDS))
    for p in phases:
        titre = (p.get("title") or "").strip()
        if not titre:
            ecarts.append("phase %r : titre vide" % p.get("id"))
        elif titre not in corps:
            ecarts.append("phase %r : le titre %r est déclaré au registre mais n'est PAS "
                          "rendu dans la page" % (p.get("id"), titre))

    # --- composants interactifs (le design figé n'en a plus aucun) ---------------------
    composants = 0
    for motif, libelle in INTERACTIFS:
        for trouve in motif.finditer(corps):
            composants += 1
            extrait = corps[max(0, trouve.start() - 25):trouve.end() + 25].replace("\n", " ")
            ecarts.append("%s présent dans la page : …%s…" % (libelle, extrait))

    report = {
        "plate": str(plate),
        "artefacts": lignes,
        "noms": sorted(r.get("name") or "" for r in declares),
        "phases": len(phases),
        "phases_ids": ids,
        "components": composants,
        "obsolete": [o.get("discord_message") for o in obsolete],
        "ecarts": ecarts,
        "verdict": "ecart" if ecarts else "concordance",
    }

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 1 if ecarts else 0

    print("page : %s" % plate)
    for ligne in lignes:
        print("  " + ligne)
    print("  phases : %d (%s) · composants interactifs : %d"
          % (len(phases), ", ".join(str(i) for i in ids), composants))
    if ecarts:
        for ecart in ecarts:
            print(ecart)
        print("%d écart(s) entre le rendu de la page et les artefacts qu'elle déclare "
              "— aucun verdict positif" % len(ecarts))
        return 1
    print("concordance : %d artefacts rendus / %d phases / %d composant interactif"
          % (len(declares), len(phases), composants))
    return 0


if __name__ == "__main__":
    sys.exit(main())
