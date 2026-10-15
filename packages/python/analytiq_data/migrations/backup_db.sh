#!/bin/bash

# Get the directory of the script
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

# Navigate to the migrations directory
cd "$SCRIPT_DIR"

# Copy the prod database on app.docrouter.ai into the local test database.
# --src-uri is MongoDB on the server (localhost:27017 there). backup_db.py
# opens an SSH tunnel and forwards it to 127.0.0.1:27018 so it does not
# collide with the local destination on port 27017.
python3 ./backup_db.py \
    --ssh-host "app.docrouter.ai" \
    --ssh-user "ubuntu" \
    --ssh-key "${HOME}/.ssh/analytiq-code-admin.pem" \
    --src-uri "mongodb://localhost:27017/?directConnection=true" \
    --dest-uri "mongodb://localhost:27017/?directConnection=true" \
    --src "prod" \
    --dest "test" \
    --force
