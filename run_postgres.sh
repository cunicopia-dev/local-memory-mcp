#!/bin/bash
# PostgreSQL + pgvector implementation runner

set -e

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
if ! python3 -c "import fastmcp, psycopg2, pgvector, requests" >/dev/null 2>&1; then
    pip install -r requirements.pgvector.txt
fi

# Run the PostgreSQL memory server
exec python3 src/postgres_memory_server.py