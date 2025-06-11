# PostgreSQL + pgvector Migration Plan

## Overview

Migration from SQLite/FAISS to PostgreSQL with pgvector extension to enable domain-segmented memory storage with better scalability and native vector operations.

## Current vs Target Architecture

### Current: SQLite + FAISS + Ollama
```
┌─────────────┐    ┌──────────────┐    ┌─────────────┐
│   SQLite    │    │    FAISS     │    │   Ollama    │
│ (metadata)  │    │ (vectors)    │    │(embeddings) │
└─────────────┘    └──────────────┘    └─────────────┘
```

### Target: PostgreSQL + pgvector + Ollama
```
┌─────────────────────────────────────┐    ┌─────────────┐
│           PostgreSQL                │    │   Ollama    │
│  ┌─────────────┐ ┌─────────────┐   │    │(embeddings) │
│  │ startup_mem │ │ health_mem  │   │    │             │
│  │ (pgvector)  │ │ (pgvector)  │   │    │             │
│  └─────────────┘ └─────────────┘   │    │             │
└─────────────────────────────────────┘    └─────────────┘
```

## Key Benefits

### 1. Domain Segmentation
- **Separate tables per domain** (e.g., `startup_memories`, `health_memories`)
- **Improved retrieval accuracy** - queries stay within relevant context
- **Efficient querying** - smaller search space per domain
- **Logical separation** - different embedding strategies per domain possible

### 2. Technical Advantages
- **Native vector operations** - no separate FAISS index management
- **ACID compliance** - transactional safety for updates
- **Better concurrency** - multiple clients can access safely
- **Scalability** - PostgreSQL performance characteristics
- **Unified storage** - metadata + vectors in single system

### 3. Operational Benefits
- **Simpler backup/restore** - single database system
- **Better monitoring** - standard PostgreSQL tooling
- **Network accessibility** - remote database support
- **Replication support** - built-in PostgreSQL features

## Database Schema Design

### Core Table Structure
Each domain table follows identical schema:

```sql
CREATE TABLE {domain}_memories (
    id VARCHAR(50) PRIMARY KEY,
    content TEXT NOT NULL,
    embedding VECTOR(768),  -- pgvector type, adjust dim as needed
    metadata JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX ON {domain}_memories USING ivfflat (embedding vector_cosine_ops);
CREATE INDEX ON {domain}_memories USING gin (metadata);
CREATE INDEX ON {domain}_memories (updated_at DESC);
CREATE INDEX ON {domain}_memories USING gin (to_tsvector('english', content));
```

### Metadata Structure (JSONB)
```json
{
    "source": "conversation",
    "importance": 0.8,
    "chunk_index": 0,
    "created_at": 1703123456.789,
    "updated_at": 1703123456.789
}
```

## API Changes Required

### Function Signatures
```python
# Current
store_memory(content: str, source: Optional[str] = None, importance: Optional[float] = None) -> str

# New  
store_memory(content: str, domain: str, source: Optional[str] = None, importance: Optional[float] = None) -> str

# Current
search_memories(query: str, limit: Optional[int] = 5, use_vector: Optional[bool] = True) -> List[Dict]

# New
search_memories(query: str, domain: str, limit: Optional[int] = 5) -> List[Dict]
```

### Usage Examples
```python
# Store in different domains
store_memory("Series A funding round completed", "startup", "meeting_notes", 0.9)
store_memory("Blood pressure: 120/80", "health", "doctor_visit", 0.7)

# Search within specific domain
search_memories("funding strategy", "startup", 5)
search_memories("blood pressure trends", "health", 3)
```

## Implementation Strategy

### Phase 1: Database Setup
1. **Install PostgreSQL + pgvector**
2. **Create initial database and first domain table**
3. **Test vector operations and indexing**

### Phase 2: Core Migration
1. **Replace MemoryStore class**
   - Swap SQLite connections for PostgreSQL
   - Replace FAISS operations with pgvector SQL
   - Add domain parameter handling

2. **Update vector operations**
   - Embedding storage: Direct INSERT with vector type
   - Similarity search: `ORDER BY embedding <=> query_vector`
   - Updates: Standard SQL UPDATE with vector replacement

3. **Preserve API compatibility**
   - Keep existing function signatures working
   - Add domain parameter with sensible defaults
   - Maintain fallback behavior patterns

### Phase 3: Enhanced Features
1. **Multi-domain support**
2. **Performance optimization**
3. **Migration utilities**

## SQL Setup Scripts

