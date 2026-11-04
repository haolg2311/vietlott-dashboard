#!/usr/bin/env python3
"""Lấy jackpot và số giải từng hạng từ các trang kết quả công khai, ghi vào data/.

Chạy bằng GitHub Actions nên không tốn token Claude. Chỉ thêm kỳ mới hoặc bổ sung kỳ còn thiếu số liệu.
"""
import html
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
AGENT = "Mozilla/5.0 (compatible; vietlott-dashboard/1.0)"
SOURCES = {
    "mega": "https://xosodaiphat.com/xs-mega-xo-so-mega-645.html",
    "power": "https://xosodaiphat.com/xs-power-xo-so-power-655.html",
    "lotto": ["https://xskt.com.vn/xslotto-5-35", "https://www.minhchinh.com/xo-so-dien-toan-lotto-535.html"],
}


def text_of(url):
    req = urllib.request.Request(url, headers={"User-Agent": AGENT})
    with urllib.request.urlopen(req, timeout=40) as res:
        raw = res.read().decode("utf-8", "ignore")
    raw = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", raw, flags=re.S | re.I)
    raw = re.sub(r"<[^>]+>", " ", raw)
    return re.sub(r"\s+", " ", html.unescape(raw))


def num(s):
    return int(re.sub(r"[.,]", "", s))


def parse_mega(t):
    out = {}
    pat = (r"Kỳ (\d+): [^0-9]*(\d\d-\d\d-\d{4}) ((?:\d\d ){6})Các con số.*?Jackpot (\d+) ([\d.]+) "
           r"Giải 1 ([\d.]+) [\d.]+ Giải 2 ([\d.]+) [\d.]+ Giải 3 ([\d.]+) [\d.]+")
    for m in re.finditer(pat, t):
        i = int(m[1])
        d = m[2].split("-")
        out[i] = {"id": i, "date": f"{d[2]}-{d[1]}-{d[0]}", "numbers": [int(x) for x in m[3].split()],
                  "jackpot": num(m[5]), "jackpot_winners": int(m[4]), "g1": num(m[6]), "g2": num(m[7]), "g3": num(m[8])}
    return out


def parse_power(t):
    out = {}
    pat = (r"Kỳ (\d+): [^0-9]*(\d\d-\d\d-\d{4}) ((?:\d\d ){7})(?:[^0-9]*?)Jackpot 1 (?:[^0-9]*?)(\d+) ([\d.]+) "
           r"Jackpot 2 (?:[^0-9]*?)(\d+) ([\d.]+) Giải 1 (?:[^0-9]*?)([\d.]+) [\d.]+ Giải 2 (?:[^0-9]*?)([\d.]+) [\d.]+ "
           r"Giải 3 (?:[^0-9]*?)([\d.]+) [\d.]+")
    for m in re.finditer(pat, t):
        i = int(m[1])
        d = m[2].split("-")
        out[i] = {"id": i, "date": f"{d[2]}-{d[1]}-{d[0]}", "numbers": [int(x) for x in m[3].split()],
                  "jackpot": num(m[5]), "jackpot_winners": int(m[4]), "jackpot2": num(m[7]), "jackpot2_winners": int(m[6]),
                  "g1": num(m[8]), "g2": num(m[9]), "g3": num(m[10])}
    return out


def lotto_row(i, numbers, cells):
    w = [num(c[0]) for c in cells]
    v = [num(c[1]) for c in cells]
    row = {"id": i, "numbers": numbers, "jackpot": v[0], "jackpot_winners": w[0],
           "winners": dict(zip(("g1", "g2", "g3", "g4", "g5", "kk"), w[1:])),
           "values": dict(zip(("g1", "g2", "g3", "g4", "g5"), v[1:6]))}
    return row


