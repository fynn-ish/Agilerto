"""Ingestion tests using fake API responses (no internet needed).
Run from the backend folder:   python -m unittest tests.test_ingest -v
"""
import os
import tempfile
import unittest
from datetime import timedelta

# Must be set before the app modules are imported.
_tmp = tempfile.mkdtemp()
os.environ["DISASTER_DB"] = os.path.join(_tmp, "test.db")
os.environ["DISABLE_SCHEDULER"] = "1"

import httpx
from fastapi.testclient import TestClient

from app import config
from app.db import connect, init_db
from app.ingest import run_all
from app.ingest.weather import parse_forecast
from app.main import app
from app.timeutil import iso, utc_now

NOW = utc_now()


def openmeteo_json(temp=29.4):
    return {
        "latitude": 13.94, "longitude": 121.16, "timezone": "Asia/Manila", "utc_offset_seconds": 28800,
        "current": {"time": "2026-11-11T15:30", "temperature_2m": temp, "apparent_temperature": 33.1,
                    "relative_humidity_2m": 78, "precipitation": 0.4, "rain": 0.4, "weather_code": 80,
                    "cloud_cover": 70, "pressure_msl": 1009.2, "wind_speed_10m": 12.5,
                    "wind_direction_10m": 90, "wind_gusts_10m": 25.0},
        "daily": {"time": ["2026-11-11", "2026-11-12", "2026-11-13"], "weather_code": [80, 3, 95],
                  "temperature_2m_max": [31, 32, 30], "temperature_2m_min": [24, 24, 23],
                  "precipitation_sum": [4.2, 0.0, 18.5], "precipitation_probability_max": [60, 20, 85],
                  "wind_speed_10m_max": [15, 12, 30], "wind_gusts_10m_max": [30, 25, 55]},
    }


def usgs_json(mag=4.6):
    def feat(i, mag, lat, lng, mins_ago, typ="earthquake"):
        t = int((NOW - timedelta(minutes=mins_ago)).timestamp() * 1000)
        return {"id": f"us{i}", "properties": {"mag": mag, "place": f"{i} km N of Test, Philippines",
                "time": t, "type": typ, "url": f"https://example.org/{i}"},
                "geometry": {"type": "Point", "coordinates": [lng, lat, 10.0]}}
    return {"features": [
        feat(1, mag, 13.5, 121.0, 90),                    # near Lipa
        feat(2, 3.1, 14.2, 121.3, 600),                   # near Lipa, older
        feat(3, 5.0, 8.0, 126.0, 30),                     # Mindanao, far away
        feat(4, 2.9, 13.9, 121.1, 10, typ="quarry blast"),  # must be skipped
        {"id": "us5", "properties": {"mag": None, "time": 1, "type": "earthquake"},
         "geometry": {"coordinates": [121, 14, 5]}},      # no magnitude: skipped
    ]}


def make_client(fail_all=False, fail_lat=None, mag=4.6, temp=29.4):
    def handler(request: httpx.Request):
        if fail_all:
            return httpx.Response(500, text="server error")
        if "open-meteo" in request.url.host:
            if fail_lat is not None and abs(float(request.url.params["latitude"]) - fail_lat) < 1e-6:
                return httpx.Response(503, text="unavailable")
            return httpx.Response(200, json=openmeteo_json(temp))
        if "usgs" in request.url.host:
            return httpx.Response(200, json=usgs_json(mag))
        return httpx.Response(404)
    return httpx.Client(transport=httpx.MockTransport(handler))


def count(table):
    c = connect()
    try:
        return c.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    finally:
        c.close()


def sync(source):
    c = connect()
    try:
        r = c.execute("SELECT * FROM sync_log WHERE source=?", (source,)).fetchone()
        return dict(r) if r else None
    finally:
        c.close()


def reset():
    c = connect()
    for t in ("weather", "earthquakes", "sync_log"):
        c.execute(f"DELETE FROM {t}")
    c.execute("DELETE FROM chunks WHERE kind IN ('weather','quake')")
    c.commit()
    c.close()


class IngestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        reset()

    def test_parse_converts_local_time_to_utc(self):
        p = parse_forecast("Lipa City", openmeteo_json())
        self.assertEqual(p["observed_at"], "2026-11-11T07:30:00Z")      # 15:30 at UTC+8
        self.assertEqual(p["current"]["condition"], "Light rain showers")
        self.assertEqual(len(p["daily"]), 3)
        self.assertEqual(p["daily"][2]["condition"], "Thunderstorm")

    def test_parse_survives_missing_fields(self):
        p = parse_forecast("X", {"current": {"time": "2026-11-11T15:30"}, "utc_offset_seconds": 0})
        self.assertIsNone(p["current"]["temp_c"])
        self.assertEqual(p["daily"], [])

    def test_successful_refresh_saves_data_with_timestamps(self):
        r = run_all(online_check=lambda: True, client=make_client(), now=NOW)
        self.assertEqual(r["status"], "ok")
        self.assertEqual(count("weather"), len(config.AREAS))
        self.assertEqual(count("earthquakes"), 3)                       # quarry blast + no-mag skipped
        for src in ("weather", "earthquakes"):
            s = sync(src)
            self.assertEqual(s["last_success_at"], iso(NOW))
            self.assertIsNone(s["last_error"])
        c = connect()
        self.assertTrue(c.execute("SELECT fetched_at FROM weather LIMIT 1").fetchone()[0].endswith("Z"))
        c.close()

    def test_chunks_built_and_searchable(self):
        run_all(online_check=lambda: True, client=make_client(), now=NOW)
        c = connect()
        self.assertEqual(c.execute("SELECT COUNT(*) FROM chunks WHERE kind='weather'").fetchone()[0], len(config.AREAS))
        self.assertEqual(c.execute("SELECT COUNT(*) FROM chunks WHERE kind='quake'").fetchone()[0], 3)
        hit = c.execute("SELECT title FROM chunks_fts WHERE chunks_fts MATCH 'PAGASA' LIMIT 1").fetchone()
        self.assertIsNotNone(hit)
        text = c.execute("SELECT text FROM chunks WHERE kind='weather' AND ref_id='Lipa City'").fetchone()[0]
        self.assertIn("not an official PAGASA warning", text)
        c.close()

    def test_failure_keeps_old_data(self):
        run_all(online_check=lambda: True, client=make_client(), now=NOW)
        w, q = count("weather"), count("earthquakes")
        later = NOW + timedelta(minutes=15)
        r = run_all(online_check=lambda: True, client=make_client(fail_all=True), now=later)
        self.assertFalse(r["weather"]["ok"])
        self.assertFalse(r["earthquakes"]["ok"])
        self.assertEqual((count("weather"), count("earthquakes")), (w, q))      # nothing deleted
        s = sync("weather")
        self.assertEqual(s["last_success_at"], iso(NOW))                        # unchanged
        self.assertEqual(s["last_attempt_at"], iso(later))
        self.assertIn("500", s["last_error"])
        self.assertGreater(count_chunks("weather"), 0)                          # chunks still there

    def test_partial_failure_saves_the_rest(self):
        bad = config.AREAS[3]
        r = run_all(online_check=lambda: True, client=make_client(fail_lat=bad["lat"]), now=NOW)
        self.assertTrue(r["weather"]["ok"])
        self.assertEqual(count("weather"), len(config.AREAS) - 1)
        s = sync("weather")
        self.assertEqual(s["last_success_at"], iso(NOW))
        self.assertIn(bad["name"], s["last_error"])                             # noted, not hidden

    def test_offline_skips_everything(self):
        r = run_all(online_check=lambda: False, client=make_client(), now=NOW)
        self.assertEqual(r["status"], "offline")
        self.assertEqual((count("weather"), count("earthquakes")), (0, 0))
        self.assertIsNone(sync("weather"))

    def test_quakes_update_in_place_no_duplicates(self):
        run_all(online_check=lambda: True, client=make_client(mag=4.6), now=NOW)
        run_all(online_check=lambda: True, client=make_client(mag=4.9), now=NOW + timedelta(minutes=15))
        self.assertEqual(count("earthquakes"), 3)
        c = connect()
        self.assertEqual(c.execute("SELECT magnitude FROM earthquakes WHERE ext_id='us1'").fetchone()[0], 4.9)
        c.close()

    def test_weather_history_is_capped(self):
        for i in range(config.WEATHER_KEEP_SNAPSHOTS + 5):
            run_all(online_check=lambda: True, client=make_client(), now=NOW + timedelta(minutes=i))
        c = connect()
        per_area = c.execute("SELECT COUNT(*) FROM weather WHERE lat=?", (config.AREAS[0]["lat"],)).fetchone()[0]
        c.close()
        self.assertEqual(per_area, config.WEATHER_KEEP_SNAPSHOTS)


def count_chunks(kind):
    c = connect()
    try:
        return c.execute("SELECT COUNT(*) FROM chunks WHERE kind=?", (kind,)).fetchone()[0]
    finally:
        c.close()


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.api = TestClient(app)

    def setUp(self):
        reset()

    def test_dashboard_before_any_sync(self):
        d = self.api.get("/api/dashboard", params={"lat": 13.94, "lng": 121.16}).json()
        self.assertIsNone(d["weather"])
        self.assertFalse(d["earthquakes"]["has_data"])          # "no data yet" is not "no earthquakes"
        self.assertTrue(d["earthquakes"]["stale"])

    def test_dashboard_with_data(self):
        run_all(online_check=lambda: True, client=make_client(), now=utc_now())
        d = self.api.get("/api/dashboard", params={"lat": 13.94, "lng": 121.16}).json()
        self.assertEqual(d["weather"]["area"], "Lipa City")
        self.assertLess(d["weather"]["distance_km"], 2)
        self.assertFalse(d["weather"]["stale"])
        self.assertEqual(d["weather"]["current"]["condition"], "Light rain showers")
        q = d["earthquakes"]
        self.assertTrue(q["has_data"])
        self.assertEqual(q["count"], 2)                         # the Mindanao quake is outside 300 km
        self.assertTrue(q["items"][0]["occurred_at"] > q["items"][1]["occurred_at"])   # newest first
        self.assertGreater(q["items"][0]["distance_km"], 0)

    def test_old_data_is_flagged_stale(self):
        run_all(online_check=lambda: True, client=make_client(), now=utc_now() - timedelta(hours=5))
        d = self.api.get("/api/dashboard", params={"lat": 13.94, "lng": 121.16}).json()
        self.assertTrue(d["weather"]["stale"])
        self.assertGreaterEqual(d["weather"]["age_minutes"], 299)
        self.assertTrue(d["earthquakes"]["stale"])
        self.assertTrue(d["sources"]["weather"]["stale"])

    def test_far_location_has_no_weather(self):
        run_all(online_check=lambda: True, client=make_client(), now=utc_now())
        d = self.api.get("/api/dashboard", params={"lat": 10.3, "lng": 123.9}).json()   # Cebu
        self.assertIsNone(d["weather"])

    def test_status_and_validation(self):
        s = self.api.get("/api/status").json()
        self.assertIn("weather", s["sources"])
        self.assertEqual(self.api.get("/api/dashboard", params={"lat": 999, "lng": 1}).status_code, 422)


if __name__ == "__main__":
    unittest.main()
