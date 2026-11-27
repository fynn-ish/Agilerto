"""Make a small SYNTHETIC test tile file, so the offline map can be tried without downloading real map data.

    python tools/make_test_tiles.py                       # writes data/tiles/test.pmtiles around Lipa City
    python tools/make_test_tiles.py --out some.pmtiles --lat 14.08 --lng 121.15

The roads, lake and buildings are invented. The map is labeled "TEST TILES, NOT A REAL MAP" on purpose,
so it can never be mistaken for real geography. For the real thing run `python get_tiles.py`.
"""
import argparse
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.pmtiles_min import encode_tile, write_pmtiles, zxy_to_tileid  # noqa: E402

EXTENT = 4096


def world(lng: float, lat: float, z: int) -> tuple[float, float]:
    """lon/lat -> fractional tile coordinates at zoom z."""
    n = 1 << z
    x = (lng + 180.0) / 360.0 * n
    y = (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n
    return x, y


def build(lat0: float, lng0: float, half_deg: float = 0.05):
    south, north, west, east = lat0 - half_deg, lat0 + half_deg, lng0 - half_deg * 1.4, lng0 + half_deg * 1.4

    def poly(points):
        return [points + [points[0]]]

    # invented geography, in lon/lat
    lake = [(lng0 - 0.045, lat0 - 0.02), (lng0 - 0.015, lat0 - 0.035), (lng0 - 0.005, lat0 + 0.005),
            (lng0 - 0.03, lat0 + 0.02), (lng0 - 0.05, lat0 + 0.005)]
    park = [(lng0 + 0.01, lat0 + 0.01), (lng0 + 0.03, lat0 + 0.01), (lng0 + 0.03, lat0 + 0.025), (lng0 + 0.01, lat0 + 0.025)]
    earth = [(west - 1, south - 1), (east + 1, south - 1), (east + 1, north + 1), (west - 1, north + 1)]
    highway = [(west, lat0 - 0.012), (lng0, lat0), (east, lat0 + 0.012)]
    major = [(lng0, south), (lng0 + 0.004, lat0), (lng0, north)]
    minors = [[(west, lat0 + k * 0.01), (east, lat0 + k * 0.01 + 0.002)] for k in (-2, -1, 1, 2)]
    houses = [[(lng0 + dx, lat0 + dy), (lng0 + dx + 0.0008, lat0 + dy), (lng0 + dx + 0.0008, lat0 + dy + 0.0006),
               (lng0 + dx, lat0 + dy + 0.0006)] for dx in (0.002, 0.004, 0.006) for dy in (-0.003, -0.0015, 0.0015)]

    def pts(coords):                                     # for each zoom the same lon/lat is converted to that tile grid
        return coords

    layers = [
        ("earth", [("polygon", [earth], {})]),
        ("landuse", [("polygon", [park + [park[0]]], {"kind": "park"})]),
        ("water", [("polygon", [lake + [lake[0]]], {"kind": "lake"}),
                   ("point", [((lake[0][0] + lake[2][0]) / 2, (lake[0][1] + lake[2][1]) / 2)],
                    {"kind": "lake", "name": "TEST LAKE (invented)"})]),
        ("roads", [("line", [highway], {"kind": "highway", "name": "TEST HIGHWAY"}),
                   ("line", [major], {"kind": "major_road", "name": "TEST ROAD"})] +
                  [("line", [m], {"kind": "minor_road", "name": "TEST STREET"}) for m in minors]),
        ("buildings", [("polygon", [h + [h[0]]], {}) for h in houses]),
        ("places", [("point", [(lng0, lat0)], {"kind": "locality", "kind_detail": "city", "name": "TEST CITY", "min_zoom": 3, "population_rank": 10}),
                    ("point", [(lng0 + 0.02, lat0 - 0.025)], {"kind": "locality", "kind_detail": "town", "name": "TEST TILES, NOT A REAL MAP", "min_zoom": 5})]),
    ]
    return layers, (west, south, east, north)


def tiles_for(layers, bounds, min_zoom, max_zoom):
    west, south, east, north = bounds
    tiles = {}
    for z in range(min_zoom, max_zoom + 1):
        x0, y1 = world(west, south, z)
        x1, y0 = world(east, north, z)
        for tx in range(int(x0), int(x1) + 1):
            for ty in range(int(y0), int(y1) + 1):
                content = {}
                for name, feats in layers:
                    out = []
                    for kind, geom, props in feats:
                        def to_tile(lng, lat):
                            fx, fy = world(lng, lat, z)
                            return int(round((fx - tx) * EXTENT)), int(round((fy - ty) * EXTENT))
                        if kind == "point":
                            parts = [to_tile(*p) for p in geom]
                            if not all(-64 <= x <= EXTENT + 64 and -64 <= y <= EXTENT + 64 for x, y in parts):
                                continue
                        else:
                            parts = [[to_tile(*p) for p in ring] for ring in geom]
                            xs = [x for ring in parts for x, _ in ring]
                            ys = [y for ring in parts for _, y in ring]
                            if max(xs) < -64 or min(xs) > EXTENT + 64 or max(ys) < -64 or min(ys) > EXTENT + 64:
                                continue
                        out.append({"type": kind, "geometry": parts, "props": props})
                    if out:
                        content[name] = out
                if content:
                    tiles[zxy_to_tileid(z, tx, ty)] = encode_tile(content)
    return tiles


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent.parent / "data" / "tiles" / "test.pmtiles"))
    ap.add_argument("--lat", type=float, default=13.9411)
    ap.add_argument("--lng", type=float, default=121.1631)
    ap.add_argument("--maxzoom", type=int, default=14)
    a = ap.parse_args()
    layers, bounds = build(a.lat, a.lng)
    tiles = tiles_for(layers, bounds, 0, a.maxzoom)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    write_pmtiles(a.out, tiles, min_zoom=0, max_zoom=a.maxzoom, bounds=bounds, center_zoom=11,
                  metadata={"name": "TEST TILES (synthetic, not a real map)", "version": "4.0.0",
                            "attribution": "Synthetic test data", "type": "baselayer"})
    print(f"Wrote {a.out}: {len(tiles)} tiles, {Path(a.out).stat().st_size / 1024:.0f} KB. These are INVENTED test tiles, not a real map.")


if __name__ == "__main__":
    main()
