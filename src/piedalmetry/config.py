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
    label: str = "PS5"
    conn_led_gpio: int = 17


@dataclass
class BrakeConfig:
    """Brake feedback hardware and mapping configuration."""

    gpio_ena: int = 18
    gpio_in1: int = 23
    gpio_in2: int = 24
    pwm_frequency: int = 100
    min_pressure: int = 10
    min_strength: int = 50
    min_car_speed: int = 0
    min_pulse_freq: float = 3.0
    max_pulse_freq: float = 12.0
    feedback_exponent: float = 3.0
    top_limit_pattern: int = 98
    foot_sensor_enabled: bool = True
    foot_sensor_gpio: int = 25
    foot_sensor_feed_gpio: int = 21
    foot_sensor_led_gpio: int = 6


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
    brake: BrakeConfig = field(default_factory=BrakeConfig)
    anti_fluctuation: AntiFluctuationConfig = field(
        default_factory=AntiFluctuationConfig
    )
    playstation: PlayStationConfig = field(default_factory=PlayStationConfig)
    _config_path: str = ""


class ConfigError(Exception):
    """Raised when config validation fails."""


_VALIDATORS: dict[str, tuple[type, Any, Any]] = {
    "brake.brake_gpio_ena": (int, 0, 27),
    "brake.brake_gpio_in1": (int, 0, 27),
    "brake.brake_gpio_in2": (int, 0, 27),
    "brake.brake_pwm_frequency": (int, 50, 25000),
    "brake.brake_min_pressure": (int, 0, 99),
    "brake.brake_min_strength": (int, 1, 99),
    "brake.brake_min_car_speed": (int, 0, 500),
    "brake.brake_min_pulse_freq": (float, 0.1, 20.0),
    "brake.brake_max_pulse_freq": (float, 0.1, 20.0),
    "brake.brake_feedback_exponent": (float, 0.1, 10.0),
    "brake.brake_top_limit_pattern": (int, 0, 100),
    "brake.brake_foot_sensor_gpio": (int, 0, 27),
    "brake.brake_foot_sensor_feed_gpio": (int, 0, 27),
    "brake.brake_foot_sensor_led_gpio": (int, 0, 27),
    "playstation.ps_conn_led_gpio": (int, 0, 27),
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

    top_limit = _get_nested(data, "brake.brake_top_limit_pattern")
    min_pressure = _get_nested(data, "brake.brake_min_pressure")
    if (
        isinstance(top_limit, (int, float))
        and top_limit > 0
        and isinstance(min_pressure, (int, float))
        and top_limit <= min_pressure
    ):
        errors.append(
            f"Invalid value for brake.brake_top_limit_pattern: {top_limit} "
            f"(must be greater than brake.brake_min_pressure={min_pressure})"
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
    brake_data = data.get("brake", {})
    af_data = data.get("anti_fluctuation", {})
    ps_data = data.get("playstation", {})

    return AppConfig(
        mock_mode=general.get("mock_mode", False),
        log_level=general.get("log_level", "INFO"),
        log_target=general.get("log_target", "stdout"),
        brake=BrakeConfig(
            gpio_ena=brake_data.get("brake_gpio_ena", 18),
            gpio_in1=brake_data.get("brake_gpio_in1", 23),
            gpio_in2=brake_data.get("brake_gpio_in2", 24),
            pwm_frequency=brake_data.get("brake_pwm_frequency", 100),
            min_pressure=brake_data.get("brake_min_pressure", 10),
            min_strength=brake_data.get("brake_min_strength", 50),
            min_car_speed=brake_data.get("brake_min_car_speed", 0),
            min_pulse_freq=float(brake_data.get("brake_min_pulse_freq", 3.0)),
            max_pulse_freq=float(brake_data.get("brake_max_pulse_freq", 12.0)),
            feedback_exponent=float(brake_data.get("brake_feedback_exponent", 3.0)),
            top_limit_pattern=int(brake_data.get("brake_top_limit_pattern", 98)),
            foot_sensor_enabled=bool(brake_data.get("brake_foot_sensor_enabled", True)),
            foot_sensor_gpio=int(brake_data.get("brake_foot_sensor_gpio", 25)),
            foot_sensor_feed_gpio=int(brake_data.get("brake_foot_sensor_feed_gpio", 21)),
            foot_sensor_led_gpio=int(brake_data.get("brake_foot_sensor_led_gpio", 6)),
        ),
        anti_fluctuation=AntiFluctuationConfig(
            dead_zone=af_data.get("dead_zone", 2.0),
            ema_alpha=af_data.get("ema_alpha", 0.3),
        ),
        playstation=PlayStationConfig(
            ip=ps_data.get("ip", ""),
            label=ps_data.get("label", "PS5"),
            conn_led_gpio=int(ps_data.get("ps_conn_led_gpio", 17)),
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
