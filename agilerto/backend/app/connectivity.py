"""Is the internet reachable? A plain TCP connect to the weather host (no data is requested)."""
import socket
import threading
import time

CHECK_HOST = ("api.open-meteo.com", 443)
_cache = {"at": -1e9, "value": False}
_lock = threading.Lock()


def is_online(force: bool = False, ttl: float = 10.0, timeout: float = 3.0) -> bool:
    """Cached for `ttl` seconds so dashboard requests don't each open a connection."""
    with _lock:
        if not force and time.monotonic() - _cache["at"] < ttl:
            return _cache["value"]

    result = {"ok": False}

    def probe():
        try:
            with socket.create_connection(CHECK_HOST, timeout=timeout):
                result["ok"] = True
        except OSError:
            pass

    # Run in a thread so a slow DNS lookup (common when offline) can't block the caller.
    t = threading.Thread(target=probe, daemon=True)
    t.start()
    t.join(timeout + 0.5)

    with _lock:
        _cache.update(at=time.monotonic(), value=result["ok"])
    return result["ok"]
