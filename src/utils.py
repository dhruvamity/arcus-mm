"""Mathematical and time utilities for Arcus perpetuals.

Handles exact integer ticks/quantums arithmetic using Decimal and timestamp formatting.
"""

import json
import time
from decimal import Decimal, ROUND_HALF_UP, ROUND_DOWN
from typing import Any, Union


def to_decimal(val: Union[str, int, float, Decimal]) -> Decimal:
    """Safely converts any numeric type or string to Decimal."""
    if isinstance(val, Decimal):
        return val
    return Decimal(str(val))


def to_ticks(
    price: Union[str, int, float, Decimal],
    tick_size: Union[str, int, float, Decimal],
) -> int:
    """Converts a human-readable decimal price to integer ticks.

    The division must be exact with no remainder, or a ValueError is raised.
    """
    p = to_decimal(price)
    ts = to_decimal(tick_size)
    if ts <= 0:
        raise ValueError(f"tick_size must be positive, got {tick_size}")

    n = p / ts
    if n != n.to_integral_value():
        raise ValueError(f"Price {price} is not an exact multiple of tick size {tick_size}")
    return int(n)


def from_ticks(
    ticks: int,
    tick_size: Union[str, int, float, Decimal],
) -> Decimal:
    """Converts integer ticks back to human-readable Decimal price."""
    return Decimal(ticks) * to_decimal(tick_size)


def to_quantums(
    quantity: Union[str, int, float, Decimal],
    step_size: Union[str, int, float, Decimal],
) -> int:
    """Converts a human-readable decimal quantity to integer quantums (steps).

    The division must be exact with no remainder, or a ValueError is raised.
    """
    q = to_decimal(quantity)
    ss = to_decimal(step_size)
    if ss <= 0:
        raise ValueError(f"step_size must be positive, got {step_size}")

    n = q / ss
    if n != n.to_integral_value():
        raise ValueError(f"Quantity {quantity} is not an exact multiple of step size {step_size}")
    return int(n)


def from_quantums(
    quantums: int,
    step_size: Union[str, int, float, Decimal],
) -> Decimal:
    """Converts integer quantums back to human-readable Decimal quantity."""
    return Decimal(quantums) * to_decimal(step_size)


def snap_to_tick(
    price: Union[str, int, float, Decimal],
    tick_size: Union[str, int, float, Decimal],
    rounding: str = ROUND_HALF_UP,
) -> Decimal:
    """Snaps a price to the nearest tick boundary using the specified rounding rule."""
    p = to_decimal(price)
    ts = to_decimal(tick_size)
    num_ticks = (p / ts).quantize(Decimal("1"), rounding=rounding)
    return num_ticks * ts


def snap_to_step(
    quantity: Union[str, int, float, Decimal],
    step_size: Union[str, int, float, Decimal],
    rounding: str = ROUND_DOWN,
) -> Decimal:
    """Snaps a quantity to the nearest step size boundary (defaults to ROUND_DOWN for safety)."""
    q = to_decimal(quantity)
    ss = to_decimal(step_size)
    num_steps = (q / ss).quantize(Decimal("1"), rounding=rounding)
    return num_steps * ss


def now_ns() -> int:
    """Returns current Unix timestamp in nanoseconds."""
    return time.time_ns()


def now_micros() -> int:
    """Returns current Unix timestamp in microseconds."""
    return int(time.time() * 1_000_000)


def good_til_time_micros(days_ahead: int = 40) -> int:
    """Generates epoch microseconds for goodTilTime.

    Arcus requires goodTilTime to be at least 1 month (30 days) in the future.
    Default is 40 days ahead for safety.
    """
    return now_micros() + days_ahead * 86_400 * 1_000_000


def good_til_time_nanos(days_ahead: int = 40) -> int:
    """Generates epoch nanoseconds for 'g' in signed order payloads."""
    return good_til_time_micros(days_ahead) * 1000


def canonical_json(obj: Any) -> str:
    """Serializes a Python object to canonical JSON: sorted keys and no whitespace."""
    return json.dumps(obj, separators=(",", ":"), sort_keys=True)


def canonical_json_bytes(obj: Any) -> bytes:
    """Serializes a Python object to UTF-8 canonical JSON bytes."""
    return canonical_json(obj).encode("utf-8")
