"""
Condition Evaluator for Rule Engine
Evaluates rule conditions against current state
"""
import re
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, time

from rules.models import RuleCondition, ConditionOperator, ConditionType

logger = logging.getLogger(__name__)


class ConditionEvaluator:
    """
    Evaluates conditions against current state
    Used by Rule Engine to determine if rule should fire
    """

    def __init__(self, state_store=None, sensor_data: Dict[str, Any] = None):
        self._state_store = state_store
        self._sensor_data = sensor_data or {}

    def set_state_store(self, state_store) -> None:
        """Set state store instance"""
        self._state_store = state_store

    def set_sensor_data(self, sensor_data: Dict[str, Any]) -> None:
        """Set sensor data for evaluation"""
        self._sensor_data = sensor_data

    async def evaluate(self, condition: RuleCondition) -> bool:
        """
        Evaluate a single condition
        
        Args:
            condition: RuleCondition to evaluate
            
        Returns:
            True if condition is met, False otherwise
        """
        try:
            evaluators = {
                ConditionType.DEVICE_STATE: self._evaluate_device_state,
                ConditionType.SENSOR_VALUE: self._evaluate_sensor_value,
                ConditionType.TIME: self._evaluate_time,
                ConditionType.DAY_OF_WEEK: self._evaluate_day,
                ConditionType.STATE_CHANGE: self._evaluate_state_change,
                ConditionType.ATTRIBUTE: self._evaluate_attribute,
                ConditionType.COMPOSITE: self._evaluate_composite,
            }

            evaluator = evaluators.get(condition.type)
            if not evaluator:
                logger.warning(f"Unknown condition type: {condition.type}")
                return False

            result = await evaluator(condition)
            
            if condition.description:
                logger.debug(f"Condition '{condition.description}': {result}")
            
            return result

        except Exception as e:
            logger.error(f"Error evaluating condition: {e}")
            return False

    async def evaluate_all(
        self,
        conditions: List[RuleCondition],
        logic: str = "AND"
    ) -> tuple[bool, List[Dict[str, Any]]]:
        """
        Evaluate multiple conditions
        
        Args:
            conditions: List of conditions to evaluate
            logic: "AND" or "OR"
            
        Returns:
            Tuple of (result, evaluation_details)
        """
        results = []
        all_passed = True

        for condition in conditions:
            passed = await self.evaluate(condition)
            results.append({
                "condition_id": condition.id,
                "condition_type": condition.type,
                "passed": passed,
                "description": condition.description
            })
            
            if logic == "AND":
                if not passed:
                    all_passed = False
            else:  # OR
                if passed:
                    all_passed = True
                    break

        return all_passed, results

    async def _evaluate_device_state(self, condition: RuleCondition) -> bool:
        """Evaluate device state condition"""
        device_uid = condition.device_uid
        
        # Try to get from sensor_data first (for event-driven)
        device_state = self._sensor_data.get("device_states", {}).get(device_uid)
        
        if not device_state and self._state_store:
            device_state = await self._state_store.get_state(device_uid)

        if not device_state:
            return False

        current_state = device_state.get("state", "")
        
        return self._compare(
            current_state.lower(),
            condition.value.lower() if isinstance(condition.value, str) else condition.value,
            condition.operator
        )

    async def _evaluate_sensor_value(self, condition: RuleCondition) -> bool:
        """Evaluate sensor value condition"""
        sensor_type = condition.sensor_type
        expected_value = condition.value
        value2 = condition.value2
        
        # Get current sensor value
        current_value = self._sensor_data.get(f"sensor_{sensor_type}")
        
        if current_value is None:
            # Try from sensor_data dict
            current_value = self._sensor_data.get(sensor_type)
        
        if current_value is None and self._state_store:
            sensor_data = await self._state_store.get_sensor_data(sensor_type)
            if sensor_data:
                current_value = sensor_data.get("value")

        if current_value is None:
            return False

        try:
            current_value = float(current_value)
        except (ValueError, TypeError):
            return False

        if condition.operator == ConditionOperator.BETWEEN:
            try:
                min_val = float(expected_value)
                max_val = float(value2)
                return min_val <= current_value <= max_val
            except (ValueError, TypeError):
                return False

        try:
            return self._compare(current_value, float(expected_value), condition.operator)
        except (ValueError, TypeError):
            return False

    async def _evaluate_time(self, condition: RuleCondition) -> bool:
        """Evaluate time condition"""
        target_time_str = condition.time
        if not target_time_str:
            return False

        try:
            target_time = datetime.strptime(target_time_str, "%H:%M").time()
        except ValueError:
            return False

        current_time = datetime.now().time()

        if condition.operator == ConditionOperator.BETWEEN:
            if not condition.time_end:
                return False
            try:
                end_time = datetime.strptime(condition.time_end, "%H:%M").time()
            except ValueError:
                return False
            
            return self._time_between(current_time, target_time, end_time)

        return self._compare_time(current_time, target_time, condition.operator)

    async def _evaluate_day(self, condition: RuleCondition) -> bool:
        """Evaluate day of week condition"""
        if not condition.days:
            return False

        current_day = datetime.now().strftime("%A").lower()
        allowed_days = [d.lower() for d in condition.days]

        return current_day in allowed_days

    async def _evaluate_state_change(self, condition: RuleCondition) -> bool:
        """Evaluate state change condition"""
        device_uid = condition.device_uid
        expected_from = condition.value
        expected_to = condition.value2

        # Get previous and current state from sensor_data
        device_states = self._sensor_data.get("device_states", {}).get(device_uid, {})
        
        previous_state = device_states.get("previous_state")
        current_state = device_states.get("state")

        if expected_from and previous_state:
            if expected_from.lower() != previous_state.lower():
                return False
        
        if expected_to and current_state:
            if expected_to.lower() != current_state.lower():
                return False
        
        return True

    async def _evaluate_attribute(self, condition: RuleCondition) -> bool:
        """Evaluate device attribute condition"""
        device_uid = condition.device_uid
        attribute = condition.attribute

        if not self._state_store or not device_uid or not attribute:
            return False

        device_state = await self._state_store.get_state(device_uid)
        if not device_state:
            return False

        attributes = device_state.get("attributes", {})
        current_value = attributes.get(attribute)

        if current_value is None:
            return False

        return self._compare(current_value, condition.value, condition.operator)

    async def _evaluate_composite(self, condition: RuleCondition) -> bool:
        """Evaluate composite condition (AND/OR of nested conditions)"""
        if not condition.conditions:
            return False

        results = []
        for nested_condition in condition.conditions:
            result = await self.evaluate(nested_condition)
            results.append(result)

        if condition.logic == "AND":
            return all(results)
        else:  # OR
            return any(results)

    def _compare(self, current: Any, expected: Any, operator: ConditionOperator) -> bool:
        """Compare values using operator"""
        operators = {
            ConditionOperator.EQ: lambda a, b: str(a).lower() == str(b).lower() if isinstance(b, str) else a == b,
            ConditionOperator.NE: lambda a, b: str(a).lower() != str(b).lower() if isinstance(b, str) else a != b,
            ConditionOperator.GT: lambda a, b: float(a) > float(b),
            ConditionOperator.LT: lambda a, b: float(a) < float(b),
            ConditionOperator.GTE: lambda a, b: float(a) >= float(b),
            ConditionOperator.LTE: lambda a, b: float(a) <= float(b),
            ConditionOperator.CONTAINS: lambda a, b: str(b) in str(a),
            ConditionOperator.STARTS_WITH: lambda a, b: str(a).startswith(str(b)),
            ConditionOperator.ENDS_WITH: lambda a, b: str(a).endswith(str(b)),
            ConditionOperator.REGEX: lambda a, b: bool(re.match(str(b), str(a))),
            ConditionOperator.IN: lambda a, b: a in (b if isinstance(b, list) else [b]),
        }
        
        return operators.get(operator, lambda a, b: False)(current, expected)

    def _compare_time(self, current: time, expected: time, operator: ConditionOperator) -> bool:
        """Compare time values"""
        operators = {
            ConditionOperator.EQ: lambda a, b: a == b,
            ConditionOperator.GT: lambda a, b: a > b,
            ConditionOperator.LT: lambda a, b: a < b,
            ConditionOperator.GTE: lambda a, b: a >= b,
            ConditionOperator.LTE: lambda a, b: a <= b,
        }
        
        return operators.get(operator, lambda a, b: False)(current, expected)

    def _time_between(self, current: time, start: time, end: time) -> bool:
        """Check if current time is between start and end"""
        if start <= end:
            return start <= current <= end
        else:
            # Handle overnight (e.g., 22:00 to 06:00)
            return current >= start or current <= end
