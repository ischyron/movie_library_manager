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
- Low‑quality tokens: DivX, XviD, aXXo, CAM, TS, TC, DVDScr, DVDRip, R5, 360p, 480p, HDCAM, SDTV, PDTV.
- Ignores common accessory/system subfolders by default (case‑insensitive):
  subs, subtitles, extras, featurettes, trailers, art, artwork, posters, covers, metadata,
  plex versions, .actors, other, sample, samples, .AppleDouble, .DS_Store, @eaDir, recycle.bin, lost+found.
  This prevents folders like `Some Movie (2021)/Subs` from being flagged as lost.
  Note: providing `--ignore-dirs` replaces (does not merge with) the built‑in list.
- For authoritative, full lists and defaults, see `AGENTS.md`.

## Token Matching Rules
- Scope: token detection checks the MOVIE FOLDER NAME first, and also the filename. Case‑insensitive substring matches. If either contains a low‑quality token, the video is considered low‑quality (subject to good‑token suppression below). Example: `Some.Movie.2004.DVDRip.XviD/YourFile.mkv` or `Clean.Title/YourFile.DVDRip.XviD.mkv` will match.
- Either‑or rule: a file is flagged low‑quality if it is tiny OR it contains a low‑quality token. You do not need both.
- Good‑token suppression: if a filename contains any “good” token (e.g., `1080p`, `2160p`, `REMUX`), size‑based flagging is suppressed. By default we also suppress token‑based flags in this case. If you want token‑based flags to win even when a good token is present, I can add a `--strict-lowq` switch.
- Configurability: all token lists are overrideable via CLI flags `--good-tokens` and `--lowq-tokens`.

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
