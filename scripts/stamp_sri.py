#!/usr/bin/env python3
"""Stamp first-party CSS/JS with content-hash ?v= and sha384 SRI.

Run after CSS/JS freeze and after PDP regen. Idempotent.
Does not rewrite asset bytes — only HTML (and the PDP builder template).
"""
from __future__ import annotations

import base64
import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

ASSETS = (
    "styles.css",
    "videos.css",
    "main.js",
    "store.js",
    "pdp-gallery.js",
    "videos.js",
    "services.css",
    "services.js",
    "templates.css",
    "templates.js",
    "terms-service.css",
    "terms-service.js",
    "assets/fonts.css",
    "assets/vendor/list.min.js",
    "assets/redirect-store.js",
    "ukiri/styles.css",
    "ukiri/main.js",
    "ukiri/player.js",
)

TAG_RE = re.compile(r"<(?:link|script)\b[^>]*>", re.I)
HREFSRC_RE = re.compile(r"""\b(href|src)=(["'])([^"']+)\2""", re.I)
INTEGRITY_RE = re.compile(r"""\bintegrity=(["'])[^"']*\1""")
URL_RE = re.compile(r"^((?:\.\./)*)([^?]+)(?:\?.*)?$")


def sri384(data: bytes) -> str:
    digest = hashlib.sha384(data).digest()
    return "sha384-" + base64.b64encode(digest).decode("ascii")


def load_stamps() -> dict[str, tuple[str, str]]:
    out: dict[str, tuple[str, str]] = {}
    for rel in ASSETS:
        path = ROOT / rel
        if not path.is_file():
            raise SystemExit(f"missing asset: {path}")
        data = path.read_bytes()
        v = hashlib.sha256(data).hexdigest()[:10]
        out[rel] = (v, sri384(data))
    return out


def asset_rel(url: str) -> str | None:
    m = URL_RE.match(url.strip())
    if not m:
        return None
    rel = m.group(2).lstrip("./")
    return rel if rel in ASSETS else None


def rewrite_tag(tag: str, stamps: dict[str, tuple[str, str]]) -> str:
    m = HREFSRC_RE.search(tag)
    if not m:
        return tag
    url = m.group(3)
    rel = asset_rel(url)
    if not rel:
        return tag
    raw = url.strip()
    um = URL_RE.match(raw)
    assert um
    prefix = "/" if raw.startswith("/") else um.group(1)
    v, sri = stamps[rel]
    new_url = f"{prefix}{rel}?v={v}"
    attr, quote = m.group(1), m.group(2)
    tag = HREFSRC_RE.sub(f"{attr}={quote}{new_url}{quote}", tag, count=1)
    if INTEGRITY_RE.search(tag):
        tag = INTEGRITY_RE.sub(f'integrity="{sri}"', tag, count=1)
    else:
        tag = HREFSRC_RE.sub(
            f'{attr}={quote}{new_url}{quote} integrity="{sri}"',
            tag,
            count=1,
        )
    return tag


def stamp_text(text: str, stamps: dict[str, tuple[str, str]]) -> str:
    return TAG_RE.sub(lambda m: rewrite_tag(m.group(0), stamps), text)


def html_targets() -> list[Path]:
    files = sorted(ROOT.glob("*.html"))
    pdir = ROOT / "p"
    if pdir.is_dir():
        files.extend(sorted(pdir.glob("*.html")))
    sdir = ROOT / "shame"
    if sdir.is_dir():
        files.extend(sorted(sdir.glob("*.html")))
    builder = ROOT / "scripts" / "build_static_pdps.py"
    if builder.is_file():
        files.append(builder)
    ukiri = ROOT / "ukiri"
    if ukiri.is_dir():
        files.extend(sorted(ukiri.glob("*.html")))
    return files


def main() -> int:
    stamps = load_stamps()
    print("stamps:")
    for rel, (v, sri) in stamps.items():
        print(f"  {rel}  v={v}  {sri}")

    changed = 0
    for path in html_targets():
        old = path.read_text(encoding="utf-8")
        new = stamp_text(old, stamps)
        if new != old:
            path.write_text(new, encoding="utf-8")
            changed += 1
            print(f"  wrote {path.relative_to(ROOT)}")
    print(f"updated {changed} files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
