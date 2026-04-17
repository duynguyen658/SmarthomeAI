"""
Custom exceptions for Smart Home production system
"""


class SmartHomeException(Exception):
    """Base exception for all Smart Home errors"""
    def __init__(self, message: str, code: str = "SMARTHOME_ERROR", details: dict = None):
        self.message = message
        self.code = code
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self) -> dict:
        return {
            "error": self.code,
            "message": self.message,
            "details": self.details
        }


class DeviceNotFoundException(SmartHomeException):
    """Raised when a device is not found"""
    def __init__(self, device_id: str = None, device_uid: str = None, location: str = None):
        identifier = device_id or device_uid or location
        message = f"Device not found: {identifier}"
        super().__init__(message, code="DEVICE_NOT_FOUND", details={"device_id": device_id, "device_uid": device_uid, "location": location})


class DeviceControlException(SmartHomeException):
    """Raised when device control operation fails"""
    def __init__(self, device_id: str, operation: str, reason: str = None):
        message = f"Failed to {operation} device {device_id}"
        if reason:
            message += f": {reason}"
        super().__init__(message, code="DEVICE_CONTROL_ERROR", details={"device_id": device_id, "operation": operation, "reason": reason})


class DeviceOfflineException(DeviceControlException):
    """Raised when attempting to control an offline device"""
    def __init__(self, device_id: str):
        super().__init__(device_id, "control", "Device is offline")
        self.code = "DEVICE_OFFLINE"


class InvalidStateTransitionException(SmartHomeException):
    """Raised when an invalid state transition is attempted"""
    def __init__(self, device_id: str, from_state: str, to_state: str):
        message = f"Invalid state transition for device {device_id}: {from_state} -> {to_state}"
        super().__init__(message, code="INVALID_STATE_TRANSITION", details={"device_id": device_id, "from_state": from_state, "to_state": to_state})


class MQTTConnectionException(SmartHomeException):
    """Raised when MQTT connection fails"""
    def __init__(self, broker: str, port: int, reason: str = None):
        message = f"Failed to connect to MQTT broker {broker}:{port}"
        if reason:
            message += f": {reason}"
        super().__init__(message, code="MQTT_CONNECTION_ERROR", details={"broker": broker, "port": port, "reason": reason})


class MQTTPublishException(SmartHomeException):
    """Raised when MQTT publish fails"""
    def __init__(self, topic: str, reason: str = None):
        message = f"Failed to publish to MQTT topic {topic}"
        if reason:
            message += f": {reason}"
        super().__init__(message, code="MQTT_PUBLISH_ERROR", details={"topic": topic, "reason": reason})


class RuleEngineException(SmartHomeException):
    """Raised when rule engine encounters an error"""
    def __init__(self, rule_id: str = None, message: str = None, reason: str = None):
        msg = message or f"Rule engine error"
        if rule_id:
            msg = f"Error in rule {rule_id}: {msg}"
        super().__init__(msg, code="RULE_ENGINE_ERROR", details={"rule_id": rule_id, "reason": reason})


class RuleConditionException(SmartHomeException):
    """Raised when rule condition evaluation fails"""
    def __init__(self, rule_id: str, condition: dict, reason: str):
        message = f"Failed to evaluate condition in rule {rule_id}"
        super().__init__(message, code="RULE_CONDITION_ERROR", details={"rule_id": rule_id, "condition": condition, "reason": reason})


class RuleActionException(SmartHomeException):
    """Raised when rule action execution fails"""
    def __init__(self, rule_id: str, action: dict, reason: str):
        message = f"Failed to execute action in rule {rule_id}"
        super().__init__(message, code="RULE_ACTION_ERROR", details={"rule_id": rule_id, "action": action, "reason": reason})


class MemoryException(SmartHomeException):
    """Raised when memory system encounters an error"""
    def __init__(self, operation: str, reason: str = None):
        message = f"Memory operation failed: {operation}"
        if reason:
            message += f": {reason}"
        super().__init__(message, code="MEMORY_ERROR", details={"operation": operation, "reason": reason})


class VectorStoreException(MemoryException):
    """Raised when vector store operation fails"""
    def __init__(self, operation: str, reason: str = None):
        super().__init__(f"Vector store {operation}", reason)
        self.code = "VECTOR_STORE_ERROR"


class StateStoreException(SmartHomeException):
    """Raised when state store (Redis) operation fails"""
    def __init__(self, operation: str, reason: str = None):
        message = f"State store operation failed: {operation}"
        if reason:
            message += f": {reason}"
        super().__init__(message, code="STATE_STORE_ERROR", details={"operation": operation, "reason": reason})


class ConfigurationException(SmartHomeException):
    """Raised when configuration is invalid"""
    def __init__(self, setting: str, reason: str):
        message = f"Invalid configuration for {setting}: {reason}"
        super().__init__(message, code="CONFIG_ERROR", details={"setting": setting, "reason": reason})


class EventBusException(SmartHomeException):
    """Raised when event bus operation fails"""
    def __init__(self, operation: str, reason: str = None):
        message = f"Event bus error: {operation}"
        if reason:
            message += f": {reason}"
        super().__init__(message, code="EVENT_BUS_ERROR", details={"operation": operation, "reason": reason})
