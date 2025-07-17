#!/bin/bash

dn="$(dirname "$(realpath "${BASH_SOURCE[0]}")")"

cd "$dn"

cd ..

pnpx concurrently --kill-others-on-fail "cd frontend && pnpm run dev" "./__inenv python backend/app.py" 