python3 filter_movies.py "/Volumes/Extreme SSD/Movies" --min-mb 900 \
  --out-lowq low_quality_movies.csv \
  --out-missing lost_movies.csv

python3 lookup_yts.py low_quality_movies.csv yts_lowq.csv
python3 lookup_yts.py lost_movies.csv yts_missing.csv
