#!/bin/bash

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# Change to the script directory
cd "$SCRIPT_DIR"

# Create data directory if it doesn't exist
mkdir -p data

# Use Docker on Windows via docker.exe
echo "Building and starting containers using Windows Docker..."
docker.exe compose -f "$SCRIPT_DIR/docker-compose.yml" up -d

# Show the logs
echo "Showing container logs..."
docker.exe compose -f "$SCRIPT_DIR/docker-compose.yml" logs -f