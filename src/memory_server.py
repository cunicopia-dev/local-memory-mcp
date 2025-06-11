from fastmcp import FastMCP
import sqlite3
import json
import os
import time
import pathlib
from typing import List, Dict, Any, Optional, Union
from vector_store import VectorStore, SimpleChunker

class MemoryStore:
    def __init__(self, db_path: str = None, vector_store: VectorStore = None):
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

# Get server name from environment or use default
server_name = os.environ.get("MCP_SERVER_NAME", "Local Context Memory")
data_dir = os.environ.get("MCP_DATA_DIR", ".")

# Initialize the MCP server
mcp = FastMCP(name=server_name)

# Check if Ollama is available
ollama_available = False
ollama_url = os.environ.get("OLLAMA_API_URL", "http://localhost:11434")
embedding_model = os.environ.get("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text")

try:
    import requests
    response = requests.get(f"{ollama_url}/api/tags")
    if response.status_code == 200:
        models = response.json().get("models", [])
        model_names = [model.get("name", "").split(":")[0] for model in models]
        
        if embedding_model in model_names or f"{embedding_model}:latest" in model_names:
            ollama_available = True
        else:
            # Ollama found but embedding model not available, using text search only
            pass
    else:
        # Ollama API returned error, using text search only
        pass
except Exception as e:
    # Ollama check failed, using text search only
    pass

# Initialize vector store if Ollama is available
vector_store = None
if ollama_available:
    try:
        vector_store = VectorStore(
            data_dir=data_dir,
            embedding_model=embedding_model,
            ollama_url=ollama_url
        )
    except Exception as e:
        # Failed to initialize vector store, using text search only
        pass
else:
    # Vector search not available, using text search only
    pass

# Initialize the memory store
memory_store = MemoryStore(vector_store=vector_store)

@mcp.tool
def store_memory(content: str, source: Optional[str] = None, importance: Optional[float] = None) -> str:
    """
    Store a new memory chunk in the persistent memory system.
    
    This tool allows you to save important information that should be remembered across conversations.
    The content will be automatically chunked and indexed for semantic search.
    
    Parameters:
    - content (str): The text content to remember. This can be facts, preferences, context, 
                    or any information that should persist. Examples:
                    * "User prefers Python over JavaScript for backend development"
                    * "Meeting scheduled for Tuesday at 3pm about project planning"
                    * "User's favorite color is blue and they work in San Francisco"
    
    - source (str, optional): Where this memory originated from. Examples:
                              * "conversation"
                              * "document"  
                              * "email"
                              * "meeting_notes"
                              
    - importance (float, optional): Importance score from 0.0 to 1.0 where:
                                   * 0.0-0.3 = Low importance (casual mentions)
                                   * 0.4-0.7 = Medium importance (useful context)
                                   * 0.8-1.0 = High importance (critical information)
    
    Returns:
    str: A unique memory ID that can be used to update or reference this memory later.
    
    Example usage:
    - store_memory("User loves hiking in the mountains", "conversation", 0.7)
    - store_memory("API key expires on Dec 31st", "documentation", 0.9)
    """
    # Storing memory
    metadata = {}
    if source:
        metadata["source"] = source
    if importance is not None:
        metadata["importance"] = importance
    
    memory_id = memory_store.store_memory(content, metadata)
    # Memory stored
    return memory_id

@mcp.tool
def update_memory(memory_id: str, content: Optional[str] = None, importance: Optional[float] = None) -> bool:
    """
    Update an existing memory chunk with new information.
    
    This tool allows you to modify previously stored memories. You can update the content,
change the importance level. If updating content, the memory will be
    re-indexed for semantic search.
    
    Parameters:
    - memory_id (str): The unique ID of the memory to update (returned from store_memory).
                      Example: "mem_1234567890123"
    
    - content (str, optional): New content to replace the existing memory content.
                              If provided, this completely replaces the old content.
                              Example: "User prefers React over Vue for frontend projects"
    
    - importance (float, optional): New importance score from 0.0 to 1.0.
                                   * 0.0-0.3 = Low importance
                                   * 0.4-0.7 = Medium importance  
                                   * 0.8-1.0 = High importance
    
    Returns:
    bool: True if the update was successful, False if the memory_id was not found.
    
    Example usage:
    - update_memory("mem_1234567890123", content="User now prefers TypeScript over JavaScript")
    - update_memory("mem_1234567890123", importance=0.9)
    """
    # Updating memory
    metadata = {}
    if importance is not None:
        metadata["importance"] = importance
    
    success = memory_store.update_memory(memory_id, content, metadata)
    # Memory update completed
    return success

