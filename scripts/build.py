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
    for line in (DATA / "raw" / GAMES[game]["file"]).read_text().splitlines():
        r = json.loads(line)
        rows.append({"id": int(r["id"]), "date": r["date"], "main": r["result"][:6], "extra": r["result"][6:7]})
    rows.sort(key=lambda r: r["id"])
    return rows


def fetch_raw():
    for game in GAMES.values():
        target = DATA / "raw" / game["file"]
        tmp = target.with_suffix(".tmp")
        subprocess.run(["curl", "-sSf", "-m", "90", "-o", str(tmp), RAW_BASE + game["file"]], check=True)
        if tmp.stat().st_size < target.stat().st_size:
            tmp.unlink()
            raise SystemExit(f"File tải về nhỏ hơn bản cũ, dừng để giữ dữ liệu: {game['file']}")
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
    if rows[-1]["jackpot_winners"] > 0:
        return min(est_tickets(game, r) for r in rows[-13:])
    return mean(est_tickets(game, r) for r in rows[-3:])


def est_next(game, rows):
    """Jackpot kỳ tới bằng mức hiện tại cộng bình quân 2 bước tăng gần nhất của chu kỳ đang chạy.

    Bước tăng phụ thuộc mạnh vào doanh số, mà doanh số đổi hẳn sau mỗi lần nổ jackpot, nên không
    lấy bước của chu kỳ trước. Kỳ ngay sau khi nổ dùng bước đầu tiên của 4 chu kỳ gần nhất.
    """
    keys = ["jackpot"] + (["jackpot2"] if game == "power" else [])
    out = {"jackpot2": 0}
    last = rows[-1]
    for key in keys:
        win_key = key + "_winners"
        cycle, firsts = [], []
        for a, b in zip(rows, rows[1:]):
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
    n_pool = GAMES[game]["pool"]
    n = len(draws)
    p = 6 / n_pool
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
            hits.append(len(set(order[:6]) & set(draws[i]["main"])))
        mu = 36 / n_pool
        var = 6 * p * (1 - p) * (n_pool - 6) / (n_pool - 1)
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
        pool = GAMES[game]["pool"]
        for i in range(1, len(draws)):
            main = set(draws[i]["main"])
            for sim in range(FULL_SIMS):
                rng = seeded("full", game, i, sim)
                wins["filter"] += len(main & set(pick_filtered(rng, pool, draws[i - 1]["main"]))) >= 3
                wins["random"] += len(main & set(pick_random(rng, pool))) >= 3
                tickets += 1
    weights = {g: (len(d) - 1) * FULL_SIMS for g, d in all_draws.items()}
    theory = sum(w * sum(odds(g).values()) for g, w in weights.items()) / tickets
    return {
        "tickets": tickets,
        "filter_win_pct": round(wins["filter"] / tickets * 100, 2),
        "random_win_pct": round(wins["random"] / tickets * 100, 2),
        "theory_win_pct": round(theory * 100, 2),
    }


def write_history(all_draws, valid_rows):
    """Lưu toàn bộ dãy số đã quay, mới nhất trước, kèm jackpot của các kỳ có số liệu."""
    out = {}
    for game, draws in all_draws.items():
        rows = {r["id"]: r for r in valid_rows[game]}
        items = []
        for d in reversed(draws):
            item = {"id": d["id"], "date": d["date"], "main": d["main"], "extra": d["extra"]}
            r = rows.get(d["id"])
            if r:
                item.update(jackpot=r["jackpot"], winners=r["jackpot_winners"])
                if game == "power":
                    item.update(jackpot2=r["jackpot2"], winners2=r["jackpot2_winners"])
            items.append(item)
        out[game] = items
    (DATA / "history.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")) + "\n")


def week_start(d):
    return d - timedelta(days=d.weekday())


