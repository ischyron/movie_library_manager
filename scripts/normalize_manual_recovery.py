#!/usr/bin/env python3
from __future__ import annotations

import csv
import re
from pathlib import Path


def parse_year_from_title(title: str) -> tuple[str, str]:
    m = re.search(r"\b(19|20)\d{2}\b", title)
    year = m.group(0) if m else ""
    return title, year


def normalize(path: Path) -> None:
    raw = list(csv.reader(path.open(encoding="utf-8")))
    out_rows = []
    for row in raw:
        if not row:
            continue
        title = (row[0] or "").strip()
        t, y = parse_year_from_title(title)
        out_rows.append({"title": t, "year": y})

    # backup original
    bak = path.with_suffix(path.suffix + ".bak")
    if not bak.exists():
        bak.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")

    # write normalized CSV with header
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["title", "year"])
        w.writeheader()
        for r in out_rows:
            w.writerow(r)


if __name__ == "__main__":
    normalize(Path("data/manual_recovery.csv"))

