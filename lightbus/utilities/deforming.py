# The opposite of casting. See lightbus.utilities.casting
from collections import OrderedDict
from datetime import datetime, date
from decimal import Decimal
from enum import Enum
from uuid import UUID

from lightbus.exceptions import DeformError
from lightbus.utilities.frozendict import frozendict
from lightbus.utilities.type_checks import is_namedtuple, is_dataclass, isinstance_safe


def deform_to_bus(value):
    """Convert value into one which can be safely serialised
    and encoded onto the bus

    The opposite of cast_to_signature()
    """
    if value is None:
        return value
    elif hasattr(value, "__to_bus__"):
        return value.__to_bus__()
    elif isinstance(value, OrderedDict):
        return deform_to_bus(dict(value))
    elif isinstance_safe(value, dict):
        for dict_key, dict_value in value.items():
            value[dict_key] = deform_to_bus(dict_value)
        return value
    elif is_namedtuple(value):
        return deform_to_bus(dict(value._asdict()))
    elif is_dataclass(value):
        from dataclasses import asdict

        return deform_to_bus(asdict(value))
    elif isinstance_safe(value, frozendict):
        return deform_to_bus(value._dict)
    elif isinstance_safe(value, Enum):
        return deform_to_bus(value.value)
    elif isinstance_safe(value, (datetime, date)):
        return value.isoformat()
    elif isinstance_safe(value, UUID):
        return str(value)
    elif type(value) == tuple:
        return list(value)
    elif isinstance_safe(value, list):
        return [deform_to_bus(v) for v in value]
    elif isinstance_safe(value, (int, float, str)):
        return value
    elif isinstance_safe(value, (Decimal, complex)):
        return str(value)
    elif hasattr(value, "__module__"):
        # some kind of custom object we don't recognise
        raise DeformError(
            f"Failed to deform value of type {type(value)} for "
            f"transmission on the bus. Perhaps specify the "
            f"__to_bus__() and __from_bus__() methods on the class. Alternatively, "
            f"transform the data before placing it onto the bus."
        )
    else:
        # A built-in that we missed in the above checks?
        return value
