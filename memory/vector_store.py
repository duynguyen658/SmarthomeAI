"""
Vector Store using Qdrant
Provides semantic search capabilities for memory storage
"""
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid

logger = logging.getLogger(__name__)

try:
    from qdrant_client import QdrantClient
    from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue
    QDRANT_AVAILABLE = True
except ImportError:
    QDRANT_AVAILABLE = False
    logger.warning("Qdrant not available, using mock vector store")


class VectorStore:
    """
    Vector store for semantic memory
    Uses Qdrant for vector similarity search
    """

    COLLECTION_NAME = "smarthome_memory"
    VECTOR_SIZE = 384  # all-MiniLM-L6-v2 dimension

    def __init__(self, host: str = "localhost", port: int = 6333, api_key: str = None):
        self._host = host
        self._port = port
        self._api_key = api_key
        self._client: Optional[QdrantClient] = None
        self._encoder = None
        self._connected = False

    async def connect(self) -> None:
        """Connect to Qdrant"""
        if not QDRANT_AVAILABLE:
            logger.warning("Qdrant not available, using mock vector store")
            self._connected = True
            self._mock_vectors: Dict[str, Dict] = {}
            return

        try:
            self._client = QdrantClient(
                host=self._host,
                port=self._port,
                api_key=self._api_key
            )
            
            # Ensure collection exists
            await self._ensure_collection()
            
            # Load encoder
            await self._load_encoder()
            
            self._connected = True
            logger.info(f"Connected to Qdrant at {self._host}:{self._port}")
            
        except Exception as e:
            logger.error(f"Failed to connect to Qdrant: {e}")
            self._connected = True
            self._mock_vectors: Dict[str, Dict] = {}
            logger.info("Using mock vector store")

    async def disconnect(self) -> None:
        """Disconnect from Qdrant"""
        self._connected = False
        self._client = None

    @property
    def is_connected(self) -> bool:
        return self._connected

    async def _ensure_collection(self) -> None:
        """Ensure collection exists"""
        if not self._client:
            return

        try:
            collections = self._client.get_collections().collections
            collection_names = [c.name for c in collections]
            
            if self.COLLECTION_NAME not in collection_names:
                self._client.create_collection(
                    collection_name=self.COLLECTION_NAME,
                    vectors_config=VectorParams(
                        size=self.VECTOR_SIZE,
                        distance=Distance.COSINE
                    )
                )
                logger.info(f"Created collection: {self.COLLECTION_NAME}")
        except Exception as e:
            logger.error(f"Failed to ensure collection: {e}")

    async def _load_encoder(self) -> None:
        """Load sentence transformer encoder"""
        try:
            from sentence_transformers import SentenceTransformer
            self._encoder = SentenceTransformer('all-MiniLM-L6-v2')
            logger.info("Loaded embedding model")
        except ImportError:
            logger.warning("sentence-transformers not available")
            self._encoder = None

    async def add(
        self,
        text: str,
        metadata: Dict[str, Any] = None,
        user_id: str = None
    ) -> str:
        """
        Add a memory to the vector store
        
        Args:
            text: Text content to store
            metadata: Additional metadata
            user_id: User ID for filtering
            
        Returns:
            Memory ID
        """
        memory_id = str(uuid.uuid4())

        if not QDRANT_AVAILABLE or not self._client or not self._encoder:
            # Mock implementation
            self._mock_vectors[memory_id] = {
                "text": text,
                "metadata": metadata or {},
                "created_at": datetime.utcnow().isoformat()
            }
            return memory_id

        try:
            # Generate embedding
            vector = self._encoder.encode(text).tolist()
            
            # Prepare payload
            payload = {
                "text": text,
                "metadata": metadata or {},
                "created_at": datetime.utcnow().isoformat()
            }
            if user_id:
                payload["user_id"] = user_id
            
            # Add to Qdrant
            self._client.upsert(
                collection_name=self.COLLECTION_NAME,
                points=[
                    PointStruct(
                        id=memory_id,
                        vector=vector,
                        payload=payload
                    )
                ]
            )
            
            logger.debug(f"Added memory: {memory_id}")
            return memory_id
            
        except Exception as e:
            logger.error(f"Failed to add memory: {e}")
            # Fallback to mock
            self._mock_vectors[memory_id] = {
                "text": text,
                "metadata": metadata or {},
                "created_at": datetime.utcnow().isoformat()
            }
            return memory_id

    async def search(
        self,
        query: str,
        limit: int = 10,
        user_id: str = None,
        filter_conditions: Dict[str, Any] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for similar memories
        
        Args:
            query: Search query
            limit: Maximum results
            user_id: Filter by user ID
            filter_conditions: Additional filter conditions
            
        Returns:
            List of matching memories with scores
        """
        if not QDRANT_AVAILABLE or not self._client or not self._encoder:
            # Mock: simple text search
            results = []
            query_lower = query.lower()
            for mid, data in self._mock_vectors.items():
                if query_lower in data["text"].lower():
                    results.append({
                        "id": mid,
                        "text": data["text"],
                        "metadata": data["metadata"],
                        "score": 1.0
                    })
                if len(results) >= limit:
                    break
            return results

        try:
            # Generate query embedding
            query_vector = self._encoder.encode(query).tolist()
            
            # Build filter
            must_conditions = []
            if user_id:
                must_conditions.append(
                    FieldCondition(
                        key="user_id",
                        match=MatchValue(value=user_id)
                    )
                )
            
            # Build search request
            from qdrant_client.models import Filter
            
            search_filter = Filter(must=must_conditions) if must_conditions else None
            
            # Search
            results = self._client.search(
                collection_name=self.COLLECTION_NAME,
                query_vector=query_vector,
                limit=limit,
                query_filter=search_filter
            )
            
            return [
                {
                    "id": r.id,
                    "text": r.payload.get("text"),
                    "metadata": r.payload.get("metadata", {}),
                    "score": r.score,
                    "created_at": r.payload.get("created_at")
                }
                for r in results
            ]
            
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []

    async def get(self, memory_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific memory by ID"""
        if not QDRANT_AVAILABLE or not self._client:
            return self._mock_vectors.get(memory_id)

        try:
            results = self._client.retrieve(
                collection_name=self.COLLECTION_NAME,
                ids=[memory_id]
            )
            
            if results:
                r = results[0]
                return {
                    "id": r.id,
                    "text": r.payload.get("text"),
                    "metadata": r.payload.get("metadata", {}),
                    "created_at": r.payload.get("created_at")
                }
            return None
            
        except Exception as e:
            logger.error(f"Failed to get memory: {e}")
            return self._mock_vectors.get(memory_id)

    async def delete(self, memory_id: str) -> bool:
        """Delete a memory"""
        if not QDRANT_AVAILABLE or not self._client:
            if memory_id in self._mock_vectors:
                del self._mock_vectors[memory_id]
                return True
            return False

        try:
            self._client.delete(
                collection_name=self.COLLECTION_NAME,
                points_selector=[memory_id]
            )
            return True
        except Exception as e:
            logger.error(f"Failed to delete memory: {e}")
            return False

    async def update(
        self,
        memory_id: str,
        text: str = None,
        metadata: Dict[str, Any] = None
    ) -> bool:
        """Update a memory"""
        if not QDRANT_AVAILABLE or not self._client:
            if memory_id in self._mock_vectors:
                if text:
                    self._mock_vectors[memory_id]["text"] = text
                if metadata:
                    self._mock_vectors[memory_id]["metadata"].update(metadata)
                return True
            return False

        try:
            current = await self.get(memory_id)
            if not current:
                return False
            
            new_text = text or current["text"]
            new_metadata = {**current["metadata"], **(metadata or {})}
            
            # Re-embed if text changed
            if text and self._encoder:
                vector = self._encoder.encode(text).tolist()
            else:
                # Get existing vector
                results = self._client.retrieve(
                    collection_name=self.COLLECTION_NAME,
                    ids=[memory_id]
                )
                if results:
                    vector = results[0].vector
                else:
                    return False
            
            self._client.upsert(
                collection_name=self.COLLECTION_NAME,
                points=[
                    PointStruct(
                        id=memory_id,
                        vector=vector,
                        payload={
                            "text": new_text,
                            "metadata": new_metadata,
                            "updated_at": datetime.utcnow().isoformat()
                        }
                    )
                ]
            )
            return True
            
        except Exception as e:
            logger.error(f"Failed to update memory: {e}")
            return False

    async def count(self, user_id: str = None) -> int:
        """Count memories"""
        if not QDRANT_AVAILABLE or not self._client:
            if user_id:
                return sum(1 for v in self._mock_vectors.values() if v["metadata"].get("user_id") == user_id)
            return len(self._mock_vectors)

        try:
            info = self._client.get_collection(self.COLLECTION_NAME)
            return info.points_count
        except Exception:
            return len(self._mock_vectors)


# Global vector store instance
_vector_store: Optional[VectorStore] = None


async def get_vector_store() -> VectorStore:
    """Get vector store singleton"""
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
        await _vector_store.connect()
    return _vector_store


async def close_vector_store() -> None:
    """Close vector store connection"""
    global _vector_store
    if _vector_store:
        await _vector_store.disconnect()
        _vector_store = None
