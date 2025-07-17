#!/bin/bash

set -e

rm -rf .venv

python3 -m virtualenv .venv

chmod +x ./__inenv

./__inenv pip cache purge
./__inenv pip install --upgrade --force-reinstall -r requirements.txt
./__inenv pip install --upgrade --force-reinstall -r backend/requirements.txt

set +e