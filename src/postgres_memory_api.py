import os
import time
import json
import psycopg2
from psycopg2.extras import RealDictCursor, Json
from psycopg2 import sql
import numpy as np
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class PostgresMemoryAPI:
    def __init__(self, ollama_embeddings=None):
        """Initialize PostgreSQL memory store with connection parameters."""
        self.connection_params = {
            'host': os.getenv('POSTGRES_HOST', 'localhost'),
            'port': os.getenv('POSTGRES_PORT', 5432),
            'database': os.getenv('POSTGRES_DB', 'postgres'),
            'user': os.getenv('POSTGRES_USER', 'postgres'),
            'password': os.getenv('POSTGRES_PASSWORD', 'postgres'),
        }
        self.default_domain = os.getenv('DEFAULT_MEMORY_DOMAIN', 'default')
        self.ollama_embeddings = ollama_embeddings
        
    def _get_connection(self):
        """Get a new database connection."""
        return psycopg2.connect(**self.connection_params)
    
    def _ensure_table_exists(self, domain: str):
        """Ensure the domain table exists."""
        with self._get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT create_domain_memories_table(%s)", (domain,))
                conn.commit()
    
    def store_memory(self, content: str, metadata: Dict[str, Any] = None, domain: str = None) -> str:
        """Store a new memory in the specified domain."""
        domain = domain or self.default_domain
        self._ensure_table_exists(domain)
        
        memory_id = f"mem_{int(time.time() * 1000)}"
        timestamp = time.time()
        
        metadata = metadata or {}
        metadata.update({
            "created_at": timestamp,
            "updated_at": timestamp,
        })
        
        # Get embedding if available
        embedding = None
        if self.ollama_embeddings:
            try:
                embedding = self.ollama_embeddings.get_embedding(content)
            except Exception as e:
                print(f"Failed to generate embedding: {e}")
        
        with self._get_connection() as conn:
            with conn.cursor() as cursor:
                table_name = sql.Identifier(f"{domain}_memories")
                
                if embedding:
                    # Store with embedding
                    query = sql.SQL("""
                        INSERT INTO {} (id, content, embedding, metadata)
                        VALUES (%s, %s, %s, %s)
                    """).format(table_name)
                    cursor.execute(query, (memory_id, content, embedding, Json(metadata)))
                else:
                    # Store without embedding
                    query = sql.SQL("""
                        INSERT INTO {} (id, content, metadata)
                        VALUES (%s, %s, %s)
                    """).format(table_name)
                    cursor.execute(query, (memory_id, content, Json(metadata)))
                
                conn.commit()
        
        return memory_id
    
    def retrieve_memories(self, query: str, limit: int = 5, domain: str = None) -> List[Dict[str, Any]]:
        """Retrieve memories using vector similarity search with text search fallback."""
        domain = domain or self.default_domain
        self._ensure_table_exists(domain)
        
        # Try vector search first if embeddings are available
        if self.ollama_embeddings:
            try:
                query_embedding = self.ollama_embeddings.get_embedding(query)
                
                with self._get_connection() as conn:
                    with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                        table_name = sql.Identifier(f"{domain}_memories")
                        
                        # Vector similarity search - return ALL results up to limit regardless of score
                        search_query = sql.SQL("""
                            SELECT id, content, metadata,
                                   1 - (embedding <=> %s::vector) AS score
                            FROM {}
                            WHERE embedding IS NOT NULL
                            ORDER BY embedding <=> %s::vector
                            LIMIT %s
                        """).format(table_name)
                        
                        cursor.execute(search_query, (query_embedding, query_embedding, limit))
                        results = cursor.fetchall()
                        
                        # Return vector results if we have any, regardless of similarity score
                        if results:
                            return [dict(row) for row in results]
                        
                        # If no records have embeddings, fall through to text search
            except Exception as e:
                print(f"Vector search failed: {e}")
        
        # Fallback to text search
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                table_name = sql.Identifier(f"{domain}_memories")
                
                # Full text search
                search_query = sql.SQL("""
                    SELECT id, content, metadata, 0.0 as score
                    FROM {}
                    WHERE to_tsvector('english', content) @@ plainto_tsquery('english', %s)
                    ORDER BY updated_at DESC
                    LIMIT %s
                """).format(table_name)
                
                cursor.execute(search_query, (query, limit))
                results = cursor.fetchall()
                
                if results:
                    return [dict(row) for row in results]
                
                # If no results from full text search, try simple LIKE
                like_query = sql.SQL("""
                    SELECT id, content, metadata, 0.0 as score
                    FROM {}
                    WHERE content ILIKE %s
                    ORDER BY updated_at DESC
                    LIMIT %s
                """).format(table_name)
                
                cursor.execute(like_query, (f"%{query}%", limit))
                results = cursor.fetchall()
                
                if results:
                    return [dict(row) for row in results]
                
                # Last resort: return most recent memories if no search matches
                fallback_query = sql.SQL("""
                    SELECT id, content, metadata, 0.0 as score
                    FROM {}
                    ORDER BY updated_at DESC
                    LIMIT %s
                """).format(table_name)
                
                cursor.execute(fallback_query, (limit,))
                results = cursor.fetchall()
                
                return [dict(row) for row in results]
    
    def update_memory(self, memory_id: str, content: str = None, metadata: Dict[str, Any] = None, domain: str = None) -> bool:
        """Update an existing memory."""
        domain = domain or self.default_domain
        
        with self._get_connection() as conn:
            with conn.cursor() as cursor:
                table_name = sql.Identifier(f"{domain}_memories")
                
                # First check if memory exists
                check_query = sql.SQL("SELECT 1 FROM {} WHERE id = %s").format(table_name)
                cursor.execute(check_query, (memory_id,))
                
                if not cursor.fetchone():
                    return False
                
                # Update metadata timestamp
                if metadata is not None:
                    metadata["updated_at"] = time.time()
                
                # Build update query based on what needs updating
                if content is not None and metadata is not None:
                    # Update both content and metadata
                    embedding = None
                    if self.ollama_embeddings:
                        try:
                            embedding = self.ollama_embeddings.get_embedding(content)
                        except Exception as e:
                            print(f"Failed to generate embedding: {e}")
                    
                    if embedding:
                        update_query = sql.SQL("""
                            UPDATE {} 
                            SET content = %s, embedding = %s, metadata = %s, updated_at = NOW()
                            WHERE id = %s
                        """).format(table_name)
                        cursor.execute(update_query, (content, embedding, Json(metadata), memory_id))
                    else:
                        update_query = sql.SQL("""
                            UPDATE {} 
                            SET content = %s, metadata = %s, updated_at = NOW()
                            WHERE id = %s
                        """).format(table_name)
                        cursor.execute(update_query, (content, Json(metadata), memory_id))
                
                elif content is not None:
                    # Update only content
                    embedding = None
                    if self.ollama_embeddings:
                        try:
                            embedding = self.ollama_embeddings.get_embedding(content)
                        except Exception as e:
                            print(f"Failed to generate embedding: {e}")
                    
                    if embedding:
                        update_query = sql.SQL("""
                            UPDATE {} 
                            SET content = %s, embedding = %s, updated_at = NOW()
                            WHERE id = %s
                        """).format(table_name)
                        cursor.execute(update_query, (content, embedding, memory_id))
                    else:
                        update_query = sql.SQL("""
                            UPDATE {} 
                            SET content = %s, updated_at = NOW()
                            WHERE id = %s
                        """).format(table_name)
                        cursor.execute(update_query, (content, memory_id))
                
                elif metadata is not None:
                    # Update only metadata
                    update_query = sql.SQL("""
                        UPDATE {} 
                        SET metadata = metadata || %s, updated_at = NOW()
                        WHERE id = %s
                    """).format(table_name)
                    cursor.execute(update_query, (Json(metadata), memory_id))
                
                conn.commit()
                return True
    
    def list_domains(self) -> List[str]:
        """List all available memory domains."""
        with self._get_connection() as conn:
            with conn.cursor() as cursor:
                # Query for all tables ending with '_memories'
                cursor.execute("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name LIKE '%_memories'
                    ORDER BY table_name
                """)
                
                domains = []
                for row in cursor.fetchall():
                    table_name = row[0]
                    # Extract domain name by removing '_memories' suffix
                    if table_name.endswith('_memories'):
                        domain = table_name[:-9]  # Remove last 9 characters ('_memories')
                        domains.append(domain)
                
                return domains