import numpy as np
import faiss
import json
import os
import requests
import time
import re
from typing import List, Dict, Any, Optional, Tuple

class SimpleChunker:
    """Simple text chunking utility that splits text by paragraphs, sentences, or fixed size."""
    
    @staticmethod
    def chunk_by_paragraph(text: str, min_size: int = 50, max_size: int = 1000) -> List[str]:
        """Split text into chunks by paragraphs."""
        paragraphs = re.split(r'\n\s*\n', text)
        
        # Filter out empty paragraphs and those below min_size
        paragraphs = [p.strip() for p in paragraphs if p.strip() and len(p.strip()) >= min_size]
        
        # Handle paragraphs that exceed max_size
        chunks = []
        for para in paragraphs:
            if len(para) <= max_size:
                chunks.append(para)
            else:
                # Split long paragraphs by sentences
                for sentence_chunk in SimpleChunker.chunk_by_sentence(para, min_size, max_size):
                    chunks.append(sentence_chunk)
        
        return chunks
    
    @staticmethod
    def chunk_by_sentence(text: str, min_size: int = 50, max_size: int = 1000) -> List[str]:
        """Split text into chunks by sentences."""
        # Simple sentence splitting - can be improved with NLP libraries if needed
        sentences = re.split(r'(?<=[.!?])\s+', text)
        
        chunks = []
        current_chunk = ""
        
        for sentence in sentences:
            # If adding this sentence would exceed max_size, save current chunk and start a new one
            if len(current_chunk) + len(sentence) > max_size and len(current_chunk) >= min_size:
                chunks.append(current_chunk.strip())
                current_chunk = sentence
            else:
                if current_chunk:
                    current_chunk += " " + sentence
                else:
                    current_chunk = sentence
        
        # Add the last chunk if it's not empty
        if current_chunk and len(current_chunk) >= min_size:
            chunks.append(current_chunk.strip())
        
        return chunks
    
    @staticmethod
    def chunk_by_fixed_size(text: str, chunk_size: int = 500, overlap: int = 100) -> List[str]:
        """Split text into chunks of fixed size with overlap."""
        if not text or len(text) <= chunk_size:
            return [text] if text else []
        
        chunks = []
        start = 0
        
        while start < len(text):
            end = min(start + chunk_size, len(text))
            
            # If we're not at the end of the text, try to find a good break point
            if end < len(text):
                # Look for the last space within the chunk
                last_space = text.rfind(' ', start, end)
                if last_space > start:
                    end = last_space
            
            chunks.append(text[start:end].strip())
            start = end - overlap if end - overlap > start else end
        
        return chunks


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


