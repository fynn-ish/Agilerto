"""Offline map tiles. One PMTiles file (a single archive of vector map tiles) is served from this computer
with HTTP Range support, so the map works without internet. The browser reads only the pieces it needs.

PMTiles format: https://github.com/protomaps/PMTiles/blob/main/spec/v3/spec.md"""
import gzip
import html
import json
import re
import struct
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response, StreamingResponse

from . import config

HEADER_LEN = 127
TILE_TYPES = {0: "unknown", 1: "vector", 2: "png", 3: "jpeg", 4: "webp", 5: "avif"}
COMPRESSION = {0: "unknown", 1: "none", 2: "gzip", 3: "brotli", 4: "zstd"}
NAME_RX = re.compile(r"^[A-Za-z0-9._-]{1,100}\.pmtiles$")
MIN_SCHEMA_MAJOR = 4          # protomaps-leaflet 5 only draws Protomaps basemap schema 4 and newer

public_router = APIRouter()   # /tiles/<file>.pmtiles
api_router = APIRouter()      # /api/tiles/info


def tiles_dir() -> Path:
    from .db import BASE_DIR
    return Path(config.TILES_DIR) if config.TILES_DIR else BASE_DIR / "data" / "tiles"


def read_header(path: Path) -> dict:
    with open(path, "rb") as f:
        b = f.read(HEADER_LEN)
    if len(b) < HEADER_LEN or b[:7] != b"PMTiles":
        raise ValueError("not a PMTiles file")
    if b[7] != 3:
        raise ValueError(f"PMTiles version {b[7]} is not supported (need version 3)")
    (root_off, root_len, meta_off, meta_len, *_rest) = struct.unpack_from("<11Q", b, 8)
    clustered, internal_comp, tile_comp, tile_type, min_zoom, max_zoom = b[96:102]
    min_lon, min_lat, max_lon, max_lat = (v / 1e7 for v in struct.unpack_from("<4i", b, 102))
    center_lon, center_lat = (v / 1e7 for v in struct.unpack_from("<2i", b, 119))
    return {
        "metadata_offset": meta_off, "metadata_length": meta_len, "internal_compression": internal_comp,
        "tile_compression": COMPRESSION.get(tile_comp, "unknown"), "tile_type": TILE_TYPES.get(tile_type, "unknown"),
        "minzoom": min_zoom, "maxzoom": max_zoom, "bounds": [min_lon, min_lat, max_lon, max_lat],
        "center": [center_lon, center_lat, b[118]], "clustered": bool(clustered),
    }


def read_metadata(path: Path, header: dict) -> dict:
    try:
        with open(path, "rb") as f:
            f.seek(header["metadata_offset"])
            raw = f.read(min(header["metadata_length"], 2_000_000))
        if header["internal_compression"] == 2:
            raw = gzip.decompress(raw)
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError, EOFError):
        return {}


def find_file() -> Path | None:
    d = tiles_dir()
    wanted = d / config.TILES_FILE
    if wanted.is_file():
        return wanted
    others = sorted(p for p in d.glob("*.pmtiles") if p.is_file()) if d.is_dir() else []
    return others[0] if others else None


def describe(path: Path) -> dict:
    """What is in the tile file, and whether the map can use it. Never raises."""
    info = {"available": True, "usable": False, "file": path.name, "url": f"/tiles/{path.name}",
            "size_bytes": path.stat().st_size}
    try:
        h = read_header(path)
    except (OSError, ValueError) as exc:
        return {**info, "reason": f"The tile file cannot be read: {exc}"}
    meta = read_metadata(path, h)
    version = str(meta.get("version", ""))
    major = int(m.group(1)) if (m := re.match(r"(\d+)\.", version + ".")) else None
    info.update({k: h[k] for k in ("tile_type", "tile_compression", "minzoom", "maxzoom", "bounds", "center")})
    info.update({"name": meta.get("name"), "schema_version": version or None,
                 "attribution": html.unescape(re.sub(r"<[^>]+>", "", meta.get("attribution", "") or "")) or None})
    if h["tile_type"] != "vector":
        info["reason"] = f"This is a {h['tile_type']} tile file. Only vector tiles (Protomaps basemap) are supported."
    elif h["tile_compression"] not in ("gzip", "none"):
        info["reason"] = f"Tile compression '{h['tile_compression']}' is not supported (need gzip)."
    elif major is not None and major < MIN_SCHEMA_MAJOR:
        info["reason"] = (f"This tile file uses an older Protomaps schema ({version}). Extract a new one from a current "
                          f"Protomaps build (version {MIN_SCHEMA_MAJOR} or newer).")
    else:
        info["usable"] = True
        if major is None:
            info["note"] = "The file does not say which schema version it uses, so it could not be checked."
    return info


@api_router.get("/tiles/info")
def tiles_info():
    path = find_file()
    if not path:
        return {"available": False, "usable": False,
                "reason": "No tile file found. Run `python get_tiles.py` (needs internet once) and copy the file to backend/data/tiles/."}
    return describe(path)


# ---------- the file itself, with Range support ----------
def _etag(path: Path) -> str:
    st = path.stat()
    return f'"{st.st_size:x}-{st.st_mtime_ns:x}"'


def parse_range(header: str, size: int) -> tuple[int, int] | None:
    """'bytes=START-END' -> (start, end) inclusive. None means the header is invalid or unsatisfiable."""
    m = re.fullmatch(r"bytes=(\d*)-(\d*)", header.strip())
    if not m or (not m.group(1) and not m.group(2)):
        return None
    if not m.group(1):                                    # bytes=-N : the last N bytes
        n = int(m.group(2))
        return (max(size - n, 0), size - 1) if n > 0 else None
    start = int(m.group(1))
    end = min(int(m.group(2)), size - 1) if m.group(2) else size - 1
    return (start, end) if start <= end and start < size else None


def _iter_file(path: Path, start: int, end: int, chunk: int = 1 << 20):
    with open(path, "rb") as f:
        f.seek(start)
        left = end - start + 1
        while left > 0:
            data = f.read(min(chunk, left))
            if not data:
                break
            left -= len(data)
            yield data


@public_router.api_route("/tiles/{name}", methods=["GET", "HEAD"])
def tile_file(name: str, request: Request):
    if not NAME_RX.fullmatch(name):
        raise HTTPException(404, "Not found")
    path = (tiles_dir() / name).resolve()
    if path.parent != tiles_dir().resolve() or not path.is_file():
        raise HTTPException(404, "Not found")
    size, etag = path.stat().st_size, _etag(path)
    headers = {"Accept-Ranges": "bytes", "ETag": etag, "Cache-Control": "no-cache"}

    if_match = request.headers.get("if-match")
    if if_match and if_match.strip() not in ("*", etag):          # the file was replaced while the page was open
        return Response(status_code=412, headers=headers)

    rng = request.headers.get("range")
    if rng:
        parsed = parse_range(rng, size)
        if not parsed:
            return Response(status_code=416, headers={**headers, "Content-Range": f"bytes */{size}"})
        start, end = parsed
        headers |= {"Content-Range": f"bytes {start}-{end}/{size}", "Content-Length": str(end - start + 1)}
        status = 206
    else:
        start, end, status = 0, size - 1, 200
        headers["Content-Length"] = str(size)

    if request.method == "HEAD":
        return Response(status_code=status, headers=headers, media_type="application/octet-stream")
    return StreamingResponse(_iter_file(path, start, end), status_code=status, headers=headers,
                             media_type="application/octet-stream")
