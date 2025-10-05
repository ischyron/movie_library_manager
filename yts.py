from __future__ import annotations

import csv
import time
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple
import difflib
import csv as _csv
from tempfile import NamedTemporaryFile

import requests


API_BASE = "https://yts.mx/api/v2"

# Console colors
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RESET = "\033[0m"

# Preference config (can be tuned centrally)
RATING_UHD_THRESHOLD = 7.0
PREF_QUALITIES_HIGH = ["2160p", "1080p", "720p"]
PREF_QUALITIES_DEFAULT = ["1080p", "720p"]


@dataclass
class YTSMovie:
    id: int
    title: str
    year: int
    url: str
    torrents: List[Dict]
    rating: float


def _sanitize_title(s: str) -> str:
    # Normalize separators, drop year in parentheses, strip punctuation, lower
    s = re.sub(r"[._]+", " ", s)
    s = re.sub(r"\((\d{4})\)", "", s)
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip().lower()
    return s


def _build_query(title: str, year: Optional[int]) -> str:
    q = title
    if year:
        q = f"{title} {year}"
    return q


def yts_search(title: str, year: Optional[int], timeout: float, retries: int, slow_after: float, verbose: bool) -> List[YTSMovie]:
    q = _build_query(_sanitize_title(title), year)
    params = {
        "query_term": q,
        "limit": 10,
        "sort_by": "year",
        "order_by": "desc",
    }
    url = f"{API_BASE}/list_movies.json"
    attempt = 0
    backoff = 0.75
    while True:
        attempt += 1
        t0 = time.monotonic()
        try:
            if verbose:
                print(f"[yts] GET {url} q='{q}' attempt={attempt}")
            r = requests.get(url, params=params, timeout=timeout)
            elapsed = time.monotonic() - t0
            if verbose:
                print(f"[yts] status={r.status_code} elapsed={elapsed:.2f}s")
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
                        rating=float(m.get("rating") or 0.0),
                    )
                )
            # Retry if the request was too slow, as requested
            if elapsed >= slow_after and attempt <= retries:
                if verbose:
                    print(f"[yts] slow ({elapsed:.2f}s >= {slow_after}s); retrying after backoff {backoff:.2f}s")
                time.sleep(backoff)
                backoff *= 2
                continue
            return movies
        except Exception as e:
            elapsed = time.monotonic() - t0
            if attempt <= retries:
                wait = backoff
                if verbose:
                    print(f"[yts] error: {e} (elapsed {elapsed:.2f}s); retry {attempt}/{retries} after {wait:.2f}s")
                time.sleep(wait)
                backoff *= 2
                continue
            if verbose:
                print(f"[yts] failed after {attempt-1} retries: {e}")
            return []


def _title_similarity(a: str, b: str) -> float:
    a_n = _sanitize_title(a)
    b_n = _sanitize_title(b)
    return difflib.SequenceMatcher(None, a_n, b_n).ratio()


def _best_match(movies: List[YTSMovie], title: str, year: Optional[int]) -> Optional[YTSMovie]:
    if not movies:
        return None
    # If year provided, first try exact year matches and pick the closest title
    if year:
        same_year = [m for m in movies if m.year == year]
        if same_year:
            best = max(same_year, key=lambda m: _title_similarity(title, m.title))
            return best
    # Otherwise choose by title similarity, breaking ties by nearest year if input year provided
    def score(m: YTSMovie) -> Tuple[float, float]:
        sim = _title_similarity(title, m.title)
        if year:
            yd = abs(m.year - year) if m.year and year else 9999
            return (sim, -1.0 / (1 + yd))
        return (sim, 0.0)

    return max(movies, key=score)


QUALITY_RANK = {"720p": 1, "1080p": 2, "1440p": 2.5, "2160p": 3, "4k": 3, "uhd": 3}


def _detect_current_quality(name: str) -> float:
    s = name.lower()
    for token, rank in ("2160p", 3), ("4k", 3), ("uhd", 3), ("1440p", 2.5), ("1080p", 2), ("1024p", 1.5), ("720p", 1):
        if token in s:
            return rank
    return 0.0


def _choose_next_quality(match: YTSMovie, cur_rank: float) -> Tuple[str, Optional[Dict]]:
    # Build qualities map -> preferred torrent (prefer bluray type)
    by_quality: Dict[str, List[Dict]] = {}
    for t in match.torrents:
        q = (t.get("quality") or "").lower()
        if not q:
            continue
        by_quality.setdefault(q, []).append(t)
    for q, arr in by_quality.items():
        arr.sort(key=lambda t: 0 if (t.get("type") or "").lower()=="bluray" else 1)

    pref = PREF_QUALITIES_HIGH if match.rating >= RATING_UHD_THRESHOLD else PREF_QUALITIES_DEFAULT
    for want in pref:
        qk = want.lower()
        rank = QUALITY_RANK.get(qk, 0)
        if rank > cur_rank and qk in by_quality:
            return want, by_quality[qk][0]
    # Fallback: highest available above current
    candidates = []
    for qk, arr in by_quality.items():
        rank = QUALITY_RANK.get(qk, 0)
        if rank > cur_rank:
            candidates.append((rank, qk, arr[0]))
    if candidates:
        candidates.sort(reverse=True)
        _, qk, tor = candidates[0]
        return qk, tor
    return "", None


