#!/usr/bin/env bash
# Wrapper cron : deployer pipeline pour hyron-fr/dino-game (board pj-dino-game).
export PJ_BOARD=pj-dino-game
exec python3 ${HOME}/.hermes/profiles/pj-master/scripts/pj_pipeline_deployer.py run
