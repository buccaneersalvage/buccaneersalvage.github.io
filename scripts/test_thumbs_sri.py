#!/usr/bin/env python3
"""Smoke/unit for build_product_thumbs + stamp_sri. No live download / no invent thumbs."""
from __future__ import annotations

import base64
import hashlib
import sys
from io import BytesIO
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_product_thumbs as thumbs  # noqa: E402
import stamp_sri as sri  # noqa: E402


def _tiny_png_rgb() -> bytes:
    im = Image.new("RGB", (80, 40), (200, 10, 10))
    buf = BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


def test_allowed_image_url():
    assert thumbs.allowed_image_url(
        "https://items-images-production.s3.us-west-2.amazonaws.com/files/x/original.jpeg"
    )
    assert thumbs.allowed_image_url("https://foo.squareup.com/bar.jpg")
    assert thumbs.allowed_image_url("https://cdn.squarecdn.com/x.webp")
    assert thumbs.allowed_image_url("https://buccaneersalvage.github.io/assets/x.webp")
    assert not thumbs.allowed_image_url("http://items-images-production.s3.us-west-2.amazonaws.com/x")
    assert not thumbs.allowed_image_url("https://evil.example/steal.jpg")
    assert not thumbs.allowed_image_url("javascript:alert(1)")


def test_to_webp_square_canvas():
    out = thumbs.to_webp(_tiny_png_rgb())
    assert out[:4] == b"RIFF" and out[8:12] == b"WEBP"
    im = Image.open(BytesIO(out))
    assert im.size == (thumbs.SIZE, thumbs.SIZE)
    assert im.format == "WEBP"


def test_sri384_prefix_and_roundtrip():
    data = b"hello-sri"
    tag = sri.sri384(data)
    assert tag.startswith("sha384-")
    digest = base64.b64decode(tag.split("-", 1)[1])
    assert digest == hashlib.sha384(data).digest()


def test_asset_rel():
    assert sri.asset_rel("store.js") == "store.js"
    assert sri.asset_rel("./store.js?v=deadbeef") == "store.js"
    assert sri.asset_rel("../main.js") == "main.js"
    assert sri.asset_rel("/assets/fonts.css?v=abc") == "assets/fonts.css"
    assert sri.asset_rel("https://cdn.example/store.js") is None
    assert sri.asset_rel("not-an-asset.js") is None


def test_rewrite_tag_stamps_v_and_integrity():
    stamps = {"store.js": ("aabbccddee", "sha384-TESTHASH")}
    tag = '<script src="store.js" defer></script>'
    out = sri.rewrite_tag(tag, stamps)
    assert 'src="store.js?v=aabbccddee"' in out
    assert 'integrity="sha384-TESTHASH"' in out
    # idempotent update of existing integrity
    tagged = '<script src="store.js?v=old" integrity="sha384-OLD" defer></script>'
    out2 = sri.rewrite_tag(tagged, stamps)
    assert "v=aabbccddee" in out2
    assert "sha384-TESTHASH" in out2
    assert "sha384-OLD" not in out2


def test_stamp_text_skips_foreign():
    stamps = sri.load_stamps()
    html = (
        '<link rel="stylesheet" href="styles.css" />'
        '<script src="https://cdn.example/x.js"></script>'
        '<script src="store.js" defer></script>'
    )
    out = sri.stamp_text(html, stamps)
    assert "styles.css?v=" in out and "integrity=" in out
    assert "https://cdn.example/x.js" in out
    assert "cdn.example" in out and "integrity" in out  # foreign tag unchanged-ish
    # foreign script should not gain our integrity from stamps of local files only
    foreign = re_search_script(out, "cdn.example")
    assert "integrity" not in foreign


def re_search_script(html: str, needle: str) -> str:
    import re

    for m in re.finditer(r"<script\b[^>]*>", html, re.I):
        if needle in m.group(0):
            return m.group(0)
    return ""


def test_load_stamps_covers_core():
    stamps = sri.load_stamps()
    for key in ("store.js", "main.js", "styles.css", "assets/redirect-store.js"):
        assert key in stamps
        v, h = stamps[key]
        assert len(v) == 10 and h.startswith("sha384-")


if __name__ == "__main__":
    tests = [
        test_allowed_image_url,
        test_to_webp_square_canvas,
        test_sri384_prefix_and_roundtrip,
        test_asset_rel,
        test_rewrite_tag_stamps_v_and_integrity,
        test_stamp_text_skips_foreign,
        test_load_stamps_covers_core,
    ]
    failed = 0
    for fn in tests:
        try:
            fn()
            print(f"PASS  {fn.__name__}")
        except Exception as exc:
            failed += 1
            print(f"FAIL  {fn.__name__}  {exc}")
    raise SystemExit(1 if failed else 0)