def magnet_from_torrent(title: str, torrent: Dict) -> str:
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
    in_place: bool,
    concurrency: int,
    timeout: float,
    retries: int,
    slow_after: float,
    verbose: bool,
) -> None:
    rows = list(_iter_csv_rows(input_csv))

    # Determine current quality rank if available
    cur_ranks: List[float] = []
    for row in rows:
        src = row.get("path") or row.get("folder_path") or ""
        cur_ranks.append(_detect_current_quality(src))

    def task(row: Dict[str, str]) -> Tuple[Dict[str, str], Optional[YTSMovie]]:
        title = (row.get("title") or row.get("title_guess") or row.get("folder_path") or "").split("/")[-1].strip()
        year = row.get("year")
        y = int(year) if year else None
        movies = yts_search(title, y, timeout=timeout, retries=retries, slow_after=slow_after, verbose=verbose)
        return row, _best_match(movies, title, y)

    out_rows: List[List[str]] = []

    def process_one(row: Dict[str, str]) -> None:
        title = (row.get("title") or row.get("title_guess") or row.get("folder_path") or "").split("/")[-1].strip()
        year = row.get("year") or ""
        src = row.get("path") or row.get("folder_path") or ""
        cur_rank = _detect_current_quality(src)
        if verbose:
            print(f"[yts] item: src='{src}' title='{title}' year='{year or ''}' cur_rank={cur_rank}")
        try:
            _, match = task(row)
        except Exception as e:
            if verbose:
                print(f"{RED}[yts] ERROR item failed: src='{src}' err={e}{RESET}")
            out_rows.append([src, "", "", "", "", ""])  # keep placeholder row
            return

        if match is None:
            if verbose:
                print(f"{RED}[yts] no match: title='{title}' year='{year or ''}'{RESET}")
            out_rows.append([src, title, year or "", "", "", ""])  # no results
            return

        kept_q: List[str] = []
        kept_mag: List[str] = []
        all_q: List[str] = []
        for t in match.torrents:
            q = t.get("quality") or ""
            typ = t.get("type") or ""
            all_q.append(f"{q}.{typ}")
            rank = QUALITY_RANK.get(q.lower(), 0)
            if rank > cur_rank:
                kept_q.append(f"{q}.{typ}")
                kept_mag.append(magnet_from_torrent(match.title, t))
        next_q, next_t = _choose_next_quality(match, cur_rank)
        next_mag = magnet_from_torrent(match.title, next_t) if next_t else ""
        if verbose:
            color = GREEN if kept_q else YELLOW
            print(f"{color}[yts] match: '{match.title}' ({match.year}) rating={match.rating} url={match.url}{RESET}")
            print(f"{color}[yts] torrents: total={len(all_q)} kept_higher={len(kept_q)} next={next_q or '-'}{RESET}")
            if len(all_q) > 0:
                print(f"[yts] all_qualities: {sorted(set(all_q))}")
            if len(kept_q) > 0:
                print(f"[yts] kept_qualities: {sorted(set(kept_q))}")

        out_rows.append([
            src,
            match.title,
            str(match.year),
            match.url,
            "|".join(sorted(set(all_q))),  # yts_quality_available (all qualities)
            next_q,
            next_mag,
        ])

    if max(1, concurrency) == 1:
        for row in rows:
            process_one(row)
    else:
        with ThreadPoolExecutor(max_workers=max(1, concurrency)) as ex:
            futs = [ex.submit(process_one, row) for row in rows]
            for fut in as_completed(futs):
                try:
                    fut.result()
                except Exception as e:
                    if verbose:
                        print(f"{RED}[yts] task error: {e}{RESET}")

    if in_place:
        # Merge columns into the input CSV by matching path/folder_path
        # Build a lookup from source_path to result row
        by_src: Dict[str, List[str]] = {r[0]: r for r in out_rows}
        with input_csv.open() as f_in:
            reader = _csv.DictReader(f_in)
            fieldnames = reader.fieldnames or []
            add_cols = ["yts_title", "yts_year", "yts_url", "qualities", "magnets"]
            new_fields = fieldnames + [c for c in add_cols if c not in fieldnames]
            tmp = NamedTemporaryFile("w", delete=False, dir=str(input_csv.parent), newline="")
            try:
                w = _csv.DictWriter(tmp, fieldnames=new_fields)
                w.writeheader()
                f_in.seek(0)
                next(f_in)  # skip header
                for row in _csv.reader(f_in):
                    pass
            finally:
                tmp.close()
            # Re-read to actually emit rows preserving order
        # Simpler: iterate original rows list
        tmp_path = input_csv.with_suffix(input_csv.suffix + ".tmp")
        with tmp_path.open("w", newline="") as f_out:
            w = _csv.writer(f_out)
            header = (rows and list(rows[0].keys())) or []
            add_cols = ["yts_title", "yts_year", "yts_url", "yts_quality_available", "yts_next_quality", "magnet"]
            w.writerow(header + add_cols)
            for row in rows:
                src = row.get("path") or row.get("folder_path") or ""
                res = by_src.get(src, ["", "", "", "", "", "", ""])
                w.writerow([row.get(k, "") for k in header] + res[1:])
        tmp_path.replace(input_csv)
        print(f"Updated {input_csv}")
    else:
        # Write separate output CSV
        header = ["source_path", "yts_title", "yts_year", "yts_url", "yts_quality_available", "yts_next_quality", "magnet"]
        with output_csv.open("w", newline="") as f:
            w = csv.writer(f)
            w.writerow(header)
            for r in out_rows:
                w.writerow(r)
        print(f"Wrote {output_csv}")
