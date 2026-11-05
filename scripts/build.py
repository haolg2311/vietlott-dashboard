#!/usr/bin/env python3
"""Tạo data/dashboard.json từ kết quả kỳ quay, jackpot và sổ danh mục giả lập.

Chạy: python3 scripts/build.py [--no-fetch]
Không tạo số "dự đoán": mọi kỳ quay được coi là độc lập, trang chỉ chấm giá trị vé.
"""
import argparse
import hashlib
import json
import math
import random
import subprocess
from datetime import date, datetime, timedelta, timezone
from math import comb
from pathlib import Path
from statistics import mean

from scipy.stats import chi2, norm

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RAW_BASE = "https://raw.githubusercontent.com/vietvudanh/vietlott-data/main/data/"
VN = timezone(timedelta(hours=7))

TICKET = 10_000
WEEK_TICKETS = 10
TAX_FREE = 20_000_000  # Luật Thuế TNCN 109/2025/QH15, hiệu lực 01/07/2026
TAX_RATE = 0.10
PLAY_PCT, LIGHT_PCT = 55, 45
PLAY_TICKETS, LIGHT_TICKETS = 5, 2
HOT_WINDOW = 30
EV_HISTORY = 30
FULL_SIMS = 40
FORWARD_START = "2026-11-02"
WEEKDAYS = ["Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7", "Chủ nhật"]

GAMES = {
    "mega": {"name": "Mega 6/45", "pool": 45, "file": "power645.jsonl", "days": (2, 4, 6), "seed_jp": 12e9},
    "power": {"name": "Power 6/55", "pool": 55, "file": "power655.jsonl", "days": (1, 3, 5), "seed_jp": 30e9},
}


LOTTO = {"name": "Lotto 5/35", "file": "power535.jsonl", "seed_jp": 6e9, "trigger": 12e9, "near_draws": 6}
LOTTO_BASE = {"g1": 10_000_000, "g2": 5_000_000, "g3": 500_000, "g4": 100_000, "g5": 30_000, "kk": 10_000}
LOTTO_TOTAL = comb(35, 5) * 12
LOTTO_ODDS = {
    "jp": 1 / LOTTO_TOTAL, "g1": 11 / LOTTO_TOTAL, "g2": 150 / LOTTO_TOTAL, "g3": 1650 / LOTTO_TOTAL,
    "g4": 4350 / LOTTO_TOTAL, "g5": 47850 / LOTTO_TOTAL,
    "kk": (comb(35, 5) - 1 - 150 - 4350) / LOTTO_TOTAL,
}
LOTTO_SHARE = {"g1": 1 / 3, "g2": 1 / 6, "g3": 1 / 6, "g4": 1 / 6, "g5": 1 / 6}


def net(prize):
    return prize - max(0, prize - TAX_FREE) * TAX_RATE


def odds(game):
    """Xác suất chính xác của từng hạng giải trên một bộ số."""
    n = GAMES[game]["pool"]
    total = comb(n, 6)
    rest = n - 6
    p = {
        "g3": comb(6, 3) * comb(rest, 3) / total,
        "g2": comb(6, 4) * comb(rest, 2) / total,
        "jp": 1 / total,
    }
    if game == "mega":
        p["g1"] = comb(6, 5) * rest / total
    else:
        p["j2"] = 6 / total
        p["g1"] = 288 / total
    return p


FIXED = {
    "mega": {"g1": 10_000_000, "g2": 300_000, "g3": 30_000},
    "power": {"g1": 40_000_000, "g2": 500_000, "g3": 50_000},
}


def share_factor(tickets, prob):
    """Tỷ lệ giữ lại khi có thể phải chia giải, giả định người chơi chọn số đều."""
    lam = tickets * prob
    return 1.0 if lam < 1e-9 else (1 - math.exp(-lam)) / lam


def fixed_ev(game):
    p = odds(game)
    return sum(p[k] * net(FIXED[game][k]) for k in ("g1", "g2", "g3"))


def ticket_ev(game, jackpot, jackpot2, tickets):
    p = odds(game)
    fixed = fixed_ev(game)
    jp = p["jp"] * net(jackpot) * share_factor(tickets, p["jp"])
    j2 = p["j2"] * net(jackpot2) * share_factor(tickets, p["j2"]) if game == "power" else 0
    total = fixed + jp + j2
    return {
        "fixed": round(fixed),
        "jackpot": round(jp),
        "jackpot2": round(j2),
        "total": round(total),
        "pct": round(total / TICKET * 100, 1),
    }


def verdict(pct):
    if pct >= PLAY_PCT:
        return "Chơi", PLAY_TICKETS
    if pct >= LIGHT_PCT:
        return "Chơi nhẹ", LIGHT_TICKETS
    return "Nghỉ", 0


def breakeven(game, tickets, jackpot2):
    p = odds(game)
    fixed = fixed_ev(game)
    j2 = p["j2"] * net(jackpot2) * share_factor(tickets, p["j2"]) if game == "power" else 0
    out = {}
    for pct in (LIGHT_PCT, PLAY_PCT, 100):
        need_net = (pct / 100 * TICKET - fixed - j2) / (p["jp"] * share_factor(tickets, p["jp"]))
        out[str(pct)] = round((need_net - TAX_RATE * TAX_FREE) / (1 - TAX_RATE), -8)
    return out


