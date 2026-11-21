"""Turn the TDX metro open data into train-by-train runs: data/metro.json.

    python3 tools/build_metro.py

Five systems: 台北捷運 TRTC, 新北捷運 NTMC, 桃園機場捷運 TYMC, 臺中捷運 TMRT, 高雄捷運 KRTC.

Lines with station timetables (板南、淡水信義、松山新店、中和新蘆、環狀、三鶯、機場捷運、高雄紅橘線):
TDX publishes, for every station, the departure times towards each terminus. A train is rebuilt by
following one departure down the line: at the next stop it is the departure closest to the expected
running time. Trains of one route never overtake each other, so the matching keeps order.
The terminus has no departure of its own; its arrival is the last departure plus the running time.

Where the operator's own timetable differs from TDX (tools/check_official.py), the operator's is used:
淡海輕軌's whole timetable (TDX still has an older one).

Lines with headways only (文湖線、臺中捷運綠線): there is no timetable to rebuild, so runs are laid out
from the first train to the last at the middle of the published headway range of each period, with
the published running times. Every station's own first and last departures are then matched: the
first trains of the day start from several stations at once, and late trains start mid-line, so a
run is added from any station whose first (or last) departure the runs from the terminus miss.
Those lines are marked est; their times are estimates, not a timetable.
"""
import collections, json, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import official

ROOT = pathlib.Path(__file__).resolve().parent.parent
RAW = ROOT / "raw" / "metro"
load = lambda n: json.loads((RAW / n).read_text(encoding="utf-8"))
WEEK = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
TOL = 2          # minutes a departure may differ from the expected running time
BRIDGE = 2       # stations with garbled times a run may be carried across
NO_FILL = {"TYMC"}
BRIDGE_OF = {"TYMC": 7}   # 機場捷運's 尖峰跳站普通車 run non-stop from A18 to A13
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


# 臺中捷運's own headways (www.tmrt.com.tw/metro-life/first-last-train, read 2026-11-21): peak 5–8,
# off-peak 8–10, after 23:00 10–20 minutes; TDX's Frequency is from 2024. [start, end, minutes]
TMRT_HEADWAYS = {0b0011111: [(360, 420, 9), (420, 540, 6.5), (540, 1020, 9), (1020, 1140, 6.5), (1140, 1380, 9), (1380, 1500, 15)],
                 0b1100000: [(360, 600, 9), (600, 1200, 6.5), (1200, 1380, 9), (1380, 1500, 15)]}
OFF = official.load_all() if (ROOT / "raw" / "official").exists() else []
DOW = lambda mask: {w: bool(mask >> k & 1) for k, w in enumerate(WEEK)}
hhmm = lambda m: f"{int(m) // 60 % 24:02d}:{int(m) % 60:02d}"


def record(lid, sid, route, way, dest, mask, deps, src="official"):
    """a departure list in the shape of a TDX StationTimeTable row"""
    return {"LineID": lid, "StationID": sid, "RouteID": route, "Direction": way, "DestinationStaionID": dest,
            "ServiceDay": DOW(mask), "Timetables": [{"DepartureTime": hhmm(t)} for t in sorted(deps)], "SrcUpdateTime": src}


def relabel(order, lists, labels, gap_max=8):
    """Carry each train's label (its branch) down a shared stretch of line. order: stations in running
    order; lists[s]: departures; labels[s]: their labels where known (the first station, branch stations).
    At each station the shift that lines up the most departures with the station before is taken,
    and every departure gets the label of the nearest one before it."""
    out = {order[0]: labels[order[0]]}
    for a, b in zip(order, order[1:]):
        if b in labels and len(set(labels[b])) == 1 and labels[b][0] is not None and b not in out:
            out[b] = labels[b]; continue
        prev = sorted(zip(lists[a], out[a]))
        have = set(lists[b])
        g = max(range(1, gap_max + 1), key=lambda g: sum(t + g in have for t, _ in prev))
        lab = []
        for t in lists[b]:
            near = min(prev, key=lambda x: abs(x[0] + g - t)) if prev else (t, None)
            lab.append(near[1] if abs(near[0] + g - t) <= 3 else (labels.get(b) or [None] * len(lists[b]))[lists[b].index(t)])
        out[b] = lab
    return out


