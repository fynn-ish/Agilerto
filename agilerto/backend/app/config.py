"""Settings for live-data ingestion. Edit AREAS to match the places your group covers."""
import os

# Places whose weather is fetched on every refresh. The dashboard shows the nearest one
# (within WEATHER_MAX_KM) to the user. Keep this list in sync with PLACES in frontend/src/constants.js.
AREAS = [
    {"name": "Lipa City",       "lat": 13.9411, "lng": 121.1631, "province": "Batangas"},
    {"name": "Tanauan City",    "lat": 14.0859, "lng": 121.1497, "province": "Batangas"},
    {"name": "Santo Tomas",     "lat": 14.1078, "lng": 121.1414, "province": "Batangas"},
    {"name": "Batangas City",   "lat": 13.7565, "lng": 121.0583, "province": "Batangas"},
    {"name": "Tagaytay City",   "lat": 14.1153, "lng": 120.9621, "province": "Cavite"},
    {"name": "Calamba City",    "lat": 14.2117, "lng": 121.1653, "province": "Laguna"},
    {"name": "Santa Rosa City", "lat": 14.3122, "lng": 121.1114, "province": "Laguna"},
    {"name": "San Pablo City",  "lat": 14.0683, "lng": 121.3253, "province": "Laguna"},
    {"name": "Lucena City",     "lat": 13.9373, "lng": 121.6171, "province": "Quezon"},
    {"name": "Imus City",       "lat": 14.4297, "lng": 120.9367, "province": "Cavite"},
]
WEATHER_MAX_KM = 30            # farther than this from every area = "no weather for this location"
WEATHER_KEEP_SNAPSHOTS = 24    # history kept per area

# Earthquakes: one request covers the whole Philippines; the dashboard filters by distance.
QUAKE_REGION = {"minlatitude": 4.0, "maxlatitude": 21.5, "minlongitude": 116.0, "maxlongitude": 127.5}
QUAKE_MIN_MAGNITUDE = 2.5
QUAKE_FETCH_DAYS = 7
QUAKE_RETENTION_DAYS = 30

# Scheduling
REFRESH_MINUTES = int(os.getenv("REFRESH_MINUTES", "15"))
SCHEDULER_ENABLED = os.getenv("DISABLE_SCHEDULER", "0") != "1"

# Data older than this is labeled "stale" in the UI (minutes)
STALE_MINUTES = {"weather": 180, "earthquakes": 120, "advisories": 180, "news": 720}

HTTP_TIMEOUT = 10
USER_AGENT = "DisasterInfoSystem/0.2 (student project)"

# ---------- AI assistant (Step 3) ----------
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")     # try qwen2.5:3b too; test Taglish on your laptop
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "180"))    # seconds; the first answer also loads the model
OLLAMA_NUM_CTX = 4096
OLLAMA_MAX_TOKENS = 350
MAX_CONCURRENT_LLM = 1          # one answer at a time keeps a small laptop responsive

MAX_SOURCES = 8                 # keep the context short so small models stay accurate
SOURCE_MAX_CHARS = 700
FACILITY_RADIUS_KM = 15
QUAKE_RADIUS_KM = 300
QUESTION_MAX_CHARS = 500


# ---------- advisories and news (Step 4) ----------
# GDACS: automated alerts from the UN and European Commission (CC BY 4.0, credit required).
# They are NOT official Philippine warnings, and the app says so.
GDACS_URL = os.getenv("GDACS_URL", "https://www.gdacs.org/xml/rss.xml")
GDACS_TYPES = ("TC", "FL", "VO")                  # tropical cyclone, flood, volcano (earthquakes come from USGS)
GDACS_NEAR_BOX = (4.0, 21.5, 116.0, 127.5)        # min_lat, max_lat, min_lng, max_lng: events here count as "near the Philippines"

# PAGASA has no data feed. This page says either that no cyclone is active, or links the bulletin PDF.
PAGASA_BULLETIN_URL = os.getenv("PAGASA_BULLETIN_URL", "https://www.pagasa.dost.gov.ph/tropical-cyclone/severe-weather-bulletin")

# Advisories are shown with their age while offline, but dropped after this long without being confirmed.
ADVISORY_MAX_AGE_HOURS = 168

# Philippine news feeds (RSS). Each fails on its own. Some outlets block automated requests.
NEWS_FEEDS = [
    {"name": "Rappler",                  "url": "https://www.rappler.com/feed/"},
    {"name": "Manila Bulletin",          "url": "https://mb.com.ph/rss/articles"},
    {"name": "Philippine Daily Inquirer", "url": "https://www.inquirer.net/fullfeed"},
]
# GDELT: free news index, no key. It allows about one request every 5 seconds, shared by everyone.
GDELT_URL = os.getenv("GDELT_URL", "https://api.gdeltproject.org/api/v2/doc/doc")
GDELT_QUERY = ("(typhoon OR earthquake OR flood OR landslide OR volcano OR Taal OR PAGASA OR PHIVOLCS OR NDRRMC) "
               "(Philippines OR Batangas OR Calabarzon OR Laguna OR Cavite)")
GDELT_TIMESPAN = "3d"
GDELT_MAX_RECORDS = 75

NEWS_KEEP_DAYS = 14             # older headlines are deleted after a successful refresh
NEWS_SHOW_DAYS = 3              # the dashboard and assistant use headlines from the last few days
SOURCE_MIN_INTERVAL_MINUTES = {"news": 30}   # news is checked less often than weather
MAX_RESPONSE_BYTES = 5_000_000

# ---------- offline map tiles (Step 5) ----------
# A PMTiles file (Protomaps basemap, version 4 or newer) in backend/data/tiles/. See `python get_tiles.py`.
TILES_DIR = os.getenv("TILES_DIR", "")                    # default: backend/data/tiles
TILES_FILE = os.getenv("TILES_FILE", "calabarzon.pmtiles")

# ---------- guardrails (Step 5) ----------
# Shown only when someone writes that they may hurt themselves. Kept here (not in the hotline CSV) so updating the
# data files never overwrites them. Source: DOH / National Center for Mental Health (NCMH) Crisis Hotline, 24/7,
# as published by DOH and repeated in a 2025 CHR statement and a Dec 2025 DOH-sourced news report.
# NUMBERS CAN CHANGE: confirm them at doh.gov.ph before any real deployment.
CRISIS_LINES = [
    {"agency": "National Emergency Hotline", "number": "911"},
    {"agency": "NCMH Crisis Hotline (landline)", "number": "1553"},
    {"agency": "NCMH Crisis Hotline (mobile)", "number": "0917 899 8727"},
    {"agency": "NCMH Crisis Hotline (mobile 2)", "number": "0966 351 4518"},
]
CHAT_RATE_LIMIT = int(os.getenv("CHAT_RATE_LIMIT", "20"))      # questions per client per window
CHAT_RATE_WINDOW_SECONDS = int(os.getenv("CHAT_RATE_WINDOW_SECONDS", "60"))

# Every data source address can be replaced with an environment variable. This is how you "block one API" while
# testing: for example  $env:GDACS_URL="http://127.0.0.1:9/"  makes GDACS unreachable and leaves everything else alone.
OPEN_METEO_URL = os.getenv("OPEN_METEO_URL", "https://api.open-meteo.com/v1/forecast")
USGS_URL = os.getenv("USGS_URL", "https://earthquake.usgs.gov/fdsnws/event/1/query")
