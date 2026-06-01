"""
Insecam detail-page enricher.

Fetches http://www.insecam.org/en/view/{cam_id}/ for each unenriched
Insecam camera and patches lat/lon, city, region, state, country, zip,
timezone, and manufacturer into the database.

Rate limiting: one request every DELAY_BETWEEN_REQUESTS seconds to avoid
hammering insecam.org and triggering blocks.
"""
import queue
import re
import threading
import time
from typing import Any

import requests

from app.db.store import Store

_BASE         = "http://www.insecam.org/en/view/{}/"
_USER_AGENT   = (
    "Mozilla/5.0 (Linux; Android 12; SAMSUNG SM-A125F) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "SamsungBrowser/19.0 Chrome/102.0.5005.125 Mobile Safari/537.36"
)
DELAY_BETWEEN_REQUESTS = 0.5   # seconds between requests — polite but fast
CONNECT_TIMEOUT        = 5
READ_TIMEOUT           = 10


def _scrape_detail(html: str) -> dict[str, Any]:
    """Extract enrichment fields from a detail page HTML string."""
    result: dict[str, Any] = {}

    # Lat/lon from Leaflet setView
    coord_m = re.search(r'setView\(\[([-\d.]+),\s*([-\d.]+)\]', html)
    if coord_m:
        try:
            result["latitude"]  = float(coord_m.group(1))
            result["longitude"] = float(coord_m.group(2))
        except ValueError:
            pass

    # Detail page has flat alternating camera-details__cell divs:
    # cells[0]='Country:', cells[1]='Germany', cells[2]='Country code:', cells[3]='DE', ...
    cells = re.findall(r'camera-details__cell[^>]*>(.*?)</div>', html, re.DOTALL)
    label_map: dict[str, str] = {}
    for i in range(0, len(cells) - 1, 2):
        label = re.sub(r'<[^>]+>', '', cells[i]).strip().rstrip(":").lower()
        value = re.sub(r'<[^>]+>', '', cells[i + 1]).strip()
        if label and value and value not in ("n/a", "—", "-", ""):
            label_map[label] = value

    if "country" in label_map:
        result["country"] = label_map["country"]
    if "region" in label_map:
        result["region"] = label_map["region"]
    if "city" in label_map:
        result["city"] = label_map["city"]
    if "state" in label_map:
        result["state"] = label_map["state"]
    if "zip" in label_map:
        result["zip"] = label_map["zip"]
    if "timezone" in label_map:
        result["timezone"] = label_map["timezone"]

    # Manufacturer via /en/bytype/ link
    mfr_m = re.search(r'href="/en/bytype/([^/"]+)/"', html)
    if mfr_m:
        result["camera_type"] = mfr_m.group(1).replace("+", " ")

    return result


class EnrichRunner:
    """
    Runs the Insecam enrichment process in a daemon thread.
    Emits events to ui_queue identical in shape to ScanRunner events.
    """

    def __init__(self, store: Store, ui_queue: queue.Queue):
        self.store    = store
        self.ui_queue = ui_queue
        self._stop    = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self, country_code: str = ""):
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run,
            args=(country_code,),
            daemon=True,
        )
        self._thread.start()

    def stop(self):
        self._stop.set()

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _emit(self, type_: str, data: Any):
        self.ui_queue.put({"type": type_, "data": data})

    def _run(self, country_code: str):
        ids = self.store.insecam_unenriched_ids(country_code)
        total = len(ids)

        if total == 0:
            self._emit("log", "[*] Enrich: no unenriched Insecam cameras found.")
            self._emit("scan_complete", {"new": 0, "updated": 0, "unchanged": 0, "total": 0})
            return

        self._emit("log", f"[*] Enriching {total} Insecam cameras ({DELAY_BETWEEN_REQUESTS}s delay between requests)...")
        self._emit("progress", {"done": 0, "total": total})

        session = requests.Session()
        session.headers.update({"User-Agent": _USER_AGENT})

        enriched = 0
        failed   = 0

        for i, cam_id in enumerate(ids):
            if self._stop.is_set():
                self._emit("log", "[!] Enrich stopped by user.")
                break

            try:
                resp = session.get(
                    _BASE.format(cam_id),
                    timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
                )
                if resp.status_code == 200:
                    fields = _scrape_detail(resp.text)
                    self.store.enrich_camera("Insecam", cam_id, fields)
                    enriched += 1
                    lat = fields.get("latitude", "")
                    lon = fields.get("longitude", "")
                    city = fields.get("city", "")
                    self._emit("log", f"[+] {cam_id} | {city} | {lat}, {lon}")
                else:
                    failed += 1
                    self._emit("log", f"[!] {cam_id} HTTP {resp.status_code}")
            except Exception as e:
                failed += 1
                self._emit("log", f"[!] {cam_id} error: {e}")

            self._emit("progress", {"done": i + 1, "total": total})
            time.sleep(DELAY_BETWEEN_REQUESTS)

        self._emit("log", f"[+] Enrich complete — {enriched} updated, {failed} failed, {total} total")
        self._emit("scan_complete", {
            "new": 0, "updated": enriched, "unchanged": total - enriched - failed, "total": total,
        })
