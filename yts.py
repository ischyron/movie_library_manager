from __future__ import annotations

import csv
import html
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import requests


API_BASE = "https://yts.mx/api/v2"


@dataclass
class YTSMovie:
    id: int
    title: str
    year: int
    url: str
    torrents: List[Dict]


def _sanitize_title(s: str) -> str:
    s = re.sub(r"[._]+", " ", s).strip()
    return s


def _build_query(title: str, year: Optional[int]) -> str:
    q = title
    if year:
        q = f"{title} {year}"
    return q


def yts_search(title: str, year: Optional[int], timeout: float) -> List[YTSMovie]:
    q = _build_query(_sanitize_title(title), year)
    params = {
        "query_term": q,
        "limit": 10,
        "sort_by": "year",
        "order_by": "desc",
    }
    r = requests.get(f"{API_BASE}/list_movies.json", params=params, timeout=timeout)
    r.raise_for_status()
    data = r.json()
    movies = []
    for m in (data.get("data", {}) or {}).get("movies", []) or []:
        movies.append(
            YTSMovie(
                id=m["id"],
                title=m.get("title") or "",
                year=m.get("year") or 0,
                url=m.get("url") or "",
                torrents=m.get("torrents") or [],
            )
        )
    return movies


def _best_match(movies: List[YTSMovie], title: str, year: Optional[int]) -> Optional[YTSMovie]:
    # Prefer exact year match if provided; else take first result
    if year:
        for m in movies:
            if m.year == year:
                return m
    return movies[0] if movies else None


def magnet_from_torrent(title: str, torrent: Dict) -> str:
    # Builds a basic magnet link from torrent hash and title
    # dn (display name) is URL-encoded title + quality
    from urllib.parse import quote

    name = f"{title}.{torrent.get('quality','')}.{torrent.get('type','')}"
    xt = f"urn:btih:{torrent.get('hash','')}"
    return f"magnet:?xt={xt}&dn={quote(name)}"


def _iter_csv_rows(path: Path) -> Iterable[Dict[str, str]]:
    with path.open() as f:
        r = csv.DictReader(f)
        for row in r:
            yield row


def yts_lookup_from_csv(
    input_csv: Path,
    output_csv: Path,
    is_lost: bool,
    concurrency: int,
    timeout: float,
) -> None:
    rows = list(_iter_csv_rows(input_csv))

    def task(row: Dict[str, str]) -> Tuple[Dict[str, str], Optional[YTSMovie]]:
        title = (row.get("title") or "").strip()
        year = row.get("year")
        y = int(year) if year else None
        movies = yts_search(title, y, timeout=timeout)
        return row, _best_match(movies, title, y)

    out_rows: List[List[str]] = []

    with ThreadPoolExecutor(max_workers=max(1, concurrency)) as ex:
        futs = [ex.submit(task, row) for row in rows]
        for fut in as_completed(futs):
            row, match = fut.result()
            if match is None:
                out_rows.append([
                    row.get("path") or row.get("folder_path") or "",
                    row.get("title") or "",
                    row.get("year") or "",
                    "",
                    "",
                    "",
                ])
                continue

            qualities = []
            magnets = []
            for t in match.torrents:
                q = t.get("quality") or ""
                typ = t.get("type") or ""
                qualities.append(f"{q}.{typ}")
                magnets.append(magnet_from_torrent(match.title, t))

            out_rows.append([
                row.get("path") or row.get("folder_path") or "",
                match.title,
                str(match.year),
                match.url,
                "|".join(sorted(set(qualities))),
                "|".join(magnets),
            ])

    # Write output CSV
    header = ["source_path", "yts_title", "yts_year", "yts_url", "qualities", "magnets"]
    with output_csv.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        for r in out_rows:
            w.writerow(r)

    print(f"Wrote {output_csv}")

