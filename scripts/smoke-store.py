#!/usr/bin/env python3
"""BuccaneerSalvage Store — local smoke test (Playwright).

Serves the hub over http.server, drives store.html in headless Chromium,
and asserts the BRIEF acceptance gates:
  - 12/page default; "Showing X-Y of N"
  - search Goodyear -> 8
  - filter brake -> 39; cores -> 2
  - sort price-asc lowest first
  - featured sort -> Holset turbo first
  - no CSP/console errors about blocked CDN

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
        check("catalog 67 items", len(cat.get("items", [])) == 67, f"n={len(cat.get('items', []))}")

        console_errors = []
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.on("console", lambda m: console_errors.append(m.text) if m.type == "error" else None)
            page.on("pageerror", lambda e: console_errors.append(str(e)))
            page.goto(f"{BASE}/store.html")
            page.wait_for_selector("#stGrid .st-card", timeout=10000)
            page.wait_for_function(
                "document.querySelectorAll('#stGrid .st-card').length > 0 && "
                "document.getElementById('stShowing').textContent.includes('of 67')"
            )

            # 1) default page size 12 + showing text
            cards = page.locator("#stGrid .st-card").count()
            check("default 12/page", cards == 12, f"cards={cards}")
            showing = page.text_content("#stShowing").strip()
            check("Showing 1-12 of 67", showing == "Showing 1–12 of 67", showing)

            # 2) search Goodyear -> 8
            page.fill("#stSearch", "Goodyear")
            page.wait_for_function("document.getElementById('stShowing').textContent.includes('of 8')")
            check("search Goodyear -> 8", True, page.text_content("#stShowing").strip())
            page.fill("#stSearch", "")
            page.wait_for_function("document.getElementById('stShowing').textContent.includes('of 67')")

            # 3) filter brake -> 39, cores -> 2
            page.click(".st-chip[data-filter='brake']")
            page.wait_for_function("document.getElementById('stShowing').textContent.includes('of 39')")
            check("filter brake -> 39", True, page.text_content("#stShowing").strip())
            page.click(".st-chip[data-filter='cores']")
            page.wait_for_function("document.getElementById('stShowing').textContent.includes('of 2')")
            check("filter cores -> 2", True, page.text_content("#stShowing").strip())
            page.click(".st-chip[data-filter='all']")
            page.wait_for_function("document.getElementById('stShowing').textContent.includes('of 67')")

            # 4) sort price-asc lowest first
            page.select_option("#stSort", "price-asc")
            page.wait_for_timeout(300)
            first_price = page.locator("#stGrid .st-card").first.get_attribute("data-price")
            check("price-asc lowest first", float(first_price) <= 10.0, f"first=${first_price}")

            # 5) featured sort -> Holset turbo first
            page.select_option("#stSort", "featured")
            page.wait_for_timeout(300)
            first_name = page.locator("#stGrid .st-card .name").first.text_content()
            check(
                "featured -> Holset turbo first",
                "holset" in first_name.lower() and "turbo" in first_name.lower(),
                first_name.strip(),
            )

            # 6) page size 24
            page.select_option("#stPageSize", "24")
            page.wait_for_function("document.getElementById('stShowing').textContent.includes('–24 of 67')")
            cards = page.locator("#stGrid .st-card").count()
            check("page size 24", cards == 24, f"cards={cards}")

            # 6b) pager page 2 range label (regression: string-coerced list.page)
            page.select_option("#stPageSize", "12")
            page.wait_for_function("document.getElementById('stShowing').textContent.includes('–12 of 67')")
            page.click("ul.pagination li:nth-child(2) .page")
            page.wait_for_timeout(300)
            showing2 = page.text_content("#stShowing").strip()
            check("page 2 -> Showing 13-24 of 67", showing2 == "Showing 13–24 of 67", showing2)

            # 7) featured cores section renders 2 core cards with warn ribbon
            cores = page.locator("#stFeaturedCores .st-card--core").count()
            ribbons = page.locator("#stFeaturedCores .st-ribbon").count()
            check("featured cores = 2 with ribbons", cores == 2 and ribbons == 2, f"cores={cores} ribbons={ribbons}")

            # 8) no CSP / blocked-CDN console errors
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
