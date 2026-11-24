"""Headlines from GDELT's free DOC 2.0 API (no key). It is a shared public service: about one request every
5 seconds, and when it is busy it answers with plain text instead of JSON, which is treated as an error."""
import json
import re
import sqlite3
from datetime import datetime, timezone

from .. import config
from ..timeutil import iso, utc_now
from .news_store import save_news, too_old
from .text import clean_text, clean_url, fetch, hazard_tags, place_tags

NAME = "gdelt"
LANGUAGES = {"", "english", "filipino", "tagalog"}


def _seen(value):
    try:
        return iso(datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc))
    except (TypeError, ValueError):
        return None


def parse_articles(payload: dict, now) -> tuple[int, list[dict]]:
    articles = payload.get("articles") or []
    out, seen_titles = [], set()
    for a in articles:
        url, title = clean_url(a.get("url")), clean_text(a.get("title"), 200)
        if not url or not title or (a.get("language") or "").lower() not in LANGUAGES:
            continue
        key = re.sub(r"\W+", "", title.lower())                  # syndicated copies of one story appear many times
        if key in seen_titles:
            continue
        tags = hazard_tags(title)
        places = place_tags(title)
        philippine = ((a.get("sourcecountry") or "").lower() == "philippines" or places
                      or "philippine" in title.lower() or (a.get("domain") or "").endswith(".ph"))
        published = _seen(a.get("seendate"))
        if not tags or not philippine or too_old(published, now):
            continue
        seen_titles.add(key)
        out.append({"url": url, "title": title, "summary": "", "source": clean_text(a.get("domain"), 80) or "GDELT",
                    "published_at": published, "tags": ",".join(tags + places)})
    return len(articles), out


def refresh(conn: sqlite3.Connection, client, now=None) -> dict:
    now = now or utc_now()
    resp = fetch(client, config.GDELT_URL, params={
        "query": config.GDELT_QUERY, "mode": "ArtList", "format": "json", "sort": "DateDesc",
        "maxrecords": config.GDELT_MAX_RECORDS, "timespan": config.GDELT_TIMESPAN})
    if "json" not in resp.headers.get("content-type", "").lower():
        raise ValueError("GDELT did not return JSON (probably busy or rate limited)")
    try:
        payload = json.loads(resp.text)
    except ValueError as exc:
        raise ValueError("GDELT returned invalid JSON") from exc
    _, items = parse_articles(payload, now)
    return {"saved": save_news(conn, items, now), "errors": []}
