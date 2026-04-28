"""Unit tests for TOML config loading and validation — T011."""

from pathlib import Path

import pytest

from pidalmetry.config import ConfigError, load_config


def _write_toml(path: Path, content: str) -> None:
    path.write_text(content)


class TestConfigValid:
    def test_loads_valid_config(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "config.toml"
        _write_toml(cfg_file, """\
[general]
mock_mode = true
log_level = "DEBUG"
log_target = "stdout"

[motor]
gpio_ena = 18
gpio_in1 = 23
gpio_in2 = 24
pwm_frequency = 1000
min_brake_pressure = 30
min_motor_strength = 50
min_car_speed = 5

[anti_fluctuation]
dead_zone = 2.0
ema_alpha = 0.3

[playstation]
ip = "192.168.1.50"
label = "PS5"
""")
        cfg = load_config(cfg_file)
        assert cfg.mock_mode is True
        assert cfg.motor.gpio_ena == 18
        assert cfg.playstation.ip == "192.168.1.50"

    def test_defaults_used_for_missing_keys(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "config.toml"
        _write_toml(cfg_file, "[general]\nmock_mode = true\n")
        cfg = load_config(cfg_file)
        assert cfg.motor.gpio_ena == 18  # default
        assert cfg.motor.min_brake_pressure == 30  # default

    def test_empty_ps_ip_is_valid(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "config.toml"
        _write_toml(cfg_file, '[playstation]\nip = ""\n')
        cfg = load_config(cfg_file)
        assert cfg.playstation.ip == ""


class TestConfigInvalid:
    def test_missing_file_raises(self) -> None:
        with pytest.raises(FileNotFoundError, match="Config file not found"):
            load_config("/nonexistent/config.toml")

    def test_out_of_range_brake_pressure(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "config.toml"
        _write_toml(cfg_file, "[motor]\nmin_brake_pressure = 150\n")
        with pytest.raises(ConfigError, match="min_brake_pressure.*150.*0-99"):
            load_config(cfg_file)

    def test_out_of_range_gpio_pin(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "config.toml"
        _write_toml(cfg_file, "[motor]\ngpio_ena = 99\n")
        with pytest.raises(ConfigError, match="gpio_ena.*99.*0-27"):
            load_config(cfg_file)

    def test_invalid_log_level(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "config.toml"
        _write_toml(cfg_file, '[general]\nlog_level = "TRACE"\n')
        with pytest.raises(ConfigError, match="log_level"):
            load_config(cfg_file)

    def test_invalid_pwm_frequency(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "config.toml"
        _write_toml(cfg_file, "[motor]\npwm_frequency = 10\n")
        with pytest.raises(ConfigError, match="pwm_frequency.*10.*50-25000"):
            load_config(cfg_file)

    def test_top_limit_pattern_default_is_zero(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "config.toml"
        _write_toml(cfg_file, "[general]\nmock_mode = true\n")
        cfg = load_config(cfg_file)
        assert cfg.motor.top_limit_pattern == 0

    def test_top_limit_pattern_loaded(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "config.toml"
        _write_toml(cfg_file, "[motor]\nmin_brake_pressure = 30\ntop_limit_pattern = 85\n")
        cfg = load_config(cfg_file)
        assert cfg.motor.top_limit_pattern == 85

    def test_top_limit_pattern_out_of_range(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "config.toml"
        _write_toml(cfg_file, "[motor]\ntop_limit_pattern = 150\n")
        with pytest.raises(ConfigError, match="top_limit_pattern.*150.*0-100"):
            load_config(cfg_file)

    def test_top_limit_pattern_must_exceed_min_brake(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "config.toml"
        _write_toml(
            cfg_file,
            "[motor]\nmin_brake_pressure = 60\ntop_limit_pattern = 50\n",
        )
        with pytest.raises(ConfigError, match="top_limit_pattern.*greater than"):
            load_config(cfg_file)

    def test_top_limit_pattern_zero_disables_check(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "config.toml"
        _write_toml(cfg_file, "[motor]\nmin_brake_pressure = 60\ntop_limit_pattern = 0\n")
        cfg = load_config(cfg_file)
        assert cfg.motor.top_limit_pattern == 0
