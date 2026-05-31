import threading
from typing import Iterator

import requests

from app.core.schema import Camera

_HEADERS = {
    "Referer": "https://weathercams.faa.gov/",
    "Origin": "https://weathercams.faa.gov",
    "Accept": "application/json",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
}


def run(
    session: requests.Session,
    stop_event: threading.Event | None = None,
) -> Iterator[tuple[Camera, str]]:
    """Yields (camera, log_message) tuples."""
    stop_event = stop_event or threading.Event()

    try:
        resp = session.get(
            "https://weathercams.faa.gov/api/sites",
            headers=_HEADERS,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        yield None, f"[!] Failed to fetch FAA data: {e}"  # type: ignore[misc]
        return

    sites = data.get("payload", [])
    yield None, f"[+] Fetched {len(sites)} FAA sites"  # type: ignore[misc]

    for site in sites:
        if stop_event.is_set():
            break

        site_name = site.get("siteName", "")
        state     = site.get("state", "")
        country   = site.get("country", "")
        site_lat  = site.get("latitude")
        site_lon  = site.get("longitude")
        elevation = site.get("elevation")
        timezone  = site.get("timeZone", "")
        icao      = site.get("icao", "")
        site_id   = site.get("siteId")

        for cam in site.get("cameras", []):
            cam_id = str(cam.get("cameraId", ""))
            cam_name = cam.get("cameraName", "")
            direction = cam.get("cameraDirection", "")

            camera = Camera(
                source="FAA WeatherCams",
                camera_id=cam_id,
                url=f"https://weathercams.faa.gov/cameras/cameraSite/{site_id}/details/camera/{cam_id}/loop-full",
                camera_name=f"{cam_name} ({direction})" if direction else cam_name,
                camera_type="weather",
                category="aviation",
                latitude=cam.get("latitude") or site_lat,
                longitude=cam.get("longitude") or site_lon,
                country=country,
                country_code="US" if country in ("United States", "US", "") else country[:2].upper(),
                state=state,
                city="",
                region="",
                extra={
                    "icao": icao,
                    "elevation_ft": elevation,
                    "timezone": timezone,
                    "in_maintenance": cam.get("cameraInMaintenance", False),
                    "out_of_order": cam.get("cameraOutOfOrder", False),
                    "last_success": cam.get("cameraLastSuccess", ""),
                    "latest_images_url": f"https://weathercams.faa.gov/api/cameras/{cam_id}/images",
                    "camera_direction": direction,
                    "site_name": site_name,
                },
            )

            msg = (
                f"[+] {site_name} | {cam_name} ({direction})"
                f" | {state}, {country}"
                f" | {camera['latitude']}, {camera['longitude']}"
            )
            yield camera, msg
