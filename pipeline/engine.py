#!/usr/bin/env python3
"""
Moteur de pipeline YAML pour le kanban Hermes — orchestré par LangGraph.

Exécute un workflow défini en YAML (workflows/*.yaml) sur un ticket kanban.
Chaque étape est soit :
  - déterministe : une commande shell (check template, CI, update kanban...)
  - agentique    : un agent externe (hermes profile+modèle, dsh, claude) dont
                   la sortie est validée contre un schéma JSON (structured
                   output).
  - gate         : une expression Python qui route pass/fail.

L'orchestration est déléguée à LangGraph (StateGraph) : les étapes deviennent
des nœuds, les branchements (gate on_pass/on_fail, on_fail d'étape) des arêtes
conditionnelles, et le fan-out parallèle (viewpoints/revalidate) est géré par
LangGraph. On garde les backends Hermes comme nœuds (une fonction Python) —
pas d'abstraction LLM LangChain.

Sortie structurée "as artifact" : chaque agent ÉCRIT son JSON dans un fichier
(.pipeline/artifacts/<étape>_<rôle>.json) via son outil write_file, puis le
moteur lit le fichier. Zéro parsing de transcript (robuste au non-déterminisme
du backend hermes).

Idempotence : le moteur écrit un fichier d'état par ticket
(.pipeline/<ticket>.json) qui enregistre les sorties de chaque étape. Un
re-run repart des étapes déjà réussies (cache) et ne rejoue que ce qui a
échoué ou changé.

Usage :
  pipeline.py run <workflow.yaml> <ticket_id> [--board <slug>] [--dry-run]
  pipeline.py list <workflow.yaml>          # étapes + types (sans exécuter)
"""

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

from backends import run_hermes_artifact, run_agent, extract_json
import pj_autonomy

# LangGraph
from langgraph.graph import StateGraph, START, END
from typing import TypedDict, Annotated, Any

# ------------------------------------------------------------------ config

HERMES_BIN = shutil.which("hermes") or os.path.expanduser(
    "~/.hermes/hermes-agent/venv/bin/hermes")
GH_BIN = shutil.which("gh") or "/usr/bin/gh"
DEFAULT_BOARD = os.environ.get("KANBAN_BOARD", "hermes-experiment")
STATE_DIR = Path(".pipeline")
ARTIFACT_DIR = STATE_DIR / "artifacts"

# --- notification Discord par étape (gh-triage) ---------------------------
DISCORD_HELPER = Path.home() / ".hermes/scripts/discord_thread.py"
ISSUE_CHANNEL = os.environ.get("ISSUE_CHANNEL", "")
DISCORD_GUILD = os.environ.get("DISCORD_GUILD", "")
GH_REPO = os.environ.get("GH_REPO", "hyron-fr/hermes-experiment")
# Cache thread_id -> issue_number pour ne pas re-lister à chaque étape.
_THREAD_CACHE: dict[int, str | None] = {}


def resolve_thread(issue_number: int) -> str | None:
    """Retrouve le thread Discord d'une issue (nom '🎫 Issue #N — …' ou
    renommé '{icon} {status} - issue N …')."""
    if issue_number in _THREAD_CACHE:
        return _THREAD_CACHE[issue_number]
    tid = None
    try:
        out = sh([sys.executable, str(DISCORD_HELPER), "threads",
                  ISSUE_CHANNEL, DISCORD_GUILD])
        pat = re.compile(rf"issue\s*#?\s*{issue_number}\b", re.IGNORECASE)
        for line in out.splitlines():
            parts = line.split(" ", 1)
            if len(parts) == 2 and pat.search(parts[1]):
                tid = parts[0]
                break
    except Exception:
        tid = None
    _THREAD_CACHE[issue_number] = tid
    return tid


