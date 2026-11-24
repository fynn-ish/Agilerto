"""PAGASA Tropical Cyclone Bulletin page. PAGASA publishes no data feed, so this reads the page.

Three outcomes, and only two of them are ever saved:
  none     the page says there is no active tropical cyclone in the Philippine Area of Responsibility
  active   a bulletin PDF is linked. We save the link only. We do NOT read the PDF (signals and areas are inside it)
  unknown  the page looks different. That is an ERROR. It is never treated as "no cyclone".

Checked against the live page on 22 Nov 2026 for the 'none' state. The 'active' layout has not been seen
and is detected by a PDF link, so it is the most likely thing to need a fix."""
import html
import re
import sqlite3
from urllib.parse import urlparse

from .. import config
from ..timeutil import iso, utc_now
from .text import clean_text, clean_url, fetch

NAME = "pagasa"
EXT_ID = "pagasa:tc-bulletin"
NONE_RX = re.compile(r"no\s+active\s+tropical\s+cyclone\s+within\s+the\s+philippine\s+area\s+of\s+responsibility", re.I)
PDF_RX = re.compile(r"""(?:href|src|data)\s*=\s*["']([^"']+?\.pdf[^"']*)["']""", re.I)


def parse_page(page_html: str, page_url: str) -> dict:
    plain = html.unescape(re.sub(r"<[^>]+>", " ", page_html))      # "No&nbsp;Active" must still match
    if NONE_RX.search(plain):
        return {"state": "none"}
    pdfs = []
    for raw in PDF_RX.findall(page_html):
        u = clean_url(raw, base=page_url)
        if u and (urlparse(u).hostname or "").endswith("pagasa.dost.gov.ph") and u not in pdfs:
            pdfs.append(u)
    if pdfs:
        return {"state": "active", "pdfs": pdfs}
    raise ValueError("unrecognised PAGASA bulletin page layout (not treated as 'no cyclone')")


def refresh(conn: sqlite3.Connection, client, now=None) -> dict:
    now_iso = iso(now or utc_now())
    url = config.PAGASA_BULLETIN_URL
    result = parse_page(fetch(client, url).text, url)
    if result["state"] == "none":
        rec = {
            "title": "PAGASA bulletin page: no active tropical cyclone within the Philippine Area of Responsibility",
            "body": ("This covers tropical cyclones only. It does not cover rainfall, thunderstorm, flood, or volcano "
                     "warnings. Check PAGASA, PHIVOLCS, and your local DRRMO for those."),
            "severity": "None", "category": "status", "url": url,
        }
    else:
        n = len(result["pdfs"])
        rec = {
            "title": "PAGASA has published a Tropical Cyclone Bulletin" + (f" ({n} documents)" if n > 1 else ""),
            "body": ("Wind signals and affected areas are in the bulletin PDF. This system does not read the PDF. "
                     "Open it on the PAGASA site."),
            "severity": "Bulletin", "category": "tropical_cyclone", "url": result["pdfs"][0],
        }
    conn.execute(
        """INSERT INTO advisories (ext_id,source,title,body,severity,category,area,issued_at,expires_at,url,lat,lng,fetched_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,NULL,NULL,?)
           ON CONFLICT(ext_id) DO UPDATE SET title=excluded.title, body=excluded.body, severity=excluded.severity,
             category=excluded.category, area=excluded.area, issued_at=excluded.issued_at, url=excluded.url,
             fetched_at=excluded.fetched_at""",
        (EXT_ID, "PAGASA", clean_text(rec["title"], 200), clean_text(rec["body"], 450), rec["severity"],
         rec["category"], "Philippine Area of Responsibility", None, None, rec["url"], now_iso),
    )
    conn.commit()
    return {"saved": 1, "errors": [], "state": result["state"]}
