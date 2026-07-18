# garmin-exporter

Export your Garmin Connect activities (CSV) and wellness metrics - sleep, HRV,
VO2max, Training Status, Training Readiness (JSON).

## Quickstart

1. Install uv:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

2. Install dependencies:

```bash
uv sync
```

3. Run:

```bash
uv run garmin-exporter --wellness
```

On the first run it asks for your Garmin email, password, and MFA code (if
enabled), then stores the **session token** in your OS keyring - the password
is never saved. Later runs reuse the session.

## Options

| Flag                | Description                                      |
| ------------------- | ------------------------------------------------ |
| `-o, --output`      | Output CSV path (default: `activities.csv`)      |
| `--days-back N`     | Only the last N days (default: all activities)   |
| `--activity-type T` | Garmin type key, e.g. `running` (default: all)   |
| `--wellness`        | Also write `<output>.wellness.json`              |
| `--hr-zones`        | Add per-activity HR time-in-zones (+1 call each) |
| `--reset-login`     | Forget the stored session and log in again       |

## Development

The project uses Makefile for typical tasks:

- `make lint` - Ruff check + mypy --strict
- `make format` - Ruff format
- `make clean` - Remove cache files
