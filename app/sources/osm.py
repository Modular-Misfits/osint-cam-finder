import threading
import time
from typing import Iterator
from urllib.parse import quote

import requests

from app.core.schema import Camera, infer_category

# overpass-api.de is the only public instance with area support (area_tags_local.bin).
_OVERPASS_URL = "https://overpass-api.de/api/interpreter"

_HEADERS = {
    "User-Agent": "osint-cam-finder/1.0 (https://github.com/Modular-Misfits/osint-cam-finder)",
    "Content-Type": "application/x-www-form-urlencoded",
}

# ISO 3166-1 alpha-2 codes to scan when no specific country is requested.
_DEFAULT_COUNTRIES = [
    "DE", "GB", "FR", "IT", "ES", "NL", "BE", "CH", "AT", "PL",
    "CZ", "SE", "NO", "DK", "FI", "PT", "RO", "HU", "SK", "HR",
    "US", "CA", "AU", "NZ", "JP", "KR", "CN", "IN", "BR", "ZA",
    "RU", "UA", "SG", "HK", "TW", "MX", "AR", "CL", "CO", "TR",
]

# Countries whose admin_level=2 area relation is too large for Overpass to
# intersect within 60s. These are queried via bbox sub-regions instead.
# Each entry: iso2 → list of (south, west, north, east, label) tuples.
_BBOX_COUNTRIES: dict[str, list[tuple[float, float, float, float, str]]] = {
    "US": [
        (37,  -125, 50,  -115, "US Pacific NW"),
        (32,  -125, 37,  -115, "US California"),
        (31,  -115, 50,   -95, "US Mountain"),
        (37,   -95, 50,   -87, "US Midwest NW"),
        (37,   -87, 50,   -80, "US Midwest NE"),
        (31,   -95, 37,   -80, "US Midwest S"),
        (40,   -80, 48,   -74, "US New England N"),
        (39,   -78, 41,   -74, "US Mid-Atlantic N"),
        (37,   -80, 39,   -74, "US Mid-Atlantic S"),
        (40,   -74, 48,   -67, "US New England E"),
        (24,   -87, 37,   -75, "US Southeast"),
        (24,   -97, 31,   -87, "US Gulf Coast"),
        (51,  -180, 72,  -130, "Alaska"),
        (18,  -160, 23,  -154, "Hawaii"),
    ],
    "RU": [
        (41,   27,  72,  60, "Russia West"),
        (41,   60,  72,  90, "Russia Central"),
        (41,   90,  72, 140, "Russia East"),
        (41,  140,  72, 180, "Russia Far East"),
    ],
    "CA": [
        (42,  -140,  72,  -95, "Canada West"),
        (42,   -95,  72,  -52, "Canada East"),
    ],
    "CN": [
        (18,   73,  54, 105, "China West"),
        (18,  105,  54, 135, "China East"),
    ],
    "AU": [
        (-44, 113, -10, 154, "Australia"),
    ],
    "BR": [
        (-34, -74,   5, -35, "Brazil"),
    ],
    "IN": [
        (  8,  68,  38,  98, "India"),
    ],
}

_NODES_PER_QUERY = 1000

_TAG_CATEGORY_HINTS = {
    "surveillance":       "security",
    "monitoring_station": "weather",
    "webcam":             "tourist",
    "traffic_signals":    "traffic",
}


def _tags_to_category(tags: dict) -> str:
    for tag_val, cat in _TAG_CATEGORY_HINTS.items():
        for v in tags.values():
            if tag_val in str(v).lower():
                return cat
    hints = [tags.get("surveillance:type", ""), tags.get("man_made", ""),
             tags.get("description", ""), tags.get("name", "")]
    return infer_category(hints)


def _post(session: requests.Session, query: str) -> tuple[list[dict], str | None]:
    for attempt in range(3):
        try:
            resp = session.post(
                _OVERPASS_URL,
                data="data=" + quote(query),
                headers=_HEADERS,
                timeout=90,
            )
            if resp.status_code in (502, 503, 504):
                time.sleep(10 * (attempt + 1))
                continue
            if resp.status_code != 200:
                return [], f"HTTP {resp.status_code}"
            data = resp.json()
            remark = data.get("remark", "")
            if remark and "timed out" in remark.lower():
                return [], f"timeout: {remark}"
            return data.get("elements", []), None
        except Exception as e:
            if attempt < 2:
                time.sleep(5)
                continue
            return [], str(e)
    return [], "max retries exceeded"


