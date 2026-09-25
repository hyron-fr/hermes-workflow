#!/usr/bin/env python3
"""pj_run_contract — contrat de résultat par run + verdict d'audit (0 LLM).

Problème résolu
---------------
Un worker peut sortir en rc=0 sans appel terminal (`kanban_complete` /
`kanban_block` / `kanban_request_review`). Hermes le classe alors
`protocol_violation` et retente (budget 3). Mais le même symptôme recouvre
deux réalités opposées, et le dispatcher ne les distingue pas :

  A. le travail EST FAIT, seul le paperwork manque  → un retry complète ;
  B. le worker n'a JAMAIS démarré (modèle invalide, quota, auth) → retenter
     est inutile tant que l'infra n'est pas réparée.

Retenter B consume le budget de violations et finit en `gave_up` + carte
`blocked`, en imputant à la tâche une panne d'infrastructure.

Ce que fait l'outil : pour chaque run en violation, il collecte les PREUVES
déjà présentes (metadata de run, events `protocol_violation`/`gave_up`,
`latest_summary`, commentaires, log worker) et rend un verdict déterministe,
avec l'artefact de contrat que le run aurait dû émettre.

Inspiré du contrat de résultat de `droid exec` (Factory) : chaque run rend un
résultat TYPÉ consommable par le pipeline, au lieu d'un exit code ambigu.

Preuves exploitées (toutes déjà écrites par Hermes — aucune instrumentation) :
  - `task_runs.metadata.protocol_violation` : marqueur durable côté Hermes
  - `task_runs.outcome` : completed | crashed | rate_limited | gave_up | …
  - events de la carte : `protocol_violation`, `gave_up` (failures, limit)
  - log worker : `Messages: N (x user, y tool calls)` + erreur provider
  - `latest_summary` : trace d'un run antérieur qui a produit le travail

Usage :
  pj_run_contract.py --board <board> --task <id> [--json OUT]
  pj_run_contract.py --board <board> --all [--json OUT]
Sortie : verdict par run + état de contrat de la carte.
Code de retour : 0 = contrat satisfait (ou rien à auditer), 1 = violation avec
travail non fait (action requise), 2 = erreur d'exécution.

Dégradation ouverte : source illisible (board sans runs, log absent) => verdict
`unclear` avec la raison, jamais un crash.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys

HERMES_BIN = shutil.which("hermes") or os.path.expanduser(
    "~/.hermes/hermes-agent/venv/bin/hermes")

# ---------------------------------------------------------------- verdicts

# Le travail est fait, seul l'acte terminal manque.
WORK_DONE = "work_done_paperwork_missing"
# Le worker n'a jamais produit d'appel d'outil : panne d'infra, retry inutile.
NEVER_STARTED = "never_started_infra"
# Violation constatée, preuves insuffisantes pour trancher.
UNCLEAR = "unclear"
# Contrat satisfait (run terminal avec metadata, ou aucune violation).
SATISFIED = "satisfied"

TERMINAL_OUTCOMES = ("completed",)
# Outcomes qui signalent une violation de protocole (rc=0 sans acte terminal).
VIOLATION_OUTCOMES = ("crashed", "gave_up")

_PROVIDER_ERROR_MARKERS = (
    "non-retryable client error",
    "invalid model name",
    "authentication failed",
    "rate limit",
    "http 400",
    "http 401",
    "http 403",
    "http 429",
    "insufficient",
    "no such model",
)

# « Messages:       1 (1 user, 0 tool calls) »
_MSG_RE = re.compile(r"Messages:\s*(\d+)\s*\((\d+)\s*user,\s*(\d+)\s*tool calls?\)")
_SESSION_RE = re.compile(r"^Session:\s*(\S+)", re.M)


def parse_worker_log(text: str) -> dict:
    """Extrait les signaux d'un log worker (déterministe, tolérant).

    Retourne {messages, user_msgs, tool_calls, provider_error, session_id}.
    Un log absent ou tronqué -> compteurs None, jamais une exception.
    """
    out = {"messages": None, "user_msgs": None, "tool_calls": None,
           "provider_error": None, "session_id": None}
    if not text:
        return out
    m = _MSG_RE.search(text)
    if m:
        out["messages"] = int(m.group(1))
        out["user_msgs"] = int(m.group(2))
        out["tool_calls"] = int(m.group(3))
    s = _SESSION_RE.search(text)
    if s:
        out["session_id"] = s.group(1)
    low = text.lower()
    for marker in _PROVIDER_ERROR_MARKERS:
        if marker in low:
            out["provider_error"] = marker
            break
    return out


def run_violated(run: dict) -> bool:
    """Un run porte-t-il une violation de protocole ?

    Marqueur durable Hermes (`metadata.protocol_violation`) en priorité ;
    repli sur le texte d'erreur pour les runs antérieurs au marqueur.
    """
    meta = run.get("metadata") or {}
    if isinstance(meta, dict) and meta.get("protocol_violation"):
        return True
    err = (run.get("error") or "").lower()
    return "protocol violation" in err or (
        "without calling kanban_complete" in err and "cleanly" in err)


def run_satisfied(run: dict) -> bool:
    """Un run a-t-il satisfait le contrat (sortie terminale + faits) ?"""
    if run.get("outcome") not in TERMINAL_OUTCOMES:
        return False
    meta = run.get("metadata")
    return isinstance(meta, dict) and bool(meta)


def classify_run(run: dict, log_text: str = "",
                 latest_summary: str | None = None,
                 is_latest: bool = True) -> dict:
    """Verdict d'un run : {verdict, reason, evidence}.

    `is_latest` : le log worker est écrasé à chaque run — il ne décrit QUE le
    dernier. Les runs antérieurs sont donc jugés sur leurs seules metadata et
    le summary, jamais sur le log d'un autre run.

    Ordre de décision (le plus décisif en premier) :
      1. run terminal avec metadata          -> SATISFIED
      2. pas de violation                     -> SATISFIED (rien à auditer)
      3. 0 appel d'outil OU erreur provider   -> NEVER_STARTED (infra)
      4. summary d'un run antérieur / artefacts -> WORK_DONE
      5. sinon                                -> UNCLEAR
    """
    ev = parse_worker_log(log_text) if is_latest else parse_worker_log("")
    meta = run.get("metadata") if isinstance(run.get("metadata"), dict) else {}

    if run_satisfied(run):
        return {"verdict": SATISFIED, "reason": "run terminal avec metadata",
                "evidence": {"outcome": run.get("outcome"),
                             "metadata_keys": sorted(meta.keys())}}

    if not run_violated(run):
        return {"verdict": SATISFIED, "reason": "aucune violation de protocole",
                "evidence": {"outcome": run.get("outcome")}}

    # (3) Le worker a-t-il seulement démarré ? (preuve = log du dernier run)
    zero_tools = ev["tool_calls"] == 0
    if zero_tools or ev["provider_error"]:
        bits = []
        if ev["tool_calls"] is not None:
            bits.append(f"{ev['tool_calls']} appel(s) d'outil")
        if ev["messages"] is not None:
            bits.append(f"{ev['messages']} message(s)")
        if ev["provider_error"]:
            bits.append(f"erreur provider: {ev['provider_error']}")
        return {"verdict": NEVER_STARTED,
                "reason": ("le worker n'a produit aucun appel d'outil ("
                           + ", ".join(bits) + ") — panne d'infra, "
                           "un retry est inutile avant réparation"),
                "evidence": {"tool_calls": ev["tool_calls"],
                             "messages": ev["messages"],
                             "provider_error": ev["provider_error"],
                             "session_id": ev["session_id"]}}

    # (4) Un run antérieur a-t-il laissé la trace du travail ?
    summary = (latest_summary or "").strip()
    low = summary.lower()
    done_hints = ("vérifié que l'implémentation", "implémentation est toujours",
                  "déjà terminée", "work done", "commit ", "pr #", "run ")
    if (is_latest and ev["tool_calls"]) or any(h in low for h in done_hints) \
            or meta.get("artifacts"):
        return {"verdict": WORK_DONE,
                "reason": ("le travail apparaît fait (trace dans "
                           "latest_summary/metadata) : seul l'acte terminal "
                           "manque — un retry doit compléter, pas refaire"),
                "evidence": {"summary_excerpt": summary[:200],
                             "metadata_keys": sorted(meta.keys()),
                             "tool_calls": ev["tool_calls"]}}

    return {"verdict": UNCLEAR,
            "reason": "violation constatée, preuves insuffisantes pour trancher",
            "evidence": {"tool_calls": ev["tool_calls"],
                         "messages": ev["messages"],
                         "session_id": ev["session_id"],
                         "summary_excerpt": summary[:200]}}


def task_contract(runs: list[dict], log_text: str = "",
                  latest_summary: str | None = None,
                  events: list[dict] | None = None) -> dict:
    """Contrat agrégé d'une carte : {state, runs_audited, violations, verdicts}."""
    violations = [r for r in runs if run_violated(r)]
    # Le log worker est écrasé à chaque run : seul le DERNIER run est jugé
    # sur le log. Les autres le sont sur metadata + summary.
    last_id = max((r.get("id") or 0) for r in runs) if runs else None
    verdicts = [classify_run(r, log_text, latest_summary,
                             is_latest=(r.get("id") == last_id))
                for r in violations]
    kinds = [v["verdict"] for v in verdicts]

    if not violations:
        state = SATISFIED
    elif NEVER_STARTED in kinds:
        # Une panne d'infra domine : retenter ne sert à rien, et elle explique
        # les violations à elle seule (aucun run n'a réellement démarré).
        state = NEVER_STARTED
    elif WORK_DONE in kinds:
        state = WORK_DONE
    else:
        state = UNCLEAR

    gave_up = [e for e in (events or [])
               if (e.get("kind") or "").lower() == "gave_up"]
    return {
        "state": state,
        "runs_audited": len(runs),
        "runs_satisfied": sum(1 for r in runs if run_satisfied(r)),
        "violations": len(violations),
        "gave_up": len(gave_up),
        "verdicts": verdicts,
    }