def _step_feedback(sid: str, stype: str, result: dict) -> str:
    """Rendu déterministe du contenu d'une étape (status + feedback détaillé).

    Aucun appel LLM : on met en forme la structure `result` renvoyée par
    l'étape (gate pass/fail, agents ok/ko + summary/feedback, sortie shell).
    """
    if stype == "gate":
        return ("pass ✓" if result.get("passed")
                else ("max_iterations atteint ✕" if result.get("max_iterations")
                      else "fail ✕"))
    if stype == "agentic":
        lines = []
        for r in result.get("results", []):
            data = r.get("data", {})
            # Données structurées : status ok/ko (revalidate, coherence...) ou
            # summary/concerns (viewpoints). Déterministe : on ne reprend que
            # des champs scalaires courts.
            st = "ok" if r.get("ok") else "ko"
            piece = f"  - {r.get('role','?')}: {st}"
            if isinstance(data, dict):
                verdict = data.get("status") or data.get("verdict")
                if verdict:
                    piece += f" ({verdict})"
                sm = data.get("summary")
                if isinstance(sm, str) and sm:
                    piece += f" — {sm[:160]}"
                for err in r.get("errors", []):
                    piece += f" [validation: {err[:120]}]"
                # feedback libre (revalidate/coherence)
                fb = data.get("feedback")
                if isinstance(fb, str) and fb and fb not in (sm,):
                    piece += f" | feedback: {fb[:160]}"
            lines.append(piece)
        return ("; ".join(lines) if lines
                else f"{len(result.get('results', []))} agent(s)")
    if stype == "deterministic":
        outs = []
        for o in result.get("outputs", []):
            o = str(o).strip().splitlines()
            outs.append(" / ".join(l for l in o if l)[:200])
        return ("; ".join(outs) if outs else "commande exécutée")
    return ""


def _step_next(sid: str, steps_def: list[dict]) -> str:
    """Déterminisme : prochaine étape à partir de l'ordre déclaré + routage.

    Suit les arêtes du graphe : `on_fail` pour un échec, `on_pass` pour un
    gate gagné, sinon l'étape suivante dans l'ordre du YAML. Retourne le mot
    réservé 'fin' quand aucune étape ne suit.
    """
    ids = [s["id"] for s in steps_def]
    if sid not in ids:
        return "fin"
    i = ids.index(sid)
    step = steps_def[i]
    stype = step.get("type", "agentic")
    nxt = ids[i + 1] if i + 1 < len(ids) else None
    if stype == "gate":
        n = step.get("on_pass", nxt)
        f = step.get("on_fail")
        if f and f != n:
            return f"{n} (ou {f} sur fail)"
        return (f"{n} (fin sur fail)" if f else (n or "fin"))
    if step.get("on_fail"):
        return f"{nxt or 'fin'} (ou {step['on_fail']} sur échec)"
    return nxt or "fin"


def notify_step(ticket: dict, sid: str, stype: str, result: dict,
                steps_def: list[dict]) -> None:
    """Status + feedback + next step sur le thread Discord ET l'issue GitHub.

    Entièrement déterministe (aucun appel LLM) : le corps est mis en forme à
    partir de `result` (sortie d'étape) et de `steps_def` (ordre + routage).
    Best-effort : un échec de notification ne casse jamais le pipeline.
    """
    if not ticket.get("issue_number"):
        return
    status = "✅" if result.get("ok") else "❌"
    feedback = _step_feedback(sid, stype, result)
    nxt = _step_next(sid, steps_def)
    body = (f"⚙️ **{ticket.get('title','')}** — étape `{sid}` ({stype}) "
            f"{status}\n"
            f"**Status** : {status}\n"
            f"**Feedback** : {feedback}\n"
            f"**Next step** : `{nxt}`")

    # Discord.
    tid = resolve_thread(ticket["issue_number"])
    if tid:
        try:
            sh([sys.executable, str(DISCORD_HELPER), "send", tid, body])
        except Exception:
            pass

    # GitHub (commentaire sur l'issue, markdown).
    try:
        sh([GH_BIN, "issue", "comment", str(ticket["issue_number"]),
            "--repo", GH_REPO, "--body", body])
    except Exception:
        pass


# --- renommage du thread Discord par étape --------------------------------
# Smileys + libellés de statut définis au niveau du YAML (clé `status` du
# workflow), pas codés en dur. Chaque étape peut surcharger `icon`/`status`.
DEFAULT_STATUS_LABELS = {
    "running": "⚙️ running",
    "done": "✅ done",
    "fail": "❌ fail",
    "retry": "🔁 retry",
}


def _status_labels(wf: dict) -> dict:
    labels = dict(DEFAULT_STATUS_LABELS)
    labels.update(wf.get("status", {}) or {})
    return labels


