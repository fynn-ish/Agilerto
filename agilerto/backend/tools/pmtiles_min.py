"""A tiny, dependency-free PMTiles v3 writer and vector-tile (MVT) encoder.
Used to make small TEST archives (see make_test_tiles.py) and for the automated tests.
It is NOT a map data tool: real map tiles come from `python get_tiles.py`."""
import gzip
import struct

# ---------- PMTiles ----------
def zxy_to_tileid(z: int, x: int, y: int) -> int:
    """Hilbert-curve tile id, exactly as in the PMTiles specification."""
    acc = ((1 << (2 * z)) - 1) // 3
    n = 1 << z
    if x >= n or y >= n:
        raise ValueError("tile outside the zoom level")
    d, s = 0, n >> 1
    while s > 0:
        rx = 1 if x & s else 0
        ry = 1 if y & s else 0
        d += s * s * ((3 * rx) ^ ry)
        if ry == 0:                                   # rotate
            if rx == 1:
                x, y = s - 1 - x, s - 1 - y
            x, y = y, x
        s >>= 1
    return acc + d


def _varint(n: int) -> bytes:
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            out.append(b | 0x80)
        else:
            out.append(b)
            return bytes(out)


def _directory(entries: list[tuple[int, int, int]]) -> bytes:
    """entries = [(tile_id, offset, length)] sorted by tile_id. Serialised as the spec describes, then gzipped."""
    out = bytearray(_varint(len(entries)))
    last = 0
    for tid, _, _ in entries:
        out += _varint(tid - last)
        last = tid
    for _ in entries:
        out += _varint(1)                              # run length
    for _, _, length in entries:
        out += _varint(length)
    prev_end = 0
    for i, (_, offset, length) in enumerate(entries):
        out += _varint(0 if i > 0 and offset == prev_end else offset + 1)
        prev_end = offset + length
    return gzip.compress(bytes(out), mtime=0)


def write_pmtiles(path, tiles: dict[int, bytes], *, tile_type=1, tile_compression=2, min_zoom, max_zoom,
                  bounds, center_zoom=0, metadata=None, version=3):
    """tiles: {tile_id: tile bytes (already compressed as tile_compression says)}. bounds: (w, s, e, n) degrees."""
    import json
    ids = sorted(tiles)
    data, entries, offset = bytearray(), [], 0
    for tid in ids:
        entries.append((tid, offset, len(tiles[tid])))
        data += tiles[tid]
        offset += len(tiles[tid])
    root = _directory(entries)
    meta = gzip.compress(json.dumps(metadata or {}).encode(), mtime=0)
    root_off, meta_off = 127, 127 + len(root)
    leaf_off = meta_off + len(meta)
    data_off = leaf_off
    w, s, e, n = bounds
    header = bytearray(b"PMTiles") + bytes([version])
    header += struct.pack("<11Q", root_off, len(root), meta_off, len(meta), leaf_off, 0, data_off, len(data),
                          len(ids), len(ids), len(ids))
    header += bytes([1, 2, tile_compression, tile_type, min_zoom, max_zoom])
    header += struct.pack("<4i", *(int(round(v * 1e7)) for v in (w, s, e, n)))
    header += bytes([center_zoom]) + struct.pack("<2i", int(round((w + e) / 2 * 1e7)), int(round((s + n) / 2 * 1e7)))
    assert len(header) == 127
    with open(path, "wb") as f:
        f.write(header + root + meta + data)


# ---------- Mapbox Vector Tile (protobuf) ----------
def _zigzag(n: int) -> int:
    return (n << 1) ^ (n >> 63)


def _field(num: int, wire: int, payload: bytes) -> bytes:
    return _varint((num << 3) | wire) + payload


def _len(num: int, data: bytes) -> bytes:
    return _field(num, 2, _varint(len(data)) + data)


def _geometry(kind: str, parts) -> list[int]:
    """parts: point -> [(x, y)]; line -> [[(x, y), ...]]; polygon -> [[(x, y), ...]] (rings). Tile coordinates."""
    cmds, cx, cy = [], 0, 0
    if kind == "point":
        cmds.append((1 & 7) | (len(parts) << 3))
        for x, y in parts:
            cmds += [_zigzag(x - cx), _zigzag(y - cy)]
            cx, cy = x, y
        return cmds
    for ring in parts:
        x0, y0 = ring[0]
        cmds += [(1 & 7) | (1 << 3), _zigzag(x0 - cx), _zigzag(y0 - cy)]
        cx, cy = x0, y0
        rest = ring[1:]
        if kind == "polygon" and rest and rest[0] == rest[-1]:
            rest = rest[:-1]
        cmds.append((2 & 7) | (len(rest) << 3))
        for x, y in rest:
            cmds += [_zigzag(x - cx), _zigzag(y - cy)]
            cx, cy = x, y
        if kind == "polygon":
            cmds.append(7 & 7 | (1 << 3))
    return cmds


def encode_layer(name: str, features: list[dict], extent: int = 4096) -> bytes:
    """features: [{'type': 'point'|'line'|'polygon', 'geometry': ..., 'props': {...}}]"""
    keys, values, body = [], [], b""
    for f in features:
        tags = []
        for k, v in f.get("props", {}).items():
            if k not in keys:
                keys.append(k)
            val = (_len(1, v.encode()) if isinstance(v, str)
                   else _field(5, 0, _varint(int(v))))                     # uint_value
            if val not in values:
                values.append(val)
            tags += [keys.index(k), values.index(val)]
        geom = _geometry(f["type"], f["geometry"])
        feat = (_len(2, b"".join(_varint(t) for t in tags)) +
                _field(3, 0, _varint({"point": 1, "line": 2, "polygon": 3}[f["type"]])) +
                _len(4, b"".join(_varint(g) for g in geom)))
        body += _len(2, feat)
    out = _field(15, 0, _varint(2)) + _len(1, name.encode()) + body
    out += b"".join(_len(3, k.encode()) for k in keys) + b"".join(_len(4, v) for v in values)
    return _len(3, out + _field(5, 0, _varint(extent)))                   # layer inside the tile message


def encode_tile(layers: dict[str, list[dict]]) -> bytes:
    return gzip.compress(b"".join(encode_layer(n, fs) for n, fs in layers.items() if fs), mtime=0)
