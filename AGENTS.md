# Agents Guide — Contracts and Defaults

Purpose
- Analyze an existing, privately-owned movie library to surface low-quality encodes and lost/empty folders; then cross-check YTS for better formats. No downloading.

Artifacts (git-managed)
- All artifacts live in `data/` at the repo root.
- Files: `low_quality_movies.csv`, `lost_movies.csv`, `yts_lowq.csv`, `yts_missing.csv`.

Heuristics (scan)
- Video extensions: mkv, mp4, avi, m4v, mov, wmv, mpg, mpeg, ts, m2ts, vob, iso
- Subtitle extensions: srt, sub, idx, ass, ssa, vtt
- Ignore dirs (case-insensitive): subs, subtitles, sample, samples, extras, featurettes, trailers, art, artwork, posters, covers, metadata, .AppleDouble, .DS_Store, @eaDir, recycle.bin, lost+found, plex versions, .actors, other
- Good-enough tokens: 720p, 1024p, 1080p, 1440p, 2160p, 4K, UHD, REMUX
- Low-quality tokens: DivX, XviD, CAM, TS, TC, DVDScr, DVDRip, R5, 360p, 480p, HDCAM, SDTV, PDTV
- Tiny threshold: 700 MiB (flag when < threshold and no good-enough token)

CLI Contracts
- Scan: `python -m cli scan --root <LIB_ROOT>` writes `data/low_quality_movies.csv` and `data/lost_movies.csv` by default.
- YTS lookup: `python -m cli yts --from-csv <csv> [--lost] [--verbose] [--retries N]` writes to `data/yts_lowq.csv` or `data/yts_missing.csv` by default.
- YTS adds `magnets` column. Verbose mode logs requests, latency, retries; slow or failed requests are retried with backoff.

Maintainability
- README describes high-level usage; this file holds authoritative defaults/heuristics to avoid duplication.