def rename_thread(ticket: dict, step: dict, outcome: str, dry_run: bool,
                  labels: dict) -> None:
    """Renomme le thread Discord de l'issue en '{icon} {status} - issue N …'.

    Best-effort : un échec de renommage ne casse jamais le pipeline.
    `outcome` ∈ {running, done, fail, retry} sélectionne le libellé dans
    `labels` (défini dans le YAML). Une étape peut surcharger `icon` et/ou
    `status` (critère 5).
    """
    if dry_run or not ticket.get("issue_number"):
        return
    tid = resolve_thread(ticket["issue_number"])
    if not tid:
        return
    label = labels.get(outcome, labels["running"])
    icon = step.get("icon")
    status = step.get("status")
    if icon or status:
        base_icon, _, base_status = label.partition(" ")
        label = f"{icon or base_icon} {status or base_status}".strip()
    name = f"{label} - issue {ticket['issue_number']} {ticket.get('title', '')}"
    try:
        sh([sys.executable, str(DISCORD_HELPER), "rename", tid, name])
    except Exception:
        pass  # le renommage ne doit jamais casser le pipeline


# ------------------------------------------------------------------ helpers

def sh(cmd: list[str], timeout: int = 300) -> str:
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd)}\n-> exit {r.returncode}\n"
                           f"{r.stderr.strip()[:500]}")
    return r.stdout


def kanban(*args: str, board: str = DEFAULT_BOARD) -> str:
    return sh([HERMES_BIN, "kanban", "--board", board, *args])


def ticket_context(ticket_id: str, board: str) -> dict:
    """Charge le ticket kanban (title + body) comme contexte d'étape."""
    out = kanban("show", ticket_id, "--json", board=board)
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        # show --json peut ne pas exister : fallback sur list --json.
        tasks = json.loads(kanban("list", "--json", board=board) or "[]")
        data = next((t for t in tasks if t.get("id") == ticket_id), {})
    # `show --json` renvoie la tâche sous la clé `task` (avec comments/events/
    # runs à côté). `list --json` renvoie la tâche à plat. On normalise.
    if isinstance(data, dict) and "task" in data and isinstance(data["task"], dict):
        data = data["task"]
    body = data.get("body", "")
    # Numéro d'issue GitHub déduit de la ligne "Importé depuis <url>" (même
    # convention que le pont gh_kanban_bridge.py).
    m = re.search(r"github\.com/[^/]+/[^/]+/issues/(\d+)", body)
    return {
        "id": data.get("id", ticket_id),
        "title": data.get("title", ""),
        "body": body,
        "status": data.get("status", ""),
        "issue_number": int(m.group(1)) if m else None,
    }


def render(template: str, ctx: dict) -> str:
    """Substitue {{ticket.id}}, {{ticket.title}}, {{step.<id>}} ... dans un
    template. Les variables inconnues restent littérales (pas d'erreur)."""
    def repl(m):
        key = m.group(1).strip()
        parts = key.split(".")
        val = ctx
        for p in parts:
            if isinstance(val, dict) and p in val:
                val = val[p]
            else:
                return m.group(0)  # inconnu -> littéral
        return str(val)
    return re.sub(r"\{\{\s*([\w.]+)\s*\}\}", repl, template)


# ------------------------------------------------------------------ schémas

def load_schema(path: str | None, base_dir: Path | None = None) -> dict | None:
    if not path:
        return None
    p = Path(path)
    if not p.is_absolute():
        p = (base_dir or Path.cwd()) / p
    if not p.exists():
        raise FileNotFoundError(f"schéma introuvable: {p}")
    return json.loads(p.read_text())


def validate_json(data: dict, schema: dict | None) -> list[str]:
    """Valide `data` contre un schéma JSON (jsonschema si dispo, sinon
    vérification minimale des clés requises). Renvoie la liste d'erreurs."""
    if schema is None:
        return []
    try:
        import jsonschema
        errors = list(jsonschema.Draft7Validator(schema).iter_errors(data))
        return [e.message for e in errors]
    except ImportError:
        # Fallback minimal : vérifie la présence des clés `required`.
        missing = [k for k in schema.get("required", []) if k not in data]
        return [f"champ requis manquant: {k}" for k in missing]


# ------------------------------------------------------------------ état

def state_path(ticket_id: str) -> Path:
    return STATE_DIR / f"{ticket_id}.json"


