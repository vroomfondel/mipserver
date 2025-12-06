from enum import auto, StrEnum
from typing import Any, Optional


class MPYPath(StrEnum):
    six = "6"
    py = "py"

    @classmethod
    def _missing_(cls, value: Any) -> Optional["MPYPath"]:
        """Ermöglicht die Initialisierung mit dem String-Wert anstelle des Member-Namens"""
        for member in cls:
            if member.value == value:
                return member
        return None


# class MStrEnum(Enum):
#     """StrEnum is introduced in 3.11 and not available in runtime 3.9"""
#     def _generate_next_value_(name, start, count, last_values):
#         return name.lower()

class SensorType(StrEnum):
    lupus = auto()
    tasmota = auto()
    reolink = auto()
    esp = auto()


