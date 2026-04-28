"""Brake-pressure to motor-duty-cycle mapping with configurable response curve.

The mapping runs from (min_brake → min_motor) to (100% → 100%).
Below min_brake the motor is off (0%).
100% brake always maps to 100% motor — this is NOT configurable (FR-014).

The response exponent controls the curve shape:
  exponent = 1.0  → linear (proportional)
  exponent > 1.0  → power curve (gentle at light braking, aggressive at heavy)
  exponent = 2.0  → quadratic; recommended for realistic haptic rumble feel
"""

from __future__ import annotations


def map_brake_to_motor(
    brake_pct: float,
    min_brake: int = 30,
    min_motor: int = 50,
    exponent: float = 1.0,
) -> float:
    """Map brake pressure percentage to motor duty cycle percentage.

    Args:
        brake_pct: Brake pressure 0.0–100.0%.
        min_brake: Minimum brake % to activate motor (config).
        min_motor: Motor strength % at min_brake (config).
        exponent: Response curve exponent. 1.0 = linear. >1 bends the
            curve downward so the motor stays quiet under light braking
            and ramps up aggressively toward maximum.

    Returns:
        Motor duty cycle 0.0–100.0%.
    """
    if brake_pct < min_brake:
        return 0.0

    if brake_pct >= 100.0:
        return 100.0

    # Normalise brake position to [0, 1] within the active range
    t = (brake_pct - min_brake) / (100.0 - min_brake)

    if exponent != 1.0:
        t = t ** exponent

    duty = min_motor + t * (100.0 - min_motor)
    return max(0.0, min(100.0, duty))
