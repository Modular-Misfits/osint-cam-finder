import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Iterator

import requests

from app.core.schema import Camera, infer_category

PAGE_POOL_SIZE  = 15   # parallel listing page fetches
CONNECT_TIMEOUT = 4
READ_TIMEOUT    = 8

USER_AGENT = (
    "Mozilla/5.0 (Linux; Android 12; SAMSUNG SM-A125F) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "SamsungBrowser/19.0 Chrome/102.0.5005.125 Mobile Safari/537.36"
)

thread_local = threading.local()


def _get_thread_session() -> requests.Session:
    if not hasattr(thread_local, "session"):
        s = requests.Session()
        s.headers.update({"User-Agent": USER_AGENT})
        thread_local.session = s
    return thread_local.session


def _fetch_page(country_code: str, page: int) -> tuple[int, str]:
    url = f"http://www.insecam.org/en/bycountry/{country_code}/?page={page}"
    resp = _get_thread_session().get(url, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT))
    resp.raise_for_status()
    return page, resp.text


# Each camera thumbnail block on the listing page looks like:
#   <div class="thumbnail-item__wrap">
#     ...src="http://IP:PORT/path"...
#     /en/view/CAMID/
#     ...timezone, city, country strings...
# We extract all fields we can directly from listing HTML — no per-camera detail requests.
_CITY_RE = re.compile(r'class="thumbnail-item__city[^"]*"[^>]*>\s*([^<]+)<', re.IGNORECASE)
_TYPE_RE = re.compile(r'class="thumbnail-item__type[^"]*"[^>]*>\s*([^<]+)<', re.IGNORECASE)


def _parse_cameras(
    html: str,
    country_code: str,
    country_name: str,
    skip_ids: set[str],
    seen_ids: set[str],
) -> list[Camera]:
    cameras = []
    # Split on thumbnail wrapper boundaries so regex doesn't bleed across blocks
    blocks = re.split(r'class="thumbnail-item__wrap"', html)
    for block in blocks[1:]:  # first split is before any block
        url_m = re.search(r'src="(http://\d+\.\d+\.\d+\.\d+:\d+[^"]*)"', block)
        id_m  = re.search(r'/en/view/(\d+)/', block)
        if not url_m or not id_m:
            continue
        cam_id   = id_m.group(1)
        cam_url  = url_m.group(1)
        if cam_id in skip_ids or cam_id in seen_ids:
            continue
        seen_ids.add(cam_id)

        city_m = _CITY_RE.search(block)
        type_m = _TYPE_RE.search(block)
        city     = city_m.group(1).strip() if city_m else ""
        cam_type = type_m.group(1).strip() if type_m else ""

        inferred = infer_category([cam_type])
        cameras.append(Camera(
            source="Insecam",
            camera_id=cam_id,
            url=cam_url,
            camera_name=cam_type or cam_id,
            camera_type=cam_type,
            category=inferred if inferred != "unknown" else "security",
            latitude=None,
            longitude=None,
            country=country_name,
            country_code=country_code,
            state="",
            city=city,
            region="",
            extra={},
        ))
    return cameras


def run(
    session: requests.Session,  # noqa: ARG001 — kept for source interface contract
    country_code: str,
    country_name: str,
    skip_ids: set[str] | None = None,
    stop_event: threading.Event | None = None,
) -> Iterator[tuple[Camera, str]]:
    """
    Yields (camera, log_message) tuples.
    All metadata is extracted from listing pages only — no per-camera HTTP requests.
    skip_ids: camera IDs already in DB — enables resume.
    stop_event: set to request graceful cancellation.
    """
    skip_ids  = skip_ids or set()
    stop_event = stop_event or threading.Event()
    seen_ids: set[str] = set()

    try:
        _, first_html = _fetch_page(country_code, 1)
    except Exception as e:
        yield None, f"[!] Failed to fetch first page: {e}"  # type: ignore[misc]
        return

    if not re.search(r'/en/view/\d+/', first_html):
        yield None, f"[!] No cameras found for {country_code}"  # type: ignore[misc]
        return

    # Pagination is driven by JS: pagenavigator("?page=", TOTAL_PAGES, CURRENT)
    # The only ?page= link in the HTML is the next-page arrow, so we must parse
    # the pagenavigator call to get the real total page count.
    pagnav_m  = re.search(r'pagenavigator\(\s*"[^"]*"\s*,\s*(\d+)', first_html)
    last_page = int(pagnav_m.group(1)) if pagnav_m else 1
    yield None, f"[*] {country_code}: {last_page} page(s) — fetching in parallel..."  # type: ignore[misc]

    # Collect all pages in parallel (first page already fetched)
    all_html: list[str] = [first_html]
    if last_page > 1 and not stop_event.is_set():
        with ThreadPoolExecutor(max_workers=PAGE_POOL_SIZE) as ex:
            futures = {
                ex.submit(_fetch_page, country_code, p): p
                for p in range(2, last_page + 1)
            }
            for fut in as_completed(futures):
                if stop_event.is_set():
                    ex.shutdown(wait=False, cancel_futures=True)
                    break
                try:
                    _, html = fut.result(timeout=30)
                    all_html.append(html)
                except Exception:
                    pass

    # Parse all pages and yield cameras immediately — no further HTTP requests
    total = 0
    for html in all_html:
        if stop_event.is_set():
            break
        cameras = _parse_cameras(html, country_code, country_name, skip_ids, seen_ids)
        for cam in cameras:
            if stop_event.is_set():
                break
            total += 1
            yield cam, f"[+] {cam['url']} | {cam['city']} | {cam['camera_type']}"  # type: ignore[misc]
        if total and total % 100 == 0:
            yield None, f"[...] {total} cameras found so far"  # type: ignore[misc]

    yield None, f"[+] Insecam {country_code} complete — {total} cameras (skipped {len(skip_ids)} already in DB)"  # type: ignore[misc]
