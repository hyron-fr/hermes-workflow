#!/usr/bin/env python3
"""pj_readiness — score de préparation « Agent Readiness » du repo cible (0 LLM).

Inspiré du modèle Agent Readiness de Factory (5 niveaux, 9 piliers, progression
à 80 %) : un worker ne doit pas être dispatché sur un repo qui ne permet pas de
VALIDER son travail. Un repo sans tests scriptables produit exactement les runs
qui tournent à l'aveugle et meurent sans acte terminal.

Niveaux (règle Factory : débloquer N+1 exige ≥ 80 % des critères du niveau N) :
  1 Functional    — README, linter, type checker, tests unitaires + runner, build
  2 Documented    — AGENTS.md, template d'env, conteneur, pre-commit, git sain
  3 Standardized  — tests d'intégration, CODEOWNERS, secret scanning, CI, docs, logs
  4 Optimized     — dépendances épinglées (lock file), CI avec cache, expérimentation
  5 Autonomous    — hors périmètre du gate (non mesuré statiquement)

Piliers (mapping Factory) : Style & Validation, Build System, Testing,
Documentation, Development Environment, Observability, Security, Task Discovery,
Product & Experimentation.

Usage :
  pj_readiness.py --repo PATH [--min-level N] [--json OUT] [--online] [--quiet]
Défaut : --min-level 3 (une slice de dev exige un repo « Standardized ») ;
le graphe complet (orchestration type mission) devrait exiger 4.
Sortie : rapport des manques niveau par niveau.
Code de retour : 0 = niveau atteint, 1 = niveau insuffisant, 2 = erreur d'exécution.

Point d'insertion recommandé : à l'import de l'issue (t0, gh_kanban_bridge) et
au claim de t1, AVANT la création du worktree — un dispatch sur un repo non
prêt est voué à l'échec.
"""
import argparse
import json
import subprocess
import sys
import tomllib
from pathlib import Path

PASS_RATIO = 0.8
MAX_LEVEL = 4  # niveau 5 non mesurable statiquement

# ---------------------------------------------------------------- helpers FS

def _exists(repo: Path, *relnames: str) -> bool:
    return any((repo / r).exists() for r in relnames)


def _exists_dir(repo: Path, *relnames: str) -> bool:
    return any((repo / r).is_dir() for r in relnames)


def _pyproject_sections(repo: Path) -> str:
    p = repo / "pyproject.toml"
    if not p.is_file():
        return ""
    try:
        doc = tomllib.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return ""
    parts = [f"[{k}]" for k in doc]
    parts += [f"[tool.{k}]" for k in (doc.get("tool") or {})]
    return " ".join(parts)


def _pkgjson(repo: Path) -> dict:
    p = repo / "package.json"
    if not p.is_file():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _pkgjson_script(repo: Path, name: str) -> bool:
    return bool((_pkgjson(repo).get("scripts") or {}).get(name))


def _count_md(repo: Path) -> int:
    return len(list(repo.glob("*.md"))) + len(list(repo.glob("*/*.md")))


def _workflows_text(repo: Path) -> list[str]:
    out = []
    wf = repo / ".github" / "workflows"
    if wf.is_dir():
        for f in sorted(wf.glob("*.y*ml"))[:10]:
            try:
                out.append(f.read_text(encoding="utf-8", errors="replace"))
            except Exception:
                pass
    return out


_TEST_RUNNERS = ("pytest", "vitest", "jest", "npm test", "cargo test",
                 "go test", "make test", "playwright")

_OBS_PATTERNS = (b"structlog", b"loguru", b"opentelemetry", b"otel", b"sentry_sdk",
                 b"prometheus", b"pino(", b"winston", b"createLogger", b"getLogger")
_SRC_SUFFIX = (".py", ".ts", ".tsx", ".js", ".mjs", ".go")
_SKIP_PARTS = {"node_modules", ".venv", "venv", "dist", "build", ".git",
               "dist-newstyle", "__pycache__", ".pixi", ".next"}


# ---------------------------------------------------------------- checks

def _ci_runs_tests(repo: Path) -> bool:
    return any(any(runner in t for runner in _TEST_RUNNERS) for t in _workflows_text(repo))


def _ci_cache(repo: Path) -> bool:
    return any(("actions/cache" in t or "cache:" in t or "pixi" in t or "uv-cache" in t)
               for t in _workflows_text(repo))


def _secret_scanning(repo: Path) -> bool:
    if _exists(repo, ".gitleaks.toml", ".secretsignore", ".detect-secrets"):
        return True
    return any(any(w in t.lower() for w in ("gitleaks", "trufflehog", "detect-secrets"))
               for t in _workflows_text(repo))