def load_draws(game):
    rows = []
    file, size = (LOTTO["file"], 5) if game == "lotto" else (GAMES[game]["file"], 6)
    for line in (DATA / "raw" / file).read_text().splitlines():
        r = json.loads(line)
        rows.append({"id": int(r["id"]), "date": r["date"], "main": r["result"][:size], "extra": r["result"][size:size + 1]})
    rows.sort(key=lambda r: r["id"])
    return rows


def fetch_raw():
    for file in [g["file"] for g in GAMES.values()] + [LOTTO["file"]]:
        target = DATA / "raw" / file
        tmp = target.with_suffix(".tmp")
        subprocess.run(["curl", "-sSf", "-m", "90", "-o", str(tmp), RAW_BASE + file], check=True)
        if target.exists() and tmp.stat().st_size < target.stat().st_size:
            tmp.unlink()
            raise SystemExit(f"File tải về nhỏ hơn bản cũ, dừng để giữ dữ liệu: {file}")
        tmp.replace(target)


def next_date(game, after):
    d = after + timedelta(days=1)
    while d.weekday() not in GAMES[game]["days"]:
        d += timedelta(days=1)
    return d


def est_tickets(game, row):
    return row["g3"] / odds(game)["g3"]


def recent_tickets(game, rows):
    """Doanh số vé rơi mạnh ngay sau khi nổ jackpot, nên dùng mức thấp của giai đoạn gần đây."""
    full = [r for r in rows if r.get("g3")]
    if rows[-1]["jackpot_winners"] > 0:
        return min(est_tickets(game, r) for r in full[-13:])
    return mean(est_tickets(game, r) for r in full[-3:])


def est_next(game, rows):
    """Jackpot kỳ tới bằng mức hiện tại cộng bình quân 2 bước tăng gần nhất của chu kỳ đang chạy.

    Bước tăng phụ thuộc mạnh vào doanh số, mà doanh số đổi hẳn sau mỗi lần nổ jackpot, nên không
    lấy bước của chu kỳ trước. Kỳ ngay sau khi nổ dùng bước đầu tiên của 4 chu kỳ gần nhất.
    """
    keys = ["jackpot"] + (["jackpot2"] if game == "power" else [])
    out = {"jackpot2": 0}
    for key in keys:
        win_key = key + "_winners"
        rows_key = [r for r in rows if r.get(key) is not None]
        last = rows_key[-1]
        cycle, firsts = [], []
        for a, b in zip(rows_key, rows_key[1:]):
            if a[win_key] > 0:
                cycle = []
            elif b[key] > a[key]:
                if not cycle:
                    firsts.append(b[key] - a[key])
                cycle.append(b[key] - a[key])
        if last[win_key] > 0:
            cycle = []
        steps = cycle[-2:] or firsts[-4:]
        step = mean(steps) if steps else 0
        base = last[key] if last[win_key] == 0 else (GAMES[game]["seed_jp"] if key == "jackpot" else 3e9)
        out[key] = base + step
    return out


def seeded(*parts):
    return random.Random(int(hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest(), 16))


