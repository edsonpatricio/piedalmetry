"""Brake-pressure to motor-duty-cycle mapping.

Two functions:
  map_brake_to_motor        — maps brake % to ON-power % (linear or power curve)
  map_brake_to_pulse_half_period — maps brake % to pulse half-period (seconds)
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
    # Clamp sensor over-range so a noisy 100%+ input still hits full duty.
    if brake_pct > 100.0:
        brake_pct = 100.0

    if brake_pct < min_brake:
        return 0.0

    span = 100 - min_brake
    if span <= 0:
        return float(min_motor)

    # Normalise brake position to [0, 1] within the active range
    t = (brake_pct - min_brake) / span

    if exponent != 1.0:
        t = t ** exponent

    duty = min_motor + t * (100.0 - min_motor)
    return max(0.0, min(100.0, duty))


def map_brake_to_pulse_half_period(
    brake_pct: float,
    min_brake: int,
    top_limit: int,
    freq_low: float,
    freq_high: float,
    exponent: float = 1.0,
) -> float:
    """Map brake pressure to pulse half-period (seconds).

    Interpolates frequency from freq_low at min_brake to freq_high at top_limit,
    then converts to half-period.  The exponent bends the ramp curve:
      1.0 = linear, >1 = slow start / fast end, <1 = fast start / slow end.
    When top_limit == 0 (continuous zone disabled), 100 is used as the span end.

    Args:
        brake_pct: Filtered brake pressure 0.0–100.0%.
        min_brake: Minimum brake % to activate motor (config).
        top_limit: Brake % threshold for continuous zone; 0 = disabled.
        freq_low: Pulse frequency (Hz) at min_brake_pressure.
        freq_high: Pulse frequency (Hz) at top_limit_pattern.
        exponent: Response curve exponent (shared with motor power ramp).

    Returns:
        Half-period in seconds.
    """
    effective_top = top_limit if top_limit > 0 else 100
    span = effective_top - min_brake
    if span <= 0:
        return 1.0 / (2.0 * freq_high)
    t = max(0.0, min(1.0, (brake_pct - min_brake) / span))
    if exponent != 1.0:
        t = t ** exponent
    freq = freq_low + t * (freq_high - freq_low)
    return 1.0 / (2.0 * freq)
