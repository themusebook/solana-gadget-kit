#!/usr/bin/env python3
"""Read the shipped README and its hero animation from disk.

The check fails unless the README maps this checkout, quotes the host
facts, names the 0.4.4 path mismatch, and keeps SolanaOS as a neighbor.
It parses the GIF or APNG the README embeds. Frame count is measured
from the file, not stored beside it.
"""

import re
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"

REQUIRED = (
    "hardware_wallet",
    "lcd_status",
    "robotics_gate",
    "solana_os_check",
    "portfolio_preview",
    "src/",
    "include/",
    "tests/host_test.c",
    "esp32/",
    "linux/",
    "android/musegadgetstest/",
    "musegadgetstest/",
    "dashboard/",
    "web-flasher/",
    "docs/solana-os.md",
    "scripts/flash-solana-os.sh",
    "0.4.4/",
    "make test",
    "make examples",
    "solana-gadget-kit-hw-wallet-seed",
    "is not a funded key",
    "secret_export=refused",
    "physical confirm",
    "home, review, expired, and cancelled",
    "240×240",
    "servo:15",
    "arm.nudge",
    "mismatch, expiry, cancel, and a missing confirmation",
    "10000000 lamports",
    "2500000 USDC base units",
    "minimum out 980000",
    "SHA256SUMS",
    "firmware/solana-os/0.4.4",
    "https://github.com/themusebook/solanaos",
    "Go local-first trading runtime",
    "solanaos hardware",
    "Arduino Modulino",
    "I2C",
    "0x29",
    "0x3C",
    "0x44",
    "0x6A",
    "0x6C",
    "0x76",
    "0x7C",
    "not the Muse ESP32/Linux gadget link and not the BP26 badge",
    "Those buses are not the same protocol.",
    "Do not merge the trees",
    "Do not vendor SolanaOS",
    "modernize/java-upgrade",
    "no `.github/workflows/esp32.yml`",
    "./build/solana_os_check 0.4.4",
    "with no arguments is not the success case",
    "WALLET signature=",
    "confirmed_verify=ok unconfirmed=refused",
    "ROBOTICS match=applied mismatch=refused expired=refused cancelled=refused missing=refused",
    "SOLANA_OS 0.4.4 checksums=ok files=4",
    "PORTFOLIO sol=0.010000000 usdc=2.500000 quote_min_out=0.980000 venue=fixture",
    "LCD frames=home,review,expired,cancelled size=240x240",
    "iOS",
    "github.com/x402agent/Solana-Os-Go",
)

FORBIDDEN = (
    "make -C solana",
    "../esp32",
    "../linux",
    "../android",
    "../ios",
    "$CLAWD",
    "CLAWD",
    "<script",
    'type="module"',
)


def fail(message):
    print(f"FAIL {message}")
    return 1


def gif_frames(data):
    if data[:6] not in (b"GIF87a", b"GIF89a"):
        return None
    index = 6
    packed = data[index + 4]
    index += 7
    if packed & 0x80:
        index += 3 * (2 << (packed & 7))
    frames = 0
    loops = False
    while index < len(data):
        block = data[index]
        if block == 0x3B:
            break
        if block == 0x21:
            index += 1
            label = data[index]
            index += 1
            payload = bytearray()
            while True:
                size = data[index]
                index += 1
                payload += data[index:index + size]
                index += size
                if size == 0:
                    break
            if label == 0xFF and payload.startswith(b"NETSCAPE2.0"):
                loops = True
            continue
        if block == 0x2C:
            frames += 1
            index += 9
            packed = data[index]
            index += 1
            if packed & 0x80:
                index += 3 * (2 << (packed & 7))
            index += 1
            while True:
                size = data[index]
                index += 1 + size
                if size == 0:
                    break
            continue
        raise ValueError(f"unexpected GIF block {block:#x} at {index}")
    return frames, loops


def png_chunk(data, index):
    length = struct.unpack(">I", data[index:index + 4])[0]
    kind = data[index + 4:index + 8]
    body = data[index + 8:index + 8 + length]
    index += 12 + length
    return kind, body, index


def apng_frames(data):
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    index = 8
    frames = None
    plays = None
    while index + 8 <= len(data):
        kind, body, index = png_chunk(data, index)
        if kind == b"acTL" and len(body) >= 8:
            frames, plays = struct.unpack(">II", body[:8])
        if kind == b"IEND":
            break
    if frames is None:
        return 1, False
    return frames, plays == 0


def animation_frames(path):
    data = path.read_bytes()
    gif = gif_frames(data)
    if gif is not None:
        return gif
    apng = apng_frames(data)
    if apng is not None:
        return apng
    raise ValueError(f"{path} is not a GIF or APNG")


def hero_path(text):
    """The first markdown image in the opening, before the map."""
    head = "\n".join(text.splitlines()[:25])
    match = re.search(r"!\[[^\]]*\]\(([^)\s]+)\)", head)
    if not match:
        raise ValueError("no markdown image in the first 25 lines of README.md")
    raw = match.group(1)
    if "://" in raw or raw.startswith("/"):
        raise ValueError(f"hero must be a repo-relative file, got {raw}")
    return (README.parent / raw).resolve()


def main():
    errors = 0
    if not README.is_file():
        return fail(f"missing {README}")
    text = README.read_text(encoding="utf-8")
    if text.startswith("# Solana examples"):
        errors += fail("README is still the old Solana examples page")
    for item in REQUIRED:
        if item not in text:
            errors += fail(f"README missing {item!r}")
    for item in FORBIDDEN:
        if item in text:
            errors += fail(f"README contains forbidden {item!r}")
    signature = re.search(r"WALLET signature=([0-9a-f]{128}) confirmed_verify=ok", text)
    if not signature:
        errors += fail("README wallet line has no 128-hex signature")
    try:
        image = hero_path(text)
    except ValueError as exc:
        return fail(str(exc))
    if not image.is_file():
        return fail(f"hero image missing: {image}")
    try:
        frames, loops = animation_frames(image)
    except (ValueError, IndexError, struct.error) as exc:
        return fail(f"hero parse: {exc}")
    if frames <= 1:
        errors += fail(f"hero has {frames} frame")
    if not loops:
        errors += fail("hero does not loop")
    if errors:
        print(f"readme_check failed errors={errors}")
        return 1
    print(f"readme_check ok frames={frames} loops=yes bytes={image.stat().st_size} image={image.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
