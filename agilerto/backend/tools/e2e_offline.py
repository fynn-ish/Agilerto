"""Open the real page in a real browser with the internet BLOCKED and check that everything works.
Optional developer tool. Needs:   pip install playwright   and   playwright install chromium

    python tools/e2e_offline.py                          # against http://127.0.0.1:8000
    python tools/e2e_offline.py --url http://127.0.0.1:8000 --screenshot offline.png

Every request to any address except the server is blocked and counted. The test passes only if the page works
and nothing tried to reach the outside world.
"""
import argparse
import sys
from urllib.parse import urlparse


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8000")
    ap.add_argument("--screenshot")
    a = ap.parse_args()
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Playwright is not installed. Run:  pip install playwright   then   playwright install chromium")
        return 2

    server = urlparse(a.url).hostname
    results, blocked, js_errors = [], [], []

    def check(ok, name, detail=""):
        results.append(ok)
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  {detail}" if detail else ""))

    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1280, "height": 900})
        ctx.route("**/*", lambda route: route.continue_() if urlparse(route.request.url).hostname == server
                  else (blocked.append(route.request.url), route.abort()))
        page = ctx.new_page()
        page.on("pageerror", lambda e: js_errors.append(str(e)))
        page.goto(a.url, wait_until="load")
        page.wait_for_selector("text=Nearby places", timeout=15000)
        page.wait_for_timeout(3500)                              # let the map draw

        check(page.locator("text=Call for help").count() > 0, "Hotline bar is visible")
        markers = page.locator(".fmark").count()
        check(markers > 0, "Facility markers are on the map", f"{markers} markers")
        check(page.locator("section[aria-label='Facility list'] li, #panel-places li").count() > 0, "Facility list is filled")

        status = page.locator("[role=status]", has_text="map").first.inner_text().replace("\n", " ")
        offline_map = status.startswith("Offline map")
        painted = page.evaluate("""() => [...document.querySelectorAll('canvas.leaflet-tile')].filter(c => {
            try { const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data; for (let i = 3; i < d.length; i += 4) if (d[i]) return true } catch (e) {} return false }).length""")
        check(offline_map and painted > 0, "Offline map is drawn from local tiles" if offline_map else "Map background",
              f"{painted} tiles painted" if offline_map else f"NOT offline: {status[:140]}")

        page.get_by_role("tab", name="Conditions").click()
        page.wait_for_timeout(500)
        check(page.locator("text=Advisories").count() > 0 and page.locator("text=Weather").count() > 0, "Conditions tab shows saved advisories and weather")

        page.get_by_role("tab", name="Ask the assistant").click()
        page.locator("#chat-input").fill("Tulong! May sunog sa bahay namin")
        page.get_by_role("button", name="Ask", exact=True).click()
        page.wait_for_selector("text=Mukhang emergency", timeout=15000)
        check(True, "The assistant answers an emergency with no internet")
        page.locator("#chat-input").fill("Should I evacuate?")
        page.get_by_role("button", name="Ask", exact=True).click()
        page.wait_for_selector("text=Something I can’t answer", timeout=15000)
        check(True, "The assistant politely refuses an evacuation decision")

        if a.screenshot:
            page.screenshot(path=a.screenshot)
        browser.close()

    check(not blocked, "Nothing tried to reach the internet", f"blocked requests: {sorted(set(blocked))[:5]}" if blocked else "")
    check(not js_errors, "No JavaScript errors", "; ".join(js_errors[:2]))
    print(f"\n{results.count(True)} of {len(results)} passed")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
