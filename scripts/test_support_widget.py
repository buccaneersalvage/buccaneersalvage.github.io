#!/usr/bin/env python3
"""Twin of the hub support-widget classifier (spec /tmp/buc-hub-widget-spec.md)."""
from __future__ import annotations

import re
import sys
from pathlib import Path

RULES = [
    ("dispute", True, ["dispute", "attorney", "lawyer", "lawsuit", "legal action"]),
    ("damage", True, ["damaged", "broken", "defect", "crushed", "wrong item"]),
    ("order", True, ["tracking", "track my", "shipped yet", "where is my order", "never arrived", "cancel my order"]),
    ("scrap", False, ["scrap", "junk removal", "junk haul", "e-waste", "ewaste", "electronics recycling", "metal haul", "pick up scrap"]),
    ("pickup", False, ["pickup", "pick up", "pick it up", "come get", "come by", "appointment"]),
    ("hours", False, ["hours", "are you open", "when are you open", "business hours"]),
    ("shipping", False, ["shipping", "delivery", "ship to", "freight", "how long to ship"]),
    ("returns", False, ["return", "refund", "warranty"]),
    ("fitment", False, ["will this fit", "fits", "compatible", "will this work", "year make"]),
    ("pay", False, ["cash app", "cashapp", "paypal", "venmo", "how to pay", "how do i pay", "checkout"]),
    ("contact", False, ["phone", "call", "text", "email", "address", "where are you"]),
]


def normalize(text: str) -> str:
    t = (text or "").lower()
    t = re.sub(r"[^\w\s]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def classify(text: str) -> tuple[str, bool]:
    n = normalize(text)
    if not n:
        return "other", True
    for rid, esc, keys in RULES:
        for key in keys:
            if normalize(key) in n:
                return rid, esc
    return "other", True


CASES = [
    ("where is my order", "order", True),
    ("do you do scrap pickup", "scrap", False),
    ("can I pick it up", "pickup", False),
    ("what are your hours", "hours", False),
    ("will this fit a 2005 F250", "fitment", False),
    ("I want my lawyer", "dispute", True),
    ("item arrived damaged", "damage", True),
    ("asdf qwerty", "other", True),
    ("how do I pay", "pay", False),
    ("do you take paypal", "pay", False),
    ("do you sell open box", "other", True),
    ("are you open today", "hours", False),
]


def main() -> int:
    failed = 0
    for text, expect_id, expect_esc in CASES:
        got_id, got_esc = classify(text)
        ok = got_id == expect_id and got_esc == expect_esc
        print(("PASS" if ok else "FAIL") + f"  {text!r} -> {got_id}/{got_esc} (want {expect_id}/{expect_esc})")
        if not ok:
            failed += 1

    js = Path(__file__).resolve().parents[1] / "main.js"
    src = js.read_text(encoding="utf-8")
    for needle in (
        "window.BucSupport",
        "function classify(",
        "function reply(",
        "Ask BuccaneerSalvage",
        "/scrap.html",
        "/terms.html",
        "pick it up",
        "are you open",
        "will this fit",
        "We do not take PayPal",
    ):
        ok = needle in src
        print(("PASS" if ok else "FAIL") + f"  main.js contains {needle!r}")
        if not ok:
            failed += 1

    stale = "one item at a time" in src
    print(("PASS" if not stale else "FAIL") + "  main.js has no one-item cart note")
    if stale:
        failed += 1

    print("RESULT", "PASS" if failed == 0 else f"FAIL {failed}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
