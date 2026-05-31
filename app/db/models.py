import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS cameras (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    source        TEXT NOT NULL,
    camera_id     TEXT NOT NULL,
    url           TEXT,
    camera_name   TEXT,
    camera_type   TEXT,
    category      TEXT DEFAULT 'unknown',
    latitude      REAL,
    longitude     REAL,
    country       TEXT,
    country_code  TEXT,
    state         TEXT,
    city          TEXT,
    region        TEXT,
    extra         TEXT,
    first_seen    TEXT,
    last_seen     TEXT,
    status        TEXT DEFAULT 'active',
    UNIQUE(source, camera_id)
);

CREATE TABLE IF NOT EXISTS scan_runs (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    source           TEXT NOT NULL,
    filter           TEXT,
    started_at       TEXT,
    finished_at      TEXT,
    status           TEXT DEFAULT 'running',
    cameras_found    INTEGER DEFAULT 0,
    cameras_new      INTEGER DEFAULT 0,
    cameras_updated  INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_cameras_source       ON cameras(source);
CREATE INDEX IF NOT EXISTS idx_cameras_category     ON cameras(category);
CREATE INDEX IF NOT EXISTS idx_cameras_country_code ON cameras(country_code);
CREATE INDEX IF NOT EXISTS idx_cameras_status       ON cameras(status);
CREATE INDEX IF NOT EXISTS idx_cameras_last_seen    ON cameras(last_seen);
"""


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()