def ntdlrt_records(rows, paths):
    """淡海輕軌 from its own timetables. They name each departure's terminus, but at some trunk stations
    trains for 淡水漁人碼頭 are listed as 往崁頂, so the branch is carried down from 紅樹林 (outbound) and
    from the two branches (inbound) by matching times station to station."""
    # A station whose list does not follow from the station before it (most departures cannot be reached
    # with one running time) carries an old timetable: 台北海洋大學 往淡水漁人碼頭 on weekends still had the
    # 2025 one in 2026-11. It is left out and the runs carry across it.
    def fits(a, b):
        have = set(b)
        return max(sum(t + g in have for t in a) for g in range(1, 13)) / max(len(b), 1)
    dropped, keep = set(), []
    for way in (0, 1):      # in running order, so a dropped station is stepped over by the next one
        for r in sorted((r for r in rows if (r["to"] == paths[0][0]) == bool(way)),
                        key=lambda r: min(q.index(r["sid"]) for q in paths if r["sid"] in q) * (-1 if way else 1)):
            prevs = set()
            for q in paths:
                if r["sid"] not in q or (not way and r["to"] not in q and r["to"] != q[-1]): continue
                k, step = q.index(r["sid"]), (1 if way else -1)
                j = k + step
                while 0 <= j < len(q) and (q[j], way, r["mask"]) in dropped: j += step
                if 0 <= j < len(q): prevs.add(q[j])
            before = [t for x in rows if x["sid"] in prevs and x["mask"] == r["mask"] and (x["to"] == paths[0][0]) == bool(way)
                      and (x["sid"], way, x["mask"]) not in dropped for t, _ in x["deps"]]
            if before and fits(before, [t for t, _ in r["deps"]]) < 0.5:
                dropped.add((r["sid"], way, r["mask"]))
                # in its place: the station before's trains for the same terminus, a running time later
                # (the shift that fits best on the other kind of day)
                src = [x for x in rows if x["sid"] in prevs and x["mask"] == r["mask"] and x["to"] == r["to"]]
                other = [x for x in rows if x["sid"] == r["sid"] and x["to"] == r["to"] and x["mask"] != r["mask"]]
                ref = [x for x in rows if x["sid"] in prevs and x["to"] == r["to"] and other and x["mask"] == other[0]["mask"]]
                if src and other and ref:
                    a_, b_ = [t for t, _ in ref[0]["deps"]], set(t for t, _ in other[0]["deps"])
                    g = max(range(1, 13), key=lambda g: sum(t + g in b_ for t in a_))
                    keep.append({**r, "deps": [(t + g, "") for t, _ in src[0]["deps"]], "src": "derived"})
                    print(f"  淡海輕軌 {r['sid']} 往{r['to']} ({r['mask']:07b}): does not follow from {'/'.join(sorted(prevs))}; "
                          f"replaced by {src[0]['sid']}'s times + {g} min")
                else:
                    print(f"  淡海輕軌 {r['sid']} 往{r['to']} ({r['mask']:07b}): does not follow from {'/'.join(sorted(prevs))}, left out")
                continue
            keep.append(r)
    rows = keep
    branch_of = lambda s: next(k for k, p in enumerate(paths) if s in p and not all(s in q for q in paths))
    trunk = [s for s in paths[0] if all(s in q for q in paths)]
    recs = []
    for mask in sorted({r["mask"] for r in rows}):
        mine = [r for r in rows if r["mask"] == mask]
        for way in (0, 1):
            lists, labels = collections.defaultdict(list), collections.defaultdict(list)
            for r in mine:
                s, to = r["sid"], r["to"]
                if (to == paths[0][0]) != bool(way): continue          # inbound trains all run to 紅樹林
                for t, _ in r["deps"]:
                    lists[s].append(t)
                    labels[s].append(branch_of(to) if not way else (branch_of(s) if s not in trunk else None))
            for s in lists:      # keep each station's departures in time order with their labels
                pairs = sorted(zip(lists[s], labels[s])); lists[s] = [t for t, _ in pairs]; labels[s] = [l for _, l in pairs]
            if not way:
                lab = {**labels, **relabel(trunk, lists, labels)}      # branch stations keep their own
            else:
                # inbound: the trunk's first station after the junction takes labels from both branches
                junction = trunk[-1]
                feeders = {k: [s for s in paths[k][::-1] if s not in trunk] for k in range(len(paths))}
                lab = {}
                for k, f in feeders.items():
                    for s in f: lab[s] = [k] * len(lists[s])
                prev = [(t, k) for k, f in feeders.items() if f for t in lists[f[-1]]]
                merged = {"_": sorted(prev)}
                lists["_"] = [t for t, _ in merged["_"]]; lab["_"] = [k for _, k in merged["_"]]
                order = ["_"] + trunk[::-1]
                lab.update(relabel(order, lists, {**labels, "_": lab["_"]}))
                del lists["_"], lab["_"]
            for s in lists:
                if way and s in trunk:      # an inbound train that starts on the trunk can take either branch's path
                    lab[s] = [0 if l is None else l for l in lab[s]]
                for k in set(lab[s]) - {None}:
                    deps = [t for t, l in zip(lists[s], lab[s]) if l == k]
                    dest = paths[k][-1] if not way else paths[0][0]
                    if s == dest: continue
                    recs.append(record("V", s, f"V-{k + 1}", way, dest, mask, deps))
                lost = sum(l is None for l in lab[s])
                if lost: print(f"  淡海輕軌 {s} {'inbound' if way else 'outbound'}: {lost} departures with no branch, left out")
    return recs


