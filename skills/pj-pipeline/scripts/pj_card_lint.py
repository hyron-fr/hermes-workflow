#!/usr/bin/env python3
"""pj-card-lint — vérifie la conformité des cartes kanban au format pj (0 LLM).

Contrôles par carte (body) :
  1. les 5 sections obligatoires, dans l'ordre : Contexte & Objectif ; Critères
     d'acceptation ; DoR & DoD ; Considérations techniques ; Hors-scope
  2. bloc Gherkin : « Fonctionnalité/Feature: » + ≥2 « Scénario: » (nominal + limite/erreur)
     avec ≥3 étapes Étant donné/Quand/Alors
  3. DoR ET DoD présents
  4. garde-fous : au moins un interdit explicite
  5. INVEST dimensionnel : signaux de dépassement (nb de fichiers cités, formulations
     « refonte complète / tout le projet », body très long) sans découpage explicite

Usage :
  pj_card_lint.py --board pj-<repo> [--all | --task <id>] [--status todo,ready]

Sortie : une ligne par carte non conforme (stdout vide = conforme → tick muet).
Code de retour : 0 conforme, 1 non conforme, 2 erreur d'exécution.

Exclusions : cartes de process (t1..t6), racine importée du pont (« Importé depuis »),
cartes done/archivées — elles ne portent pas ce contrat.
"""

import argparse
import json
import os
import re
import subprocess
import sys

HERMES_BIN = os.environ.get("PJ_HERMES_BIN") or os.path.expanduser(
    "~/.hermes/hermes-agent/venv/bin/hermes")

SECTION_PATTERNS = [
    ("Contexte & Objectif", re.compile(r"^\s*#*\s*(?:\d\.\s*)?(?:contexte|context)\s*&\s*objectif", re.I | re.M)),
    ("Critères d'acceptation", re.compile(r"^\s*#*\s*(?:\d\.\s*)?crit[eè]res\s+d'acceptation", re.I | re.M)),
    ("DoR & DoD", re.compile(r"^\s*#*\s*(?:\d\.\s*)?DoR\s*&\s*DoD", re.I | re.M)),
    ("Considérations techniques", re.compile(r"^\s*#*\s*(?:\d\.\s*)?consid[eé]rations\s+techniques", re.I | re.M)),
    ("Hors-scope", re.compile(r"^\s*#*\s*(?:\d\.\s*)?hors[-\s]?scope", re.I | re.M)),
]
GHERKIN_FEATURE = re.compile(r"^\s*#*\s*(fonctionnalit[eé]|feature)\s*:", re.I | re.M)
GHERKIN_SCENARIO = re.compile(r"^\s*#*\s*(sc[eé]nario|scenario|exemple|example)\s*:", re.I | re.M)
GHERKIN_STEPS = re.compile(r"^\s*#*\s*(étant donn[eé]|etant donne|quand|alors|given|when|then)\b", re.I | re.M)
DOR = re.compile(r"\bDoR\b|definition of ready|d[eé]finition of ready", re.I)
DOD = re.compile(r"\bDoD\b|definition of done|d[eé]finition of done", re.I)
GUARDRAIL = re.compile(r"\b(interdit|ne pas|jamais|pas de |no |forbidden|must not|garde[-\s]?fou)", re.I)
INVEST_SPLIT = re.compile(r"\binvest\b|\bslice\b|\bsous[-\s]carte|\bd[eé]coup", re.I)
BLOAT = re.compile(r"\b(refonte compl[eè]te|r[eé][eé]criture globale|tout le projet|complet du "
                   r"module|migration totale)\b", re.I)
FILE_MENTION = re.compile(r"\b[\w./-]+\.(py|ts|tsx|js|jsx|json|ya?ml|toml|md|sh|css|html)\b")


def sh(args, timeout=90):
    env = dict(os.environ)
    env["PATH"] = os.path.expanduser("~/.local/bin:") + env.get("PATH", "")
    return subprocess.run(args, capture_output=True, text=True, env=env, timeout=timeout)


def fetch(board, statuses=None):
    r = sh([HERMES_BIN, "kanban", "--board", board, "list", "--json"])
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip()[:200] or "kanban list a échoué")
    tasks = json.loads(r.stdout or "[]")
    if statuses:
        tasks = [t for t in tasks if t.get("status") in statuses]
    return tasks


def fetch_one(board, task_id):
    r = sh([HERMES_BIN, "kanban", "--board", board, "show", task_id, "--json"])
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip()[:200])
    return [json.loads(r.stdout)["task"]]


def lint(task):
    """Retourne la liste des manquements (vide = conforme)."""
    body = task.get("body") or ""
    issues = []
    if not body.strip():
        return ["body vide"]

    positions = []
    for label, pat in SECTION_PATTERNS:
        m = pat.search(body)
        if not m:
            issues.append("section manquante : « " + label + " »")
        else:
            positions.append(m.start())
    if len(positions) == len(SECTION_PATTERNS) and positions != sorted(positions):
        issues.append("sections dans le désordre (attendu 1→5)")

    if not GHERKIN_FEATURE.search(body):
        issues.append("Gherkin : pas de bloc « Fonctionnalité:/Feature: »")
    n_scen = len(GHERKIN_SCENARIO.findall(body))
    if n_scen < 2:
        issues.append(f"Gherkin : {n_scen} scénario(s), minimum 2 (nominal + limite/erreur)")
    n_steps = len(GHERKIN_STEPS.findall(body))
    if n_steps < 3:
        issues.append(f"Gherkin : {n_steps} étape(s) Étant donné/Quand/Alors, minimum 3")

    if not DOR.search(body):
        issues.append("DoR absent")
    if not DOD.search(body):
        issues.append("DoD absent")
    if not GUARDRAIL.search(body):
        issues.append("garde-fous : aucun interdit explicite")

    n_files = len(set(FILE_MENTION.findall(body)))
    if n_files > 5 and not INVEST_SPLIT.search(body):
        issues.append(f"INVEST/Small : {n_files} fichiers cités sans découpage explicite")
    if BLOAT.search(body) and not INVEST_SPLIT.search(body):
        issues.append("INVEST/Small : formulation « tout/refonte complète » sans découpage")
    if len(body) > 12000:
        issues.append(f"INVEST/Small : body très long ({len(body)} car.) — découper ?")
    return issues


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--board", required=True)
    ap.add_argument("--task")
    ap.add_argument("--all", action="store_true",
                    help="toutes les cartes actives (todo/ready/blocked/running)")
    ap.add_argument("--status", default="todo,ready")
    a = ap.parse_args()

    statuses = [s.strip() for s in a.status.split(",") if s.strip()]
    try:
        tasks = fetch_one(a.board, a.task) if a.task else fetch(
            a.board, None if a.all else statuses)
    except Exception as e:
        print(f"[pj-lint] ERREUR: {e}")
        return 2

    def is_spec(t):
        title = (t.get("title") or "").strip()
        if re.match(r"^t[1-6]\b", title.lower()):
            return False
        if t.get("status") in ("done", "archived"):
            return False
        if "importé depuis" in (t.get("body") or "").lower():
            return False  # racine du pont (body = issue GitHub, pas une spec pj)
        return True

    bad = 0
    for t in tasks:
        if not is_spec(t):
            continue
        problems = lint(t)
        if problems:
            bad += 1
            print(f"[pj-lint] {t['id']} « {(t.get('title') or '')[:60]} » ({t.get('status')}) — NON CONFORME :")
            for p in problems:
                print(f"           - {p}")
    if bad:
        print(f"[pj-lint] {bad} carte(s) non conforme(s) sur {a.board} — compléter avant validation.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
