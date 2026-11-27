"""Download an offline map for your area. Needs internet ONCE, on any computer. Then copy the file to the device
that runs Agilerto (backend/data/tiles/). The finished file works with no internet at all.

    python get_tiles.py                          # Calabarzon, up to zoom 14
    python get_tiles.py --dry-run                # shows how big the download would be, saves nothing
    python get_tiles.py --area batangas --maxzoom 13
    python get_tiles.py --area lipa              # a small area: quick to try
    python get_tiles.py --bbox 120.9,13.7,121.5,14.2
    python get_tiles.py --source https://build.protomaps.com/20260101.pmtiles   # a build you picked yourself
    python get_tiles.py --download-cli           # fetch the official `pmtiles` tool first (GitHub release)

How it works: Protomaps publishes a whole-world map every day. The official `pmtiles` tool copies only the part
you ask for (using HTTP range requests). Map data (c) OpenStreetMap contributors (ODbL).

Size depends mostly on --maxzoom (each extra zoom level is roughly 2 to 4 times bigger) and less on the area.
Use --dry-run first. If the `pmtiles` program is blocked on your computer (for example by an Application Control
policy), run this on another computer and copy the .pmtiles file over. The device that serves the map needs no program.
"""
import argparse
import datetime as dt
import io
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import urllib.request
import zipfile
from pathlib import Path

from app import config
from app.tiles import describe, tiles_dir

BUILD_URL = "https://build.protomaps.com/{date}.pmtiles"
RELEASE_API = "https://api.github.com/repos/protomaps/go-pmtiles/releases/latest"
AREAS = {                                   # min_lon,min_lat,max_lon,max_lat (approximate, generous)
    "calabarzon": "120.5,13.0,122.6,14.9",
    "batangas": "120.4,13.5,121.6,14.3",
    "lipa": "121.0,13.8,121.35,14.1",
}
HERE = Path(__file__).resolve().parent


# ---------- pieces that can be tested without internet ----------
def pick_asset(names: list[str], system: str, machine: str) -> str | None:
    """Choose the right release file for this computer, e.g. 'go-pmtiles_1.31.2_Windows_x86_64.zip'."""
    os_key = {"Windows": "Windows", "Linux": "Linux", "Darwin": "Darwin"}.get(system)
    arch = "arm64" if machine.lower() in ("arm64", "aarch64") else "x86_64"
    for n in names:
        if os_key and os_key in n and arch in n and n.endswith((".zip", ".tar.gz")):
            return n
    return None


def find_latest_build(head_ok, today: dt.date, days: int = 14) -> str | None:
    """Newest daily build URL that exists. `head_ok(url) -> bool` is passed in so this can be tested."""
    for back in range(days):
        url = BUILD_URL.format(date=(today - dt.timedelta(days=back)).strftime("%Y%m%d"))
        if head_ok(url):
            return url
    return None


def parse_bbox(text: str) -> str:
    try:
        w, s, e, n = (float(x) for x in text.split(","))
    except ValueError:
        raise SystemExit("--bbox must be four numbers: min_lon,min_lat,max_lon,max_lat")
    if not (-180 <= w < e <= 180 and -90 <= s < n <= 90):
        raise SystemExit("--bbox is not valid (min must be smaller than max, lon -180..180, lat -90..90)")
    return f"{w},{s},{e},{n}"


# ---------- the parts that need internet ----------
def head_ok(url: str) -> bool:
    try:
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "agilerto-get-tiles"})
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status == 200
    except OSError:
        return False


def download_cli() -> Path:
    import json
    with urllib.request.urlopen(urllib.request.Request(RELEASE_API, headers={"User-Agent": "agilerto-get-tiles"}), timeout=30) as r:
        release = json.load(r)
    assets = {a["name"]: a["browser_download_url"] for a in release["assets"]}
    name = pick_asset(list(assets), platform.system(), platform.machine())
    if not name:
        raise SystemExit(f"No pmtiles download for {platform.system()} {platform.machine()}. See https://github.com/protomaps/go-pmtiles/releases")
    print(f"Downloading {name} ...")
    with urllib.request.urlopen(assets[name], timeout=120) as r:
        blob = r.read()
    dest = HERE / "tools" / "bin"
    dest.mkdir(parents=True, exist_ok=True)
    exe = "pmtiles.exe" if platform.system() == "Windows" else "pmtiles"
    if name.endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(blob)) as z:
            member = next(m for m in z.namelist() if Path(m).name == exe)
            (dest / exe).write_bytes(z.read(member))
    else:
        with tarfile.open(fileobj=io.BytesIO(blob), mode="r:gz") as t:
            member = next(m for m in t.getmembers() if Path(m.name).name == exe)
            (dest / exe).write_bytes(t.extractfile(member).read())
    (dest / exe).chmod(0o755)
    print(f"Saved {dest / exe}")
    return dest / exe


