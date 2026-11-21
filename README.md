# Agilerto

**An offline-first disaster information assistant for Batangas and Calabarzon, Philippines.**

Agilerto shows the nearest hospitals, evacuation centers, fire stations, and police stations, plus weather, recent earthquakes, and emergency hotlines. A local AI assistant answers questions in English, Tagalog, or Taglish using **only saved data**, and cites every source. Everything is stored locally and labeled with its source and age, so it keeps working when the internet goes down.

> **Safety notice:** Agilerto is an information tool. It does **not** predict disasters or tell anyone whether to evacuate. In an emergency, call **911** and follow your local DRRMO, NDRRMC, PAGASA, and PHIVOLCS.

## Features

- **Offline-first:** the map, hotlines, safety guides, and AI all run from local SQLite and Ollama.
- **Honest about freshness:** every card shows its source and fetch time. Old data is labeled stale, and an Online/Offline badge shows the sync state.
- **Cited answers:** the assistant uses only retrieved records, shows numbered citations, and checks every answer in code before showing it.
- **Safety guardrails:** emergencies get hotlines and the nearest help immediately. Evacuation and prediction questions are refused politely.
- **Phone-friendly:** one server can serve the API and the app to phones over WiFi.

## Status

| Step | Scope | Status |
|---|---|---|
| 0 to 1 | Schema, seed data, facilities API, offline map | Done |
| 2 | Weather and earthquake ingestion | Done |
| 3 | AI chat with citations, guardrails, status badge | Done |
| 4 | News and advisory ingestion | Planned |
| 5 | Offline map tiles (PMTiles) | Planned |
| 6 | Packaging and deployment | Planned |

## Quick start

Requires Python 3.11+, Node.js 20.19+, and [Ollama](https://ollama.com/download).

```bash
# Terminal 1: backend
cd agilerto/backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python seed.py                     # load saved data
python refresh.py                  # fetch weather and quakes (needs internet)
python -m uvicorn app.main:app --port 8000

# Terminal 2: frontend
cd agilerto/frontend
npm install
npm run dev                        # http://localhost:5173

# One time: the local AI
ollama pull llama3.2:3b
```

For a single-server setup, run `npm run build` in `frontend`, then start uvicorn with `--host 0.0.0.0`. Phones on the same WiFi can open `http://<computer-ip>:8000`.

## How it works

1. `seed.py` loads facilities, hotlines, and safety guides from CSV into SQLite (the offline backbone).
2. While online, a scheduler fetches weather (Open-Meteo) and earthquakes (USGS) every 15 minutes. On failure, old data is kept.
3. The API reads only from SQLite, so every endpoint works offline.
4. For chat, plain-code safety checks run first, then retrieval, then the local AI, then an answer check. If the check fails or Ollama is down, the saved records are shown instead.

## Project structure

```
agilerto/
├── backend/
│   ├── app/            FastAPI app: routes, ingest, rag (guardrails, retrieval, llm, validate)
│   ├── data/           facilities.csv, emergency_numbers.csv, safety_guides.csv
│   ├── tests/          test_ingest.py, test_rag.py
│   ├── schema.sql
│   ├── seed.py  import_osm.py  refresh.py  eval_chat.py
└── frontend/           React + Tailwind + Leaflet (Vite)
```

## API

| Endpoint | Description |
|---|---|
| `GET /api/dashboard?lat=&lng=` | Nearest weather, nearby quakes, freshness status |
| `GET /api/facilities?lat=&lng=&radius_km=&type=` | Facilities nearest-first |
| `GET /api/emergency-numbers` | Hotlines |
| `GET /api/safety-guides?hazard=` | Safety guides |
| `POST /api/chat` | Ask the assistant: `{question, lat, lng}` |
| `GET /api/status` | Online state and last sync per source |
| `GET /api/ai/status` | Whether Ollama and the model are ready |

Interactive docs are at `/docs`.

## Configuration

Settings are in `backend/app/config.py`. The most useful environment variables:

| Variable | Default | Purpose |
|---|---|---|
| `OLLAMA_MODEL` | `llama3.2:3b` | Model to use (try `qwen2.5:3b`) |
| `REFRESH_MINUTES` | `15` | Time between refreshes |
| `DISASTER_DB` | `backend/data/disaster.db` | SQLite file path |

## Replace the sample data

The bundled CSV rows are **placeholders** marked `verified=0`. Before real use:

1. Run `python import_osm.py --replace-samples` for real facilities.
2. Add the official evacuation center list from your MDRRMO to `data/facilities.csv`.
3. Confirm every hotline and safety guide against official sources.
4. Set `verified=1` only after checking, then run `python seed.py`.

## Testing

```bash
cd agilerto/backend
python -m unittest tests.test_ingest tests.test_rag -v   # no internet or Ollama needed
python eval_chat.py                                      # tries your real model on 18 questions
```

## Troubleshooting

| Problem | Fix |
|---|---|
| `uvicorn` not recognized or blocked | Activate the venv, or run `python -m uvicorn ...` |
| Badge says **AI not ready** | Start Ollama and check `ollama list` |
| "No information" for weather or quakes | Run `python refresh.py` while online |
| GPS button does nothing | GPS needs HTTPS or localhost. Use the city picker. |
| Map background is grey | Tiles need internet until offline tiles are added |

## Known limitations

- Sample facility and hotline data is unverified.
- Each question is answered alone, with no conversation memory.
- No news or advisories yet.
- Weather is model data, not an official PAGASA forecast.
- Answers can be slow on laptops without a GPU.

## Contributing

Use [Conventional Commits](https://www.conventionalcommits.org/) (`feat(backend): ...`). Run the tests and `npm run build` before pushing. Don't commit `.venv/`, `node_modules/`, `dist/`, or `disaster.db`. Mark data `verified=1` only after checking an official source. Keep the scope: no predictions and no evacuation advice.

## Acknowledgments

Map data &copy; [OpenStreetMap](https://www.openstreetmap.org/copyright) contributors. Weather from [Open-Meteo](https://open-meteo.com/). Earthquakes from [USGS](https://earthquake.usgs.gov/). Local models via [Ollama](https://ollama.com/).