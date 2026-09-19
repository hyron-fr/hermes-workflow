#!/usr/bin/env python3
"""Adapte la config d'un nouveau profil pj depuis pj-dev (provider + memory + toolsets).

La clé API n'est JAMAIS réécrite à la main : le fichier source est copié, ce qui
préserve la valeur réelle (un `read_file` la masque en `sk-…`, et une valeur inventée
produit un 401 au premier appel).

Usage : pj_profile_config.py <profil>
"""
import os
import sys

import yaml

SRC = os.path.expanduser("~/.hermes/profiles/pj-dev/config.yaml")
PROFILES_ROOT = os.path.expanduser("~/.hermes/profiles")


def build(cfg: dict) -> dict:
    """Config d'un profil worker pj : provider/memory/toolsets, sans bot Discord."""
    out = dict(cfg or {})
    out.setdefault("model", {})
    out.setdefault("providers", {})
    out["memory"] = {"provider": "hindsight"}
    out["kanban"] = {"dispatch_in_gateway": True}
    out["toolsets"] = ["kanban", "file", "terminal", "web", "skills",
                       "memory", "delegation", "session_search", "code_execution", "todo"]
    out.setdefault("agent", {})["max_turns"] = 150
    out["plugins"] = {"enabled": []}       # aucun bot Discord sur ces profils
    out.pop("discord", None)
    out.pop("platform_toolsets", None)
    return out


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: pj_profile_config.py <profil>")
        return 2
    prof = sys.argv[1]
    dest_dir = os.path.join(PROFILES_ROOT, prof)
    if not os.path.isdir(dest_dir):
        print(f"profil {prof} absent ({dest_dir})")
        return 1
    if not os.path.exists(SRC):
        print(f"source absente: {SRC}")
        return 1
    cfg = yaml.safe_load(open(SRC)) or {}
    dest = os.path.join(dest_dir, "config.yaml")
    with open(dest, "w") as f:
        yaml.dump(build(cfg), f, default_flow_style=False, sort_keys=False, allow_unicode=True)
    print(f"{dest} écrit (provider={build(cfg)['model'].get('provider')})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