def _query_by_area(session: requests.Session, iso2: str) -> tuple[list[dict], str | None]:
    query = f"""[out:json][timeout:60];
area["ISO3166-1"="{iso2}"][admin_level=2]->.a;
(
  node["man_made"="surveillance"](area.a);
  node["man_made"="webcam"](area.a);
  node["surveillance"="outdoor"](area.a);
  node["surveillance"="traffic"](area.a);
);
out body {_NODES_PER_QUERY};
"""
    return _post(session, query)


def _query_by_bbox(session: requests.Session, south: float, west: float, north: float, east: float) -> tuple[list[dict], str | None]:
    bbox = f"{south},{west},{north},{east}"
    query = f"""[out:json][timeout:60];
(
  node["man_made"="surveillance"]({bbox});
  node["man_made"="webcam"]({bbox});
  node["surveillance"="outdoor"]({bbox});
  node["surveillance"="traffic"]({bbox});
);
out body {_NODES_PER_QUERY};
"""
    return _post(session, query)


def run(
    session: requests.Session,
    stop_event: threading.Event | None = None,
    countries: list[str] | None = None,
) -> Iterator[tuple[Camera, str]]:
    """
    Yields (camera, log_message) tuples.
    countries: list of ISO 3166-1 alpha-2 codes, or None to use _DEFAULT_COUNTRIES.
    """
    stop_event = stop_event or threading.Event()
    country_list = countries if countries is not None else _DEFAULT_COUNTRIES

    total_nodes = 0

    for iso2 in country_list:
        if stop_event.is_set():
            break

        if iso2 in _BBOX_COUNTRIES:
            # Large country: query each bbox sub-region
            for south, west, north, east, label in _BBOX_COUNTRIES[iso2]:
                if stop_event.is_set():
                    break
                yield None, f"[*] Querying Overpass: {label}..."  # type: ignore[misc]
                elements, err = _query_by_bbox(session, south, west, north, east)
                if err:
                    yield None, f"[!] {label} failed: {err}"  # type: ignore[misc]
                    time.sleep(2)
                    continue
                total_nodes += len(elements)
                yield None, f"[+] {label}: {len(elements)} nodes ({total_nodes} total)"  # type: ignore[misc]
                yield from _emit_cameras(elements, iso2, stop_event)
                time.sleep(2)
        else:
            yield None, f"[*] Querying Overpass: {iso2}..."  # type: ignore[misc]
            elements, err = _query_by_area(session, iso2)
            if err:
                yield None, f"[!] {iso2} failed: {err}"  # type: ignore[misc]
                time.sleep(2)
                continue
            total_nodes += len(elements)
            yield None, f"[+] {iso2}: {len(elements)} nodes ({total_nodes} total)"  # type: ignore[misc]
            yield from _emit_cameras(elements, iso2, stop_event)
            time.sleep(2)

    yield None, f"[+] Overpass complete — {total_nodes} nodes total"  # type: ignore[misc]


def _emit_cameras(
    elements: list[dict],
    iso2: str,
    stop_event: threading.Event,
) -> Iterator[tuple[Camera, str]]:
    for el in elements:
        if stop_event.is_set():
            break
        tags     = el.get("tags", {})
        node_id  = str(el.get("id", ""))
        lat      = el.get("lat")
        lon      = el.get("lon")
        name     = (tags.get("name") or tags.get("description")
                    or tags.get("operator") or tags.get("note") or f"OSM {node_id}")
        url      = tags.get("url") or tags.get("contact:website") or tags.get("image") or ""
        city     = tags.get("addr:city") or tags.get("is_in:city") or tags.get("is_in") or ""
        state    = tags.get("addr:state") or tags.get("is_in:state") or ""
        country  = tags.get("addr:country") or tags.get("is_in:country") or ""
        cam_type = tags.get("surveillance:type") or tags.get("man_made") or tags.get("surveillance") or "surveillance"
        category = _tags_to_category(tags)

        camera = Camera(
            source="OpenStreetMap",
            camera_id=node_id,
            url=url or None,
            camera_name=name,
            camera_type=cam_type,
            category=category,
            latitude=lat,
            longitude=lon,
            country=country or iso2,
            country_code=iso2,
            state=state,
            city=city,
            region="",
            extra={"osm_tags": tags},
        )
        yield camera, f"[+] OSM {node_id} | {name} | {category} | {lat}, {lon}"
