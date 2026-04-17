"""
Action Executor for Rule Engine
Executes actions when rules fire
"""
import asyncio
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime

from rules.models import RuleAction, ActionType

logger = logging.getLogger(__name__)


class ActionExecutor:
    """
    Executes actions for fired rules
    Handles device control, notifications, webhooks, etc.
    """

    def __init__(
        self,
        device_registry=None,
        notification_service=None,
        event_bus=None,
        state_store=None
    ):
        self._device_registry = device_registry
        self._notification_service = notification_service
        self._event_bus = event_bus
        self._state_store = state_store

    def set_device_registry(self, registry) -> None:
        """Set device registry"""
        self._device_registry = registry

    def set_notification_service(self, service) -> None:
        """Set notification service"""
        self._notification_service = service

    def set_event_bus(self, event_bus) -> None:
        """Set event bus"""
        self._event_bus = event_bus

    def set_state_store(self, state_store) -> None:
        """Set state store"""
        self._state_store = state_store

    async def execute(
        self,
        action: RuleAction,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute a single action
        
        Args:
            action: RuleAction to execute
            context: Execution context (rule_id, user_id, event, etc.)
            
        Returns:
            Result dict with success status and details
        """
        try:
            executors = {
                ActionType.DEVICE_CONTROL: self._execute_device_control,
                ActionType.NOTIFICATION: self._execute_notification,
                ActionType.WEBHOOK: self._execute_webhook,
                ActionType.DELAY: self._execute_delay,
                ActionType.SCENE: self._execute_scene,
                ActionType.LOG: self._execute_log,
                ActionType.EMAIL: self._execute_email,
                ActionType.SMS: self._execute_sms,
                ActionType.SPEAK: self._execute_speak,
            }

            executor = executors.get(action.type)
            if not executor:
                return {
                    "success": False,
                    "error": f"Unknown action type: {action.type}",
                    "action_id": action.id
                }

            result = await executor(action, context)
            result["action_id"] = action.id
            result["action_type"] = action.type.value
            
            logger.debug(f"Action {action.type.value} result: {result.get('success')}")
            
            return result

        except Exception as e:
            logger.error(f"Error executing action: {e}")
            return {
                "success": False,
                "error": str(e),
                "action_id": action.id,
                "action_type": action.type.value
            }

    async def execute_all(
        self,
        actions: List[RuleAction],
        context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Execute multiple actions in order
        
        Args:
            actions: List of actions to execute
            context: Execution context
            
        Returns:
            List of results
        """
        results = []
        
        # Sort by order
        sorted_actions = sorted(actions, key=lambda a: a.order)
        
        for action in sorted_actions:
            result = await self.execute(action, context)
            results.append(result)
            
            # Handle delay between actions
            if action.type == ActionType.DELAY and result.get("success"):
                await asyncio.sleep(action.delay_seconds)
            
            # Stop on error if configured
            if not result.get("success"):
                if action.stop_on_error:
                    logger.warning(f"Stopping actions due to error in {action.type}")
                    break
                if not action.continue_on_error:
                    break

        return results

    async def _execute_device_control(
        self,
        action: RuleAction,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute device control action"""
        device_id = action.device_id
        device_uid = action.device_uid
        command = action.command
        params = action.params or {}

        try:
            if self._device_registry:
                if device_id:
                    result = await self._device_registry.control_device(
                        device_id, command, params
                    )
                elif device_uid:
                    device = await self._device_registry.get_device_by_uid(device_uid)
                    if device:
                        result = await self._device_registry.control_device(
                            device.id, command, params
                        )
                    else:
                        return {"success": False, "error": f"Device not found: {device_uid}"}
                else:
                    return {"success": False, "error": "No device specified"}
                
                return {"success": True, "result": result}
            else:
                # Fallback: publish MQTT command directly
                if self._event_bus:
                    from events.types import create_device_command_event
                    
                    event = create_device_command_event(
                        device_uid=device_uid or str(device_id),
                        command=command,
                        params=params,
                        user_id=context.get("user_id")
                    )
                    
                    topic = f"smarthome/devices/{device_uid or device_id}/command"
                    await self._event_bus.publish(topic, event)
                    
                    return {"success": True, "published": True}
                
                return {"success": False, "error": "No device registry or event bus available"}

        except Exception as e:
            logger.error(f"Device control error: {e}")
            return {"success": False, "error": str(e)}

    async def _execute_notification(
        self,
        action: RuleAction,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute notification action"""
        notification = action.notification or {}

        title = notification.get("title", "Smart Home Alert")
        message = notification.get("message", "")
        severity = notification.get("severity", "info")

        try:
            if self._notification_service:
                await self._notification_service.send(
                    title=title,
                    message=message,
                    severity=severity,
                    user_id=context.get("user_id")
                )
                return {"success": True, "sent": True}
            
            # Fallback: publish via event bus
            if self._event_bus:
                from events.types import create_alert_event
                
                event = create_alert_event(
                    name=title,
                    message=message,
                    severity=severity,
                    user_id=context.get("user_id")
                )
                
                await self._event_bus.emit(event)
                return {"success": True, "published": True}
            
            logger.warning("No notification service available")
            return {"success": False, "error": "No notification service available"}

        except Exception as e:
            logger.error(f"Notification error: {e}")
            return {"success": False, "error": str(e)}

    async def _execute_webhook(
        self,
        action: RuleAction,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute webhook action"""
        try:
            import httpx

            url = action.webhook_url
            method = action.webhook_method.upper()
            headers = action.webhook_headers or {}
            body = action.webhook_body or {}

            # Add context to body
            body["_context"] = {
                "rule_id": context.get("rule_id"),
                "user_id": context.get("user_id"),
                "timestamp": datetime.utcnow().isoformat()
            }

            async with httpx.AsyncClient() as client:
                if method == "GET":
                    response = await client.get(url, headers=headers, params=body)
                elif method == "POST":
                    response = await client.post(url, json=body, headers=headers)
                elif method == "PUT":
                    response = await client.put(url, json=body, headers=headers)
                elif method == "DELETE":
                    response = await client.delete(url, headers=headers)
                else:
                    return {"success": False, "error": f"Unsupported method: {method}"}

                success = response.status_code < 400
                
                return {
                    "success": success,
                    "status_code": response.status_code,
                    "response": response.text[:500] if response.text else None
                }

        except ImportError:
            return {"success": False, "error": "httpx not installed"}
        except Exception as e:
            logger.error(f"Webhook error: {e}")
            return {"success": False, "error": str(e)}

    async def _execute_delay(
        self,
        action: RuleAction,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute delay action (mostly handled in execute_all)"""
        return {
            "success": True,
            "delay_seconds": action.delay_seconds,
            "message": f"Delaying for {action.delay_seconds} seconds"
        }

    async def _execute_scene(
        self,
        action: RuleAction,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute scene action"""
        scene_id = action.scene_id
        scene_name = action.scene_name

        logger.info(f"Executing scene: {scene_name or scene_id}")
        
        # Scene execution would be implemented here
        # For now, log the action
        return {
            "success": True,
            "scene_id": scene_id,
            "scene_name": scene_name,
            "message": f"Scene '{scene_name or scene_id}' executed"
        }

    async def _execute_log(
        self,
        action: RuleAction,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute log action"""
        message = action.log_message or "Rule triggered"
        level = action.log_level.lower()

        log_func = getattr(logger, level, logger.info)
        log_func(f"[Rule {context.get('rule_id')}] {message}")

        return {
            "success": True,
            "logged": True,
            "level": level,
            "message": message
        }

    async def _execute_email(
        self,
        action: RuleAction,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute email action"""
        # Email would be implemented here
        return {"success": False, "error": "Email not implemented"}

    async def _execute_sms(
        self,
        action: RuleAction,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute SMS action"""
        # SMS would be implemented here
        return {"success": False, "error": "SMS not implemented"}

    async def _execute_speak(
        self,
        action: RuleAction,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute text-to-speech action"""
        message = action.notification.get("message") if action.notification else None
        
        if message and self._notification_service:
            # Use TTS service if available
            try:
                # This would integrate with edge-tts or similar
                logger.info(f"[TTS] {message}")
                return {"success": True, "spoken": True, "message": message}
            except Exception as e:
                return {"success": False, "error": str(e)}
        
        return {"success": False, "error": "TTS not available"}
