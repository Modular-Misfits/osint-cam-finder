import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Iterator

import requests

from app.core.schema import Camera, infer_category

_API_BASE    = "https://api.windy.com/webcams/api/v3/webcams"
_LIMIT       = 50    # Windy v3 hard cap per request
_PAGE_WORKERS = 10   # concurrent page fetches

_WINDY_CAT_MAP = {
    "traffic":  "traffic",
    "weather":  "weather",
    "nature":   "nature",
    "city":     "tourist",
    "tourism":  "tourist",
    "mountain": "nature",
    "beach":    "tourist",
    "airport":  "aviation",
    "ski":      "nature",
}


def _map_category(windy_cats: list[str]) -> str:
    for cat in windy_cats:
        normalized = _WINDY_CAT_MAP.get(cat.lower(), "")
        if normalized:
            return normalized
    return infer_category(windy_cats)


def _build_url(offset: int, country_filter: str) -> str:
    # Build manually — requests percent-encodes commas, Windy v3 returns 400 on that.
    return (
        f"{_API_BASE}?limit={_LIMIT}&offset={offset}"
        f"&include=location,categories{country_filter}"
    )


def _fetch_page(session: requests.Session, offset: int, country_filter: str, api_key: str) -> list[dict]:
    url = _build_url(offset, country_filter)
    resp = session.get(url, headers={"x-windy-api-key": api_key}, timeout=30)
    resp.raise_for_status()
    return resp.json().get("webcams", [])


def _webcam_to_camera(wc: dict) -> Camera:
    cam_id  = str(wc.get("webcamId", ""))
    loc     = wc.get("location", {})
    cats    = [c.get("name", "") for c in wc.get("categories", [])]
    return Camera(
        source="Windy Webcams",
        camera_id=cam_id,
        url=f"https://www.windy.com/webcams/{cam_id}" if cam_id else "",
        camera_name=wc.get("title", ""),
        camera_type=", ".join(cats) if cats else "webcam",
        category=_map_category(cats),
        latitude=loc.get("latitude"),
        longitude=loc.get("longitude"),
        country=loc.get("country", ""),
        country_code=loc.get("countryCode", ""),
        state="",
        city=loc.get("city", ""),
        region=loc.get("region", ""),
        extra={"windy_status": wc.get("status", ""), "categories": cats},
    )


def run(
    session: requests.Session,
    stop_event: threading.Event | None = None,
    country_code: str = "",
) -> Iterator[tuple[Camera, str]]:
    """
    Yields (camera, log_message) tuples.
    Requires WINDY_API_KEY env var. Pages are fetched in parallel batches.
    """
    stop_event = stop_event or threading.Event()

    api_key = os.environ.get("WINDY_API_KEY", "")
    if not api_key:
        yield None, "[!] WINDY_API_KEY not set — skipping Windy source"  # type: ignore[misc]
        return

    country_filter = f"&country={country_code}" if country_code else ""

    # Fetch page 0 to learn the total count
    try:
        first_page = _fetch_page(session, 0, country_filter, api_key)
    except Exception as e:
        yield None, f"[!] Windy API error: {e}"  # type: ignore[misc]
        return

    if not first_page:
        yield None, "[+] Windy: no cameras returned"  # type: ignore[misc]
        return

    # Get total from a fresh request (total field in response)
    try:
        url0 = _build_url(0, country_filter)
        total_resp = session.get(url0, headers={"x-windy-api-key": api_key}, timeout=30)
        total = total_resp.json().get("total", 0)
    except Exception:
        total = len(first_page)

    offsets = list(range(_LIMIT, total, _LIMIT))
    yield None, f"[*] Windy: {total} cameras across {1 + len(offsets)} pages — fetching in parallel..."  # type: ignore[misc]

    # Collect all pages: first page already fetched, rest in parallel
    all_webcams: list[dict] = list(first_page)

    if offsets and not stop_event.is_set():
        with ThreadPoolExecutor(max_workers=_PAGE_WORKERS) as ex:
            futures = {
                ex.submit(_fetch_page, session, off, country_filter, api_key): off
                for off in offsets
            }
            for fut in as_completed(futures):
                if stop_event.is_set():
                    ex.shutdown(wait=False, cancel_futures=True)
                    break
                try:
                    all_webcams.extend(fut.result())
                except Exception as e:
                    yield None, f"[!] Windy page error: {e}"  # type: ignore[misc]

    yield None, f"[*] Windy: building cameras from {len(all_webcams)} records..."  # type: ignore[misc]

    total_emitted = 0
    for wc in all_webcams:
        if stop_event.is_set():
            break
        try:
            cam = _webcam_to_camera(wc)
        except Exception:
            continue
        msg = f"[+] Windy {cam['camera_id']} | {cam['camera_name']} | {cam['category']} | {cam['city']}, {cam['country_code']}"
        yield cam, msg
        total_emitted += 1

    yield None, f"[+] Windy complete — {total_emitted} cameras"  # type: ignore[misc]
