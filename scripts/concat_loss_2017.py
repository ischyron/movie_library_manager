#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import List, Dict


def gather_csvs(in_dir: Path, pattern: str) -> List[Path]:
    return sorted(in_dir.glob(pattern))


def read_all_rows(paths: List[Path]) -> (List[str], List[Dict[str, str]]):
    rows: List[Dict[str, str]] = []
    header_set = []  # preserve discovery order
    seen = set()
    for p in paths:
        with p.open(newline="", encoding="utf-8") as f:
            r = csv.DictReader(f)
            if r.fieldnames:
                for h in r.fieldnames:
                    if h not in seen:
                        seen.add(h)
                        header_set.append(h)
            for row in r:
                rows.append({k: (v or "") for k, v in row.items()})
    return header_set, rows


def write_out(out: Path, header: List[str], rows: List[Dict[str, str]]) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=header)
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, "") for k in header})


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Concatenate CSVs from a folder into data_loss_2017.csv with unified header.")
    ap.add_argument("--dir", default="data/lost-2017", type=Path, help="Folder with per-row CSVs")
    ap.add_argument("--glob", default="*.csv", help="Glob pattern to pick CSVs in the folder")
    ap.add_argument("--out", default="data/data_loss_2017.csv", type=Path, help="Output CSV path")
    args = ap.parse_args(argv)

    if not args.dir.exists():
        print(f"ERROR: input dir does not exist: {args.dir}")
        return 2

    csvs = gather_csvs(args.dir, args.glob)
    if not csvs:
        print(f"ERROR: no CSV files matched {args.glob} in {args.dir}")
        return 3

    header, rows = read_all_rows(csvs)
    write_out(args.out, header, rows)
    print(f"Wrote {args.out} from {len(csvs)} file(s), {len(rows)} row(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