def is_uncrowded(nums, last_main):
    """Lọc các kiểu chọn số phổ biến. Không làm tăng khả năng trúng."""
    nums = sorted(nums)
    if sum(n > 31 for n in nums) < 3:
        return False
    run = best = 1
    for a, b in zip(nums, nums[1:]):
        run = run + 1 if b == a + 1 else 1
        best = max(best, run)
    if best >= 3:
        return False
    tails, tens = {}, {}
    for n in nums:
        tails[n % 10] = tails.get(n % 10, 0) + 1
        tens[n // 10] = tens.get(n // 10, 0) + 1
    if max(tails.values()) > 2 or max(tens.values()) > 3:
        return False
    return len(set(nums) & set(last_main)) < 3


def pick_filtered(rng, pool, last_main):
    while True:
        nums = rng.sample(range(1, pool + 1), 6)
        if is_uncrowded(nums, last_main):
            return sorted(nums)


def pick_random(rng, pool):
    return sorted(rng.sample(range(1, pool + 1), 6))


def fixed_prize(game, ticket, draw):
    """Tiền thực nhận từ các giải cố định. Jackpot báo riêng vì không có lịch sử đủ dài."""
    hit = len(set(ticket) & set(draw["main"]))
    extra = draw["extra"][0] if draw["extra"] else None
    if hit == 3:
        return net(FIXED[game]["g3"]), None
    if hit == 4:
        return net(FIXED[game]["g2"]), None
    if hit == 5:
        if game == "power" and extra in ticket:
            return 0, "jackpot2"
        return net(FIXED[game]["g1"]), None
    if hit == 6:
        return 0, "jackpot"
    return 0, None


def randomness(game, draws):
    n_pool = 35 if game == "lotto" else GAMES[game]["pool"]
    k = 5 if game == "lotto" else 6
    n = len(draws)
    p = k / n_pool
    counts = [0] * (n_pool + 1)
    for d in draws:
        for x in d["main"]:
            counts[x] += 1
    expected = n * p
    stat = sum((counts[i] - expected) ** 2 / expected for i in range(1, n_pool + 1)) / (1 - p)
    z = [round((counts[i] - expected) / math.sqrt(n * p * (1 - p)), 2) for i in range(1, n_pool + 1)]

    def signal(reverse):
        hits = []
        for i in range(HOT_WINDOW, n):
            window = [0] * (n_pool + 1)
            for d in draws[i - HOT_WINDOW:i]:
                for x in d["main"]:
                    window[x] += 1
            order = sorted(range(1, n_pool + 1), key=lambda x: (-window[x], x) if reverse else (window[x], x))
            hits.append(len(set(order[:k]) & set(draws[i]["main"])))
        mu = k * k / n_pool
        var = k * p * (1 - p) * (n_pool - k) / (n_pool - 1)
        zs = (mean(hits) - mu) / math.sqrt(var / len(hits))
        return {"mean": round(mean(hits), 3), "expected": round(mu, 3), "z": round(zs, 2),
                "p": round(2 * norm.sf(abs(zs)), 3), "draws": len(hits)}

    return {
        "draws": n, "first_id": draws[0]["id"], "last_id": draws[-1]["id"], "first_date": draws[0]["date"],
        "chi2": round(stat, 1), "df": n_pool - 1, "p": round(float(chi2.sf(stat, n_pool - 1)), 3),
        "expected_count": round(expected, 1), "counts": counts[1:], "z": z,
        "outside": sum(abs(v) > 1.96 for v in z), "outside_expected": round(n_pool * 0.05, 1),
        "hot": signal(True), "cold": signal(False),
    }


def filter_check(all_draws):
    """So tỷ lệ vé trúng từ giải ba trở lên giữa bộ số đã lọc, chọn ngẫu nhiên và lý thuyết."""
    wins = {"filter": 0, "random": 0}
    tickets = 0
    for game, draws in all_draws.items():
        if game == "lotto":
            continue
        pool = GAMES[game]["pool"]
        for i in range(1, len(draws)):
            main = set(draws[i]["main"])
            for sim in range(FULL_SIMS):
                rng = seeded("full", game, i, sim)
                wins["filter"] += len(main & set(pick_filtered(rng, pool, draws[i - 1]["main"]))) >= 3
                wins["random"] += len(main & set(pick_random(rng, pool))) >= 3
                tickets += 1
    weights = {g: (len(d) - 1) * FULL_SIMS for g, d in all_draws.items() if g != "lotto"}
    theory = sum(w * sum(odds(g).values()) for g, w in weights.items()) / tickets
    return {
        "tickets": tickets,
        "filter_win_pct": round(wins["filter"] / tickets * 100, 2),
        "random_win_pct": round(wins["random"] / tickets * 100, 2),
        "theory_win_pct": round(theory * 100, 2),
    }


def write_history(all_draws, valid_rows, lotto):
    """Lưu toàn bộ dãy số đã quay, mới nhất trước, kèm jackpot của các kỳ có số liệu."""
    out = {}
    for game, draws in all_draws.items():
        if game == "lotto":
            continue
        rows = {r["id"]: r for r in valid_rows[game]}
        items = []
        for d in reversed(draws):
            item = {"id": d["id"], "date": d["date"], "main": d["main"], "extra": d["extra"]}
            r = rows.get(d["id"])
            if r:
                item.update(jackpot=r["jackpot"], winners=r["jackpot_winners"])
                if game == "power":
                    item.update(jackpot2=r.get("jackpot2"), winners2=r.get("jackpot2_winners", 0))
            items.append(item)
        out[game] = items
    rows = {r["id"]: r for r in lotto["rows"]}
    rolled = {x["id"] for x in lotto["rolldowns"]}
    ids = {d["id"]: d for d in all_draws["lotto"]}
    ids[lotto["latest"]["id"]] = lotto["latest"]
    items = []
    for i in sorted(ids, reverse=True):
        d = ids[i]
        item = {"id": d["id"], "date": d["date"], "main": d["main"], "extra": d["extra"]}
        if i in rows:
            item.update(jackpot=rows[i]["jackpot"], winners=rows[i]["jackpot_winners"])
        if i in rolled:
            item["rolldown"] = True
        items.append(item)
    out["lotto"] = items
    (DATA / "history.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")) + "\n")


def lotto_fixed_ev():
    return sum(LOTTO_ODDS[k] * net(LOTTO_BASE[k]) for k in LOTTO_BASE)


def rolldown_ev(jackpot, tickets):
    """Giá trị một vé ở kỳ chia giải, giả định đủ hạng có người trúng và chọn số đều."""
    paid = 0.0
    for tier, share in LOTTO_SHARE.items():
        pool = jackpot * share
        winners = max(tickets * LOTTO_ODDS[tier], 1)
        paid += winners * net(pool / winners + LOTTO_BASE[tier]) - winners * LOTTO_BASE[tier]
    extra = paid / tickets
    total = extra + lotto_fixed_ev()
    return {"share": round(extra), "fixed": round(lotto_fixed_ev()), "total": round(total), "pct": round(total / TICKET * 100, 1)}


def rolldown_ahead(jackpot, tickets):
    """Giá trị vé trước kỳ quay. Có người trúng Độc đắc thì không chia giải, tiền về người trúng."""
    split = rolldown_ev(jackpot, tickets)
    miss = math.exp(-tickets * LOTTO_ODDS["jp"])
    share = miss * split["share"] + (1 - miss) * net(jackpot) / tickets
    total = share + lotto_fixed_ev()
    return {"share": round(share), "fixed": split["fixed"], "total": round(total), "pct": round(total / TICKET * 100, 1),
            "hit_pct": round((1 - miss) * 100)}


