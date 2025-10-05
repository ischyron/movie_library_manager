#!/usr/bin/env python3
# find_media_issues.py
import os, re, sys, csv, argparse

VIDEO_EXT = {'.mkv','.mp4','.avi','.m4v','.mov','.wmv','.mpg','.mpeg','.ts','.m2ts','.vob','.iso'}
SUB_EXT   = {'.srt','.sub','.idx','.ass','.ssa','.vtt'}
JUNK_DIR_NAMES = {
    'subs','sub','subtitles','subtitle','samples','sample','extras','featurettes','trailers',
    'art','artwork','posters','covers','metadata','.appledouble','.ds_store','@eadir',
    'recycle.bin','lost+found','plex versions','plex versions (optimized)'
}

LOW_QUALITY_RX = re.compile(r'''(?ix)\b(
    DivX|XviD|VCD|SVCD|VHSRip|TVRip|PDTV|DVDSCR|R5|CAM|CAMRIP|TS|TELESYNC|TC|TELECINE|
    C[ _-]?DRIP|CD[ _-]?RIP|CD1|CD2|1CD|2CD|H\.?263|FLV|3GP|320p|360p|400p|480p
)\b''')
GOOD_ENOUGH_RX = re.compile(r'(?i)\b(720p|1024p|1080p|1440p|2160p|4K|UHD|REMUX)\b')

STRIP_TOKENS_RX = re.compile(r'''(?ix)
    [\[\(].*?[\]\)]| \b(19|20)\d{2}\b |
    \b(480|576|720|1024|1080|1440|2160)p\b |
    \b(x264|x265|H\.?26[45]|AVC|HEVC|DivX|XviD)\b |
    \b(Blu-?ray|BRRip|BDRip|WEB[- ]?DL|WEB[- ]?Rip|HDRip|DVDRip|DVDScr)\b |
    \b(DDP?\d\.\d|DTS(-?HD)?|TrueHD|Atmos|AAC|AC-3|EAC3|MP3)\b |
    \b(CD1|CD2|1CD|2CD|REMUX|UHD|CAM|TS|TC|PROPER|REPACK|READNFO|LIMITED|EXTENDED|UNCUT)\b |
    \b\w{2,}-RG\b
''')
SEPARATORS_RX = re.compile(r'[._]+')
SPACES_RX = re.compile(r'\s{2,}')

def looks_video(path:str)->bool:
    return os.path.splitext(path)[1].lower() in VIDEO_EXT

def looks_sub(path:str)->bool:
    return os.path.splitext(path)[1].lower() in SUB_EXT

def guess_title(path:str)->str:
    parent = os.path.basename(os.path.dirname(path))
    stem = os.path.splitext(os.path.basename(path))[0]
    candidate = parent if parent.lower() not in {'movies','movie','video','videos'} else stem
    s = SEPARATORS_RX.sub(' ', candidate)
    s = STRIP_TOKENS_RX.sub(' ', s)
    s = SPACES_RX.sub(' ', s).strip(' -_.').strip()
    return ' '.join([w if (w.isupper() and len(w)<=4) else w.title() for w in s.split()])

def is_junk_dir(name:str)->bool:
    n = name.lower().strip()
    return n in JUNK_DIR_NAMES or n.startswith('.')

def should_flag_low_quality(filename:str, size_bytes:int, min_mb:int):
    if GOOD_ENOUGH_RX.search(filename): return False, []
    flags=[]
    if LOW_QUALITY_RX.search(filename): flags.append('name:low_quality_token')
    if size_bytes/1048576.0 <= min_mb: flags.append(f'size<=${min_mb}MB')
    return (len(flags)>0), flags

def scan(root:str, min_mb:int, out_lowq:str, out_missing:str):
    lowq_rows=[]
    missing_rows=[]
    for dirpath, subdirs, files in os.walk(root):
        base = os.path.basename(dirpath)
        # skip obvious junk directories entirely
        if is_junk_dir(base): 
            subdirs[:] = []  # do not descend further
            continue

        # --- Low-quality scan (file-level) ---
        for fn in files:
            full = os.path.join(dirpath, fn)
            if not looks_video(full): 
                continue
            try: size = os.path.getsize(full)
            except OSError: continue
            flag, flags = should_flag_low_quality(fn, size, min_mb)
            if not flag: 
                continue
            if GOOD_ENOUGH_RX.search(base): 
                continue
            lowq_rows.append({
                'title_guess': guess_title(full),
                'size_mb': round(size/1048576.0,1),
                'markers': ';'.join(flags),
                'path': full
            })

        # --- Missing/empty movie folder scan (directory-level) ---
        # Only evaluate **leaf** directories to avoid flagging collection roots.
        if subdirs: 
            continue
        # a leaf folder is candidate if its name looks like a movie-ish label and not junk
        if is_junk_dir(base): 
            continue
        # Count media types inside this leaf
        video_files=[]; zero_byte_videos=0; subs=0; nonvideo=0
        for fn in files:
            full = os.path.join(dirpath, fn)
            if looks_video(full):
                try: sz=os.path.getsize(full)
                except OSError: sz=0
                video_files.append((fn,sz))
                if sz==0: zero_byte_videos+=1
            elif looks_sub(full):
                subs+=1
            else:
                nonvideo+=1
        if len(video_files)==0 or (len(video_files)>0 and all(sz==0 for _,sz in video_files)):
            reason = 'no_video_files' if len(video_files)==0 else 'only_zero_byte_videos'
            # avoid flagging folders that are clearly subtitle/art stubs by name
            name_bad = re.search(r'(?i)\b(sub|subtitle|sample|extras?|featurettes?|trailers?)\b', base)
            if name_bad: 
                pass  # skip
            else:
                missing_rows.append({
                    'folder': dirpath,
                    'reason': reason,
                    'video_files': len(video_files),
                    'zero_byte_videos': zero_byte_videos,
                    'subtitle_files': subs,
                    'other_files': nonvideo
                })

    # sort and write
    lowq_rows.sort(key=lambda r: (r['title_guess'].lower(), r['size_mb']))
    with open(out_lowq,'w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f, fieldnames=['title_guess','size_mb','markers','path'])
        w.writeheader(); w.writerows(lowq_rows)

    missing_rows.sort(key=lambda r: r['folder'].lower())
    with open(out_missing,'w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f, fieldnames=['folder','reason','video_files','zero_byte_videos','subtitle_files','other_files'])
        w.writeheader(); w.writerows(missing_rows)

    print(f"Wrote {len(lowq_rows)} low-quality rows -> {out_lowq}")
    print(f"Wrote {len(missing_rows)} missing/empty folders -> {out_missing}")

def main():
    ap = argparse.ArgumentParser(description="Find low-quality videos and empty/invalid movie folders.")
    ap.add_argument('root', help='Root media folder')
    ap.add_argument('--min-mb', type=int, default=900, help='Low-quality size threshold (MB)')
    ap.add_argument('--out-lowq', default='low_quality_movies.csv', help='Output CSV: low-quality files')
    ap.add_argument('--out-missing', default='missing_movie_folders.csv', help='Output CSV: missing/empty folders')
    args = ap.parse_args()
    scan(args.root, args.min_mb, args.out_lowq, args.out_missing)

if __name__ == '__main__':
    main()
