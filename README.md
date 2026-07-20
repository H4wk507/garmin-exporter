# garmin-exporter

Export your Garmin Connect activities

| File                      | Contents                                                                                |
| ------------------------- | --------------------------------------------------------------------------------------- |
| `activities.csv`          | One row per activity (distance, pace, HR, power, training load, VO2max, ...)            |
| `activities.splits.csv`   | One row per km split, with `--splits`                                                   |
| `activities.wellness.csv` | One row per day: sleep, HRV, stress, steps, Training Status and ACWR, with `--wellness` |
| `activities.profile.json` | Profile (age, sex, weight, height), thresholds (LTHR, pace) and monthly load balance    |

## Install

The package is published on [PyPI](https://pypi.org/project/garmin-exporter/),
so the recommended way to install it is with `uv` or `pip`:

```bash
# with uv (recommended)
uv tool install garmin-exporter

# or with pip
pip install garmin-exporter
```

## Quickstart

```bash
# Show help
garmin-exporter --help

# Export activities to CSV + a year of daily wellness metrics (sleep, HRV,
# Training Status, ...) to CSV, plus profile and thresholds to JSON
garmin-exporter --wellness

# Shorter wellness window (e.g. last 30 days)
garmin-exporter --wellness --wellness-days 30

# Also add per-activity HR time-in-zones
garmin-exporter --hr-zones

# Write per-run km splits to activities.splits.csv
garmin-exporter --splits
```

On the first run it asks for your Garmin email, password, and MFA code (if
enabled), then stores the **session token** in your OS keyring - the password
is never saved. Later runs reuse the session.

## Options

| Flag                | Description                                                  |
| ------------------- | ------------------------------------------------------------ |
| `-o, --output`      | Output CSV path (default: `activities.csv`)                  |
| `--days-back N`     | Only the last N days (default: all activities)               |
| `--activity-type T` | Garmin type key, e.g. `running` (default: all)               |
| `--wellness`        | Also write `<output>.wellness.csv` + `<output>.profile.json` |
| `--wellness-days N` | Days of wellness history with `--wellness` (default: 365)    |
| `--hr-zones`        | Add per-activity HR time-in-zones (+1 call each)             |
| `--splits`          | Write per-run km splits to `<output>.splits.csv`             |
| `--reset-login`     | Forget the stored session and log in again                   |

## Development

The project uses Makefile for typical tasks:

- `make lint` - Ruff check + mypy --strict
- `make format` - Ruff format
- `make clean` - Remove cache files
