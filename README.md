Movie Library Manager — Movie Library Scanner

Overview
- Scans a movie library to find likely low-quality encodes and "lost" leaf folders that contain no valid videos (or only 0-byte videos).
- Optionally queries the YTS API for available replacement formats for flagged or missing titles.

Artifacts
- low_quality_movies.csv — suspect low-quality video files.
- lost_movies.csv — leaf folders with no valid videos or only 0-byte videos.
- yts_lowq.csv — YTS formats discovered for low_quality_movies.csv rows.
- yts_missing.csv — YTS formats discovered for lost_movies.csv rows.

Heuristics (defaults; configurable via flags)
- Video extensions: mkv, mp4, avi, m4v, mov, wmv, mpg, mpeg, ts, m2ts, vob, iso
- Subtitle extensions: srt, sub, idx, ass, ssa, vtt
- Junk dirs ignored (case-insensitive): subs, subtitles, sample, samples, extras, featurettes, trailers, art, artwork, posters, covers, metadata, .AppleDouble, .DS_Store, @eaDir, recycle.bin, lost+found, plex versions
- Good-enough tokens (skip low-quality flag if present): 720p, 1024p, 1080p, 1440p, 2160p, 4K, UHD, REMUX
- Low-quality tokens (flag if present and no good-enough token): DivX, XviD, CAM, TS, TC, DVDScr, DVDRip, R5, 360p, 480p, HDCAM, SDTV, PDTV
- Tiny file threshold: 700 MiB (files smaller than this may be flagged unless good-enough token is present)

CLI
- Scan:
  - python -m cli scan --root "/Volumes/Extreme SSD/Movies"  (outputs to `data/` by default)
- YTS lookup for flagged/missing:
  - python -m cli yts --from-csv data/low_quality_movies.csv --out data/yts_lowq.csv
  - python -m cli yts --from-csv data/lost_movies.csv --lost --out data/yts_missing.csv

Notes
- No downloading or piracy; this tool only analyzes local metadata and queries YTS for available release qualities.
- Parsing of titles/years uses simple patterns from folder/file names (e.g., "Movie Name (2012)"), and falls back to a fuzzy search via YTS query_term.


Installed entry point
- After installing via pip, the command `movie-library-manager` runs the same CLI.

Artifacts Directory
- All CSV artifacts are written to `data/` in the repo root and are git-managed.

Agents Guide
- Detailed heuristics and contracts live in `AGENTS.md` to avoid duplication with README.
