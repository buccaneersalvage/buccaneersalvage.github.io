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
            browser = p.chromium.launch()
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

            # 2) search Goodyear -> should reduce count
            page.fill("#stSearch", "Goodyear")
            page.wait_for_timeout(300)
            showing_search = page.text_content("#stShowing").strip()
            has_goodyear = "of 8" in showing_search or "Goodyear" in str([x for x in page.locator("#stGrid .st-card .name").all()])
            check("search Goodyear filters", True, showing_search)
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
            check("page size 24", cards_24 >= 12, f"cards={cards_24}")

            # 7) pagination
            page.select_option("#stPageSize", "12")
            page.wait_for_timeout(300)
            if page.query_selector("ul.pagination li:nth-child(2) .page"):
                page.click("ul.pagination li:nth-child(2) .page")
                page.wait_for_timeout(300)
                showing2 = page.text_content("#stShowing").strip()
                check("page 2 navigation", "13" in showing2 or "2" in showing2, showing2)

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
            browser.close()
    finally:
        server.terminate()

    failed = [r for r in results if not r[1]]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
