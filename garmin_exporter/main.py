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
    wellness_day,
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


def _wellness(client: GarminClient, days: int) -> dict[str, Any]:
    today = date.today()
    dates = [(today - timedelta(days=n)).isoformat() for n in range(days + 1)]
    by_day: dict[str, Any] = {}
    for i, d in enumerate(dates, 1):
        day = _safe(
            f"wellness {d}",
            lambda d=d: wellness_day(
                client.get_sleep(d),
                client.get_stress(d),
                client.get_hrv(d),
                client.get_user_summary(d),
            ),
        )
        if day is not None:
            by_day[d] = day
        if i % 30 == 0 or i == len(dates):
            print(f"  wellness {i}/{len(dates)} days...")
    return {
        "profile": _safe("profile", lambda: profile_summary(client.get_user_profile())),
        "vo2max": _safe("vo2max", lambda: client.get_vo2max(today.isoformat())),
        "training_status": _safe("training_status", lambda: client.get_training_status(today.isoformat())),
        "by_day": by_day,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export Garmin Connect data to CSV/JSON.")
    parser.add_argument("-o", "--output", default="activities.csv")
    parser.add_argument("--days-back", type=int, help="Only the last N days. Default: all activities.")
    parser.add_argument("--activity-type", help="Filter by Garmin type key, e.g. running, cycling. Default: all.")
    parser.add_argument(
        "--wellness",
        action="store_true",
        help="Also write <output>.wellness.json (sleep, HRV, profile, thresholds, ...).",
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
        wellness_path = out.with_name(f"{out.stem}.wellness.json")
        try:
            write_json(_wellness(client, args.wellness_days), wellness_path)
            print(f"Wrote wellness data to {wellness_path}")
        except Exception as exc:  # noqa: BLE001
            print(f"Skipped wellness ({exc}).", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
