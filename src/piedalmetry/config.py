"""TOML configuration loader, validator, and write-back.

References Constitution Principle VII: Configuration-Driven Runtime.
References:
  - Bornhall/gt7telemetry for protocol defaults
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import tomli_w


@dataclass
class PlayStationConfig:
    """PlayStation connection configuration."""

    ip: str = ""
    label: str = ""


@dataclass
class MotorConfig:
    """Motor hardware and mapping configuration."""

    gpio_ena: int = 18
    gpio_in1: int = 23
    gpio_in2: int = 24
    pwm_frequency: int = 1000
    min_brake_pressure: int = 30
    min_motor_strength: int = 50
    min_car_speed: int = 5
    response_exponent: float = 1.0
    top_limit_pattern: int = 0


@dataclass
class AntiFluctuationConfig:
    """Anti-fluctuation filter configuration."""

    dead_zone: float = 2.0
    ema_alpha: float = 0.3


@dataclass
class AppConfig:
    """Complete application configuration."""

    mock_mode: bool = False
    log_level: str = "INFO"
    log_target: str = "stdout"
    motor: MotorConfig = field(default_factory=MotorConfig)
    anti_fluctuation: AntiFluctuationConfig = field(
        default_factory=AntiFluctuationConfig
    )
    playstation: PlayStationConfig = field(default_factory=PlayStationConfig)
    _config_path: str = ""


class ConfigError(Exception):
    """Raised when config validation fails."""


_VALIDATORS: dict[str, tuple[type, Any, Any]] = {
    "motor.gpio_ena": (int, 0, 27),
    "motor.gpio_in1": (int, 0, 27),
    "motor.gpio_in2": (int, 0, 27),
    "motor.pwm_frequency": (int, 50, 25000),
    "motor.min_brake_pressure": (int, 0, 99),
    "motor.min_motor_strength": (int, 1, 99),
    "motor.min_car_speed": (int, 0, 500),
    "motor.response_exponent": (float, 0.1, 10.0),
    "motor.top_limit_pattern": (int, 0, 100),
    "anti_fluctuation.dead_zone": (float, 0.0, 50.0),
    "anti_fluctuation.ema_alpha": (float, 0.0, 1.0),
}


def _get_nested(data: dict[str, Any], dotted_key: str) -> Any:
    """Get a value from a nested dict using dotted notation."""
    keys = dotted_key.split(".")
    current: Any = data
    for k in keys:
        if not isinstance(current, dict) or k not in current:
            return None
        current = current[k]
    return current


def _validate(data: dict[str, Any]) -> list[str]:
    """Validate config data and return list of error messages."""
    errors: list[str] = []

    # Check log_level
    log_level = _get_nested(data, "general.log_level")
    if log_level is not None and log_level not in ("DEBUG", "INFO", "WARNING", "ERROR"):
        errors.append(
            f"Invalid value for general.log_level: {log_level!r} "
            f"(valid: DEBUG, INFO, WARNING, ERROR)"
        )

    # Check log_target
    log_target = _get_nested(data, "general.log_target")
    if log_target is not None and log_target not in ("journald", "stdout", "file"):
        errors.append(
            f"Invalid value for general.log_target: {log_target!r} "
            f"(valid: journald, stdout, file)"
        )

    # Range validations
    for key, (expected_type, min_val, max_val) in _VALIDATORS.items():
        val = _get_nested(data, key)
        if val is None:
            continue  # Use default
        if not isinstance(val, (int, float)):
            errors.append(
                f"Invalid type for {key}: expected number, got {type(val).__name__}"
            )
            continue
        if expected_type is int and isinstance(val, float) and not val.is_integer():
            errors.append(f"Invalid type for {key}: expected integer, got float")
            continue
        if val < min_val or val > max_val:
            errors.append(
                f"Invalid value for {key}: {val} (valid: {min_val}-{max_val})"
            )

    top_limit = _get_nested(data, "motor.top_limit_pattern")
    min_brake = _get_nested(data, "motor.min_brake_pressure")
    if (
        isinstance(top_limit, (int, float))
        and top_limit > 0
        and isinstance(min_brake, (int, float))
        and top_limit <= min_brake
    ):
        errors.append(
            f"Invalid value for motor.top_limit_pattern: {top_limit} "
            f"(must be greater than motor.min_brake_pressure={min_brake})"
        )

    return errors


def load_config(path: str | Path) -> AppConfig:
    """Load, validate, and return AppConfig from a TOML file.

    Raises:
        ConfigError: If the file is missing or contains invalid values.
        FileNotFoundError: If the config file does not exist.
    """
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(
            f"Config file not found: {config_path}. "
            f"Copy config.example.toml to this path and edit as needed."
        )

    with open(config_path, "rb") as f:
        data = tomllib.load(f)

    errors = _validate(data)
    if errors:
        msg = "Config validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
        raise ConfigError(msg)

    general = data.get("general", {})
    motor_data = data.get("motor", {})
    af_data = data.get("anti_fluctuation", {})
    ps_data = data.get("playstation", {})

    return AppConfig(
        mock_mode=general.get("mock_mode", False),
        log_level=general.get("log_level", "INFO"),
        log_target=general.get("log_target", "stdout"),
        motor=MotorConfig(
            gpio_ena=motor_data.get("gpio_ena", 18),
            gpio_in1=motor_data.get("gpio_in1", 23),
            gpio_in2=motor_data.get("gpio_in2", 24),
            pwm_frequency=motor_data.get("pwm_frequency", 1000),
            min_brake_pressure=motor_data.get("min_brake_pressure", 30),
            min_motor_strength=motor_data.get("min_motor_strength", 50),
            min_car_speed=motor_data.get("min_car_speed", 5),
            response_exponent=float(motor_data.get("response_exponent", 1.0)),
            top_limit_pattern=int(motor_data.get("top_limit_pattern", 0)),
        ),
        anti_fluctuation=AntiFluctuationConfig(
            dead_zone=af_data.get("dead_zone", 2.0),
            ema_alpha=af_data.get("ema_alpha", 0.3),
        ),
        playstation=PlayStationConfig(
            ip=ps_data.get("ip", ""),
            label=ps_data.get("label", ""),
        ),
        _config_path=str(config_path),
    )


def write_back_ip(config: AppConfig, ip: str) -> None:
    """Write a discovered PlayStation IP back to the config file.

    Reads the existing TOML, updates the playstation.ip key, and
    writes it back preserving other values.
    """
    config_path = Path(config._config_path)
    if not config_path.exists():
        return

    with open(config_path, "rb") as f:
        data = tomllib.load(f)

    if "playstation" not in data:
        data["playstation"] = {}
    data["playstation"]["ip"] = ip

    with open(config_path, "wb") as f:
        tomli_w.dump(data, f)

    config.playstation.ip = ip
