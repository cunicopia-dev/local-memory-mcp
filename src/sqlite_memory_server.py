from fastmcp import FastMCP
import os
import time
from typing import List, Dict, Any, Optional
from sqlite_memory_api import SQLiteMemoryAPI
from sqlite_vector_api import FAISSVectorAPI
from ollama_embeddings import OllamaEmbeddings

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
        vector_store = FAISSVectorAPI(
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

# Initialize the SQLite memory API
memory_api = SQLiteMemoryAPI(vector_store=vector_store)

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
    
    memory_id = memory_api.store_memory(content, metadata)
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
    
    success = memory_api.update_memory(memory_id, content, metadata)
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
    results = memory_api.retrieve_memories(query, limit)
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
    results = memory_api.retrieve_memories(query, limit, use_vector)
    
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