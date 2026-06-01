from typing import TypedDict, Optional

CATEGORIES = ("weather", "traffic", "tourist", "aviation", "nature", "security", "unknown")

# Keywords in camera_type / tags that map to a category (checked lowercase, in order)
_TYPE_CATEGORY_MAP = [
    ("weather", "weather"),
    ("meteo",   "weather"),
    ("rain",    "weather"),
    ("wind",    "weather"),
    ("traffic", "traffic"),
    ("highway", "traffic"),
    ("freeway", "traffic"),
    ("road",    "traffic"),
    ("dot",     "traffic"),
    ("tour",    "tourist"),
    ("beach",   "tourist"),
    ("city",    "tourist"),
    ("scenic",  "tourist"),
    ("landmark","tourist"),
    ("airport", "aviation"),
    ("runway",  "aviation"),
    ("faa",     "aviation"),
    ("icao",    "aviation"),
    ("park",    "nature"),
    ("forest",  "nature"),
    ("river",   "nature"),
    ("lake",    "nature"),
    ("wildlife","nature"),
    ("mountain","nature"),
    ("ski",     "nature"),
    ("hikvision","security"),
    ("axis",    "security"),
    ("dahua",   "security"),
    ("cctv",    "security"),
    ("surveil", "security"),
    ("onvif",   "security"),
    ("vivotek", "security"),
    ("bosch",   "security"),
    ("hanwha",  "security"),
    ("uniview", "security"),
    ("reolink", "security"),
    ("foscam",  "security"),
    ("amcrest", "security"),
    ("acti",    "security"),
    ("mobotix", "security"),
    ("panasonic","security"),
    ("pelco",   "security"),
    ("avigilon","security"),
    ("genetec", "security"),
    ("milestone","security"),
    ("ip camera","security"),
    ("network camera","security"),
    ("webcam",  "security"),
    ("generic", "security"),
    ("ipcam",   "security"),
]


def infer_category(hints: list[str]) -> str:
    """Return the best-matching category from a list of hint strings."""
    combined = " ".join(h.lower() for h in hints if h)
    for keyword, category in _TYPE_CATEGORY_MAP:
        if keyword in combined:
            return category
    return "unknown"


class Camera(TypedDict):
    source:       str
    camera_id:    str
    url:          Optional[str]
    camera_name:  str
    camera_type:  str
    category:     str          # one of CATEGORIES
    latitude:     Optional[float]
    longitude:    Optional[float]
    country:      str
    country_code: str
    state:        str
    city:         str
    region:       str
    extra:        dict          # source-specific fields
