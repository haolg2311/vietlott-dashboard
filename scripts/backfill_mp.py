#!/usr/bin/env python3
"""Lấy lịch sử Mega 6/45 hoặc Power 6/55 (jackpot, số người trúng từng giải) từ trang theo ngày của XSKT, chậm rãi."""
import json, re, sys, time
from datetime import date
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import fetch_results as f

game = sys.argv[1]
base, file, size = {"mega": ("xsmega645", "power645.jsonl", 6), "power": ("xspower", "power655.jsonl", 7)}[game]
OUT = f.DATA / f"{game}_history.json"
cell = r"([\d,]+) ([\d,]+)"
if game == "mega":
    pat = re.compile(r"#0*(\d+) Kết quả ((?:\d\d ){6})Thống kê trúng giải Giải Trùng khớp Số người trúng Trị giá giải \(VNĐ\) "
                     rf"J\.pot {cell} G\.1 {cell} G\.2 {cell} G\.3 {cell}")
else:
    pat = re.compile(r"#0*(\d+) Kết quả ((?:\d\d ){6})Số JP2 (\d\d) Thống kê trúng giải Giải Trùng khớp Số người trúng Trị giá giải \(VNĐ\) "
                     rf"J\.pot {cell} Jpot2 {cell} G\.1 {cell} G\.2 {cell} G\.3 {cell}")
dates = {}
for line in (f.DATA / "raw" / file).read_text().splitlines():
    r = json.loads(line)
    dates[int(r["id"])] = r["date"]


def parse(t):
    out = {}
    for m in pat.finditer(t):
        g = list(m.groups())
        i = int(g.pop(0))
        nums = [int(x) for x in g.pop(0).split()]
        if game == "power":
            nums.append(int(g.pop(0)))
        v = [f.num(x) for x in g]
        row = {"id": i, "date": dates.get(i), "numbers": nums, "jackpot": v[1], "jackpot_winners": v[0]}
        if game == "power":
            row.update(jackpot2=v[3], jackpot2_winners=v[2])
            v = v[4:]
        else:
            v = v[2:]
        row.update(g1=v[0], g2=v[2], g3=v[4])
        out[i] = row
    return out


rows = {int(k): v for k, v in json.loads(OUT.read_text()).items()} if OUT.exists() else {}
miss = []
try:
    rows.update(parse(f.text_of(f"https://xskt.com.vn/{base}/200-ngay")))
except Exception as e:
    miss.append(f"200-ngay {e}")
lo, hi = int(sys.argv[2]), int(sys.argv[3])
for i in range(lo, hi + 1):
    if i in rows or i not in dates:
        continue
    d = date.fromisoformat(dates[i])
    try:
        found = parse(f.text_of(f"https://xskt.com.vn/{base}/ngay-{d.day}-{d.month}-{d.year}"))
        rows.update(found)
        if i not in found:
            miss.append(i)
    except Exception as e:
        miss.append(f"{i} {str(e)[:50]}")
    time.sleep(4)
keys = sorted(rows)
f.fix_split([rows[k] for k in keys])
OUT.write_text(json.dumps({str(k): rows[k] for k in keys}, ensure_ascii=False) + "\n")
print(game, len(rows), "kỳ; thiếu", len(miss), miss[:40])
