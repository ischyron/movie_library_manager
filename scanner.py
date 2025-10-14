from __future__ import annotations

import csv
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple


GOOD_TITLE_RE = re.compile(r"^(?P<title>.+?)\s*\((?P<year>\d{4})\)")

# Built-in ignore list for accessory/system folders (case-insensitive)
# Matches Agents Guide defaults so users don't need to pass --ignore-dirs.
DEFAULT_IGNORE_DIRS: Set[str] = {
    # system metadata
    ".appledouble", ".ds_store", "@eadir", "recycle.bin", "lost+found", ".git",
    # accessory media folders
    "subs", "subtitles", "extras", "featurettes", "trailers", "art", "artwork",
    "posters", "covers", "metadata", "plex versions", ".actors", "other",
    # legacy/sample content
    "sample", "samples",
}


@dataclass
class VideoEntry:
    path: Path
    size_bytes: int
    reason: str
    tokens_matched: List[str]

    @property
    def size_mib(self) -> float:
        return self.size_bytes / (1024 * 1024)


def _iter_dirs(root: Path, ignore_dirs: Optional[Set[str]] = None) -> Iterable[Path]:
    if ignore_dirs is None:
        ignore_dirs = DEFAULT_IGNORE_DIRS
    for dirpath, dirnames, filenames in os.walk(root):
        # prune ignored + dot directories
        pruned = []
        for d in list(dirnames):
            if d.startswith('.'):
                continue
            if d.lower() in ignore_dirs:
                continue
            pruned.append(d)
        dirnames[:] = pruned
        yield Path(dirpath)


def _is_video(path: Path, video_exts: Set[str]) -> bool:
    return path.suffix.lower().lstrip(".") in video_exts


def _is_subtitle(path: Path, subtitle_exts: Set[str]) -> bool:
    return path.suffix.lower().lstrip(".") in subtitle_exts


def _match_tokens(name: str, tokens: List[str]) -> List[str]:
    found = []
    low = name.lower()
    for t in tokens:
        if not t:
            continue
        if t.lower() in low:
            found.append(t)
    return found


_BRACKET_RX = re.compile(r"\[[^\]]*\]|\([^\)]*\)|\{[^\}]*\}")
_SEPS_RX = re.compile(r"[._]+")
_TOKENS_RX = re.compile(
    r"""
    \b(
        480p|576p|720p|1024p|1080p|1440p|2160p|4k|uhd|hdr|hdr10|dolby\s+vision|
        x264|x265|xvid|divx|h\.?26[45]|avc|hevc|
        dvdrip|brrip|bdrip|bluray|web[- ]?dl|web[- ]?rip|hdrip|tvrip|pdtv|r5|cams?|ts|tc|telesync|telecine|
        proper|repack|extended|limited|uncut|
        dts(?:-?hd)?|truehd|atmos|aac|ac-3|eac3|mp3|
        multi|subs?|subtitles|dubbed|nl|eng|ita|spa|fre|fr|ger|deu|hin|rus
    )\b
""", re.IGNORECASE | re.VERBOSE)

# Size tokens like 350MB, 1.4 GB, 700MiB
_SIZE_RX = re.compile(r"\b\d+(?:\.\d+)?\s*(?:MB|MiB|GB|GiB)\b", re.IGNORECASE)
# Trailing release group patterns like " - VYTO", "-YIFY", "-RARBG" at end
_TRAIL_GROUP_RX = re.compile(r"[\s]*[-–—][\s]*[A-Za-z0-9][A-Za-z0-9._-]{1,}$")

