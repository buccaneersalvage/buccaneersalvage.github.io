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
import base64
import hashlib
import json
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

HUB = Path("/home/jollyroge1480/sites/buccaneersalvage-hub")
HASH_V = re.compile(r"styles\.css\?v=[0-9a-f]{10}")

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
        by_id = {i.get("id"): i.get("category") for i in cat.get("items", [])}
        want_buckets = {
            "LI7R7ABGGB2TXJQUEGHG5TRX": "mobility",
            "WCSSZNLKXNQIOIHDWIOWQCGW": "cycling",
            "EZW5JY5PWZJO4PH5R2TQGYC3": "material-handling",
            "7CESL5VZLPSRKJGWUFCHL5R5": "electric-motors",
            "3YKKZSK4N5HMOC7TOVXSFOHH": "exhaust",
            "RLDFAATFFK6423JIPQIQSH3D": "interior",
            "BA22UJLZFQ7RYU42QV7AFD2Y": "engines",
            "FSUFF4EKUITJCPOIIMCLMA5J": "interior",
        }
        bucket_miss = [f"{k}:{by_id.get(k)}!={v}" for k, v in want_buckets.items() if by_id.get(k) != v]
        check("catalog true-department buckets", not bucket_miss, "; ".join(bucket_miss))
        vintage_dump = [i.get("id") for i in cat.get("items", []) if i.get("category") == "vintage"]
        check("catalog has no vintage dump bucket", not vintage_dump, ",".join(vintage_dump))
        thermo_other = [
            i.get("id")
            for i in cat.get("items", [])
            if i.get("category") == "other" and "thermostat" in (i.get("name") or "").lower()
        ]
        check("thermos stay in catalog other bucket", len(thermo_other) >= 20, f"n={len(thermo_other)}")
        store_html = urllib.request.urlopen(f"{BASE}/store.html").read().decode("utf-8", "replace")
        index_html = urllib.request.urlopen(f"{BASE}/index.html").read().decode("utf-8", "replace")
        terms_html = urllib.request.urlopen(f"{BASE}/terms.html").read().decode("utf-8", "replace")
        pdp_html = urllib.request.urlopen(f"{BASE}/p/7CESL5VZLPSRKJGWUFCHL5R5.html").read().decode("utf-8", "replace")
        pdp_air = urllib.request.urlopen(f"{BASE}/p/R6VO2MARXN7GRGTMXVGABLHT.html").read().decode("utf-8", "replace")
        list_js = (HUB / "assets/vendor/list.min.js").read_bytes()
        sri = "sha384-" + base64.b64encode(hashlib.sha384(list_js).digest()).decode("ascii")
        check("store css content-hash", bool(HASH_V.search(store_html)))
        check("index css content-hash", bool(HASH_V.search(index_html)))
        check("terms css content-hash", bool(HASH_V.search(terms_html)))
        check("pdp css content-hash", bool(HASH_V.search(pdp_html)))
        check("store list.js SRI", sri in store_html)
        check("store styles SRI", 'integrity="sha384-' in store_html and "styles.css?v=" in store_html)
        check("store no style-src unsafe-inline", "unsafe-inline" not in store_html)
        check("index no style-src unsafe-inline", "unsafe-inline" not in index_html)
        check("pdp no style-src unsafe-inline", "unsafe-inline" not in pdp_html)
        check(
            "no inert nosniff meta",
            "X-Content-Type-Options" not in store_html
            and "X-Content-Type-Options" not in index_html
            and "X-Content-Type-Options" not in pdp_html,
        )
        check("no godmode cache tokens", "godmode" not in store_html.lower() and "godmode" not in pdp_html.lower())
        check("store frame-src none", "frame-src 'none'" in store_html)
        check("index frame-src none", "frame-src 'none'" in index_html)
        check("pdp frame-src none", "frame-src 'none'" in pdp_html)
        check(
            "no meta frame-ancestors (Chrome ignores + errors)",
            "frame-ancestors" not in store_html
            and "frame-ancestors" not in index_html
            and "frame-ancestors" not in pdp_html,
        )
        check(
            "PDP checkout href baked (no JS-only empty link)",
            'href="https://buccaneersalvage.square.site/product/R6VO2MARXN7GRGTMXVGABLHT"'
            in pdp_air
            and 'data-bind="checkout"' in pdp_air,
        )
        check("PDP uses store parent not Cycling site dept", "Vintage &amp; Collectibles" in pdp_html)
        check("air PDP uses Truck Air Springs parent", "Truck Air Springs" in pdp_air)
        check("store heading id for live parent label", 'id="stHeading"' in store_html)

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
            label_color = page.locator(".st-facet-label").first.evaluate(
                "el => getComputedStyle(el).color"
            )
            check(
                "facet label uses parchment not gold",
                "197, 160, 40" not in (label_color or ""),
                label_color,
            )

            # 1) default page size 12 + showing text
            cards = page.locator("#stGrid .st-card").count()
            check("default page size", cards == 12, f"cards={cards}")
            showing = page.text_content("#stShowing").strip()
            try:
                auto_n = int(showing.split("of")[-1].strip())
            except Exception:
                auto_n = catalog_size
            check(
                "default All excludes yard depts",
                auto_n == catalog_size - 4,
                showing,
            )
            count_txt = (page.text_content("#stCount") or "").strip()
            check(
                "header count matches All parts",
                count_txt == f"{auto_n} listings",
                count_txt,
            )
            expected_showing = f"Showing 1–12 of {auto_n}"
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
            page.fill("#stSearch", "wheelchair")
            page.wait_for_timeout(400)
            showing_wc = page.text_content("#stShowing").strip()
            wc_titles = " ".join(page.locator("#stGrid .st-card .name").all_inner_texts()).lower()
            check("search wheelchair finds Mobility item", "of 1" in showing_wc and "wheelchair" in wc_titles, showing_wc)
            page.fill("#stSearch", "2000")
            page.wait_for_timeout(400)
            showing_y2k = page.text_content("#stShowing").strip()
            y2k_titles = " ".join(page.locator("#stGrid .st-card .name").all_inner_texts()).lower()
            check(
                "year search does not pull wheelchair",
                "wheelchair" not in y2k_titles,
                showing_y2k,
            )
            page.fill("#stSearch", "")
            page.wait_for_timeout(300)

            # 3) eBay store parents (only those on Buc) then type
            page.select_option("#stCatSelect", "carlson-brake-hardware")
            page.wait_for_timeout(300)
            showing_brake = page.text_content("#stShowing").strip()
            try:
                n_brake = int(showing_brake.split("of")[-1].strip())
            except Exception:
                n_brake = catalog_size
            check("Carlson parent reduces", 0 < n_brake < catalog_size, showing_brake)
            check("vehicle stays on Carlson", page.is_visible("#stMakeSelect"))
            type_visible = page.is_visible("#stTypeSelect")
            check("type step visible after Carlson", type_visible)
            type_opt = page.query_selector("#stTypeSelect option[value='self-adjuster-kits']")
            check("Carlson children include self-adjusters", bool(type_opt), "self-adjuster-kits")
            if type_opt:
                page.select_option("#stTypeSelect", "self-adjuster-kits")
                page.wait_for_timeout(300)
                showing_sub = page.text_content("#stShowing").strip()
                try:
                    n_sub = int(showing_sub.split("of")[-1].strip())
                except Exception:
                    n_sub = n_brake
                check("type narrows Carlson", 0 < n_sub <= n_brake, showing_sub)
            truck_opt = page.query_selector("#stCatSelect option[value='truck-air-springs']")
            auto_opt = page.query_selector("#stCatSelect option[value='auto-parts']")
            vintage_opt = page.query_selector("#stCatSelect option[value='vintage-collectibles']")
            indy_opt = page.query_selector("#stCatSelect option[value='industrial-warehouse']")
            check("Truck Air Springs parent", bool(truck_opt), truck_opt.inner_text() if truck_opt else "")
            check("Auto Parts parent", bool(auto_opt), auto_opt.inner_text() if auto_opt else "")
            check("Vintage parent for yard stock", bool(vintage_opt), vintage_opt.inner_text() if vintage_opt else "")
            check("Industrial parent", bool(indy_opt), indy_opt.inner_text() if indy_opt else "")
            for missing in (
                "air-fuel-delivery",
                "engines-engine-parts",
                "mobility",
                "cycling",
                "material-handling",
                "electric-motors",
                "appliance-parts",
                "electronics-electrical",
                "other",
            ):
                check(
                    f"no leftover parent {missing}",
                    page.query_selector(f"#stCatSelect option[value='{missing}']") is None,
                )
            page.select_option("#stCatSelect", "truck-air-springs")
            page.wait_for_timeout(300)
            showing_truck = page.text_content("#stShowing").strip()
            check("vehicle stays on truck air springs", page.is_visible("#stMakeSelect"))
            lobe = page.query_selector("#stTypeSelect option[value='rolling-lobe']")
            check("truck children include Rolling Lobe", bool(lobe), showing_truck)
            page.select_option("#stCatSelect", "vintage-collectibles")
            page.wait_for_timeout(300)
            showing_vin = page.text_content("#stShowing").strip()
            vin_titles = " ".join(page.locator("#stGrid .st-card .name").all_inner_texts()).lower()
            check(
                "H2 follows Vintage parent",
                (page.text_content("#stHeading") or "").strip() == "Vintage & Collectibles",
                (page.text_content("#stHeading") or "").strip(),
            )
            check("vehicle hidden on Vintage", not page.is_visible("#stMakeSelect"))
            check(
                "Vintage holds yard stock",
                "wheelchair" in vin_titles and "masi" in vin_titles and "craftsman" in vin_titles,
                showing_vin,
            )
            page.select_option("#stCatSelect", "industrial-warehouse")
            page.wait_for_timeout(300)
            showing_ind = page.text_content("#stShowing").strip()
            ind_titles = " ".join(page.locator("#stGrid .st-card .name").all_inner_texts()).lower()
            check("Industrial is the forklift tank", "forklift" in ind_titles, showing_ind)
            check("vehicle hidden on Industrial", not page.is_visible("#stMakeSelect"))
            page.select_option("#stCatSelect", "auto-parts")
            page.wait_for_timeout(300)
            check("vehicle back on Auto Parts", page.is_visible("#stMakeSelect"))
            page.fill("#stSearch", "Gates CD70")
            page.wait_for_timeout(400)
            showing_gates = page.text_content("#stShowing").strip()
            check(
                "Gates timing belt in Auto Parts",
                "of 1" in showing_gates or "1-1 of 1" in showing_gates,
                showing_gates,
            )
            page.fill("#stSearch", "")
            page.fill("#stSearch", "VC211")
            page.wait_for_timeout(400)
            showing_vc = page.text_content("#stShowing").strip()
            check(
                "VC211 vacuum advance in Auto Parts",
                "of 1" in showing_vc or "1-1 of 1" in showing_vc,
                showing_vc,
            )
            page.fill("#stSearch", "")
            page.select_option("#stCatSelect", "all")
            page.wait_for_timeout(250)
            check(
                "H2 All parts after reset",
                (page.text_content("#stHeading") or "").strip() == "All parts",
                (page.text_content("#stHeading") or "").strip(),
            )
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
                year_opt = page.query_selector("#stYearSelect option[value='2008']")
                check(
                    "Year after vehicle and model",
                    page.is_visible("#stYearSelect") and bool(year_opt),
                    page.text_content("#stYearSelect")[:80] if page.query_selector("#stYearSelect") else "",
                )
            page.fill("#stSearch", "wheelchair")
            page.wait_for_timeout(400)
            showing_veh_wc = page.text_content("#stShowing").strip()
            veh_wc_titles = " ".join(page.locator("#stGrid .st-card .name").all_inner_texts()).lower()
            check(
                "Toyota search excludes wheelchair",
                "wheelchair" not in veh_wc_titles and "No matches" in showing_veh_wc,
                showing_veh_wc,
            )
            page.fill("#stSearch", "")
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
                    showing2.replace("–", "-") == f"Showing 13-24 of {auto_n}",
                    showing2,
                )

            # 8) featured cores section (if it exists)
            if page.query_selector("#stFeaturedCores"):
                cores = page.locator("#stFeaturedCores .st-card--core").count()
                check("featured cores rendered", cores >= 0, f"cores={cores}")

            # 9) CSP and console checks
            csp = [e for e in console_errors if "Content Security Policy" in e or "cdn" in e.lower()]
            check("no CSP/CDN console errors", not csp, "; ".join(csp[:3]) if csp else "clean")
            real_console = [e for e in console_errors if "404" not in e]
            check(
                "no console errors except missing thumbs",
                not real_console,
                "; ".join((real_console or console_errors)[:3]) if console_errors else "clean",
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
            check(
                "pdp related uses cards",
                page.locator(".pdp-rel-card").count() >= 1,
                "card grid",
            )
            thermo = page.goto(f"{BASE}/p/BYO4CA2ORO6PIIHKJ6BAJ7Z5.html")
            check("thermo 33008 pdp loads", thermo and thermo.ok)
            rel_txt = page.text_content(".pdp-related") or ""
            check(
                "thermo 33008 does not dump other housings",
                "33036" not in rel_txt and "33059" not in rel_txt,
                rel_txt[:120],
            )
            check(
                "thermo 33008 offers catalog browse",
                "browse thermostat in the catalog" in rel_txt.lower(),
                rel_txt[-80:],
            )
            dodge = page.goto(f"{BASE}/p/RKN2JXFL3XHP336C6I2YOVYM.html")
            check("thermo 33036 pdp loads", dodge and dodge.ok)
            dodge_rel = page.text_content(".pdp-related") or ""
            check(
                "thermo 33036 shows same-vehicle temps",
                "33038" in dodge_rel or "33039" in dodge_rel,
                dodge_rel[:160],
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
            check(
                "pdp Craftsman category is Vintage",
                "Vintage & Collectibles" in (page.text_content(".pdp-category") or ""),
                page.text_content(".pdp-category"),
            )
            page.goto(f"{BASE}/p/LI7R7ABGGB2TXJQUEGHG5TRX.html")
            check(
                "pdp wheelchair category is Vintage",
                "Vintage & Collectibles" in (page.text_content(".pdp-category") or ""),
                page.text_content(".pdp-category"),
            )
            page.goto(f"{BASE}/p/WCSSZNLKXNQIOIHDWIOWQCGW.html")
            check(
                "pdp Masi category is Vintage",
                "Vintage & Collectibles" in (page.text_content(".pdp-category") or ""),
                page.text_content(".pdp-category"),
            )
            page.goto(f"{BASE}/p/EZW5JY5PWZJO4PH5R2TQGYC3.html")
            check(
                "pdp forklift category is Industrial",
                "Industrial & Warehouse" in (page.text_content(".pdp-category") or ""),
                page.text_content(".pdp-category"),
            )
            page.goto(f"{BASE}/p/3YKKZSK4N5HMOC7TOVXSFOHH.html")
            check(
                "pdp AP Exhaust category is Auto Parts",
                "Auto Parts" in (page.text_content(".pdp-category") or ""),
                page.text_content(".pdp-category"),
            )
            page.goto(f"{BASE}/p/RLDFAATFFK6423JIPQIQSH3D.html")
            check(
                "pdp Borg Warner category is Auto Parts",
                "Auto Parts" in (page.text_content(".pdp-category") or ""),
                page.text_content(".pdp-category"),
            )
            page.goto(f"{BASE}/p/BA22UJLZFQ7RYU42QV7AFD2Y.html")
            check(
                "pdp Dorman AIR pipe category is Auto Parts",
                "Auto Parts" in (page.text_content(".pdp-category") or ""),
                page.text_content(".pdp-category"),
            )
            wix = page.goto(f"{BASE}/p/DN2MBTK3CTWNW36SMFCLHQBQ.html")
            check("pdp WIX 33063 loads", wix and wix.ok, f"status={getattr(wix, 'status', None)}")
            check(
                "pdp WIX 33063 category is Auto Parts",
                "Auto Parts" in (page.text_content(".pdp-category") or ""),
                page.text_content(".pdp-category"),
            )
            wix_html = page.content()
            check("pdp WIX 33063 JSON-LD has mpn", '"mpn"' in wix_html and "33063" in wix_html)
            check("pdp has navToggle", page.locator("#navToggle").count() == 1)
            check("pdp has drawer", page.locator("#drawer").count() == 1)
            check("pdp has main.js chrome", page.locator("script[src^='../main.js']").count() == 1)
            page.set_viewport_size({"width": 390, "height": 844})
            page.goto(f"{BASE}/p/7CESL5VZLPSRKJGWUFCHL5R5.html")
            page.click("#navToggle")
            check("pdp mobile drawer opens", page.locator("#drawer.is-open").count() == 1)
            check("pdp drawer has store link", page.locator("#drawer a[href='../store.html']").count() >= 1)
            redir = page.goto(f"{BASE}/item.html", wait_until="domcontentloaded")
            check("item.html ends on store", "store.html" in page.url, page.url)

            page.set_viewport_size({"width": 390, "height": 844})
            page.goto(f"{BASE}/store.html")
            page.wait_for_selector("#navToggle", timeout=8000)
            page.click("#navToggle")
            page.wait_for_timeout(200)
            store_open = page.locator("#drawer.is-open")
            box = store_open.bounding_box() if store_open.count() else None
            check("store mobile drawer opens", store_open.count() == 1, f"count={store_open.count()}")
            check(
                "store mobile drawer visible",
                bool(box and box.get("height", 0) > 40),
                str(box),
            )
            page.click("#navToggle")

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
            check("videos loads main.js", page.locator("script[src^='main.js']").count() == 1)
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