@mcp.resource("memory://{query}")
def get_memories(query: str, limit: Optional[int] = 5) -> List[Dict[str, Any]]:
    """
    Retrieve memories relevant to a search query using semantic search.
    
    This resource performs intelligent semantic search across all stored memories,
    finding relevant content even if the exact words don't match. It uses vector
    embeddings to understand meaning and context.
    
    Parameters:
    - query (str): The search query to find relevant memories. This can be:
                  * Natural language questions: "What does the user like to do?"
                  * Keywords: "python programming preferences" 
                  * Concepts: "work schedule" or "personal information"
                  * Specific topics: "machine learning projects"
    
    - limit (int, optional): Maximum number of memories to return (default: 5).
                            Higher values return more results but may include less relevant ones.
                            Recommended range: 3-10.
    
    Returns:
    List[Dict[str, Any]]: A list of memory objects, each containing:
        - id (str): Unique memory identifier
        - content (str): The stored memory content
        - metadata (dict): Associated metadata including source, importance, timestamps
        - score (float): Relevance score (higher = more relevant)
    
    Example queries:
    - "What programming languages does the user prefer?"
    - "meeting schedule"
    - "personal preferences"
    - "technical documentation"
    
    Note: This uses the URI pattern memory://{query} where {query} is automatically
    extracted from the resource path.
    """
    # Resource requested
    results = memory_store.retrieve_memories(query, limit)
    # Returning results
    return results

@mcp.tool
def search_memories(query: str, limit: Optional[int] = 5, 
                   use_vector: Optional[bool] = True) -> List[Dict[str, Any]]:
    """
    Search for memories using advanced semantic search with optional fallback.
    
    This tool provides more control over the search process compared to the resource.
    It allows you to choose between semantic vector search and traditional text search,
    and returns additional metadata about the search process.
    
    Parameters:
    - query (str): The search query to find relevant memories. Examples:
                  * "What does the user like for breakfast?"
                  * "programming projects and preferences"
                  * "work meetings this week"
                  * "personal goals and aspirations"
    
    - limit (int, optional): Maximum number of memories to return (default: 5).
                            Range: 1-20. Higher values may include less relevant results.
    
    - use_vector (bool, optional): Whether to use semantic vector search (default: True).
                                  * True: Uses AI embeddings for semantic understanding
                                  * False: Uses traditional keyword-based text search
                                  If vector search fails, automatically falls back to text search.
    
    Returns:
    List[Dict[str, Any]]: A list of memory objects with search metadata:
        - id (str): Unique memory identifier
        - content (str): The stored memory content  
        - metadata (dict): Memory metadata (source, importance, timestamps)
        - score (float): Relevance/similarity score
        - query (str): The original search query (for reference)
    
    Example usage:
    - search_memories("user preferences", 3, True)  # Semantic search, top 3 results
    - search_memories("python", 10, False)  # Text search for "python", up to 10 results
    
    Note: This tool provides more detailed search control than the memory:// resource.
    """
    # Searching memories
    results = memory_store.retrieve_memories(query, limit, use_vector)
    
    # Add search information
    for result in results:
        result["query"] = query
        if "score" not in result:
            result["score"] = 0.0
    
    # Search completed
    return results

@mcp.prompt
def summarize_memories(memories: List[Dict[str, Any]]) -> str:
    """
    Create a prompt for summarizing a list of memories.
    
    Parameters:
    - memories: List of memory chunks to summarize
    
    Returns:
    - A prompt for the LLM to create a summary
    """
    memory_texts = [f"Memory {i+1}: {mem['content']}" for i, mem in enumerate(memories)]
    formatted_memories = "\n".join(memory_texts)
    
    prompt = f"""Below are several memory chunks related to a user's interests and history.
Please create a concise summary that captures the key points and patterns:

{formatted_memories}

Summary:"""

    # Generated summarization prompt
    return prompt

if __name__ == "__main__":
    mcp.run()  # Start the FastMCP server
