"""Read the operators' own timetables in raw/official/ (tools/fetch_official.py) into one list.

    from official import load_all
    rows = load_all()     # [{op, sid, to, mask, deps: [(minute, kind)], src}]

op      the TDX operator code (TRTC, NTMC, TYMC, KRTC, KLRT, NTDLRT)
sid     the TDX station ID the departures are from
to      the direction: a terminus station ID ("BL23"), or 0/1 where only a direction is given
mask    the weekdays the list applies to, bit 0 = Monday … bit 6 = Sunday
deps    departures in minutes after midnight of the service day (00:30 is 1470), with the train
        type where the timetable gives one (機場捷運: express, commuter …; else "")
"""
import html, json, pathlib, re, zipfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
RAW = ROOT / "raw" / "official"
WEEKDAYS, MON_THU, FRI, SAT, SUN, WEEKEND = 0b0011111, 0b0001111, 0b0010000, 0b0100000, 0b1000000, 0b1100000


def minute(h, m):
    h, m = int(h), int(m)
    return h * 60 + m + (1440 if h < 4 else 0)     # 00:15 and 24:15 both belong to the day before


def text_of(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


# ── 台北捷運 (and 環狀線): one PDF per station and direction, three columns of days ──
def day_mask(label):
    if re.search(r"週一至週五|平常日|Weekdays", label): return WEEKDAYS
    if re.search(r"週六.*週日|例假日|Saturday.*Sunday", label): return WEEKEND
    if re.search(r"週日|Sunday", label): return SUN
    if re.search(r"週六|Saturday", label): return SAT
    raise ValueError(label)


class Unreadable(Exception):
    """the 小碧潭 and 新北投 shuttle PDFs: one has no text, the other's columns run together"""


def trtc_pdf(path):
    """[(mask, [minutes])] by column; the PDF's text keeps its layout, so columns are cut by position"""
    import pypdf
    lines = pypdf.PdfReader(path).pages[0].extract_text(extraction_mode="layout").split("\n")
    head = next((k for k, l in enumerate(lines) if l.lstrip().startswith("Hour") or l.lstrip().startswith("時")), None)
    starts = [m.start() for m in re.finditer(r"Hour|時\s*Hour", lines[head])] if head is not None else []
    if len(starts) < 2 or "分Hour" in lines[head]: raise Unreadable(path.name)
    labels = ["" for _ in starts]
    for l in lines[max(0, head - 4):head]:
        for k, x in enumerate(starts):
            labels[k] += l[x:starts[k + 1] if k + 1 < len(starts) else None]
    if not "".join(labels).strip(): labels = [" ".join(lines[max(0, head - 4):head])] * len(starts)
    cols = [[] for _ in starts]
    hour = [None] * len(starts)
    for l in lines[head + 1:]:
        if re.search(r"註|Note|生效", l): break
        for m in re.finditer(r"\d\d", l):
            k = max(i for i, x in enumerate(starts) if x <= m.start() + 2) if m.start() + 2 >= starts[0] else 0
            v = m.group(0)
            if abs(m.start() - starts[k]) <= 2: hour[k] = int(v)          # the hour column
            elif hour[k] is not None: cols[k].append(minute(hour[k], v))
    return [(day_mask(lab), sorted(c)) for lab, c in zip(labels, cols) if c]


def trtc():
    rows = []
    d = RAW / "trtc"
    for info in sorted(d.glob("info-*.json")):
        for r in json.loads(info.read_text()):
            f = r.get("FileName")
            if not f or not (d / f).exists(): continue
            to = re.match(r"往\s*([A-Z]+\d+A?)", r["Direction"]).group(1)
            # a transfer station carries every line's code ("G16 BR11"); keep the one on the PDF's line
            line = re.match(r"[A-Z]+", to).group(0)
            sid = next(c for c in r["StationLabel"].split() if re.match(r"[A-Z]+", c).group(0) == line)
            op = "NTMC" if line == "Y" else "TRTC"
            try: cols = trtc_pdf(d / f)
            except Unreadable: SKIPPED.append(f); continue
            for mask, deps in cols:
                rows.append({"op": op, "sid": sid, "to": to, "mask": mask, "deps": [(t, "") for t in deps], "src": f})
    return rows


# ── 高雄捷運 and 高雄輕軌: HTML tables, one tab per direction ──
def krtc_tables(page):
    """[(direction label, [minutes])]; a transfer station (美麗島) has a block of tabs per line,
    and the blocks reuse the same tab ids"""
    out = []
    for block in re.split(r'<div id="jQTab\d+"', page)[1:]:
        for tid, label in re.findall(r'<a href="#(tabs-\d+)">\s*<strong>(.*?)</strong>', block, flags=re.S):
            i = block.find(f'<div id="{tid}">'); j = block.find('<div id="tabs-', i + 10)
            seg = block[i:j if j > 0 else None]
            deps = []
            for h, cell in re.findall(r"<th>(\d+)時</th>\s*<td>(.*?)</td>", seg, flags=re.S):
                deps += [minute(h, m) for m in re.findall(r"<span[^>]*>\s*(\d\d)\s*</span>", cell)]
            out.append((text_of(label), sorted(deps)))
    return out


def krtc():
    days = {"wk": MON_THU, "fri": FRI, "sat": SAT, "sun": SUN}
    rows = []
    for p in sorted((RAW / "krtc").glob("tt-*.html")):
        tag, sid = p.stem.split("-")[1:]
        for label, deps in krtc_tables(p.read_text(encoding="utf-8")):
            to = 0 if label.startswith("上行") else 1 if label.startswith("下行") else label
            line = "O" if re.search("大寮|哈瑪星", label) else "R"
            here = {("R10", "O"): "O5", ("O5", "R"): "R10"}.get((sid, line), sid)     # 美麗島 lists both lines
            rows.append({"op": "KRTC", "sid": here, "to": to, "label": label, "mask": days[tag], "deps": [(t, "") for t in deps], "src": p.name})
    return rows


def klrt():
    days = {"wk": WEEKDAYS, "hol": WEEKEND}
    rows = []
    for p in sorted((RAW / "klrt").glob("tt-*.html")):
        tag, sid = p.stem.split("-")[1:]
        for label, deps in krtc_tables(p.read_text(encoding="utf-8")):
            to = 0 if label.startswith("順行") else 1 if label.startswith("逆行") else label
            rows.append({"op": "KLRT", "sid": sid, "to": to, "mask": days[tag], "deps": [(t, "") for t in deps], "src": p.name})
    return rows


# ── 桃園機場捷運: an HTML table per direction, every departure labelled with its train type ──
TYMC_KIND = [("尖峰增停直達", "express+"), ("直達", "express"), ("跳站", "skip"), ("增開往機場", "airport"), ("普通", "commuter")]


def tymc():
    days = {"mon": MON_THU, "fri": FRI, "sat": SAT, "sun": SUN}
    rows = []
    for p in sorted((RAW / "tymc").glob("tt-*.html")):
        tag, sid = p.stem.split("-")[1:]
        page = p.read_text(encoding="utf-8")
        seen = set()
        for summary, table in re.findall(r'<table[^>]*summary="桃園捷運列車時刻表:([^"]*)"[^>]*class="time-table"[^>]*>(.*?)</table>', page, flags=re.S):
            if summary in seen or summary == "-": continue     # the page repeats each table for phones
            seen.add(summary)
            deps = []
            for h, m, kind in re.findall(r'(\d\d)點</div>\s*<span[^>]*><i>(\d\d)</i></span>\s*<div[^>]*>([^<]*)</div>', table):
                deps.append((minute(h, m), next((k for w, k in TYMC_KIND if w in kind), kind)))
            to = "A1" if "台北" in summary else "A22"
            rows.append({"op": "TYMC", "sid": sid, "to": to, "label": summary, "mask": days[tag], "deps": sorted(deps), "src": p.name})
    return rows


# ── 淡海輕軌: an .odt per station, departures listed by destination ──
def ntdlrt():
    names = {s["StationName"]["Zh_tw"]: s["StationID"] for s in json.loads((ROOT / "raw" / "metro" / "Station-NTDLRT.json").read_text())}
    rows = []
    for p in sorted((RAW / "ntdlrt").glob("V*.odt")):
        xml = zipfile.ZipFile(p).read("content.xml").decode("utf-8")
        text = re.sub(r"<[^>]+>", "", re.sub(r"</text:p>", "\n", xml))
        mask, got = None, {}
        for line in text.split("\n"):
            line = line.strip()
            if "時：" not in line and "時:" not in line:      # a heading: "1月台往崁頂及淡水漁人碼頭站平常日"
                if "平常日" in line: mask = WEEKDAYS
                elif re.search("週六|假日", line): mask = WEEKEND
                continue
            m = re.match(r"^(\d+)時[：:](.*)$", line)
            if not m or mask is None: continue
            for mins, dest in re.findall(r"([\d、]+)分往(\S+?)站", m.group(2)):
                to = names.get(dest) or names.get(dest + "站") or dest
                got.setdefault((mask, to), []).extend(minute(m.group(1), x) for x in mins.split("、") if x)
        for (mask, to), deps in got.items():
            rows.append({"op": "NTDLRT", "sid": p.stem, "to": to, "mask": mask, "deps": [(t, "") for t in sorted(deps)], "src": p.name})
    return rows


# ── 臺中捷運: first and last trains only ──
def tmrt_first_last():
    """{(station name, toward name): (first, last)} and the headway text"""
    t = text_of(re.sub(r"<script.*?</script>|<style.*?</style>", "", (RAW / "tmrt" / "first-last-train.html").read_text(encoding="utf-8"), flags=re.S))
    i = t.index("首班車 末班車 首班車 末班車") + len("首班車 末班車 首班車 末班車"); j = t.index("班距", i)
    body = t[i:j]
    out = {}
    for name, times in re.findall(r"(\D+?)\s+((?:\d\d:\d\d\s*){2,4})", body):
        v = [minute(*x.split(":")) for x in times.split()]
        name = name.strip()
        if len(v) == 4: out[(name, "北屯總站")] = (v[0], v[1]); out[(name, "高鐵臺中站")] = (v[2], v[3])
        elif name.startswith("北屯"): out[(name, "高鐵臺中站")] = (v[0], v[1])
        else: out[(name, "北屯總站")] = (v[0], v[1])
    return out, t[j:t.index("功能選單", j)]


SKIPPED = []


def load_all():
    rows = []
    for f in (trtc, krtc, klrt, tymc, ntdlrt):
        if (RAW / f.__name__).exists(): rows += f()
    return rows


if __name__ == "__main__":
    import collections
    rows = load_all()
    print(collections.Counter((r["op"], r["mask"]) for r in rows))
    print(sum(len(r["deps"]) for r in rows), "departures")
