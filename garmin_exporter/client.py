from __future__ import annotations

from datetime import date, timedelta
from getpass import getpass
from typing import Any

from garminconnect import Garmin

from garmin_exporter.keyring import load_session, save_session


class GarminClient:
    def __init__(self) -> None:
        self._api = Garmin()
        self._authenticate()

    def get_activities(
        self,
        days_back: int | None = None,
        activity_type: str | None = None,
    ) -> list[dict[str, Any]]:
        if days_back is not None:
            start = (date.today() - timedelta(days=days_back)).isoformat()
            end = date.today().isoformat()
            found: list[dict[str, Any]] = self._api.get_activities_by_date(start, end, activity_type)
            return found

        found = []
        offset, batch = 0, 200
        while True:
            chunk: list[dict[str, Any]] = self._api.get_activities(offset, batch)
            if not chunk:
                break
            found.extend(chunk)
            if len(chunk) < batch:
                break
            offset += batch
        if activity_type:
            found = [a for a in found if (a.get("activityType") or {}).get("typeKey") == activity_type]
        return found

    def get_sleep(self, day: str) -> Any:
        return self._api.get_sleep_data(day)

    def get_hrv(self, day: str) -> Any:
        return self._api.get_hrv_data(day)

    def get_stress(self, day: str) -> Any:
        return self._api.get_stress_data(day)

    def get_vo2max(self, day: str) -> Any:
        return self._api.get_max_metrics(day)

    def get_training_status(self, day: str) -> Any:
        return self._api.get_training_status(day)

    def get_training_readiness(self, day: str) -> Any:
        return self._api.get_training_readiness(day)

    def get_user_summary(self, day: str) -> Any:
        return self._api.get_user_summary(day)

    def get_hr_zones(self, activity_id: int) -> Any:
        """Per-activity HR time-in-zones (one extra API call per activity)."""
        return self._api.get_activity_hr_in_timezones(activity_id)

    def _authenticate(self) -> None:
        token = load_session()
        if token:
            try:
                self._api.login(token)
                return
            except Exception:  # noqa: BLE001
                pass
        self._login()

    def _login(self) -> None:
        print("Log in to Garmin Connect.")
        email = input("Email: ").strip()
        password = getpass("Password: ")
        self._api = Garmin(email, password, prompt_mfa=lambda: getpass("MFA code: ").strip())
        self._api.client.skip_strategies = {"mobile+cffi", "mobile+requests"}
        self._api.login()
        save_session(self._api.client.dumps())