def _clean_title_and_year(text: str) -> Tuple[str, int | None]:
    s = _SEPS_RX.sub(" ", text)
    # remove bracketed content
    s = _BRACKET_RX.sub(" ", s)
    # first codec/source token
    tok = _TOKENS_RX.search(s)
    tok_idx = tok.start() if tok else None
    # plausible year only if not leading (avoid stripping titles like '2001'/'1984')
    ym = None
    for m in re.finditer(r"\b(19|20)\d{2}\b", s):
        if m.start() > 0:
            ym = m
            break
    year = int(ym.group(0)) if ym else None
    year_idx = ym.start() if ym else None
    # cut at earliest token/year if any
    candidates = [i for i in (tok_idx, year_idx) if i is not None]
    if candidates:
        s = s[:min(candidates)]
    # strip remaining tokens, sizes, and trailing group markers
    s = _TOKENS_RX.sub(" ", s)
    s = _SIZE_RX.sub(" ", s)
    s = _TRAIL_GROUP_RX.sub(" ", s)
    s = re.sub(r"\s{2,}", " ", s).strip(" -_.\t\n\r").strip()
    return s, year

def _parse_title_year_from_path(path: Path) -> Tuple[str, int | None]:
    folder = path.parent.name
    file_stem = path.stem

    # Prefer folder metadata for title (and year if present)
    m_folder = GOOD_TITLE_RE.match(folder)
    if m_folder:
        return m_folder.group("title").strip(), int(m_folder.group("year"))

    # Clean folder name into title; attempt to infer year from folder or file
    title, year = _clean_title_and_year(folder)
    if year is not None:
        return title, year

    # Try to get a year from the filename without adopting its title
    m_file = GOOD_TITLE_RE.match(file_stem)
    if m_file:
        return title, int(m_file.group("year"))

    _, fyear = _clean_title_and_year(file_stem)
    return title, fyear


def _looks_like_movie_dir(name: str) -> bool:
    return GOOD_TITLE_RE.match(name) is not None


