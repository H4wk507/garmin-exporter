#!/usr/bin/env python3

from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from garminconnect import GarminConnectTooManyRequestsError

from garmin_exporter.cache import Cache
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
    except GarminConnectTooManyRequestsError:
        raise
    except Exception as exc:  # noqa: BLE001
        print(f"Skipped {label} ({exc}).", file=sys.stderr)
        return None


def _wellness_rows(client: GarminClient, days: int) -> tuple[list[dict[str, Any]], bool]:
    today = date.today()
    dates = [(today - timedelta(days=n)).isoformat() for n in range(days + 1)]
    rows: list[dict[str, Any]] = []
    for i, d in enumerate(dates, 1):
        try:
            row = wellness_row(
                d,
                _safe(f"sleep {d}", lambda d=d: client.get_sleep(d)),
                _safe(f"stress {d}", lambda d=d: client.get_stress(d)),
                _safe(f"hrv {d}", lambda d=d: client.get_hrv(d)),
                _safe(f"summary {d}", lambda d=d: client.get_user_summary(d)),
                _safe(f"training status {d}", lambda d=d: client.get_training_status(d)),
            )
        except GarminConnectTooManyRequestsError:
            print(
                f"Rate limited by Garmin after {len(rows)}/{len(dates)} days. "
                "Progress is cached - rerun the same command to resume.",
                file=sys.stderr,
            )
            return rows, True
        rows.append(row)
        if i % 30 == 0 or i == len(dates):
            print(f"  wellness {i}/{len(dates)} days...")
    return rows, False


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
    parser.add_argument("--no-cache", action="store_true", help="Ignore the on-disk cache and refetch everything.")
    parser.add_argument("--cache-dir", help="Override the cache location (default: OS cache dir).")
    args = parser.parse_args(argv)

    if args.reset_login:
        delete_session()
        print("Cleared stored Garmin session.")

    cache = Cache(root=Path(args.cache_dir) if args.cache_dir else None, enabled=not args.no_cache)
    client = GarminClient(cache=cache)
    rate_limited = False

    print("Fetching activities...")
    activities = client.get_activities(days_back=args.days_back, activity_type=args.activity_type)
    rows = to_rows(activities)

    if args.hr_zones:
        print(f"Fetching HR zones for {len(rows)} activities...")
        for row in rows:
            try:
                row.update(hr_zone_seconds(client.get_hr_zones(row["id"])))
            except GarminConnectTooManyRequestsError:
                print("Rate limited by Garmin during HR zones. Progress is cached - rerun to resume.", file=sys.stderr)
                rate_limited = True
                break
            except Exception as exc:  # noqa: BLE001
                row.update(hr_zone_seconds(None))
                print(f"Skipped HR zones {row['id']} ({exc}).", file=sys.stderr)

    if rows:
        write_csv(rows, args.output)
        print(f"Wrote {len(rows)} activities to {args.output}")
    else:
        print("No activities found.")

    out = Path(args.output)

    if args.splits and not rate_limited:
        runs = [row for row in rows if row["activity_type"] == "running"]
        print(f"Fetching splits for {len(runs)} runs...")
        splits: list[dict[str, Any]] = []
        for row in runs:
            try:
                splits.extend(split_rows(row["id"], client.get_activity_splits(row["id"])))
            except GarminConnectTooManyRequestsError:
                print("Rate limited by Garmin during splits. Progress is cached - rerun to resume.", file=sys.stderr)
                rate_limited = True
                break
            except Exception as exc:  # noqa: BLE001
                print(f"Skipped splits {row['id']} ({exc}).", file=sys.stderr)
        if splits:
            splits_path = out.with_name(f"{out.stem}.splits.csv")
            write_csv(splits, splits_path)
            print(f"Wrote {len(splits)} splits to {splits_path}")
        else:
            print("No splits found.")

    if args.wellness and not rate_limited:
        print(f"Fetching wellness for {args.wellness_days} days...")
        try:
            wellness, rate_limited = _wellness_rows(client, args.wellness_days)
            wellness_path = out.with_name(f"{out.stem}.wellness.csv")
            write_csv(wellness, wellness_path)
            print(f"Wrote {len(wellness)} wellness days to {wellness_path}")

            if not rate_limited:
                profile_path = out.with_name(f"{out.stem}.profile.json")
                write_json(_profile(client), profile_path)
                print(f"Wrote profile to {profile_path}")
        except Exception as exc:  # noqa: BLE001
            print(f"Skipped wellness ({exc}).", file=sys.stderr)

    if cache.enabled and (cache.hits or cache.misses):
        print(f"Cache: {cache.hits} from cache, {cache.misses} fetched from Garmin.")

    # Non-zero exit tells scripts the export is incomplete and worth rerunning.
    return 1 if rate_limited else 0


if __name__ == "__main__":
    raise SystemExit(main())
