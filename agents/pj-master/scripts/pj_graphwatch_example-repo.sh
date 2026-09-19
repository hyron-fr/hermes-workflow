#!/usr/bin/env bash
export PJ_BOARD=pj-example-repo
exec python3 ${HOME}/.hermes/profiles/pj-master/scripts/pj_graphwatch.py run
