#!/usr/bin/env python3
"""Lấy lịch sử Lotto 5/35 (số người trúng từng giải) từ trang kết quả theo ngày của XSKT, chậm rãi, ghi data/lotto_history.json."""
import json, sys, time
from datetime import date, timedelta
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import fetch_results as f

OUT = f.DATA / "lotto_history.json"
start, end = date.fromisoformat(sys.argv[1]), date.fromisoformat(sys.argv[2])
rows = {int(k): v for k, v in json.loads(OUT.read_text()).items()} if OUT.exists() else {}
miss = []
try:
    for i, r in f.parse_xskt(f.text_of("https://xskt.com.vn/xslotto-5-35/200-ngay")).items():
        rows[i] = dict(r, date=f.lotto_date(i))
except Exception as e:
    miss.append(f"200-ngay {e}")
d = start
while d <= end:
    url = f"https://xskt.com.vn/xslotto-5-35/ngay-{d.day}-{d.month}-{d.year}"
    try:
        found = f.parse_xskt(f.text_of(url))
        for i, r in found.items():
            rows[i] = dict(r, date=f.lotto_date(i))
        if len(found) < 2:
            miss.append(f"{d} {len(found)}")
    except Exception as e:
        miss.append(f"{d} {str(e)[:60]}")
    time.sleep(4)
    d += timedelta(days=1)
OUT.write_text(json.dumps({str(k): rows[k] for k in sorted(rows)}, ensure_ascii=False) + "\n")
print(len(rows), "kỳ; thiếu:", miss)
