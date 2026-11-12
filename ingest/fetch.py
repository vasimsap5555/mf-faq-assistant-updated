"""Download every fetchable source in data/sources.csv into data/raw/.

PDF sources come from files.hdfcfund.com / amfiindia.com and download directly.
www.hdfcfund.com HTML pages block automated clients, so those rows are marked
fetch_mode=snapshot and are read from data/snapshots/<id>.md instead.
"""
from __future__ import annotations

import sys
import time

import requests

from core import config

HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}


def main(force: bool = False) -> None:
    config.RAW_DIR.mkdir(parents=True, exist_ok=True)
    for sid, row in config.load_sources().items():
        mode = row["fetch_mode"]
        if mode in ("snapshot", "link_only"):
            print(f"{sid}  skip ({mode})")
            continue
        ext = "pdf" if mode == "pdf" else "html"
        dest = config.RAW_DIR / f"{sid}.{ext}"
        if dest.exists() and not force:
            print(f"{sid}  cached")
            continue
        try:
            r = requests.get(row["url"], headers=HEADERS, timeout=90)
            r.raise_for_status()
            dest.write_bytes(r.content)
            print(f"{sid}  ok  {len(r.content) // 1024} KB")
        except requests.RequestException as e:
            print(f"{sid}  FAILED: {e}", file=sys.stderr)
        time.sleep(0.5)


if __name__ == "__main__":
    main(force="--force" in sys.argv)
