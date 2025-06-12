# Docker Build and Release Guide

This document explains how to build and publish the Local Memory MCP Docker images.

## Prerequisites

- Docker Desktop installed and running
- Docker Hub account
- Docker logged in: `docker login`

## Building Images Locally

For local development and testing:

```bash
# Build SQLite version
docker build -f Dockerfile.sqlite_version -t local-memory-mcp:sqlite_version .

# Build PostgreSQL version  
docker build -f Dockerfile.postgres_version -t local-memory-mcp:postgres_version .

# Test locally
docker run --rm -i -v $(pwd)/data:/app/data local-memory-mcp:sqlite_version
docker run --rm -i -v $(pwd)/postgres_data:/var/lib/postgresql/data local-memory-mcp:postgres_version
```

## Building Multi-Platform Images for Release

### One-Time Setup

Create a buildx builder for multi-platform builds:

```bash
docker buildx create --name multiplatform --use
docker buildx inspect --bootstrap
```

### Build and Push to Docker Hub

Build for both ARM64 (Apple Silicon) and AMD64 (Intel) architectures:

```bash
# SQLite version - multi-platform build and push
docker buildx build --platform linux/amd64,linux/arm64 \
  -f Dockerfile.sqlite_version \
  -t cunicopia/local-memory-mcp:sqlite \
  --push .

# PostgreSQL version - multi-platform build and push
docker buildx build --platform linux/amd64,linux/arm64 \
  -f Dockerfile.postgres_version \
  -t cunicopia/local-memory-mcp:postgres \
  --push .
```

### Versioned Releases

For tagged releases, use version tags:

```bash
# Build with version tags (replace v1.0.0 with actual version)
docker buildx build --platform linux/amd64,linux/arm64 \
  -f Dockerfile.sqlite_version \
  -t cunicopia/local-memory-mcp:sqlite \
  -t cunicopia/local-memory-mcp:sqlite:v1.0.0 \
  --push .

docker buildx build --platform linux/amd64,linux/arm64 \
  -f Dockerfile.postgres_version \
  -t cunicopia/local-memory-mcp:postgres \
  -t cunicopia/local-memory-mcp:postgres:v1.0.0 \
  --push .
```

## Verifying Builds

Check that both architectures are available:

```bash
# Inspect the manifest to see available platforms
docker buildx imagetools inspect cunicopia/local-memory-mcp:sqlite
docker buildx imagetools inspect cunicopia/local-memory-mcp:postgres
```

You should see both `linux/amd64` and `linux/arm64` in the output.

## User Instructions

Once published, users can run the images directly without building:

```bash
# SQLite version
docker run --rm -i -v $(pwd)/data:/app/data cunicopia/local-memory-mcp:sqlite

# PostgreSQL version
docker run --rm -i -v $(pwd)/postgres_data:/var/lib/postgresql/data cunicopia/local-memory-mcp:postgres
```

## Troubleshooting

### Build Context Too Large
If builds are slow due to large context:
```bash
# Add to .dockerignore:
echo "*.git*" >> .dockerignore
echo "node_modules" >> .dockerignore
echo "*.md" >> .dockerignore
```

### Authentication Issues
```bash
# Re-login to Docker Hub
docker logout
docker login
```

### Platform Build Issues
```bash
# Reset buildx builder
docker buildx rm multiplatform
docker buildx create --name multiplatform --use
```

## CI/CD Integration

For automated builds, consider using GitHub Actions with the workflow in `.github/workflows/docker.yml` to automatically build and push on releases.