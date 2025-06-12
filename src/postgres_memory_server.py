from fastmcp import FastMCP
import os
import time
from typing import List, Dict, Any, Optional
from postgres_memory_api import PostgresMemoryAPI
from ollama_embeddings import OllamaEmbeddings

# Get server name from environment or use default
server_name = os.environ.get("MCP_SERVER_NAME", "Local Context Memory")

# Initialize the MCP server
mcp = FastMCP(name=server_name)

# Check if Ollama is available
ollama_available = False
ollama_url = os.environ.get("OLLAMA_API_URL", "http://localhost:11434")
embedding_model = os.environ.get("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text")
ollama_embeddings = None

try:
    import requests
    response = requests.get(f"{ollama_url}/api/tags")
    if response.status_code == 200:
        models = response.json().get("models", [])
        model_names = [model.get("name", "").split(":")[0] for model in models]
        
        if embedding_model in model_names or f"{embedding_model}:latest" in model_names:
            ollama_available = True
            ollama_embeddings = OllamaEmbeddings(
                model_name=embedding_model,
                base_url=ollama_url
            )
        else:
            print(f"Ollama found but embedding model {embedding_model} not available, using text search only")
    else:
        print("Ollama API returned error, using text search only")
except Exception as e:
    print(f"Ollama check failed: {e}, using text search only")

# Initialize the PostgreSQL memory API
memory_api = PostgresMemoryAPI(ollama_embeddings=ollama_embeddings)

@mcp.tool
def store_memory(content: str, domain: Optional[str] = None, 
                 source: Optional[str] = None, importance: Optional[float] = None) -> str:
    """
    Store a new memory chunk in the persistent memory system.
    
    This tool allows you to save important information that should be remembered across conversations.
    The content will be automatically indexed for semantic search (if Ollama is available) or text search.
    
    Parameters:
    - content (str): The text content to remember. This can be facts, preferences, context, 
                    or any information that should persist. Examples:
                    * "User prefers Python over JavaScript for backend development"
                    * "Meeting scheduled for Tuesday at 3pm about project planning"
                    * "User's favorite color is blue and they work in San Francisco"
    
    - domain (str, optional): The domain/context for this memory. Memories are segmented by domain
                             for better retrieval accuracy. Defaults to 'default'. Examples:
                             * "startup" - for business-related memories
                             * "health" - for health-related information
                             * "personal" - for personal preferences
                             
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
    - store_memory("User loves hiking in the mountains", "personal", "conversation", 0.7)
    - store_memory("Series A funding closed at $10M", "startup", "meeting", 0.9)
    """
    metadata = {}
    if source:
        metadata["source"] = source
    if importance is not None:
        metadata["importance"] = importance
    
    memory_id = memory_api.store_memory(content, metadata, domain)
    return memory_id

@mcp.tool
def update_memory(memory_id: str, content: Optional[str] = None, 
                  importance: Optional[float] = None, domain: Optional[str] = None) -> bool:
    """
    Update an existing memory chunk with new information.
    
    This tool allows you to modify previously stored memories. You can update the content,
    change the importance level. If updating content, the memory will be
    re-indexed for search.
    
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
                                   
    - domain (str, optional): The domain where this memory is stored.
                             If not specified, uses the default domain.
    
    Returns:
    bool: True if the update was successful, False if the memory_id was not found.
    
    Example usage:
    - update_memory("mem_1234567890123", content="User now prefers TypeScript over JavaScript")
    - update_memory("mem_1234567890123", importance=0.9)
    """
    metadata = {}
    if importance is not None:
        metadata["importance"] = importance
    
    success = memory_api.update_memory(memory_id, content, metadata, domain)
    return success

@mcp.resource("memory://{domain}/{query}")
def get_memories(domain: str, query: str, limit: Optional[int] = 5) -> List[Dict[str, Any]]:
    """
    Retrieve memories from a specific domain using semantic or text search.
    
    This resource performs intelligent search within a specific domain,
    finding relevant content based on the query. Uses vector embeddings if available,
    falls back to text search otherwise.
    
    URI Pattern: memory://{domain}/{query}
    
    Parameters:
    - domain (str): The domain to search within. Examples:
                   * "default" - general memories
                   * "startup" - business context
                   * "health" - health information
                   * "personal" - personal preferences
    
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
    
    Example URIs:
    - memory://startup/funding%20strategy
    - memory://health/blood%20pressure
    - memory://default/programming%20preferences
    """
    results = memory_api.retrieve_memories(query, limit, domain)
    return results

@mcp.tool
def search_memories(query: str, domain: Optional[str] = None, 
                   limit: Optional[int] = 5) -> List[Dict[str, Any]]:
    """
    Search for memories within a specific domain or the default domain.
    
    This tool provides semantic search (if Ollama is available) or text search
    across memories in the specified domain. Domain segmentation ensures
    queries return contextually relevant results.
    
    Parameters:
    - query (str): The search query to find relevant memories. Examples:
                  * "What does the user like for breakfast?"
                  * "programming projects and preferences"
                  * "work meetings this week"
                  * "personal goals and aspirations"
    
    - domain (str, optional): The domain to search within. If not specified,
                             searches the default domain. Examples:
                             * "startup" - business memories
                             * "health" - health information
                             * "personal" - personal data
    
    - limit (int, optional): Maximum number of memories to return (default: 5).
                            Range: 1-20. Higher values may include less relevant results.
    
    Returns:
    List[Dict[str, Any]]: A list of memory objects with search metadata:
        - id (str): Unique memory identifier
        - content (str): The stored memory content  
        - metadata (dict): Memory metadata (source, importance, timestamps)
        - score (float): Relevance/similarity score
        - query (str): The original search query (for reference)
    
    Example usage:
    - search_memories("user preferences", "personal", 3)
    - search_memories("python programming", limit=10)  # searches default domain
    - search_memories("recent meetings", "startup", 5)
    """
    results = memory_api.retrieve_memories(query, limit, domain)
    
    # Add search information
    for result in results:
        result["query"] = query
        if "score" not in result:
            result["score"] = 0.0
    
    return results

@mcp.tool
def list_memory_domains() -> List[str]:
    """
    List all available memory domains in the database.
    
    This tool returns a list of all domain tables that have been created in the database.
    Each domain represents a separate context for storing memories (e.g., 'default', 'startup', 'health').
    
    Returns:
    List[str]: A list of domain names that can be used with store_memory and search_memories.
    
    Example usage:
    - list_memory_domains() might return: ["default", "startup", "health", "personal"]
    
    This is useful for:
    - Discovering what domains are available before storing/searching
    - Understanding the organization of stored memories
    - Validating domain names before use
    """
    return memory_api.list_domains()

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

    return prompt

if __name__ == "__main__":
    mcp.run()  # Start the FastMCP server