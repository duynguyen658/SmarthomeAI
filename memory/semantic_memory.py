"""
Semantic Memory
Stores learned facts, preferences, and knowledge
"""
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from enum import Enum

from memory.vector_store import VectorStore, get_vector_store

logger = logging.getLogger(__name__)


class MemoryType(str, Enum):
    """Types of semantic memories"""
    FACT = "fact"
    PREFERENCE = "preference"
    HABIT = "habit"
    ROUTINE = "routine"
    RELATIONSHIP = "relationship"
    KNOWLEDGE = "knowledge"


class MemoryCategory(str, Enum):
    """Categories for memories"""
    DEVICE = "device"
    LOCATION = "location"
    USER = "user"
    AUTOMATION = "automation"
    ENVIRONMENT = "environment"
    SCHEDULE = "schedule"
    GENERAL = "general"


class SemanticMemory:
    """
    Semantic memory storage
    Stores structured knowledge about user preferences, habits, and facts
    """

    def __init__(self, vector_store: VectorStore = None):
        self._vector_store = vector_store

    async def initialize(self) -> None:
        """Initialize with vector store"""
        if self._vector_store is None:
            self._vector_store = await get_vector_store()

    def set_vector_store(self, vector_store: VectorStore) -> None:
        """Set vector store"""
        self._vector_store = vector_store

    async def store(
        self,
        user_id: str,
        content: str,
        memory_type: MemoryType = MemoryType.FACT,
        category: MemoryCategory = MemoryCategory.GENERAL,
        confidence: float = 1.0,
        source: str = "interaction",
        **kwargs
    ) -> str:
        """
        Store a semantic memory
        
        Args:
            user_id: User identifier
            content: Memory content
            memory_type: Type of memory
            category: Category
            confidence: Confidence score (0-1)
            source: Source of the memory
            
        Returns:
            Memory ID
        """
        await self.initialize()

        metadata = {
            "user_id": user_id,
            "type": memory_type.value if isinstance(memory_type, MemoryType) else memory_type,
            "category": category.value if isinstance(category, MemoryCategory) else category,
            "confidence": confidence,
            "source": source,
            **kwargs
        }

        memory_id = await self._vector_store.add(content, metadata, user_id)
        
        logger.debug(f"Stored semantic memory: {memory_id} ({memory_type})")
        return memory_id

    async def recall(
        self,
        user_id: str,
        query: str,
        memory_type: MemoryType = None,
        category: MemoryCategory = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Recall memories related to query
        
        Args:
            user_id: User identifier
            query: Search query
            memory_type: Filter by type
            category: Filter by category
            limit: Maximum results
            
        Returns:
            List of matching memories
        """
        await self.initialize()

        # Build filter conditions
        filter_conditions = {}
        if memory_type:
            filter_conditions["type"] = memory_type.value if isinstance(memory_type, MemoryType) else memory_type
        if category:
            filter_conditions["category"] = category.value if isinstance(category, MemoryCategory) else category

        results = await self._vector_store.search(
            query=query,
            limit=limit,
            user_id=user_id,
            filter_conditions=filter_conditions
        )

        return results

    async def learn_preference(
        self,
        user_id: str,
        preference: str,
        category: str,
        context: str = None
    ) -> str:
        """Learn a user preference"""
        content = preference
        if context:
            content = f"{context}: {preference}"
        
        return await self.store(
            user_id=user_id,
            content=content,
            memory_type=MemoryType.PREFERENCE,
            category=MemoryCategory(category),
            source="learning"
        )

    async def learn_habit(
        self,
        user_id: str,
        habit: str,
        time: str = None,
        location: str = None
    ) -> str:
        """Learn a user habit"""
        content = habit
        if time:
            content = f"{time}: {habit}"
        
        metadata = {}
        if time:
            metadata["time"] = time
        if location:
            metadata["location"] = location
        
        return await self.store(
            user_id=user_id,
            content=content,
            memory_type=MemoryType.HABIT,
            **metadata
        )

    async def get_preferences(
        self,
        user_id: str,
        category: str = None
    ) -> List[Dict[str, Any]]:
        """Get user preferences"""
        return await self.recall(
            user_id=user_id,
            query="preference",
            memory_type=MemoryType.PREFERENCE,
            category=MemoryCategory(category) if category else None,
            limit=50
        )

    async def get_habits(
        self,
        user_id: str,
        time: str = None
    ) -> List[Dict[str, Any]]:
        """Get user habits"""
        results = await self.recall(
            user_id=user_id,
            query="habit routine",
            memory_type=MemoryType.HABIT,
            limit=50
        )
        
        if time:
            results = [r for r in results if r["metadata"].get("time") == time]
        
        return results

    async def forget(
        self,
        memory_id: str
    ) -> bool:
        """Forget a memory"""
        return await self._vector_store.delete(memory_id)

    async def update(
        self,
        memory_id: str,
        content: str = None,
        confidence: float = None
    ) -> bool:
        """Update a memory"""
        metadata = {}
        if confidence is not None:
            metadata["confidence"] = confidence
        
        return await self._vector_store.update(memory_id, content, metadata)
