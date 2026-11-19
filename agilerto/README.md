# Agilerto

**An offline-first disaster information assistant for Batangas and Calabarzon, Philippines.**

Agilerto shows people the nearest hospitals, evacuation centers, fire stations, and police stations, along with current weather, recent earthquakes, and emergency hotlines. It keeps working when the internet goes down, because everything it shows is saved locally and clearly labeled with its source and the time it was last updated.

An AI chat assistant that answers questions using *only* the saved data (with citations) is planned. See the [roadmap](#roadmap).

> **Safety notice:** Agilerto is an information tool. It does **not** predict disasters and does **not** tell anyone whether or when to evacuate. In an emergency, call **911** and follow instructions from your local DRRMO, NDRRMC, PAGASA, and PHIVOLCS.

---

## Contents

- [Features](#features)
- [Project status](#project-status)
- [How it works](#how-it-works)
- [Tech stack](#tech-stack)
- [Project structure](#project-structure)
- [Getting started](#getting-started)
- [Configuration](#configuration)
- [API reference](#api-reference)
- [Data and sources](#data-and-sources)
- [Replacing the sample data](#replacing-the-sample-data)
- [Testing](#testing)
- [Known limitations](#known-limitations)
- [Roadmap](#roadmap)

---

## Features

**Works offline**
- Facility map, facility list, type filters, and hotlines all run from the local SQLite database.
- The last result is also cached in the browser, so the page still shows something if the connection to the backend drops.
- When the internet is down, the background refresh is skipped and old data is kept, never deleted.

**Honest about freshness**
- Every weather and earthquake card shows its source and when it was fetched.
- Data past a freshness limit is labeled **stale** (weather after 3 hours, earthquakes after 2 hours).
- Unverified facility and hotline records are flagged in the UI.

**Location handling**
- Browser GPS when available, with a city picker and tap-the-map as fallbacks.
- Nearest-first results with distances, using a bounding-box filter followed by exact haversine distance.

**Built for phones on a local network**
- One server can serve both the API and the built React app, so a laptop, mini-PC, or Raspberry Pi can act as a local hub that phones reach over WiFi.
- Accessible design: facility types are identified by color, letter, and shape together, in a high-legibility font (Atkinson Hyperlegible).

## Project status

| Step | Scope | Status |
|---|---|---|
| 0 | Project setup, SQLite schema, static data seeding | Done |
| 1 | Facilities API and React map (works offline) | Done |
| 2 | Weather and earthquake ingestion, scheduler, dashboard, freshness labels | Done |
| 3 | RAG retrieval and Ollama chat with citations | Planned |
| 4 | News and advisory ingestion | Planned |
| 5 | Offline map tiles (PMTiles), guardrails, full offline testing | Planned |
| 6 | Packaging and deployment on the target device | Planned |

## How it works

```
 Open-Meteo ─┐                                        ┌─ GET /api/dashboard ─┐
 USGS ───────┼─► ingest (every 15 min, online only) ─►│  SQLite database     │─► React app
 OSM (once) ─┘        │                               │  (static + dynamic)  │   (map, cards,
                      └─ on failure: keep old data ──►└─ GET /api/facilities ┘    hotlines)
                         record error in sync_log
```

1. **Static data** (facilities, hotlines, safety guides) is loaded from CSV files by `seed.py`. This is the offline backbone.
2. **Live data** (weather, earthquakes) is fetched on a schedule while online. Each record is stored with a `fetched_at` timestamp, and each source's last success and last error are recorded in `sync_log`.
3. **The API reads only from SQLite**, never from the internet, so every endpoint works offline and returns whatever was last saved.
4. **Text chunks** are built from each record and indexed with SQLite FTS5. This is the foundation for the planned chat assistant.

## Tech stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11+, FastAPI, Uvicorn, httpx, SQLite (with FTS5) |
| Frontend | React 19, Vite, Tailwind CSS 4, Leaflet |
| Live data | Open-Meteo (weather), USGS (earthquakes), OpenStreetMap Overpass (facility import) |
| Planned | Ollama (local LLM), PMTiles (offline map tiles) |

## Project structure

```
Agilerto/
├── README.md
└── agilerto/
    ├── backend/
    │   ├── schema.sql            all tables (static, dynamic, chunks + FTS5, sync_log)
    │   ├── seed.py               loads data/*.csv into SQLite and builds chunks
    │   ├── import_osm.py         imports real facilities from OpenStreetMap (online, run once)
    │   ├── refresh.py            runs one data refresh by hand
    │   ├── requirements.txt
    │   ├── data/                 facilities.csv, emergency_numbers.csv, safety_guides.csv
    │   ├── tests/                ingestion and API tests (no internet needed)
    │   └── app/
    │       ├── main.py           FastAPI app, scheduler startup, serves built frontend
    │       ├── config.py         areas, thresholds, refresh interval
    │       ├── db.py             SQLite connection and schema init
    │       ├── geo.py            bounding box and haversine distance
    │       ├── connectivity.py   online/offline detection
    │       ├── scheduler.py      background refresh loop
    │       ├── chunks.py         turns records into searchable text chunks
    │       ├── ingest/           one module per source (weather, earthquakes)
    │       └── routes/           dashboard, facilities, reference
    └── frontend/
        ├── index.html
        ├── vite.config.js        dev proxy: /api goes to the backend on port 8000
        └── src/
            ├── App.jsx
            ├── api.js            API client with localStorage fallback
            ├── constants.js      facility types, city list, tile settings
            ├── hooks/useDashboard.js
            └── components/       map, facility list, weather/quake cards, hotline bar, filters
```

## Getting started

### Prerequisites

- Python 3.11 or newer
- Node.js 18 or newer
- Internet access for the first run (to install packages and fetch live data)

### 1. Backend

```bash
cd agilerto/backend
python -m venv .venv

# Activate the virtual environment:
source .venv/bin/activate          # macOS / Linux / Git Bash
.venv\Scripts\Activate.ps1         # Windows PowerShell
.venv\Scripts\activate.bat         # Windows cmd

pip install -r requirements.txt
python seed.py                     # creates data/disaster.db from the CSV files
uvicorn app.main:app --reload --port 8000
```

The first live-data refresh runs a couple of seconds after the server starts. To trigger one manually, run `python refresh.py`.

### 2. Frontend (development)

In a second terminal:

```bash
cd agilerto/frontend
npm install
npm run dev                        # http://localhost:5173
```

The Vite dev server forwards `/api` requests to the backend and is reachable from phones on the same network.

### 3. Single server (like deployment)

Build the frontend once, and FastAPI serves it from the same port:

```bash
cd agilerto/frontend
npm install && npm run build

cd ../backend
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Open `http://localhost:8000`. Phones on the same WiFi can use `http://<this-computer-ip>:8000`. Interactive API docs are at `/docs`.

## Configuration

Edit `agilerto/backend/app/config.py`, or set environment variables where noted.

| Setting | Default | Purpose |
|---|---|---|
| `AREAS` | 10 Calabarzon cities | Places whose weather is fetched. Keep in sync with `PLACES` in `frontend/src/constants.js`. |
| `WEATHER_MAX_KM` | `30` | Farther than this from every area means "no weather for this location". |
| `QUAKE_REGION` | Philippines bounding box | Region requested from USGS. |
| `QUAKE_MIN_MAGNITUDE` | `2.5` | Smallest quake stored. |
| `QUAKE_RETENTION_DAYS` | `30` | How long quake records are kept. |
| `STALE_MINUTES` | weather 180, quakes 120 | Age after which data is labeled stale. |
| `REFRESH_MINUTES` (env) | `15` | Time between automatic refreshes. |
| `DISABLE_SCHEDULER` (env) | `0` | Set to `1` to turn off background refresh. |
| `DISASTER_DB` (env) | `backend/data/disaster.db` | Path to the SQLite file. |
| `VITE_TILE_URL` (env, frontend) | OpenStreetMap tiles | Map tile source. Will point to local tiles once offline tiles are added. |

## API reference

All endpoints are under `/api` and read from SQLite, so they work offline.

| Endpoint | Description |
|---|---|
| `GET /api/dashboard?lat=&lng=&quake_radius_km=300&quake_days=7&min_magnitude=2.5` | Nearest weather, nearby earthquakes, and per-source freshness status. |
| `GET /api/facilities?lat=&lng=&radius_km=10&type=hospital,fire_station&limit=100` | Facilities nearest-first, with `distance_km`. Types: `hospital`, `evacuation_center`, `fire_station`, `police_station`. |
| `GET /api/emergency-numbers` | Hotlines in priority order. |
| `GET /api/safety-guides?hazard=earthquake` | Safety guides, optionally filtered by hazard. |
| `GET /api/status` | Online state, refresh interval, and last sync result per source. |
| `GET /api/health` | Row counts for each table. |
| `POST /api/refresh` | Manual refresh. Limited to once every 30 seconds. |

## Data and sources

| Data | Source | Notes |
|---|---|---|
| Weather | [Open-Meteo](https://open-meteo.com/) | Forecast model data, **not** an official PAGASA warning. |
| Earthquakes | [USGS](https://earthquake.usgs.gov/) | USGS may list small local quakes late or not at all. PHIVOLCS is the official Philippine source and can be added as a second source. |
| Facilities | `data/facilities.csv`, optionally enriched from [OpenStreetMap](https://www.openstreetmap.org/) | Sample rows are placeholders until replaced. See below. |
| Hotlines and safety guides | `data/*.csv` | Each row has a `source` and a `verified` flag. |

## Replacing the sample data

The bundled CSV rows are **placeholders** with approximate coordinates, all marked `verified=0`. Replace them before any real use.

1. **Facilities from OpenStreetMap** (needs internet once):
   ```bash
   python import_osm.py --replace-samples
   python import_osm.py --bbox south,west,north,east    # a different area
   ```
2. **Evacuation centers:** OSM coverage is patchy. Get the official list from your MDRRMO, add it to `data/facilities.csv` with `verified=1`, then run `python seed.py`.
3. **Hotlines:** confirm every number and add your local MDRRMO line in `data/emergency_numbers.csv`.
4. **Safety guides:** compare the text with current NDRRMC, PHIVOLCS, PAGASA, Red Cross, and BFP material, then set `verified=1`.

`seed.py` is safe to re-run. It upserts by the `ref` column and rebuilds the text chunks.

## Testing

Tests use fake API responses, so no internet is needed. From `agilerto/backend`:

```bash
python -m unittest tests.test_ingest -v
```

They cover successful refreshes, failures that keep old data, partial failures, offline skipping, duplicate prevention, history limits, stale flags, and dashboard behavior with and without data.

For a manual offline check: load the app, disconnect the internet, and reload. Facilities, hotlines, and the last saved weather and earthquake data should still appear.

## Known limitations

- **The map background needs internet** until offline tiles are added. Markers, list, hotlines, and filters already work offline.
- **"Use my location" (GPS) only works over HTTPS or on localhost.** Browsers block it on a plain `http://192.168.x.x` address, so the city picker and tap-the-map fallbacks exist for that case.
- **Sample facility and hotline data is unverified.** Do not rely on it in a real emergency.
- **Weather is model-based**, not an official PAGASA forecast or warning.
- **Earthquake coverage depends on USGS**, which can miss or delay small local events.

## Roadmap

- [ ] **RAG chat assistant:** FTS5 retrieval combined with distance filtering and recency, answered by a local Ollama model (such as `qwen2.5:3b`), with citations and "as of" times
- [ ] **Guardrails:** refuse prediction and evacuation-decision questions, warn on stale data, answer "no information available" when nothing is retrieved
- [ ] **Taglish prompts** and a model test with Tagalog and Taglish questions to choose the best model for the target hardware
- [ ] **News and advisory ingestion** (ReliefWeb, GDELT, PAGASA, NDRRMC, LGU pages) with each source failing independently
- [ ] **PHIVOLCS** as a second earthquake source
- [ ] **Offline map tiles** (PMTiles extract of the target area, served locally)
- [ ] **Online/offline status badge** and persistent disclaimer in the UI
- [ ] **Packaging and a setup script** for the target device

## Acknowledgments

Map data &copy; [OpenStreetMap](https://www.openstreetmap.org/copyright) contributors. Weather from Open-Meteo. Earthquake data from the U.S. Geological Survey.