"""Structured logging setup for Piedalmetry.

All log entries use key=value format for machine parseability.
References Constitution Principle II: Observability & Structured Logging.
"""

from __future__ import annotations

import logging
import sys
import time
from typing import Any


class KVFormatter(logging.Formatter):
    """Emit log records as ``ts=... level=... module=... msg=...`` lines."""

    def format(self, record: logging.LogRecord) -> str:
        ts = self.formatTime(record, "%Y-%m-%dT%H:%M:%S")
        msg = record.getMessage()
        base = f"ts={ts} level={record.levelname} module={record.module} msg=\"{msg}\""
        # Append any extra kv pairs attached to the record
        extras: dict[str, Any] = getattr(record, "kv", {})
        if extras:
            kv_str = " ".join(f"{k}={v}" for k, v in extras.items())
            base = f"{base} {kv_str}"
        return base


class KVLoggerAdapter(logging.LoggerAdapter):  # type: ignore[type-arg]
    """Logger adapter that passes extra kv pairs to the formatter."""

    def process(
        self, msg: str, kwargs: dict[str, Any]
    ) -> tuple[str, dict[str, Any]]:
        extra = kwargs.get("extra", {})
        kv = (
            {**self.extra, **extra.get("kv", {})} if self.extra else extra.get("kv", {})
        )
        kwargs["extra"] = {**extra, "kv": kv}
        return msg, kwargs


def setup_logging(level: str = "INFO", target: str = "stdout") -> KVLoggerAdapter:
    """Configure and return the application logger.

    Args:
        level: One of DEBUG, INFO, WARNING, ERROR.
        target: One of "stdout", "journald", "file".

    Returns:
        A KVLoggerAdapter wrapping the root piedalmetry logger.
    """
    logger = logging.getLogger("piedalmetry")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    logger.handlers.clear()

    handler: logging.Handler
    if target == "journald":
        # journald receives from stdout when run as systemd service
        handler = logging.StreamHandler(sys.stdout)
    elif target == "file":
        handler = logging.FileHandler("/var/log/piedalmetry.log")
    else:
        handler = logging.StreamHandler(sys.stdout)

    handler.setFormatter(KVFormatter())
    logger.addHandler(handler)
    return KVLoggerAdapter(logger, {})


class LatencyTracker:
    """Measure and log elapsed time for pipeline stages."""

    def __init__(self, logger: KVLoggerAdapter, label: str = "cycle") -> None:
        self._logger = logger
        self._label = label
        self._start: int = 0

    def start(self) -> None:
        self._start = time.monotonic_ns()

    def stop_and_log(self) -> float:
        """Stop timing and log the elapsed milliseconds. Returns ms."""
        elapsed_ns = time.monotonic_ns() - self._start
        elapsed_ms = elapsed_ns / 1_000_000
        self._logger.debug(
            f"{self._label} completed",
            extra={"kv": {"latency_ms": f"{elapsed_ms:.2f}"}},
        )
        return elapsed_ms
