"""Settings for live-data ingestion. Edit AREAS to match the places your group covers."""
import os

# Places whose weather is fetched on every refresh. The dashboard shows the nearest one
# (within WEATHER_MAX_KM) to the user. Keep this list in sync with PLACES in frontend/src/constants.js.
AREAS = [
    {"name": "Lipa City",       "lat": 13.9411, "lng": 121.1631},
    {"name": "Tanauan City",    "lat": 14.0859, "lng": 121.1497},
    {"name": "Santo Tomas",     "lat": 14.1078, "lng": 121.1414},
    {"name": "Batangas City",   "lat": 13.7565, "lng": 121.0583},
    {"name": "Tagaytay City",   "lat": 14.1153, "lng": 120.9621},
    {"name": "Calamba City",    "lat": 14.2117, "lng": 121.1653},
    {"name": "Santa Rosa City", "lat": 14.3122, "lng": 121.1114},
    {"name": "San Pablo City",  "lat": 14.0683, "lng": 121.3253},
    {"name": "Lucena City",     "lat": 13.9373, "lng": 121.6171},
    {"name": "Imus City",       "lat": 14.4297, "lng": 120.9367},
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
STALE_MINUTES = {"weather": 180, "earthquakes": 120}

HTTP_TIMEOUT = 10
USER_AGENT = "DisasterInfoSystem/0.2 (student project)"
