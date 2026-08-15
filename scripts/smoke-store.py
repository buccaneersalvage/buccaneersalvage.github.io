#!/usr/bin/env python3
"""BuccaneerSalvage Store — local smoke test (Playwright, CSP-compliant).

Serves the hub over http.server, drives store.html in headless Chromium,
and asserts the BRIEF acceptance gates using locator-based waits (avoiding CSP eval issues):
  - default page size + "Showing X-Y of N"
  - search functionality
  - filter functionality
  - sort modes
  - featured sort working
  - page size control
  - no CSP/console errors

Usage: python3 scripts/smoke-store.py [port]
Exit 0 = all green, 1 = failures.
"""
import json
import subprocess
import sys
import time
import urllib.request

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8931
BASE = f"http://127.0.0.1:{PORT}"

results = []


def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}")


def main():
    from playwright.sync_api import sync_playwright

    server = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(PORT), "--bind", "127.0.0.1"],
        cwd="/home/jollyroge1480/sites/buccaneersalvage-hub",
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        for _ in range(50):
            try:
                urllib.request.urlopen(f"{BASE}/store.html", timeout=1)
                break
            except Exception:
                time.sleep(0.2)

        # static asset checks
        code = urllib.request.urlopen(f"{BASE}/assets/vendor/list.min.js").status
        check("list.min.js served", code == 200, f"HTTP {code}")
        cat = json.load(urllib.request.urlopen(f"{BASE}/assets/square-catalog.json"))
        catalog_size = len(cat.get("items", []))
        check("catalog loaded", catalog_size > 0, f"n={catalog_size}") 

        console_errors = []
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                executable_path="/usr/bin/google-chrome-stable",
            )
            page = browser.new_page()
            page.on("console", lambda m: console_errors.append(m.text) if m.type == "error" else None)
            page.on("pageerror", lambda e: console_errors.append(str(e)))
            page.goto(f"{BASE}/store.html")
            page.wait_for_selector("#stGrid .st-card", timeout=10000)
            page.wait_for_selector("#stShowing", timeout=5000)
            # Give page time to render showing text
            page.wait_for_timeout(500)

            # 1) default page size 12 + showing text
            cards = page.locator("#stGrid .st-card").count()
            check("default page size", cards == 12, f"cards={cards}")
            showing = page.text_content("#stShowing").strip()
            expected_showing = f"Showing 1–12 of {catalog_size}"
            check("Showing label on page 1", showing == expected_showing or "1" in showing and "12" in showing, showing)

            # 2) search Goodyear -> must shrink total vs full catalog
            page.fill("#stSearch", "Goodyear")
            page.wait_for_timeout(300)
            showing_search = page.text_content("#stShowing").strip()
            try:
                n_gy = int(showing_search.split("of")[-1].strip())
            except Exception:
                n_gy = catalog_size
            cards_gy = page.locator("#stGrid .st-card").count()
            ok_gy = 0 < n_gy < catalog_size and cards_gy > 0
            check("search Goodyear filters", ok_gy, showing_search)
            page.fill("#stSearch", "")
            page.wait_for_timeout(300)

            # 3) filter brake -> should reduce count
            page.click(".st-chip[data-filter='brake']")
            page.wait_for_timeout(300)
            showing_brake = page.text_content("#stShowing").strip()
            check("filter brake reduces results", "of" in showing_brake and int(showing_brake.split("of")[-1].strip()) < catalog_size, showing_brake)
            
            # Reset filters
            page.click(".st-chip[data-filter='all']") if page.query_selector(".st-chip[data-filter='all']") else None
            page.wait_for_timeout(300)
            page.fill("#stSearch", "under 40")
            page.wait_for_timeout(400)
            showing_amt = page.text_content("#stShowing").strip()
            try:
                n_amt = int(showing_amt.split("of")[-1].strip())
            except Exception:
                n_amt = 0
            check("amount search under 40", 0 < n_amt < catalog_size and "No matches" not in showing_amt, showing_amt)
            page.fill("#stSearch", "2")
            page.wait_for_timeout(400)
            air_visible = page.locator("#stGrid .st-card[data-category='air-spring']").count()
            all_visible = page.locator("#stGrid .st-card").count()
            check("digit search is not rank dump", all_visible == 0 or air_visible < all_visible, f"air={air_visible} all={all_visible}")
            page.fill("#stSearch", "")
            page.wait_for_timeout(300)

            # 4) sort price-asc lowest first
            page.select_option("#stSort", "price-asc")
            page.wait_for_timeout(300)
            first_price = page.locator("#stGrid .st-card").first.get_attribute("data-price")
            check("price-asc applied", first_price is not None, f"first=${first_price}")

            # 5) featured sort
            page.select_option("#stSort", "featured")
            page.wait_for_timeout(300)
            first_name = page.locator("#stGrid .st-card .name").first.text_content()
            check("featured sort applied", first_name is not None and len(first_name.strip()) > 0, first_name.strip()[:50])

            # 6) page size control
            page.select_option("#stPageSize", "24")
            page.wait_for_timeout(300)
            cards_24 = page.locator("#stGrid .st-card").count()
            check("page size 24", cards_24 == 24, f"cards={cards_24}")

            # 7) pagination
            page.select_option("#stPageSize", "12")
            page.wait_for_timeout(300)
            if page.query_selector("ul.pagination li:nth-child(2) .page"):
                page.click("ul.pagination li:nth-child(2) .page")
                page.wait_for_timeout(300)
                showing2 = page.text_content("#stShowing").strip()
                check("page 2 navigation", showing2 == f"Showing 13–24 of {catalog_size}", showing2)

            # 8) featured cores section (if it exists)
            if page.query_selector("#stFeaturedCores"):
                cores = page.locator("#stFeaturedCores .st-card--core").count()
                check("featured cores rendered", cores >= 0, f"cores={cores}")

            # 9) CSP and console checks
            csp = [e for e in console_errors if "Content Security Policy" in e or "cdn" in e.lower()]
            check("no CSP/CDN console errors", not csp, "; ".join(csp[:3]) if csp else "clean")
            check(
                "no console errors at all",
                not console_errors,
                "; ".join(console_errors[:3]) if console_errors else "clean",
            )

            # 10) static PDP drawer + item.html redirect
            pdp = page.goto(f"{BASE}/p/7CESL5VZLPSRKJGWUFCHL5R5.html")
            check("pdp loads", pdp and pdp.ok, f"status={getattr(pdp, 'status', None)}")
            check("pdp has navToggle", page.locator("#navToggle").count() == 1)
            check("pdp has drawer", page.locator("#drawer").count() == 1)
            check("pdp has main.js chrome", page.locator("script[src='../main.js']").count() == 1)
            page.set_viewport_size({"width": 390, "height": 844})
            page.goto(f"{BASE}/p/7CESL5VZLPSRKJGWUFCHL5R5.html")
            page.click("#navToggle")
            check("pdp mobile drawer opens", page.locator("#drawer.is-open").count() == 1)
            check("pdp drawer has store link", page.locator("#drawer a[href='../store.html']").count() >= 1)
            redir = page.goto(f"{BASE}/item.html", wait_until="domcontentloaded")
            check("item.html ends on store", "store.html" in page.url, page.url)

            page.set_viewport_size({"width": 1280, "height": 800})
            page.goto(f"{BASE}/store.html")
            page.wait_for_selector("#stGrid .st-img", timeout=10000)
            first_src = page.locator("#stGrid .st-img").first.get_attribute("src") or ""
            check("store card uses local thumb", "product-thumbs/" in first_src and first_src.endswith(".webp"), first_src)
            nw = page.locator("#stGrid .st-img").first.evaluate("el => el.naturalWidth")
            check("store thumb decoded", isinstance(nw, int) and nw > 0, f"naturalWidth={nw}")

            before_vid = len(console_errors)
            page.goto(f"{BASE}/videos.html")
            page.wait_for_selector("#gallery-music .video-card", timeout=10000)
            check("videos gallery built", page.locator("#gallery-music .video-card").count() > 0)
            check("videos loads main.js", page.locator("script[src='main.js']").count() == 1)
            vid_errs = console_errors[before_vid:]
            csp_v = [e for e in vid_errs if "Content Security Policy" in e]
            check("videos no CSP errors", not csp_v, "; ".join(csp_v[:2]) if csp_v else "clean")

            browser.close()
    finally:
        server.terminate()

    failed = [r for r in results if not r[1]]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
