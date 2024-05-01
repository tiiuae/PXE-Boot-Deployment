from __future__ import annotations
from enum import Enum
from typing import Dict


class POEPort(object):

    class Power(Enum):
        Off = 'off'
        On = 'auto-on'
        ForcedON = 'forced-on'

        @staticmethod
        def from_string(value: str) -> POEPort.Power:
            for state in POEPort.Power:
                if state.value == value:
                    return state
            raise ValueError(f'Value "{value}" is unsupported')

        def __str__(self) -> str:
            return self.value

        def __repr__(self) -> str:
            return self.value

    class Voltage(Enum):
        Auto = 'auto'
        Low = 'low'
        High = 'high'

        @staticmethod
        def from_string(value: str) -> POEPort.Voltage:
            for volt in POEPort.Voltage:
                if volt.value == value:
                    return volt
            raise ValueError(f'Value "{value}" is unsupported')

        def __str__(self) -> str:
            return self.value

        def __repr__(self) -> str:
            return self.value

    def __init__(self, name: str):
        self.name: str = name
        self.state: POEPort.Power = POEPort.Power.Off
        self.voltage: POEPort.Voltage = POEPort.Voltage.Auto
        self.__priority: int = 0
        self.__lldp_enabled: bool = False
        self.__cycle_ping_enabled: bool = False
        self.power_cycle_interval: str = 'none'

    @property
    def priority(self) -> int:
        return self.__priority

    @priority.setter
    def priority(self, value) -> None:
        self.__priority = self.cast_to_int(value)

    @property
    def lldp_enabled(self) -> bool:
        return self.__lldp_enabled

    @lldp_enabled.setter
    def lldp_enabled(self, enabled) -> None:
        self.__lldp_enabled = self.extract_boolean_parameter(enabled)

    @property
    def cycle_ping_enabled(self) -> bool:
        return self.__cycle_ping_enabled

    @cycle_ping_enabled.setter
    def cycle_ping_enabled(self, enabled) -> None:
        self.__cycle_ping_enabled = self.extract_boolean_parameter(enabled)

    @staticmethod
    def str_to_bool(value: str) -> bool:
        if value.lower() in ['1', 'yes', 'true', 'enabled', 'y']:
            return True
        elif value.lower() in ['0', 'n', 'no', 'none', 'false', 'disabled']:
            return False
        else:
            raise ValueError(f'Can not cast from String "{value}" to the Boolean type')

    @staticmethod
    def extract_boolean_parameter(value) -> bool:
        if isinstance(value, bool):
            return value
        elif isinstance(value, str):
            return POEPort.str_to_bool(value)
        else:
            # Hoping the type of the 'enabled' is convertible to bool
            return bool(value)

    @staticmethod
    def cast_to_int(value) -> int:
        return value if isinstance(value, int) else int(value)

    def __str__(self) -> str:
        return f'POEPort({str(self.__repr__())})'

    def __repr__(self) -> Dict:
        return {
            'name': self.name,
            'state': self.state,
            'voltage': self.voltage,
            'priority': self.priority,
            'lldp_enabled': self.lldp_enabled,
            'cycle_ping_enabled': self.cycle_ping_enabled,
            'power_cycle_interval': self.power_cycle_interval,
        }
