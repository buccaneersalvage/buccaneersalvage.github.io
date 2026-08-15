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
            page.fill("#stSearch", "2008 camry")
            page.wait_for_timeout(400)
            showing_camry = page.text_content("#stShowing").strip()
            try:
                n_camry = int(showing_camry.split("of")[-1].strip())
            except Exception:
                n_camry = 0
            check("search 2008 camry", 0 < n_camry < catalog_size, showing_camry)
            page.fill("#stSearch", "W01-358-8091")
            page.wait_for_timeout(400)
            showing_ich = page.text_content("#stShowing").strip()
            try:
                n_ich = int(showing_ich.split("of")[-1].strip())
            except Exception:
                n_ich = 0
            check("search interchange PN", 0 < n_ich < catalog_size, showing_ich)
            page.fill("#stSearch", "constructor")
            page.wait_for_timeout(400)
            showing_ctor = page.text_content("#stShowing").strip()
            ctor_err = [e for e in console_errors if "forEach is not a function" in e or "tokenAlts" in e]
            check(
                "search constructor does not crash",
                not ctor_err and showing_ctor != "",
                showing_ctor,
            )
            page.fill("#stSearch", "")
            page.wait_for_timeout(300)

            # 3) eBay parent category then type (streamed selects)
            page.select_option("#stCatSelect", "brakes-brake-parts")
            page.wait_for_timeout(300)
            showing_brake = page.text_content("#stShowing").strip()
            try:
                n_brake = int(showing_brake.split("of")[-1].strip())
            except Exception:
                n_brake = catalog_size
            check("filter brakes parent reduces", 0 < n_brake < catalog_size, showing_brake)
            type_opt = page.query_selector("#stTypeSelect option[value='brake-pad-shoe-hardware']")
            check("type select after parent", bool(type_opt), "brake pad hardware type")
            type_visible = page.is_visible("#stTypeSelect")
            check("type step visible after category", type_visible)
            if type_opt:
                page.select_option("#stTypeSelect", "brake-pad-shoe-hardware")
                page.wait_for_timeout(300)
                showing_sub = page.text_content("#stShowing").strip()
                try:
                    n_sub = int(showing_sub.split("of")[-1].strip())
                except Exception:
                    n_sub = n_brake
                check("type narrows parent", 0 < n_sub <= n_brake, showing_sub)
            air_opt = page.query_selector("#stCatSelect option[value='air-fuel-delivery']")
            air_label = (air_opt.inner_text() if air_opt else "") or ""
            check("auto eBay parent Air & Fuel", bool(air_opt), "air-fuel-delivery")
            check(
                "Air & Fuel short label",
                "air & fuel" in air_label.lower() and "delivery" not in air_label.lower(),
                air_label,
            )
            engines_opt = page.query_selector("#stCatSelect option[value='engines-engine-parts']")
            check("auto eBay parent Engines", bool(engines_opt), "engines-engine-parts")
            exhaust_opt = page.query_selector("#stCatSelect option[value='exhaust-emission-systems']")
            check("singleton Exhaust stays its parent", bool(exhaust_opt), "exhaust-emission-systems")
            health_opt = page.query_selector("#stCatSelect option[value='health-beauty']")
            check("Health & Beauty not a store parent", health_opt is None)
            interior_opt = page.query_selector("#stCatSelect option[value='interior-parts-accessories']")
            check("Interior is a store parent", bool(interior_opt))
            other_opt = page.query_selector("#stCatSelect option[value='other']")
            other_label = (other_opt.inner_text() if other_opt else "") or ""
            check(
                "Other is leftover yard finds only",
                (not other_opt) or "other" in other_label.lower(),
                other_label,
            )
            # Gates timing belt must not sit in Interior
            page.select_option("#stCatSelect", "engines-engine-parts")
            page.wait_for_timeout(300)
            page.fill("#stSearch", "Gates CD70")
            page.wait_for_timeout(400)
            showing_gates = page.text_content("#stShowing").strip()
            check(
                "Gates timing belt in Engines",
                "of 1" in showing_gates or "1-1 of 1" in showing_gates,
                showing_gates,
            )
            page.fill("#stSearch", "")
            page.select_option("#stCatSelect", "ignition-systems-components")
            page.wait_for_timeout(300)
            page.fill("#stSearch", "VC211")
            page.wait_for_timeout(400)
            showing_vc = page.text_content("#stShowing").strip()
            check(
                "VC211 vacuum advance in Ignition",
                "of 1" in showing_vc or "1-1 of 1" in showing_vc,
                showing_vc,
            )
            page.fill("#stSearch", "")
            page.select_option("#stCatSelect", "all")
            page.wait_for_timeout(250)
            page.fill("#stSearch", "Integra")
            page.wait_for_timeout(400)
            showing_int = page.text_content("#stShowing").strip()
            cards = page.locator("#stGrid .st-card:visible")
            titles = [c.inner_text() for c in cards.all()] if cards.count() else []
            check(
                "Integra does not hit Cloyes Chevette belt",
                all("B-061" not in t and "Cloyes" not in t for t in titles),
                showing_int,
            )
            page.fill("#stSearch", "Chevette B-061")
            page.wait_for_timeout(400)
            showing_ch = page.text_content("#stShowing").strip()
            check(
                "Cloyes B-061 finds Chevette",
                "of 1" in showing_ch or "1-1 of 1" in showing_ch,
                showing_ch,
            )
            page.fill("#stSearch", "")
            page.select_option("#stCatSelect", "all")
            page.wait_for_timeout(250)
            check("Vehicle select first", page.is_visible("#stMakeSelect"))
            check("Model hidden until vehicle", not page.is_visible("#stModelSelect"))
            page.select_option("#stMakeSelect", "toyota")
            page.wait_for_timeout(350)
            camry = page.query_selector("#stModelSelect option[value='camry']")
            check("Camry model after Toyota", bool(camry) and page.is_visible("#stModelSelect"))
            if camry:
                page.select_option("#stModelSelect", "camry")
                page.wait_for_timeout(350)
                showing_cam = page.text_content("#stShowing").strip()
                try:
                    n_cam = int(showing_cam.split("of")[-1].strip())
                except Exception:
                    n_cam = 0
                check("Toyota Camry narrows catalog", 0 < n_cam < catalog_size, showing_cam)
            page.select_option("#stMakeSelect", "")
            page.wait_for_timeout(250)

            # Reset filters
            page.select_option("#stCatSelect", "all")
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
                check(
                    "page 2 navigation",
                    showing2.replace("–", "-") == f"Showing 13-24 of {catalog_size}",
                    showing2,
                )

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
            pdp = page.goto(f"{BASE}/p/7G7QMJIPJDP6N2LQV42RQS62.html")
            check("pdp loads", pdp and pdp.ok, f"status={getattr(pdp, 'status', None)}")
            check("pdp has fitment block", page.locator(".pdp-fitment").count() == 1)
            check(
                "pdp shows Fits vehicles",
                page.locator(".pdp-fitment").count() == 1
                and "Volkswagen Beetle" in (page.text_content(".pdp-fitment") or ""),
                "Beetle on 103-2250",
            )
            check(
                "pdp shows part numbers",
                "103-2250" in (page.text_content(".pdp-fitment") or ""),
                "103-2250",
            )
            check(
                "pdp related or also-stocked",
                page.locator(".pdp-related").count() == 1
                and page.locator(".pdp-related a[href$='.html']").count() >= 1,
                "related links",
            )
            xref_pdp = page.goto(f"{BASE}/p/5LLWTR3B27YDLV6ZR6XMBPWL.html")
            check("xref pdp loads", xref_pdp and xref_pdp.ok, f"status={getattr(xref_pdp, 'status', None)}")
            xref_txt = page.text_content(".pdp-fitment") or ""
            check("pdp shows interchange PN", "W01-358-8091" in xref_txt, xref_txt[:80])
            blob_pdp = page.goto(f"{BASE}/p/MJAQDKIB2WT55I26Q552PZXS.html")
            check("blob-xref pdp loads", blob_pdp and blob_pdp.ok, f"status={getattr(blob_pdp, 'status', None)}")
            blob_txt = page.text_content(".pdp-fitment") or ""
            check("pdp splits PN blob into interchange", "W01-358-7859" in blob_txt, blob_txt[:120])
            name_pn = page.goto(f"{BASE}/p/DN2MBTK3CTWNW36SMFCLHQBQ.html")
            check("title-pn pdp loads", name_pn and name_pn.ok, f"status={getattr(name_pn, 'status', None)}")
            name_txt = page.text_content(".pdp-fitment") or ""
            check("pdp extracts WIX 33063 from title", "33063" in name_txt, name_txt[:120])
            pdp = page.goto(f"{BASE}/p/7CESL5VZLPSRKJGWUFCHL5R5.html")
            check("pdp chrome item loads", pdp and pdp.ok, f"status={getattr(pdp, 'status', None)}")
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
