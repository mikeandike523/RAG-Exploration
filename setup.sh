#!/bin/bash

set -e

python3 -m virtualenv .venv

chmod +x ./__inenv

./__inenv pip install  -r requirements.txt

set +e