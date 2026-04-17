"""
Rule Engine Core
Event-driven automation engine for Smart Home
"""
import asyncio
import logging
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime
from collections import defaultdict

from rules.models import Rule, RuleExecution, TriggerType, TriggerConfig
from rules.conditions import ConditionEvaluator
from rules.actions import ActionExecutor
from events.types import EventBase, EventType

logger = logging.getLogger(__name__)


class RuleEngine:
    """
    Core rule engine for Smart Home automation
    Evaluates conditions and executes actions
    """

    def __init__(
        self,
        action_executor: ActionExecutor = None,
        condition_evaluator: ConditionEvaluator = None,
        state_store=None,
        event_bus=None
    ):
        self._action_executor = action_executor or ActionExecutor()
        self._condition_evaluator = condition_evaluator or ConditionEvaluator()
        self._state_store = state_store
        self._event_bus = event_bus

        # Rule storage
        self._rules: Dict[str, Rule] = {}
        self._rules_by_trigger: Dict[TriggerType, List[str]] = defaultdict(list)

        # Execution tracking
        self._running = False
        self._execution_history: List[RuleExecution] = []
        self._max_history = 1000

        # Event handlers
        self._on_rule_executed: Optional[Callable] = None
        self._on_rule_error: Optional[Callable] = None

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def rules(self) -> List[Rule]:
        return list(self._rules.values())

    @property
    def rule_count(self) -> int:
        return len(self._rules)

    def set_state_store(self, state_store) -> None:
        """Set state store"""
        self._state_store = state_store
        self._condition_evaluator.set_state_store(state_store)

    def set_event_bus(self, event_bus) -> None:
        """Set event bus"""
        self._event_bus = event_bus

    def set_action_executor(self, executor: ActionExecutor) -> None:
        """Set action executor"""
        self._action_executor = executor

    def set_on_rule_executed(self, callback: Callable) -> None:
        """Set callback for rule execution"""
        self._on_rule_executed = callback

    def set_on_rule_error(self, callback: Callable) -> None:
        """Set callback for rule errors"""
        self._on_rule_error = callback

    # ==================== Rule Management ====================

    async def add_rule(self, rule: Rule) -> None:
        """Add a rule to the engine"""
        self._rules[rule.id] = rule
        self._rules_by_trigger[rule.trigger.type].append(rule.id)
        
        logger.info(f"Added rule: {rule.name} ({rule.id})")

    async def remove_rule(self, rule_id: str) -> bool:
        """Remove a rule from the engine"""
        if rule_id not in self._rules:
            return False

        rule = self._rules[rule_id]
        
        # Remove from storage
        del self._rules[rule_id]
        
        # Remove from trigger index
        if rule_id in self._rules_by_trigger[rule.trigger.type]:
            self._rules_by_trigger[rule.trigger.type].remove(rule_id)

        logger.info(f"Removed rule: {rule.name} ({rule_id})")
        return True

    async def enable_rule(self, rule_id: str) -> bool:
        """Enable a rule"""
        if rule_id not in self._rules:
            return False
        self._rules[rule_id].enabled = True
        return True

    async def disable_rule(self, rule_id: str) -> bool:
        """Disable a rule"""
        if rule_id not in self._rules:
            return False
        self._rules[rule_id].enabled = False
        return True

    async def get_rule(self, rule_id: str) -> Optional[Rule]:
        """Get rule by ID"""
        return self._rules.get(rule_id)

    async def get_rules_by_tag(self, tag: str) -> List[Rule]:
        """Get rules by tag"""
        return [r for r in self._rules.values() if tag in r.tags]

    async def get_enabled_rules(self) -> List[Rule]:
        """Get all enabled rules"""
        return [r for r in self._rules.values() if r.enabled]

    # ==================== Event Handling ====================

    async def start(self) -> None:
        """Start the rule engine"""
        if self._running:
            return

        self._running = True
        logger.info("Rule engine started")

        # Subscribe to events if event bus available
        if self._event_bus:
            await self._subscribe_to_events()

    async def stop(self) -> None:
        """Stop the rule engine"""
        self._running = False
        logger.info("Rule engine stopped")

    async def _subscribe_to_events(self) -> None:
        """Subscribe to event bus"""
        if not self._event_bus:
            return

        # Subscribe to all event types
        for event_type in EventType:
            self._event_bus.on_event(event_type, self._handle_event)

    async def _handle_event(self, event: EventBase) -> None:
        """Handle incoming event"""
        if not self._running:
            return

        logger.debug(f"Processing event: {event.event_type}")

        # Get rules triggered by this event type
        triggered_rules = await self._get_rules_for_event(event)

        for rule in triggered_rules:
            await self._evaluate_and_execute(rule, event)

    async def _get_rules_for_event(self, event: EventBase) -> List[Rule]:
        """Get rules that should be triggered by this event"""
        triggered = []

        # Check event-triggered rules
        event_rules = self._rules_by_trigger.get(TriggerType.EVENT, [])
        
        for rule_id in event_rules:
            rule = self._rules.get(rule_id)
            if not rule or not rule.enabled:
                continue

            # Check if rule should be triggered by this event type
            if rule.trigger.event_types:
                if event.event_type.value not in rule.trigger.event_types:
                    continue

            # Check topic pattern if specified
            if rule.trigger.topic_pattern:
                topic = getattr(event, "mqtt_topic", "")
                if not self._matches_pattern(topic, rule.trigger.topic_pattern):
                    continue

            triggered.append(rule)

        # Sort by priority
        triggered.sort(key=lambda r: -r.priority)

        return triggered

    def _matches_pattern(self, topic: str, pattern: str) -> bool:
        """Check if topic matches pattern"""
        import fnmatch
        return fnmatch.fnmatch(topic, pattern)

    # ==================== Rule Execution ====================

    async def evaluate_rule(self, rule: Rule, context: Dict[str, Any] = None) -> tuple[bool, List[Dict]]:
        """
        Evaluate rule conditions
        
        Returns:
            Tuple of (conditions_matched, evaluation_details)
        """
        if not rule.conditions:
            return True, []

        self._condition_evaluator.set_sensor_data(context or {})
        
        return await self._condition_evaluator.evaluate_all(
            rule.conditions,
            rule.condition_logic
        )

    async def execute_rule(
        self,
        rule: Rule,
        context: Dict[str, Any] = None
    ) -> RuleExecution:
        """
        Execute a rule
        
        Args:
            rule: Rule to execute
            context: Execution context
            
        Returns:
            RuleExecution record
        """
        start_time = datetime.utcnow()

        execution = RuleExecution(
            rule_id=rule.id,
            rule_name=rule.name,
            triggered_by=context.get("triggered_by", "manual") if context else "manual"
        )

        try:
            # Check if rule can execute
            can_execute, reason = rule.can_execute()
            if not can_execute:
                execution.status = "skipped"
                execution.error = reason
                return execution

            # Evaluate conditions
            conditions_matched, evaluation_details = await self.evaluate_rule(rule, context)
            execution.conditions_evaluated = evaluation_details
            execution.conditions_matched = conditions_matched

            if not conditions_matched:
                execution.status = "skipped"
                execution.error = "Conditions not met"
                return execution

            # Execute actions
            action_results = await self._action_executor.execute_all(
                rule.actions,
                context or {}
            )
            execution.actions_executed = action_results

            # Check overall success
            all_success = all(r.get("success", False) for r in action_results)
            any_success = any(r.get("success", False) for r in action_results)

            if all_success:
                execution.status = "success"
            elif any_success:
                execution.status = "partial"
            else:
                execution.status = "failed"

            # Update rule stats
            rule.mark_executed(success=True)

            logger.info(f"Rule '{rule.name}' executed: {execution.status}")

        except Exception as e:
            execution.status = "failed"
            execution.error = str(e)
            rule.last_error = str(e)
            logger.error(f"Rule '{rule.name}' execution error: {e}")

            if self._on_rule_error:
                try:
                    await self._on_rule_error(rule, e)
                except Exception:
                    pass

        # Calculate execution time
        execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
        execution.execution_time_ms = int(execution_time)

        # Store execution record
        self._add_execution(execution)

        # Fire callback
        if self._on_rule_executed and execution.status != "skipped":
            try:
                await self._on_rule_executed(rule, execution)
            except Exception:
                pass

        return execution

    async def _evaluate_and_execute(
        self,
        rule: Rule,
        event: EventBase
    ) -> Optional[RuleExecution]:
        """Evaluate and execute a rule for an event"""
        if not rule.enabled:
            return None

        # Build context from event
        context = {
            "rule_id": rule.id,
            "event": event.model_dump() if hasattr(event, "model_dump") else {},
            "event_type": event.event_type.value,
            "triggered_by": event.event_type.value,
            "user_id": event.user_id,
        }

        # Add sensor data from event
        if hasattr(event, "sensor_type"):
            context[f"sensor_{event.sensor_type}"] = getattr(event, "value", None)

        return await self.execute_rule(rule, context)

    async def trigger_rule(self, rule_id: str, context: Dict = None) -> Optional[RuleExecution]:
        """Manually trigger a rule"""
        rule = self._rules.get(rule_id)
        if not rule:
            return None

        ctx = context or {}
        ctx["triggered_by"] = "manual"

        return await self.execute_rule(rule, ctx)

    # ==================== Execution History ====================

    def _add_execution(self, execution: RuleExecution) -> None:
        """Add execution to history"""
        self._execution_history.append(execution)
        
        # Trim history
        if len(self._execution_history) > self._max_history:
            self._execution_history = self._execution_history[-self._max_history:]

    async def get_execution_history(
        self,
        rule_id: str = None,
        limit: int = 100,
        status: str = None
    ) -> List[RuleExecution]:
        """Get execution history"""
        history = self._execution_history[-limit:]

        if rule_id:
            history = [h for h in history if h.rule_id == rule_id]

        if status:
            history = [h for h in history if h.status == status]

        return list(reversed(history))

    async def get_rule_stats(self, rule_id: str) -> Dict[str, Any]:
        """Get statistics for a rule"""
        rule = self._rules.get(rule_id)
        if not rule:
            return {}

        executions = await self.get_execution_history(rule_id=rule_id)
        
        success_count = sum(1 for e in executions if e.status == "success")
        failed_count = sum(1 for e in executions if e.status == "failed")
        
        avg_time = 0
        if executions:
            avg_time = sum(e.execution_time_ms for e in executions) / len(executions)

        return {
            "rule_id": rule_id,
            "rule_name": rule.name,
            "enabled": rule.enabled,
            "execution_count": rule.execution_count,
            "success_count": success_count,
            "failed_count": failed_count,
            "avg_execution_time_ms": avg_time,
            "last_triggered": rule.last_triggered.isoformat() if rule.last_triggered else None,
            "last_error": rule.last_error,
        }


# Global rule engine instance
_rule_engine: Optional[RuleEngine] = None


def get_rule_engine() -> RuleEngine:
    """Get rule engine singleton"""
    global _rule_engine
    if _rule_engine is None:
        _rule_engine = RuleEngine()
    return _rule_engine


def set_rule_engine(engine: RuleEngine) -> None:
    """Set rule engine instance"""
    global _rule_engine
    _rule_engine = engine