def find_cli(explicit: str | None) -> Path | None:
    exe = "pmtiles.exe" if platform.system() == "Windows" else "pmtiles"
    for cand in (explicit, os.getenv("PMTILES_CLI"), HERE / "tools" / "bin" / exe, shutil.which("pmtiles")):
        if cand and Path(cand).is_file():
            return Path(cand)
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description="Download an offline map (PMTiles) for your area.")
    ap.add_argument("--area", choices=sorted(AREAS), default="calabarzon")
    ap.add_argument("--bbox", help="min_lon,min_lat,max_lon,max_lat (overrides --area)")
    ap.add_argument("--maxzoom", type=int, default=14, help="14 is sharp enough for streets; lower is much smaller")
    ap.add_argument("--source", help="a .pmtiles URL or file to copy from (default: the newest Protomaps daily build)")
    ap.add_argument("--out", help=f"output file (default: data/tiles/{config.TILES_FILE})")
    ap.add_argument("--cli", help="path to the pmtiles program")
    ap.add_argument("--download-cli", action="store_true", help="download the official pmtiles program first")
    ap.add_argument("--dry-run", action="store_true", help="only show what would be downloaded")
    a = ap.parse_args()

    if not 1 <= a.maxzoom <= 15:
        raise SystemExit("--maxzoom must be between 1 and 15")
    bbox = parse_bbox(a.bbox or AREAS[a.area])

    cli = find_cli(a.cli)
    if not cli and a.download_cli:
        cli = download_cli()
    if not cli:
        print("The `pmtiles` program was not found.\n"
              "  Get it automatically:   python get_tiles.py --download-cli\n"
              "  Or download it yourself: https://github.com/protomaps/go-pmtiles/releases (then use --cli PATH)\n"
              "If your computer blocks it, run this on another computer and copy the .pmtiles file to data/tiles/.")
        return 1

    source = a.source
    if not source:
        print("Looking for the newest Protomaps daily build ...")
        source = find_latest_build(head_ok, dt.date.today())
        if not source:
            print("Could not find a recent build. Open https://maps.protomaps.com/builds/ , copy a build URL, and run:\n"
                  "  python get_tiles.py --source <that URL>")
            return 1
    print(f"Source: {source}\nArea:   {bbox}   maximum zoom: {a.maxzoom}")

    out = Path(a.out) if a.out else tiles_dir() / config.TILES_FILE
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".pmtiles.part")
    cmd = [str(cli), "extract", source, str(tmp), f"--bbox={bbox}", f"--maxzoom={a.maxzoom}"]
    if a.dry_run:
        cmd.append("--dry-run")
    elif shutil.disk_usage(out.parent).free < 1_000_000_000:
        print("Less than 1 GB of free disk space. Free some space first.")
        return 1

    print("Running:", " ".join(cmd), "\n")
    try:
        result = subprocess.run(cmd)
    except OSError as exc:
        print(f"\nThe pmtiles program could not run: {exc}\nIf it is blocked by your computer's policy, run this on another computer.")
        return 1
    if result.returncode != 0:
        tmp.unlink(missing_ok=True)
        print("\nThe download failed. Nothing was changed.")
        return result.returncode
    if a.dry_run:
        print("\nDry run only. Nothing was saved. Run again without --dry-run to download.")
        return 0

    info = describe(tmp)
    if not info["usable"]:
        tmp.unlink(missing_ok=True)
        print(f"\nThe downloaded file cannot be used: {info.get('reason')}\nNothing was changed.")
        return 1
    if out.exists():
        shutil.copy2(out, out.with_suffix(".pmtiles.bak"))        # keep the previous map until the new one is in place
    os.replace(tmp, out)
    mb = out.stat().st_size / 1e6
    print(f"\nDone. {out}  ({mb:.1f} MB, zoom {info['minzoom']} to {info['maxzoom']}, schema {info.get('schema_version')}).\n"
          "Restart the backend. The status line under the map will say \"Offline map\".")
    return 0


if __name__ == "__main__":
    sys.exit(main())
