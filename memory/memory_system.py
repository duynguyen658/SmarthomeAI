"""
Memory System
Unified interface for all memory types
"""
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from memory.vector_store import VectorStore, get_vector_store
from memory.semantic_memory import SemanticMemory, MemoryType, MemoryCategory
from memory.episodic_memory import EpisodicMemory, EventType
from memory.working_memory import WorkingMemory

logger = logging.getLogger(__name__)


class MemorySystem:
    """
    Unified memory system
    Combines semantic, episodic, and working memory
    """

    def __init__(
        self,
        vector_store: VectorStore = None,
        state_store=None
    ):
        self._vector_store = vector_store
        self._semantic = SemanticMemory(vector_store)
        self._episodic = EpisodicMemory()
        self._working = WorkingMemory(state_store)

    async def initialize(self) -> None:
        """Initialize memory system"""
        if self._vector_store is None:
            self._vector_store = await get_vector_store()
        self._semantic.set_vector_store(self._vector_store)
        self._working.set_state_store(self._state_store)

    def set_vector_store(self, vector_store: VectorStore) -> None:
        """Set vector store"""
        self._vector_store = vector_store
        self._semantic.set_vector_store(vector_store)

    def set_state_store(self, state_store) -> None:
        """Set state store"""
        self._working.set_state_store(state_store)

    # ==================== Remember ====================

    async def remember(
        self,
        user_id: str,
        content: str,
        memory_type: str = "fact",
        category: str = "general",
        **metadata
    ) -> str:
        """
        Store a memory
        
        Args:
            user_id: User identifier
            content: Memory content
            memory_type: Type of memory
            category: Category
            **metadata: Additional metadata
            
        Returns:
            Memory ID
        """
        memory_id = await self._semantic.store(
            user_id=user_id,
            content=content,
            memory_type=MemoryType(memory_type),
            category=MemoryCategory(category),
            **metadata
        )

        # Also record as episodic event
        await self._episodic.add(
            user_id=user_id,
            event_type=EventType.USER_INTERACTION,
            event_data={
                "action": "remember",
                "memory_id": memory_id,
                "content": content
            }
        )

        return memory_id

    async def recall(
        self,
        user_id: str,
        query: str,
        limit: int = 10
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Recall memories
        
        Args:
            user_id: User identifier
            query: Search query
            limit: Maximum results
            
        Returns:
            Dict with semantic and episodic memories
        """
        semantic = await self._semantic.recall(user_id, query, limit=limit)
        
        # Get recent episodes
        recent = await self._episodic.get_recent(user_id, limit=limit)

        return {
            "semantic": semantic,
            "recent_episodes": recent
        }

    # ==================== Context Building ====================

    async def build_context(
        self,
        user_id: str,
        query: str = None,
        include_conversation: bool = True,
        include_preferences: bool = True,
        include_device_state: bool = True,
        include_recent_events: bool = True
    ) -> Dict[str, Any]:
        """
        Build context for AI agent
        
        Args:
            user_id: User identifier
            query: Optional query for semantic search
            include_conversation: Include conversation history
            include_preferences: Include user preferences
            include_device_state: Include device states
            include_recent_events: Include recent events
            
        Returns:
            Context dict for agent
        """
        context = {
            "user_id": user_id,
            "timestamp": datetime.utcnow().isoformat()
        }

        # Get working memory context
        working_context = await self._working.get_context(user_id)
        if working_context:
            context["working"] = working_context

        # Semantic memories
        if query:
            memories = await self.recall(user_id, query, limit=20)
            context["memories"] = memories
        else:
            # Get all relevant memories
            memories = await self.recall(user_id, "", limit=20)
            context["memories"] = memories

        # Extract preferences
        preferences = await self._extract_preferences(context.get("memantic", {}).get("semantic", []))
        if preferences:
            context["preferences"] = preferences

        # Conversation history
        if include_conversation:
            conversation = await self._working.get_conversation(user_id, limit=10)
            if conversation:
                context["conversation"] = conversation

        # User preferences from working memory
        if include_preferences:
            prefs = await self._working.get(user_id, "preferences")
            if prefs:
                context["user_preferences"] = prefs

        # Device state
        if include_device_state:
            device_focus = await self._working.get_device_focus(user_id)
            if device_focus:
                context["device_focus"] = device_focus

        # Recent events
        if include_recent_events:
            recent_events = await self._episodic.get_recent(user_id, limit=50)
            context["recent_events"] = recent_events

        return context

    async def _extract_preferences(
        self,
        memories: List[Dict]
    ) -> Dict[str, Any]:
        """Extract preferences from memories"""
        preferences = {}

        for memory in memories:
            metadata = memory.get("metadata", {})
            if metadata.get("type") == "preference":
                category = metadata.get("category", "general")
                preferences[category] = memory.get("text")

        return preferences

    # ==================== Learning ====================

    async def learn_preference(
        self,
        user_id: str,
        preference: str,
        category: str,
        context: str = None
    ) -> str:
        """Learn a user preference"""
        memory_id = await self._semantic.learn_preference(
            user_id=user_id,
            preference=preference,
            category=category,
            context=context
        )

        # Update working memory
        await self._working.set_preference(user_id, category, preference)

        # Record as episode
        await self.record_event(
            user_id=user_id,
            event_type=EventType.USER_INTERACTION,
            event_data={
                "action": "learn_preference",
                "category": category,
                "preference": preference
            }
        )

        return memory_id

    async def learn_habit(
        self,
        user_id: str,
        habit: str,
        time: str = None,
        location: str = None
    ) -> str:
        """Learn a user habit"""
        memory_id = await self._semantic.learn_habit(
            user_id=user_id,
            habit=habit,
            time=time,
            location=location
        )

        # Record as episode
        await self.record_event(
            user_id=user_id,
            event_type=EventType.USER_INTERACTION,
            event_data={
                "action": "learn_habit",
                "habit": habit,
                "time": time,
                "location": location
            }
        )

        return memory_id

    async def learn_from_interaction(
        self,
        user_id: str,
        query: str,
        response: str,
        outcome: str = None,
        device_action: str = None
    ) -> None:
        """
        Learn from user interaction
        
        Args:
            user_id: User identifier
            query: User query
            response: AI response
            outcome: Interaction outcome
            device_action: Device action taken
        """
        # Record interaction
        await self.record_event(
            user_id=user_id,
            event_type=EventType.USER_INTERACTION,
            event_data={
                "query": query,
                "response": response,
                "outcome": outcome,
                "device_action": device_action
            }
        )

        # Add to conversation
        await self._working.set_conversation_turn(user_id, "user", query)
        await self._working.set_conversation_turn(user_id, "assistant", response)

        # Extract and store facts
        if device_action:
            await self.remember(
                user_id=user_id,
                content=f"User requested: {device_action}",
                memory_type="fact",
                category="action"
            )

        # Store confirmed outcomes
        if outcome:
            await self.remember(
                user_id=user_id,
                content=f"Confirmed: {outcome}",
                memory_type="fact",
                category="confirmation"
            )

    # ==================== Events ====================

    async def record_event(
        self,
        user_id: str,
        event_type: str,
        event_data: Dict[str, Any],
        context: Dict[str, Any] = None
    ) -> str:
        """Record an episodic event"""
        return await self._episodic.add(
            user_id=user_id,
            event_type=EventType(event_type),
            event_data=event_data,
            context=context
        )

    async def get_device_history(
        self,
        user_id: str,
        device_uid: str = None,
        days: int = 7
    ) -> List[Dict[str, Any]]:
        """Get device control history"""
        return await self._episodic.get_device_history(
            user_id=user_id,
            device_uid=device_uid,
            days=days
        )

    async def get_alert_history(
        self,
        user_id: str,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """Get alert history"""
        return await self._episodic.get_alert_history(user_id, days=days)

    # ==================== Working Memory ====================

    async def set_user_context(
        self,
        user_id: str,
        context: Dict[str, Any]
    ) -> None:
        """Set user context"""
        await self._working.set_context(user_id, context)

    async def get_user_context(
        self,
        user_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get user context"""
        return await self._working.get_context(user_id)

    async def update_user_context(
        self,
        user_id: str,
        updates: Dict[str, Any]
    ) -> None:
        """Update user context"""
        await self._working.update_context(user_id, updates)

    # ==================== Cleanup ====================

    async def cleanup_old_memories(self, days: int = 30) -> int:
        """Remove old episodic memories"""
        from datetime import datetime, timedelta
        cutoff = datetime.utcnow() - timedelta(days=days)
        return await self._episodic.delete_before(cutoff)


# Global memory system instance
_memory_system: Optional[MemorySystem] = None


def get_memory_system() -> MemorySystem:
    """Get memory system singleton"""
    global _memory_system
    if _memory_system is None:
        _memory_system = MemorySystem()
    return _memory_system


async def initialize_memory_system(
    vector_store: VectorStore = None,
    state_store=None
) -> MemorySystem:
    """Initialize memory system"""
    global _memory_system
    _memory_system = MemorySystem(vector_store, state_store)
    await _memory_system.initialize()
    return _memory_system
