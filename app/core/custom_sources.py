import json
import os
import re
import threading
from typing import Any, Callable, Iterator

import jmespath
import requests

from app.core.schema import CATEGORIES, Camera, infer_category

_BUILTIN_NAMES = {"Insecam", "FAA WeatherCams", "OpenStreetMap", "Windy Webcams", "US DOT Traffic"}
_TOKEN_RE = re.compile(r"\{([A-Z][A-Z0-9_]*)\}")
_ENV_VAR_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")

_CUSTOM_SOURCES_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "custom_sources.json")
)


def _interpolate(value: str) -> str:
    """Replace {ENV_VAR} tokens with values from os.environ."""
    return _TOKEN_RE.sub(lambda m: os.environ.get(m.group(1), ""), value)


def _interpolate_dict(d: dict) -> dict:
    return {k: _interpolate(v) if isinstance(v, str) else v for k, v in d.items()}


def _extract(obj: Any, path: str) -> Any:
    if not path:
        return obj
    try:
        return jmespath.search(path, obj)
    except Exception:
        return None


def _validate(defn: dict, existing_names: set[str] | None = None) -> list[str]:
    errors: list[str] = []
    name = defn.get("name", "").strip()

    if not name:
        errors.append("Name is required.")
    elif name in _BUILTIN_NAMES:
        errors.append(f"'{name}' conflicts with a built-in source name.")
    elif existing_names and name in existing_names:
        errors.append(f"A custom source named '{name}' already exists.")

    endpoint = defn.get("endpoint", "")
    if not endpoint.startswith("http://") and not endpoint.startswith("https://"):
        errors.append("Endpoint must start with http:// or https://")

    if defn.get("method", "GET") not in ("GET", "POST"):
        errors.append("Method must be GET or POST.")

    if "camera_id" not in defn.get("field_map", {}):
        errors.append("Field map must include 'camera_id' (required for deduplication).")

    pag = defn.get("pagination", {})
    if pag.get("style") == "cursor":
        if not pag.get("cursor_path"):
            errors.append("Cursor pagination requires 'cursor_path'.")
        if not pag.get("cursor_param"):
            errors.append("Cursor pagination requires 'cursor_param'.")

    env_var = defn.get("api_key_env_var", "")
    if env_var and not _ENV_VAR_RE.match(env_var):
        errors.append("API key env var must be uppercase letters, numbers, and underscores.")

    return errors


def _assemble_camera(item: dict, defn: dict, source_name: str) -> Camera | None:
    field_map: dict = defn.get("field_map", {})
    defaults: dict = defn.get("defaults", {})

    def get(field: str) -> Any:
        path = field_map.get(field)
        if path:
            val = _extract(item, path)
            if val is not None:
                return val
        return defaults.get(field)

    cam_id = get("camera_id")
    if cam_id is None:
        return None

    lat = get("latitude")
    lon = get("longitude")
    try:
        lat = float(lat) if lat is not None else None
    except (ValueError, TypeError):
        lat = None
    try:
        lon = float(lon) if lon is not None else None
    except (ValueError, TypeError):
        lon = None

    cam_type = str(get("camera_type") or "webcam")
    category  = str(get("category") or "unknown")
    if category not in CATEGORIES:
        cam_name_hint = str(get("camera_name") or "")
        category = infer_category([cam_type, cam_name_hint])

    return Camera(
        source=source_name,
        camera_id=str(cam_id),
        url=str(get("url")) if get("url") else None,
        camera_name=str(get("camera_name") or cam_id),
        camera_type=cam_type,
        category=category,
        latitude=lat,
        longitude=lon,
        country=str(get("country") or ""),
        country_code=str(get("country_code") or ""),
        state=str(get("state") or ""),
        city=str(get("city") or ""),
        region=str(get("region") or ""),
        extra={},
    )