# ------------------------------------------------ P6 : reprise de session
#
# Repère Factory Droid « persistent sessions : resume / fork ». À chaque
# tentative d'une étape agentique, l'id de session est capturé
# (--pass-session-id) et posé dans un sidecar par (ticket, étape, rôle).
# Au retry, si l'étape déclare `resume: true` (et que le run précédent
# n'a PAS abouti à un résultat validé), le même id est repassé via
# --resume : le contexte + tool calls de la tentative précédente sont
# conservés. Défaut = fork (session neuve) : le comportement historique.
# Dégradation ouverte : id absent/illisible -> pas de reprise, pas d'erreur.

def session_sidecar_path(ticket_id: str) -> Path:
    return STATE_DIR / f"{ticket_id}.sessions.json"


def _load_sessions(ticket_id: str) -> dict:
    p = session_sidecar_path(ticket_id)
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text())
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def save_session(ticket_id: str, step_id: str, role: str,
                 session_id: str | None) -> None:
    """Capture l'id de session d'une tentative (best-effort, jamais bloquant)."""
    if not session_id:
        return
    try:
        data = _load_sessions(ticket_id)
        data[f"{step_id}:{role}"] = session_id
        p = session_sidecar_path(ticket_id)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(data, ensure_ascii=False))
    except OSError:
        pass


def resume_session_for(step: dict, ticket_id: str, step_id: str,
                       role: str) -> str | None:
    """Id de session à REPRENDRE pour cette tentative (P6), ou None.

    Seuil : l'étape doit déclarer `resume: true` ET le run précédent n'avoir
    PAS produit un résultat validé (un résultat ok est mis en cache côté
    `steps` : il ne repasse pas ici, donc la capture reste correcte).
    """
    if not step.get("resume"):
        return None
    data = _load_sessions(ticket_id)
    sid = data.get(f"{step_id}:{role}")
    return str(sid) if sid else None


def load_state(ticket_id: str) -> dict:
    p = state_path(ticket_id)
    if p.exists():
        try:
            return json.loads(p.read_text())
        except json.JSONDecodeError:
            return {}
    return {}