def draw_slot(draw_id):
    """Mỗi ngày có 2 kỳ: kỳ số lẻ quay lúc 13h, kỳ số chẵn quay lúc 21h."""
    return "13h" if draw_id % 2 else "21h"


def step_draw(day, slot):
    return (day, "21h") if slot == "13h" else (day + timedelta(days=1), "13h")


def lotto_uncrowded(nums, last_main):
    nums = sorted(nums)
    if not any(n > 31 for n in nums):
        return False
    run = best = 1
    for a, b in zip(nums, nums[1:]):
        run = run + 1 if b == a + 1 else 1
        best = max(best, run)
    tails = {}
    for n in nums:
        tails[n % 10] = tails.get(n % 10, 0) + 1
    return best < 3 and max(tails.values()) <= 2 and len(set(nums) & set(last_main)) < 3


def pick_lotto(rng, last_main):
    while True:
        nums = rng.sample(range(1, 36), 5)
        if lotto_uncrowded(nums, last_main):
            return sorted(nums) + [rng.randint(1, 12)]


def lotto_prize(ticket, row):
    main, special = set(row["numbers"][:5]), row["numbers"][5]
    hit, sp = len(set(ticket[:5]) & main), ticket[5] == special
    if hit == 5:
        return (0, "jackpot") if sp else (net(row["values"]["g1"]), None)
    if hit == 4:
        return net(row["values"]["g2"] if sp else row["values"]["g3"]), None
    if hit == 3:
        return net(row["values"]["g4"] if sp else row["values"]["g5"]), None
    return (LOTTO_BASE["kk"] if sp else 0), None


