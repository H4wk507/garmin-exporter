from __future__ import annotations

import csv
import json
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import Any


def _num(value: float | None) -> float | None:
    return None if value is None else round(float(value), 3)


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


def _mmss(seconds: float | None) -> str | None:
    if not seconds or seconds <= 0:
        return None
    m, s = divmod(int(round(seconds)), 60)
    return f"{m}:{s:02d}"


def _pace_per_km(distance_m: float | None, duration_s: float | None) -> str | None:
    if not distance_m or distance_m <= 0 or not duration_s:
        return None
    return _mmss(duration_s / (distance_m / 1000))


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


def _age(birth_date: str | None) -> int | None:
    born = _parse_dt(birth_date)
    if born is None:
        return None
    today = datetime.now()
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))


def profile_summary(profile: Any) -> dict[str, Any]:
    ud = (profile or {}).get("userData") or {}
    weight_g = _num(ud.get("weight"))
    speed_mps = _num(ud.get("lactateThresholdSpeed"))
    suspect = speed_mps is not None and speed_mps < 1.0
    return {
        "age": _age(ud.get("birthDate")),
        "birth_date": ud.get("birthDate"),
        "gender": ud.get("gender"),
        "weight_kg": round(weight_g / 1000, 3) if weight_g else None,
        "height_cm": _num(ud.get("height")),
        "vo2max_running": _num(ud.get("vo2MaxRunning")),
        "vo2max_cycling": _num(ud.get("vo2MaxCycling")),
        "lthr_bpm": ud.get("lactateThresholdHeartRate"),
        "threshold_pace_mps": None if suspect else speed_mps,
        "threshold_pace_per_km": None if suspect or not speed_mps else _mmss(1000 / speed_mps),
        "threshold_pace_suspect": suspect,
    }


def split_rows(activity_id: Any, splits: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for lap in (splits or {}).get("lapDTOs") or []:
        distance_m = _num(lap.get("distance"))
        duration_s = _num(lap.get("duration"))
        rows.append(
            {
                "activity_id": activity_id,
                "lap_index": lap.get("lapIndex"),
                "distance_km": (distance_m / 1000) if distance_m else None,
                "duration_seconds": duration_s,
                "pace_per_km": _pace_per_km(distance_m, duration_s),
                "avg_speed_mps": _num(lap.get("averageSpeed")),
                "max_speed_mps": _num(lap.get("maxSpeed")),
                "avg_hr": _num(lap.get("averageHR")),
                "max_hr": _num(lap.get("maxHR")),
                "avg_run_cadence": _num(lap.get("averageRunCadence")),
                "max_run_cadence": _num(lap.get("maxRunCadence")),
                "avg_power": _num(lap.get("averagePower")),
                "max_power": _num(lap.get("maxPower")),
                "elevation_gain_m": _num(lap.get("elevationGain")),
                "elevation_loss_m": _num(lap.get("elevationLoss")),
            }
        )
    return rows


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
    fieldnames = list(dict.fromkeys(key for row in rows for key in row))
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
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
        "sleep_deep_seconds": dto.get("deepSleepSeconds"),
        "sleep_light_seconds": dto.get("lightSleepSeconds"),
        "sleep_rem_seconds": dto.get("remSleepSeconds"),
        "sleep_awake_seconds": dto.get("awakeSleepSeconds"),
        "sleep_score": overall.get("value"),
        "sleep_avg_respiration": _num(dto.get("averageRespirationValue")),
        "sleep_avg_stress": _num(dto.get("avgSleepStress")),
        "sleep_avg_hr": _num(dto.get("avgHeartRate")),
        "resting_hr": src.get("restingHeartRate"),
        "body_battery_change": src.get("bodyBatteryChange"),
    }