class VectorStore:
    """Vector store using FAISS for similarity search."""
    
    def __init__(self, 
                 data_dir: str = ".",
                 embedding_model: str = "nomic-embed-text",
                 embedding_dim: int = 768,
                 ollama_url: str = "http://localhost:11434",
                 index_file: str = "faiss_index.bin",
                 metadata_file: str = "faiss_metadata.json"):
        
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)
        
        self.index_path = os.path.join(data_dir, index_file)
        self.metadata_path = os.path.join(data_dir, metadata_file)
        
        self.embedding_model = OllamaEmbeddings(
            model_name=embedding_model,
            base_url=ollama_url
        )
        
        self.embedding_dim = embedding_dim
        self.chunker = SimpleChunker()
        
        # Initialize or load FAISS index
        self._initialize_index()
        
        # Initialize or load metadata
        self._initialize_metadata()
    
    def _initialize_index(self):
        """Initialize FAISS index or load existing one."""
        if os.path.exists(self.index_path):
            try:
                self.index = faiss.read_index(self.index_path)
            except Exception as e:
                self.index = faiss.IndexFlatL2(self.embedding_dim)
        else:
            self.index = faiss.IndexFlatL2(self.embedding_dim)
    
    def _initialize_metadata(self):
        """Initialize metadata store or load existing one."""
        if os.path.exists(self.metadata_path):
            try:
                with open(self.metadata_path, 'r') as f:
                    self.metadata = json.load(f)
            except Exception as e:
                self.metadata = {"chunks": [], "id_map": {}}
        else:
            self.metadata = {"chunks": [], "id_map": {}}
    
    def _save_index(self):
        """Save FAISS index to disk."""
        faiss.write_index(self.index, self.index_path)
    
    def _save_metadata(self):
        """Save metadata to disk."""
        with open(self.metadata_path, 'w') as f:
            json.dump(self.metadata, f)
    
    def add_text(self, text_id: str, content: str, metadata: Dict[str, Any] = None) -> List[int]:
        """
        Add text to the vector store, chunking it first.
        Returns list of chunk IDs.
        """
        # Chunk the text
        chunks = self.chunker.chunk_by_paragraph(content)
        
        # If no chunks (text too small), treat the whole text as one chunk
        if not chunks:
            chunks = [content]
        
        # Get embeddings for all chunks
        embeddings = self.embedding_model.get_embeddings(chunks)
        
        # Add to FAISS index
        chunk_indices = []
        
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            # Convert to numpy array and reshape for FAISS
            embedding_np = np.array(embedding).astype('float32').reshape(1, -1)
            
            # Add to index
            faiss.normalize_L2(embedding_np)  # Normalize for cosine similarity
            self.index.add(embedding_np)
            
            # Get the index
            chunk_index = len(self.metadata["chunks"])
            chunk_indices.append(chunk_index)
            
            # Store metadata
            chunk_metadata = {
                "chunk_index": chunk_index,
                "text_id": text_id,
                "chunk_num": i,
                "content": chunk,
                "metadata": metadata or {},
                "created_at": time.time()
            }
            
            self.metadata["chunks"].append(chunk_metadata)
        
        # Update id_map to track which chunks belong to which text_id
        self.metadata["id_map"][text_id] = chunk_indices
        
        # Save changes
        self._save_index()
        self._save_metadata()
        
        return chunk_indices
    
    def update_text(self, text_id: str, content: str = None, metadata: Dict[str, Any] = None) -> bool:
        """
        Update text in the vector store.
        If content is provided, re-chunk and re-embed.
        If only metadata is provided, update metadata for all chunks of this text_id.
        Returns True if successful, False otherwise.
        """
        # Check if text_id exists
        if text_id not in self.metadata["id_map"]:
            return False
        
        # If content is provided, we need to re-chunk and re-embed
        if content is not None:
            # Get the old chunk indices
            old_chunk_indices = self.metadata["id_map"][text_id]
            
            # Add the new content (which will create new chunks)
            self.add_text(text_id, content, metadata)
            
            # Mark old chunks as deleted (we don't actually remove from FAISS index,
            # but we remove from metadata so they won't be returned in searches)
            for idx in old_chunk_indices:
                if idx < len(self.metadata["chunks"]):
                    # Mark as deleted by setting text_id to None
                    self.metadata["chunks"][idx]["text_id"] = None
            
            # Save metadata changes
            self._save_metadata()
            
            return True
        
        # If only metadata is provided, just update metadata
        elif metadata is not None:
            chunk_indices = self.metadata["id_map"][text_id]
            
            for idx in chunk_indices:
                if idx < len(self.metadata["chunks"]) and self.metadata["chunks"][idx]["text_id"] == text_id:
                    # Update metadata
                    self.metadata["chunks"][idx]["metadata"].update(metadata)
                    # Update timestamp
                    self.metadata["chunks"][idx]["metadata"]["updated_at"] = time.time()
            
            # Save metadata changes
            self._save_metadata()
            
            return True
        
        return False  # No changes made
    
    def search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Search for similar texts using vector similarity.
        Returns list of results sorted by relevance.
        """
        # Get query embedding
        query_embedding = self.embedding_model.get_embedding(query)
        query_np = np.array([query_embedding]).astype('float32')
        
        # Normalize for cosine similarity
        faiss.normalize_L2(query_np)
        
        # Search FAISS index
        D, I = self.index.search(query_np, limit * 3)  # Get more results than needed to filter
        
        # Collect results, filtering out deleted chunks
        results = []
        seen_text_ids = set()
        
        for i, idx in enumerate(I[0]):
            if idx >= len(self.metadata["chunks"]):
                continue
                
            chunk = self.metadata["chunks"][idx]
            text_id = chunk["text_id"]
            
            # Skip if this is a deleted chunk or we already included this text_id
            if text_id is None or text_id in seen_text_ids:
                continue
            
            # Add to results
            results.append({
                "id": text_id,
                "content": chunk["content"],
                "metadata": chunk["metadata"],
                "score": float(D[0][i]),
                "chunk_index": idx
            })
            
            seen_text_ids.add(text_id)
            
            # Stop once we have enough results
            if len(results) >= limit:
                break
        
        return results

    def get_all_chunks_for_text(self, text_id: str) -> List[Dict[str, Any]]:
        """Get all chunks associated with a text_id."""
        if text_id not in self.metadata["id_map"]:
            return []
        
        chunk_indices = self.metadata["id_map"][text_id]
        chunks = []
        
        for idx in chunk_indices:
            if idx < len(self.metadata["chunks"]) and self.metadata["chunks"][idx]["text_id"] == text_id:
                chunks.append(self.metadata["chunks"][idx])
        
        return chunks