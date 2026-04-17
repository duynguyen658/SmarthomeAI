"""
Rule models for Smart Home automation engine
Pydantic models for rules, conditions, and actions
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
import uuid


class ConditionOperator(str, Enum):
    """Operators for condition evaluation"""
    EQ = "eq"          # Equal
    NE = "ne"          # Not equal
    GT = "gt"          # Greater than
    LT = "lt"          # Less than
    GTE = "gte"        # Greater than or equal
    LTE = "lte"        # Less than or equal
    BETWEEN = "between"  # Between range
    CONTAINS = "contains"
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"
    REGEX = "regex"
    IN = "in"          # Value in list


class ConditionType(str, Enum):
    """Types of conditions"""
    DEVICE_STATE = "device_state"
    SENSOR_VALUE = "sensor_value"
    TIME = "time"
    DAY_OF_WEEK = "day_of_week"
    STATE_CHANGE = "state_change"
    ATTRIBUTE = "attribute"
    COMPOSITE = "composite"


class ActionType(str, Enum):
    """Types of actions"""
    DEVICE_CONTROL = "device_control"
    NOTIFICATION = "notification"
    WEBHOOK = "webhook"
    DELAY = "delay"
    SCENE = "scene"
    LOG = "log"
    EMAIL = "email"
    SMS = "sms"
    SPEAK = "speak"


class TriggerType(str, Enum):
    """Types of rule triggers"""
    EVENT = "event"
    SCHEDULE = "schedule"
    MANUAL = "manual"


class RuleCondition(BaseModel):
    """Condition for rule evaluation"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: ConditionType
    description: Optional[str] = None
    
    # Device state condition
    device_uid: Optional[str] = None
    device_id: Optional[int] = None
    
    # Sensor condition
    sensor_type: Optional[str] = None
    
    # Time condition
    time: Optional[str] = None  # HH:MM format
    time_end: Optional[str] = None  # For BETWEEN time
    
    # Day of week
    days: Optional[List[str]] = None  # ["monday", "tuesday", ...]
    
    # Attribute condition
    attribute: Optional[str] = None
    
    # Comparison
    operator: ConditionOperator = ConditionOperator.EQ
    value: Any = None
    value2: Any = None  # For BETWEEN operator
    
    # Nested conditions (for COMPOSITE)
    conditions: Optional[List["RuleCondition"]] = None
    logic: str = "AND"  # AND/OR for nested conditions
    
    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump(exclude_none=True)


class RuleAction(BaseModel):
    """Action to execute when rule conditions are met"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: ActionType
    description: Optional[str] = None
    order: int = 0  # Execution order
    
    # Device control action
    device_uid: Optional[str] = None
    device_id: Optional[int] = None
    command: Optional[str] = None  # on, off, toggle, set
    params: Optional[Dict[str, Any]] = None
    
    # Notification action
    notification: Optional[Dict[str, Any]] = None  # {title, message, severity}
    
    # Webhook action
    webhook_url: Optional[str] = None
    webhook_method: str = "POST"
    webhook_headers: Optional[Dict[str, str]] = None
    webhook_body: Optional[Dict[str, Any]] = None
    
    # Delay action
    delay_seconds: int = 0
    
    # Scene action
    scene_id: Optional[str] = None
    scene_name: Optional[str] = None
    
    # Log action
    log_message: Optional[str] = None
    log_level: str = "info"
    
    # Control
    stop_on_error: bool = False
    continue_on_error: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump(exclude_none=True)


class TriggerConfig(BaseModel):
    """Configuration for rule trigger"""
    type: TriggerType
    
    # Event trigger config
    event_types: Optional[List[str]] = None  # ["device.state.changed", ...]
    topic_pattern: Optional[str] = None  # MQTT topic pattern
    
    # Schedule trigger config
    cron: Optional[str] = None  # Cron expression
    time: Optional[str] = None  # HH:MM format
    days: Optional[List[str]] = None  # Days of week
    
    # Interval trigger
    interval_seconds: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump(exclude_none=True)


class Rule(BaseModel):
    """Automation rule model"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: Optional[str] = None
    
    enabled: bool = True
    priority: int = 0  # Higher = more priority (executed first)
    
    # Conditions
    conditions: List[RuleCondition] = Field(default_factory=list)
    condition_logic: str = "AND"  # AND/OR
    
    # Actions
    actions: List[RuleAction] = Field(default_factory=list)
    
    # Trigger
    trigger: TriggerConfig
    
    # Execution control
    cooldown_seconds: int = 0  # Minimum time between executions
    max_executions: Optional[int] = None  # Max times rule can fire
    execution_count: int = 0
    
    # State
    last_triggered: Optional[datetime] = None
    last_executed: Optional[datetime] = None
    last_error: Optional[str] = None
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: Optional[str] = None
    
    # Tags for grouping
    tags: List[str] = Field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        data = self.model_dump(exclude_none=True)
        # Convert datetime to ISO string
        for key in ["created_at", "updated_at", "last_triggered", "last_executed"]:
            if key in data and isinstance(data[key], datetime):
                data[key] = data[key].isoformat()
        return data

    def can_execute(self) -> tuple[bool, str]:
        """Check if rule can be executed"""
        # Check if enabled
        if not self.enabled:
            return False, "Rule is disabled"
        
        # Check max executions
        if self.max_executions and self.execution_count >= self.max_executions:
            return False, "Max executions reached"
        
        # Check cooldown
        if self.cooldown_seconds > 0 and self.last_triggered:
            elapsed = (datetime.utcnow() - self.last_triggered).total_seconds()
            if elapsed < self.cooldown_seconds:
                return False, f"In cooldown ({elapsed:.0f}s elapsed)"
        
        return True, ""

    def mark_executed(self, success: bool = True, error: str = None) -> None:
        """Mark rule as executed"""
        self.execution_count += 1
        self.last_executed = datetime.utcnow()
        self.last_triggered = datetime.utcnow()
        if not success:
            self.last_error = error


