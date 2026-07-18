from __future__ import annotations

import csv
import json
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import Any


def _num(value: float | None) -> float | None:
    return None if value is None else float(value)


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _iso_week(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    iso = dt.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def activity_row(a: dict[str, Any]) -> dict[str, Any]:
    local = _parse_dt(a.get("startTimeLocal"))
    distance_m = _num(a.get("distance"))
    duration_s = _num(a.get("duration"))
    activity_type = (a.get("activityType") or {}).get("typeKey")
    return {
        "id": a.get("activityId"),
        "name": a.get("activityName"),
        "activity_type": activity_type,
        "date_local": local.isoformat() if local else a.get("startTimeLocal"),
        "day_of_week": local.strftime("%A") if local else None,
        "iso_week": _iso_week(local),
        "distance_km": (distance_m / 1000) if distance_m else None,
        "duration_seconds": duration_s,
        "moving_duration_seconds": _num(a.get("movingDuration")),
        "elevation_gain_m": _num(a.get("elevationGain")),
        "average_speed_mps": _num(a.get("averageSpeed")),
        "max_speed_mps": _num(a.get("maxSpeed")),
        "calories": _num(a.get("calories")),
        "average_hr": _num(a.get("averageHR")),
        "max_hr": _num(a.get("maxHR")),
        "average_run_cadence": _num(a.get("averageRunningCadenceInStepsPerMinute")),
        "average_power": _num(a.get("avgPower")),
        "norm_power": _num(a.get("normPower")),
        "max_power": _num(a.get("maxPower")),
        "aerobic_te": _num(a.get("aerobicTrainingEffect")),
        "anaerobic_te": _num(a.get("anaerobicTrainingEffect")),
        "training_load": _num(a.get("activityTrainingLoad")),
        "training_effect_label": a.get("trainingEffectLabel"),
        "vo2max": _num(a.get("vO2MaxValue")),
        "moderate_intensity_min": _num(a.get("moderateIntensityMinutes")),
        "vigorous_intensity_min": _num(a.get("vigorousIntensityMinutes")),
        "avg_ground_contact_ms": _num(a.get("avgGroundContactTime")),
        "avg_vertical_oscillation_cm": _num(a.get("avgVerticalOscillation")),
        "avg_vertical_ratio": _num(a.get("avgVerticalRatio")),
        "avg_stride_length_cm": _num(a.get("avgStrideLength")),
        "max_run_cadence": _num(a.get("maxRunningCadenceInStepsPerMinute")),
        "avg_respiration_rate": _num(a.get("avgRespirationRate")),
        "steps": _num(a.get("steps")),
        "location": a.get("locationName"),
    }


def to_rows(activities: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build rows sorted newest first (ISO date strings sort chronologically)."""
    rows = [activity_row(a) for a in activities]
    rows.sort(key=lambda r: r["date_local"] or "", reverse=True)
    return rows


def hr_zone_seconds(zones: Any) -> dict[str, Any]:
    """Flatten get_activity_hr_in_timezones() into hr_zone1..5_seconds columns."""
    by_zone: dict[int, float | None] = {}
    for z in zones or []:
        number = z.get("zoneNumber")
        if number is not None:
            by_zone[int(number)] = _num(z.get("secsInZone"))
    return {f"hr_zone{n}_seconds": by_zone.get(n) for n in range(1, 6)}


def write_csv(rows: list[dict[str, Any]], path: str | Path) -> None:
    if not rows:
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_json(data: dict[str, Any], path: str | Path) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)


def _sleep_summary(sleep: Any) -> dict[str, Any]:
    dto = (sleep or {}).get("dailySleepDTO") or {}
    overall = (dto.get("sleepScores") or {}).get("overall") or {}
    src = sleep or {}
    return {
        "sleep_seconds": dto.get("sleepTimeSeconds"),
        "deep_seconds": dto.get("deepSleepSeconds"),
        "light_seconds": dto.get("lightSleepSeconds"),
        "rem_seconds": dto.get("remSleepSeconds"),
        "awake_seconds": dto.get("awakeSleepSeconds"),
        "sleep_score": overall.get("value"),
        "avg_respiration": dto.get("averageRespirationValue"),
        "avg_sleep_stress": dto.get("avgSleepStress"),
        "avg_hr": dto.get("avgHeartRate"),
        "resting_hr": src.get("restingHeartRate"),
        "avg_overnight_hrv": src.get("avgOvernightHrv"),
        "hrv_status": src.get("hrvStatus"),
        "body_battery_change": src.get("bodyBatteryChange"),
    }


def _activity_summary(summary: Any) -> dict[str, Any]:
    s = summary or {}
    return {
        "steps": s.get("totalSteps"),
        "total_kcal": s.get("totalKilocalories"),
        "active_kcal": s.get("activeKilocalories"),
        "distance_m": s.get("totalDistanceMeters"),
        "moderate_intensity_min": s.get("moderateIntensityMinutes"),
        "vigorous_intensity_min": s.get("vigorousIntensityMinutes"),
        "floors_ascended_m": s.get("floorsAscendedInMeters"),
        "highly_active_seconds": s.get("highlyActiveSeconds"),
        "active_seconds": s.get("activeSeconds"),
        "sedentary_seconds": s.get("sedentarySeconds"),
        "sleeping_seconds": s.get("sleepingSeconds"),
    }


def wellness_day(sleep: Any, stress: Any, hrv: Any, readiness: Any, summary: Any) -> dict[str, Any]:
    stress = stress or {}
    readiness_row = readiness[0] if isinstance(readiness, list) and readiness else (readiness or None)
    return {
        "sleep": _sleep_summary(sleep),
        "stress": {"max": stress.get("maxStressLevel"), "avg": stress.get("avgStressLevel")},
        "hrv": (hrv or {}).get("hrvSummary"),
        "training_readiness": readiness_row,
        "activity": _activity_summary(summary),
    }
