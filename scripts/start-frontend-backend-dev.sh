#!/bin/bash

dn="$(dirname "$(realpath "${BASH_SOURCE[0]}")")"

cd "$dn"

cd ..

pnpx concurrently "cd frontend && pnpm run dev" "./__python backend/app.py" 