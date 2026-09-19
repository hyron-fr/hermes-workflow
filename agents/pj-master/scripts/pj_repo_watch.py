#!/usr/bin/env python3
"""pj-repo-watch — détecte les nouveaux repos hyron-fr et les onboard sur le pipeline pj.

Déterministe, aucun LLM. Onboard en 2 PHASES (idempotent, retry au tick) :

  Phase A — dès la création du repo (AUCUN contenu requis) :
    wrappers bridge+deployer + crons pj-bridge-<slug>/pj-deploy-<slug>
    + board pj-<slug>. Dès lors, le bridge poll le repo : les issues ouvertes
    sont importées en triage (0 LLM) et attendent le code.
    Marqueur de complétion : le board existe.

  Phase B (dès le premier commit) :
    branche dev sur GitHub (depuis la default), clone --branch dev dans
    ${HOME}/pj-repos/<repo>, set-default-workdir (ancrage worktree).
    Marqueur : le clone existe.

stdout : une ligne par action réelle ; tick muet si rien de nouveau.
Variables : PJ_WATCH_VERBOSE=1, DRY_RUN=1.
"""

import json
import os
from pathlib import Path
import re
import subprocess
import sys

# Racine du dépôt : résolue depuis ce fichier (aucun chemin absolu).
WORKFLOW_ROOT = Path(__file__).resolve().parents[1]

GH_REPO_OWNER = "hyron-fr"
ANCHOR_ROOT = "${HOME}/pj-repos"
PROFILE_HOME = "${HOME}/.hermes/profiles/pj-master"
PROFILE_SCRIPTS = os.path.join(PROFILE_HOME, "scripts")
BRIDGE_PATH = str(WORKFLOW_ROOT / "bridge" / "gh_kanban_bridge.py")
DEPLOYER_PATH = os.path.join(PROFILE_SCRIPTS, "pj_pipeline_deployer.py")

VERBOSE = os.environ.get("PJ_WATCH_VERBOSE") == "1"
DRY_RUN = os.environ.get("DRY_RUN") == "1"


def log(msg: str) -> None:
    print(f"[pj-watch] {msg}")


def sh(args, timeout=120, env=None) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout, env=env)


def board_slug(repo: str) -> str:
    return f"pj-{re.sub(r'[^a-z0-9-]+', '-', repo.lower()).strip('-')}"


def hermes(*args: str) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["HERMES_HOME"] = PROFILE_HOME
    env["PATH"] = os.path.expanduser("~/.local/bin:") + env.get("PATH", "")
    return sh(["hermes", *args], env=env)


def boards() -> list[str]:
    r = hermes("kanban", "boards", "list")
    slugs = []
    for line in r.stdout.splitlines():
        line = line.strip()
        if line.startswith("●"):
            line = line[1:]
        parts = line.split()
        if parts and not parts[0].startswith("SLUG"):
            slugs.append(parts[0])
    return slugs


def cron_names() -> set[str]:
    r = hermes("cron", "list")
    return {ln.split(":", 1)[1].strip() for ln in r.stdout.splitlines()
            if ln.strip().startswith("Name:")}


def phase_a(repo: str, full: str, slug: str) -> bool:
    """Wrappers + crons + board (aucun contenu requis)."""
    os.makedirs(PROFILE_SCRIPTS, exist_ok=True)
    for kind in ("bridge", "deploy"):
        name = f"pj_{kind}_{repo}.sh"
        path = os.path.join(PROFILE_SCRIPTS, name)
        if kind == "bridge":
            content = (
                "#!/usr/bin/env bash\n"
                f"# Wrapper cron : pont GitHub<->kanban pour {full} (board {slug}).\n"
                'export PATH="$HOME/.local/bin:$PATH"\n'
                'command -v gh >/dev/null 2>&1 || { echo "gh introuvable"; exit 1; }\n'
                f"export GH_REPO={full}\n"
                f"export KANBAN_BOARD={slug}\n"
                "export KANBAN_ASSIGNEE=pj-master\n"
                "export BOT_GRACE_SECONDS=0\n"
                "export PJ_IMPORT_TRIAGE=1\n"
                f'exec python3 {BRIDGE_PATH} "$@"\n'
            )
        else:
            content = (
                "#!/usr/bin/env bash\n"
                f"# Wrapper cron : deployer pipeline pour {full} (board {slug}).\n"
                f"export PJ_BOARD={slug}\n"
                f'exec python3 {DEPLOYER_PATH} run\n'
            )
        if not DRY_RUN:
            with open(path, "w") as f:
                f.write(content)
            os.chmod(path, 0o755)
        log(f"{repo}: wrapper {name} {'(dry-run)' if DRY_RUN else 'écrit'}")

    existing = cron_names()
    for name, script in ((f"pj-bridge-{repo}", f"pj_bridge_{repo}.sh"),
                         (f"pj-deploy-{repo}", f"pj_deploy_{repo}.sh")):
        if name in existing:
            continue
        if DRY_RUN:
            log(f"{repo}: cron {name} (dry-run)")
            continue
        rc = hermes("cron", "create", "*/5 * * * *", "--name", name,
                    "--script", script, "--no-agent")
        if rc.returncode != 0:
            log(f"{repo}: cron {name} échoué ({rc.stderr.strip()[:100]}) — retry")
            return False
        log(f"{repo}: cron {name} créé")

    if DRY_RUN:
        log(f"{repo}: board {slug} (dry-run) — phase A complète")
        return True
    rc = hermes("kanban", "boards", "create", slug)
    if rc.returncode != 0 and "already" not in rc.stdout + rc.stderr:
        log(f"{repo}: board {slug} échoué ({rc.stderr.strip()[:80]}) — retry")
        return False
    log(f"{repo}: phase A complète (board {slug} + crons + wrappers)")
    return True