# ---------------------------------------------------------------- lecture kanban

def _sh(cmd: list[str], timeout: int = 120):
    env = dict(os.environ)
    env["PATH"] = os.path.expanduser("~/.local/bin:") + env.get("PATH", "")
    return subprocess.run(cmd, capture_output=True, text=True, env=env,
                          timeout=timeout)


def kanban(board: str, *args: str, timeout: int = 120) -> str:
    r = _sh([HERMES_BIN, "kanban", "--board", board, *args], timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError(
            f"kanban {' '.join(args)} -> exit {r.returncode}\n"
            f"{r.stderr.strip()[:300]}")
    return r.stdout


def read_task(board: str, task_id: str) -> dict:
    """Carte + events (la forme varie : on normalise)."""
    raw = json.loads(kanban(board, "show", task_id, "--json") or "{}")
    if isinstance(raw, dict) and isinstance(raw.get("task"), dict):
        return {"task": raw["task"], "events": raw.get("events") or [],
                "latest_summary": raw.get("latest_summary")}
    return {"task": raw if isinstance(raw, dict) else {},
            "events": [], "latest_summary": None}


def read_runs(board: str, task_id: str) -> list[dict]:
    try:
        data = json.loads(kanban(board, "runs", task_id, "--json") or "[]")
        return data if isinstance(data, list) else []
    except Exception:
        return []


def read_log(board: str, task_id: str, tail: int = 4000) -> str:
    try:
        return kanban(board, "log", task_id, "--tail", str(tail))
    except Exception:
        return ""


def list_tasks(board: str, statuses=None) -> list[dict]:
    """Cartes du board.

    Attention : `hermes kanban list --json` sur un board inexistant sort en
    rc=0 avec un MESSAGE TEXTE sur stdout (« board 'x' does not exist »), pas
    du JSON. Avaler l'erreur produirait un faux « rien à auditer » (exit 0) —
    on la remonte donc explicitement.
    """
    raw = kanban(board, "list", "--json")
    try:
        data = json.loads(raw or "[]")
    except json.JSONDecodeError:
        raise RuntimeError(f"board illisible ({raw.strip()[:120]})")
    if not isinstance(data, list):
        raise RuntimeError(f"board illisible (JSON inattendu: {type(data).__name__})")
    if statuses:
        data = [t for t in data if t.get("status") in statuses]
    return data


def audit_task(board: str, task_id: str) -> dict:
    """Audit complet d'une carte : contrat + identité."""
    ctx = read_task(board, task_id)
    task = ctx["task"]
    runs = read_runs(board, task_id)
    log_text = read_log(board, task_id)
    contract = task_contract(runs, log_text, ctx.get("latest_summary"),
                             ctx.get("events"))
    contract.update({
        "task_id": task_id,
        "title": task.get("title", ""),
        "status": task.get("status", ""),
        "assignee": task.get("assignee", ""),
        "board": board,
    })
    return contract


# ---------------------------------------------------------------- CLI

_ACTIVE = ("blocked", "ready", "running", "todo", "review", "scheduled")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--board", required=True)
    ap.add_argument("--task")
    ap.add_argument("--all", action="store_true",
                    help="audite les cartes actives du board")
    ap.add_argument("--json", dest="json_path", default="")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()

    if not a.task and not a.all:
        ap.error("--task ou --all requis")

    try:
        if a.task:
            targets = [a.task]
        else:
            targets = [t.get("id") for t in list_tasks(a.board, _ACTIVE)
                       if t.get("id")]
    except Exception as e:
        print(f"[pj-contract] ERREUR: {e}")
        return 2
    contracts = []
    unreadable = 0
    for tid in targets:
        try:
            contracts.append(audit_task(a.board, tid))
        except Exception as e:
            unreadable += 1
            contracts.append({"task_id": tid, "state": UNCLEAR,
                              "reason": f"lecture impossible: {e}",
                              "read_error": True, "verdicts": []})

    if a.json_path:
        with open(a.json_path, "w", encoding="utf-8") as fh:
            json.dump(contracts, fh, ensure_ascii=False, indent=2)

    # Source entièrement illisible = erreur d'exécution, pas un verdict métier
    # (board supprimé, hermes/kanban cassé) : exit 2, distinct d'une carte à
    # trancher (exit 1).
    if contracts and unreadable == len(contracts):
        first = contracts[0].get("reason", "source illisible")
        print(f"[pj-contract] ERREUR: aucune carte lisible sur {a.board} "
              f"({first})")
        return 2

    actionable = 0
    for c in contracts:
        state = c.get("state")
        if state == SATISFIED:
            if not a.quiet:
                print(f"[pj-contract] {c['task_id']} OK — contrat satisfait")
            continue
        if state in (WORK_DONE, NEVER_STARTED, UNCLEAR):
            actionable += 1
            tag = {WORK_DONE: "TRAVAIL FAIT / PAPERWORK MANQUANT",
                   NEVER_STARTED: "JAMAIS DÉMARRÉ (INFRA)",
                   UNCLEAR: "INDÉTERMINÉ"}[state]
            print(f"[pj-contract] {c['task_id']} « {c.get('title','')[:50]} » "
                  f"({c.get('status')}) — {tag}")
            print(f"           violations={c.get('violations')} "
                  f"gave_up={c.get('gave_up')}")
            for v in c.get("verdicts", []):
                print(f"           - {v['verdict']}: {v['reason']}")

    if actionable:
        print(f"[pj-contract] {actionable} carte(s) nécessitent une décision "
              f"humaine ou une réparation d'infra.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())