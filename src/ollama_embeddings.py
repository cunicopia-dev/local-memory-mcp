import requests
import sys
from typing import List

class OllamaEmbeddings:
    """Client for getting embeddings from Ollama API."""
    
    def __init__(self, model_name: str = "nomic-embed-text", base_url: str = "http://localhost:11434", 
                 keep_alive: str = "10m"):
        self.model_name = model_name
        self.base_url = base_url
        self.api_url = f"{base_url}/api/embed"  # Use newer endpoint
        self.keep_alive = keep_alive
        
        # Create a session for connection pooling
        self.session = requests.Session()
        
        # Simple LRU cache for embeddings (to avoid re-computing same text)
        self._embedding_cache = {}
        self._cache_max_size = 100  # Keep last 100 embeddings
    
    def get_embedding(self, text: str) -> List[float]:
        """Get embedding for a single text."""
        # Check cache first
        cache_key = hash(text)
        if cache_key in self._embedding_cache:
            return self._embedding_cache[cache_key]
        
        try:
            response = self.session.post(
                self.api_url,
                json={
                    "model": self.model_name, 
                    "prompt": text,
                    "keep_alive": self.keep_alive
                },
                timeout=30
            )
            response.raise_for_status()
            embedding = response.json()["embedding"]
            
            # Cache the result
            self._cache_embedding(cache_key, embedding)
            
            return embedding
        except Exception as e:
            print(f"Error getting embedding: {e}", file=sys.stderr)
            # Return a zero vector as fallback
            return [0.0] * 768  # Assuming 768-dim embeddings, adjust if different
    
    def _cache_embedding(self, key: int, embedding: List[float]):
        """Cache an embedding with simple LRU eviction."""
        if len(self._embedding_cache) >= self._cache_max_size:
            # Remove oldest entry (simple FIFO, not true LRU for simplicity)
            oldest_key = next(iter(self._embedding_cache))
            del self._embedding_cache[oldest_key]
        
        self._embedding_cache[key] = embedding
    
    def __del__(self):
        """Clean up the session when the object is destroyed."""
        if hasattr(self, 'session'):
            self.session.close()
    
    def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Get embeddings for multiple texts."""
        return [self.get_embedding(text) for text in texts]