def _gh_owner_repo(repo: Path) -> str:
    r = subprocess.run(["git", "-C", str(repo), "remote", "get-url", "origin"],
                       capture_output=True, text=True, timeout=15)
    if r.returncode != 0:
        return ""
    raw = r.stdout.strip()
    if raw.startswith("git@"):
        raw = raw.split(":", 1)[-1]
    elif "github.com/" in raw:
        raw = raw.split("github.com/", 1)[-1]
    return raw.removesuffix(".git").strip("/")


def _branch_protected(repo: Path) -> bool:
    """Critère en ligne (mode --online) : interroge gh api."""
    owner_repo = _gh_owner_repo(repo)
    if owner_repo.count("/") != 1:
        return False
    try:
        r = subprocess.run(["gh", "api", f"repos/{owner_repo}/branches"],
                           capture_output=True, text=True, timeout=30)
        return r.returncode == 0
    except Exception:
        return False


def _observability_signal(repo: Path, max_files: int = 150) -> bool:
    """Heuristique : logging structuré / tracing / métriques dans le code source."""
    n = 0
    for suffix in _SRC_SUFFIX:
        for f in repo.rglob(f"*{suffix}"):
            if n >= max_files:
                return False
            if set(f.parts) & _SKIP_PARTS:
                continue
            n += 1
            try:
                head = f.read_bytes()[:6000]
            except Exception:
                continue
            if any(p in head for p in _OBS_PATTERNS):
                return True
    return False


# ---------------------------------------------------------------- critères
# (id, niveau, pilier, description, check(repo) -> bool)

CRITERIA = [
    # --- Niveau 1 : Functional
    ("readme", 1, "Documentation", "README à la racine",
     lambda r: _exists(r, "README.md", "README.rst", "README")),
    ("lint_config", 1, "Style & Validation",
     "config linter (ruff/flake8/eslint/biome/pylint)",
     lambda r: _exists(r, "ruff.toml", ".ruff.toml", ".flake8", "biome.json",
                       "eslint.config.mjs", ".eslintrc", ".eslintrc.js",
                       ".eslintrc.json", ".eslintrc.yml", ".pylintrc")
     or "[tool.ruff]" in _pyproject_sections(r)
     or "[tool.pylint]" in _pyproject_sections(r)),
    ("type_check", 1, "Style & Validation",
     "type checker (mypy/pyright/tsconfig)",
     lambda r: _exists(r, "mypy.ini", ".mypy.ini", "pyrightconfig.json", "tsconfig.json")
     or "[tool.mypy]" in _pyproject_sections(r)),
    ("unit_tests", 1, "Testing", "tests unitaires présents",
     lambda r: bool(list(r.glob("test_*.py")) or list(r.glob("*_test.py"))
                    or list((r / "tests").glob("**/test_*.py"))
                    or list((r / "test").glob("**/test_*.py"))
                    or list(r.glob("src/**/test_*.py"))
                    or list(r.glob("**/*.test.ts")) or list(r.glob("**/*.test.js"))
                    or (r / "__tests__").is_dir())),
    ("test_runner", 1, "Testing",
     "runner de tests configuré (pytest/vitest/jest/tox/script npm)",
     lambda r: _exists(r, "pytest.ini", "tox.ini", "vitest.config.ts", "vitest.config.js",
                       "jest.config.js", "jest.config.ts", "jest.config.mjs")
     or "[tool.pytest" in _pyproject_sections(r)
     or "[tool:pytest]" in _pyproject_sections(r)
     or _pkgjson_script(r, "test")),
    ("build_commands", 1, "Build System",
     "commandes de build définies (Makefile/pyproject/package.json/just/Taskfile)",
     lambda r: _exists(r, "Makefile", "makefile", "justfile", ".justfile",
                       "Taskfile.yml", "Cargo.toml", "go.mod", "pixi.toml")
     or "[project]" in _pyproject_sections(r)
     or _pkgjson_script(r, "build")),

    # --- Niveau 2 : Documented
    ("agents_md", 2, "Documentation",
     "AGENTS.md — conventions lues par les agents (critère clé du pipeline)",
     lambda r: _exists(r, "AGENTS.md", ".agents/AGENTS.md", "agents.md")),
    ("env_template", 2, "Development Environment",
     "template d'environnement (.env.example)",
     lambda r: _exists(r, ".env.example", ".env.sample", ".example.env", ".env.template")),
    ("container", 2, "Development Environment",
     "environnement reproductible (devcontainer/compose/Dockerfile)",
     lambda r: _exists(r, ".devcontainer/devcontainer.json", "docker-compose.yml",
                       "docker-compose.yaml", "compose.yml", "compose.yaml", "Dockerfile")),
    ("precommit", 2, "Style & Validation",
     "hooks de pre-commit (.pre-commit-config.yaml/.husky)",
     lambda r: _exists(r, ".pre-commit-config.yaml", ".husky")),
    ("git_wellformed", 2, "Task Discovery",
     "repo git sain (.gitignore présent)",
     lambda r: (r / ".git").exists() and (r / ".gitignore").is_file()),
    ("branch_protection", 2, "Security",
     "protection de branche (gh api — mode --online uniquement)",
     _branch_protected),

    # --- Niveau 3 : Standardized
    ("integration_tests", 3, "Testing",
     "tests d'intégration/e2e séparés (tests/integration, e2e, playwright)",
     lambda r: _exists_dir(r, "tests/integration", "tests/e2e", "test/e2e", "e2e", "cypress")
     or _exists(r, "playwright.config.ts", "playwright.config.js", "cypress.config.ts")
     or bool(list(r.glob("tests/**/*integration*.py")))),
    ("codeowners", 3, "Security", "CODEOWNERS défini",
     lambda r: _exists(r, "CODEOWNERS", ".github/CODEOWNERS", "docs/CODEOWNERS")),
    ("secret_scanning", 3, "Security",
     "secret scanning (gitleaks/trufflehog/detect-secrets)",
     _secret_scanning),
    ("ci_pipeline", 3, "Build System",
     "pipeline CI qui lance les tests (.github/workflows)",
     _ci_runs_tests),
    ("docs_dir", 3, "Documentation",
     "documentation au-delà du README (docs/ ou ≥5 .md)",
     lambda r: (r / "docs").is_dir() or _count_md(r) >= 5),
    ("observability", 3, "Debugging & Observability",
     "logging structuré / tracing / métriques dans le code",
     _observability_signal),

    # --- Niveau 4 : Optimized
    ("deps_pinned", 4, "Build System",
     "dépendances épinglées (pixi.lock/uv.lock/poetry.lock/package-lock…)",
     lambda r: _exists(r, "pixi.lock", "uv.lock", "poetry.lock", "Pipfile.lock",
                       "package-lock.json", "pnpm-lock.yaml", "yarn.lock",
                       "Cargo.lock", "go.sum", "Gemfile.lock")),
    ("ci_cache", 4, "Build System",
     "CI avec cache (feedback rapide)",
     _ci_cache),
    ("experimentation", 4, "Product & Experimentation",
     "instrumentation produit / expérimentation (analytics, flags, experiments)",
     lambda r: _exists_dir(r, "experiments", "analytics")
     or _pkgjson_script(r, "analytics")),
]