### Initial Database Setup
```sql
-- setup_database.sql
CREATE EXTENSION IF NOT EXISTS vector;

-- Function to create standardized domain tables
CREATE OR REPLACE FUNCTION create_domain_memories_table(domain_name TEXT)
RETURNS VOID AS $$
BEGIN
    EXECUTE format('
        CREATE TABLE IF NOT EXISTS %I_memories (
            id VARCHAR(50) PRIMARY KEY,
            content TEXT NOT NULL,
            embedding VECTOR(768),
            metadata JSONB NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )', domain_name);
    
    -- Create indexes
    EXECUTE format('CREATE INDEX IF NOT EXISTS %I_memories_embedding_idx 
                   ON %I_memories USING ivfflat (embedding vector_cosine_ops)', 
                   domain_name, domain_name);
    
    EXECUTE format('CREATE INDEX IF NOT EXISTS %I_memories_metadata_idx 
                   ON %I_memories USING gin (metadata)', 
                   domain_name, domain_name);
    
    EXECUTE format('CREATE INDEX IF NOT EXISTS %I_memories_updated_idx 
                   ON %I_memories (updated_at DESC)', 
                   domain_name, domain_name);
                   
    EXECUTE format('CREATE INDEX IF NOT EXISTS %I_memories_content_idx 
                   ON %I_memories USING gin (to_tsvector(''english'', content))', 
                   domain_name, domain_name);
END;
$$ LANGUAGE plpgsql;

-- Create first domain table
SELECT create_domain_memories_table('default');
```

### Common Operations
```sql
-- search_operations.sql

-- Semantic search within domain
SELECT id, content, metadata, 
       1 - (embedding <=> %s::vector) AS similarity_score
FROM {domain}_memories 
WHERE embedding IS NOT NULL
ORDER BY embedding <=> %s::vector 
LIMIT %s;

-- Fallback text search within domain
SELECT id, content, metadata, 0.0 as similarity_score
FROM {domain}_memories 
WHERE to_tsvector('english', content) @@ plainto_tsquery('english', %s)
ORDER BY updated_at DESC 
LIMIT %s;

-- Insert new memory
INSERT INTO {domain}_memories (id, content, embedding, metadata)
VALUES (%s, %s, %s::vector, %s::jsonb);

-- Update existing memory
UPDATE {domain}_memories 
SET content = %s, embedding = %s::vector, metadata = %s::jsonb, updated_at = NOW()
WHERE id = %s;
```

## Configuration Changes

### Environment Variables
```bash
# Database connection
POSTGRES_HOST=localhost
POSTGRES_PORT=5432  
POSTGRES_DB=memory_store
POSTGRES_USER=memory_user
POSTGRES_PASSWORD=secure_password

# Existing Ollama config
OLLAMA_API_URL=http://localhost:11434
OLLAMA_EMBEDDING_MODEL=nomic-embed-text

# Default domain for backward compatibility
DEFAULT_MEMORY_DOMAIN=default
```

### Connection Management
```python
import psycopg2
from psycopg2.extras import RealDictCursor
import os

class PostgresMemoryStore:
    def __init__(self):
        self.connection_params = {
            'host': os.getenv('POSTGRES_HOST', 'localhost'),
            'port': os.getenv('POSTGRES_PORT', 5432),
            'database': os.getenv('POSTGRES_DB', 'memory_store'),
            'user': os.getenv('POSTGRES_USER', 'memory_user'),
            'password': os.getenv('POSTGRES_PASSWORD', ''),
        }
        self.default_domain = os.getenv('DEFAULT_MEMORY_DOMAIN', 'default')
```

## Migration Path

### 1. Parallel Development
- Keep existing SQLite/FAISS system running
- Develop PostgreSQL version alongside
- Test with sample data

### 2. Data Migration Utility
```python
def migrate_sqlite_to_postgres():
    """Migrate existing SQLite data to PostgreSQL default domain"""
    # Read from existing SQLite
    # Generate embeddings if missing
    # Insert into default_memories table
    # Verify data integrity
```

### 3. Gradual Rollout
- Deploy with feature flag
- Migrate existing users gradually  
- Monitor performance and accuracy
- Full cutover after validation

## Testing Strategy

### 1. Unit Tests
- Database connection handling
- Vector operations (insert, search, update)
- Domain table management
- Error handling and fallbacks

### 2. Integration Tests  
- End-to-end memory operations
- Multi-domain scenarios
- Performance under load
- Data consistency checks

### 3. Migration Testing
- SQLite → PostgreSQL data migration
- Backward compatibility verification
- Performance comparison benchmarks

## Risk Mitigation

### 1. Backward Compatibility
- Maintain existing API signatures
- Default domain for single-domain usage
- Graceful degradation patterns

### 2. Performance Concerns
- Proper indexing strategy
- Connection pooling
- Query optimization
- Monitoring and alerting

### 3. Operational Risks
- Database backup/restore procedures
- High availability setup considerations
- Migration rollback procedures
- Data validation and integrity checks

## Success Metrics

### 1. Performance
- Query response time < 100ms for vector search
- Support for 10K+ memories per domain
- Concurrent user support without degradation

### 2. Accuracy
- Retrieval accuracy maintained or improved
- Domain segmentation improves relevance scores
- No data loss during migration

### 3. Usability
- Seamless API transition
- Multi-domain workflows enabled
- Simplified deployment and operations

## Next Steps

1. **Environment Setup**: PostgreSQL + pgvector installation and configuration
2. **Proof of Concept**: Single domain table with basic operations
3. **Core Implementation**: PostgresMemoryStore class development
4. **Testing**: Comprehensive test suite development
5. **Migration Tools**: Data migration and validation utilities
6. **Documentation**: API documentation and deployment guides
7. **Rollout**: Gradual migration and monitoring plan