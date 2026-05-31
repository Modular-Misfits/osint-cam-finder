import threading
from typing import Iterator

import requests

from app.core.schema import Camera

# Only feeds that have been manually verified to return JSON without an API key.
# Each entry: state_code → {name, url, parser}
# "parser" is a function name string resolved below.

_FEEDS: dict[str, dict] = {
    "NY": {
        "name": "New York",
        "url": "https://511ny.org/api/getcameras?key=demo&format=json",
        "parser": "ny511",
    },
}


def _parse_ny511(data: list) -> list[Camera]:
    cameras = []
    for item in data:
        if item.get("Disabled"):
            continue
        cam_id   = str(item.get("ID", ""))
        name     = item.get("Name", "")
        lat      = item.get("Latitude")
        lon      = item.get("Longitude")
        roadway  = item.get("RoadwayName", "")
        # Prefer live stream URL; fall back to map page URL
        url      = item.get("VideoUrl") or item.get("Url") or ""
        cameras.append(Camera(
            source="US DOT Traffic",
            camera_id=f"NY-{cam_id}",
            url=url or None,
            camera_name=name,
            camera_type="traffic",
            category="traffic",
            latitude=float(lat) if lat else None,
            longitude=float(lon) if lon else None,
            country="United States",
            country_code="US",
            state="NY",
            city=roadway,   # best available location label from this API
            region=name,
            extra={"direction": item.get("DirectionOfTravel", "")},
        ))
    return cameras


_PARSERS = {
    "ny511": _parse_ny511,
}


def run(
    session: requests.Session,
    state_code: str = "",
    stop_event: threading.Event | None = None,
) -> Iterator[tuple[Camera, str]]:
    stop_event = stop_event or threading.Event()

    feeds_to_run = (
        {state_code: _FEEDS[state_code]}
        if state_code and state_code in _FEEDS
        else _FEEDS
    )

    if not feeds_to_run:
        yield None, f"[!] No open feed available for state: {state_code}"  # type: ignore[misc]
        return

    for sc, cfg in feeds_to_run.items():
        if stop_event.is_set():
            break

        state_name = cfg["name"]
        yield None, f"[*] Fetching {state_name} DOT cameras..."  # type: ignore[misc]

        try:
            resp = session.get(cfg["url"], timeout=30)
            resp.raise_for_status()
            data = resp.json()
            parser = _PARSERS[cfg["parser"]]
            cams = parser(data if isinstance(data, list) else [])
            yield None, f"[*] Parsed {len(cams)} cameras from {state_name}"  # type: ignore[misc]
            for cam in cams:
                if stop_event.is_set():
                    break
                yield cam, f"[+] {sc} | {cam['camera_name']} | {cam['latitude']}, {cam['longitude']}"
        except Exception as e:
            yield None, f"[!] {sc} feed failed: {e}"  # type: ignore[misc]
