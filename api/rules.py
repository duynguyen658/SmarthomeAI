"""
Rules API
REST API endpoints for rule management
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid

from database import get_db
from rules.engine import get_rule_engine, set_rule_engine
from rules.models import Rule, RuleCondition, RuleAction, TriggerConfig, TriggerType, ActionType, ConditionType, ConditionOperator
from rules.scheduler import get_rule_scheduler

router = APIRouter(prefix="/api/rules", tags=["rules"])


# Pydantic models for API
class ConditionModel(BaseModel):
    type: str
    device_uid: Optional[str] = None
    device_id: Optional[int] = None
    sensor_type: Optional[str] = None
    time: Optional[str] = None
    time_end: Optional[str] = None
    days: Optional[List[str]] = None
    operator: str = "eq"
    value: Any = None
    value2: Any = None
    description: Optional[str] = None


class ActionModel(BaseModel):
    type: str
    device_uid: Optional[str] = None
    device_id: Optional[int] = None
    command: Optional[str] = None
    params: Optional[Dict[str, Any]] = None
    notification: Optional[Dict[str, Any]] = None
    webhook_url: Optional[str] = None
    webhook_method: str = "POST"
    delay_seconds: int = 0
    stop_on_error: bool = False
    description: Optional[str] = None


class TriggerModel(BaseModel):
    type: str = "event"
    event_types: Optional[List[str]] = None
    cron: Optional[str] = None
    time: Optional[str] = None
    days: Optional[List[str]] = None
    interval_seconds: Optional[int] = None


class RuleCreate(BaseModel):
    name: str
    description: Optional[str] = None
    enabled: bool = True
    priority: int = 0
    conditions: List[ConditionModel] = []
    condition_logic: str = "AND"
    actions: List[ActionModel] = []
    trigger: TriggerModel
    cooldown_seconds: int = 0
    max_executions: Optional[int] = None
    tags: List[str] = []


class RuleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    enabled: Optional[bool] = None
    priority: Optional[int] = None
    conditions: Optional[List[ConditionModel]] = None
    condition_logic: Optional[str] = None
    actions: Optional[List[ActionModel]] = None
    trigger: Optional[TriggerModel] = None
    cooldown_seconds: Optional[int] = None
    max_executions: Optional[int] = None
    tags: Optional[List[str]] = None


class RuleResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    enabled: bool
    priority: int
    conditions: List[Dict]
    condition_logic: str
    actions: List[Dict]
    trigger: Dict
    cooldown_seconds: int
    max_executions: Optional[int]
    execution_count: int
    last_triggered: Optional[str]
    created_at: str
    tags: List[str]


def convert_condition_model(c: ConditionModel) -> RuleCondition:
    """Convert API model to RuleCondition"""
    return RuleCondition(
        type=ConditionType(c.type),
        device_uid=c.device_uid,
        device_id=c.device_id,
        sensor_type=c.sensor_type,
        time=c.time,
        time_end=c.time_end,
        days=c.days,
        operator=ConditionOperator(c.operator),
        value=c.value,
        value2=c.value2,
        description=c.description
    )


def convert_action_model(a: ActionModel) -> RuleAction:
    """Convert API model to RuleAction"""
    return RuleAction(
        type=ActionType(a.type),
        device_uid=a.device_uid,
        device_id=a.device_id,
        command=a.command,
        params=a.params,
        notification=a.notification,
        webhook_url=a.webhook_url,
        webhook_method=a.webhook_method,
        delay_seconds=a.delay_seconds,
        stop_on_error=a.stop_on_error,
        description=a.description
    )


def convert_trigger_model(t: TriggerModel) -> TriggerConfig:
    """Convert API model to TriggerConfig"""
    return TriggerConfig(
        type=TriggerType(t.type),
        event_types=t.event_types,
        cron=t.cron,
        time=t.time,
        days=t.days,
        interval_seconds=t.interval_seconds
    )


@router.get("/", response_model=List[RuleResponse])
async def list_rules():
    """List all rules"""
    engine = get_rule_engine()
    rules = engine.rules
    
    return [
        RuleResponse(
            id=r.id,
            name=r.name,
            description=r.description,
            enabled=r.enabled,
            priority=r.priority,
            conditions=[c.model_dump() for c in r.conditions],
            condition_logic=r.condition_logic,
            actions=[a.model_dump() for a in r.actions],
            trigger=r.trigger.model_dump(),
            cooldown_seconds=r.cooldown_seconds,
            max_executions=r.max_executions,
            execution_count=r.execution_count,
            last_triggered=r.last_triggered.isoformat() if r.last_triggered else None,
            created_at=r.created_at.isoformat(),
            tags=r.tags
        )
        for r in rules
    ]


@router.post("/", response_model=RuleResponse)
async def create_rule(rule_data: RuleCreate):
    """Create a new rule"""
    engine = get_rule_engine()
    scheduler = get_rule_scheduler()

    # Convert to rule model
    rule = Rule(
        id=str(uuid.uuid4()),
        name=rule_data.name,
        description=rule_data.description,
        enabled=rule_data.enabled,
        priority=rule_data.priority,
        conditions=[convert_condition_model(c) for c in rule_data.conditions],
        condition_logic=rule_data.condition_logic,
        actions=[convert_action_model(a) for a in rule_data.actions],
        trigger=convert_trigger_model(rule_data.trigger),
        cooldown_seconds=rule_data.cooldown_seconds,
        max_executions=rule_data.max_executions,
        tags=rule_data.tags
    )

    # Add to engine
    await engine.add_rule(rule)

    # Schedule if needed
    if rule.trigger.type == TriggerType.SCHEDULE and rule.enabled:
        scheduler.schedule_rule(rule)

    return RuleResponse(
        id=rule.id,
        name=rule.name,
        description=rule.description,
        enabled=rule.enabled,
        priority=rule.priority,
        conditions=[c.model_dump() for c in rule.conditions],
        condition_logic=rule.condition_logic,
        actions=[a.model_dump() for a in rule.actions],
        trigger=rule.trigger.model_dump(),
        cooldown_seconds=rule.cooldown_seconds,
        max_executions=rule.max_executions,
        execution_count=rule.execution_count,
        last_triggered=None,
        created_at=rule.created_at.isoformat(),
        tags=rule.tags
    )


@router.get("/{rule_id}", response_model=RuleResponse)
async def get_rule(rule_id: str):
    """Get rule by ID"""
    engine = get_rule_engine()
    rule = await engine.get_rule(rule_id)
    
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    return RuleResponse(
        id=rule.id,
        name=rule.name,
        description=rule.description,
        enabled=rule.enabled,
        priority=rule.priority,
        conditions=[c.model_dump() for c in rule.conditions],
        condition_logic=rule.condition_logic,
        actions=[a.model_dump() for a in rule.actions],
        trigger=rule.trigger.model_dump(),
        cooldown_seconds=rule.cooldown_seconds,
        max_executions=rule.max_executions,
        execution_count=rule.execution_count,
        last_triggered=rule.last_triggered.isoformat() if rule.last_triggered else None,
        created_at=rule.created_at.isoformat(),
        tags=rule.tags
    )


@router.put("/{rule_id}", response_model=RuleResponse)
async def update_rule(rule_id: str, rule_data: RuleUpdate):
    """Update a rule"""
    engine = get_rule_engine()
    scheduler = get_rule_scheduler()
    
    rule = await engine.get_rule(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    # Update fields
    if rule_data.name is not None:
        rule.name = rule_data.name
    if rule_data.description is not None:
        rule.description = rule_data.description
    if rule_data.enabled is not None:
        rule.enabled = rule_data.enabled
    if rule_data.priority is not None:
        rule.priority = rule_data.priority
    if rule_data.conditions is not None:
        rule.conditions = [convert_condition_model(c) for c in rule_data.conditions]
    if rule_data.condition_logic is not None:
        rule.condition_logic = rule_data.condition_logic
    if rule_data.actions is not None:
        rule.actions = [convert_action_model(a) for a in rule_data.actions]
    if rule_data.trigger is not None:
        rule.trigger = convert_trigger_model(rule_data.trigger)
    if rule_data.cooldown_seconds is not None:
        rule.cooldown_seconds = rule_data.cooldown_seconds
    if rule_data.max_executions is not None:
        rule.max_executions = rule_data.max_executions
    if rule_data.tags is not None:
        rule.tags = rule_data.tags
    
    rule.updated_at = datetime.utcnow()

    # Update schedule if needed
    if rule.trigger.type == TriggerType.SCHEDULE:
        scheduler.update_schedule(rule)

    return RuleResponse(
        id=rule.id,
        name=rule.name,
        description=rule.description,
        enabled=rule.enabled,
        priority=rule.priority,
        conditions=[c.model_dump() for c in rule.conditions],
        condition_logic=rule.condition_logic,
        actions=[a.model_dump() for a in rule.actions],
        trigger=rule.trigger.model_dump(),
        cooldown_seconds=rule.cooldown_seconds,
        max_executions=rule.max_executions,
        execution_count=rule.execution_count,
        last_triggered=rule.last_triggered.isoformat() if rule.last_triggered else None,
        created_at=rule.created_at.isoformat(),
        tags=rule.tags
    )


@router.delete("/{rule_id}")
async def delete_rule(rule_id: str):
    """Delete a rule"""
    engine = get_rule_engine()
    scheduler = get_rule_scheduler()
    
    # Unschedule first
    scheduler.unschedule_rule(rule_id)
    
    # Remove from engine
    success = await engine.remove_rule(rule_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Rule not found")

    return {"message": "Rule deleted", "rule_id": rule_id}


@router.post("/{rule_id}/toggle")
async def toggle_rule(rule_id: str):
    """Enable or disable a rule"""
    engine = get_rule_engine()
    scheduler = get_rule_scheduler()
    
    rule = await engine.get_rule(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    rule.enabled = not rule.enabled
    
    # Update schedule
    if rule.trigger.type == TriggerType.SCHEDULE:
        scheduler.update_schedule(rule)

    return {"rule_id": rule_id, "enabled": rule.enabled}


@router.post("/{rule_id}/test")
async def test_rule(rule_id: str, context: Optional[Dict[str, Any]] = None):
    """Test execute a rule"""
    engine = get_rule_engine()
    
    rule = await engine.get_rule(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    ctx = context or {}
    ctx["triggered_by"] = "test"

    execution = await engine.execute_rule(rule, ctx)

    return {
        "rule_id": rule_id,
        "rule_name": rule.name,
        "status": execution.status,
        "conditions_matched": execution.conditions_matched,
        "conditions_evaluated": execution.conditions_evaluated,
        "actions_executed": execution.actions_executed,
        "execution_time_ms": execution.execution_time_ms,
        "error": execution.error
    }


@router.get("/{rule_id}/stats")
async def get_rule_stats(rule_id: str):
    """Get rule statistics"""
    engine = get_rule_engine()
    
    stats = await engine.get_rule_stats(rule_id)
    if not stats:
        raise HTTPException(status_code=404, detail="Rule not found")

    return stats


@router.get("/{rule_id}/history")
async def get_rule_history(rule_id: str, limit: int = 50):
    """Get rule execution history"""
    engine = get_rule_engine()
    
    history = await engine.get_execution_history(rule_id=rule_id, limit=limit)
    
    return [
        {
            "id": h.id,
            "triggered_at": h.triggered_at.isoformat(),
            "triggered_by": h.triggered_by,
            "conditions_matched": h.conditions_matched,
            "status": h.status,
            "execution_time_ms": h.execution_time_ms,
            "error": h.error
        }
        for h in history
    ]
