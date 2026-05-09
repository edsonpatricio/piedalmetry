# Piedalmetry — Codebase Guide

GT7 brake-pressure-to-motor rumble feedback for Raspberry Pi 2B running DietPi.
Reads UDP telemetry from Gran Turismo 7, maps brake pressure to PWM motor output
via an L298N driver, and runs as a systemd service.

## Tech Stack

- **Python 3.11+** — `uv` for dependency management and venv
- **Click** — CLI (`piedalmetry` entry point → `src/piedalmetry/cli.py`)
- **gpiozero** + **lgpio** — GPIO on DietPi (lgpio is the backend)
- **pycryptodome** — Salsa20 decryption of GT7 UDP packets (needs C extensions, ARMv7-compatible)
- **Hatchling** — build backend
- **pytest / ruff / mypy** — test, lint, type-check

## Project Structure

```
src/piedalmetry/
  cli.py              # Click command group — all user-facing subcommands
  config.py           # Config loading (TOML) and write_back_ip
  logging.py          # Structured logging setup
  motor/              # PWM motor controller
  led/                # LED blink states (connecting, connected, error)
  foot_sensor/        # Foot sensor input
  shutdown_button/    # GPIO shutdown button handler
  telemetry/
    discovery.py      # UDP broadcast to find PlayStation IP
    listener.py       # GT7 telemetry listener (re-discovery via `piedalmetry discovery`)
    parser.py         # Salsa20 decrypt + packet parse
  service/
    runner.py         # Main service loop; chokes PermissionError on write_back_ip
    installer.py      # systemd install/uninstall; chowns config to service user
    updater.py        # GitHub tar.gz update; detects venv from ExecStart in service file

tests/
  unit/               # Fast, no hardware
  integration/        # Requires config file / file system
  mock/               # Fake GPIO and GT7 UDP server
```

## Common Commands

```bash
uv sync                          # Install / sync dependencies
uv run pytest                    # Run all tests
uv run pytest tests/unit/        # Unit tests only
uv run ruff check src/ tests/    # Lint
uv run ruff format src/ tests/   # Format
uv run mypy src/                 # Type-check
uv run piedalmetry --help        # CLI help
uv run piedalmetry run --mock    # Run without hardware
```

## Key Architectural Decisions

- **Installer bakes the venv Python path into `ExecStart`** — avoids `sudo uv run` which
  fails on CIFS mounts. Install with:
  ```bash
  sudo $(uv run which python) -m piedalmetry install --config /etc/piedalmetry/config.toml
  ```
- **Config is chowned to the service user at install time** — lets `write_back_ip` persist
  the discovered PS IP at runtime without requiring root.
- **Updater detects venv from the systemd service file** (ExecStart line), not from
  `sys.executable` (which becomes `/usr/bin/python3` under sudo).
- **CIFS/Samba installs** must set `UV_PROJECT_ENVIRONMENT` to a local path so the venv
  symlinks don't land on the network share.


## Release Process

1. Edit `pyproject.toml` → bump `version`
2. `git add pyproject.toml && git commit -m "chore: bump version to X.Y.Z"`
3. `git tag vX.Y.Z && git push origin main --tags`
4. `gh release create vX.Y.Z --title "vX.Y.Z" --notes "..."`

No CI/CD. Releases are distributed as GitHub tar.gz archives; `piedalmetry update`
downloads from `github.com/edsonpatricio/piedalmetry/archive/refs/tags/{tag}.tar.gz`.

## Working Instructions

Follow these rules on every task:

1. **Branch first** — before executing any plan, create a feature branch:
   `git checkout -b <type>/<short-description>` (e.g. `feat/led-blink`, `fix/updater-venv`).
   Never implement directly on `main`.

2. **Keep docs in sync** — any code change that affects user-facing behaviour must be
   reflected in the relevant doc (`docs/installation.md`, `docs/configuration.md`,
   `docs/troubleshooting.md`, `config.example.toml`). Update them in the same PR.

3. **Keep log messages accurate** — if you change what a function does, update its
   `logger.info / warning / error` messages to match. Stale log strings are misleading
   in production.

4. **Keep config comments accurate** — `config.example.toml` is the canonical reference
   for every config key. When a key is added, removed, renamed, or its semantics change,
   update the comment in that file immediately.

5. **Remove dead code** — before closing a task, scan for unreachable branches,
   unused imports, and orphaned functions introduced or exposed by the change. Delete
   them; don't leave TODO comments.

## Commit Style

Conventional commits: `fix:`, `feat:`, `docs:`, `chore:`, `refactor:`, `test:`.
No `Co-Authored-By` lines.

## Docs

- `docs/installation.md` — full install guide (the main user-facing doc)
- `docs/configuration.md` — all config options
- `docs/troubleshooting.md` — diagnostics
- `docs/hardware/wiring.md` — GPIO wiring diagram
- `config.example.toml` — annotated config template
