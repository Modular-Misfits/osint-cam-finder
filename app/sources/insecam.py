import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Iterator

import requests

from app.core.schema import Camera, infer_category

THREAD_POOL_SIZE   = 40   # Phase 2 enrichment — network-latency bound, benefits from more threads
PAGE_POOL_SIZE     = 10   # Phase 1 page scraping
CONNECT_TIMEOUT    = 4
READ_TIMEOUT       = 5
FUTURE_DEADLINE    = CONNECT_TIMEOUT + READ_TIMEOUT + 3

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


def _fetch_detail(cam_id: str) -> dict:
    url = f"http://www.insecam.org/en/view/{cam_id}/"
    try:
        resp = _get_thread_session().get(url, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT))
        html = resp.text

        title_m = re.search(r'<title>\s*View\s+(.*?)\s+camera\s+in\s+(.*?)\s*</title>', html, re.IGNORECASE)
        cam_type = title_m.group(1).strip() if title_m else ""
        location_raw = title_m.group(2).strip() if title_m else ""

        coords = re.findall(r'(?:setView|marker|LatLng)\s*\(\s*\[?\s*(-?[\d.]+)\s*,\s*(-?[\d.]+)', html, re.IGNORECASE)
        latitude = float(coords[0][0]) if coords else None
        longitude = float(coords[0][1]) if coords else None

        city = region = ""
        desc_m = re.search(r'Watch live cam located in ([^\r\n<]+)', html, re.IGNORECASE)
        if desc_m:
            raw = desc_m.group(1).strip()
            region_m = re.search(r'region\s+(\S+)\s+(.*)', raw)
            if region_m:
                region = region_m.group(1).strip()
                city = region_m.group(2).strip()
        elif location_raw:
            parts = [p.strip() for p in location_raw.split(",")]
            if len(parts) >= 2:
                city = parts[-1]

        return {
            "camera_type": cam_type,
            "latitude": latitude,
            "longitude": longitude,
            "city": city,
            "region": region,
            "location_raw": location_raw,
        }
    except Exception:
        return {}


def _enrich(cam_id: str, cam_url: str, country_code: str, country_name: str) -> Camera:
    try:
        resp = _get_thread_session().get(cam_url, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT))
        status = resp.status_code
        server = resp.headers.get("Server", "")
    except Exception:
        status, server = None, ""

    detail = _fetch_detail(cam_id)
    cam_type = detail.get("camera_type", "")

    return Camera(
        source="Insecam",
        camera_id=cam_id,
        url=cam_url,
        camera_name=cam_type or cam_id,
        camera_type=cam_type,
        category=infer_category([cam_type, server or ""]),
        latitude=detail.get("latitude"),
        longitude=detail.get("longitude"),
        country=country_name,
        country_code=country_code,
        state="",
        city=detail.get("city", ""),
        region=detail.get("region", ""),
        extra={
            "http_status": status,
            "server": server,
            "location_raw": detail.get("location_raw", ""),
        },
    )


def _fetch_page(country_code: str, page: int) -> tuple[int, str]:
    """Fetch one listing page; returns (page_number, html)."""
    url = f"http://www.insecam.org/en/bycountry/{country_code}/?page={page}"
    resp = _get_thread_session().get(url, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT))
    resp.raise_for_status()
    return page, resp.text


def _parse_pairs(html: str, skip_ids: set[str], existing: dict[str, str]) -> dict[str, str]:
    """Extract (cam_id → stream_url) pairs from one listing page HTML."""
    pairs: dict[str, str] = {}
    for m in re.finditer(r'/en/view/(\d+)/', html):
        cid = m.group(1)
        if cid in existing or cid in skip_ids:
            continue
        tail = html[m.start(): m.start() + 600]
        url_m = re.search(r'src="(http://\d+\.\d+\.\d+\.\d+:\d+[^"]*)"', tail)
        if url_m:
            pairs[cid] = url_m.group(1)
    return pairs


def run(
    session: requests.Session,  # noqa: ARG001 — kept for source interface contract
    country_code: str,
    country_name: str,
    skip_ids: set[str] | None = None,
    stop_event: threading.Event | None = None,
) -> Iterator[tuple[Camera, str]]:
    """
    Yields (camera, log_message) tuples.
    skip_ids: camera IDs already in DB — enables resume.
    stop_event: set to request graceful cancellation.
    """
    skip_ids = skip_ids or set()
    stop_event = stop_event or threading.Event()

    all_pairs: dict[str, str] = {}

    # Phase 1: discover total page count from page 1, then fetch remaining pages in parallel
    try:
        _, first_html = _fetch_page(country_code, 1)
        if not re.search(r'/en/view/\d+/', first_html):
            yield None, f"[!] No cameras found for {country_code}"  # type: ignore[misc]
            return

        all_pairs.update(_parse_pairs(first_html, skip_ids, all_pairs))

        # Discover last page number from pagination links
        page_nums = [int(n) for n in re.findall(r'\?page=(\d+)', first_html)]
        last_page = max(page_nums) if page_nums else 1

        if last_page > 1 and not stop_event.is_set():
            yield None, f"[*] {country_code}: {last_page} pages to fetch — parallel..."  # type: ignore[misc]
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
                        _, html = fut.result(timeout=FUTURE_DEADLINE)
                        all_pairs.update(_parse_pairs(html, skip_ids, all_pairs))
                    except Exception:
                        pass
    except Exception as e:
        yield None, f"[!] Page collection error: {e}"  # type: ignore[misc]

    total = len(all_pairs)
    yield None, f"[+] Found {total} new cameras to enrich (skipped {len(skip_ids)} already in DB)"  # type: ignore[misc]

    if not all_pairs or stop_event.is_set():
        return

    # Phase 2: parallel enrichment
    done = 0
    with ThreadPoolExecutor(max_workers=THREAD_POOL_SIZE) as executor:
        futures = {
            executor.submit(_enrich, cid, curl, country_code, country_name): cid
            for cid, curl in all_pairs.items()
        }
        for future in as_completed(futures):
            if stop_event.is_set():
                executor.shutdown(wait=False, cancel_futures=True)
                break
            cid = futures[future]
            try:
                cam = future.result(timeout=FUTURE_DEADLINE)
                city_display = cam["city"] or cam["extra"].get("location_raw", "")
                lat = cam["latitude"] or ""
                lon = cam["longitude"] or ""
                msg = (
                    f"[+] {cam['url']}  [{cam['extra'].get('server', '')}]"
                    f"  [{cam['extra'].get('http_status', '')}]"
                    f"  | {city_display} | {lat}, {lon}"
                )
                yield cam, msg
            except TimeoutError:
                yield None, f"[!] Camera {cid} timed out — skipping"  # type: ignore[misc]
            except Exception:
                pass
            done += 1
            if done % 50 == 0:
                yield None, f"[...] {done}/{total} cameras processed"  # type: ignore[misc]