# ---------------------------------------------------------------- scoring

def evaluate(repo: Path, online: bool = False) -> dict:
    """Score du repo → {level, ratios, criteria, missing}."""
    criteria = [c for c in CRITERIA if online or c[0] != "branch_protection"]
    results = []
    for cid, level, pillar, desc, check in criteria:
        try:
            ok = bool(check(repo))
        except Exception:
            ok = False
        results.append({"id": cid, "level": level, "pillar": pillar,
                        "desc": desc, "passed": ok})

    ratios = {}
    for lvl in (1, 2, 3, 4):
        subset = [r for r in results if r["level"] == lvl]
        if subset:
            ratios[lvl] = sum(r["passed"] for r in subset) / len(subset)

    level = 0
    for lvl in (1, 2, 3, 4):
        if ratios.get(lvl, 0.0) >= PASS_RATIO:
            level = lvl
        else:
            break

    missing = [r for r in results if not r["passed"] and r["level"] <= level + 1]
    return {"level": level, "max_level": MAX_LEVEL,
            "ratios": {str(k): round(v, 2) for k, v in ratios.items()},
            "criteria": results, "missing": missing,
            "repo": str(repo)}


# ---------------------------------------------------------------- CLI

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--min-level", type=int, default=3)
    ap.add_argument("--json", dest="json_path", default="")
    ap.add_argument("--online", action="store_true",
                    help="inclut les critères nécessitant gh api (branch protection)")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()

    repo = Path(a.repo).expanduser().resolve()
    if not repo.is_dir():
        print(f"[pj-ready] ERREUR: repo introuvable: {repo}")
        return 2

    report = evaluate(repo, online=a.online)
    if a.json_path:
        Path(a.json_path).write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    lvl = report["level"]
    if not a.quiet:
        total = len(report["criteria"])
        passed = sum(1 for r in report["criteria"] if r["passed"])
        print(f"[pj-ready] {repo} — niveau {lvl}/{report['max_level']} "
              f"({passed}/{total} critères)")
        for r in report["missing"]:
            print(f"[pj-ready]   manque [N{r['level']}|{r['pillar']}] {r['desc']}")

    if lvl >= a.min_level:
        if not a.quiet:
            print(f"[pj-ready] PRÊT — orchestration autorisée (requis N{a.min_level}).")
        return 0
    print(f"[pj-ready] REFUS — niveau requis N{a.min_level}, atteint N{lvl}. "
          f"Compléter les manques ci-dessus avant de dispatcher un worker.")
    return 1


if __name__ == "__main__":
    sys.exit(main())