def timetables(op, paths_of):
    """TDX's station timetables, corrected with the operator's own where they differ"""
    recs = load(f"StationTimeTable-{op}.json")
    mine = [r for r in OFF if r["op"] == op]
    if op == "NTDLRT" and mine:
        recs = ntdlrt_records(mine, paths_of("V"))
    return recs


def first_last(op, lid, path):
    """{(station, direction): (first, last)}: 臺中捷運 from its own page, 文湖線 from TDX
    (台北捷運's own sheets are images; the 六張犁 one matched TDX to the minute)"""
    out = {}
    if op == "TMRT" and (ROOT / "raw" / "official" / "tmrt").exists():
        ids = {short(s["StationName"]["Zh_tw"]).removesuffix("站"): s["StationID"] for s in load("Station-TMRT.json")}
        fl, _ = official.tmrt_first_last()
        for (name, toward), v in fl.items():
            s, d = ids[name.removesuffix("站")], ids[toward.removesuffix("站")]
            out[(s, int(path.index(d) < path.index(s)))] = v
        return out
    for r in load(f"FirstLastTimetable-{op}.json"):
        if r["LineID"] != lid or r["StationID"] == r["DestinationStaionID"]: continue
        s, d = r["StationID"], r["DestinationStaionID"]
        out[(s, int(path.index(d) < path.index(s)))] = (minute(r["FirstTrainTime"]), minute(r["LastTrainTime"]))
    return out


