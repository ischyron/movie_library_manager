# Movie Library Manager

## Overview
- Scan a movie library for likely low‑quality encodes and “lost” folders (no valid videos or only 0‑byte videos).
- Optionally check the YTS API for available replacement formats (no downloading).

## Quick Start
- Setup (script): `source scripts/setup.sh`  (keeps venv active)
- Setup (manual): `python3 -m venv .venv && source .venv/bin/activate && pip install -e .`
- Scan: `python -m cli scan --root "/path/to/Movies"`
- YTS: `python -m cli yts --from-csv data/low_quality_movies.csv --verbose`
- Short command: `ml yts --from-csv data/low_quality_movies.csv --verbose`

## CLI
- Scan: `python -m cli scan --root "/Volumes/Movies"` (writes CSVs to `data/` by default)
- YTS (low‑quality): `python -m cli yts --from-csv data/low_quality_movies.csv --verbose`
- In‑place update: `ml yts --from-csv data/low_quality_movies.csv --verbose` (appends YTS columns to the same CSV)
- YTS (missing): `python -m cli yts --from-csv data/lost_movies.csv --lost --verbose`
- Entry point: `movie-library-manager` provides the same commands.
- Short alias: `ml` mirrors the same subcommands, e.g. `ml yts --from-csv data/low_quality_movies.csv --verbose`

## Artifacts
- `data/low_quality_movies.csv` — suspect low‑quality videos.
- `data/lost_movies.csv` — leaf folders with no valid videos or only 0‑byte videos.
- `data/yts_lowq.csv` and `data/yts_missing.csv` — YTS lookup results.

## Heuristics (condensed)
- Flags tiny files (< 700 MiB) unless a “good” token is present; flags explicit low‑quality tokens.
- Good tokens: 720p, 1024p, 1080p, 1440p, 2160p, 4K, UHD, REMUX.
- Low‑quality tokens: DivX, XviD, CAM, TS, TC, DVDScr, DVDRip, R5, 360p, 480p, HDCAM, SDTV, PDTV.
- Ignores common junk subfolders (e.g., subs, samples, extras, artwork). Uses common video containers and subtitle files.
- For authoritative, full lists and defaults, see `AGENTS.md`.

## Kodi on macOS
- Install Kodi 21 “Omega” for your Mac (ARM64 for Apple Silicon, x86_64 for Intel). If unstable, try latest 21.x or Kodi 20.2/20.3.
- On first launch, allow external‑disk and network permissions.

## Mac → USB → TV Workflow
- Organize: one‑movie‑per‑folder named `Title (Year)`; keep extras in ignored subfolders.
- In Kodi (Mac): Videos → Files → Add → set content “Movies” with “separate folders” and “use folder names”.
- Export: Settings → Media → Library → Export → “Separate files per item” (writes `.nfo`, `poster.jpg`, `fanart.jpg`).
- USB: format as exFAT; copy the organized folders with exported metadata.
- On TV Kodi: Add source from USB → set content Movies → scraper “Local information only” → Update library.

## Notes
- No downloading; only local analysis and YTS metadata queries.
- Title/year parsing prefers `Title (YYYY)`; otherwise falls back to fuzzy search.

## Agents Guide
- Contracts, defaults, and full heuristics live in `AGENTS.md`.
