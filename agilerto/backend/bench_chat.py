"""Ask the same question many times and measure how consistent and how fast the assistant is.
A small model can answer differently each time. Safe answers must not.

    python bench_chat.py                                   # 3 typical questions, 10 times each
    python bench_chat.py --runs 5 --question "Where is the nearest hospital?"
    python bench_chat.py --url http://192.168.1.9:8000

Run it against the running backend with Ollama on. Every run goes through the whole system, so the timing is what a
person would feel. While it runs, open Task Manager (Ctrl+Shift+Esc) and watch memory and CPU for "ollama" to see
whether your laptop can cope.

CONSISTENT means the same outcome and the same cited sources in at least 90% of runs. The wording may still differ.
"""
import argparse
import json
import statistics
import sys
import time
import urllib.error
import urllib.request
from collections import Counter

DEFAULTS = ["Where is the nearest hospital?", "What should I do during an earthquake?", "Saan ang pinakamalapit na evacuation center?"]


def ask(url, question, lat, lng, timeout):
    body = json.dumps({"question": question, "lat": lat, "lng": lng}).encode()
    req = urllib.request.Request(url.rstrip("/") + "/api/chat", data=body, headers={"Content-Type": "application/json"})
    t0 = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.load(r), time.monotonic() - t0
    except urllib.error.HTTPError as e:
        if e.code == 429:                                   # asked too fast: wait as told, then continue
            time.sleep(int(e.headers.get("Retry-After", "10")))
            return ask(url, question, lat, lng, timeout)
        raise


def percentile(values, p):
    if len(values) < 2:
        return values[0]
    return statistics.quantiles(values, n=100, method="inclusive")[p - 1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8000")
    ap.add_argument("--question", action="append", help="repeat the option for more than one question")
    ap.add_argument("--runs", type=int, default=10)
    ap.add_argument("--lat", type=float, default=13.9411)
    ap.add_argument("--lng", type=float, default=121.1631)
    ap.add_argument("--timeout", type=float, default=240)
    a = ap.parse_args()

    worst = "CONSISTENT"
    for q in a.question or DEFAULTS:
        print(f"\nQuestion: {q}   ({a.runs} runs)")
        outcomes, sources, answers, times = Counter(), Counter(), Counter(), []
        for i in range(a.runs):
            try:
                body, secs = ask(a.url, q, a.lat, a.lng, a.timeout)
            except (OSError, ValueError) as exc:
                print(f"  run {i + 1}: could not reach the assistant ({exc})")
                return 1
            outcomes[body["outcome"]] += 1
            sources[tuple(sorted((c["n"], c["title"]) for c in body["citations"]))] += 1
            answers[body["answer"].strip()] += 1
            times.append(secs)
            print(f"  run {i + 1:2}: {body['outcome']:15} {secs:6.1f}s  cites {[c['n'] for c in body['citations']]}")
        n = a.runs
        top_outcome, top_out_n = outcomes.most_common(1)[0]
        top_src_n = sources.most_common(1)[0][1]
        consistent = top_out_n / n >= 0.9 and top_src_n / n >= 0.9
        worst = worst if consistent else "NOT CONSISTENT"
        print(f"  outcomes: {dict(outcomes)}")
        print(f"  same cited sources in {top_src_n}/{n} runs | {len(answers)} different wordings | most common wording {answers.most_common(1)[0][1]}/{n}")
        print(f"  time: fastest {min(times):.1f}s | typical {statistics.median(times):.1f}s | slowest-10% {percentile(times, 90):.1f}s | slowest {max(times):.1f}s")
        print(f"  verdict: {'CONSISTENT' if consistent else 'NOT CONSISTENT: try another model or lower the temperature'}")
        if top_outcome in ("fallback", "ai_unavailable"):
            print(f"  note: mostly '{top_outcome}'. The AI is not giving usable answers.")
    print(f"\nOverall: {worst}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
