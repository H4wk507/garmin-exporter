#!/usr/bin/env python3

from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from garmin_exporter.client import GarminClient
from garmin_exporter.export import (
    hr_zone_seconds,
    profile_summary,
    split_rows,
    to_rows,
    training_snapshot,
    wellness_row,
    write_csv,
    write_json,
)
from garmin_exporter.keyring import delete_session


def _safe(label: str, fn: Any) -> Any:
    try:
        return fn()
    except Exception as exc:  # noqa: BLE001
        print(f"Skipped {label} ({exc}).", file=sys.stderr)
        return None


def _wellness_rows(client: GarminClient, days: int) -> list[dict[str, Any]]:
    today = date.today()
    dates = [(today - timedelta(days=n)).isoformat() for n in range(days + 1)]
    rows: list[dict[str, Any]] = []
    for i, d in enumerate(dates, 1):
        rows.append(
            wellness_row(
                d,
                _safe(f"sleep {d}", lambda d=d: client.get_sleep(d)),
                _safe(f"stress {d}", lambda d=d: client.get_stress(d)),
                _safe(f"hrv {d}", lambda d=d: client.get_hrv(d)),
                _safe(f"summary {d}", lambda d=d: client.get_user_summary(d)),
                _safe(f"training status {d}", lambda d=d: client.get_training_status(d)),
            )
        )
        if i % 30 == 0 or i == len(dates):
            print(f"  wellness {i}/{len(dates)} days...")
    return rows


def _profile(client: GarminClient) -> dict[str, Any]:
    today = date.today().isoformat()
    status = _safe("training status", lambda: client.get_training_status(today))
    return {
        "profile": _safe("profile", lambda: profile_summary(client.get_user_profile())),
        "training_snapshot": training_snapshot(status),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export Garmin Connect data to CSV/JSON.")
    parser.add_argument("-o", "--output", default="activities.csv")
    parser.add_argument("--days-back", type=int, help="Only the last N days. Default: all activities.")
    parser.add_argument("--activity-type", help="Filter by Garmin type key, e.g. running, cycling. Default: all.")
    parser.add_argument(
        "--wellness",
        action="store_true",
        help="Also write <output>.wellness.csv (daily sleep, HRV, Training Status, ...) "
        "and <output>.profile.json (profile, thresholds, load balance).",
    )
    parser.add_argument(
        "--wellness-days",
        type=int,
        default=365,
        help="Days of wellness history to fetch with --wellness (default: 365).",
    )
    parser.add_argument(
        "--hr-zones",
        action="store_true",
        help="Add per-activity HR time-in-zones columns (one extra API call each).",
    )
    parser.add_argument(
        "--splits",
        action="store_true",
        help="Write per-run km splits to <output>.splits.csv (one extra API call per run).",
    )
    parser.add_argument("--reset-login", action="store_true", help="Forget the stored session and log in again.")
    args = parser.parse_args(argv)

    if args.reset_login:
        delete_session()
        print("Cleared stored Garmin session.")

    client = GarminClient()

    print("Fetching activities...")
    activities = client.get_activities(days_back=args.days_back, activity_type=args.activity_type)
    rows = to_rows(activities)

    if args.hr_zones:
        print(f"Fetching HR zones for {len(rows)} activities...")
        for row in rows:
            try:
                row.update(hr_zone_seconds(client.get_hr_zones(row["id"])))
            except Exception as exc:  # noqa: BLE001
                row.update(hr_zone_seconds(None))
                print(f"Skipped HR zones {row['id']} ({exc}).", file=sys.stderr)

    if rows:
        write_csv(rows, args.output)
        print(f"Wrote {len(rows)} activities to {args.output}")
    else:
        print("No activities found.")

    out = Path(args.output)

    if args.splits:
        runs = [row for row in rows if row["activity_type"] == "running"]
        print(f"Fetching splits for {len(runs)} runs...")
        splits: list[dict[str, Any]] = []
        for row in runs:
            try:
                splits.extend(split_rows(row["id"], client.get_activity_splits(row["id"])))
            except Exception as exc:  # noqa: BLE001
                print(f"Skipped splits {row['id']} ({exc}).", file=sys.stderr)
        if splits:
            splits_path = out.with_name(f"{out.stem}.splits.csv")
            write_csv(splits, splits_path)
            print(f"Wrote {len(splits)} splits to {splits_path}")
        else:
            print("No splits found.")

    if args.wellness:
        print(f"Fetching wellness for {args.wellness_days} days...")
        try:
            wellness_path = out.with_name(f"{out.stem}.wellness.csv")
            wellness = _wellness_rows(client, args.wellness_days)
            write_csv(wellness, wellness_path)
            print(f"Wrote {len(wellness)} wellness days to {wellness_path}")

            profile_path = out.with_name(f"{out.stem}.profile.json")
            write_json(_profile(client), profile_path)
            print(f"Wrote profile to {profile_path}")
        except Exception as exc:  # noqa: BLE001
            print(f"Skipped wellness ({exc}).", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
