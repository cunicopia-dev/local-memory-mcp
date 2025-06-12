#!/bin/bash
set -e

# Save original stdout and redirect setup output to stderr
exec 3>&1
exec 1>&2

# Switch to postgres user for database operations
sudo() {
    su postgres -c "$*"
}

# Initialize PostgreSQL if data directory is empty
if [ ! -s "$PGDATA/PG_VERSION" ]; then
    echo "Initializing PostgreSQL database..."
    sudo "/usr/lib/postgresql/15/bin/initdb -D $PGDATA"
    
    # Start PostgreSQL temporarily for setup
    sudo "/usr/lib/postgresql/15/bin/pg_ctl -D $PGDATA -o '-c listen_addresses=localhost' -w start"
    
    # Create database and extensions
    sudo "/usr/lib/postgresql/15/bin/psql -c \"CREATE EXTENSION IF NOT EXISTS vector;\""
    
    # Run setup SQL if it exists
    if [ -f sql/setup_database.sql ]; then
        sudo "/usr/lib/postgresql/15/bin/psql -f sql/setup_database.sql"
    fi
    
    # Stop temporary PostgreSQL
    sudo "/usr/lib/postgresql/15/bin/pg_ctl -D $PGDATA -m fast -w stop"
fi

# Start PostgreSQL in background
sudo "/usr/lib/postgresql/15/bin/pg_ctl -D $PGDATA -o '-c listen_addresses=localhost' -w start"

# Wait for PostgreSQL to be ready
until sudo "/usr/lib/postgresql/15/bin/pg_isready -h localhost -p 5432"; do
    echo "Waiting for PostgreSQL to be ready..."
    sleep 1
done

echo "PostgreSQL is ready. Starting MCP server..."

# Restore original stdout for the MCP server
exec 1>&3

# Start the MCP server
exec python3 src/postgres_memory_server.py