def update_portfolio(next_rows, all_draws, today):
    path = DATA / "portfolio.json"
    ledger = json.loads(path.read_text()) if path.exists() else []
    by_id = {g: {d["id"]: d for d in draws} for g, draws in all_draws.items()}
    for e in ledger:
        if e["status"] == "pending" and e["id"] in by_id[e["game"]]:
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
        ws = week_start(date.fromisoformat(row["date"]))
        used = sum(len(e["tickets"]) for e in ledger if week_start(date.fromisoformat(e["date"])) == ws)
        count = min(row["tickets"], max(0, WEEK_TICKETS - used))
        rng = seeded("base", row["game"], row["id"])
        ledger.append({
            "game": row["game"], "id": row["id"], "date": row["date"], "verdict": row["verdict"],
            "ev_pct": row["ev"]["pct"], "tickets": row["sets"][:count],
            "baseline": [pick_random(rng, GAMES[row["game"]]["pool"]) for _ in range(count)],
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

    for game, info in GAMES.items():
        draws = all_draws[game]
        by_id = {d["id"]: d for d in draws}
        rows = []
        for r in sorted(jackpots[game], key=lambda x: x["id"]):
            d = by_id.get(r["id"])
            if d is None:
                warnings.append(f"{info['name']} kỳ {r['id']}: chưa có trong dữ liệu kết quả.")
            elif d["main"] + d["extra"] != r["numbers"] or d["date"] != r["date"]:
                warnings.append(f"{info['name']} kỳ {r['id']}: hai nguồn lệch nhau, đã bỏ kỳ này.")
            else:
                rows.append(r)
        valid_rows[game] = rows
        last = draws[-1]
        if not rows or rows[-1]["id"] != last["id"]:
            warnings.append(f"{info['name']}: thiếu jackpot kỳ {last['id']}, số ước tính có thể cũ.")
        last_date = date.fromisoformat(last["date"])
        if (today - last_date).days > 3:
            warnings.append(f"{info['name']}: dữ liệu kết quả dừng ở {last['date']}.")

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
             "pct": ticket_ev(game, r["jackpot"], r.get("jackpot2", 0), est_tickets(game, r))["pct"]}
            for r in rows[-EV_HISTORY:]
        ]
        be[game] = breakeven(game, tickets, est["jackpot2"])
        tests[game] = randomness(game, draws)

    portfolio = update_portfolio(next_rows, all_draws, today)
    write_history(all_draws, valid_rows)
    commentary_file = DATA / "commentary.json"
    commentary = json.loads(commentary_file.read_text()) if commentary_file.exists() else {}
    if commentary.get("date") != today.isoformat():
        best = max(next_rows, key=lambda r: r["ev"]["pct"])
        all_rest = all(r["tickets"] == 0 for r in next_rows)
        commentary = {
            "date": today.isoformat(), "auto": True,
            "headline": "Hai kỳ tới chưa đáng mua vé." if all_rest else f"{best['name']} là kỳ đáng cân nhắc nhất.",
            "paragraphs": [f"{best['name']} đang có giá trị kỳ vọng cao hơn, khoảng {best['ev']['total']:,}đ trên vé 10.000đ.".replace(",", ".")],
        }
    out = {
        "generated_at": now.isoformat(timespec="minutes"), "today": today.isoformat(),
        "weekday": WEEKDAYS[today.weekday()], "commentary": commentary, "warnings": warnings,
        "next": sorted(next_rows, key=lambda r: r["date"]), "latest": latest, "ev_history": ev_history,
        "breakeven": be, "tests": tests, "portfolio": portfolio, "filter_check": filter_check(all_draws),
        "rules": {"ticket": TICKET, "play_pct": PLAY_PCT, "light_pct": LIGHT_PCT, "play_tickets": PLAY_TICKETS,
                  "light_tickets": LIGHT_TICKETS, "week_tickets": WEEK_TICKETS, "hot_window": HOT_WINDOW},
        "odds": {g: {k: round(1 / v) for k, v in odds(g).items()} for g in GAMES},
    }
    (DATA / "dashboard.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n")
    print(json.dumps({"next": [(r["name"], r["id"], r["date"], r["ev"], r["verdict"]) for r in out["next"]],
                      "warnings": warnings}, ensure_ascii=False))


if __name__ == "__main__":
    main()
