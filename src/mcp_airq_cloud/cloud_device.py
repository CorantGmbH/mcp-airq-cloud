"""Thin wrapper around the air-Q Cloud REST API for a single device."""

import aiohttp

BASE_URL = "https://air-q-cloud.de/open_api/v3"


class CloudDevice:
    """Async client for one air-Q device via the Cloud API."""

    def __init__(
        self, device_id: str, api_key: str, session: aiohttp.ClientSession
    ) -> None:
        self._device_id = device_id
        self._api_key = api_key
        self._session = session

    async def get_latest_data(self) -> dict:
        """Get the most recent sensor data for this device."""
        url = f"{BASE_URL}/devices/{self._device_id}/sensordata/latest"
        async with self._session.get(
            url, headers={"Api-Key": self._api_key}
        ) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def get_data_timerange(self, from_ms: int, to_ms: int) -> list[dict]:
        """Get sensor data within a time range (millisecond timestamps)."""
        url = f"{BASE_URL}/devices/{self._device_id}/sensordata/timerange"
        params = {"f": str(from_ms), "t": str(to_ms)}
        async with self._session.get(
            url, headers={"Api-Key": self._api_key}, params=params
        ) as resp:
            resp.raise_for_status()
            return await resp.json()
