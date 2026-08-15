#!/usr/bin/env python3
"""Download Square catalog images and write 400x400 WebP thumbs."""
from __future__ import annotations

import json
import re
import sys
import urllib.error
import urllib.request
from io import BytesIO
from pathlib import Path
from urllib.parse import urlparse

from PIL import Image

HUB = Path(__file__).resolve().parents[1]
CATALOG = HUB / "assets" / "square-catalog.json"
OUT = HUB / "assets" / "product-thumbs"
MANIFEST = OUT / "manifest.json"
SIZE = 400
UA = "BuccaneerSalvageHub/1.0 (product-thumbs; local build)"
SQUARE_ID_RE = re.compile(r"^[A-Z0-9]{16,32}$")
ALLOWED_IMG_HOSTS = (
    "buccaneersalvage.github.io",
    "items-images-production.s3.us-west-2.amazonaws.com",
)


def allowed_image_url(url: str) -> bool:
    if not url.startswith("https://"):
        return False
    try:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
    except Exception:
        return False
    return (
        host in ALLOWED_IMG_HOSTS
        or host.endswith(".squareup.com")
        or host.endswith(".squarecdn.com")
    )


def load_items() -> list[dict]:
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    items = data.get("items") if isinstance(data, dict) else data
    if not isinstance(items, list):
        raise SystemExit("catalog has no items list")
    return items


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=45) as resp:
        return resp.read()


def to_webp(raw: bytes) -> bytes:
    im = Image.open(BytesIO(raw))
    if im.mode not in ("RGB", "RGBA"):
        im = im.convert("RGB")
    elif im.mode == "RGBA":
        bg = Image.new("RGB", im.size, (12, 10, 8))
        bg.paste(im, mask=im.split()[-1])
        im = bg
    im.thumbnail((SIZE, SIZE), Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", (SIZE, SIZE), (12, 10, 8))
    x = (SIZE - im.width) // 2
    y = (SIZE - im.height) // 2
    canvas.paste(im, (x, y))
    buf = BytesIO()
    canvas.save(buf, format="WEBP", quality=80, method=4)
    return buf.getvalue()


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    items = load_items()
    ok, skip, fail = 0, 0, []
    for item in items:
        iid = str(item.get("id") or "").strip()
        url = str(item.get("image") or "").strip()
        if not SQUARE_ID_RE.fullmatch(iid):
            fail.append({"id": iid, "error": "bad catalog id"})
            continue
        dest = (OUT / f"{iid}.webp").resolve()
        if dest.parent != OUT.resolve():
            fail.append({"id": iid, "error": "path escaped thumbs dir"})
            continue
        if dest.exists() and dest.stat().st_size > 200:
            skip += 1
            continue
        if not allowed_image_url(url):
            fail.append({"id": iid, "error": "image host not allowlisted"})
            continue
        try:
            dest.write_bytes(to_webp(fetch(url)))
            ok += 1
            print(f"ok {iid}", flush=True)
        except (urllib.error.URLError, OSError, ValueError) as e:
            fail.append({"id": iid, "error": str(e)[:200]})
            print(f"FAIL {iid} {e}", flush=True)
    thumbs = sorted(p.name for p in OUT.glob("*.webp"))
    MANIFEST.write_text(
        json.dumps(
            {"count": len(thumbs), "generated": ok, "skipped": skip, "failed": fail},
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"thumbs={len(thumbs)} generated={ok} skipped={skip} failed={len(fail)}")
    if fail and ok == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
