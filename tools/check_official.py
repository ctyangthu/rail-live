"""Compare the TDX station timetables the site is built from with the operators' own timetables.

    python3 tools/check_official.py [--site] [--detail OP]

--site compares the runs the site shows (data/metro.json) instead of TDX's timetables.

For every station, direction and kind of day (Monday, Friday, Saturday, Sunday) it counts the
departures in each source and how many agree to the minute, and prints a summary per line, the
worst stations, and the first and last trains that differ. 臺中捷運 publishes no timetable, so
its first and last trains are compared with the runs the site lays out from the headways.
"""
import collections, json, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import official

ROOT = pathlib.Path(__file__).resolve().parent.parent
RAW = ROOT / "raw" / "metro"
WEEK = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
DAYS = {0: "一", 4: "五", 5: "六", 6: "日"}
fmt = lambda m: f"{int(m) // 60 % 24:02d}:{int(m) % 60:02d}" if m is not None else "—"


def network():
    """per operator: the station-ID paths of each line, and the line of each station"""
    d = json.loads((ROOT / "data" / "metro.json").read_text())
    ids = [s[1] for s in d["stations"]]
    paths, line_of = collections.defaultdict(list), {}
    for l in d["lines"]:
        for p in l["paths"]:
            paths[l["op"]].append([ids[i] for i in p])
            for i in p: line_of[(l["op"], ids[i])] = l["name"]
    return paths, line_of


def way(paths, s, d):
    """+1 when a train at s bound for d runs along the paths' order, -1 against it.
    Every line's paths start from the same end (南勢角, 紅樹林 …), so branches share the sign."""
    for p in paths:
        if s in p and d in p and s != d: return 1 if p.index(d) > p.index(s) else -1
    return None


# 台北捷運's 小碧潭 and 新北投 shuttle PDFs cannot be read (official.Unreadable), so those runs are left out
SHUTTLES = {"G03A", "R22A"}      # 台北捷運 codes only (高雄捷運 has an R22A of its own)


def tdx_lists(op):
    """[(sid, dest, direction field, weekday, [minutes])]"""
    out = []
    for r in json.loads((RAW / f"StationTimeTable-{op}.json").read_text()):
        deps = [official.minute(*t["DepartureTime"].split(":")) for t in r["Timetables"]]
        if op == "TRTC" and {r["StationID"], r["DestinationStaionID"]} & SHUTTLES: continue
        for k, w in enumerate(WEEK):
            if r["ServiceDay"].get(w): out.append((r["StationID"], r["DestinationStaionID"], r.get("Direction"), k, deps))
    return out


def compare(rows, tdx, sign_off, sign_tdx):
    """per (station, direction, weekday): official vs TDX counts and matches"""
    off, got = collections.defaultdict(list), collections.defaultdict(list)
    for r in rows:
        for k in DAYS:
            if r["mask"] >> k & 1: off[(r["sid"], sign_off(r), k)] += [t for t, _ in r["deps"]]
    for sid, dest, w, k, deps in tdx:
        if k in DAYS: got[(sid, sign_tdx(sid, dest, w), k)] += deps
    res = []
    for key in off:
        a, b = sorted(off[key]), sorted(got.get(key, []))
        ca, cb = collections.Counter(a), collections.Counter(b)
        res.append({"sid": key[0], "to": key[1], "day": key[2], "off": len(a), "tdx": len(b), "same": sum((ca & cb).values()),
                    "first": (a[0] if a else None, b[0] if b else None), "last": (a[-1] if a else None, b[-1] if b else None)})
    return res


def site_lists(op):
    """the departures of the runs in data/metro.json, in the shape of tdx_lists (direction 0 → paths' order)"""
    d = json.loads((ROOT / "data" / "metro.json").read_text())
    ids = [s[1] for s in d["stations"]]
    out = []
    for t in d["trips"]:
        if d["lines"][t[0]]["op"] != op: continue
        stops, offs = d["patterns"][t[4]], d["offsets"][t[5]]
        if op == "TRTC" and {ids[st] for st in stops} & SHUTTLES: continue
        for k in range(7):
            if not t[7] >> k & 1: continue
            for st, o in list(zip(stops, offs))[:-1]:          # the last stop is an arrival
                out.append((ids[st], None, t[2], k, [round(t[6] + o)]))
    return out


def report(op, name, res, line_of, detail):
    tot = collections.defaultdict(lambda: [0, 0, 0])
    for r in res:
        t = tot[(line_of.get((op, r["sid"]), "?"), r["day"])]
        t[0] += r["off"]; t[1] += r["tdx"]; t[2] += r["same"]
    print(f"\n■ {name}")
    for (line, k), (o, g, s) in sorted(tot.items()):
        print(f"  {line:8s} 週{DAYS[k]}  官方 {o:5d} 班次・TDX {g:5d}・時刻相同 {s:5d}（{100 * s / max(o, 1):5.1f}%）")
    bad = sorted((r for r in res if r["same"] < max(r["off"], r["tdx"])), key=lambda r: r["same"] / max(r["off"], r["tdx"], 1))
    for r in bad[:detail]:
        print(f"    {r['sid']:>4} 往{r['to']} 週{DAYS[r['day']]}: 官方 {r['off']}・TDX {r['tdx']}・相同 {r['same']}  "
              f"首班 {fmt(r['first'][0])}/{fmt(r['first'][1])}  末班 {fmt(r['last'][0])}/{fmt(r['last'][1])}")


