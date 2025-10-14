#!/usr/bin/env python3
from __future__ import annotations

import csv
import sys
from pathlib import Path
import re


INPUT = Path("data/manual_recovery.csv")
BACKUP = INPUT.with_suffix(INPUT.suffix + ".bak")


def _normalize_title(s: str) -> str:
    # Strip known prefixes like "James Bond - " (case-insensitive)
    s = re.sub(r"^\s*james\s+bond\s*-\s*", "", s, flags=re.IGNORECASE)
    # Replace dots with spaces (e.g., Les.Miserables -> Les Miserables)
    s = s.replace(".", " ")
    # Collapse whitespace
    s = re.sub(r"\s+", " ", s).strip()
    return s


def extract_titles(path: Path) -> list[str]:
    titles: list[str] = []
    seen = set()
    if not path.exists():
        return titles
    raw = path.read_text(encoding="utf-8", errors="ignore")
    # Split on newlines, also handle accidental clumps separated by commas-only lines
    for line in raw.splitlines():
        s = line.strip().strip("\r").strip()
        if not s:
            continue
        # If this looks like a CSV row, take the first field as the title
        if "," in s:
            s = s.split(",", 1)[0].strip().strip('"')
        s = _normalize_title(s)
        # Ignore pure commas rows
        if not s or all(c == "," for c in s):
            continue
        if s not in seen:
            seen.add(s)
            titles.append(s)
    return titles


def write_single_column(path: Path, titles: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["title"])  # single column header
        for t in titles:
            w.writerow([t])


def main() -> int:
    if not INPUT.exists():
        print(f"ERROR: {INPUT} not found", file=sys.stderr)
        return 2
    # Backup once
    if not BACKUP.exists():
        BACKUP.write_text(INPUT.read_text(encoding="utf-8", errors="ignore"), encoding="utf-8")
    titles = extract_titles(INPUT)
    write_single_column(INPUT, titles)
    print(f"Cleaned {INPUT}: {len(titles)} titles, single-column 'title'")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
