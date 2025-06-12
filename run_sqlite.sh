#!/bin/bash
# SQLite + FAISS implementation runner

set -e

# Check if virtual environment exists and activate it
if [[ -f ".venv/bin/activate" ]]; then
    source .venv/bin/activate
fi

# Install dependencies if needed
if ! python3 -c "import fastmcp, sqlite3, faiss, numpy, requests" >/dev/null 2>&1; then
    pip install -r requirements.sqlite.txt
fi

# Run the SQLite memory server
exec python3 src/sqlite_memory_server.py