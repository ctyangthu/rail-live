"""Turn the TDX metro open data into train-by-train runs: data/metro.json.

    python3 tools/build_metro.py

Five systems: 台北捷運 TRTC, 新北捷運 NTMC, 桃園機場捷運 TYMC, 臺中捷運 TMRT, 高雄捷運 KRTC.

Lines with station timetables (板南、淡水信義、松山新店、中和新蘆、環狀、三鶯、機場捷運、高雄紅橘線):
TDX publishes, for every station, the departure times towards each terminus. A train is rebuilt by
following one departure down the line: at the next stop it is the departure closest to the expected
running time. Trains of one route never overtake each other, so the matching keeps order.
The terminus has no departure of its own; its arrival is the last departure plus the running time.

Lines with headways only (文湖線、臺中捷運綠線): there is no timetable to rebuild, so runs are laid out
from the first train to the last at the middle of the published headway range of each period, with
the published running times. Those lines are marked est; their times are estimates, not a timetable.
"""
import collections, json, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
RAW = ROOT / "raw" / "metro"
load = lambda n: json.loads((RAW / n).read_text(encoding="utf-8"))
WEEK = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
TOL = 2          # minutes a departure may differ from the expected running time
BRIDGE = 2       # stations with garbled times a run may be carried across
GUESS = 2.0      # minutes between two neighbouring stations that have no published running time or distance
LRT_PACE = 3.2   # minutes per kilometre, stops included, for the light rails without published running times

A_ORDER = [f"A{n}" for n in range(1, 14)] + ["A14a"] + [f"A{n}" for n in range(15, 23)]
KR_ORDER = ["R3", "R4", "R4A"] + [f"R{n}" for n in range(5, 23)] + ["R22A", "R23", "R24", "RK1"]
KO_ORDER = ["O1", "O2"] + [f"O{n}" for n in range(4, 15)] + ["OT1"]
# [operator, line, name, source, fixed station orders (None: the routes of StationOfRoute)]
LINES = [
    ("TRTC", "BR", "文湖線", "freq", None),
    ("TRTC", "R", "淡水信義線", "tt", None),
    ("TRTC", "G", "松山新店線", "tt", None),
    ("TRTC", "O", "中和新蘆線", "tt", None),
    ("TRTC", "BL", "板南線", "tt", None),
    ("NTMC", "Y", "環狀線", "tt", None),
    ("NTMC", "LB", "三鶯線", "tt", None),
    ("NTDLRT", "V", "淡海輕軌", "tt", None),
    ("NTALRT", "K", "安坑輕軌", "tt", None),
    ("TYMC", "A", "桃園機場捷運", "tt", [A_ORDER]),
    ("TMRT", "G", "臺中捷運綠線", "freq", None),
    ("KRTC", "R", "高雄捷運紅線", "tt", [KR_ORDER]),
    ("KRTC", "O", "高雄捷運橘線", "tt", [KO_ORDER]),
    ("KLRT", "C", "高雄環狀輕軌", "tt", None),
]
OPS = sorted({l[0] for l in LINES})


def minute(s):
    h, m = map(int, s.split(":"))
    return h * 60 + m + (1440 if h < 4 else 0)     # after midnight belongs to the service day before


def short(name):
    return name if name.endswith(("車站", "總站")) or not name.endswith("站") else name[:-1]


def mask_of(day):
    return sum(1 << k for k, d in enumerate(WEEK) if day.get(d))


def route_paths(op, lid):
    """the longest station sequences of a line: the trunk first, then each branch"""
    seqs = [[s["StationID"] for s in sorted(r["Stations"], key=lambda s: s["Sequence"])]
            for r in load(f"StationOfRoute-{op}.json") if r["LineID"] == lid and r.get("Direction", 0) == 0]
    seqs.sort(key=len, reverse=True)
    keep = []
    for q in seqs:
        inside = any(any(p[i:i + len(q)] == q for i in range(len(p) - len(q) + 1)) for p in keep)
        if not inside: keep.append(q)
    return keep


