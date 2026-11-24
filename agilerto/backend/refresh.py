"""Run a data refresh by hand (needs internet). Handy for demos and for checking each real source.

    python refresh.py                       # everything, as the scheduler would
    python refresh.py --force --show        # ignore the "news was checked recently" rule and print what was saved
    python refresh.py --only gdacs,pagasa   # just some sources or groups
                                            # names: weather, earthquakes, advisories, news, gdacs, pagasa, rss, gdelt

After a run it prints the health of every source. A line starting with FAILING tells you which source broke
and why (for example HTTP 403 when a news site blocks automated requests).
"""
import argparse
import logging

from app.db import connect, init_db
from app.ingest import run_all

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logging.getLogger("uvicorn.error.ingest").setLevel(logging.INFO)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="comma-separated group or source names")
    ap.add_argument("--force", action="store_true", help="ignore the minimum interval for news")
    ap.add_argument("--show", action="store_true", help="print the saved advisories and headlines")
    args = ap.parse_args()

    init_db()
    result = run_all(only=args.only.split(",") if args.only else None, force=args.force)
    if result["status"] != "ok":
        print(f"Nothing was refreshed: {result['status']}")
        return
    print()
    for group, r in result.items():
        if isinstance(r, dict):
            state = "skipped (checked recently)" if r.get("skipped") else ("ok" if r["ok"] else "FAILED")
            print(f"{group:12} {state:28} saved={r['saved']}  {'; '.join(r['errors'])[:160]}")

    conn = connect()
    print("\nSource health:")
    for row in conn.execute("SELECT * FROM sync_log WHERE source LIKE '%:%' ORDER BY source"):
        failing = row["last_error"] and row["last_attempt_at"] != row["last_success_at"]
        print(f"  {'FAILING' if failing else 'ok     '} {row['source']:22} last ok: {row['last_success_at']}  {row['last_error'] or ''}")
    if args.show:
        print("\nAdvisories:")
        for r in conn.execute("SELECT source, severity, title FROM advisories ORDER BY source, severity"):
            print(f"  [{r['source']}] {r['severity']}: {r['title'][:110]}")
        print("\nHeadlines:")
        for r in conn.execute("SELECT source, published_at, title, tags FROM news ORDER BY published_at DESC LIMIT 15"):
            print(f"  [{r['source']}] {r['published_at'] or 'no date'}  {r['title'][:90]}  ({r['tags']})")
    conn.close()


if __name__ == "__main__":
    main()
