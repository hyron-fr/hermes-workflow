#!/usr/bin/env bash
export PJ_BOARD=pj-example-repo
exec python3 ${HOME}/.hermes/scripts/pj_pipeline_deployer.py run
