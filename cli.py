import argparse
import sys
from pathlib import Path

from scanner import scan_library
from yts import yts_lookup_from_csv


def find_repo_root(start: Path) -> Path:
    cur = start
    for _ in range(10):
        if (cur / ".git").exists():
            return cur
        if cur.parent == cur:
            break
        cur = cur.parent
    return start


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Scan movie library for low-quality/lost items and query YTS replacements.",
    )

    sub = p.add_subparsers(dest="cmd", required=True)

    # scan command
    sp = sub.add_parser("scan", help="Scan a library root and emit CSVs")
    sp.add_argument("--root", required=True, type=Path, help="Root directory of movie library")
    sp.add_argument("--out-dir", type=Path, default=None, help="Directory for CSV outputs (defaults to repo data/)")
    sp.add_argument("--tiny-mib", type=int, default=700, help="Max MiB for tiny files to flag")
    sp.add_argument(
        "--good-tokens",
        default="720p,1024p,1080p,1440p,2160p,4K,UHD,REMUX",
        help="Comma-separated tokens that skip low-quality flag",
    )
    sp.add_argument(
        "--lowq-tokens",
        default="DivX,XviD,CAM,TS,TC,DVDScr,DVDRip,R5,360p,480p,HDCAM,SDTV,PDTV",
        help="Comma-separated tokens that indicate low quality",
    )
    sp.add_argument(
        "--video-exts",
        default="mkv,mp4,avi,m4v,mov,wmv,mpg,mpeg,ts,m2ts,vob,iso",
        help="Comma-separated video extensions",
    )
    sp.add_argument(
        "--subtitle-exts",
        default="srt,sub,idx,ass,ssa,vtt",
        help="Comma-separated subtitle extensions",
    )
    sp.add_argument(
        "--ignore-dirs",
        default="",
        help="Optional comma-separated dir names to ignore (overrides built-in defaults)",
    )

    # yts command
    yp = sub.add_parser("yts", help="Query YTS for items listed in a CSV")
    yp.add_argument("--from-csv", required=True, type=Path, help="Input CSV from scan phase (will be updated in place)")
    yp.add_argument("--lost", action="store_true", help="Treat input as lost_movies.csv format")
    yp.add_argument("--concurrency", type=int, default=6, help="Parallel requests to YTS")
    yp.add_argument("--sequential", action="store_true", help="Process one movie at a time (sets concurrency=1)")
    yp.add_argument("--timeout", type=float, default=12.0, help="HTTP timeout seconds")
    yp.add_argument("--retries", type=int, default=3, help="Retries per YTS query on failure/slow")
    yp.add_argument("--slow-after", type=float, default=9.0, help="Warn/retry if a request exceeds this many seconds")
    yp.add_argument("--verbose", action="store_true", help="Verbose logging for YTS lookups")

    return p


def main(argv=None) -> int:
    argv = argv or sys.argv[1:]
    args = build_parser().parse_args(argv)

    if args.cmd == "scan":
        out_dir = args.out_dir
        if out_dir is None:
            repo = find_repo_root(Path.cwd())
            out_dir = repo / "data"
        scan_library(
            root=args.root,
            out_dir=out_dir,
            tiny_mib=args.tiny_mib,
            good_tokens=[t.strip() for t in args.good_tokens.split(",") if t.strip()],
            lowq_tokens=[t.strip() for t in args.lowq_tokens.split(",") if t.strip()],
            video_exts=[e.strip().lower() for e in args.video_exts.split(",") if e.strip()],
            subtitle_exts=[e.strip().lower() for e in args.subtitle_exts.split(",") if e.strip()],
            ignore_dirs=[d.strip().lower() for d in args.ignore_dirs.split(",") if d.strip()] or None,
        )
        return 0

    if args.cmd == "yts":
        yts_lookup_from_csv(
            input_csv=args.from_csv,
            output_csv=None,
            is_lost=args.lost,
            in_place=True,
            concurrency=(1 if args.sequential else args.concurrency),
            timeout=args.timeout,
            retries=args.retries,
            slow_after=args.slow_after,
            verbose=args.verbose,
        )
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
