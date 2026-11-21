"""Tests for the assistant: guardrails, retrieval, answer checking, fallbacks, and the API.
A scripted fake stands in for Ollama, so no model or internet is needed.
Run from the backend folder:   python -m unittest tests.test_rag -v
"""
import os
import tempfile
import unittest
from datetime import timedelta
from unittest import mock

_tmp = tempfile.mkdtemp()
os.environ.setdefault("DISASTER_DB", os.path.join(_tmp, "rag.db"))
os.environ["DISABLE_SCHEDULER"] = "1"

import httpx
from fastapi.testclient import TestClient

import seed
from app import config
from app.chunks import rebuild_static_chunks
from app.db import connect, init_db
from app.ingest import run_all
from app.main import app
from app.rag import guardrails as G
from app.rag import llm, validate as V
from app.rag.llm import OllamaError
from app.rag.pipeline import answer_question
from app.rag.retrieval import retrieve
from app.timeutil import utc_now
from tests.test_ingest import make_client

LIPA = (13.9411, 121.1631)
CEBU = (10.3157, 123.8854)


class FakeLLM:
    """Plays back scripted replies and records every prompt it receives."""
    def __init__(self, *replies):
        self.replies, self.calls = list(replies), []

    def __call__(self, messages):
        self.calls.append(messages)
        r = self.replies.pop(0) if len(self.replies) > 1 else self.replies[0]
        if isinstance(r, Exception):
            raise r
        return r


def setup_db():
    init_db()
    c = connect()
    for t in ("weather", "earthquakes", "sync_log", "chat_log"):
        c.execute(f"DELETE FROM {t}")
    c.execute("DELETE FROM chunks")
    with c:
        seed.seed(c)
        rebuild_static_chunks(c)
    c.close()
    run_all(online_check=lambda: True, client=make_client(), now=utc_now())


def ask(question, fake, loc=LIPA, **kw):
    c = connect()
    try:
        return answer_question(c, question, *loc, llm_chat=fake, online=kw.pop("online", True), **kw)
    finally:
        c.close()


def log_rows():
    c = connect()
    try:
        return [dict(r) for r in c.execute("SELECT * FROM chat_log ORDER BY id")]
    finally:
        c.close()


class ValidateTests(unittest.TestCase):
    def test_citation_formats(self):
        self.assertEqual(V.cited_numbers("a [1] b [2][3] c [2, 4]"), [1, 2, 3, 4])

    def test_phone_like_numbers_ignore_measurements_years_decimals(self):
        txt = "0.49 km away, 300 people, 85%, built 2019, M4.6, call (02) 8911-1406 or 911 [1]"
        self.assertEqual(V.phone_like_numbers(txt), ["0289111406", "911"])

    def test_check_rules(self):
        allowed = ["Emergency hotline: NDRRMC (National): (02) 8911-1406."]
        self.assertIsNone(V.check("Call (02) 8911-1406 [1].", 1, allowed)[0])
        self.assertIn("do not exist", V.check("Call it [5].", 2, allowed)[0])
        self.assertIn("no citations", V.check("Call it now.", 2, allowed)[0])
        self.assertIn("not in the sources", V.check("Call 8888-1234 [1].", 1, allowed)[0])
        self.assertIsNone(V.check("I don't have that information in my saved data.", 2, allowed)[0])
        self.assertIsNotNone(V.check("   ", 2, allowed)[0])


class GuardrailTests(unittest.TestCase):
    def test_refusals(self):
        for q, code in [("Should I evacuate?", "evacuation"), ("Dapat ba akong lumikas?", "evacuation"),
                        ("Lilindol ba ulit?", "prediction"), ("Will there be another earthquake?", "prediction"),
                        ("Will it flood tonight?", "prediction"), ("Is it safe to go home?", "safety"),
                        ("Ligtas ba sa Lipa?", "safety"), ("Kailangan ba naming mag-evacuate?", "evacuation")]:
            self.assertEqual(G.detect_refusal(q), code, q)

    def test_normal_questions_are_not_refused(self):
        for q in ["Where is the nearest hospital?", "What should I do during an earthquake?", "Is the evacuation center open?",
                  "Will it rain tomorrow?", "Saan ang pinakamalapit na ospital?", "Ano ang gagawin kapag lumilindol?",
                  "May lindol ba kanina?", "Should I bring water to the evacuation center?"]:
            self.assertIsNone(G.detect_refusal(q), q)

    def test_emergencies(self):
        for q, kind in [("Tulong! May sunog sa bahay namin", "fire"), ("help me I'm trapped", "general"),
                        ("hindi makahinga ang lolo ko", "medical"), ("There is a fire in my house", "fire"),
                        ("May baha na dito sa amin", "general")]:
            self.assertEqual(G.detect_emergency(q)["kind"], kind, q)
        for q in ["What should I do if there is a fire?", "Ano ang gagawin kung may sunog?", "nearest fire station",
                  "emergency hotline numbers", "Ano ang gagawin kapag lumilindol?"]:
            self.assertIsNone(G.detect_emergency(q), q)

    def test_language(self):
        self.assertEqual(G.language_of("Where is the nearest hospital?"), "en")
        self.assertEqual(G.language_of("Saan ang pinakamalapit na ospital?"), "tl")


class RetrievalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        setup_db()
        cls.conn = connect()

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    def kinds(self, q, loc=LIPA):
        return [(s.kind, s.title) for s in retrieve(self.conn, q, *loc)]

    def test_nearest_hospital_sorted_by_distance(self):
        src = retrieve(self.conn, "Where is the nearest hospital?", *LIPA)
        self.assertTrue(src and all(s.kind == "facility" and s.facility["type"] == "hospital" for s in src))
        self.assertEqual(src[0].title, "Mary Mediatrix Medical Center")
        self.assertEqual([s.distance_km for s in src], sorted(s.distance_km for s in src))
        self.assertEqual([s.n for s in src], list(range(1, len(src) + 1)))

    def test_tagalog_question(self):
        src = retrieve(self.conn, "Saan ang pinakamalapit na ospital?", *LIPA)
        self.assertEqual(src[0].kind, "facility")

    def test_weather_returns_only_nearest_city(self):
        src = retrieve(self.conn, "What's the weather now?", *LIPA)
        self.assertEqual([(s.kind, s.ref_id) for s in src], [("weather", "Lipa City")])
        self.assertIsNotNone(src[0].as_of)

    def test_quakes_nearby_only(self):
        src = retrieve(self.conn, "Recent earthquakes near me", *LIPA)
        quakes = [s for s in src if s.kind == "quake"]
        self.assertEqual(len(quakes), 2)                     # the Mindanao one is beyond 300 km
        self.assertLessEqual(len([s for s in src if s.kind == "guide"]), 1)

    def test_howto_returns_guides_only(self):
        src = retrieve(self.conn, "What should I do during an earthquake?", *LIPA)
        self.assertTrue(src and all(s.kind == "guide" for s in src))
        self.assertIn("during", src[0].title.lower())

    def test_hotlines_skip_placeholder_numbers(self):
        src = retrieve(self.conn, "emergency hotline numbers", *LIPA)
        self.assertTrue(src and all(s.kind == "hotline" for s in src))
        self.assertFalse(any("ADD LOCAL NUMBER" in s.text for s in src))

    def test_record_text_reads_naturally(self):
        src = retrieve(self.conn, "Nearest evacuation center", *LIPA)
        self.assertTrue(src and all("is an evacuation center" in s.text for s in src))

    def test_off_topic_returns_nothing(self):
        self.assertEqual(self.kinds("who won the basketball game"), [])

    def test_far_from_any_data_returns_nothing(self):
        self.assertEqual(self.kinds("Where is the nearest hospital?", CEBU), [])

    def test_never_more_than_the_limit(self):
        self.assertLessEqual(len(retrieve(self.conn, "hospital weather earthquake hotline fire police evacuation", *LIPA)),
                             config.MAX_SOURCES)


class PipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        setup_db()

    def setUp(self):
        c = connect(); c.execute("DELETE FROM chat_log"); c.commit(); c.close()

    def test_good_answer_is_returned_with_citations(self):
        fake = FakeLLM("The nearest hospital is Mary Mediatrix Medical Center, 0.49 km away [1]. Next is Lipa Medix Medical Center [2].")
        r = ask("Where is the nearest hospital?", fake)
        self.assertEqual(r["outcome"], "answered")
        self.assertEqual([c["n"] for c in r["citations"]], [1, 2])      # only the cited ones come back
        self.assertEqual(r["citations"][0]["facility"]["type"], "hospital")
        self.assertIsInstance(r["citations"][0]["facility"]["id"], int)
        self.assertEqual(len(fake.calls), 1)
        self.assertEqual(r["model"], config.OLLAMA_MODEL)

    def test_prompt_contains_only_retrieved_sources_and_status(self):
        fake = FakeLLM("Light rain showers, 29 C [1].")
        ask("What's the weather now?", fake, online=False)
        system = fake.calls[0][0]["content"]
        sources_part = system.split("SOURCES:")[1]                       # the rules also mention "[2]" as an example
        self.assertIn("[1] (Weather, as of", sources_part)
        self.assertNotIn("[2]", sources_part)                           # only the one retrieved record is shown
        self.assertIn("OFFLINE", system)
        self.assertEqual(fake.calls[0][1]["content"], "Question: What's the weather now?")

    def test_weather_answer_has_as_of_and_offline_notice(self):
        r = ask("What's the weather now?", FakeLLM("Light rain showers, 29 C [1]."), online=False)
        self.assertIsNotNone(r["as_of"])
        self.assertTrue(any("Offline" in n["text"] for n in r["notices"]))
        r = ask("What's the weather now?", FakeLLM("Light rain showers, 29 C [1]."), online=True)
        self.assertFalse(any("Offline" in n["text"] for n in r["notices"]))

    def test_stale_data_gets_a_warning(self):
        r = ask("What's the weather now?", FakeLLM("Light rain showers [1]."), now=utc_now() + timedelta(hours=5))
        self.assertTrue(any("old" in n["text"].lower() for n in r["notices"]))

    def test_unverified_places_get_a_notice(self):
        r = ask("Where is the nearest hospital?", FakeLLM("Mary Mediatrix Medical Center [1]."))
        self.assertTrue(any("not verified" in n["text"] for n in r["notices"]))

    def test_nonexistent_citation_triggers_one_retry(self):
        fake = FakeLLM("It is Mary Mediatrix Medical Center [9].", "It is Mary Mediatrix Medical Center [1].")
        r = ask("Where is the nearest hospital?", fake)
        self.assertEqual(r["outcome"], "answered")
        self.assertEqual(len(fake.calls), 2)
        self.assertIn("rejected", fake.calls[1][-1]["content"])

    def test_invented_phone_number_is_caught(self):
        fake = FakeLLM("Call the hotline at 8888-1234 [1].", "Call (02) 8911-1406 [3].")
        r = ask("What is the NDRRMC hotline number?", fake)
        self.assertEqual(r["outcome"], "answered")
        self.assertIn("8911-1406", r["answer"])
        self.assertIn("not in the sources", fake.calls[1][-1]["content"])

    def test_two_bad_answers_fall_back_to_saved_records(self):
        fake = FakeLLM("Totally made up [7].")
        r = ask("Where is the nearest hospital?", fake)
        self.assertEqual(r["outcome"], "fallback")
        self.assertIn("Mary Mediatrix", r["answer"])
        self.assertNotIn("made up", r["answer"])
        self.assertEqual(len(fake.calls), 2)
        self.assertEqual(log_rows()[-1]["outcome"], "fallback")

    def test_uncited_answer_is_not_accepted(self):
        r = ask("Where is the nearest hospital?", FakeLLM("There is a hospital nearby."))
        self.assertEqual(r["outcome"], "fallback")

    def test_model_saying_it_does_not_know_is_accepted(self):
        r = ask("Where is the nearest hospital?", FakeLLM("I don't have that information in my saved data."))
        self.assertEqual(r["outcome"], "not_in_sources")
        self.assertEqual(r["citations"], [])

    def test_ollama_not_running_shows_saved_records(self):
        r = ask("Where is the nearest hospital?", FakeLLM(OllamaError("not_running", "Ollama is not running")))
        self.assertEqual(r["outcome"], "ai_unavailable")
        self.assertIn("Mary Mediatrix", r["answer"])
        self.assertTrue(r["citations"])
        self.assertEqual(r["ai_error"], "not_running")

    def test_refusals_never_reach_the_ai(self):
        for q, code, lang in [("Should I evacuate?", "evacuation", "en"), ("Lilindol ba ulit?", "prediction", "tl"),
                              ("Is it safe to go home?", "safety", "en")]:
            fake = FakeLLM("should not be used [1]")
            r = ask(q, fake)
            self.assertEqual((r["outcome"], r["refusal"], r["lang"]), ("refused", code, lang))
            self.assertEqual(len(fake.calls), 0, q)
            self.assertTrue(r["emergency_numbers"])                     # official numbers always come with a refusal
            if code != "prediction":
                self.assertIn("911", r["answer"])

    def test_emergency_skips_the_ai_and_shows_numbers_first(self):
        fake = FakeLLM("should not be used [1]")
        r = ask("Tulong! May sunog sa bahay namin", fake)
        self.assertEqual((r["outcome"], r["emergency"]), ("emergency", "fire"))
        self.assertEqual(len(fake.calls), 0)
        self.assertTrue(r["answer"].startswith("Mukhang emergency"))
        self.assertIn("911", r["answer"])
        kinds = {c["kind"] for c in r["citations"]}
        self.assertTrue({"hotline", "facility", "guide"} <= kinds)
        self.assertEqual([c for c in r["citations"] if c["kind"] == "facility"][0]["facility"]["type"], "fire_station")

    def test_medical_emergency_points_to_nearest_hospital(self):
        r = ask("hindi makahinga ang lolo ko", FakeLLM("x"))
        self.assertEqual(r["emergency"], "medical")
        self.assertEqual([c for c in r["citations"] if c["kind"] == "facility"][0]["facility"]["type"], "hospital")

    def test_no_records_means_no_ai_call(self):
        fake = FakeLLM("should not be used [1]")
        r = ask("who won the basketball game", fake)
        self.assertEqual(r["outcome"], "no_sources")
        self.assertEqual(len(fake.calls), 0)
        r = ask("Where is the nearest hospital?", fake, loc=CEBU)
        self.assertEqual(r["outcome"], "no_sources")

    def test_log_keeps_problem_questions_only_and_no_location(self):
        ask("who won the basketball game", FakeLLM("x"))
        ask("Should I evacuate?", FakeLLM("x"))
        ask("Where is the nearest hospital?", FakeLLM("Mary Mediatrix Medical Center [1]."))      # success: not logged
        rows = log_rows()
        self.assertEqual([r["outcome"] for r in rows], ["no_sources", "refused_evacuation"])
        self.assertEqual(rows[0]["question"], "who won the basketball game")
        self.assertIsNone(rows[1]["question"])                                                   # refusals: no text kept
        self.assertNotIn("lat", rows[0])

    def test_very_long_question_is_trimmed(self):
        fake = FakeLLM("Mary Mediatrix Medical Center [1].")
        ask("Where is the nearest hospital? " + "please " * 400, fake)
        self.assertLessEqual(len(fake.calls[0][1]["content"]), config.QUESTION_MAX_CHARS + len("Question: "))


