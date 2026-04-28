"""Integration tests: config write-back on PlayStation discovery.

Tests that discovered IP addresses are persisted to the config file.

References:
  - Constitution Principle VII: auto-discovery write-back requirement
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pidalmetry.config import (
    AntiFluctuationConfig,
    AppConfig,
    MotorConfig,
    PlayStationConfig,
    load_config,
    write_back_ip,
)


def _write_config_file(path: Path, ip: str = "") -> None:
    """Write a minimal valid config file to the given path."""
    content = f"""\
[general]
mock_mode = true
log_level = "INFO"
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
ip = {ip!r}
label = "PS5"
"""
    path.write_text(content)


class TestConfigWriteBack:
    """Test that discovered IPs are persisted to the config file."""

    def test_discovered_ip_written_to_config(self, tmp_path: Path) -> None:
        config_file = tmp_path / "config.toml"
        _write_config_file(config_file, ip="")

        cfg = load_config(config_file)
        assert cfg.playstation.ip == ""

        write_back_ip(cfg, "192.168.1.50")

        # Reload from file and verify
        cfg2 = load_config(config_file)
        assert cfg2.playstation.ip == "192.168.1.50"

    def test_write_back_updates_in_memory_config(self, tmp_path: Path) -> None:
        config_file = tmp_path / "config.toml"
        _write_config_file(config_file, ip="")

        cfg = load_config(config_file)
        write_back_ip(cfg, "192.168.1.99")

        # In-memory object should also be updated
        assert cfg.playstation.ip == "192.168.1.99"

    def test_rediscovery_clears_old_ip_and_writes_new_one(
        self, tmp_path: Path
    ) -> None:
        config_file = tmp_path / "config.toml"
        _write_config_file(config_file, ip="192.168.1.50")

        cfg = load_config(config_file)
        assert cfg.playstation.ip == "192.168.1.50"

        # Simulate re-discovery: clear old IP, write new one
        write_back_ip(cfg, "")
        cfg2 = load_config(config_file)
        assert cfg2.playstation.ip == ""

        write_back_ip(cfg2, "192.168.1.77")
        cfg3 = load_config(config_file)
        assert cfg3.playstation.ip == "192.168.1.77"

    def test_write_back_preserves_other_config_keys(
        self, tmp_path: Path
    ) -> None:
        config_file = tmp_path / "config.toml"
        _write_config_file(config_file, ip="")

        cfg = load_config(config_file)
        write_back_ip(cfg, "192.168.1.50")

        cfg2 = load_config(config_file)
        assert cfg2.motor.gpio_ena == 18
        assert cfg2.motor.min_brake_pressure == 30
        assert cfg2.anti_fluctuation.dead_zone == pytest.approx(2.0)
        assert cfg2.log_level == "INFO"

    def test_write_back_noop_if_config_file_missing(self) -> None:
        """write_back_ip should not raise if config file path is gone."""
        cfg = AppConfig(
            motor=MotorConfig(),
            anti_fluctuation=AntiFluctuationConfig(),
            playstation=PlayStationConfig(ip=""),
            _config_path="/nonexistent/path/config.toml",
        )
        # Should not raise
        write_back_ip(cfg, "192.168.1.50")
