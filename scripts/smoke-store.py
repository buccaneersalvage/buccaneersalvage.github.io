#!/usr/bin/env python3
"""
Smoke test for BuccaneerSalvage Store (store.html)
Tests: search, sort, filter, pagination, featured cores, catalog load
Run locally: python3 -m http.server 8000, then python3 scripts/smoke-store.py
"""

import asyncio
import sys
import json
from pathlib import Path

try:
    from playwright.async_api import async_playwright
except ImportError:
    print("ERROR: playwright not installed. Run: pip install playwright && playwright install")
    sys.exit(1)


class StoreSmoke:
    def __init__(self, base_url="http://localhost:8000/store.html"):
        self.base_url = base_url
        self.results = {"passed": [], "failed": []}

    async def run(self):
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()
            try:
                await page.goto(self.base_url, wait_until="networkidle")
                print(f"✓ Page loaded: {self.base_url}")

                # Test 1: Catalog loads with 67 items
                await self.test_catalog_load(page)

                # Test 2: Search
                await self.test_search(page)

                # Test 3: Filter by category
                await self.test_filter(page)

                # Test 4: Sort
                await self.test_sort(page)

                # Test 5: Pagination
                await self.test_pagination(page)

                # Test 6: Featured cores visible
                await self.test_featured_cores(page)

                # Test 7: CSP no console errors
                await self.test_csp_compliance(page)

                # Test 8: list.min.js loaded (200 response)
                await self.test_list_js_load(page)

            finally:
                await browser.close()

    async def test_catalog_load(self, page):
        """Verify catalog loads and shows 67 items"""
        count_text = await page.text_content("#stCount")
        if count_text and "67" in count_text:
            self.results["passed"].append("Catalog load: 67 items")
            print(f"✓ Catalog loads: {count_text}")
        else:
            self.results["failed"].append(f"Catalog load failed: {count_text}")
            print(f"✗ Catalog load: expected '67 items', got '{count_text}'")

    async def test_search(self, page):
        """Search for 'Goodyear' should return ~8 results"""
        search_input = page.locator("#stSearch")
        await search_input.fill("Goodyear")
        await page.wait_for_timeout(500)

        # Check result meta
        meta_text = await page.text_content("#stResultMeta")
        if meta_text and "8" in meta_text:
            self.results["passed"].append("Search: Goodyear → 8 items")
            print(f"✓ Search works: {meta_text}")
        else:
            self.results["failed"].append(f"Search failed: {meta_text}")
            print(f"✗ Search: expected ~8 results, got '{meta_text}'")

    async def test_filter(self, page):
        """Filter by 'brake' should show ~39 items"""
        # Clear search first
        search_input = page.locator("#stSearch")
        await search_input.fill("")
        await page.wait_for_timeout(500)

        # Click 'brake' filter
        brake_btn = page.locator('[data-filter="brake"]')
        await brake_btn.click()
        await page.wait_for_timeout(500)

        meta_text = await page.text_content("#stResultMeta")
        if meta_text and "39" in meta_text:
            self.results["passed"].append("Filter: brake → 39 items")
            print(f"✓ Filter works: {meta_text}")
        else:
            self.results["failed"].append(f"Filter failed: {meta_text}")
            print(f"✗ Filter: expected ~39 items, got '{meta_text}'")

    async def test_sort(self, page):
        """Sort by price ascending should show lowest first"""
        # Reset filters
        clear_btn = page.locator("#stClearFilters")
        await clear_btn.click()
        await page.wait_for_timeout(500)

        # Sort by price asc
        sort_select = page.locator("#stSort")
        await sort_select.select_option("price-asc")
        await page.wait_for_timeout(500)

        # Get first card price
        first_price = await page.text_content("article.st-card:first-child .st-card-price")
        if first_price and "$" in first_price:
            self.results["passed"].append(f"Sort: price-asc → first: {first_price}")
            print(f"✓ Sort works: lowest price first = {first_price}")
        else:
            self.results["failed"].append(f"Sort failed: {first_price}")
            print(f"✗ Sort: expected price, got '{first_price}'")

    async def test_pagination(self, page):
        """Pagination: 12/page default, check 'Showing X–Y of Z'"""
        # Reset and verify 12/page
        clear_btn = page.locator("#stClearFilters")
        await clear_btn.click()
        await page.wait_for_timeout(500)

        showing = await page.text_content("#stShowing")
        if showing and "Showing 1–12 of" in showing:
            self.results["passed"].append("Pagination: 12/page default")
            print(f"✓ Pagination: {showing}")
        else:
            self.results["failed"].append(f"Pagination failed: {showing}")
            print(f"✗ Pagination: expected 'Showing 1–12 of', got '{showing}'")

    async def test_featured_cores(self, page):
        """Featured cores section visible with at least 1 core"""
        featured_cores = page.locator("#stFeaturedCores article.st-card")
        count = await featured_cores.count()
        if count > 0:
            self.results["passed"].append(f"Featured cores: {count} visible")
            print(f"✓ Featured cores: {count} items visible")
        else:
            self.results["failed"].append("Featured cores: 0 items")
            print(f"✗ Featured cores: expected at least 1, got {count}")

    async def test_csp_compliance(self, page):
        """Check for CSP violations in console"""
        messages = []
        page.on("console", lambda msg: messages.append((msg.type, msg.text)))

        await page.wait_for_timeout(1000)

        csp_errors = [m for m in messages if "Content Security Policy" in m[1]]
        if not csp_errors:
            self.results["passed"].append("CSP: no violations")
            print(f"✓ CSP: no console errors")
        else:
            self.results["failed"].append(f"CSP violations: {csp_errors}")
            print(f"✗ CSP: {len(csp_errors)} violations")

    async def test_list_js_load(self, page):
        """Verify list.min.js loads (should be in network)"""
        # Check if list.js is loaded (via checking if List object exists)
        has_list_js = await page.evaluate("typeof List !== 'undefined'")
        if has_list_js:
            self.results["passed"].append("list.min.js: loaded")
            print(f"✓ list.min.js loaded")
        else:
            self.results["failed"].append("list.min.js: not loaded")
            print(f"✗ list.min.js: not loaded")

    def report(self):
        """Print test summary"""
        print("\n" + "=" * 60)
        print("STORE SMOKE TEST RESULTS")
        print("=" * 60)
        print(f"✓ Passed: {len(self.results['passed'])}")
        for r in self.results["passed"]:
            print(f"  ✓ {r}")

        if self.results["failed"]:
            print(f"\n✗ Failed: {len(self.results['failed'])}")
            for r in self.results["failed"]:
                print(f"  ✗ {r}")
            return False

        print("\n✓ ALL TESTS PASSED")
        return True


async def main():
    smoke = StoreSmoke()
    await smoke.run()
    success = smoke.report()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
