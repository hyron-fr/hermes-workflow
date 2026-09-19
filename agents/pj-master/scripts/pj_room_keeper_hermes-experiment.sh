#!/usr/bin/env bash
# Tick du keeper de rooms pour un board : ensure -> ask -> report -> disband.
export PATH="$HOME/.local/bin:$PATH"
export PJ_BOARD=pj-hermes-experiment
exec python3 "$HOME/.hermes/profiles/pj-master/scripts/pj_room_keeper.py"
