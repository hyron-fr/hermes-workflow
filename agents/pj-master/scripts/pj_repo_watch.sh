#!/usr/bin/env bash
export PATH="$HOME/.local/bin:$PATH"
exec python3 ${HOME}/.hermes/profiles/pj-master/scripts/pj_repo_watch.py
