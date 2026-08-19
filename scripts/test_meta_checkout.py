#!/usr/bin/env python3
"""Parse Meta Shops products= query the same way main.js does."""
from __future__ import annotations

import re
import sys

ID_RE = re.compile(r"^[A-Z0-9]{16,32}$")
MAX_QTY = 20
MAX_LINES = 30


def parse_meta_products_param(raw: str) -> list[tuple[str, int]]:
    s = (raw or "").strip()
    if not s:
        return []
    out: list[tuple[str, int]] = []
    for part in s.split(","):
        bit = part.strip()
        if not bit:
            continue
        colon = bit.rfind(":")
        pid = (bit if colon == -1 else bit[:colon]).strip()
        qty_raw = "1" if colon == -1 else bit[colon + 1 :].strip()
        if not ID_RE.fullmatch(pid):
            continue
        try:
            qty = int(float(qty_raw))
        except ValueError:
            qty = 1
        qty = max(1, min(MAX_QTY, qty))
        out.append((pid, qty))
    return out[:MAX_LINES]


CASES = [
    ("", []),
    ("R6VO2MARXN7GRGTMXVGABLHT:2", [("R6VO2MARXN7GRGTMXVGABLHT", 2)]),
    (
        "R6VO2MARXN7GRGTMXVGABLHT:3,5JADFNOGZU4ORSIITZGU6T3I:1",
        [("R6VO2MARXN7GRGTMXVGABLHT", 3), ("5JADFNOGZU4ORSIITZGU6T3I", 1)],
    ),
    ("not-an-id:1", []),
    ("R6VO2MARXN7GRGTMXVGABLHT", [("R6VO2MARXN7GRGTMXVGABLHT", 1)]),
    ("R6VO2MARXN7GRGTMXVGABLHT:99", [("R6VO2MARXN7GRGTMXVGABLHT", 20)]),
]


def main() -> int:
    failed = 0
    for raw, expect in CASES:
        got = parse_meta_products_param(raw)
        ok = got == expect
        print(f"{'PASS' if ok else 'FAIL'}  {raw!r} -> {got}")
        if not ok:
            print(f"       expected {expect}")
            failed += 1
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
