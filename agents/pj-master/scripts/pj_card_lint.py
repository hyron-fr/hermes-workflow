#!/usr/bin/env python3
"""pj-card-lint — vérifie la conformité des cartes kanban au format pj (0 LLM).

Contrôles par carte (body) :
  1. les 5 sections obligatoires, dans l'ordre — **BILINGUE** :
     FR « Contexte & Objectif », « Critères d'acceptation », « DoR & DoD »,
        « Considérations techniques », « Hors-scope »
     EN « Context & Objective », « Acceptance criteria », « DoR & DoD »,
        « Technical considerations », « Out of scope »
  2. bloc Gherkin : « Fonctionnalité/Feature: » + au moins 2 « Scénario/Scenario: »
     (nominal + limite/erreur) avec Étant donné/Quand/Alors (ou Given/When/Then)
  3. DoR ET DoD présents (les deux mots-clés)
  4. garde-fous : au moins un interdit explicite (mot-clé d'interdiction, FR ou EN)
  5. INVEST dimensionnel : détection des signaux de dépassement (Small) —
     nb de puces « fichiers »/modules cités, mentions « refonte/global/complet »,
     absence de découpage explicite quand > 5 fichiers listés.

BILINGUISME (décision humaine du 20/09, remplace le gel des libellés) : les deux jeux
de titres sont acceptés, et les messages de sortie sont en anglais. Le linter reste
donc lisible pour un contributeur qui ne lit pas le français, sans invalider les
cartes françaises déjà en base (compatibilité ascendante mesurée par
tests/test_issue2_plate_reproducible.py).

Usage :
  pj_card_lint.py --board pj-<repo> [--all | --task <id>] [--status todo,ready]
Sortie : une ligne par carte non conforme (stdout vide = tout conforme → tick muet).
Code de retour : 0 = conforme, 1 = au moins une carte non conforme, 2 = erreur d'exécution.
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
    # Les DEUX jeux de titres sont acceptés (bilingue) : le français reste valide
    # pour les cartes déjà en base, l'anglais est le registre cible.
    ("Context & Objective", re.compile(
        r"^\s*#*\s*(?:\d\.\s*)?(?:contexte|context)\s*&\s*(?:objectif|objective)", re.I | re.M)),
    ("Acceptance criteria", re.compile(
        r"^\s*#*\s*(?:\d\.\s*)?(?:crit[eè]res\s+d'acceptation|acceptance\s+criteria)", re.I | re.M)),
    ("DoR & DoD", re.compile(r"^\s*#*\s*(?:\d\.\s*)?DoR\s*&\s*DoD", re.I | re.M)),
    ("Technical considerations", re.compile(
        r"^\s*#*\s*(?:\d\.\s*)?(?:consid[eé]rations\s+techniques|technical\s+considerations)", re.I | re.M)),
    ("Out of scope", re.compile(
        r"^\s*#*\s*(?:\d\.\s*)?(?:hors[-\s]?scope|out[-\s]?of[-\s]?scope)", re.I | re.M)),
]
GHERKIN_FEATURE = re.compile(r"^\s*#*\s*(fonctionnalit[eé]|feature)\s*:", re.I | re.M)
GHERKIN_SCENARIO = re.compile(r"^\s*#*\s*(sc[eé]nario|scenario|exemple|example)\s*:", re.I | re.M)
GHERKIN_STEPS = re.compile(r"^\s*#*\s*(étant donn[eé]|etant donne|quand|alors|given|when|then)\b", re.I | re.M)
DOR = re.compile(r"\bDoR\b|definition of ready|d[eé]finition of ready", re.I)
DOD = re.compile(r"\bDoD\b|definition of done|d[eé]finition of done", re.I)
GUARDRAIL = re.compile(
    r"\b(interdit|ne pas|jamais|pas de |no |forbidden|must not|never|do not|don't|"
    r"garde[-\s]?fou|guardrail)", re.I)
INVEST_SPLIT = re.compile(r"\binvest\b|\bslice\b|\bsous[-\s]carte|\bd[eé]coup", re.I)
BLOAT = re.compile(r"\b(refonte compl[eè]te|r[eé][eé]criture globale|tout le projet|complet du "
                   r"module|migration totale)\b", re.I)
FILE_MENTION = re.compile(r"\b[\w./-]+\.(py|ts|tsx|js|jsx|json|ya?ml|toml|md|sh|css|html)\b")


def sh(args, timeout=90):
    env = dict(os.environ)
    env["PATH"] = os.path.expanduser("~/.local/bin:") + env.get("PATH", "")
    return subprocess.run(args, capture_output=True, text=True, env=env, timeout=timeout)


def fetch(board: str, statuses=None):
    args = [HERMES_BIN, "kanban", "--board", board, "list", "--json"]
    r = sh(args)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip()[:200] or "kanban list a échoué")
    tasks = json.loads(r.stdout or "[]")
    if statuses:
        tasks = [t for t in tasks if t.get("status") in statuses]
    return tasks


def fetch_one(board: str, task_id: str):
    r = sh([HERMES_BIN, "kanban", "--board", board, "show", task_id, "--json"])
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip()[:200])
    return [json.loads(r.stdout)["task"]]


def lint(task: dict) -> list[str]:
    """Retourne la liste des manquements (vide = conforme)."""
    body = task.get("body") or ""
    title = task.get("title") or ""
    issues = []

    if not body.strip():
        return ["empty body"]

    # 1. sections obligatoires, dans l'ordre (les deux jeux de titres acceptés)
    positions = []
    for label, pat in SECTION_PATTERNS:
        m = pat.search(body)
        if not m:
            issues.append(f"missing section: « {label} »")
        else:
            positions.append((label, m.start()))
    if len(positions) == len(SECTION_PATTERNS):
        ordered = [p[1] for p in positions]
        if ordered != sorted(ordered):
            issues.append("sections out of order (expected 1→5)")

    # 2. Gherkin
    if not GHERKIN_FEATURE.search(body):
        issues.append("Gherkin: no « Feature: / Fonctionnalité: » block")
    n_scen = len(GHERKIN_SCENARIO.findall(body))
    if n_scen < 2:
        issues.append(f"Gherkin: {n_scen} scenario(s), minimum 2 (nominal + edge/error)")
    n_steps = len(GHERKIN_STEPS.findall(body))
    if n_steps < 3:
        issues.append(f"Gherkin: {n_steps} step(s) Given/When/Then, minimum 3")

    # 3. DoR & DoD
    if not DOR.search(body):
        issues.append("DoR missing")
    if not DOD.search(body):
        issues.append("DoD missing")

    # 4. garde-fous
    if not GUARDRAIL.search(body):
        issues.append("guardrails: no explicit prohibition")

    # 5. INVEST dimensionnel (signaux de dépassement)
    files = set(FILE_MENTION.findall(body)) or set()
    n_files = len(files)
    if n_files > 5 and not INVEST_SPLIT.search(body):
        issues.append(f"INVEST/Small: {n_files} files mentioned without explicit split")
    if BLOAT.search(body) and not INVEST_SPLIT.search(body):
        issues.append("INVEST/Small: « whole rewrite » wording without a split")
    if len(body) > 12000:
        issues.append(f"INVEST/Small: oversized body ({len(body)} chars) — split?")

    return issues


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--board", required=True)
    ap.add_argument("--task")
    ap.add_argument("--all", action="store_true",
                    help="toutes les cartes actives (todo/ready/blocked/running)")
    ap.add_argument("--status", default="todo,ready",
                    help="statuts filtrés (défaut: todo,ready)")
    a = ap.parse_args()

    statuses = [s.strip() for s in a.status.split(",") if s.strip()]
    try:
        tasks = fetch_one(a.board, a.task) if a.task else fetch(
            a.board, None if a.all else statuses)
    except Exception as e:
        print(f"[pj-lint] ERREUR: {e}")
        return 2

    # Ne linter que les cartes qui portent une SPEC ou une implémentation :
    # on exclut les cartes de process du pipeline (t1..t6, racine importée du pont)
    # et les cartes déjà terminées/archivées par un run antérieur au contrat.
    def is_spec(t):
        title = (t.get("title") or "").strip()
        low = title.lower()
        # Cartes de process du pipeline : t1..t6 et variantes t4a/t3b.
        # Tout le reste (test-k, dev-k, conv-k, doc-k, doc-review, doc-memory,
        # worktree-mk/rm) est une carte de production -> lintée.
        if re.match(r"^t\d+[a-z]?\b", low):
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
            print(f"[pj-lint] {t['id']} « {t['title'][:60]} » ({t.get('status')}) — NOT COMPLIANT:")
            for p in problems:
                print(f"           - {p}")
    if bad:
        print(f"[pj-lint] {bad} non-compliant card(s) on {a.board} — complete before validation.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())