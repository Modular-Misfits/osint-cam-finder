import queue
import threading
from typing import Any

import requests

from app.core.custom_sources import CustomSourceRegistry, run_custom_source
from app.db.store import Store
from app.sources import dot_traffic, faa, insecam, osm, windy

custom_registry = CustomSourceRegistry()

# Event types emitted to the UI queue
# {"type": "camera_found",  "data": dict}
# {"type": "progress",      "data": {"done": int, "total": int}}
# {"type": "log",           "data": str}
# {"type": "scan_complete", "data": {"new": int, "updated": int, "unchanged": int, "total": int}}
# {"type": "scan_error",    "data": str}

SOURCES = {
    "Insecam":        insecam,
    "FAA WeatherCams": faa,
    "OpenStreetMap":  osm,
    "Windy Webcams":  windy,
    "US DOT Traffic": dot_traffic,
}


def _emit(q: queue.Queue, type_: str, data: Any):
    q.put({"type": type_, "data": data})


class ScanRunner:
    def __init__(self, store: Store, ui_queue: queue.Queue):
        self.store = store
        self.ui_queue = ui_queue
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self, source: str, **kwargs):
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            args=(source,),
            kwargs=kwargs,
            daemon=True,
        )
        self._thread.start()

    def stop(self):
        self._stop_event.set()

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _run(self, source: str, **kwargs):
        q = self.ui_queue
        store = self.store

        filter_val = kwargs.get("country_code", kwargs.get("state", ""))
        run_id = store.start_run(source, filter_val)

        session = requests.Session()
        counts = {"new": 0, "updated": 0, "unchanged": 0, "total": 0}
        seen_ids: set[str] = set()

        try:
            _emit(q, "log", f"[*] Starting {source} scan...")

            if source == "Insecam":
                country_code = kwargs.get("country_code", "")
                country_name = kwargs.get("country_name", "")
                skip_ids = store.known_camera_ids("Insecam", country_code)
                if skip_ids:
                    _emit(q, "log", f"[*] Resuming — skipping {len(skip_ids)} cameras already in DB")

                generator = insecam.run(
                    session=session,
                    country_code=country_code,
                    country_name=country_name,
                    skip_ids=skip_ids,
                    stop_event=self._stop_event,
                )

            elif source == "FAA WeatherCams":
                generator = faa.run(session=session, stop_event=self._stop_event)

            elif source == "OpenStreetMap":
                generator = osm.run(
                    session=session,
                    stop_event=self._stop_event,
                    countries=kwargs.get("countries"),
                )

            elif source == "Windy Webcams":
                generator = windy.run(
                    session=session,
                    stop_event=self._stop_event,
                    country_code=kwargs.get("country_code", ""),
                )

            elif source == "US DOT Traffic":
                generator = dot_traffic.run(
                    session=session,
                    state_code=kwargs.get("state_code", ""),
                    stop_event=self._stop_event,
                )

            elif (defn := custom_registry.get(source)) is not None:
                generator = run_custom_source(defn, session, self._stop_event)

            else:
                _emit(q, "scan_error", f"Unknown source: {source}")
                store.finish_run(run_id, "failed", 0, 0, 0)
                return

            for cam, msg in generator:
                if msg:
                    _emit(q, "log", msg)

                if cam is None:
                    continue

                delta = store.upsert_camera(cam)
                if delta == "skipped":
                    continue
                seen_ids.add(cam["camera_id"])
                counts[delta] = counts.get(delta, 0) + 1
                counts["total"] += 1
                _emit(q, "camera_found", {**cam, "_delta": delta})

            # Mark cameras not seen in this run as offline
            if source == "Insecam" and not self._stop_event.is_set():
                country_code = kwargs.get("country_code", "")
                store.mark_offline("Insecam", country_code, seen_ids)

            status = "interrupted" if self._stop_event.is_set() else "completed"
            store.finish_run(run_id, status, counts["total"], counts["new"], counts["updated"])

            _emit(q, "scan_complete", counts)
            _emit(q, "log", (
                f"[+] Done — {counts['total']} cameras"
                f" ({counts['new']} new, {counts['updated']} updated,"
                f" {counts['unchanged']} unchanged)"
            ))

        except Exception as e:
            _emit(q, "scan_error", str(e))
            store.finish_run(run_id, "failed", counts["total"], counts["new"], counts["updated"])