def scan_library(
    root: Path,
    out_dir: Path,
    tiny_mib: int,
    good_tokens: List[str],
    lowq_tokens: List[str],
    video_exts: List[str],
    subtitle_exts: List[str],
    ignore_dirs: Optional[List[str]] = None,
) -> None:
    root = root.expanduser().resolve()
    out_dir = out_dir.expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    vexts = set(e.lower() for e in video_exts)
    sexts = set(e.lower() for e in subtitle_exts)
    ignores = set(d.lower() for d in ignore_dirs) if ignore_dirs else None

    lowq_rows: List[VideoEntry] = []
    lost_rows: List[Tuple[Path, str, int, int]] = []  # (folder, reason, file_count, video_count)

    # Track directories that contain any non-zero-length video directly
    has_nonzero_video: Dict[Path, bool] = {}
    # Track whether any ancestor (parent chain) contains a non-zero-length video
    ancestor_has_video: Dict[Path, bool] = {}

    tiny_bytes = tiny_mib * 1024 * 1024

    for d in _iter_dirs(root, ignores):
        # gather files
        files = [p for p in d.iterdir() if p.is_file()]
        child_dirs = [c for c in d.iterdir() if c.is_dir()]
        vids = [p for p in files if _is_video(p, vexts)]
        subs = [p for p in files if _is_subtitle(p, sexts)]

        is_movie_dir = _looks_like_movie_dir(d.name)
        is_collection_container = any(_looks_like_movie_dir(c.name) for c in child_dirs)

        # compute direct non-zero video presence for current directory
        nonzero_vids = [p for p in vids if p.stat().st_size > 0]
        # treat any folder with non-zero videos as a movie folder for ancestor blocking
        # (but do not propagate from collection containers)
        has_nonzero_video[d] = (len(nonzero_vids) > 0) and (not is_collection_container)
        # compute ancestor_has_video by inheriting from parent
        parent = d.parent if d != root else None
        ancestor_has_video[d] = False
        if parent is not None:
            ancestor_has_video[d] = has_nonzero_video.get(parent, False) or ancestor_has_video.get(parent, False)

        # Determine "lost" leaf folders: no subdirs and no non-zero-length videos
        has_child_dirs = len(child_dirs) > 0
        if not has_child_dirs:
            if len(nonzero_vids) == 0:
                # Skip accessory subdirs under a parent folder that already has a movie file
                parent = d.parent
                if parent and has_nonzero_video.get(parent, False):
                    # Only consider the movie folder itself, not its children
                    pass
                else:
                    # Skip if any ancestor movie directory already contains a valid video
                    if not ancestor_has_video.get(d, False):
                        reason = "no_videos" if len(vids) == 0 else "zero_byte_videos_only"
                        lost_rows.append((d, reason, len(files), len(vids)))

        # flag low-quality videos (skip collection containers)
        if not is_collection_container:
            # Folder-level gating only suppresses tiny-only flags when a clear good/large signal exists.
            # Low-quality tokens should still be flagged even if a large video is present.
            folder_good = bool(_match_tokens(d.name, good_tokens))
            name_good = any(_match_tokens(p.name, good_tokens) for p in vids)
            has_large_video = any((p.stat().st_size >= tiny_bytes) for p in vids if p.exists())
            folder_lowq = bool(_match_tokens(d.name, lowq_tokens))
            name_lowq = any(_match_tokens(p.name, lowq_tokens) for p in vids)
            allow_scan = (not (folder_good or name_good or has_large_video)) or folder_lowq or name_lowq

            if allow_scan:
                for v in vids:
                    try:
                        size = v.stat().st_size
                    except FileNotFoundError:
                        continue

                    # Token scope: check BOTH folder name and filename
                    folder_name = v.parent.name
                    file_name = v.name
                    good = _match_tokens(folder_name, good_tokens) + _match_tokens(file_name, good_tokens)
                    lowq_tokens_folder = _match_tokens(folder_name, lowq_tokens)
                    lowq_tokens_file = _match_tokens(file_name, lowq_tokens)
                    lowq = list({*lowq_tokens_folder, *lowq_tokens_file})

                    reason_parts = []
                    if good:
                        pass
                    else:
                        if size < tiny_bytes:
                            reason_parts.append(f"tiny<{tiny_mib}MiB")
                        if lowq:
                            reason_parts.append("tokens")

                    if reason_parts:
                        lowq_rows.append(
                            VideoEntry(path=v, size_bytes=size, reason=";".join(reason_parts), tokens_matched=lowq)
                        )

    # Aggregate low-quality entries by movie folder (one folder = one movie)
    by_folder: Dict[Path, VideoEntry] = {}
    tokens_by_folder: Dict[Path, Set[str]] = {}
    count_by_folder: Dict[Path, int] = {}
    for entry in lowq_rows:
        folder = entry.path.parent
        count_by_folder[folder] = count_by_folder.get(folder, 0) + 1
        tokset = tokens_by_folder.setdefault(folder, set())
        tokset.update(entry.tokens_matched)
        current = by_folder.get(folder)
        if current is None or entry.size_bytes < current.size_bytes:
            by_folder[folder] = entry

    # Write CSVs (low quality) with title first, size_mib second
    lowq_csv = out_dir / "low_quality_movies.csv"
    with lowq_csv.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["title", "size_mib", "year", "folder_path", "rep_video_path", "size_bytes", "reason", "tokens", "flagged_count"])
        for folder, rep in sorted(by_folder.items(), key=lambda kv: str(kv[0]).lower()):
            title, year = _parse_title_year_from_path(rep.path)
            w.writerow([
                title,
                f"{rep.size_mib:.2f}",
                year if year is not None else "",
                str(folder),
                str(rep.path),
                rep.size_bytes,
                rep.reason,
                "|".join(sorted(tokens_by_folder.get(folder, set()))),
                count_by_folder.get(folder, 1),
            ])

    lost_csv = out_dir / "lost_movies.csv"
    with lost_csv.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["title", "size_mib", "year", "folder_path", "reason", "file_count", "video_count"])
        for folder, reason, file_count, video_count in lost_rows:
            title, year = _parse_title_year_from_path(folder / "dummy.ext")
            w.writerow([
                title,
                "0.00",
                year if year is not None else "",
                str(folder),
                reason,
                file_count,
                video_count,
            ])

    print(f"Wrote {lowq_csv}")
    print(f"Wrote {lost_csv}")
