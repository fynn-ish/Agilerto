-- ============================================================
-- Disaster Info System: SQLite schema
-- STATIC tables  = permanent data, the offline backbone
-- DYNAMIC tables = cached online data, always carry fetched_at
-- ============================================================

-- ---------- STATIC ----------
CREATE TABLE IF NOT EXISTS facilities (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    ref       TEXT NOT NULL UNIQUE,            -- stable id, e.g. 'seed:lipa-hospital-1' or 'osm:node/123'
    type      TEXT NOT NULL CHECK (type IN
              ('hospital','evacuation_center','fire_station','police_station')),
    name      TEXT NOT NULL,
    lat       REAL NOT NULL,
    lng       REAL NOT NULL,
    address   TEXT,
    phone     TEXT,
    capacity  INTEGER,                         -- evacuation centers: max people
    source    TEXT NOT NULL,                   -- where this record came from
    verified  INTEGER NOT NULL DEFAULT 0,      -- 1 = checked against an official list
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
CREATE INDEX IF NOT EXISTS idx_facilities_geo  ON facilities (lat, lng);
CREATE INDEX IF NOT EXISTS idx_facilities_type ON facilities (type);

CREATE TABLE IF NOT EXISTS emergency_numbers (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    ref      TEXT NOT NULL UNIQUE,
    agency   TEXT NOT NULL,
    number   TEXT NOT NULL,
    area     TEXT NOT NULL DEFAULT 'National',
    notes    TEXT,
    priority INTEGER NOT NULL DEFAULT 100,     -- lower = shown first
    source   TEXT NOT NULL,
    verified INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS safety_guides (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    ref    TEXT NOT NULL UNIQUE,
    hazard TEXT NOT NULL,                      -- earthquake, typhoon, flood, fire, landslide...
    phase  TEXT NOT NULL DEFAULT 'during',     -- before | during | after
    title  TEXT NOT NULL,
    body   TEXT NOT NULL,
    source TEXT NOT NULL,
    verified INTEGER NOT NULL DEFAULT 0
);

-- ---------- DYNAMIC (filled by ingestion in Steps 2 and 4) ----------
CREATE TABLE IF NOT EXISTS weather (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    lat          REAL NOT NULL,
    lng          REAL NOT NULL,
    payload_json TEXT NOT NULL,
    fetched_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS earthquakes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ext_id      TEXT UNIQUE,                   -- source event id, prevents duplicates
    magnitude   REAL,
    depth_km    REAL,
    lat         REAL NOT NULL,
    lng         REAL NOT NULL,
    place       TEXT,
    occurred_at TEXT NOT NULL,
    source      TEXT NOT NULL,
    url         TEXT,
    fetched_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS advisories (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    ext_id     TEXT UNIQUE,
    source     TEXT NOT NULL,
    title      TEXT NOT NULL,
    body       TEXT,
    severity   TEXT,
    area       TEXT,
    issued_at  TEXT,
    expires_at TEXT,
    url        TEXT,
    fetched_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS news (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    url          TEXT UNIQUE,
    title        TEXT NOT NULL,
    summary      TEXT,
    source       TEXT,
    published_at TEXT,
    fetched_at   TEXT NOT NULL
);

-- ---------- SYNC STATUS ----------
CREATE TABLE IF NOT EXISTS sync_log (
    source          TEXT PRIMARY KEY,          -- 'weather', 'earthquakes', ...
    last_success_at TEXT,
    last_attempt_at TEXT,
    last_error      TEXT
);

-- ---------- RAG (used from Step 3) ----------
CREATE TABLE IF NOT EXISTS chunks (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    kind       TEXT NOT NULL,                  -- facility | hotline | guide | weather | quake | advisory | news
    ref_id     TEXT NOT NULL,                  -- ref of the source record
    title      TEXT,
    text       TEXT NOT NULL,
    lat        REAL,
    lng        REAL,
    source     TEXT,
    fetched_at TEXT,                           -- NULL for static content
    UNIQUE (kind, ref_id)
);
CREATE INDEX IF NOT EXISTS idx_chunks_kind ON chunks (kind);

-- Full-text index kept in sync with chunks by triggers
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    title, text, content='chunks', content_rowid='id', tokenize='unicode61 remove_diacritics 2'
);
CREATE TRIGGER IF NOT EXISTS chunks_ai AFTER INSERT ON chunks BEGIN
    INSERT INTO chunks_fts(rowid, title, text) VALUES (new.id, new.title, new.text);
END;
CREATE TRIGGER IF NOT EXISTS chunks_ad AFTER DELETE ON chunks BEGIN
    INSERT INTO chunks_fts(chunks_fts, rowid, title, text) VALUES ('delete', old.id, old.title, old.text);
END;
CREATE TRIGGER IF NOT EXISTS chunks_au AFTER UPDATE ON chunks BEGIN
    INSERT INTO chunks_fts(chunks_fts, rowid, title, text) VALUES ('delete', old.id, old.title, old.text);
    INSERT INTO chunks_fts(rowid, title, text) VALUES (new.id, new.title, new.text);
END;

-- ---------- ASSISTANT LOG (Step 3) ----------
-- Only problem cases are stored (no answer, AI down, failed citation check) so the team can see
-- data gaps. Refusals and emergencies are logged without the question text. No coordinates stored.
CREATE TABLE IF NOT EXISTS chat_log (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at   TEXT NOT NULL,
    outcome      TEXT NOT NULL,
    question     TEXT,
    source_count INTEGER,
    elapsed_ms   INTEGER,
    note         TEXT
);