def site_first_last(op, lid):
    """{(sid, direction, weekday): (first, last)} departures of the runs in data/metro.json"""
    d = json.loads((ROOT / "data" / "metro.json").read_text())
    ids = [s[1] for s in d["stations"]]
    li = next(i for i, l in enumerate(d["lines"]) if l["op"] == op and l["id"] == lid)
    out = {}
    for t in d["trips"]:
        if t[0] != li: continue
        stops, offs = d["patterns"][t[4]], d["offsets"][t[5]]
        for k in DAYS:
            if not t[7] >> k & 1: continue
            for st, o in list(zip(stops, offs))[:-1]:          # the last stop is an arrival
                key = (ids[st], 1 if t[2] == 0 else -1, k); v = t[6] + o
                a, b = out.get(key, (v, v)); out[key] = (min(a, v), max(b, v))
    return out


def estimated(paths):
    """文湖線 and 臺中捷運 have no timetable: their runs are laid out from headways. Compare their first
    and last trains with 臺中捷運's own table and with 台北捷運's (through TDX FirstLastTimetable,
    which matched the official 六張犁 sheet)"""
    sts = {s["StationName"]["Zh_tw"]: s["StationID"] for s in json.loads((RAW / "Station-TMRT.json").read_text())}
    sts.update({k.removesuffix("站"): v for k, v in list(sts.items())})
    fl, _ = official.tmrt_first_last()
    want = {}
    for (name, toward), v in fl.items():
        s, D = sts[name.removesuffix("站")], sts[toward.removesuffix("站")]
        for k in DAYS: want[("TMRT", s, way(paths["TMRT"], s, D), k)] = v
    for r in json.loads((RAW / "FirstLastTimetable-TRTC.json").read_text()):
        if r["LineID"] != "BR": continue
        for k, w in enumerate(WEEK):
            if k in DAYS and r["ServiceDay"].get(w):
                want[("TRTC", r["StationID"], way(paths["TRTC"], r["StationID"], r["DestinationStaionID"]), k)] = \
                    (official.minute(*r["FirstTrainTime"].split(":")), official.minute(*r["LastTrainTime"].split(":")))
    for op, lid, name in (("TRTC", "BR", "文湖線"), ("TMRT", "G", "臺中捷運綠線")):
        have = site_first_last(op, lid)
        rows = [(k, v, have.get(k[1:])) for k, v in want.items() if k[0] == op]
        off = [(k, v, h) for k, v, h in rows if not h or abs(v[0] - h[0]) > 1 or abs(v[1] - h[1]) > 1]
        print(f"\n■ {name}（推估班次）首末班與官方相差 1 分以上：{len(off)} / {len(rows)}")
        for k, v, h in sorted(off, key=lambda x: (x[0][3], x[0][2], x[0][1]))[:12]:
            print(f"    {k[1]:>4} {'順' if k[2] == 1 else '逆'} 週{DAYS[k[3]]}: 首班 官方 {fmt(v[0])} 系統 {fmt(h and h[0])}  末班 官方 {fmt(v[1])} 系統 {fmt(h and h[1])}")


SITE = "--site" in sys.argv


def main():
    detail = 8 if "--detail" not in sys.argv else 40
    only = sys.argv[sys.argv.index("--detail") + 1] if "--detail" in sys.argv else None
    paths, line_of = network()
    rows = official.load_all()
    for op, name in (("TRTC", "台北捷運"), ("NTMC", "新北捷運環狀線（台北捷運官網）"), ("TYMC", "桃園機場捷運"),
                     ("KRTC", "高雄捷運"), ("KLRT", "高雄環狀輕軌"), ("NTDLRT", "淡海輕軌")):
        mine = [r for r in rows if r["op"] == op]
        if not mine or (only and only != op): continue
        P = paths[op]
        if op == "KLRT":       # a loop: the timetables and TDX both say 順行 0 / 逆行 1
            so, st = (lambda r: r["to"]), (lambda s, d, w: w)
        elif op == "KRTC":     # 上行 (towards 岡山車站, 大寮) is along the paths
            so, st = (lambda r: 1 if r["to"] == 0 else -1), (lambda s, d, w: way(P, s, d))
        else:
            so, st = (lambda r: way(P, r["sid"], r["to"])), (lambda s, d, w: way(P, s, d))
        if SITE:      # what the site shows: the runs rebuilt in data/metro.json
            sw = (lambda s, d, w: w) if op == "KLRT" else (lambda s, d, w: 1 if w == 0 else -1)
            report(op, name + "（網站列車）", compare(mine, site_lists(op), so, sw), line_of, detail)
        else:
            report(op, name, compare(mine, tdx_lists(op), so, st), line_of, detail)
    if not only or only in ("TRTC", "TMRT"): estimated(paths)
    if official.SKIPPED: print("\n未能讀取的官方檔（略過）:", ", ".join(official.SKIPPED))


if __name__ == "__main__":
    main()
