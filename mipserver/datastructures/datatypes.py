"""Enumerations and type aliases shared across the mipserver package.

The types in here carry no behaviour of their own; they exist so that the rest of
the package can be annotated precisely instead of falling back to ``Any``.
"""

from enum import StrEnum, auto
from typing import Dict, List, Optional, Union

#: A JSON scalar as produced by :func:`json.load` / accepted by :func:`json.dump`.
JSONScalar = Union[None, bool, int, float, str]

#: Any value that can appear in a parsed JSON document.
#:
#: Used instead of ``Any`` wherever data crosses the JSON boundary (package.json
#: files, YAML settings documents, ...). Consumers have to narrow the union before
#: use, which is exactly the intent.
JSONValue = Union[JSONScalar, List["JSONValue"], Dict[str, "JSONValue"]]

#: A parsed JSON object, i.e. the common top-level shape of the files read here.
JSONObject = Dict[str, JSONValue]


class MPYPath(StrEnum):
    """Selects what the ``mip`` client wants to be served for a package.

    The value is taken verbatim from the first path segment of the
    ``/package/{mpy_version}/...`` request, hence the non-descriptive member names.

    Attributes:
        six: mpy bytecode format version 6; sources are cross-compiled to ``.mpy``.
        py: plain Python sources are served as-is.
    """

    six = "6"
    py = "py"

    @classmethod
    def _missing_(cls, value: object) -> Optional["MPYPath"]:
        """Resolve a member by its value rather than by its member name.

        Args:
            value: The value to look up, e.g. ``"6"`` or ``"py"``.

        Returns:
            The matching member, or ``None`` if no member carries that value, in
            which case the enum raises a ``ValueError``.
        """
        for member in cls:
            if member.value == value:
                return member
        return None


# class MStrEnum(Enum):
#     """StrEnum is introduced in 3.11 and not available in runtime 3.9"""
#     def _generate_next_value_(name, start, count, last_values):
#         return name.lower()


class SensorType(StrEnum):
    """Sensor vendor/protocol families.

    Leftover from the project this app was scaffolded from; kept because
    :class:`mipserver.datastructures.models.Sensor` still references it. Members
    take their lower-cased member name as value.
    """

    lupus = auto()
    tasmota = auto()
    reolink = auto()
    esp = auto()