class OllamaClientTests(unittest.TestCase):
    def client(self, handler):
        return httpx.Client(transport=httpx.MockTransport(handler))

    def test_chat_sends_low_temperature_and_returns_text(self):
        seen = {}
        def handler(req):
            seen.update(__import__("json").loads(req.content))
            return httpx.Response(200, json={"message": {"role": "assistant", "content": " Hello [1] "}, "done": True})
        out = llm.chat([{"role": "user", "content": "hi"}], client=self.client(handler))
        self.assertEqual(out, "Hello [1]")
        self.assertEqual(seen["options"]["temperature"], 0.1)
        self.assertFalse(seen["stream"])
        self.assertEqual(seen["model"], config.OLLAMA_MODEL)

    def test_errors_are_translated(self):
        def refuse(req): raise httpx.ConnectError("refused")
        def slow(req): raise httpx.ReadTimeout("slow")
        for handler, kind in [(refuse, "not_running"), (slow, "timeout"), (lambda r: httpx.Response(404), "model_missing"),
                              (lambda r: httpx.Response(500), "http_error"),
                              (lambda r: httpx.Response(200, json={"oops": 1}), "bad_reply")]:
            with self.assertRaises(OllamaError) as cm:
                llm.chat([{"role": "user", "content": "hi"}], client=self.client(handler))
            self.assertEqual(cm.exception.kind, kind)

    def test_status(self):
        up = lambda r: httpx.Response(200, json={"models": [{"name": config.OLLAMA_MODEL}]})
        self.assertTrue(llm.status(self.client(up))["model_installed"])
        other = lambda r: httpx.Response(200, json={"models": [{"name": "mistral:7b"}]})
        s = llm.status(self.client(other))
        self.assertTrue(s["running"] and not s["model_installed"])
        self.assertIn("ollama pull", s["message"])
        def down(req): raise httpx.ConnectError("refused")
        self.assertFalse(llm.status(self.client(down))["running"])


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        setup_db()
        cls.api = TestClient(app)

    def test_chat_endpoint(self):
        with mock.patch.object(llm, "chat", return_value="Mary Mediatrix Medical Center is closest [1]."):
            r = self.api.post("/api/chat", json={"question": "Where is the nearest hospital?", "lat": LIPA[0], "lng": LIPA[1]})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["outcome"], "answered")
        for key in ("answer", "citations", "online", "as_of", "notices", "elapsed_ms"):
            self.assertIn(key, body)

    def test_chat_validation(self):
        post = lambda **kw: self.api.post("/api/chat", json={"question": "hi", "lat": 13.9, "lng": 121.1, **kw}).status_code
        self.assertEqual(post(question=""), 422)
        self.assertEqual(post(question="   "), 422)
        self.assertEqual(post(question="x" * 501), 422)
        self.assertEqual(post(lat=999), 422)

    def test_ai_status_endpoint(self):
        with mock.patch.object(llm, "status", return_value={"running": False, "model": "m", "model_installed": False,
                                                           "installed_models": [], "message": "down"}):
            self.assertFalse(self.api.get("/api/ai/status").json()["running"])


if __name__ == "__main__":
    unittest.main()
