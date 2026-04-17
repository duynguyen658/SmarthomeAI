"""
Rule Scheduler
Schedule-based rule triggers using APScheduler
"""
import logging
from typing import Dict, Optional, List
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.date import DateTrigger

from rules.models import Rule, TriggerConfig, TriggerType
from rules.engine import RuleEngine

logger = logging.getLogger(__name__)


class RuleScheduler:
    """
    Scheduler for time-based rule triggers
    Wraps APScheduler for rule execution
    """

    def __init__(self, rule_engine: RuleEngine = None):
        self._scheduler = AsyncIOScheduler()
        self._rule_engine = rule_engine
        self._job_map: Dict[str, str] = {}  # rule_id -> job_id

    def set_rule_engine(self, engine: RuleEngine) -> None:
        """Set rule engine"""
        self._rule_engine = engine

    def start(self) -> None:
        """Start the scheduler"""
        if not self._scheduler.running:
            self._scheduler.start()
            logger.info("Rule scheduler started")

    def stop(self) -> None:
        """Stop the scheduler"""
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)
            logger.info("Rule scheduler stopped")

    @property
    def is_running(self) -> bool:
        return self._scheduler.running

    def schedule_rule(self, rule: Rule) -> Optional[str]:
        """
        Schedule a rule based on its trigger configuration
        
        Args:
            rule: Rule to schedule
            
        Returns:
            Job ID if scheduled, None otherwise
        """
        if rule.trigger.type == TriggerType.SCHEDULE:
            job_id = self._do_schedule(rule)
        elif rule.trigger.type == TriggerType.EVENT:
            # Event-based rules are handled by rule engine
            job_id = None
        elif rule.trigger.type == TriggerType.MANUAL:
            # Manual rules are not scheduled
            job_id = None
        else:
            logger.warning(f"Unknown trigger type: {rule.trigger.type}")
            return None

        if job_id:
            self._job_map[rule.id] = job_id
            logger.info(f"Scheduled rule: {rule.name} ({rule.id})")

        return job_id

    def _do_schedule(self, rule: Rule) -> Optional[str]:
        """Schedule rule based on trigger config"""
        trigger_config = rule.trigger

        # Cron expression
        if trigger_config.cron:
            try:
                # Parse simple cron (minute hour day month day_of_week)
                parts = trigger_config.cron.split()
                if len(parts) >= 5:
                    trigger = CronTrigger(
                        minute=parts[0],
                        hour=parts[1],
                        day=parts[2],
                        month=parts[3],
                        day_of_week=parts[4]
                    )
                else:
                    logger.error(f"Invalid cron expression: {trigger_config.cron}")
                    return None
            except Exception as e:
                logger.error(f"Failed to parse cron: {e}")
                return None

        # Time-based with days
        elif trigger_config.time:
            try:
                hour, minute = map(int, trigger_config.time.split(":"))
            except ValueError:
                logger.error(f"Invalid time format: {trigger_config.time}")
                return None

            if trigger_config.days:
                # Specific days of week
                days_map = {
                    "monday": 0, "tuesday": 1, "wednesday": 2,
                    "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6
                }
                day_nums = [days_map[d.lower()] for d in trigger_config.days if d.lower() in days_map]
                
                if day_nums:
                    trigger = CronTrigger(
                        day_of_week=",".join(map(str, day_nums)),
                        hour=hour,
                        minute=minute
                    )
                else:
                    logger.error(f"No valid days specified: {trigger_config.days}")
                    return None
            else:
                # Daily
                trigger = CronTrigger(hour=hour, minute=minute)

        # Interval-based
        elif trigger_config.interval_seconds:
            trigger = IntervalTrigger(seconds=trigger_config.interval_seconds)

        else:
            logger.error(f"No valid schedule config for rule: {rule.name}")
            return None

        # Add job
        job_id = f"rule_{rule.id}"
        
        try:
            self._scheduler.add_job(
                self._execute_scheduled_rule,
                trigger=trigger,
                args=[rule.id],
                id=job_id,
                name=rule.name,
                replace_existing=True
            )
            return job_id
        except Exception as e:
            logger.error(f"Failed to schedule rule: {e}")
            return None

    def unschedule_rule(self, rule_id: str) -> bool:
        """
        Unschedule a rule
        
        Args:
            rule_id: Rule ID to unschedule
            
        Returns:
            True if unscheduled, False if not found
        """
        if rule_id not in self._job_map:
            return False

        job_id = self._job_map[rule_id]

        try:
            self._scheduler.remove_job(job_id)
            del self._job_map[rule_id]
            logger.info(f"Unscheduled rule: {rule_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to unschedule rule {rule_id}: {e}")
            return False

    def update_schedule(self, rule: Rule) -> Optional[str]:
        """
        Update schedule for a rule
        
        Args:
            rule: Rule with updated trigger config
            
        Returns:
            New job ID if rescheduled, None otherwise
        """
        # Remove existing schedule
        self.unschedule_rule(rule.id)
        
        # Schedule with new config
        if rule.enabled and rule.trigger.type == TriggerType.SCHEDULE:
            return self.schedule_rule(rule)
        
        return None

    def reschedule_all(self, rules: List[Rule]) -> int:
        """
        Reschedule all rules
        
        Args:
            rules: List of rules to schedule
            
        Returns:
            Number of rules scheduled
        """
        # Clear existing schedules
        self._scheduler.remove_all_jobs()
        self._job_map.clear()

        # Schedule enabled rules
        count = 0
        for rule in rules:
            if rule.enabled and rule.trigger.type == TriggerType.SCHEDULE:
                if self.schedule_rule(rule):
                    count += 1

        logger.info(f"Rescheduled {count} rules")
        return count

    def get_scheduled_jobs(self) -> List[Dict[str, any]]:
        """Get list of scheduled jobs"""
        jobs = self._scheduler.get_jobs()
        return [
            {
                "id": job.id,
                "name": job.name,
                "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
                "rule_id": job.id.replace("rule_", "") if job.id.startswith("rule_") else None
            }
            for job in jobs
        ]

    async def _execute_scheduled_rule(self, rule_id: str) -> None:
        """Execute a scheduled rule"""
        if not self._rule_engine:
            logger.error("No rule engine configured")
            return

        rule = await self._rule_engine.get_rule(rule_id)
        if not rule:
            logger.warning(f"Rule not found: {rule_id}")
            return

        if not rule.enabled:
            logger.debug(f"Rule disabled, skipping: {rule.name}")
            return

        context = {
            "rule_id": rule_id,
            "triggered_by": "schedule"
        }

        try:
            await self._rule_engine.execute_rule(rule, context)
            logger.debug(f"Executed scheduled rule: {rule.name}")
        except Exception as e:
            logger.error(f"Error executing scheduled rule {rule.name}: {e}")


# Global scheduler instance
_rule_scheduler: Optional[RuleScheduler] = None


def get_rule_scheduler(rule_engine: RuleEngine = None) -> RuleScheduler:
    """Get rule scheduler singleton"""
    global _rule_scheduler
    if _rule_scheduler is None:
        _rule_scheduler = RuleScheduler(rule_engine)
    return _rule_scheduler


def set_rule_scheduler(scheduler: RuleScheduler) -> None:
    """Set rule scheduler instance"""
    global _rule_scheduler
    _rule_scheduler = scheduler