def phase_b(repo: str, full: str, slug: str) -> bool:
    """Branche dev + clone + default_workdir (exige au moins 1 commit)."""
    # Repo vide -> différé (rien à brancher, rien à cloner).
    r = sh(["gh", "api", f"repos/{full}/commits", "--jq", "length"])
    if r.returncode != 0 or r.stdout.strip() in ("", "0"):
        if VERBOSE:
            log(f"{repo}: repo vide — phase B différée au premier commit")
        return False

    r = sh(["gh", "api", f"repos/{full}", "--jq", ".default_branch"])
    default_branch = (r.stdout.strip() if r.returncode == 0 and r.stdout.strip() else "main")

    r = sh(["gh", "api", f"repos/{full}/branches/dev", "--jq", ".name"])
    if r.returncode != 0:
        r2 = sh(["gh", "api", f"repos/{full}/branches/{default_branch}", "--jq", ".commit.sha"])
        if r2.returncode != 0:
            log(f"{repo}: branche par défaut illisible — retry")
            return False
        sha = r2.stdout.strip()
        rc = sh(["gh", "api", "-X", "POST", f"repos/{full}/git/refs",
                 "-f", "ref=refs/heads/dev", "-f", f"sha={sha}"])
        if rc.returncode != 0 and "already exists" not in rc.stderr:
            log(f"{repo}: création dev échouée ({rc.stderr.strip()[:80]}) — retry")
            return False
        log(f"{repo}: branche dev créée depuis {default_branch}")

    anchor = os.path.join(ANCHOR_ROOT, repo)
    if not os.path.isdir(anchor):
        rc = sh(["git", "clone", "--branch", "dev", "-q", f"https://github.com/{full}.git", anchor],
                timeout=300)
        if rc.returncode != 0:
            log(f"{repo}: clone échoué ({rc.stderr.strip()[:80]}) — retry")
            return False
        log(f"{repo}: cloné (dev) -> {anchor}")

    if DRY_RUN:
        log(f"{repo}: set-default-workdir (dry-run) — phase B complète")
        return True
    rc = hermes("kanban", "boards", "set-default-workdir", slug, anchor)
    if rc.returncode != 0:
        log(f"{repo}: set-default-workdir échoué — retry")
        return False
    log(f"{repo}: phase B complète (worktree anchor {anchor})")
    return True


def main() -> int:
    r = sh(["gh", "repo", "list", GH_REPO_OWNER, "--limit", "100",
            "--json", "name,isArchived"])
    if r.returncode != 0:
        log(f"gh repo list échoué: {r.stderr.strip()[:100]}")
        return 1
    repos = [x["name"] for x in json.loads(r.stdout or "[]") if not x.get("isArchived")]
    have = set(boards())
    actions = 0
    for repo in repos:
        slug = board_slug(repo)
        full = f"{GH_REPO_OWNER}/{repo}"
        try:
            if slug not in have:
                if phase_a(repo, full, slug):
                    actions += 1
                continue  # phase B au prochain tick (après le board)
            # Phase B : si pas d'anchor clone, tenter (skippé vite fait si clone présent)
            if not os.path.isdir(os.path.join(ANCHOR_ROOT, repo)):
                if phase_b(repo, full, slug):
                    actions += 1
        except Exception as e:
            log(f"ERREUR {repo}: {e}")
    if not actions and not VERBOSE:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())