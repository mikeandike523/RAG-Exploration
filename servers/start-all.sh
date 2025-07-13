#!/bin/bash

dn="$(dirname "$(realpath "${BASH_SOURCE[0]}")")"

cd "$dn"

cd mysql

docker compose down -v
docker compose up -d

cd ..

cd qdrant

docker compose down -v
docker compose up -d

cd ..

cd redis

docker compose down -v
docker compose up -d

cd ..

echo "All services have been started successfully!"