def save_state(ticket_id: str, state: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    state_path(ticket_id).write_text(json.dumps(state, indent=1,
                                                ensure_ascii=False))


# ------------------------------------------------------------------ état LangGraph

def _merge_steps(a: dict, b: dict) -> dict:
    """Reducer : fusionne les résultats d'étapes au lieu de les écraser."""
    merged = dict(a or {})
    merged.update(b or {})
    return merged


class WFState(TypedDict, total=False):
    ticket: dict
    steps: Annotated[dict, _merge_steps]  # id d'étape -> résultat (fusionné)
    errors: list
    iterations: int
    dry_run: bool
    base_dir: str
    autonomy_level: str   # niveau d'autonomie du workflow (pj_autonomy)
    escalated: str        # id de l'étape escaladée ("" si aucune)


# ------------------------------------------------------------ autonomie

def _autonomy_guard(step: dict, state: WFState) -> dict | None:
    """Politique d'autonomie avant l'exécution d'une étape (0 LLM).

    Retourne une mise à jour d'état si l'étape doit être ESCALADÉE (le
    graphe s'arrête ensuite sur END), None si elle peut s'exécuter.
    Le gate n'est jamais escaladé (routage lecture-seule, aucun effet).
    `dry_run` : décision prise, aucun effet de bord (pas de comment ni
    de block kanban).
    """
    level = state.get("autonomy_level") or pj_autonomy.DEFAULT_LEVEL
    verdict, reason = pj_autonomy.decision(
        pj_autonomy.effective_level(step, level), step)
    if verdict != "escalate":
        return None
    dry_run = state.get("dry_run", False)
    sid = step.get("id", "?")
    ticket = state.get("ticket", {}) or {}
    board = state.get("board", DEFAULT_BOARD)
    comment = pj_autonomy.escalate_comment(step, reason, board, ticket.get("id", ""))
    if not dry_run:
        try:
            kanban("comment", ticket.get("id", ""), comment, board=board)
        except Exception:
            pass
        try:
            kanban("block", ticket.get("id", ""), "--kind", "needs_input",
                   reason, board=board)
        except Exception:
            pass
    return {"escalated": sid,
            "steps": {sid: {"ok": False, "escalated": True,
                            "reason": reason, "dry_run": dry_run}}}


# ------------------------------------------------------------------ nœuds

def make_agentic_node(step: dict, labels: dict):
    """Nœud LangGraph : exécute une étape agentique (parallèle via LangGraph)."""
    prompt_tpl = step.get("prompt", "")
    agents = step.get("agents") or [step.get("agent")]
    agents = [a for a in agents if a]
    schema_path = step.get("output", {}).get("schema")

    def node(state: WFState) -> dict:
        ctx = {
            "ticket": state["ticket"],
            "steps": state.get("steps", {}),
            "board": state.get("board", DEFAULT_BOARD),
        }
        base_dir = Path(state.get("base_dir", "."))
        schema = load_schema(schema_path, base_dir)
        dry_run = state.get("dry_run", False)
        # Autonomie : décision AVANT toute exécution (off => le LLM ne
        # doit PAS démarrer). Escalade -> le graphe s'arrête (arête sortante).
        esc = _autonomy_guard(step, state)
        if esc is not None:
            return esc
        ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
        rename_thread(state["ticket"], step, "running", dry_run, labels)

        results = []
        parallel = bool(step.get("parallel"))
        if parallel and len(agents) > 1:
            # Parallélise les agents indépendants (viewpoints, revalidate) via
            # un ThreadPoolExecutor. Chaque agent écrit son artifact dans son
            # propre fichier (pas de collision). Résultats collectés dans
            # l'ordre de déclaration.
            from concurrent.futures import ThreadPoolExecutor

            def _run_one(agent: dict) -> dict:
                render_ctx = dict(ctx)
                render_ctx["role"] = agent.get("role", "")
                prompt = render(prompt_tpl, render_ctx)
                if dry_run:
                    return {"role": agent.get("role", "?"),
                            "dry_run": True, "data": {}, "ok": True}
                backend = agent.get("backend", "hermes")
                if backend == "hermes":
                    out_path = ARTIFACT_DIR / f"{step['id']}_{agent.get('role', 'agent')}.json"
                    resume = resume_session_for(
                        step, state["ticket"].get("id", ""),
                        step["id"], agent.get("role", "agent"))
                    raw, sid = run_hermes_artifact(
                        prompt, str(out_path),
                        profile=agent.get("profile", "default"),
                        model=agent.get("model"), timeout=600,
                        resume_session=resume,
                    )
                    save_session(state["ticket"].get("id", ""),
                                 step["id"], agent.get("role", "agent"), sid)
                    data = json.loads(raw)
                else:
                    raw = run_agent(agent, prompt)
                    data = extract_json(raw)
                errors = validate_json(data, schema)
                return {"role": agent.get("role", "?"),
                        "data": data, "errors": errors,
                        "ok": not errors}

            with ThreadPoolExecutor(max_workers=len(agents)) as ex:
                results = list(ex.map(_run_one, agents))
        else:
            for agent in agents:
                render_ctx = dict(ctx)
                render_ctx["role"] = agent.get("role", "")
                prompt = render(prompt_tpl, render_ctx)
                if dry_run:
                    results.append({"role": agent.get("role", "?"),
                                    "dry_run": True, "data": {}, "ok": True})
                    continue
                backend = agent.get("backend", "hermes")
                if backend == "hermes":
                    # Pattern "structured output as artifact" : l'agent écrit son
                    # JSON dans un fichier, on lit le fichier (pas de parsing de
                    # transcript). Fichier dédié par étape + rôle.
                    out_path = ARTIFACT_DIR / f"{step['id']}_{agent.get('role', 'agent')}.json"
                    resume = resume_session_for(
                        step, state["ticket"].get("id", ""),
                        step["id"], agent.get("role", "agent"))
                    raw, sid = run_hermes_artifact(
                        prompt, str(out_path),
                        profile=agent.get("profile", "default"),
                        model=agent.get("model"), timeout=600,
                        resume_session=resume,
                    )
                    save_session(state["ticket"].get("id", ""),
                                 step["id"], agent.get("role", "agent"), sid)
                    data = json.loads(raw)
                else:
                    # Autres backends (dsh, claude) : parsing transcript (moins
                    # robuste, mais ces backends ne sont plus utilisés par défaut).
                    raw = run_agent(agent, prompt)
                    data = extract_json(raw)
                errors = validate_json(data, schema)
                results.append({"role": agent.get("role", "?"),
                                "data": data, "errors": errors,
                                "ok": not errors})
        ok = all(r["ok"] for r in results)
        rename_thread(state["ticket"], step, "done" if ok else "fail",
                      dry_run, labels)
        return {"steps": {step["id"]: {"ok": ok, "results": results}}}
    return node


def make_deterministic_node(step: dict, labels: dict):
    """Nœud LangGraph : étape déterministe (commande shell / actions)."""
    def node(state: WFState) -> dict:
        ctx = {
            "ticket": state["ticket"],
            "steps": state.get("steps", {}),
            "board": state.get("board", DEFAULT_BOARD),
        }
        dry_run = state.get("dry_run", False)
        # Autonomie : décision AVANT exécution (irréversible -> escalade).
        esc = _autonomy_guard(step, state)
        if esc is not None:
            return esc
        rename_thread(state["ticket"], step, "running", dry_run, labels)
        commands = step.get("command") or step.get("actions") or []
        if isinstance(commands, str):
            commands = [commands]
        outputs = []
        for cmd in commands:
            rendered = render(cmd, ctx)
            if dry_run:
                outputs.append(f"[dry-run] {rendered}")
                continue
            outputs.append(sh(["bash", "-c", rendered]))
        rename_thread(state["ticket"], step, "done", dry_run, labels)
        return {"steps": {step["id"]: {"ok": True, "outputs": outputs}}}
    return node


def make_gate_node(step: dict, max_iter: int = 10, labels: dict | None = None):
    """Nœud LangGraph : gate — évalue une expression Python, route pass/fail.

    Le gate incrémente `iterations` dans l'état. Si l'expression échoue et que
    le nombre d'itérations dépasse `max_iter`, il route vers finalize (sortie)
    au lieu de reboucler indéfiniment sur on_fail.
    """
    expr = step.get("check", "True")
    labels = labels or DEFAULT_STATUS_LABELS

    def node(state: WFState) -> dict:
        ctx = {
            "ticket": state["ticket"],
            "steps": state.get("steps", {}),
            "board": state.get("board", DEFAULT_BOARD),
        }
        dry_run = state.get("dry_run", False)
        rename_thread(state["ticket"], step, "running", dry_run, labels)
        env = {"ctx": ctx, "all": all, "any": any}
        for k, v in ctx.get("steps", {}).items():
            env[k] = v
        try:
            passed = bool(eval(expr, {"__builtins__": {}}, env))
        except Exception as e:
            rename_thread(state["ticket"], step, "fail", dry_run, labels)
            return {"steps": {step["id"]: {"ok": False,
                                           "error": f"gate invalide: {e}"}},
                    "iterations": state.get("iterations", 0) + 1}
        iterations = state.get("iterations", 0) + 1
        # Si le gate échoue mais qu'on a atteint max_iterations, on force la
        # sortie (route vers finalize) pour ne pas boucler indéfiniment.
        if not passed and iterations > max_iter:
            rename_thread(state["ticket"], step, "fail", dry_run, labels)
            return {"steps": {step["id"]: {"ok": False, "passed": False,
                                           "max_iterations": True}},
                    "iterations": iterations}
        rename_thread(state["ticket"], step,
                      "done" if passed else "retry", dry_run, labels)
        return {"steps": {step["id"]: {"ok": passed, "passed": passed}},
                "iterations": iterations}
    return node


# ------------------------------------------------------------------ graphe

def build_graph(wf: dict, base_dir: Path):
    """Compile le workflow YAML en StateGraph LangGraph."""
    g = StateGraph(WFState)
    steps = wf["steps"]
    by_id = {s["id"]: s for s in steps}
    max_iter = wf.get("orchestration", {}).get("max_iterations", 10)
    labels = _status_labels(wf)

    # Nœuds
    for step in steps:
        sid = step["id"]
        stype = step.get("type", "agentic")
        if stype == "agentic":
            g.add_node(sid, make_agentic_node(step, labels))
        elif stype == "deterministic":
            g.add_node(sid, make_deterministic_node(step, labels))
        elif stype == "gate":
            g.add_node(sid, make_gate_node(step, max_iter, labels))
        else:
            raise ValueError(f"type d'étape inconnu: {stype}")

    # Arêtes : on relie chaque étape à la suivante (ordre déclaratif), sauf
    # les étapes avec on_fail / gate qui routent conditionnellement.
    # Autonomie : une étape escaladée (_autonomy_guard pose `escalated`)
    # arrête le graphe — le ticket est bloqué needs_input pour l'humain.
    # La vérification se fait sur les ARÊTES sortantes de chaque nœud.
    def _esc(cond) :
        """Enveloppe un routeur : `escalated` court-circuite vers END."""
        def router(s: WFState) -> str:
            if s.get("escalated"):
                return END
            return cond(s)
        return router

    for i, step in enumerate(steps):
        sid = step["id"]
        stype = step.get("type", "agentic")
        nxt = steps[i + 1]["id"] if i + 1 < len(steps) else END

        if stype == "gate":
            # gate : on_pass -> X, on_fail -> Y (arête conditionnelle).
            on_pass = step.get("on_pass", nxt)
            on_fail = step.get("on_fail", nxt)
            # Si max_iterations atteint, on force la sortie vers finalize.
            finalize_id = next((s["id"] for s in steps
                                if s.get("type") == "deterministic"
                                and s.get("id") == "finalize"), on_pass)
            g.add_conditional_edges(
                sid,
                _esc(lambda s, st=step, op=on_pass, of=on_fail, fi=finalize_id:
                    fi if s["steps"].get(st["id"], {}).get("max_iterations")
                    else (op if s["steps"].get(st["id"], {}).get("passed") else of)),
                {on_pass: on_pass, on_fail: on_fail,
                 finalize_id: finalize_id, END: END},
            )
        elif step.get("on_fail"):
            # Étape avec on_fail : si échec -> on_fail, sinon -> suivant.
            on_fail = step["on_fail"]
            g.add_conditional_edges(
                sid,
                _esc(lambda s, st=step, n=nxt, of=on_fail:
                    of if not s["steps"].get(st["id"], {}).get("ok") else n),
                {nxt: nxt, on_fail: on_fail, END: END},
            )
        else:
            g.add_conditional_edges(
                sid,
                _esc(lambda s, n=nxt: n),
                {nxt: nxt, END: END},
            )

    g.add_edge(START, steps[0]["id"])
    return g.compile()


# ------------------------------------------------------------------ moteur

def run_workflow(wf: dict, ticket_id: str, board: str, dry_run: bool,
                 base_dir: Path | None = None) -> dict:
    """Exécute le workflow sur un ticket via LangGraph. Renvoie l'état final."""
    base_dir = base_dir or Path.cwd()
    graph = build_graph(wf, base_dir)

    ctx = {
        "ticket": ticket_context(ticket_id, board),
        "steps": {},
        "board": board,
        "dry_run": dry_run,
        "base_dir": str(base_dir),
        "autonomy_level": pj_autonomy.workflow_level(wf),
    }

    # Idempotence : repart des étapes déjà réussies (cache).
    state = load_state(ticket_id)
    if state.get("steps") and not dry_run:
        ctx["steps"] = {k: v for k, v in state["steps"].items()
                        if v.get("ok")}

    result = graph.invoke(ctx)

    # Notifications Discord + GitHub à chaque étape (gh-triage).
    if not dry_run:
        for sid, sres in result.get("steps", {}).items():
            stype = next((s.get("type", "agentic") for s in wf["steps"]
                          if s["id"] == sid), "agentic")
            notify_step(result["ticket"], sid, stype, sres, wf["steps"])

    final = {
        "ticket": ticket_id,
        "steps": result.get("steps", {}),
        "ok": (not result.get("escalated")
               and result.get("steps", {}).get("finalize", {}).get("ok", False)),
        "escalated": result.get("escalated", ""),
    }
    if not dry_run:
        save_state(ticket_id, final)
    return final


# ------------------------------------------------------------------ CLI

def cmd_list(wf: dict) -> None:
    for s in wf.get("steps", []):
        stype = s.get("type", "agentic")
        agents = s.get("agents") or ([s.get("agent")] if s.get("agent") else [])
        desc = ", ".join(a.get("role", "?") for a in agents if a) or "-"
        print(f"{s.get('id'):<16} {stype:<13} {desc}")


def main() -> None:
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    action, wf_path = sys.argv[1], sys.argv[2]
    wf_path = Path(wf_path)
    wf = yaml.safe_load(wf_path.read_text())
    base_dir = wf_path.resolve().parent

    if action == "list":
        cmd_list(wf)
        return

    if action != "run":
        sys.exit(__doc__)

    ticket_id = sys.argv[3]
    board = DEFAULT_BOARD
    dry_run = "--dry-run" in sys.argv
    if "--board" in sys.argv:
        board = sys.argv[sys.argv.index("--board") + 1]

    result = run_workflow(wf, ticket_id, board, dry_run, base_dir)
    print(json.dumps(result, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
