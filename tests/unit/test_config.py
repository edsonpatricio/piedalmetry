"""Unit tests for TOML config loading and validation — T011."""

from pathlib import Path

import pytest

from piedalmetry.config import ConfigError, load_config


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

[brake]
brake_gpio_ena = 18
brake_gpio_in1 = 23
brake_gpio_in2 = 24
brake_pwm_frequency = 1000
brake_min_pressure = 30
brake_min_car_speed = 5

[anti_fluctuation]
dead_zone = 2.0
ema_alpha = 0.3

[playstation]
ip = "192.168.1.50"
label = "PS5"
""")
        cfg = load_config(cfg_file)
        assert cfg.mock_mode is True
        assert cfg.brake.gpio_ena == 18
        assert cfg.playstation.ip == "192.168.1.50"

    def test_defaults_used_for_missing_keys(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "config.toml"
        _write_toml(cfg_file, "[general]\nmock_mode = true\n")
        cfg = load_config(cfg_file)
        assert cfg.brake.gpio_ena == 18       # default
        assert cfg.brake.min_pressure == 10   # default

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
        _write_toml(cfg_file, "[brake]\nbrake_min_pressure = 150\n")
        with pytest.raises(ConfigError, match="brake_min_pressure.*150.*0-99"):
            load_config(cfg_file)

    def test_out_of_range_gpio_pin(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "config.toml"
        _write_toml(cfg_file, "[brake]\nbrake_gpio_ena = 99\n")
        with pytest.raises(ConfigError, match="brake_gpio_ena.*99.*0-27"):
            load_config(cfg_file)

    def test_invalid_log_level(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "config.toml"
        _write_toml(cfg_file, '[general]\nlog_level = "TRACE"\n')
        with pytest.raises(ConfigError, match="log_level"):
            load_config(cfg_file)

    def test_invalid_pwm_frequency(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "config.toml"
        _write_toml(cfg_file, "[brake]\nbrake_pwm_frequency = 10\n")
        with pytest.raises(ConfigError, match="brake_pwm_frequency.*10.*50-25000"):
            load_config(cfg_file)

    def test_top_limit_pattern_default(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "config.toml"
        _write_toml(cfg_file, "[general]\nmock_mode = true\n")
        cfg = load_config(cfg_file)
        assert cfg.brake.top_limit_pattern == 98

    def test_top_limit_pattern_loaded(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "config.toml"
        _write_toml(cfg_file, "[brake]\nbrake_min_pressure = 30\nbrake_top_limit_pattern = 85\n")
        cfg = load_config(cfg_file)
        assert cfg.brake.top_limit_pattern == 85

    def test_top_limit_pattern_out_of_range(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "config.toml"
        _write_toml(cfg_file, "[brake]\nbrake_top_limit_pattern = 150\n")
        with pytest.raises(ConfigError, match="brake_top_limit_pattern.*150.*0-100"):
            load_config(cfg_file)

    def test_top_limit_pattern_must_exceed_min_brake(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "config.toml"
        _write_toml(
            cfg_file,
            "[brake]\nbrake_min_pressure = 60\nbrake_top_limit_pattern = 50\n",
        )
        with pytest.raises(ConfigError, match="brake_top_limit_pattern.*greater than"):
            load_config(cfg_file)

    def test_top_limit_pattern_zero_disables_check(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "config.toml"
        _write_toml(cfg_file, "[brake]\nbrake_min_pressure = 60\nbrake_top_limit_pattern = 0\n")
        cfg = load_config(cfg_file)
        assert cfg.brake.top_limit_pattern == 0

    def test_foot_sensor_enabled_defaults_to_true(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "config.toml"
        _write_toml(cfg_file, "[general]\nmock_mode = true\n")
        cfg = load_config(cfg_file)
        assert cfg.brake.foot_sensor_enabled is True

    def test_foot_sensor_gpio_defaults_to_25(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "config.toml"
        _write_toml(cfg_file, "[general]\nmock_mode = true\n")
        cfg = load_config(cfg_file)
        assert cfg.brake.foot_sensor_gpio == 25

    def test_foot_sensor_gpio_loaded(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "config.toml"
        _write_toml(cfg_file, "[brake]\nbrake_foot_sensor_enabled = true\nbrake_foot_sensor_gpio = 22\n")
        cfg = load_config(cfg_file)
        assert cfg.brake.foot_sensor_enabled is True
        assert cfg.brake.foot_sensor_gpio == 22

    def test_foot_sensor_gpio_out_of_range(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "config.toml"
        _write_toml(cfg_file, "[brake]\nbrake_foot_sensor_gpio = 99\n")
        with pytest.raises(ConfigError, match="brake_foot_sensor_gpio.*99.*0-27"):
            load_config(cfg_file)

    def test_foot_sensor_led_gpio_defaults_to_6(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "config.toml"
        _write_toml(cfg_file, "[general]\nmock_mode = true\n")
        cfg = load_config(cfg_file)
        assert cfg.brake.foot_sensor_led_gpio == 6

    def test_foot_sensor_led_gpio_loaded(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "config.toml"
        _write_toml(cfg_file, "[brake]\nbrake_foot_sensor_led_gpio = 13\n")
        cfg = load_config(cfg_file)
        assert cfg.brake.foot_sensor_led_gpio == 13

    def test_foot_sensor_led_gpio_out_of_range(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "config.toml"
        _write_toml(cfg_file, "[brake]\nbrake_foot_sensor_led_gpio = 99\n")
        with pytest.raises(ConfigError, match="brake_foot_sensor_led_gpio.*99.*0-27"):
            load_config(cfg_file)

    def test_shutdown_button_gpio_defaults_to_3(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "config.toml"
        _write_toml(cfg_file, "[general]\nmock_mode = true\n")
        cfg = load_config(cfg_file)
        assert cfg.shutdown_button_gpio == 3

    def test_shutdown_button_gpio_loaded(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "config.toml"
        _write_toml(cfg_file, "[general]\nshutdown_button_gpio = 5\n")
        cfg = load_config(cfg_file)
        assert cfg.shutdown_button_gpio == 5

    def test_shutdown_button_gpio_negative_one_disables(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "config.toml"
        _write_toml(cfg_file, "[general]\nshutdown_button_gpio = -1\n")
        cfg = load_config(cfg_file)
        assert cfg.shutdown_button_gpio == -1

    def test_shutdown_button_gpio_out_of_range(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "config.toml"
        _write_toml(cfg_file, "[general]\nshutdown_button_gpio = 99\n")
        with pytest.raises(ConfigError, match="shutdown_button_gpio.*99.*-1-27"):
            load_config(cfg_file)
