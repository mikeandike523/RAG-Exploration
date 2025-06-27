#!/bin/bash

python3 -m virtualenv .venv

chmod +x ./__inenv

chmod +x ./__hfcli

./__inenv pip install  -r requirements.txt
