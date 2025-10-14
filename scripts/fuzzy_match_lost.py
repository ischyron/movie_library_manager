#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import difflib
import re
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import scanner as _scanner


def _norm_title(s: str) -> str:
    s = s or ""
    s = re.sub(r"[._]+", " ", s)
    s = re.sub(r"\((\d{4})\)", "", s)
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip().lower()
    return s


def _guess_title_and_year_from_row(row: Dict[str, str]) -> Tuple[str, Optional[int]]:
    # try common fields that may contain a folder-ish movie string
    for key in ("folder_path", "path", "movie", "title", "name", "folder"):
        val = (row.get(key) or "").strip()
        if val:
            # prefer leaf folder name if a path
            leaf = val.rsplit("/", 1)[-1]
            t, y = _scanner._clean_title_and_year(leaf)  # type: ignore[attr-defined]
            if t:
                return t, y
    # fallback: first non-empty field
    for v in row.values():
        s = (v or "").strip()
        if s:
            leaf = s.rsplit("/", 1)[-1]
            t, y = _scanner._clean_title_and_year(leaf)  # type: ignore[attr-defined]
            if t:
                return t, y
    return "", None


def index_library(root: Path) -> List[Tuple[Path, str, Optional[int]]]:
    items: List[Tuple[Path, str, Optional[int]]] = []
    if not root.exists():
        return items
    for p in sorted(root.iterdir(), key=lambda x: x.name.lower()):
        if p.is_dir():
            t, y = _scanner._clean_title_and_year(p.name)  # type: ignore[attr-defined]
            items.append((p, t, y))
    return items


def best_match(title: str, year: Optional[int], lib: List[Tuple[Path, str, Optional[int]]]) -> Tuple[Optional[Path], float]:
    t_norm = _norm_title(title)
    best: Tuple[Optional[Path], float] = (None, 0.0)
    # exact match pass
    for p, t, y in lib:
        if _norm_title(t) == t_norm and (year is None or y == year):
            return p, 1.0
    # fuzzy similarity with small year boost
    for p, t, y in lib:
        sim = difflib.SequenceMatcher(None, t_norm, _norm_title(t)).ratio()
        if year is not None and y == year:
            sim += 0.05
        if sim > best[1]:
            best = (p, sim)
    return best


def run(in_csv: Path, movies_root: Path, out_csv: Path, min_score: float) -> Tuple[int, int]:
    with in_csv.open(newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        rows = list(r)

    lib = index_library(movies_root)

    lost_rows: List[Dict[str, str]] = []
    for row in rows:
        title, year = _guess_title_and_year_from_row(row)
        if not title:
            # consider missing title as lost
            lost_rows.append({"title": "", "year": "", "status": "lost", "best_match": "", "score": "0.00"})
            continue
        p, score = best_match(title, year, lib)
        if p is None or score < min_score:
            lost_rows.append({
                "title": title,
                "year": str(year or ""),
                "status": "lost",
                "best_match": "",
                "score": f"{score:.2f}",
            })

    # write lost-only file with the title/year we will use downstream
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["title", "year", "status", "best_match", "score"])
        w.writeheader()
        for r in lost_rows:
            w.writerow(r)

    return len(rows), len(lost_rows)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Fuzzy-match combined lost titles against a Movies folder and keep truly lost ones.")
    ap.add_argument("--in", dest="in_csv", default="data/data_loss_2017.csv", type=Path)
    ap.add_argument("--root", default="/Volumes/Extreme SSD/Movies", type=Path)
    ap.add_argument("--out", dest="out_csv", default="data/data_loss_2017.csv", type=Path)
    ap.add_argument("--min-score", type=float, default=0.88)
    args = ap.parse_args(argv)

    total, lost = run(args.in_csv, args.root, args.out_csv, args.min_score)
    print(f"Matched: kept {lost} lost of {total} total -> {args.out_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