def main():
    stations, lines, index = [], [], {}
    for li, (op, lid, name, source, fixed) in enumerate(LINES):
        src = {s["StationID"]: s for s in load(f"Station-{op}.json")}
        paths = fixed or route_paths(op, lid)
        assert paths, f"{op} {lid}: no route"
        for sid in dict.fromkeys(s for p in paths for s in p):
            s = src[sid]
            index[(li, sid)] = len(stations)
            stations.append([li, sid, short(s["StationName"]["Zh_tw"]), (s["StationName"]["En"] or "").replace(" Station", ""),
                             round(s["StationPosition"]["PositionLat"], 5), round(s["StationPosition"]["PositionLon"], 5)])
        lines.append({"id": lid, "op": op, "name": name, "est": source == "freq", "paths": [[index[(li, s)] for s in p] for p in paths], "_ids": paths})

    # running times in minutes: by train type and direction where published, else either way round
    est_k, est_any = {}, {}
    for op in OPS:
        if not (RAW / f"S2STravelTime-{op}.json").exists(): continue     # 淡海 and 安坑 publish none
        for r in load(f"S2STravelTime-{op}.json"):
            tts = sorted(r["TravelTimes"], key=lambda t: t["Sequence"])
            for k, t in enumerate(tts):
                dwell = tts[k + 1]["StopTime"] if op == "KRTC" and k + 1 < len(tts) else 0 if op in ("KRTC", "TYMC") else t.get("StopTime") or 0
                v = (t["RunTime"] + dwell) / 60
                a, b, lid = t["FromStationID"], t["ToStationID"], r.get("LineID")
                key = (op, lid, r.get("TrainType") or 0, a, b)
                est_k[key] = min(v, est_k.get(key, v))      # a loop lists both ways round; the shorter is the ride
                est_any.setdefault((op, lid, a, b), v); est_any.setdefault((op, lid, b, a), v)

    # distances between neighbours, for the lines without running times
    km = {}
    for op in OPS:
        if not (RAW / f"StationOfRoute-{op}.json").exists(): continue
        for r in load(f"StationOfRoute-{op}.json"):
            sts = sorted(r["Stations"], key=lambda s: s["Sequence"])
            for a, b in zip(sts, sts[1:]):
                d = abs((b.get("CumulativeDistance") or 0) - (a.get("CumulativeDistance") or 0))
                if d: km[(op, r["LineID"], a["StationID"], b["StationID"])] = km[(op, r["LineID"], b["StationID"], a["StationID"])] = d

    trips = collections.defaultdict(int)     # (line, kind, dir, path, stops, times) → weekday mask
    stats, missing = collections.Counter(), set()
    updated = []
    for li, (op, lid, name, source, fixed) in enumerate(LINES):
        paths = lines[li]["_ids"]

        def expect(pi, kind, a, b):
            """minutes from leaving a to leaving b"""
            e = est_k.get((op, lid, kind, a, b))
            if e is None: e = est_any.get((op, lid, a, b))
            if e is None:      # not neighbours: add up the stations between
                p = paths[pi]; i, j = p.index(a), p.index(b); step = 1 if j > i else -1
                if abs(i - j) == 1:      # no running time: by distance, else a flat guess
                    if (op, lid, a, b) in km: return km[(op, lid, a, b)] * LRT_PACE
                    missing.add(f"{op} {lid} {a}–{b}"); return GUESS
                e = sum(expect(pi, kind, p[k], p[k + step]) for k in range(i, j, step))
            return e

        if source == "freq":
            assert len(paths) == 1
            path = paths[0]
            first_last = [r for r in load(f"FirstLastTimetable-{op}.json") if r["LineID"] == lid]
            for fr in load(f"Frequency-{op}.json"):
                if fr["LineID"] != lid: continue
                updated.append(fr.get("SrcUpdateTime") or "")
                mask = mask_of(fr["ServiceDay"])
                spans = sorted((minute(h["StartTime"]) if h["StartTime"] != "24:00" else 1440,
                                (minute(h["EndTime"]) if h["EndTime"] not in ("24:00", "00:00") else 1440),
                                (h["MinHeadwayMins"] + h["MaxHeadwayMins"]) / 2) for h in fr["Headways"] if h["MaxHeadwayMins"])
                headway = lambda t: next((hw for a, b, hw in spans if a <= t < b), spans[-1][2] if t >= spans[-1][1] else spans[0][2])
                for direction in (0, 1):
                    seq = path[::-1] if direction else path
                    fl = [r for r in first_last if r["StationID"] == seq[0] and r["DestinationStaionID"] == seq[-1]]
                    fl = [r for r in fl if mask_of(r["ServiceDay"]) & mask] or fl
                    assert fl, f"{op} {lid}: no first/last train at {seq[0]}"
                    t, end = minute(fl[0]["FirstTrainTime"]), minute(fl[0]["LastTrainTime"])
                    if end < t: end += 1440
                    offs = [0.0]
                    for a, b in zip(seq, seq[1:]):
                        e = expect(0, 0, a, b)
                        offs.append(offs[-1] + e)
                    offs = tuple(round(o, 1) for o in offs)
                    stops = tuple(index[(li, s)] for s in seq)
                    while t <= end + 1e-6:
                        trips[(li, 0, direction, 0, stops, tuple(round(t + o, 1) for o in offs))] |= mask
                        stats[f"{op}-{lid} runs"] += 1
                        t += headway(t)
            continue

        groups = collections.defaultdict(lambda: collections.defaultdict(list))
        for r in load(f"StationTimeTable-{op}.json"):
            if r["LineID"] != lid: continue
            updated.append(r["SrcUpdateTime"])
            mask = mask_of(r["ServiceDay"])
            for t in r["Timetables"]:
                g = (mask, r.get("RouteID") or "", r.get("Direction"), r["DestinationStaionID"], t.get("TrainType") or 0, t.get("StoppingPatternID"))
                groups[g][r["StationID"]].append(minute(t["DepartureTime"]))
        for (mask, route, way, dest, kind, pattern), at in groups.items():
            pi = next((k for k, p in enumerate(paths) if dest in p and all(s in p for s in at)), None)
            assert pi is not None, f"{op} {lid} {route}→{dest}: stations on no single path {sorted(at)}"
            if paths[pi][0] == paths[pi][-1]:
                # a loop (高雄環狀輕軌) starts and ends at the same station: the direction comes from the data,
                # and that station's departures are the start of the run
                assert dest == paths[pi][0] and way in (0, 1), (op, lid, dest, way)
                direction, pos = way, {}
                for k, sid in enumerate(paths[pi][::-1] if way else paths[pi]): pos.setdefault(sid, k)
                seq = sorted(at, key=pos.get)
            else:
                pos = {sid: k for k, sid in enumerate(paths[pi])}
                direction = int(pos[next(s for s in at if s != dest)] > pos[dest])
                seq = sorted(at, key=lambda s: pos[s], reverse=bool(direction))
                # a few termini list their arrivals as well; they then close the run instead of an estimate
                assert all(s == dest or (pos[s] < pos[dest]) != bool(direction) for s in seq) and dest not in seq[:-1], (op, lid, dest, seq)

            runs, open_ = [], []
            for k, sid in enumerate(seq):
                times = sorted(at[sid])
                if k == 0:
                    open_ = [[(sid, t)] for t in times]; runs += open_; continue
                # near the published running time, the gap that carries the most departures on to this stop.
                # Only near it: with even headways a gap one headway longer fits just as many departures.
                have, about = set(times), round(expect(pi, kind, seq[k - 1], sid))
                e = max(range(max(1, about - 2), about + 3), key=lambda g: (sum(r[-1][1] + g in have for r in open_), -abs(g - about), -g))
                # first the trains that keep that time to the minute, then the ones held a little longer
                # (機捷 commuter trains wait at A8 for the express to pass); order is kept in both passes
                # A station whose published times are garbled (淡海輕軌 on holidays has a few) must not cut a train
                # in two: a run with no match stays open for up to BRIDGE stations and is aimed at the next ones
                # by the running time from its last good stop; the stops it missed are filled in between.
                at_k = {s_: n for n, s_ in enumerate(seq)}
                aim = {id(r): r[-1][1] + (e if r[-1][0] == seq[k - 1] else round(expect(pi, kind, r[-1][0], sid))) for r in open_}
                order_ = sorted(open_, key=lambda r: aim[id(r)])
                taken, nxt, matched = set(), [], set()
                for lo, hi in ((-1, 1), (-TOL, 8)):
                    i = 0
                    for r in order_:
                        if id(r) in matched: continue
                        target = aim[id(r)]
                        while i < len(times) and (times[i] < target + lo or i in taken): i += 1
                        if i < len(times) and times[i] <= target + hi:
                            j0, t0 = at_k[r[-1][0]], r[-1][1]
                            if k - j0 > 1:      # fill the stops in between, spaced by their running times
                                parts = [expect(pi, kind, seq[n], seq[n + 1]) for n in range(j0, k)]
                                acc = 0
                                for n in range(j0 + 1, k):
                                    acc += parts[n - j0 - 1]
                                    r.append((seq[n], t0 + max(1, min(times[i] - t0 - 1, round((times[i] - t0) * acc / sum(parts))))))
                                stats[f"{op}-{lid} stops filled in"] += k - j0 - 1
                            r.append((sid, times[i])); taken.add(i); matched.add(id(r)); nxt.append(r); i += 1
                for r in open_:
                    if id(r) in matched: continue
                    if k - at_k[r[-1][0]] < BRIDGE + 1 and k < len(seq) - 1: nxt.append(r)      # still open
                    else: stats[f"{op}-{lid} ends early"] += 1
                for i, t in enumerate(times):
                    if i not in taken: nxt.append([(sid, t)]); runs.append(nxt[-1])
                open_ = sorted(nxt, key=lambda r: r[-1][1])
            for r in runs:
                if r[-1][0] == seq[-1] and (seq[-1] != dest or paths[pi][0] == paths[pi][-1]):
                    r.append((dest, r[-1][1] + max(1, round(expect(pi, kind, seq[-1], dest)))))
                if len(r) < 2: stats[f"{op}-{lid} single stop"] += 1; continue
                if r[0][0] != seq[0]: stats[f"{op}-{lid} starts mid-line"] += 1
                stops = tuple(index[(li, s)] for s, _ in r)
                trips[(li, kind, direction, pi, stops, tuple(t for _, t in r))] |= mask
                stats[f"{op}-{lid} runs"] += 1

    patterns, offsets, out = {}, {}, []
    for (li, kind, direction, pi, stops, times), mask in sorted(trips.items(), key=lambda kv: (kv[0][0], kv[0][5][0])):
        p = patterns.setdefault(stops, len(patterns))
        o = offsets.setdefault(tuple(round(t - times[0], 1) for t in times), len(offsets))
        out.append([li, kind, direction, pi, p, o, times[0], mask])
    for l in lines: del l["_ids"]
    num = lambda v: int(v) if float(v).is_integer() else v
    data = {"updated": max(updated)[:10], "lines": lines, "stations": stations,
            "patterns": [list(p) for p in patterns], "offsets": [[num(v) for v in o] for o in offsets],
            "trips": [t[:6] + [num(t[6]), t[7]] for t in out]}
    (ROOT / "data" / "metro.json").write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    per_day = collections.Counter()
    for li, kind, direction, pi, p, o, t0, mask in out:
        for d in (0, 5, 6):
            if mask >> d & 1: per_day[(LINES[li][0] + "-" + lines[li]["id"], "一二三四五六日"[d])] += 1
    print(f"data/metro.json: {len(stations)} stations, {len(out)} runs, {len(patterns)} stop patterns, {len(offsets)} timings")
    print("runs per day:", {f"{l}{d}": n for (l, d), n in sorted(per_day.items())})
    print("checks:", dict(sorted(stats.items())))
    if missing: print(f"no published running time, {GUESS} min assumed:", sorted(missing))


if __name__ == "__main__":
    main()
