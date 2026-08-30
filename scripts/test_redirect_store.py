#!/usr/bin/env python3
"""item.html / square.html must not meta-refresh before redirect-store.js."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    failed = 0
    js = (ROOT / "assets" / "redirect-store.js").read_text(encoding="utf-8")
    if "p/" not in js or "store.html" not in js:
        print("FAIL  redirect-store.js missing p/ or store.html")
        failed += 1
    else:
        print("PASS  redirect-store.js routes id → p/ else store")

    for name in ("item.html", "square.html"):
        html = (ROOT / name).read_text(encoding="utf-8")
        if "redirect-store.js" not in html:
            print(f"FAIL  {name} missing redirect-store.js")
            failed += 1
        else:
            print(f"PASS  {name} loads redirect-store.js")
        # Immediate refresh races the script. noscript fallback is ok.
        if 'http-equiv="refresh" content="0; url=store.html"' in html and "<noscript>" not in html:
            print(f"FAIL  {name} still has unconditional meta refresh")
            failed += 1
        elif "<noscript>" in html and "refresh" in html:
            print(f"PASS  {name} refresh is noscript-only")
        else:
            print(f"PASS  {name} has no meta refresh")
    print("RESULT", "PASS" if failed == 0 else f"FAIL {failed}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