def layout(seq, fl, direction, headway, expect):
    """runs along seq: from the terminus every headway between its first and last train, then a run
    from every station whose own first or last departure those runs miss. A run keeps to the
    station's published first/last time where that is a plausible ride from the stop before."""
    first = {s: fl[(s, direction)][0] for s in seq[:-1] if (s, direction) in fl}
    last = {s: fl[(s, direction)][1] for s in seq[:-1] if (s, direction) in fl}
    def run(k, t, keep):
        times = [t]
        for a, b in zip(seq[k:], seq[k + 1:]):
            e = expect(a, b); want = keep.get(b)
            ok = want is not None and 0.5 * e <= want - times[-1] <= e + 3
            times.append(want if ok else times[-1] + e)
        return (k, tuple(round(x, 1) for x in times))
    t0, t1 = first[seq[0]], last[seq[0]]
    runs, t = [], t0
    while t < t1 - headway(t) / 2:
        runs.append(run(0, t, first if t == t0 else {})); t += headway(t)
    runs.append(run(0, t1, last))
    for k, s in enumerate(seq[1:-1], 1):
        at = [r[1][k - r[0]] for r in runs if r[0] <= k]
        if s in first and first[s] < min(at) - 1: runs.append(run(k, first[s], first))
        if s in last and last[s] > max(at) + 1: runs.append(run(k, last[s], last))
    return runs


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
            fl = first_last(op, lid, path)
            if op == "TMRT":
                plans = [(mask, sorted(v)) for mask, v in TMRT_HEADWAYS.items()]
                updated.append("2026-11-21")
            else:
                plans = []
                for fr in load(f"Frequency-{op}.json"):
                    if fr["LineID"] != lid: continue
                    updated.append(fr.get("SrcUpdateTime") or "")
                    plans.append((mask_of(fr["ServiceDay"]), sorted((minute(h["StartTime"]) if h["StartTime"] != "24:00" else 1440,
                                  (minute(h["EndTime"]) if h["EndTime"] not in ("24:00", "00:00") else 1440),
                                  (h["MinHeadwayMins"] + h["MaxHeadwayMins"]) / 2) for h in fr["Headways"] if h["MaxHeadwayMins"])))
            for mask, spans in plans:
                headway = lambda t, spans=spans: next((hw for a, b, hw in spans if a <= t < b), spans[-1][2] if t >= spans[-1][1] else spans[0][2])
                for direction in (0, 1):
                    seq = path[::-1] if direction else path
                    for k, times in layout(seq, fl, direction, headway, lambda a, b: expect(0, 0, a, b)):
                        stops = tuple(index[(li, s)] for s in seq[k:])
                        trips[(li, 0, direction, 0, stops, times)] |= mask
                        stats[f"{op}-{lid} runs"] += 1
                        if k: stats[f"{op}-{lid} starts mid-line"] += 1
            continue

        groups = collections.defaultdict(lambda: collections.defaultdict(list))
        for r in timetables(op, lambda l: lines[next(i for i, x in enumerate(LINES) if x[0] == op and x[1] == l)]["_ids"]):
            if r["LineID"] != lid: continue
            if r["SrcUpdateTime"] != "official": updated.append(r["SrcUpdateTime"])
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
                            # fill the stops in between, spaced by their running times; not on 機場捷運, whose
                            # 尖峰跳站普通車 really do pass A20 and A19 (and its express trains pass most stations)
                            if k - j0 > 1 and op not in NO_FILL:
                                parts = [expect(pi, kind, seq[n], seq[n + 1]) for n in range(j0, k)]
                                acc = 0
                                for n in range(j0 + 1, k):
                                    acc += parts[n - j0 - 1]
                                    r.append((seq[n], t0 + max(1, min(times[i] - t0 - 1, round((times[i] - t0) * acc / sum(parts))))))
                                stats[f"{op}-{lid} stops filled in"] += k - j0 - 1
                            r.append((sid, times[i])); taken.add(i); matched.add(id(r)); nxt.append(r); i += 1
                for r in open_:
                    if id(r) in matched: continue
                    if k - at_k[r[-1][0]] < BRIDGE_OF.get(op, BRIDGE) + 1 and k < len(seq) - 1: nxt.append(r)      # still open
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
