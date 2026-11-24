"""Headlines from Philippine news RSS feeds (RSS 2.0 or Atom). Only items about hazards are kept.
Each feed fails on its own. Some outlets block automated requests, which shows up as an HTTP error."""
import sqlite3

from .. import config
from ..timeutil import utc_now
from .base import short_error
from .news_store import save_news, too_old
from .text import clean_text, clean_url, fetch, hazard_tags, parse_date, place_tags, safe_xml

NAME = "rss"
ATOM = "{http://www.w3.org/2005/Atom}"
DC = "{http://purl.org/dc/elements/1.1/}"


def _text(el):
    return el.text.strip() if el is not None and el.text and el.text.strip() else None


def _entries(root):
    """(title, link, summary, date) for every RSS <item> or Atom <entry>."""
    if root.tag.lower().endswith("feed"):
        for e in root.iter(ATOM + "entry"):
            link = next((l.get("href") for l in e.findall(ATOM + "link") if l.get("rel") in (None, "alternate")), None)
            yield (_text(e.find(ATOM + "title")), link,
                   _text(e.find(ATOM + "summary")) or _text(e.find(ATOM + "content")),
                   _text(e.find(ATOM + "published")) or _text(e.find(ATOM + "updated")))
    else:
        for it in root.iter("item"):
            guid = it.find("guid")
            link = _text(it.find("link")) or (_text(guid) if guid is not None and guid.get("isPermaLink") != "false" else None)
            yield (_text(it.find("title")), link, _text(it.find("description")),
                   _text(it.find("pubDate")) or _text(it.find(DC + "date")))


def parse_feed(xml_text: str, source_name: str, now) -> tuple[int, list[dict]]:
    """(entries in the feed, hazard-related items worth saving)."""
    root = safe_xml(xml_text)
    total, out, seen = 0, [], set()
    for title, link, summary, date in _entries(root):
        total += 1
        url, title_c = clean_url(link), clean_text(title, 200)
        if not url or not title_c or url in seen:
            continue
        summary_c = clean_text(summary, 300)
        if summary_c.lower().startswith(title_c.lower()[:60]):
            summary_c = ""                                   # many feeds repeat the headline as the summary
        tags = hazard_tags(f"{title_c} {summary_c}")
        published = parse_date(date)
        if not tags or too_old(published, now):
            continue
        seen.add(url)
        out.append({"url": url, "title": title_c, "summary": summary_c, "source": source_name,
                    "published_at": published, "tags": ",".join(tags + place_tags(f"{title_c} {summary_c}"))})
    return total, out


def refresh(conn: sqlite3.Connection, client, now=None) -> dict:
    now = now or utc_now()
    saved, errors = 0, []
    for feed in config.NEWS_FEEDS:
        try:
            total, items = parse_feed(fetch(client, feed["url"]).text, feed["name"], now)
            if total == 0:
                raise ValueError("the feed had no entries")
            saved += save_news(conn, items, now)
        except Exception as exc:                              # one blocked or broken feed must not stop the others
            conn.rollback()
            errors.append(f"{feed['name']}: {short_error(exc)}")
    return {"saved": saved, "errors": errors}
