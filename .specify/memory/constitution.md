<!--
  Sync Impact Report
  ==================
  Version change: 1.2.0 → 1.2.1
  Modified principles:
    - VII. Configuration-Driven Runtime — expanded PlayStation IP
      config key with auto-discovery rules
  Added sections: None
  Removed sections: None
  Templates requiring updates:
    ✅ plan-template.md   — No changes needed
    ✅ spec-template.md   — No changes needed
    ✅ tasks-template.md  — No changes needed
    ✅ commands/*.md      — No changes needed
    ✅ AGENTS.md          — No changes needed
  Follow-up TODOs: None
-->

# Pidalmetry Constitution

## Core Principles

### I. Hardware-First Documentation

Every hardware component (Raspberry Pi 2B GPIO, L298N motor driver,
12V rumble motor) MUST be documented with:

- Mermaid diagrams inside Markdown files showing wiring topology
- Pin-out images clearly identifying the first pin on each board
- Exact GPIO BCM numbers, voltage levels, and current limits
- Physical connection tables mapping Pi pins → L298N pins → motor
- RPi.GPIO over gpiozero: gpiozero is more modern, but could be les compatible with dietpi.
- Rationale: A wiring mistake can destroy hardware; documentation
  MUST be unambiguous enough for someone to reproduce the setup
  without prior electronics experience.

### II. Observability & Structured Logging

All runtime behaviour MUST be observable:

- Structured logging (JSON or key=value) at every layer: UDP
  listener, Salsa20 decryption, brake-pressure mapping, PWM output
- Log levels: DEBUG, INFO, WARNING, ERROR — configurable at runtime
- The CLI MUST expose `log` and `troubleshoot` sub-commands to
  inspect service health, tail logs, and diagnose issues on the Pi
- Rationale: Embedded systems are hard to debug in situ; logs are
  often the only debugging tool available on a headless DietPi box.

### III. Test & Mock Everything

Testing is mandatory at every boundary:

- Unit tests for telemetry parsing, Salsa20 decryption, and
  brake-to-PWM mapping logic.
- Mock motor driver MUST simulate L298N PWM output without real
  GPIO hardware, enabling development and CI on x86 machines.
- Mock GT7 telemetry server MUST replay captured UDP packets for
  deterministic end-to-end tests.
- Mock GT7 telemetry server MUST active the motor.
- We can choose a percentage range of mock brake pressure to active motor as real packages.
- Integration tests MUST cover the full pipeline: UDP → decrypt →
  map → PWM (using mocks for hardware).
- The CLI MUST expose a `mock` sub-command to exercise the motor
  mapping without a live GT7 session.
- Rationale: Hardware is not always available; every code path
  MUST be verifiable without physical devices.
- Should be possible run with `uv run python` (documentated way) to test before installation

### IV. Performance-Constrained Design

The Raspberry Pi 2B (ARMv7, 1 GB RAM, quad-core 900 MHz) and
DietPi impose hard resource limits:

- Latency budget: brake-pressure-to-motor-output minimum possible and it should log the latency
- No heavy frameworks; prefer standard-library solutions
- UDP packet processing MUST be non-blocking
- Salsa20 decryption MUST use a C-extension or native binding
  (pure-Python crypto is too slow for real-time on ARMv7)
- Rationale: Exceeding resource limits causes thermal throttling,
  OOM kills, or unacceptable latency on Pi 2B hardware.

### V. Service-Native Deployment

The application MUST run as a systemd service on DietPi:

- A single `install` CLI command (or script) MUST configure and
  enable the systemd unit file
- The service MUST start on boot, restart on failure, and log
  to journald
- Uninstall MUST cleanly remove the service and configuration
- The CLI MUST provide `status`, `start`, `stop`, `restart` proxy
  commands for the underlying service
- Rationale: A headless Pi demands unattended operation; manual
  process management is unacceptable in production.


### VI. Simplicity & Reproducibility

- Python with `uv` as the sole dependency/project manager
- Minimal dependency tree — every third-party package MUST be
  justified in `pyproject.toml` comments or docs
- Single `uv sync && pidalmetry install` MUST be sufficient to
  go from a fresh DietPi image to a running service
- YAGNI: no web UI, no database, no cloud connectivity unless
  explicitly requested later
- Rationale: Complexity is the enemy of reliability on embedded
  systems; fewer moving parts mean fewer failure modes.

### VII. Configuration-Driven Runtime

All tuneable runtime parameters MUST be managed through a
configuration file — not hard-coded or solely via CLI flags:

- The project MUST define a documented config file format (TOML
  preferred, aligning with `pyproject.toml` conventions)
- The config file MUST have a well-defined schema with:
  - Every key documented (purpose, type, default, valid range)
  - An annotated example file shipped in the repository
    (e.g. `config.example.toml`)
  - Validation at startup with clear error messages for invalid
    or missing values
- Config keys MUST cover at minimum:
  - PlayStation IP address — with auto-discovery behaviour:
    - If the `playstation_ip` key is empty or absent, the service
      MUST perform UDP broadcast discovery to locate the console
    - On successful discovery, the service MUST:
      1. Log the discovered IP at INFO level
      2. Write the discovered IP back into the config file so
         subsequent restarts use it directly
    - If the configured (or previously discovered) IP fails to
      respond after **3 consecutive connection attempts** with
      at least **3 seconds between each attempt**, the service
      MUST:
      1. Log a WARNING indicating the configured IP is
         unreachable and discovery will re-run
      2. Clear the stored IP in the config file
      3. Re-run broadcast discovery
      4. On success, log and persist the new IP as above
    - This cycle MUST repeat indefinitely so the service
      self-heals when the console changes IP (e.g. DHCP lease
      renewal)
  - UDP listen port
  - GPIO pin assignments (ENA, IN1, IN2): the number of Raspberry Pi 2 Model B physical pins
  - Log level and log output target (journald / file / stdout)
  - Mock mode toggle
- CLI flags MAY override config file values, but the config file
  is the canonical source of truth
- Config file location MUST follow XDG conventions or use a
  well-documented fixed path (e.g. `/etc/pidalmetry/config.toml`)
- Rationale: A headless Pi cannot be interactively configured;
  a single, validated config file reduces deployment errors and
  enables reproducible setups across devices.


## Platform & Hardware Constraints

- **Target board**: Raspberry Pi 2 Model B (BCM2836, ARMv7,
  1 GB RAM)
- **OS**: DietPi (Debian-based minimal image)
- **Python**: 3.11+ (DietPi-compatible, ARMv7 wheels available)
- **Motor driver**: L298N dual H-bridge
- **Motor**: 12V DC rumble motor (single channel)
- **Power**: Separate 12V supply for motor; Pi powered via USB
- **GPIO library**: `RPi.GPIO`
- **Networking**: UDP port 33739 (GT7 telemetry default)
- **Speed unit**: km/h

## Development Workflow

- **Branching**: Feature branches per speckit convention
- **Commits**: Atomic, prefixed (`feat:`, `fix:`, `docs:`, `test:`,
  `chore:`)
- **CI gate**: All tests MUST pass; mocks MUST exercise the full
  pipeline without hardware
- **Documentation gate**: Every PR touching hardware wiring or pin
  assignments MUST update the corresponding Mermaid diagram and
  pin-out image
- **Code style**: `ruff` for linting and formatting; enforced in CI
- **Type checking**: `mypy` strict mode; all public APIs MUST have
  type annotations
- **Code storage and cross-compilitaion**: This repo is mirrored on dietpi@192.168.1.128 (copies thourght SSH is not necessary, it is already mirrored), in /home/dietpi/dev/pidalmetry. The code can be create here, but it MUST be run and tested on the RPi 2B, not on host Mac. Cross-compilation is not an option, the codeMUST be run on the target hardware (RPi2B). We can run thought SSH. The 2 machines have ssh key exchanged so the password is not needed. Use SSH only run test commands never copy files, code, or compilation procedures.
- **PlayStation IP Address for tests**: 192.168.1.50

### Documentation Deliverables (Mandatory)

Every new spec, feature, or task MUST produce or update
documentation covering the following four areas:

1. **Installation** — Step-by-step instructions to install the
   feature/component on a fresh DietPi system. MUST include
   prerequisites, exact commands, and expected output.
2. **Configuration** — Description of all config file keys
   introduced or modified by the feature. MUST include:
   - An annotated config file example (TOML snippet)
   - Default values and valid ranges
   - How to verify the configuration is correct
3. **Logging** — What log entries the feature emits, at which
   log levels, and how to filter/search for them using the CLI
   `log` sub-command or `journalctl`.
4. **Troubleshooting** — A table or checklist of common failure
   modes, their symptoms, likely causes, and resolution steps.

A feature is NOT considered complete until all four documentation
sections are present and reviewed.

## Project References

The following open-source projects MUST be referenced in project
documentation (README, spec, plan, and relevant code-level comments)
as primary sources for GT7 telemetry protocol knowledge:

- **Bornhall/gt7telemetry** —
  <https://github.com/Bornhall/gt7telemetry>
  Python script for accessing GT7 telemetry data via UDP. Provides
  the foundational Salsa20 decryption logic, packet structure
  parsing, and heartbeat mechanism. Originally derived from
  [lmirel/mfc](https://github.com/lmirel/mfc/blob/master/clients/gt7racedata.py)
  and the
  [GTPlanet motion-rig thread](https://www.gtplanet.net/forum/threads/gt7-is-compatible-with-motion-rig.410728).
  Key file: `gt7telemetry.py` (Salsa20 key derivation, struct
  unpacking of ~300-byte packets).

- **snipem/gt7dashboard** —
  <https://github.com/snipem/gt7dashboard>
  Full-featured GT7 race telemetry dashboard (Bokeh-based). Forked
  from Bornhall/gt7telemetry with extensive additions: lap
  recording, speed/distance graphs, fuel maps, brake-point
  detection, Docker deployment. Useful as a reference for: packet
  handling architecture, test data samples (`test_data/`), and
  real-world GT7 integration patterns.

Documentation files MUST include these references in a "References"
or "Acknowledgments" section. Code modules that implement telemetry
parsing or Salsa20 decryption MUST cite the originating repository
in their module docstring.

## Governance

- This constitution supersedes all other development practices for
  the Pidalmetry project.
- Amendments require: (1) a written proposal, (2) updated
  constitution with version bump, (3) propagation to all dependent
  templates.
- Versioning follows SemVer: MAJOR for principle removal/redefinition,
  MINOR for new principles or material expansions, PATCH for
  clarifications and typo fixes.
- Every code review MUST verify compliance with the applicable
  principles above.
- Complexity beyond what is documented here MUST be justified in the
  plan's Complexity Tracking table.
- Runtime development guidance lives in `AGENTS.md` at the project
  root.

**Version**: 1.2.1 | **Ratified**: 2026-04-26 | **Last Amended**: 2026-04-26
