import requests
from typing import List

class OllamaEmbeddings:
    """Client for getting embeddings from Ollama API."""
    
    def __init__(self, model_name: str = "nomic-embed-text", base_url: str = "http://localhost:11434"):
        self.model_name = model_name
        self.base_url = base_url
        self.api_url = f"{base_url}/api/embeddings"
    
    def get_embedding(self, text: str) -> List[float]:
        """Get embedding for a single text."""
        try:
            response = requests.post(
                self.api_url,
                json={"model": self.model_name, "prompt": text}
            )
            response.raise_for_status()
            return response.json()["embedding"]
        except Exception as e:
            # Error getting embedding
            # Return a zero vector as fallback
            return [0.0] * 768  # Assuming 768-dim embeddings, adjust if different
    
    def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Get embeddings for multiple texts."""
        return [self.get_embedding(text) for text in texts]