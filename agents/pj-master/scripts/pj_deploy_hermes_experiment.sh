#!/usr/bin/env bash
export PJ_BOARD=pj-hermes-experiment
exec python3 ${HOME}/.hermes/scripts/pj_pipeline_deployer.py run
