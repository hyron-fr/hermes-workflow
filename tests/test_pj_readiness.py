"""Tests du gate de readiness (pj_readiness) — fixtures tmp, sans réseau."""
import importlib.util
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]

PATH = str(REPO / "pipeline" / "pj_readiness.py")

PASS_RATIO = 0.8  # règle Factory : N+1 exige >= 80 % des critères de N


@pytest.fixture(scope="module")
def rd():
    spec = importlib.util.spec_from_file_location("rd", PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def build(repo: Path, *relpaths: str) -> Path:
    """Crée une arborescence de fichiers vides (ou avec contenu si 'content:')."""
    for rel in relpaths:
        p = repo / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        if "::" in rel:
            target, content = rel.split("::", 1)
            (repo / target).write_text(content, encoding="utf-8")
        else:
            p.touch()
    return repo


def level_of(rd, repo: Path, online=False):
    return rd.evaluate(repo, online=online)["level"]


# ---------------------------------------------------------------- niveaux

def test_empty_repo_level0(rd, tmp_path):
    repo = tmp_path / "empty"
    repo.mkdir()
    report = rd.evaluate(repo)
    assert report["level"] == 0
    assert report["ratios"]["1"] == 0.0
    assert len(report["missing"]) > 0


def test_level1_complete(rd, tmp_path):
    repo = build(tmp_path / "l1",
                 "README.md", ".flake8", "mypy.ini", "pytest.ini", "Makefile",
                 "tests/test_a.py")
    assert level_of(rd, repo) == 1
    report = rd.evaluate(repo)
    assert report["ratios"]["1"] == 1.0


def test_level1_ratio_80_unlocks(rd, tmp_path):
    # 5/6 critères niveau 1 = 0.83 >= 0.8 → niveau 1 débloqué
    repo = build(tmp_path / "l1p",
                 "README.md", ".flake8", "mypy.ini", "Makefile",
                 "tests/test_a.py")  # pas de runner (pytest.ini absent)
    report = rd.evaluate(repo)
    assert report["ratios"]["1"] == pytest.approx(5 / 6, abs=0.01)
    assert level_of(rd, repo) == 1


def test_level1_80pct_exact_boundary(rd, tmp_path):
    # 4/6 = 0.667 < 0.8 → niveau 0 (règle stricte)
    repo = build(tmp_path / "l1f",
                 "README.md", ".flake8", "Makefile", "tests/test_a.py")
    report = rd.evaluate(repo)
    assert report["ratios"]["1"] < 0.8
    assert level_of(rd, repo) == 0


def test_level2_requires_level1(rd, tmp_path):
    # Niveau 2 complet mais niveau 1 incomplet → plafonné à 0
    repo = build(tmp_path / "l2only",
                 "AGENTS.md", ".env.example", "docker-compose.yml",
                 ".pre-commit-config.yaml", ".gitignore", ".git/config")
    assert level_of(rd, repo) == 0


def test_level2_80pct(rd, tmp_path):
    # N1 complet (6/6) + N2 à 4/5 = 0.8 → niveau 2
    repo = build(tmp_path / "l2",
                 "README.md", ".flake8", "mypy.ini", "pytest.ini", "Makefile",
                 "tests/test_a.py",
                 "AGENTS.md", ".env.example", "docker-compose.yml",
                 ".pre-commit-config.yaml", "no-gitignore.txt")
    (repo / ".git").mkdir(exist_ok=True)
    assert level_of(rd, repo) == 2
    assert rd.evaluate(repo)["ratios"]["2"] == pytest.approx(0.8, abs=0.01)


def test_level3_full(rd, tmp_path):
    repo = build(tmp_path / "l3",
                 "README.md", ".flake8", "mypy.ini", "pytest.ini", "Makefile",
                 "tests/test_a.py",
                 "AGENTS.md", ".env.example", "docker-compose.yml",
                 ".pre-commit-config.yaml", ".gitignore", ".git/config",
                 "tests/integration/test_flow.py", "CODEOWNERS",
                 ".gitleaks.toml", "docs/archi.md",
                 ".github/workflows/ci.yml::run: pytest\n")
    f = repo / "src" / "app.py"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("import structlog\nlog = structlog.get_logger()\n", encoding="utf-8")
    report = rd.evaluate(repo)
    assert level_of(rd, repo) == 3
    assert report["ratios"]["3"] == 1.0


def test_level4_full(rd, tmp_path):
    repo = build(tmp_path / "l4",
                 "README.md", ".flake8", "mypy.ini", "pytest.ini", "Makefile",
                 "tests/test_a.py",
                 "AGENTS.md", ".env.example", "docker-compose.yml",
                 ".pre-commit-config.yaml", ".gitignore", ".git/config",
                 "tests/integration/test_flow.py", "CODEOWNERS",
                 ".gitleaks.toml", "docs/archi.md",
                 "src/app.py::import structlog\n",
                 "pixi.lock",
                 ".github/workflows/ci.yml::run: pytest\ncache: npm\n",
                 "experiments/run1.json")
    assert level_of(rd, repo) == 4


# ---------------------------------------------------------------- critères clés

def test_missing_shows_next_level_gaps(rd, tmp_path):
    repo = build(tmp_path / "gap",
                 "README.md", ".flake8", "mypy.ini", "pytest.ini", "Makefile",
                 "tests/test_a.py")
    report = rd.evaluate(repo)
    missing_ids = {m["id"] for m in report["missing"]}
    # niveau atteint = 1 → on liste les manques jusqu'au niveau 2
    assert "agents_md" in missing_ids
    assert "deps_pinned" not in missing_ids  # niveau 4, hors portée


def test_ci_runs_tests_detected(rd, tmp_path):
    repo = build(tmp_path / "ci", ".github/workflows/ci.yml::"
                 "- run: python -m pytest tests/\n")
    assert rd._ci_runs_tests(repo) is True
    empty = tmp_path / "noci"
    empty.mkdir()
    assert rd._ci_runs_tests(empty) is False


def test_secret_scanning_via_workflow(rd, tmp_path):
    repo = build(tmp_path / "sec", ".github/workflows/leaks.yml::"
                 "- run: gitleaks detect\n")
    assert rd._secret_scanning(repo) is True


def test_observability_skip_junk_dirs(rd, tmp_path):
    junk = tmp_path / "obs" / "node_modules" / "x.js"
    junk.parent.mkdir(parents=True)
    junk.write_text("winston.createLogger()", encoding="utf-8")
    repo = tmp_path / "obs"
    assert rd._observability_signal(repo) is False
    src = repo / "app.py"
    src.write_text("log = structlog.get_logger()\n", encoding="utf-8")
    assert rd._observability_signal(repo) is True


def test_pyproject_sections(rd, tmp_path):
    repo = tmp_path / "pp"
    repo.mkdir()
    (repo / "pyproject.toml").write_text(
        "[project]\nname='x'\n[tool.pytest.ini_options]\ntestpaths=['tests']\n"
        "[tool.ruff]\nline-length=100\n", encoding="utf-8")
    sections = rd._pyproject_sections(repo)
    assert "[tool.ruff]" in sections and "[tool.pytest]" in sections


def test_evaluate_report_shape(rd, tmp_path):
    repo = build(tmp_path / "shape", "README.md")
    report = rd.evaluate(repo)
    for key in ("level", "max_level", "ratios", "criteria", "missing", "repo"):
        assert key in report
    entry = report["criteria"][0]
    for key in ("id", "level", "pillar", "desc", "passed"):
        assert key in entry


def test_branch_protection_only_online(rd, tmp_path):
    repo = build(tmp_path / "bp", "README.md")
    ids_off = {c["id"] for c in rd.evaluate(repo)["criteria"]}
    assert "branch_protection" not in ids_off


def test_main_exit_codes(rd, tmp_path, monkeypatch, capsys):
    # repo inexistant → 2
    monkeypatch.setattr("sys.argv",
                        ["pj_readiness.py", "--repo", str(tmp_path / "nope")])
    assert rd.main() == 2
    # repo vide, défaut --min-level 3 → 1
    repo = tmp_path / "empty"
    repo.mkdir()
    monkeypatch.setattr("sys.argv",
                        ["pj_readiness.py", "--repo", str(repo), "--quiet"])
    assert rd.main() == 1


def test_main_json_output(rd, tmp_path, monkeypatch):
    repo = build(tmp_path / "j", "README.md", ".flake8", "mypy.ini",
                 "pytest.ini", "Makefile", "tests/test_a.py",
                 "AGENTS.md", ".env.example", "docker-compose.yml",
                 ".pre-commit-config.yaml", ".gitignore", ".git/config")
    out = tmp_path / "report.json"
    monkeypatch.setattr("sys.argv",
                        ["pj_readiness.py", "--repo", str(repo),
                         "--min-level", "2", "--json", str(out), "--quiet"])
    assert rd.main() == 0
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["level"] == 2