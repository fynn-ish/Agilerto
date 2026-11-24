"""Helpers for text that comes from the internet. Treat all of it as untrusted:
strip markup, limit length, neutralise things that could fake a citation, and only accept plain web links."""
import html
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin

from .. import config
from ..timeutil import iso

_SCRIPT_RX = re.compile(r"<(script|style)\b[^>]*>.*?</\1\s*>", re.I | re.S)
_TAG_RX = re.compile(r"<[^>]*>")
_CTRL_RX = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f\u200b-\u200f\u202a-\u202e\u2066-\u2069]")


def clean_text(value, max_len: int = 300) -> str:
    """Plain, single-line text. Square brackets become round ones so a headline can never look like a
    citation such as [1]. Hidden control and direction-override characters are removed."""
    if not value:
        return ""
    s = html.unescape(str(value))
    s = _SCRIPT_RX.sub(" ", s)
    s = _TAG_RX.sub(" ", s)
    s = html.unescape(s)
    s = _CTRL_RX.sub("", s)
    s = s.replace("[", "(").replace("]", ")")
    s = re.sub(r"\s+", " ", s).strip()
    return s if len(s) <= max_len else s[: max_len - 1].rstrip() + "\u2026"


def clean_url(value, base: str | None = None) -> str | None:
    """Only plain http(s) links are kept (no javascript:, data:, or file: links)."""
    if not value:
        return None
    u = html.unescape(str(value)).strip()
    if base:
        u = urljoin(base, u)
    if not re.match(r"^https?://[^\s<>\"']+$", u, re.I) or len(u) > 500:
        return None
    return u


def safe_xml(text: str) -> ET.Element:
    """Parse untrusted XML. Documents that declare entities or a DOCTYPE are refused (entity-expansion attacks)."""
    text = text.lstrip("\ufeff \t\r\n")
    if re.search(r"<!\s*(DOCTYPE|ENTITY)", text, re.I):
        raise ValueError("refused XML with a DOCTYPE or ENTITY declaration")
    try:
        return ET.fromstring(text)
    except ET.ParseError as exc:
        raise ValueError(f"invalid XML: {exc}") from exc


def fetch(client, url: str, params: dict | None = None):
    """GET with redirects and a size limit. Raises on HTTP errors."""
    resp = client.get(url, params=params, follow_redirects=True)
    resp.raise_for_status()
    if len(resp.content) > config.MAX_RESPONSE_BYTES:
        raise ValueError("response too large")
    return resp


def parse_date(value) -> str | None:
    """RFC 822 (RSS) or ISO 8601 date -> UTC ISO string ending in Z, or None."""
    if not value:
        return None
    value = str(value).strip()
    try:
        dt = parsedate_to_datetime(value)
    except (TypeError, ValueError, IndexError):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return iso(dt)


# ---------- tags used to find relevant, local news ----------
_HAZARDS = {
    "typhoon": r"typhoon|bagyo|tropical (?:storm|depression|cyclone)|signal no|wind signal|low pressure area|\blpa\b|\btcws\b",
    "earthquake": r"earthquake|lindol|magnitude|aftershock|phivolcs|tsunami",
    "flood": r"flood|\bbaha\b|flooding|inundat|rainfall warning|heavy rain",
    "landslide": r"landslide|mudslide|\bguho\b|pagguho",
    "volcano": r"\btaal\b|volcano|volcanic|bulkan|ashfall|ash fall|eruption|phreatic",
    "evacuation": r"evacuat|lumikas|evacuee",
}
_PLACES = {
    "batangas": r"batangas|\blipa\b|tanauan|santo tomas|\btaal\b|nasugbu|lemery|balayan|calaca|\bbauan\b|lobo|\blian\b|rosario|san jose, batangas",
    "laguna": r"laguna|calamba|santa rosa|san pablo|los ba[nñ]os|bi[nñ]an|cabuyao|san pedro|laguna de bay",
    "cavite": r"cavite|\bimus\b|tagaytay|dasmari[nñ]as|bacoor|kawit|trece martires|silang|carmona",
    "quezon": r"quezon province|lucena|tayabas|lucban|pagbilao|mauban|infanta, quezon|real, quezon",
    "rizal": r"\brizal\b|antipolo|cainta|taytay|angono|rodriguez, rizal",
    "calabarzon": r"calabarzon|region iv-a|region 4-a|southern luzon",
}
_HAZARD_RX = {k: re.compile(v, re.I) for k, v in _HAZARDS.items()}
_PLACE_RX = {k: re.compile(v, re.I) for k, v in _PLACES.items()}


def hazard_tags(text: str) -> list[str]:
    return [k for k, rx in _HAZARD_RX.items() if rx.search(text)]


def place_tags(text: str) -> list[str]:
    return [k for k, rx in _PLACE_RX.items() if rx.search(text)]
