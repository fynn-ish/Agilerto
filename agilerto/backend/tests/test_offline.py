"""Offline behavior: the map tile file and its server, the tile download tool, and a tripwire that proves
the running system never reaches for the internet while serving. No internet or Ollama needed.
Run from the backend folder:   python -m unittest tests.test_offline -v
"""
import datetime as dt
import gzip
import json
import os
import socket
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

_tmp = tempfile.mkdtemp()
os.environ.setdefault("DISASTER_DB", os.path.join(_tmp, "offline.db"))
os.environ["DISABLE_SCHEDULER"] = "1"

from fastapi.testclient import TestClient

import get_tiles
from app import config, tiles
from app.main import app
from app.rag import llm
from app.rag.llm import OllamaError
from tests.test_news_advisories import run as load_everything, setup_db as setup_everything
from tests.test_rag import LIPA, FakeLLM
from tools.pmtiles_min import encode_tile, write_pmtiles, zxy_to_tileid


def make_archive(path, *, version="4.0.0", tile_type=1, compression=2, with_version=True, bounds=(121.0, 13.8, 121.4, 14.1)):
    tile = encode_tile({"earth": [{"type": "polygon", "geometry": [[(0, 0), (4096, 0), (4096, 4096), (0, 4096), (0, 0)]], "props": {}}]})
    meta = {"name": "Unit test tiles", "attribution": "&copy; OpenStreetMap contributors"}
    if with_version:
        meta["version"] = version
    write_pmtiles(path, {zxy_to_tileid(0, 0, 0): tile, zxy_to_tileid(1, 0, 0): tile}, tile_type=tile_type,
                  tile_compression=compression, min_zoom=0, max_zoom=14, bounds=bounds, center_zoom=10, metadata=meta)


