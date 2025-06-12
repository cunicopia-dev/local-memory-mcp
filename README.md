# Local Context Memory MCP

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![MCP Compatible](https://img.shields.io/badge/MCP-Compatible-green.svg)](https://modelcontextprotocol.io/)  
[![Docker Support](https://img.shields.io/badge/Docker-Supported-green.svg)](https://www.docker.com/)

Ever wanted the ChatGPT memory feature but **across all your LLMs** and stored on **your own hardware**? Ever hate how there's a **limit to how many memories** ChatGPT can store, and that you **can't segment your memories** into different domains? 

**Here's your fix.**

> **Give any AI assistant persistent, unlimited memory that you control completely.**

A production-ready persistent memory system for AI agents using the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/). Works with Claude Desktop, any MCP-compatible client, and gives you the memory features you've been wanting.

## Table of Contents

- [Why This Matters](#why-this-matters)
- [Choose Your Implementation](#choose-your-implementation)
- [Tools & Capabilities](#tools--capabilities)
  - [Available Tools](#available-tools)
  - [Available Resources](#available-resources)
  - [Available Prompts](#available-prompts)
- [Architecture Diagrams](#architectures)
  - [SQLite + FAISS Implementation](#sqlite--faiss-implementation-original)
  - [PostgreSQL + pgvector Implementation](#postgresql--pgvector-implementation-new)
- [Features](#features)
- [Quick Start](#quick-start)
  - [Prerequisites](#prerequisites)
  - [Ollama Setup](#ollama-setup-optional-but-recommended)
- [Claude Desktop Setup](#claude-desktop-setup)
- [Examples](#examples)
- [Components](#components)
- [Configuration](#configuration)
- [Development](#development)
  - [Docker](#docker)
- [Manual Installation](#manual-installation)
- [Demo](#demo)
- [License](#license)

## Why This Matters

**Traditional AI Problem**: AI assistants forget everything between conversations. Every interaction starts from scratch, requiring users to repeatedly provide context about their preferences, projects, and history.

**Solution**: Local Context Memory gives your AI persistent, searchable memory that:
- 🧠 **Remembers across sessions** - User preferences, project details, conversation history
- 🎯 **Finds relevant context** - Semantic search surfaces the right memories at the right time  
- 🏢 **Organizes by domain** - Separate contexts for work, health, personal life (PostgreSQL)
- 🔒 **Stays private** - All data stored locally under your control
- ⚡ **Works immediately** - Drop-in compatibility with Claude Desktop and MCP clients

## Choose Your Implementation

- **SQLite + FAISS**: Perfect for personal use, development, and simple deployments
- **PostgreSQL + pgvector**: Production-ready with domain segmentation and team collaboration

## Tools & Capabilities

```mermaid
graph LR
    subgraph "Client"
        USER[User]
        CD[Claude Desktop]
    end
    
    subgraph "MCP Server"
        subgraph "Tools"
            SM[store_memory]
            UM[update_memory]
            SRCH[search_memories]
            LMD[list_memory_domains]
        end
        
        subgraph "Resources"
            RES_SQL[memory://query]
            RES_PG[memory://domain/query]
        end
        
        subgraph "Prompts"
            SUM[summarize_memories]
        end
    end
    
    subgraph "Domain Context"
        DC[PostgreSQL Only]
        DC2[Multi-domain isolation:<br/>startup, health, personal]
    end
    
    USER --> CD
    CD -->|MCP Protocol| SM
    CD -->|MCP Protocol| UM
    CD -->|MCP Protocol| SRCH
    CD -->|MCP Protocol| LMD
    CD -->|MCP Protocol| RES_SQL
    CD -->|MCP Protocol| RES_PG
    CD -->|MCP Protocol| SUM
    
    LMD -.->|Available in| DC
    RES_PG -.->|Available in| DC
    DC --> DC2
    
    classDef client fill:#e3f2fd,stroke:#1976d2,stroke-width:2px,color:#0d47a1
    classDef server fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px,color:#4a148c
    classDef tool fill:#fff3e0,stroke:#f57c00,stroke-width:2px,color:#e65100
    classDef resource fill:#e8f5e8,stroke:#388e3c,stroke-width:2px,color:#1b5e20
    classDef prompt fill:#fce4ec,stroke:#c2185b,stroke-width:2px,color:#880e4f
    classDef domain fill:#f1f8e9,stroke:#689f38,stroke-width:2px,color:#33691e
    
    class USER,CD client
    class SM,UM,SRCH,LMD tool
    class RES_SQL,RES_PG resource
    class SUM prompt
    class DC,DC2 domain
```

### Available Tools

#### `store_memory`
Store new information in persistent memory with automatic semantic indexing.
- **SQLite**: `store_memory(content, source?, importance?)`
- **PostgreSQL**: `store_memory(content, domain?, source?, importance?)`
- **Examples**:
  - `"User prefers TypeScript over JavaScript for new projects"`
  - `"Weekly team meeting every Tuesday at 2 PM PST"`

#### `update_memory` 
Modify existing memories while preserving search indexing.
- **SQLite**: `update_memory(memory_id, content?, importance?)`
- **PostgreSQL**: `update_memory(memory_id, content?, importance?, domain?)`
- **Use case**: Update outdated information or change importance levels

#### `search_memories`
Find relevant memories using semantic or keyword search.
- **SQLite**: `search_memories(query, limit?, use_vector?)`
- **PostgreSQL**: `search_memories(query, domain?, limit?)`
- **Examples**: 
  - `"What programming languages does the user prefer?"`
  - `"Recent project decisions about database choices"`

#### `list_memory_domains` *(PostgreSQL Only)*
Discover available memory domains for organized context switching.
- **Returns**: `["default", "work", "health", "personal"]`
- **Use case**: Switch between different memory contexts

### Available Resources

#### `memory://query` *(SQLite)*
Quick semantic search via URI pattern for simple memory retrieval.

#### `memory://domain/query` *(PostgreSQL)*
Domain-scoped semantic search for isolated memory contexts.
- **Examples**:
  - `memory://work/project deadlines`
  - `memory://health/medication schedule`

### Available Prompts

#### `summarize_memories`
Generate intelligent summaries of retrieved memory collections.
- **Input**: List of memory objects
- **Output**: Structured summary highlighting key patterns and insights
- **Use case**: Create context summaries for complex topics

## Architectures

### SQLite + FAISS Implementation (Original)

```mermaid
graph TB
    subgraph "Client Layer"
        CD[Claude Desktop]
        AI[AI Agent]
    end
    
    subgraph "MCP Server Layer"
        SMS[SQLite Memory Server]
    end
    
    subgraph "API Layer" 
        SMA[SQLite Memory API]
        SVA[SQLite Vector API]
        OE[Ollama Embeddings]
        SC[Smart Chunker]
    end
    
    subgraph "Storage Layer"
        SQL[(SQLite Database)]
        FAISS[(FAISS Index)]
    end
    
    subgraph "External Services"
        OL[Ollama API]
        EM[nomic-embed-text]
    end
    
    CD -->|MCP Protocol| SMS
    AI -->|HTTP/JSON-RPC| SMS
    
    SMS --> SMA
    SMA --> SVA
    SVA --> SC
    SVA --> OE
    
    SMA -->|Store Metadata| SQL
    SVA -->|Vector Operations| FAISS
    
    OE -->|Generate Embeddings| OL
    OL --> EM
    
    classDef client fill:#e3f2fd,stroke:#1976d2,stroke-width:2px,color:#0d47a1
    classDef server fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px,color:#4a148c
    classDef api fill:#fff3e0,stroke:#f57c00,stroke-width:2px,color:#e65100
    classDef storage fill:#e8f5e8,stroke:#388e3c,stroke-width:2px,color:#1b5e20
    classDef external fill:#fce4ec,stroke:#c2185b,stroke-width:2px,color:#880e4f
    
    class CD,AI client
    class SMS server
    class SMA,SVA,OE,SC api
    class SQL,FAISS storage
    class OL,EM external
```

### PostgreSQL + pgvector Implementation (New)

```mermaid
graph TB
    subgraph "Client Layer"
        CD[Claude Desktop]
        AI[AI Agent]
    end
    
    subgraph "MCP Server Layer"
        PMS[PostgreSQL Memory Server]
    end
    
    subgraph "API Layer"
        PMA[PostgreSQL Memory API]
        OE[Ollama Embeddings]
    end
    
    subgraph "PostgreSQL Database"
        subgraph "Domain Tables"
            DT1[default_memories]
            DT2[startup_memories]
            DT3[health_memories]
        end
        PGV[pgvector Extension]
    end
    
    subgraph "External Services"
        OL[Ollama API]
        EM[nomic-embed-text]
    end
    
    CD -->|MCP Protocol| PMS
    AI -->|HTTP/JSON-RPC| PMS
    
    PMS --> PMA
    PMA --> OE
    PMA -->|SQL + Vector Ops| PGV
    PGV --> DT1
    PGV --> DT2
    PGV --> DT3
    
    OE -->|Generate Embeddings| OL
    OL --> EM
    
    classDef client fill:#e3f2fd,stroke:#1976d2,stroke-width:2px,color:#0d47a1
    classDef server fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px,color:#4a148c
    classDef api fill:#fff3e0,stroke:#f57c00,stroke-width:2px,color:#e65100
    classDef storage fill:#e8f5e8,stroke:#388e3c,stroke-width:2px,color:#1b5e20
    classDef external fill:#fce4ec,stroke:#c2185b,stroke-width:2px,color:#880e4f
    
    class CD,AI client
    class PMS server
    class PMA,OE api
    class DT1,DT2,DT3,PGV storage
    class OL,EM external
```
## Features

### Common Features
- **Semantic Search**: Uses Ollama embeddings for intelligent memory retrieval
- **Smart Chunking**: Automatically breaks down long text for better search results  
- **MCP Standard**: Full MCP protocol compliance for Claude Desktop integration
- **Docker Ready**: Simple containerized deployment with self-contained images
- **Fallback Search**: Automatic fallback to text search when vector search unavailable

### SQLite + FAISS Specific
- **Local Storage**: Everything runs locally with SQLite + FAISS files
- **Zero Setup**: No database server required
- **Portable**: Single directory contains all data

### PostgreSQL + pgvector Specific  
- **Domain Segmentation**: Separate memory contexts (startup, health, personal, etc.)
- **Production Ready**: ACID compliance, concurrent access, replication support
- **Native Vector Ops**: Efficient similarity search without separate index files
- **Scalable**: Handles large datasets with proper indexing

## Quick Start

🚀 **Recommended: Use Docker for the easiest setup!** Skip all dependency management and get running in seconds.

### Option 1: Docker (Recommended) ⭐

**SQLite Version** (simplest):
```bash
# Run immediately - no setup required!
docker run --rm -i -v ./memory-data:/app/data cunicopia/local-memory-mcp:sqlite
```

**PostgreSQL Version** (with domain segmentation):
```bash
# Run immediately - includes full PostgreSQL database!
docker run --rm -i -v ./postgres-data:/var/lib/postgresql/data cunicopia/local-memory-mcp:postgres
```

That's it! The containers are self-contained and handle all dependencies automatically.


### Prerequisites
- Docker (for containerized deployment) or Python 3.12+ (for local installation)
- Ollama with `nomic-embed-text` model (optional but recommended for enhanced semantic search)

### Ollama Setup (Optional but Recommended)

Ollama enables enhanced semantic search with vector embeddings. Without it, the system falls back to text-based search.

**Installation:**
- **macOS/Windows**: Download installer from [ollama.com/download](https://ollama.com/download)
- **Linux**: `curl -fsSL https://ollama.com/install.sh | sh`

**Setup:**
```bash
# Install the embedding model
ollama pull nomic-embed-text:v1.5

# Verify it's running (should show localhost:11434)
curl http://localhost:11434/api/tags
```

**System Requirements:**
- At least 4GB disk space for Ollama
- Additional 2-8GB for the embedding model
- Ollama runs on `http://localhost:11434` by default

### Setup & Installation

## Claude Desktop Setup

Once you have the Docker containers ready (or local installation), connect to Claude Desktop by adding this to your MCP settings:

### Docker Configuration (Recommended)
```json
{
  "mcpServers": {
    "localMemoryMCP-SQLite": {
      "command": "docker",
      "args": ["run", "--rm", "-i", "-v", "/path/to/your/memory-data:/app/data", "cunicopia/local-memory-mcp:sqlite"]
    },
    
    "localMemoryMCP-PostgreSQL": {
      "command": "docker", 
      "args": ["run", "--rm", "-i", "-v", "/path/to/your/postgres-data:/var/lib/postgresql/data", "cunicopia/local-memory-mcp:postgres"]
    }
  }
}
```

**Volume Paths:** Replace `/path/to/your/memory-data` and `/path/to/your/postgres-data` with any directory where you want to store your memories (e.g., `~/Documents/memory-data`, `/Users/yourname/my-memories`, etc.)

### Local Installation Configuration (Alternative)

**Note:** Only use if you cannot use Docker. Requires manual setup first (see [Manual Installation](#manual-installation)).

```json
{
  "mcpServers": {
    "localMemoryMCP": {
      "command": "bash",
      "args": ["/path/to/local-memory-mcp/run_sqlite.sh"]
    }
  }
}
```



## Examples

### SQLite Implementation
```javascript
// Store a memory
store_memory(
  "User prefers Python for backend development", 
  "conversation", 
  0.8
)

// Search memories
search_memories("programming preferences", 5, true)

// Get memories via resource
// Access: memory://programming
```

### PostgreSQL Implementation
```javascript
// List available domains
list_memory_domains()
// Returns: ["default", "startup", "health"]

// Store memories in different domains
store_memory(
  "Series A funding closed at $10M",
  "startup",  // domain
  "meeting",   // source
  0.9         // importance
)

store_memory(
  "User has peanut allergy",
  "health",
  "medical_record",
  1.0
)

// Search within specific domain
search_memories("funding", "startup", 5)

// Get memories via resource
// Access: memory://startup/funding%20strategy
```

## Components

### SQLite Implementation
- **FastMCP**: Python MCP server framework
- **SQLite**: Structured metadata and text search fallback
- **FAISS**: Vector similarity search
- **Ollama**: Local embedding generation (optional)
- **Smart Chunker**: Text processing for optimal retrieval

### PostgreSQL Implementation
- **FastMCP**: Python MCP server framework  
- **PostgreSQL**: Full database with metadata and vector storage
- **pgvector**: Native PostgreSQL vector similarity search
- **Ollama**: Local embedding generation (optional)
- **Domain Tables**: Isolated memory contexts for better organization

## Configuration

### Common Environment Variables
- `OLLAMA_API_URL`: Ollama endpoint (default: `http://localhost:11434`)
- `OLLAMA_EMBEDDING_MODEL`: Model name (default: `nomic-embed-text`)
- `MCP_SERVER_NAME`: Server name for MCP (default: `Local Context Memory`)

### SQLite Specific
- `MCP_DATA_DIR`: Data storage path (default: `./data`)

### PostgreSQL Specific
- `POSTGRES_HOST`: Database host (default: `localhost`)
- `POSTGRES_PORT`: Database port (default: `5432`)
- `POSTGRES_DB`: Database name (default: `postgres`)
- `POSTGRES_USER`: Database user (default: `postgres`)
- `POSTGRES_PASSWORD`: Database password (required)
- `DEFAULT_MEMORY_DOMAIN`: Default domain for memories (default: `default`)

## Development

### SQLite Version
```bash
pip install -r requirements.sqlite.txt
python src/sqlite_memory_server.py
```

### PostgreSQL Version
```bash
pip install -r requirements.pgvector.txt
python src/postgres_memory_server.py
```

### Docker

Docker support is fully functional with self-contained containers! Both SQLite and PostgreSQL versions run completely independently.

```bash
# Run pre-built images directly (recommended)
# SQLite version - replace './data' with your preferred data directory
docker run --rm -i -v ./data:/app/data cunicopia/local-memory-mcp:sqlite

# PostgreSQL version - replace './postgres_data' with your preferred data directory  
docker run --rm -i -v ./postgres_data:/var/lib/postgresql/data cunicopia/local-memory-mcp:postgres
```

**Building from source (optional):**
```bash
# Only needed if you want to build yourself
docker build -f Dockerfile.sqlite_version -t local-memory-mcp:sqlite_version .
docker build -f Dockerfile.postgres_version -t local-memory-mcp:postgres_version .
```

## Manual Installation

⚠️ **We strongly recommend using Docker instead** - it handles all dependencies automatically. Use this section only if Docker is not available or you have specific requirements.

### SQLite + FAISS (Simple, Local)
```bash
git clone https://github.com/cunicopia-dev/local-memory-mcp
cd local-memory-mcp
pip install -r requirements.sqlite.txt
python src/sqlite_memory_server.py
```

### PostgreSQL + pgvector (Production, Scalable)

**For Debian-based systems:**
```bash
# Install PostgreSQL + pgvector
sudo apt install postgresql postgresql-contrib
sudo apt install postgresql-17-pgvector  # Adjust version as needed

# Change directory to where you downloaded the repo
cd /path/to/local-memory-mcp

# Set up database
# PLEASE NOTE: We create a user and basic password here, please change this if you want to host it locally
psql < sql/create_user.sql
psql -U postgres < sql/setup_database.sql

# Install Python dependencies
pip install -r requirements.pgvector.txt

# Configure connection (edit .env file)
cp .env.example .env

# Run server
python src/postgres_memory_server.py
```

**For macOS:**
```bash
# Install PostgreSQL and pgvector (Homebrew-based)
brew install postgresql@17
brew services start postgresql@17

# Link psql and other tools if needed
brew link --force postgresql@17

# Install pgvector extension (PostgreSQL must be running)
# This installs the extension into your local PostgreSQL environment
brew install pgvector

# OPTIONAL: If pgvector doesn't register properly, you can manually build it
# git clone --branch v0.8.0 https://github.com/pgvector/pgvector.git
# cd pgvector
# make && make install

# PLEASE NOTE: We create a user and basic password here, please change this if you want to host it locally
psql < sql/create_user.sql

# Set up database
psql -U postgres -f sql/setup_database.sql

# Install Python dependencies
pip install -r requirements.pgvector.txt

# Configure connection (edit .env file)
cp .env.example .env

# Run server
python src/postgres_memory_server.py
```

**⚠️ SECURITY CAUTION:** Please go to sql/create_user.sql and create a more secure user and password, the ones listed are for example purposes only! Please protect your data and take your data security seriously.

## License

MIT License

## Demo

See the local memory system in action:

### Example 1
![Example 1](docs/pictures/memory_example1.png)


### Example 2 
![Example 2](docs/pictures/memory_example2.png)

