#!/usr/bin/env bash
# Wrapper cron : deployer pipeline pour hyron-fr/hermes-experiment (board pj-hermes-experiment).
export PJ_BOARD=pj-hermes-experiment
exec python3 ${HOME}/.hermes/profiles/pj-master/scripts/pj_pipeline_deployer.py run
