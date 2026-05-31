import json
import os
import sqlite3
from datetime import datetime, timezone
from app.db.models import init_db

_DEFAULT_DB = os.environ.get("OSINT_CAM_DB", "cameras.db")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, path: str = _DEFAULT_DB):
        self.path = path
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        init_db(self.conn)

    def close(self):
        self.conn.close()

    # ── scan_runs ─────────────────────────────────────────────────────────────

    def start_run(self, source: str, filter_val: str = "") -> int:
        cur = self.conn.execute(
            "INSERT INTO scan_runs (source, filter, started_at, status) VALUES (?,?,?,?)",
            (source, filter_val, _now(), "running"),
        )
        self.conn.commit()
        return cur.lastrowid  # type: ignore[return-value]

    def finish_run(self, run_id: int, status: str, found: int, new: int, updated: int):
        self.conn.execute(
            """UPDATE scan_runs
               SET finished_at=?, status=?, cameras_found=?, cameras_new=?, cameras_updated=?
               WHERE id=?""",
            (_now(), status, found, new, updated, run_id),
        )
        self.conn.commit()

    def get_runs(self) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM scan_runs ORDER BY id DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    # ── cameras ───────────────────────────────────────────────────────────────

    def known_camera_ids(self, source: str, country_code: str = "") -> set[str]:
        """Return IDs already in the DB for a source (used for resume logic)."""
        if country_code:
            rows = self.conn.execute(
                "SELECT camera_id FROM cameras WHERE source=? AND country_code=?",
                (source, country_code),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT camera_id FROM cameras WHERE source=?",
                (source,),
            ).fetchall()
        return {r["camera_id"] for r in rows}

    def upsert_camera(self, cam: dict) -> str:
        """
        Insert or update a camera record.
        Returns delta status: 'new' | 'updated' | 'unchanged' | 'skipped'
        Skips records that have no URL and no usable location (lat/lon or city/country).
        """
        has_url = bool(cam.get("url"))
        has_coords = cam.get("latitude") is not None and cam.get("longitude") is not None
        has_place = bool(cam.get("city") or cam.get("state")) and bool(cam.get("country") or cam.get("country_code"))
        if not has_url and not has_coords and not has_place:
            return "skipped"

        extra = json.dumps(cam.get("extra") or {})
        now = _now()

        existing = self.conn.execute(
            "SELECT * FROM cameras WHERE source=? AND camera_id=?",
            (cam["source"], cam["camera_id"]),
        ).fetchone()

        if existing is None:
            self.conn.execute(
                """INSERT INTO cameras
                   (source, camera_id, url, camera_name, camera_type, category,
                    latitude, longitude, country, country_code, state, city, region,
                    extra, first_seen, last_seen, status)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    cam.get("source", ""),
                    cam.get("camera_id", ""),
                    cam.get("url"),
                    cam.get("camera_name", ""),
                    cam.get("camera_type", ""),
                    cam.get("category", "unknown"),
                    cam.get("latitude"),
                    cam.get("longitude"),
                    cam.get("country", ""),
                    cam.get("country_code", ""),
                    cam.get("state", ""),
                    cam.get("city", ""),
                    cam.get("region", ""),
                    extra,
                    now,
                    now,
                    "active",
                ),
            )
            self.conn.commit()
            return "new"

        # Check for meaningful field changes
        changed = any([
            existing["url"] != cam.get("url"),
            existing["camera_name"] != cam.get("camera_name", ""),
            existing["camera_type"] != cam.get("camera_type", ""),
            existing["category"] != cam.get("category", "unknown"),
            existing["latitude"] != cam.get("latitude"),
            existing["longitude"] != cam.get("longitude"),
            existing["city"] != cam.get("city", ""),
            existing["region"] != cam.get("region", ""),
            existing["state"] != cam.get("state", ""),
        ])

        self.conn.execute(
            """UPDATE cameras
               SET url=?, camera_name=?, camera_type=?, category=?,
                   latitude=?, longitude=?, country=?, country_code=?,
                   state=?, city=?, region=?, extra=?, last_seen=?, status='active'
               WHERE source=? AND camera_id=?""",
            (
                cam.get("url"),
                cam.get("camera_name", ""),
                cam.get("camera_type", ""),
                cam.get("category", "unknown"),
                cam.get("latitude"),
                cam.get("longitude"),
                cam.get("country", ""),
                cam.get("country_code", ""),
                cam.get("state", ""),
                cam.get("city", ""),
                cam.get("region", ""),
                extra,
                now,
                cam["source"],
                cam["camera_id"],
            ),
        )
        self.conn.commit()
        return "updated" if changed else "unchanged"

    def mark_offline(self, source: str, country_code: str, seen_ids: set[str]):
        """Mark cameras not seen in the current scan as offline."""
        known = self.known_camera_ids(source, country_code)
        missing = known - seen_ids
        if missing:
            placeholders = ",".join("?" * len(missing))
            self.conn.execute(
                f"UPDATE cameras SET status='offline' WHERE source=? AND camera_id IN ({placeholders})",
                (source, *missing),
            )
            self.conn.commit()

    def query(
        self,
        source: str = "",
        categories: list[str] | None = None,
        country_code: str = "",
        status: str = "",
        search: str = "",
        date_from: str = "",
        date_to: str = "",
        limit: int = 5000,
        offset: int = 0,
    ) -> list[dict]:
        clauses, params = [], []

        if source:
            clauses.append("source=?")
            params.append(source)
        if categories:
            placeholders = ",".join("?" * len(categories))
            clauses.append(f"category IN ({placeholders})")
            params.extend(categories)
        if country_code:
            clauses.append("country_code=?")
            params.append(country_code)
        if status:
            clauses.append("status=?")
            params.append(status)
        if search:
            clauses.append("(camera_name LIKE ? OR city LIKE ? OR url LIKE ?)")
            params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])
        if date_from:
            clauses.append("last_seen >= ?")
            params.append(date_from)
        if date_to:
            clauses.append("last_seen <= ?")
            params.append(date_to)

        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        rows = self.conn.execute(
            f"SELECT * FROM cameras {where} ORDER BY last_seen DESC LIMIT ? OFFSET ?",
            (*params, limit, offset),
        ).fetchall()
        return [dict(r) for r in rows]

    def count(self, **kwargs) -> int:
        kwargs.pop("limit", None)
        kwargs.pop("offset", None)
        clauses, params = [], []
        if kwargs.get("source"):
            clauses.append("source=?"); params.append(kwargs["source"])
        if kwargs.get("categories"):
            placeholders = ",".join("?" * len(kwargs["categories"]))
            clauses.append(f"category IN ({placeholders})")
            params.extend(kwargs["categories"])
        if kwargs.get("country_code"):
            clauses.append("country_code=?"); params.append(kwargs["country_code"])
        if kwargs.get("status"):
            clauses.append("status=?"); params.append(kwargs["status"])
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        row = self.conn.execute(f"SELECT COUNT(*) FROM cameras {where}", params).fetchone()
        return row[0]

    def export_json(self, path: str, **query_kwargs) -> int:
        query_kwargs["limit"] = 999999
        rows = self.query(**query_kwargs)
        with open(path, "w") as f:
            json.dump(rows, f, indent=2)
        return len(rows)

    def sources(self) -> list[str]:
        rows = self.conn.execute("SELECT DISTINCT source FROM cameras ORDER BY source").fetchall()
        return [r[0] for r in rows]

    def country_codes(self, source: str = "") -> list[str]:
        if source:
            rows = self.conn.execute(
                "SELECT DISTINCT country_code FROM cameras WHERE source=? ORDER BY country_code",
                (source,),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT DISTINCT country_code FROM cameras ORDER BY country_code"
            ).fetchall()
        return [r[0] for r in rows if r[0]]
