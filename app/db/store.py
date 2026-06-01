import json
import os
import sqlite3
from datetime import datetime, timezone
from app.db.models import init_db
from app.core.schema import infer_category

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
        Skips records with no URL — a URL is required for a camera to be useful.
        """
        if not cam.get("url"):
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

    def insecam_unenriched_ids(self, country_code: str = "") -> list[str]:
        """Return Insecam camera_ids that are missing lat/lon (not yet enriched)."""
        if country_code:
            rows = self.conn.execute(
                "SELECT camera_id FROM cameras WHERE source='Insecam' AND country_code=? "
                "AND (latitude IS NULL OR longitude IS NULL) ORDER BY camera_id",
                (country_code,),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT camera_id FROM cameras WHERE source='Insecam' "
                "AND (latitude IS NULL OR longitude IS NULL) ORDER BY camera_id",
            ).fetchall()
        return [r["camera_id"] for r in rows]

    def enrich_camera(self, source: str, camera_id: str, fields: dict) -> None:
        """Patch specific fields on an existing camera row. Only updates non-None values."""
        allowed = {
            "latitude", "longitude", "city", "region", "state",
            "country", "country_code", "camera_type", "camera_name",
        }
        updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
        if not updates:
            return
        # Re-infer category when camera_type is updated; Insecam defaults to security
        if "camera_type" in updates:
            cam_name = updates.get("camera_name", "")
            inferred = infer_category([updates["camera_type"], cam_name])
            if inferred == "unknown" and source == "Insecam":
                inferred = "security"
            updates["category"] = inferred
        set_clause = ", ".join(f"{k}=?" for k in updates)
        self.conn.execute(
            f"UPDATE cameras SET {set_clause}, last_seen=? WHERE source=? AND camera_id=?",
            (*updates.values(), _now(), source, camera_id),
        )
        self.conn.commit()

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

    def recategorize_all(self) -> int:
        """Re-run infer_category on every row and update category where it changed."""
        rows = self.conn.execute(
            "SELECT source, camera_id, camera_type, camera_name, category FROM cameras"
        ).fetchall()
        updated = 0
        for row in rows:
            new_cat = infer_category([row["camera_type"] or "", row["camera_name"] or ""])
            if new_cat == "unknown" and row["source"] == "Insecam":
                new_cat = "security"
            if new_cat != row["category"]:
                self.conn.execute(
                    "UPDATE cameras SET category=? WHERE source=? AND camera_id=?",
                    (new_cat, row["source"], row["camera_id"]),
                )
                updated += 1
        if updated:
            self.conn.commit()
        return updated

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
