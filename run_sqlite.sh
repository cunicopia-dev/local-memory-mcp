#!/bin/bash
# SQLite + FAISS implementation runner

set -e

# Get the directory of this script and change to it
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Check if virtual environment exists and activate it
if [[ -f ".venv/bin/activate" ]]; then
    source .venv/bin/activate
fi

# Load environment variables if .env exists
if [[ -f .env ]]; then
    set -a
    source .env
    set +a
fi

# Install dependencies if needed
if ! python3 -c "import fastmcp, sqlite3, faiss, numpy, requests" >/dev/null 2>&1; then
    pip install -r requirements.sqlite.txt
fi

# Run the SQLite memory server
exec python3 src/sqlite_memory_server.py