def parse_xskt(t):
    out = {}
    pat = (r"#0*(\d+) \((?:13|21)h\) Kết quả ((?:\d\d ){6})Thống kê trúng giải Giải Trùng khớp Số người trúng Trị giá giải \(VNĐ\) "
           r"J\.pot ([\d,]+) ([\d,]+) G\.1 ([\d,]+) ([\d,]+) G\.2 ([\d,]+) ([\d,]+) G\.3 ([\d,]+) ([\d,]+) "
           r"G\.4 ([\d,]+) ([\d,]+) G\.5 ([\d,]+) ([\d,]+) KK ([\d,]+) ([\d,]+)")
    for m in re.finditer(pat, t):
        g = m.groups()
        cells = [(g[k], g[k + 1]) for k in range(2, 16, 2)]
        out[int(g[0])] = lotto_row(int(g[0]), [int(x) for x in g[1].split()], cells)
    return out


def parse_minhchinh(t):
    out = {}
    pat = (r"kỳ #(\d+) ngày \d\d/\d\d/\d{4} - Lúc \d\d:\d\d ((?:\d\d ){6}).{0,120}?Độc đắc ([\d,]+) ([\d,]+) "
           r"Giải nhất ([\d,]+) ([\d,]+) Giải nhì ([\d,]+) ([\d,]+) Giải ba ([\d,]+) ([\d,]+) "
           r"Giải tư ([\d,]+) ([\d,]+) Giải năm ([\d,]+) ([\d,]+) Giải kk ([\d,]+) ([\d,]+)")
    for m in re.finditer(pat, t):
        g = m.groups()
        cells = [(g[k], g[k + 1]) for k in range(2, 16, 2)]
        out[int(g[0])] = lotto_row(int(g[0]), [int(x) for x in g[1].split()], cells)
    return out


def merge(rows, found, floor):
    """Thêm kỳ mới, và thay kỳ đang thiếu số giải bằng bản đầy đủ. Không đụng kỳ đã đủ số liệu."""
    by_id = {r["id"]: r for r in rows}
    added = []
    for i, r in sorted(found.items()):
        old = by_id.get(i)
        partial = old is not None and not (old.get("g3") or old.get("winners"))
        if (old is None and i > floor) or partial:
            by_id[i] = r
            added.append(i)
    return [by_id[i] for i in sorted(by_id)], added


def lotto_date(i):
    return (date(2025, 6, 29) + timedelta(days=(i - 1) // 2)).isoformat()


def main():
    report = {}
    jackpots = json.loads((DATA / "jackpots.json").read_text())
    for game, parser in (("mega", parse_mega), ("power", parse_power)):
        try:
            found = parser(text_of(SOURCES[game]))
            floor = jackpots[game][-1]["id"]
            jackpots[game], added = merge(jackpots[game], found, floor)
            report[game] = {"read": len(found), "added": added}
        except Exception as e:  # nguồn lỗi thì giữ nguyên dữ liệu, trang tự hiện cảnh báo
            report[game] = {"error": str(e)[:120]}
        time.sleep(2)
    (DATA / "jackpots.json").write_text(json.dumps(jackpots, ensure_ascii=False, indent=1) + "\n")

    store = json.loads((DATA / "lotto.json").read_text())
    found = {}
    errors = []
    for url, parser in zip(SOURCES["lotto"], (parse_xskt, parse_minhchinh)):
        try:
            for i, r in parser(text_of(url)).items():
                found.setdefault(i, r)
        except Exception as e:
            errors.append(str(e)[:120])
        time.sleep(2)
    floor = store["rows"][-1]["id"]
    for i, r in found.items():
        r["date"] = lotto_date(i)
    store["rows"], added = merge(store["rows"], found, floor)
    (DATA / "lotto.json").write_text(json.dumps(store, ensure_ascii=False, indent=0) + "\n")
    report["lotto"] = {"read": len(found), "added": added, "errors": errors}
    print(json.dumps(report, ensure_ascii=False))
    if not any(report[g].get("read") for g in report):
        sys.exit("Không đọc được nguồn nào")


if __name__ == "__main__":
    main()
