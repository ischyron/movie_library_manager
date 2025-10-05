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
  - python -m cli scan --root "/Volumes/Extreme SSD/Movies"
  - Options: --out-dir, --tiny-mib, --good-tokens, --lowq-tokens, --video-exts, --ignore-dirs
- YTS lookup for flagged items:
  - python -m cli yts --from-csv low_quality_movies.csv --out yts_lowq.csv
  - python -m cli yts --from-csv lost_movies.csv --lost --out yts_missing.csv

Notes
- No downloading or piracy; this tool only analyzes local metadata and queries YTS for available release qualities.
- Parsing of titles/years uses simple patterns from folder/file names (e.g., "Movie Name (2012)"), and falls back to a fuzzy search via YTS query_term.


Installed entry point
- After installing via pip, the command `movie-library-manager` runs the same CLI.