class TileFileTests(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.patch = mock.patch.object(config, "TILES_DIR", str(self.dir))
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def test_header_is_read_correctly(self):
        make_archive(self.dir / "a.pmtiles")
        h = tiles.read_header(self.dir / "a.pmtiles")
        self.assertEqual((h["tile_type"], h["tile_compression"], h["minzoom"], h["maxzoom"]), ("vector", "gzip", 0, 14))
        self.assertEqual([round(x, 4) for x in h["bounds"]], [121.0, 13.8, 121.4, 14.1])
        self.assertTrue(h["clustered"])

    def test_a_good_file_is_usable(self):
        make_archive(self.dir / "a.pmtiles")
        d = tiles.describe(self.dir / "a.pmtiles")
        self.assertTrue(d["usable"])
        self.assertEqual((d["name"], d["schema_version"], d["attribution"]), ("Unit test tiles", "4.0.0", "© OpenStreetMap contributors"))

    def test_files_the_map_cannot_draw_are_refused_with_a_reason(self):
        cases = {
            "raster": (dict(tile_type=2), "png"),
            "old schema": (dict(version="3.7.1"), "older Protomaps schema"),
            "brotli": (dict(compression=3), "compression"),
        }
        for name, (kw, expect) in cases.items():
            p = self.dir / f"{name.replace(' ', '_')}.pmtiles"
            make_archive(p, **kw)
            d = tiles.describe(p)
            self.assertFalse(d["usable"], name)
            self.assertIn(expect, d["reason"], name)

    def test_unknown_schema_is_allowed_but_noted(self):
        make_archive(self.dir / "a.pmtiles", with_version=False)
        d = tiles.describe(self.dir / "a.pmtiles")
        self.assertTrue(d["usable"])
        self.assertIn("could not be checked", d["note"])

    def test_damaged_files_never_crash(self):
        (self.dir / "bad.pmtiles").write_bytes(b"this is not a tile file at all" * 10)
        (self.dir / "short.pmtiles").write_bytes(b"PMTiles\x03")
        (self.dir / "v2.pmtiles").write_bytes(b"PMTiles\x02" + b"\0" * 200)
        for n in ("bad", "short", "v2"):
            d = tiles.describe(self.dir / f"{n}.pmtiles")
            self.assertFalse(d["usable"], n)
            self.assertIn("cannot be read", d["reason"])

    def test_choosing_the_file(self):
        self.assertIsNone(tiles.find_file())
        make_archive(self.dir / "other.pmtiles")
        self.assertEqual(tiles.find_file().name, "other.pmtiles")                 # any tile file will do
        make_archive(self.dir / config.TILES_FILE)
        self.assertEqual(tiles.find_file().name, config.TILES_FILE)               # the configured one wins

    def test_range_parsing(self):
        pr = tiles.parse_range
        self.assertEqual(pr("bytes=0-9", 100), (0, 9))
        self.assertEqual(pr("bytes=90-", 100), (90, 99))
        self.assertEqual(pr("bytes=-10", 100), (90, 99))
        self.assertEqual(pr("bytes=50-500", 100), (50, 99))                       # end is clipped to the file
        for bad in ("bytes=100-", "bytes=9-3", "bytes=-0", "bytes=", "items=0-5", "bytes=0-1,5-6", "garbage"):
            self.assertIsNone(pr(bad, 100), bad)


class TileServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.api = TestClient(app)

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        p = mock.patch.object(config, "TILES_DIR", str(self.dir))
        p.start()
        self.addCleanup(p.stop)
        make_archive(self.dir / "map.pmtiles")
        self.raw = (self.dir / "map.pmtiles").read_bytes()

    def test_info_without_a_file_says_what_to_do(self):
        (self.dir / "map.pmtiles").unlink()
        d = self.api.get("/api/tiles/info").json()
        self.assertEqual((d["available"], d["usable"]), (False, False))
        self.assertIn("get_tiles.py", d["reason"])

    def test_info_with_a_file(self):
        d = self.api.get("/api/tiles/info").json()
        self.assertTrue(d["usable"] and d["available"])
        self.assertEqual((d["url"], d["maxzoom"]), ("/tiles/map.pmtiles", 14))

    def test_whole_file_and_headers(self):
        r = self.api.get("/tiles/map.pmtiles")
        self.assertEqual((r.status_code, r.content), (200, self.raw))
        self.assertEqual(r.headers["accept-ranges"], "bytes")
        self.assertTrue(r.headers["etag"].startswith('"'))

    def test_ranges(self):
        r = self.api.get("/tiles/map.pmtiles", headers={"Range": "bytes=0-126"})
        self.assertEqual((r.status_code, r.content), (206, self.raw[:127]))
        self.assertEqual(r.headers["content-range"], f"bytes 0-126/{len(self.raw)}")
        r = self.api.get("/tiles/map.pmtiles", headers={"Range": "bytes=-10"})
        self.assertEqual((r.status_code, r.content), (206, self.raw[-10:]))
        r = self.api.get("/tiles/map.pmtiles", headers={"Range": f"bytes={len(self.raw) - 5}-"})
        self.assertEqual(r.content, self.raw[-5:])

    def test_bad_ranges_and_changed_files(self):
        r = self.api.get("/tiles/map.pmtiles", headers={"Range": "bytes=99999999-"})
        self.assertEqual(r.status_code, 416)
        r = self.api.get("/tiles/map.pmtiles", headers={"Range": "bytes=0-5", "If-Match": '"something-else"'})
        self.assertEqual(r.status_code, 412)                                       # the file was replaced while the page was open
        etag = self.api.get("/tiles/map.pmtiles").headers["etag"]
        ok = self.api.get("/tiles/map.pmtiles", headers={"Range": "bytes=0-5", "If-Match": etag})
        self.assertEqual(ok.status_code, 206)
        make_archive(self.dir / "map.pmtiles", bounds=(120.0, 13.0, 122.0, 15.0), version="4.1.0")
        (self.dir / "map.pmtiles").write_bytes((self.dir / "map.pmtiles").read_bytes() + b"x")
        self.assertNotEqual(self.api.get("/tiles/map.pmtiles").headers["etag"], etag)

    def test_head_has_no_body(self):
        r = self.api.head("/tiles/map.pmtiles")
        self.assertEqual((r.status_code, r.content), (200, b""))
        self.assertEqual(int(r.headers["content-length"]), len(self.raw))

    def test_only_tile_files_in_the_tile_folder_can_be_read(self):
        (self.dir.parent / "secret.pmtiles").write_bytes(b"secret")
        (self.dir / "notes.txt").write_text("private")
        for url in ("/tiles/notes.txt", "/tiles/missing.pmtiles", "/tiles/..%2Fsecret.pmtiles", "/tiles/%2e%2e/secret.pmtiles",
                    "/tiles/sub/map.pmtiles", "/tiles/map.pmtiles%00.txt"):
            self.assertEqual(self.api.get(url).status_code, 404, url)


class GetTilesToolTests(unittest.TestCase):
    ASSETS = ["go-pmtiles-1.31.2_Darwin_arm64.zip", "go-pmtiles-1.31.2_Darwin_x86_64.zip", "go-pmtiles_1.31.2_Linux_arm64.tar.gz",
              "go-pmtiles_1.31.2_Linux_x86_64.tar.gz", "go-pmtiles_1.31.2_Windows_arm64.zip", "go-pmtiles_1.31.2_Windows_x86_64.zip"]

    def test_picks_the_right_download_for_each_computer(self):
        pick = lambda s, m: get_tiles.pick_asset(self.ASSETS, s, m)
        self.assertEqual(pick("Windows", "AMD64"), "go-pmtiles_1.31.2_Windows_x86_64.zip")
        self.assertEqual(pick("Linux", "x86_64"), "go-pmtiles_1.31.2_Linux_x86_64.tar.gz")
        self.assertEqual(pick("Darwin", "arm64"), "go-pmtiles-1.31.2_Darwin_arm64.zip")
        self.assertEqual(pick("Linux", "aarch64"), "go-pmtiles_1.31.2_Linux_arm64.tar.gz")
        self.assertIsNone(pick("Plan9", "x86_64"))

    def test_finds_the_newest_build_that_exists(self):
        today = dt.date(2026, 11, 26)
        exists = {"https://build.protomaps.com/20261124.pmtiles"}
        self.assertEqual(get_tiles.find_latest_build(lambda u: u in exists, today), "https://build.protomaps.com/20261124.pmtiles")
        self.assertIsNone(get_tiles.find_latest_build(lambda u: False, today, days=5))

    def test_area_boxes_are_valid(self):
        for name, box in get_tiles.AREAS.items():
            self.assertEqual(get_tiles.parse_bbox(box), ",".join(str(float(x)) for x in box.split(",")), name)
        for bad in ("1,2,3", "122,13,121,14", "a,b,c,d", "0,0,200,10"):
            with self.assertRaises(SystemExit):
                get_tiles.parse_bbox(bad)

    def test_areas_contain_lipa_and_the_sample_cities(self):
        for name in ("calabarzon", "batangas", "lipa"):
            w, s, e, n = (float(x) for x in get_tiles.AREAS[name].split(","))
            self.assertTrue(w < 121.1631 < e and s < 13.9411 < n, name)
        w, s, e, n = (float(x) for x in get_tiles.AREAS["calabarzon"].split(","))
        for a in config.AREAS:                                                    # every monitored city is on the offline map
            self.assertTrue(w < a["lng"] < e and s < a["lat"] < n, a["name"])


class NoInternetTripwire:
    """Records, and refuses, every attempt to reach a computer that is not this one."""
    LOOPBACK = {"127.0.0.1", "localhost", "::1", "testserver", "0.0.0.0"}

    def __init__(self):
        self.attempts, self._lock = [], threading.Lock()

    def __enter__(self):
        real_conn, real_info = socket.create_connection, socket.getaddrinfo

        def conn(address, *a, **k):
            if address[0] in self.LOOPBACK:
                return real_conn(address, *a, **k)
            with self._lock:
                self.attempts.append(address[0])
            raise OSError("offline test: no internet")

        def info(host, *a, **k):
            if host in self.LOOPBACK or host is None:
                return real_info(host, *a, **k)
            with self._lock:
                self.attempts.append(host)
            raise socket.gaierror("offline test: no internet")

        self.patches = [mock.patch.object(socket, "create_connection", conn), mock.patch.object(socket, "getaddrinfo", info)]
        for p in self.patches:
            p.start()
        return self

    def __exit__(self, *exc):
        for p in self.patches:
            p.stop()


class OfflineSystemTests(unittest.TestCase):
    """Load everything while 'online', then pull the plug and use the whole system."""
    PROBE = {"api.open-meteo.com"}                    # the one deliberate check "is the internet there?"

    @classmethod
    def setUpClass(cls):
        setup_everything()
        load_everything(force=True)                  # weather, earthquakes, advisories and news saved
        cls.api = TestClient(app)

    def get_all(self):
        return {u: self.api.get(u) for u in (
            "/api/health", f"/api/facilities?lat={LIPA[0]}&lng={LIPA[1]}&radius_km=10", "/api/emergency-numbers",
            "/api/safety-guides?hazard=earthquake", f"/api/dashboard?lat={LIPA[0]}&lng={LIPA[1]}", "/api/status",
            "/api/ai/status", "/api/tiles/info")}

    def test_every_page_of_data_works_with_no_internet(self):
        with NoInternetTripwire() as wire:
            pages = self.get_all()
        for url, r in pages.items():
            self.assertEqual(r.status_code, 200, url)
        d = pages[f"/api/dashboard?lat={LIPA[0]}&lng={LIPA[1]}"].json()
        self.assertFalse(d["online"])
        self.assertEqual(d["weather"]["area"], "Lipa City")                       # the last saved weather is still there
        self.assertTrue(d["advisories"]["has_data"] and d["news"]["has_data"])
        self.assertGreater(pages["/api/facilities?lat=13.9411&lng=121.1631&radius_km=10"].json()["count"], 5)
        self.assertGreaterEqual(pages["/api/emergency-numbers"].json()["count"], 3)
        self.assertFalse(pages["/api/ai/status"].json()["running"] and False)     # the local AI check never leaves this computer
        self.assertLessEqual(set(wire.attempts), self.PROBE, f"tried to reach the internet: {set(wire.attempts)}")

    def test_the_assistant_works_with_no_internet(self):
        questions = ["Where is the nearest hospital?", "What should I do during an earthquake?", "Emergency hotline numbers",
                     "Any advisories or warnings?", "What's the weather now?", "Latest news about the typhoon",
                     "Saan ang pinakamalapit na ospital?"]
        with NoInternetTripwire() as wire, mock.patch.object(llm, "chat", return_value="Saved data says so [1]."):
            for q in questions:
                r = self.api.post("/api/chat", json={"question": q, "lat": LIPA[0], "lng": LIPA[1]})
                self.assertEqual(r.status_code, 200, q)
                body = r.json()
                self.assertIn(body["outcome"], ("answered", "no_advisories"), q)
                self.assertFalse(body["online"], q)
                if body["outcome"] == "answered":
                    self.assertTrue(body["citations"], q)
            self.assertEqual(self.api.post("/api/chat", json={"question": "Tulong! May sunog", "lat": 13.9, "lng": 121.1}).json()["outcome"], "emergency")
            self.assertEqual(self.api.post("/api/chat", json={"question": "Should I evacuate?", "lat": 13.9, "lng": 121.1}).json()["outcome"], "refused")
        self.assertLessEqual(set(wire.attempts), self.PROBE, f"tried to reach the internet: {set(wire.attempts)}")

    def test_offline_answers_say_how_old_the_data_is(self):
        with NoInternetTripwire(), mock.patch.object(llm, "chat", return_value="Light rain showers [1]."):
            r = self.api.post("/api/chat", json={"question": "What's the weather now?", "lat": LIPA[0], "lng": LIPA[1]}).json()
        self.assertTrue(any("Offline" in n["text"] for n in r["notices"]))
        self.assertIsNotNone(r["as_of"])

    def test_without_the_local_ai_the_saved_records_are_still_shown(self):
        with NoInternetTripwire() as wire, mock.patch.object(llm, "chat", side_effect=OllamaError("not_running", "Ollama is not running")):
            r = self.api.post("/api/chat", json={"question": "Where is the nearest hospital?", "lat": LIPA[0], "lng": LIPA[1]}).json()
        self.assertEqual(r["outcome"], "ai_unavailable")
        self.assertIn("Mary Mediatrix", r["answer"])
        self.assertLessEqual(set(wire.attempts), self.PROBE)

    def test_the_tripwire_itself_works(self):
        with NoInternetTripwire() as wire:
            with self.assertRaises(OSError):
                socket.create_connection(("example.com", 80), timeout=1)
        self.assertEqual(wire.attempts, ["example.com"])


if __name__ == "__main__":
    unittest.main()
