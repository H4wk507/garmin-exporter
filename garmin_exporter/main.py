#!/usr/bin/env python3

from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from garmin_exporter.client import GarminClient
from garmin_exporter.export import hr_zone_seconds, to_rows, wellness_day, write_csv, write_json
from garmin_exporter.keyring import delete_session


def _wellness(client: GarminClient, days_back: int) -> dict[str, Any]:
    today = date.today()
    days = [(today - timedelta(days=n)).isoformat() for n in range(days_back + 1)]
    return {
        "vo2max": client.get_vo2max(today.isoformat()),
        "training_status": client.get_training_status(today.isoformat()),
        "by_day": {
            d: wellness_day(
                client.get_sleep(d),
                client.get_stress(d),
                client.get_hrv(d),
                client.get_training_readiness(d),
                client.get_user_summary(d),
            )
            for d in days
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export Garmin Connect data to CSV/JSON.")
    parser.add_argument("-o", "--output", default="activities.csv")
    parser.add_argument("--days-back", type=int, help="Only the last N days. Default: all activities.")
    parser.add_argument("--activity-type", help="Filter by Garmin type key, e.g. running, cycling. Default: all.")
    parser.add_argument("--wellness", action="store_true", help="Also write <output>.wellness.json.")
    parser.add_argument(
        "--hr-zones",
        action="store_true",
        help="Add per-activity HR time-in-zones columns (one extra API call each).",
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

    if args.wellness:
        wellness_path = out.with_name(f"{out.stem}.wellness.json")
        try:
            write_json(_wellness(client, args.days_back or 30), wellness_path)
            print(f"Wrote wellness data to {wellness_path}")
        except Exception as exc:  # noqa: BLE001
            print(f"Skipped wellness ({exc}).", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