class RuleExecution(BaseModel):
    """Record of rule execution"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    rule_id: str
    rule_name: str
    
    triggered_at: datetime = Field(default_factory=datetime.utcnow)
    triggered_by: str  # event_type, schedule, manual
    
    conditions_evaluated: List[Dict[str, Any]] = Field(default_factory=list)
    conditions_matched: bool
    
    actions_executed: List[Dict[str, Any]] = Field(default_factory=list)
    
    status: str = "success"  # success, partial, failed, skipped
    error: Optional[str] = None
    
    execution_time_ms: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        data = self.model_dump(exclude_none=True)
        if isinstance(data.get("triggered_at"), datetime):
            data["triggered_at"] = data["triggered_at"].isoformat()
        return data


class RuleTemplate(BaseModel):
    """Template for creating common rules"""
    name: str
    description: str
    category: str  # lighting, climate, security, energy, custom
    conditions: List[Dict[str, Any]]
    actions: List[Dict[str, Any]]
    trigger_type: TriggerType = TriggerType.EVENT


# Common rule templates
RULE_TEMPLATES = {
    "auto_lights": RuleTemplate(
        name="Auto Lights",
        description="Turn on lights when it gets dark",
        category="lighting",
        conditions=[
            {"type": "sensor_value", "sensor_type": "light", "operator": "lt", "value": 800}
        ],
        actions=[
            {"type": "device_control", "command": "on"}
        ]
    ),
    "gas_alert": RuleTemplate(
        name="Gas Alert",
        description="Alert when gas level is dangerous",
        category="security",
        conditions=[
            {"type": "sensor_value", "sensor_type": "gas", "operator": "gt", "value": 2000}
        ],
        actions=[
            {"type": "notification", "notification": {"title": "Gas Alert", "severity": "critical"}}
        ]
    ),
    "night_mode": RuleTemplate(
        name="Night Mode",
        description="Turn off all lights at 11 PM",
        category="lighting",
        conditions=[
            {"type": "time", "time": "23:00"}
        ],
        actions=[
            {"type": "device_control", "command": "off"}
        ],
        trigger_type=TriggerType.SCHEDULE
    ),
    "morning_routine": RuleTemplate(
        name="Morning Routine",
        description="Turn on lights and fan at 6 AM",
        category="custom",
        conditions=[
            {"type": "time", "time": "06:00"},
            {"type": "day_of_week", "days": ["monday", "tuesday", "wednesday", "thursday", "friday"]}
        ],
        actions=[
            {"type": "device_control", "device_type": "light", "command": "on"},
            {"type": "device_control", "device_type": "fan", "command": "on"}
        ],
        trigger_type=TriggerType.SCHEDULE
    ),
}
