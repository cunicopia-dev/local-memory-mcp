import sqlite3
import json
import os
import time
import pathlib
from typing import List, Dict, Any, Optional
from sqlite_vector_api import FAISSVectorAPI

class SQLiteMemoryAPI:
    def __init__(self, db_path: str = None, vector_store: FAISSVectorAPI = None):
        # Set default path or use provided path
        if db_path is None:
            data_dir = os.environ.get("MCP_DATA_DIR", ".")
            pathlib.Path(data_dir).mkdir(parents=True, exist_ok=True)
            self.db_path = os.path.join(data_dir, "memory.db")
        else:
            self.db_path = db_path
            
        self._initialize_db()
        
        # Initialize vector store
        self.vector_store = vector_store
    
    def _initialize_db(self):
        """Initialize the SQLite database with required tables."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create memories table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS memories (
            id TEXT PRIMARY KEY,
            content TEXT NOT NULL,
            metadata TEXT NOT NULL,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        )
        ''')
        
        conn.commit()
        conn.close()
    
    def store_memory(self, content: str, metadata: Dict[str, Any] = None) -> str:
        """Store a new memory chunk in the database."""
        memory_id = f"mem_{int(time.time() * 1000)}"
        timestamp = time.time()
        
        metadata = metadata or {}
        metadata.update({
            "created_at": timestamp,
            "updated_at": timestamp,
        })
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            "INSERT INTO memories (id, content, metadata, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (memory_id, content, json.dumps(metadata), timestamp, timestamp)
        )
        
        conn.commit()
        conn.close()
        
        # Add to vector store if available
        if self.vector_store:
            try:
                self.vector_store.add_text(memory_id, content, metadata)
            except Exception as e:
                pass  # Silently handle vector store errors
        return memory_id
    
    def retrieve_memories(self, query: str, limit: int = 5, use_vector: bool = True) -> List[Dict[str, Any]]:
        """
        Retrieve memories relevant to the query.
        
        If vector_store is available and use_vector is True, use semantic search.
        Otherwise, fall back to SQL text search.
        """
        # Try vector search first if available and requested
        if self.vector_store and use_vector:
            try:
                # Performing vector search
                vector_results = self.vector_store.search(query, limit)
                
                # Convert to standard format
                results = []
                for result in vector_results:
                    results.append({
                        "id": result["id"],
                        "content": result["content"],
                        "metadata": result["metadata"],
                        "score": result.get("score", 0)
                    })
                
                if results:
                    # Vector search found results
                    return results
                else:
                    # Vector search returned no results, falling back to text search
                    pass
            except Exception as e:
                # Vector search failed, falling back to text search
                pass
        
        # Fall back to text search
        # Performing text search
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT id, content, metadata FROM memories WHERE content LIKE ? ORDER BY updated_at DESC LIMIT ?",
            (f"%{query}%", limit)
        )
        
        results = []
        for row in cursor.fetchall():
            results.append({
                "id": row["id"],
                "content": row["content"],
                "metadata": json.loads(row["metadata"])
            })
        
        conn.close()
        # Text search found results
        return results
    
    def update_memory(self, memory_id: str, content: str = None, metadata: Dict[str, Any] = None) -> bool:
        """Update an existing memory chunk."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get current memory
        cursor.execute("SELECT content, metadata FROM memories WHERE id = ?", (memory_id,))
        result = cursor.fetchone()
        
        if not result:
            conn.close()
            return False
        
        current_content, current_metadata_str = result
        current_metadata = json.loads(current_metadata_str)
        
        # Update content if provided
        if content is not None:
            new_content = content
        else:
            new_content = current_content
        
        # Update metadata if provided
        if metadata is not None:
            new_metadata = current_metadata.copy()
            new_metadata.update(metadata)
        else:
            new_metadata = current_metadata
        
        # Always update the updated_at timestamp
        new_metadata["updated_at"] = time.time()
        
        cursor.execute(
            "UPDATE memories SET content = ?, metadata = ?, updated_at = ? WHERE id = ?",
            (new_content, json.dumps(new_metadata), new_metadata["updated_at"], memory_id)
        )
        
        conn.commit()
        conn.close()
        
        # Update vector store if available
        if self.vector_store:
            try:
                if content is not None:
                    # If content changed, update the embeddings
                    self.vector_store.update_text(memory_id, content, new_metadata)
                elif metadata is not None:
                    # If only metadata changed, just update metadata
                    self.vector_store.update_text(memory_id, None, new_metadata)
                # Updated memory in vector store
            except Exception as e:
                pass  # Silently handle vector store update errors
        
        return True