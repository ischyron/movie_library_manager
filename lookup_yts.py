#!/usr/bin/env python3
# yts_lookup.py
import csv, json, sys, urllib.parse, urllib.request, time, re
from difflib import SequenceMatcher

API = "https://yts.mx/api/v2/list_movies.json"  # JSON API

def norm(s):
    s = s.lower()
    s = re.sub(r'[\[\]\(\)\._-]+', ' ', s)
    s = re.sub(r'\b(19|20)\d{2}\b', ' ', s)  # drop years
    s = re.sub(r'\b(uhd|remux|x26[45]|h\.?26[45]|hdrip|bdrip|brrip|webrip|web[- ]?dl|dvdrip|dvdscr|bluray|cam|ts|tc)\b', ' ', s)
    s = re.sub(r'\s{2,}', ' ', s).strip()
    return s

def best_match(q, movies):
    if not movies: return None, 0.0
    n = norm(q)
    best = max(movies, key=lambda m: SequenceMatcher(None, n, norm(m.get('title', ''))).ratio())
    score = SequenceMatcher(None, n, norm(best.get('title',''))).ratio()
    return best, score

def query_yts(title, year_hint=None):
    params = {'query_term': title}
    if year_hint:
        # YTS supports filtering by year; include when we can.
        params['year'] = str(year_hint)
    url = f"{API}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=15) as r:
        data = json.load(r)
    return data.get('data', {}).get('movies', [])

def infer_year(s):
    m = re.search(r'\b(19|20)\d{2}\b', s)
    return int(m.group(0)) if m else None

def pick_title(row):
    # Prefer explicit columns if present
    for k in ('title_guess','title','movie','name'):
        if k in row and row[k].strip(): return row[k].strip()
    # Else derive from path
    p = row.get('path','') or row.get('full_path','') or row.get('file','')
    return (p.rsplit('/',1)[-1] or p).rsplit('.',1)[0]

def main():
    if len(sys.argv) < 3:
        print("Usage: python3 yts_lookup.py input.csv output.csv", file=sys.stderr)
        sys.exit(2)

    inp, outp = sys.argv[1], sys.argv[2]
    rows_out = []
    with open(inp, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            title_in = pick_title(row)
            year_hint = infer_year(title_in) or infer_year(row.get('path','') or '')
            try:
                movies = query_yts(title_in, year_hint)
            except Exception as e:
                rows_out.append({'input_title': title_in, 'status': f'error:{e}'})
                continue

            best, score = best_match(title_in, movies)
            if not best or score < 0.55:
                rows_out.append({'input_title': title_in, 'status': 'no_match'})
                continue

            tor = best.get('torrents', []) or []
            # Flatten available formats
            formats = []
            for t in tor:
                q = t.get('quality')        # 720p / 1080p / 2160p / 3D
                ty = t.get('type')          # bluray / web, etc.
                sz = t.get('size')          # human-readable (e.g., "1.7 GB")
                sd = t.get('seeds')
                pr = t.get('peers')
                h  = t.get('hash')
                magnet = f"magnet:?xt=urn:btih:{h}" if h else ''
                formats.append(f"{q}|{ty}|{sz}|seeds:{sd}|peers:{pr}|{magnet}")
            rows_out.append({
                'input_title': title_in,
                'match_title': best.get('title_long') or best.get('title'),
                'year': best.get('year'),
                'imdb_code': best.get('imdb_code'),
                'yts_url': best.get('url'),
                'match_score': f"{score:.2f}",
                'available_formats': ' || '.join(formats) if formats else '',
                'status': 'ok'
            })
            time.sleep(0.2)  # be polite

    # Write output
    fieldnames = ['input_title','match_title','year','imdb_code','yts_url','match_score','available_formats','status']
    with open(outp, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows_out: w.writerow({k: r.get(k,'') for k in fieldnames})

if __name__ == "__main__":
    main()
