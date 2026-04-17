"""
Device State Machine
Manages valid state transitions for devices
"""
from enum import Enum
from typing import Optional, Dict, Set, List
from dataclasses import dataclass

from core.exceptions import InvalidStateTransitionException


class DeviceStateType(str, Enum):
    """Device state types"""
    ONLINE = "online"
    OFFLINE = "offline"
    ON = "on"
    OFF = "off"
    ERROR = "error"
    UPDATING = "updating"
    UNKNOWN = "unknown"


@dataclass
class StateTransition:
    """Represents a valid state transition"""
    from_state: DeviceStateType
    to_state: DeviceStateType
    trigger: str
    action: Optional[str] = None
    conditions: Optional[List[str]] = None


class DeviceStateMachine:
    """
    State machine for device state management
    Validates and manages state transitions
    """

    # Define valid transitions
    TRANSITIONS: Dict[DeviceStateType, Set[DeviceStateType]] = {
        DeviceStateType.UNKNOWN: {DeviceStateType.ONLINE, DeviceStateType.OFFLINE, DeviceStateType.ERROR},
        DeviceStateType.OFFLINE: {DeviceStateType.ONLINE, DeviceStateType.ERROR},
        DeviceStateType.ONLINE: {
            DeviceStateType.OFFLINE,
            DeviceStateType.ON,
            DeviceStateType.OFF,
            DeviceStateType.ERROR,
            DeviceStateType.UPDATING
        },
        DeviceStateType.ON: {DeviceStateType.OFF, DeviceStateType.ERROR, DeviceStateType.UPDATING},
        DeviceStateType.OFF: {DeviceStateType.ON, DeviceStateType.ERROR, DeviceStateType.UPDATING},
        DeviceStateType.UPDATING: {
            DeviceStateType.ON,
            DeviceStateType.OFF,
            DeviceStateType.ERROR,
            DeviceStateType.ONLINE
        },
        DeviceStateType.ERROR: {
            DeviceStateType.ONLINE,
            DeviceStateType.OFFLINE,
            DeviceStateType.ON,
            DeviceStateType.OFF
        },
    }

    # Define commands and their valid state changes
    COMMANDS: Dict[str, Dict[DeviceStateType, DeviceStateType]] = {
        "connect": {
            DeviceStateType.OFFLINE: DeviceStateType.ONLINE,
            DeviceStateType.UNKNOWN: DeviceStateType.ONLINE,
        },
        "disconnect": {
            DeviceStateType.ONLINE: DeviceStateType.OFFLINE,
            DeviceStateType.ON: DeviceStateType.OFFLINE,
            DeviceStateType.OFF: DeviceStateType.OFFLINE,
        },
        "turn_on": {
            DeviceStateType.ONLINE: DeviceStateType.ON,
            DeviceStateType.OFF: DeviceStateType.ON,
        },
        "turn_off": {
            DeviceStateType.ON: DeviceStateType.OFF,
            DeviceStateType.ONLINE: DeviceStateType.OFF,
        },
        "toggle": {
            DeviceStateType.ON: DeviceStateType.OFF,
            DeviceStateType.OFF: DeviceStateType.ON,
        },
        "error": {state: DeviceStateType.ERROR for state in DeviceStateType},
        "recover": {
            DeviceStateType.ERROR: DeviceStateType.ONLINE,
        },
        "update_start": {
            DeviceStateType.ONLINE: DeviceStateType.UPDATING,
            DeviceStateType.ON: DeviceStateType.UPDATING,
            DeviceStateType.OFF: DeviceStateType.UPDATING,
        },
        "update_complete": {
            DeviceStateType.UPDATING: DeviceStateType.ONLINE,
        },
    }

    # State groups
    POWER_STATES = {DeviceStateType.ON, DeviceStateType.OFF}
    CONNECTIVITY_STATES = {DeviceStateType.ONLINE, DeviceStateType.OFFLINE}
    ALL_STATES = set(DeviceStateType)

    @classmethod
    def is_valid_state(cls, state: str) -> bool:
        """Check if state is valid"""
        try:
            DeviceStateType(state.lower())
            return True
        except ValueError:
            return False

    @classmethod
    def can_transition(cls, from_state: str, to_state: str) -> bool:
        """Check if transition is valid"""
        try:
            from_s = DeviceStateType(from_state.lower())
            to_s = DeviceStateType(to_state.lower())
            return to_s in cls.TRANSITIONS.get(from_s, set())
        except ValueError:
            return False

    @classmethod
    def get_next_state(cls, current_state: str, command: str) -> Optional[str]:
        """Get next state for a command"""
        try:
            current = DeviceStateType(current_state.lower())
            transitions = cls.COMMANDS.get(command, {})
            next_state = transitions.get(current)
            return next_state.value if next_state else None
        except ValueError:
            return None

    @classmethod
    def validate_command(
        cls,
        current_state: str,
        command: str
    ) -> tuple[bool, Optional[str], Optional[str]]:
        """
        Validate if command can be executed in current state
        
        Returns:
            Tuple of (is_valid, next_state, error_message)
        """
        try:
            current = DeviceStateType(current_state.lower())
        except ValueError:
            return False, None, f"Invalid current state: {current_state}"

        next_state = cls.get_next_state(current_state, command)
        
        if next_state is None:
            return False, None, f"Command '{command}' not valid for state '{current_state}'"

        return True, next_state, None

    @classmethod
    def execute_command(
        cls,
        current_state: str,
        command: str,
        raise_on_error: bool = True
    ) -> str:
        """
        Execute a command and return new state
        
        Args:
            current_state: Current device state
            command: Command to execute
            raise_on_error: Whether to raise exception on invalid transition
            
        Returns:
            New state after command execution
            
        Raises:
            InvalidStateTransitionException: If transition is invalid and raise_on_error=True
        """
        is_valid, next_state, error = cls.validate_command(current_state, command)
        
        if not is_valid:
            if raise_on_error:
                raise InvalidStateTransitionException(
                    device_id="unknown",
                    from_state=current_state,
                    to_state=next_state or "unknown"
                )
            return current_state
        
        return next_state

    @classmethod
    def get_available_commands(cls, current_state: str) -> List[str]:
        """Get list of available commands for current state"""
        try:
            current = DeviceStateType(current_state.lower())
        except ValueError:
            return []

        commands = []
        for command, transitions in cls.COMMANDS.items():
            if current in transitions:
                commands.append(command)
        
        return commands

    @classmethod
    def is_powered_on(cls, state: str) -> bool:
        """Check if device is powered on"""
        try:
            return DeviceStateType(state.lower()) == DeviceStateType.ON
        except ValueError:
            return False

    @classmethod
    def is_online(cls, state: str) -> bool:
        """Check if device is online"""
        try:
            s = DeviceStateType(state.lower())
            return s in {DeviceStateType.ONLINE, DeviceStateType.ON, DeviceStateType.UPDATING}
        except ValueError:
            return False

    @classmethod
    def is_error(cls, state: str) -> bool:
        """Check if device is in error state"""
        try:
            return DeviceStateType(state.lower()) == DeviceStateType.ERROR
        except ValueError:
            return False

    @classmethod
    def get_state_info(cls, state: str) -> Dict[str, any]:
        """Get information about a state"""
        try:
            s = DeviceStateType(state.lower())
        except ValueError:
            return {"valid": False, "state": state}

        return {
            "valid": True,
            "state": s.value,
            "is_powered_on": s in {DeviceStateType.ON},
            "is_online": s in {DeviceStateType.ONLINE, DeviceStateType.ON, DeviceStateType.UPDATING},
            "is_error": s == DeviceStateType.ERROR,
            "available_commands": cls.get_available_commands(state),
        }

    @classmethod
    def normalize_state(cls, state: str) -> str:
        """Normalize state string to standard format"""
        state = state.lower().strip()
        
        # Map common variations
        mappings = {
            "true": "on",
            "false": "off",
            "1": "on",
            "0": "off",
            "active": "on",
            "inactive": "off",
            "running": "on",
            "stopped": "off",
            "connected": "online",
            "disconnected": "offline",
        }
        
        return mappings.get(state, state)

    @classmethod
    def get_state_display_name(cls, state: str) -> str:
        """Get display name for state"""
        names = {
            "online": "Đang kết nối",
            "offline": "Ngoại tuyến",
            "on": "Bật",
            "off": "Tắt",
            "error": "Lỗi",
            "updating": "Đang cập nhật",
            "unknown": "Không xác định",
        }
        
        normalized = cls.normalize_state(state)
        return names.get(normalized, state.title())