def split_values(row):
    """Tính giá trị từng giải ở kỳ chia giải khi nguồn chỉ ghi giá trị cơ bản."""
    tiers = [t for t in LOTTO_SHARE if row["winners"].get(t)]
    spare = sum(LOTTO_SHARE[t] for t in LOTTO_SHARE if t not in tiers)
    out = dict(row["values"])
    for t in tiers:
        share = LOTTO_SHARE[t] + spare / len(tiers)
        out[t] = LOTTO_BASE[t] + int(row["jackpot"] * share / row["winners"][t] // 5000 * 5000)
    return out


def lotto_block(draws, store, warnings, today):
    by_id = {d["id"]: d for d in draws}
    rows = []
    for r in sorted(store["rows"], key=lambda x: x["id"]):
        r = {"values": dict((k, v) for k, v in LOTTO_BASE.items() if k != "kk"), **r}
        d = by_id.get(r["id"])
        if d is not None and (d["main"] + d["extra"] != r["numbers"] or d["date"] != r["date"]):
            warnings.append(f"Lotto 5/35 kỳ {r['id']}: hai nguồn lệch nhau, đã bỏ kỳ này.")
            continue
        rows.append(r)
    known = {x["id"] for x in store["rolldowns"]}
    row_of = {r["id"]: r for r in rows}
    for i, a in enumerate(rows):
        if a["jackpot"] <= LOTTO["trigger"] or a["jackpot_winners"] > 0 or not a.get("winners"):
            continue
        after = rows[i + 1] if i + 1 < len(rows) else None
        earlier = row_of.get(a["id"] - 2)
        due = draw_slot(a["id"]) == "21h" and earlier is not None and earlier["jackpot"] > LOTTO["trigger"]
        if (after is not None and after["jackpot"] < a["jackpot"]) or (after is None and due):
            if a["values"]["g2"] == LOTTO_BASE["g2"]:
                a["values"] = split_values(a)
            if a["id"] not in known:
                known.add(a["id"])
                store["rolldowns"].append({"id": a["id"], "date": a["date"], "jackpot": a["jackpot"],
                                           "tickets": round(a["winners"]["kk"] / LOTTO_ODDS["kk"], -4),
                                           "basis": "Suy từ số giải Khuyến khích"})
    for r in rows:
        if r["jackpot_winners"] == 0 and r["values"]["g2"] > LOTTO_BASE["g2"] and r["id"] not in known and r.get("winners"):
            store["rolldowns"].append({"id": r["id"], "date": r["date"], "jackpot": r["jackpot"],
                                       "tickets": round(r["winners"]["kk"] / LOTTO_ODDS["kk"], -4),
                                       "basis": "Suy từ số giải Khuyến khích"})
    store["rolldowns"].sort(key=lambda x: x["id"])

    last = rows[-1]
    last_raw = draws[-1]
    if last["id"] < last_raw["id"]:
        warnings.append(f"Lotto 5/35: chưa có số liệu kỳ {last_raw['id']}, sẽ cập nhật ở lượt sau.")
    for r in rows:
        if r["id"] > draws[-1]["id"]:
            draws.append({"id": r["id"], "date": r["date"], "main": r["numbers"][:5], "extra": r["numbers"][5:]})
    latest = draws[-1]
    day, slot = date.fromisoformat(latest["date"]), draw_slot(latest["id"])
    start = max((i + 1 for i, r in enumerate(rows) if r["jackpot_winners"] > 0 or r["id"] in known), default=0)
    start = max([start] + [i + 1 for i, (a, b) in enumerate(zip(rows, rows[1:])) if b["jackpot"] < a["jackpot"]])
    cycle = rows[start:]
    rises = [b["jackpot"] - a["jackpot"] for a, b in zip(cycle, cycle[1:]) if b["jackpot"] > a["jackpot"]][-3:]
    step = mean(rises) if rises else 240e6
    tickets = mean(r["winners"]["g5"] / LOTTO_ODDS["g5"] for r in [x for x in rows if x.get("winners")][-3:])
    jackpot = last["jackpot"] if last["jackpot_winners"] == 0 and last["values"]["g2"] == LOTTO_BASE["g2"] else LOTTO["seed_jp"]
    armed_date = None
    if jackpot > LOTTO["trigger"]:
        first = rows[-1]
        for r in reversed(rows):
            if r["jackpot"] <= LOTTO["trigger"] or r["jackpot_winners"] > 0 or r["values"]["g2"] != LOTTO_BASE["g2"]:
                break
            first = r
        armed_date = date.fromisoformat(first["date"]) + timedelta(days=1)

    next_day, next_slot = step_draw(day, slot)
    next_id = latest["id"] + 1
    if armed_date and next_day > armed_date:
        if last["id"] < last_raw["id"]:
            warnings.append("Lotto 5/35: đã qua kỳ chia giải dự kiến, đang chờ số liệu thật của kỳ đó.")
        armed_date, jackpot = None, LOTTO["seed_jp"]
    draws_to = 0 if armed_date else max(1, math.ceil((LOTTO["trigger"] - jackpot + 1) / step))
    if armed_date:
        target_day = armed_date
    else:
        reach_day, reach_slot = day, slot
        for _ in range(draws_to):
            reach_day, reach_slot = step_draw(reach_day, reach_slot)
        target_day = reach_day + timedelta(days=1)
    gap = 0
    d_, s_ = next_day, next_slot
    while (d_, s_) != (target_day, "21h"):
        d_, s_ = step_draw(d_, s_)
        gap += 1
    target_id = next_id + gap
    est_jackpot = jackpot + step * (gap + 1)
    ratio = store["rolldowns"][-1]["tickets"] / store["rolldowns"][-1]["jackpot"]
    est_tickets = est_jackpot * ratio
    roll = rolldown_ahead(est_jackpot, est_tickets)
    is_rolldown = armed_date is not None and (next_day, next_slot) == (armed_date, "21h")
    status = "rolldown" if is_rolldown else "armed" if armed_date else "near" if draws_to <= LOTTO["near_draws"] else "normal"

    fixed = lotto_fixed_ev()
    jp = LOTTO_ODDS["jp"] * net(jackpot + step) * share_factor(tickets, LOTTO_ODDS["jp"])
    ev = {"fixed": round(fixed), "jackpot": round(jp), "jackpot2": 0, "total": round(fixed + jp), "pct": round((fixed + jp) / TICKET * 100, 1)}
    if is_rolldown:
        ev = {"fixed": roll["fixed"], "jackpot": roll["share"], "jackpot2": 0, "total": roll["total"], "pct": roll["pct"]}
    if is_rolldown and roll["pct"] >= 100:
        label, count = "Chơi", WEEK_TICKETS
    elif is_rolldown:
        label, count = verdict(roll["pct"])
    else:
        label, count = "Nghỉ", 0
    rng = seeded("set", "lotto", next_id)
    sets = [pick_lotto(rng, latest["main"]) for _ in range(max(count, LIGHT_TICKETS))]
    book = [dict(x, value=rolldown_ev(x["jackpot"], x["tickets"])["total"], pct=rolldown_ev(x["jackpot"], x["tickets"])["pct"]) for x in store["rolldowns"]]
    return {
        "game": "lotto", "name": LOTTO["name"], "id": next_id, "date": next_day.isoformat(), "slot": next_slot,
        "weekday": WEEKDAYS[next_day.weekday()], "jackpot": round(jackpot + step, -6), "jackpot2": 0,
        "tickets_est": round(tickets, -3), "ev": ev, "verdict": label, "tickets": count, "sets": sets,
        "status": status, "current_jackpot": jackpot, "trigger": LOTTO["trigger"], "draws_to": draws_to,
        "target": {"id": target_id, "date": target_day.isoformat(), "weekday": WEEKDAYS[target_day.weekday()],
                   "jackpot": round(est_jackpot, -7), "tickets": round(est_tickets, -4), "ev": roll},
        "rolldowns": book, "rows": rows, "latest": latest,
    }


def due_lotto(now):
    """Kỳ Lotto gần nhất đáng lẽ đã có số liệu, chừa 3 giờ sau giờ quay."""
    n = (now.date() - date(2025, 6, 29)).days * 2
    return n + 1 if now.hour >= 16 else n


def due_game(days, now):
    """Ngày quay Mega hoặc Power gần nhất đáng lẽ đã có số liệu, chừa 3 giờ sau 18h."""
    d = now.date() - timedelta(days=0 if now.hour >= 21 else 1)
    while d.weekday() not in days:
        d -= timedelta(days=1)
    return d


def week_start(d):
    return d - timedelta(days=d.weekday())


def update_portfolio(next_rows, all_draws, today, lotto_rows):
    path = DATA / "portfolio.json"
    ledger = json.loads(path.read_text()) if path.exists() else []
    by_id = {g: {d["id"]: d for d in draws} for g, draws in all_draws.items()}
    lotto_by_id = {r["id"]: r for r in lotto_rows}
    for e in ledger:
        if e["status"] == "pending" and e["game"] == "lotto" and e["id"] in lotto_by_id:
            row = lotto_by_id[e["id"]]
            res = [lotto_prize(t, row) for t in e["tickets"]]
            base = [lotto_prize(t, row) for t in e["baseline"]]
            e.update(status="done", date=row["date"], returned=sum(r[0] for r in res),
                     returned_baseline=sum(r[0] for r in base),
                     jackpot_hits=[r[1] for r in res if r[1]], numbers=row["numbers"])
        elif e["status"] == "pending" and e["game"] != "lotto" and e["id"] in by_id[e["game"]]:
            draw = by_id[e["game"]][e["id"]]
            res = [fixed_prize(e["game"], t, draw) for t in e["tickets"]]
            base = [fixed_prize(e["game"], t, draw) for t in e["baseline"]]
            e.update(status="done", date=draw["date"], returned=sum(r[0] for r in res),
                     returned_baseline=sum(r[0] for r in base),
                     jackpot_hits=[r[1] for r in res if r[1]],
                     numbers=draw["main"] + draw["extra"])
    for row in sorted(next_rows, key=lambda r: r["date"]):
        if any(e["game"] == row["game"] and e["id"] == row["id"] for e in ledger):
            continue
        if row["game"] == "lotto" and row["tickets"] == 0:
            continue
        ws = week_start(date.fromisoformat(row["date"]))
        used = sum(len(e["tickets"]) for e in ledger if week_start(date.fromisoformat(e["date"])) == ws)
        count = min(row["tickets"], max(0, WEEK_TICKETS - used))
        rng = seeded("base", row["game"], row["id"])
        pick = (lambda: pick_random(rng, 35)[:5] + [rng.randint(1, 12)]) if row["game"] == "lotto" else (lambda: pick_random(rng, GAMES[row["game"]]["pool"]))
        ledger.append({
            "game": row["game"], "id": row["id"], "date": row["date"], "verdict": row["verdict"],
            "ev_pct": row["ev"]["pct"], "tickets": row["sets"][:count],
            "baseline": [pick() for _ in range(count)],
            "status": "pending",
        })
    path.write_text(json.dumps(ledger, ensure_ascii=False, indent=1) + "\n")
    ws = week_start(today)
    done = [e for e in ledger if e["status"] == "done"]
    spent = sum(len(e["tickets"]) for e in done) * TICKET
    return {
        "start": FORWARD_START,
        "week_used": sum(len(e["tickets"]) for e in ledger if week_start(date.fromisoformat(e["date"])) == ws),
        "week_cap": WEEK_TICKETS,
        "spent": spent, "returned": round(sum(e["returned"] for e in done)),
        "returned_baseline": round(sum(e["returned_baseline"] for e in done)),
        "skipped": sum(1 for e in done if not e["tickets"]),
        "resolved": len(done),
        "log": ledger[-12:][::-1],
    }


def pct_error(est, actual):
    return round(abs(est - actual) / actual * 100, 1) if est and actual else None


def actual_result(entry, all_draws, valid_rows, lotto):
    """Trả về kết quả thật của một kỳ, hoặc None nếu chưa có đủ dãy số và jackpot."""
    if entry["game"] == "lotto":
        row = next((r for r in lotto["rows"] if r["id"] == entry["id"]), None)
        if row is None:
            return None
        main, jackpot2 = row["numbers"][:5], None
        tickets = row["winners"]["g5"] / LOTTO_ODDS["g5"] if row.get("winners") else None
    else:
        row = next((r for r in valid_rows[entry["game"]] if r["id"] == entry["id"]), None)
        draw = next((d for d in all_draws[entry["game"]] if d["id"] == entry["id"]), None)
        if row is None or draw is None:
            return None
        main, jackpot2 = draw["main"], row.get("jackpot2")
        tickets = est_tickets(entry["game"], row) if row.get("g3") else None
    hits = [len(set(t[:len(main)]) & set(main)) for t in entry["sets"]]
    return {
        "jackpot": row["jackpot"], "jackpot2": jackpot2, "tickets": round(tickets, -3) if tickets else None,
        "jackpot_winners": row["jackpot_winners"], "numbers": row["numbers"], "set_hits": hits,
        "jackpot_error_pct": pct_error(entry["jackpot_est"], row["jackpot"]),
        "tickets_error_pct": pct_error(entry["tickets_est"], tickets),
    }


def update_forecast_log(all_rows, all_draws, valid_rows, lotto, now):
    """Sổ dự báo: mỗi lượt chạy một dòng cho mỗi kỳ tới, không sửa số đã ghi của lượt trước."""
    path = DATA / "forecast_log.json"
    log = json.loads(path.read_text()) if path.exists() else []
    run = now.strftime("%Y-%m-%d") + ("-sang" if now.hour < 14 else "-toi")
    for e in log:
        if e["actual"] is None:
            e["actual"] = actual_result(e, all_draws, valid_rows, lotto)
    upcoming = {(r["game"], r["id"]) for r in all_rows}
    log = [e for e in log if not (e["run"] == run and e["actual"] is None and (e["game"], e["id"]) in upcoming)]
    done = {(e["game"], e["id"]) for e in log if e["actual"] is not None}
    for r in all_rows:
        if (r["game"], r["id"]) in done:
            continue
        target = r.get("target") or {}
        log.append({
            "run": run, "run_at": now.isoformat(timespec="minutes"), "game": r["game"], "id": r["id"],
            "draw_date": r["date"], "slot": r.get("slot"), "jackpot_est": r["jackpot"],
            "jackpot2_est": r["jackpot2"] or None, "tickets_est": r["tickets_est"], "ev_total": r["ev"]["total"],
            "ev_pct": r["ev"]["pct"], "verdict": r["verdict"], "tickets": r["tickets"], "sets": r["sets"],
            "status": r.get("status"), "draws_to": r.get("draws_to"), "target_id": target.get("id"),
            "target_date": target.get("date"), "target_jackpot": target.get("jackpot"),
            "target_tickets": target.get("tickets"), "target_ev": (target.get("ev") or {}).get("total"), "actual": None,
        })
    path.write_text("[\n" + ",\n".join(json.dumps(e, ensure_ascii=False, separators=(",", ":")) for e in log) + "\n]\n")

    summary = {"forecasts": len(log), "start": log[0]["run_at"][:10], "games": {}}
    pool = {"mega": (45, 6), "power": (55, 6), "lotto": (35, 5)}
    for game, (n, k) in pool.items():
        last = {}
        for e in log:
            if e["game"] == game and e["actual"] is not None:
                last[e["id"]] = e
        rows = list(last.values())
        jack = [e["actual"]["jackpot_error_pct"] for e in rows if e["actual"]["jackpot_error_pct"] is not None]
        tick = [e["actual"]["tickets_error_pct"] for e in rows if e["actual"]["tickets_error_pct"] is not None]
        hits = [h for e in rows for h in e["actual"]["set_hits"]]
        summary["games"][game] = {
            "scored": len(rows), "jackpot_error": round(mean(jack), 1) if jack else None,
            "tickets_error": round(mean(tick), 1) if tick else None,
            "set_hits": round(mean(hits), 3) if hits else None, "set_hits_expected": round(k * k / n, 3),
            "sets": len(hits),
        }
    errors = []
    for x in lotto["rolldowns"]:
        made = [e for e in log if e["game"] == "lotto" and e["target_id"] and e["id"] <= x["id"] and e["run_at"][:10] <= x["date"] and e["id"] > x["id"] - 30]
        if made:
            errors.append({"id": x["id"], "forecasts": len(made), "first_target": made[0]["target_id"], "last_target": made[-1]["target_id"]})
    summary["rolldowns"] = errors
    return summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-fetch", action="store_true", help="dùng dữ liệu đã có trong data/raw")
    args = ap.parse_args()
    if not args.no_fetch:
        fetch_raw()

    now = datetime.now(VN)
    today = now.date()
    jackpots = json.loads((DATA / "jackpots.json").read_text())
    all_draws = {g: load_draws(g) for g in GAMES}
    warnings, next_rows, ev_history, be, tests, latest, valid_rows = [], [], {}, {}, {}, {}, {}
    stale = []

    for game, info in GAMES.items():
        draws = all_draws[game]
        by_id = {d["id"]: d for d in draws}
        rows = []
        for r in sorted(jackpots[game], key=lambda x: x["id"]):
            d = by_id.get(r["id"])
            if d is None and r["id"] > draws[-1]["id"]:
                d = {"id": r["id"], "date": r["date"], "main": r["numbers"][:6], "extra": r["numbers"][6:]}
                draws.append(d)
                by_id[r["id"]] = d
            if d is None:
                warnings.append(f"{info['name']} kỳ {r['id']}: chưa có trong dữ liệu kết quả.")
            elif d["main"] + d["extra"] != r["numbers"] or d["date"] != r["date"]:
                warnings.append(f"{info['name']} kỳ {r['id']}: hai nguồn lệch nhau, đã bỏ kỳ này.")
            else:
                rows.append(r)
        valid_rows[game] = rows
        last = draws[-1]
        if not rows or rows[-1]["id"] != last["id"]:
            warnings.append(f"{info['name']}: chưa có jackpot kỳ {last['id']}, sẽ cập nhật ở lượt sau.")
        last_date = date.fromisoformat(last["date"])
        if (today - last_date).days > 3:
            warnings.append(f"{info['name']}: dữ liệu kết quả dừng ở {last['date']}.")
        if not rows or rows[-1]["date"] < due_game(info["days"], now).isoformat():
            stale.append(info["name"])

        tickets = recent_tickets(game, rows)
        est = est_next(game, rows)
        ev = ticket_ev(game, est["jackpot"], est["jackpot2"], tickets)
        label, count = verdict(ev["pct"])
        when = next_date(game, last_date)
        draw_id = last["id"] + 1
        rng = seeded("set", game, draw_id)
        sets = [pick_filtered(rng, info["pool"], last["main"]) for _ in range(max(count, LIGHT_TICKETS))]
        next_rows.append({
            "game": game, "name": info["name"], "id": draw_id, "date": when.isoformat(),
            "weekday": WEEKDAYS[when.weekday()], "jackpot": round(est["jackpot"], -6),
            "jackpot2": round(est["jackpot2"], -6), "tickets_est": round(tickets, -4),
            "ev": ev, "verdict": label, "tickets": count, "sets": sets,
        })
        latest[game] = {
            "id": last["id"], "date": last["date"], "weekday": WEEKDAYS[last_date.weekday()],
            "main": last["main"], "extra": last["extra"],
            "jackpot": rows[-1]["jackpot"] if rows else None,
            "jackpot_winners": rows[-1]["jackpot_winners"] if rows else None,
        }
        ev_history[game] = [
            {"id": r["id"], "date": r["date"], "jackpot": r["jackpot"], "winners": r["jackpot_winners"],
             "pct": ticket_ev(game, r["jackpot"], r.get("jackpot2") or 0, est_tickets(game, r))["pct"]}
            for r in [x for x in rows if x.get("g3")][-EV_HISTORY:]
        ]
        be[game] = breakeven(game, tickets, est["jackpot2"])
        tests[game] = randomness(game, draws)

    store = json.loads((DATA / "lotto.json").read_text())
    lotto_draws = load_draws("lotto")
    lotto = lotto_block(lotto_draws, store, warnings, today)
    (DATA / "lotto.json").write_text(json.dumps(store, ensure_ascii=False, indent=0) + "\n")
    tests["lotto"] = randomness("lotto", lotto_draws)
    if lotto["status"] in ("near", "armed", "rolldown"):
        for r in next_rows:
            r["hold"] = True
            r["verdict"] = "Giữ vé" if r["tickets"] else r["verdict"]
            r["tickets"] = 0
    lotto_card = {k: v for k, v in lotto.items() if k not in ("rows", "rolldowns", "latest")}
    all_rows = next_rows + [lotto_card]
    portfolio = update_portfolio(all_rows, all_draws, today, lotto["rows"])
    write_history({**all_draws, "lotto": lotto_draws}, valid_rows, lotto)
    accuracy = update_forecast_log(all_rows, all_draws, valid_rows, lotto, now)
    latest["lotto"] = {
        "id": lotto["latest"]["id"], "date": lotto["latest"]["date"],
        "weekday": WEEKDAYS[date.fromisoformat(lotto["latest"]["date"]).weekday()],
        "main": lotto["latest"]["main"], "extra": lotto["latest"]["extra"],
        "jackpot": lotto["rows"][-1]["jackpot"], "jackpot_winners": lotto["rows"][-1]["jackpot_winners"],
    }
    commentary_file = DATA / "commentary.json"
    commentary = json.loads(commentary_file.read_text()) if commentary_file.exists() else {}
    if lotto["rows"][-1]["id"] < due_lotto(now):
        stale.append(LOTTO["name"])
    for name in stale:
        if not any(w.startswith(name) for w in warnings):
            warnings.append(f"{name}: chưa có số liệu kỳ mới nhất, nhận định có thể chưa cập nhật.")
    if commentary.get("date") == today.isoformat() and "status" not in commentary:
        commentary["status"] = lotto["status"]
        commentary_file.write_text(json.dumps(commentary, ensure_ascii=False, indent=1) + "\n")
    if stale or commentary.get("date") != today.isoformat() or commentary.get("status") != lotto["status"]:
        best = max(all_rows, key=lambda r: r["ev"]["pct"])
        all_rest = all(r["tickets"] == 0 for r in all_rows)
        commentary = {
            "date": today.isoformat(), "auto": True,
            "headline": "Đang chờ số liệu kỳ mới." if stale
            else "Hôm nay có kỳ chia giải Lotto 5/35." if lotto["status"] == "rolldown"
            else "Sắp có kỳ chia giải Lotto 5/35." if lotto["status"] in ("near", "armed")
            else "Các kỳ tới chưa đáng mua vé." if all_rest else f"{best['name']} là kỳ đáng cân nhắc nhất.",
            "paragraphs": ["Đang chờ số liệu kỳ mới, nhận định sẽ cập nhật ở lượt sau." if stale else
                           f"{best['name']} đang có giá trị vé cao nhất, khoảng {best['ev']['total']:_}đ trên vé 10.000đ.".replace("_", ".")],
        }
    out = {
        "generated_at": now.isoformat(timespec="minutes"), "today": today.isoformat(),
        "weekday": WEEKDAYS[today.weekday()], "commentary": commentary, "warnings": warnings, "stale": stale,
        "next": sorted(all_rows, key=lambda r: (r["date"], r["game"] != "lotto")), "latest": latest, "ev_history": ev_history,
        "rolldowns": lotto["rolldowns"], "lotto_fixed": round(lotto_fixed_ev()), "lotto_odds": {k: round(1 / v) for k, v in LOTTO_ODDS.items()},
        "lotto_breakeven": {str(j): round(0.95 * j * 1e9 / (TICKET - lotto_fixed_ev()), -4) for j in (13, 20, 30)},
        "breakeven": be, "tests": tests, "portfolio": portfolio, "accuracy": accuracy, "filter_check": filter_check(all_draws),
        "rules": {"ticket": TICKET, "play_pct": PLAY_PCT, "light_pct": LIGHT_PCT, "play_tickets": PLAY_TICKETS,
                  "light_tickets": LIGHT_TICKETS, "week_tickets": WEEK_TICKETS, "hot_window": HOT_WINDOW},
        "odds": {g: {k: round(1 / v) for k, v in odds(g).items()} for g in GAMES},
    }
    (DATA / "dashboard.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n")
    print(json.dumps({"next": [(r["name"], r["id"], r["date"], r["ev"], r["verdict"], r.get("status")) for r in out["next"]],
                      "warnings": warnings}, ensure_ascii=False))


if __name__ == "__main__":
    main()
