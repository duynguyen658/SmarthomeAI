"""
Working Memory
Stores current session context in Redis
"""
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
import json

logger = logging.getLogger(__name__)


class WorkingMemory:
    """
    Working memory storage
    Stores current session context for fast access
    """

    def __init__(self, state_store=None):
        self._state_store = state_store
        self._prefix = "smarthome:working:"

    def set_state_store(self, state_store) -> None:
        """Set state store"""
        self._state_store = state_store

    async def set(
        self,
        user_id: str,
        key: str,
        value: Any,
        ttl: int = 3600
    ) -> None:
        """
        Set working memory
        
        Args:
            user_id: User identifier
            key: Memory key
            value: Memory value
            ttl: Time to live in seconds
        """
        if not self._state_store:
            logger.warning("No state store available")
            return

        await self._state_store.set_working(user_id, key, value, ttl)

    async def get(
        self,
        user_id: str,
        key: str
    ) -> Optional[Any]:
        """Get working memory"""
        if not self._state_store:
            return None

        return await self._state_store.get_working(user_id, key)

    async def delete(
        self,
        user_id: str,
        key: str = None
    ) -> None:
        """Delete working memory"""
        if not self._state_store:
            return

        await self._state_store.delete_working(user_id, key)

    async def set_context(
        self,
        user_id: str,
        context: Dict[str, Any],
        ttl: int = 3600
    ) -> None:
        """Set full session context"""
        await self.set(user_id, "context", context, ttl)

    async def get_context(
        self,
        user_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get full session context"""
        return await self.get(user_id, "context")

    async def update_context(
        self,
        user_id: str,
        updates: Dict[str, Any]
    ) -> None:
        """Update session context"""
        context = await self.get_context(user_id) or {}
        context.update(updates)
        await self.set_context(user_id, context)

    async def set_conversation_turn(
        self,
        user_id: str,
        role: str,
        content: str,
        max_turns: int = 10
    ) -> None:
        """Add a conversation turn"""
        turns = await self.get(user_id, "conversation") or []
        
        turns.append({
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow().isoformat()
        })

        # Keep only recent turns
        if len(turns) > max_turns:
            turns = turns[-max_turns:]

        await self.set(user_id, "conversation", turns)

    async def get_conversation(
        self,
        user_id: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get conversation history"""
        turns = await self.get(user_id, "conversation") or []
        return turns[-limit:]

    async def clear_conversation(self, user_id: str) -> None:
        """Clear conversation history"""
        await self.delete(user_id, "conversation")

    async def set_current_intent(
        self,
        user_id: str,
        intent: str,
        entities: Dict[str, Any] = None
    ) -> None:
        """Set current user intent"""
        await self.set(
            user_id,
            "current_intent",
            {
                "intent": intent,
                "entities": entities or {},
                "timestamp": datetime.utcnow().isoformat()
            }
        )

    async def get_current_intent(
        self,
        user_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get current user intent"""
        return await self.get(user_id, "current_intent")

    async def set_device_focus(
        self,
        user_id: str,
        device_uid: str = None
    ) -> None:
        """Set focused device"""
        await self.set(user_id, "device_focus", device_uid)

    async def get_device_focus(
        self,
        user_id: str
    ) -> Optional[str]:
        """Get focused device"""
        return await self.get(user_id, "device_focus")

    async def add_device_command(
        self,
        user_id: str,
        device_uid: str,
        command: str,
        result: str = None
    ) -> None:
        """Record a device command"""
        commands = await self.get(user_id, "recent_commands") or []
        
        commands.append({
            "device_uid": device_uid,
            "command": command,
            "result": result,
            "timestamp": datetime.utcnow().isoformat()
        })

        # Keep only recent
        if len(commands) > 20:
            commands = commands[-20:]

        await self.set(user_id, "recent_commands", commands)

    async def get_recent_commands(
        self,
        user_id: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get recent device commands"""
        commands = await self.get(user_id, "recent_commands") or []
        return commands[-limit:]

    async def set_preference(
        self,
        user_id: str,
        key: str,
        value: Any
    ) -> None:
        """Set a user preference in working memory"""
        prefs = await self.get(user_id, "preferences") or {}
        prefs[key] = value
        await self.set(user_id, "preferences", prefs)

    async def get_preference(
        self,
        user_id: str,
        key: str,
        default: Any = None
    ) -> Any:
        """Get a user preference"""
        prefs = await self.get(user_id, "preferences") or {}
        return prefs.get(key, default)

    async def clear(self, user_id: str) -> None:
        """Clear all working memory for user"""
        await self.delete(user_id)
