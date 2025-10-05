# Media Hygiene Agents — Context, Contracts, and CLI Plan
Movie libary refrence data for which I hold originals. This not for piracy or to download.
I want to investigate commonalities in  magnet links.

## Problem
Old, recovered, or inconsistent movie libraries often contain:
- Low-quality encodes (CD-era, CAM/TS, tiny files).
- Empty or “lost” movie folders with only subs/artifacts or 0-byte videos.

Goal: deterministically find bad items, then check what *good* replacements exist on YTS.

## Scope
Root example: `/Volumes/Extreme SSD/Movies`

Artifacts:
- `low_quality_movies.csv` — suspect low-quality files.
- `lost_movies.csv` — leaf folders with no valid videos or only 0-byte videos.
- `yts_lowq.csv` — YTS formats for `low_quality_movies.csv`.
- `yts_missing.csv` — YTS formats for `lost_movies.csv`.

## Heuristics
**Video extensions**: mkv, mp4, avi, m4v, mov, wmv, mpg, mpeg, ts, m2ts, vob, iso  
**Subtitle extensions**: srt, sub, idx, ass, ssa, vtt  
**Junk dirs ignored**: subs, subtitles, sample(s), extras, featurettes, trailers, art, artwork, posters, covers, metadata, `.AppleDouble`, `.DS_Store`, `@eaDir`, recycle.bin, lost+found, “plex versions”.

**Good-enough tokens** (skip): `720p|1024p|1080p|1440p|2160p|4K|UHD|REMUX`  
**Low-quality tokens** (flag): `DivX|Xvi