def _hrv_summary(hrv: Any) -> dict[str, Any]:
    summary = (hrv or {}).get("hrvSummary") or {}
    baseline = summary.get("baseline") or {}
    return {
        "hrv_last_night_avg": summary.get("lastNightAvg"),
        "hrv_weekly_avg": summary.get("weeklyAvg"),
        "hrv_last_night_5min_high": summary.get("lastNight5MinHigh"),
        "hrv_status": summary.get("status"),
        "hrv_baseline_low_upper": baseline.get("lowUpper"),
        "hrv_baseline_balanced_low": baseline.get("balancedLow"),
        "hrv_baseline_balanced_upper": baseline.get("balancedUpper"),
    }


def _primary_device_entry(by_device: Any) -> dict[str, Any]:
    entries = list((by_device or {}).values())
    for entry in entries:
        if entry.get("primaryTrainingDevice"):
            return dict(entry)
    return dict(entries[0]) if entries else {}


def _status_label(phrase: str | None) -> str | None:
    if not phrase:
        return None
    head, _, tail = phrase.rpartition("_")
    return head if head and tail.isdigit() else phrase


def _training_day(training_status: Any) -> dict[str, Any]:
    latest = (training_status or {}).get("mostRecentTrainingStatus") or {}
    status = _primary_device_entry(latest.get("latestTrainingStatusData"))
    acute = status.get("acuteTrainingLoadDTO") or {}
    return {
        "training_status": _status_label(status.get("trainingStatusFeedbackPhrase")),
        "training_status_sport": status.get("sport"),
        "training_status_since": status.get("sinceDate"),
        "fitness_trend": status.get("fitnessTrend"),
        "acwr": _num(acute.get("dailyAcuteChronicWorkloadRatio")),
        "acwr_status": acute.get("acwrStatus"),
        "load_acute": _num(acute.get("dailyTrainingLoadAcute")),
        "load_chronic": _num(acute.get("dailyTrainingLoadChronic")),
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
        "floors_ascended_m": _num(s.get("floorsAscendedInMeters")),
        "highly_active_seconds": s.get("highlyActiveSeconds"),
        "active_seconds": s.get("activeSeconds"),
        "sedentary_seconds": s.get("sedentarySeconds"),
        "sleeping_seconds": s.get("sleepingSeconds"),
    }


def wellness_row(
    day: str,
    sleep: Any,
    stress: Any,
    hrv: Any,
    summary: Any,
    training_status: Any,
) -> dict[str, Any]:
    stress = stress or {}
    return {
        "date": day,
        **_sleep_summary(sleep),
        **_hrv_summary(hrv),
        "stress_avg": stress.get("avgStressLevel"),
        "stress_max": stress.get("maxStressLevel"),
        **_training_day(training_status),
        **_activity_summary(summary),
    }


def training_snapshot(training_status: Any) -> dict[str, Any]:
    load_balance = (training_status or {}).get("mostRecentTrainingLoadBalance") or {}
    balance = _primary_device_entry(load_balance.get("metricsTrainingLoadBalanceDTOMap"))
    devices = load_balance.get("recordedDevices") or []
    return {
        "as_of": balance.get("calendarDate"),
        "device": next((d.get("deviceName") for d in devices if d.get("deviceName")), None),
        "load_aerobic_low": _num(balance.get("monthlyLoadAerobicLow")),
        "load_aerobic_low_target": [
            balance.get("monthlyLoadAerobicLowTargetMin"),
            balance.get("monthlyLoadAerobicLowTargetMax"),
        ],
        "load_aerobic_high": _num(balance.get("monthlyLoadAerobicHigh")),
        "load_aerobic_high_target": [
            balance.get("monthlyLoadAerobicHighTargetMin"),
            balance.get("monthlyLoadAerobicHighTargetMax"),
        ],
        "load_anaerobic": _num(balance.get("monthlyLoadAnaerobic")),
        "load_anaerobic_target": [
            balance.get("monthlyLoadAnaerobicTargetMin"),
            balance.get("monthlyLoadAnaerobicTargetMax"),
        ],
        "balance_feedback": balance.get("trainingBalanceFeedbackPhrase"),
    }