def run_custom_source(
    defn: dict,
    session: requests.Session,
    stop_event: threading.Event | None = None,
    max_preview: int | None = None,
) -> Iterator[tuple[Camera | None, str]]:
    """
    Execute a custom source definition. Yields (Camera | None, log_str).
    max_preview: if set, stop after this many cameras (used for test preview).
    """
    stop_event = stop_event or threading.Event()
    source_name: str = defn["name"]
    endpoint: str = _interpolate(defn.get("endpoint", ""))
    method: str = defn.get("method", "GET").upper()
    headers: dict = _interpolate_dict(defn.get("headers", {}))
    params: dict = _interpolate_dict({k: str(v) for k, v in defn.get("params", {}).items()})
    cameras_path: str = defn.get("cameras_path", "")
    pag: dict = defn.get("pagination", {})
    pag_style: str = pag.get("style", "none")
    pag_param: str = pag.get("param_name", "offset")
    page_size: int = int(pag.get("page_size", 100))
    max_pages: int = int(pag.get("max_pages", 200))
    cursor_path: str = pag.get("cursor_path", "")
    cursor_param: str = pag.get("cursor_param", "")

    total = 0
    page = 0
    offset = 0
    cursor: str | None = None

    while not stop_event.is_set():
        if page >= max_pages:
            yield None, f"[!] {source_name}: reached max_pages limit ({max_pages})"  # type: ignore[misc]
            break

        # Build request params for this page
        req_params = dict(params)
        if pag_style == "offset":
            req_params[pag_param] = str(offset)
        elif pag_style == "page":
            req_params[pag_param] = str(page)
        elif pag_style == "cursor" and cursor is not None:
            req_params[cursor_param] = cursor

        yield None, f"[*] {source_name}: fetching page {page + 1}..."  # type: ignore[misc]

        try:
            if method == "POST":
                resp = session.post(endpoint, headers=headers, json=req_params, timeout=30)
            else:
                resp = session.get(endpoint, headers=headers, params=req_params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            yield None, f"[!] {source_name} request failed: {e}"  # type: ignore[misc]
            return

        # Extract camera list
        if cameras_path:
            cam_list = _extract(data, cameras_path)
        else:
            cam_list = data

        if cam_list is None:
            yield None, f"[!] {source_name}: cameras_path '{cameras_path}' returned nothing"  # type: ignore[misc]
            return

        if isinstance(cam_list, dict):
            cam_list = [cam_list]

        if not isinstance(cam_list, list):
            yield None, f"[!] {source_name}: expected a list, got {type(cam_list).__name__}"  # type: ignore[misc]
            return

        page_count = 0
        for item in cam_list:
            if stop_event.is_set():
                return
            cam = _assemble_camera(item, defn, source_name)
            if cam is None:
                continue
            total += 1
            page_count += 1
            yield cam, f"[+] {source_name} | {cam['camera_id']} | {cam['camera_name']} | {cam['city']}"
            if max_preview is not None and total >= max_preview:
                return

        yield None, f"[+] {source_name}: {total} cameras so far"  # type: ignore[misc]

        # Decide whether to continue
        if pag_style == "none":
            break
        elif pag_style in ("offset", "page"):
            if page_count < page_size:
                break  # last page
            offset += page_size
        elif pag_style == "cursor":
            cursor = _extract(data, cursor_path)
            if not cursor:
                break

        page += 1

    yield None, f"[+] {source_name} complete — {total} cameras"  # type: ignore[misc]


class CustomSourceRegistry:
    def __init__(self):
        self._sources: list[dict] = []
        self._callbacks: list[Callable] = []
        self._lock = threading.Lock()
        self.load()

    def load(self) -> None:
        if os.path.exists(_CUSTOM_SOURCES_PATH):
            try:
                with open(_CUSTOM_SOURCES_PATH) as f:
                    data = json.load(f)
                if isinstance(data, list):
                    with self._lock:
                        self._sources = data
            except Exception:
                pass

    def save(self) -> None:
        with self._lock:
            sources = list(self._sources)
        with open(_CUSTOM_SOURCES_PATH, "w") as f:
            json.dump(sources, f, indent=2)

    def all(self) -> list[dict]:
        with self._lock:
            return list(self._sources)

    def enabled(self) -> list[dict]:
        with self._lock:
            return [s for s in self._sources if s.get("enabled", True)]

    def get(self, name: str) -> dict | None:
        with self._lock:
            for s in self._sources:
                if s.get("name") == name:
                    return dict(s)
        return None

    def _existing_names(self, exclude: str = "") -> set[str]:
        with self._lock:
            return {s["name"] for s in self._sources if s.get("name") != exclude}

    def add(self, defn: dict) -> None:
        errors = _validate(defn, existing_names=self._existing_names())
        if errors:
            raise ValueError("\n".join(errors))
        with self._lock:
            self._sources.append(defn)
        self.save()
        self._notify()

    def update(self, name: str, defn: dict) -> None:
        errors = _validate(defn, existing_names=self._existing_names(exclude=name))
        if errors:
            raise ValueError("\n".join(errors))
        with self._lock:
            for i, s in enumerate(self._sources):
                if s.get("name") == name:
                    self._sources[i] = defn
                    break
        self.save()
        self._notify()

    def delete(self, name: str) -> None:
        with self._lock:
            self._sources = [s for s in self._sources if s.get("name") != name]
        self.save()
        self._notify()

    def register_change_callback(self, cb: Callable) -> None:
        self._callbacks.append(cb)

    def _notify(self) -> None:
        for cb in self._callbacks:
            try:
                cb()
            except Exception:
                pass

    def validate(self, defn: dict, original_name: str = "") -> list[str]:
        return _validate(defn, existing_names=self._existing_names(exclude=original_name))
