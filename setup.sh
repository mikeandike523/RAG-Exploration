#!/bin/bash

set -e

python3 -m virtualenv .venv

chmod +x ./__inenv

chmod +x ./__hfcli

chmod +x ./RAG/flanking-paragraphs/__inenv

./__inenv pip install  -r requirements.txt

set +e