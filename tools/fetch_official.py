"""Download the operators' own timetables and first/last train tables into raw/official/.

    python3 tools/fetch_official.py [trtc tymc krtc klrt tmrt ntdlrt]

These are the sources the TDX data are checked against (tools/check_official.py):
  trtc    台北捷運 (also 環狀線): every station's timetable PDF, one per direction, with weekday,
          Saturday and Sunday columns            web.metro.taipei/apis/metrostationapi + /img/ALL/timetables/
  tymc    桃園機場捷運: each station's timetable (train type marked) for a coming Monday, Friday,
          Saturday and Sunday, and its first and last trains
                                                 www.tymetro.com.tw/.../travel-guide/timetable-A1, dep-A1 …
  krtc    高雄捷運紅線、橘線: each station's timetable for 平常日, 假日前一日, 週六, 週日, and its first
          and last trains                         www.krtc.com.tw/Guide/train_times, first_and_last_train
  klrt    高雄環狀輕軌: each station's timetable for 平常日 and 假日, and its first and last trains
                                                 www.krtc.com.tw/KLRT/train_timesLRT, first_and_last_train
  tmrt    臺中捷運: one page with every station's first and last trains and the headways
                                                 www.tmrt.com.tw/metro-life/first-last-train
  ntdlrt  淡海輕軌: every station's timetable (.odt)  www.ntmetro.com.tw/basic/?mode=detail&node=447…460
新北捷運 publishes nothing machine-readable for 環狀線 (台北捷運 does), 安坑輕軌 or 三鶯線.
Files already downloaded are kept; delete raw/official/<name>/ to refresh. Requests are spaced out.
"""
import datetime, html, http.cookiejar, json, pathlib, re, sys, time, urllib.parse, urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "raw" / "official"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"}
PAUSE = 0.6


OPENER = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))


def get(url, data=None, json_body=None):
    headers = dict(UA)
    if json_body is not None:
        data = json.dumps(json_body).encode(); headers["Content-Type"] = "application/json"
    elif isinstance(data, dict):
        data = urllib.parse.urlencode(data).encode(); headers["Content-Type"] = "application/x-www-form-urlencoded"
    req = urllib.request.Request(url, data=data, headers=headers)
    with OPENER.open(req, timeout=60) as r: body = r.read()
    time.sleep(PAUSE)
    return body


def save(path, fetch):
    if path.exists() and path.stat().st_size: return path.read_bytes()
    path.parent.mkdir(parents=True, exist_ok=True)
    body = fetch(); path.write_bytes(body); print(f"  {path.relative_to(ROOT)} {len(body) / 1024:.0f} KB", flush=True)
    return body


def trtc():
    api = "https://web.metro.taipei/apis/metrostationapi/"
    d = OUT / "trtc"
    menu = json.loads(save(d / "menuline.json", lambda: get(api + "menuline", json_body={"LineID": "0", "Lang": "tw"})))
    sids = sorted({s["SID"] for l in menu for s in l["LineStations"]})
    files = []
    for sid in sids:
        info = json.loads(save(d / f"info-{sid}.json", lambda: get(api + "timetableinfo", json_body={"SID": sid, "Lang": "tw"})))
        files += [i["FileName"] for i in info if i.get("FileName")]
    for f in sorted(set(files)):
        save(d / f, lambda: get("https://web.metro.taipei/img/ALL/timetables/" + urllib.parse.quote(f)))


def next_day(weekday):
    """the next date (from tomorrow) falling on weekday, Monday = 0"""
    d = datetime.date.today() + datetime.timedelta(days=1)
    while d.weekday() != weekday: d += datetime.timedelta(days=1)
    return d.isoformat()


# 桃園機場捷運 shows the timetable of a date kept in the session; one sample date per kind of day
TYMC_DAYS = {"mon": 0, "fri": 4, "sat": 5, "sun": 6}


def tymc():
    base = "https://www.tymetro.com.tw/tymetro-new/tw/_pages/travel-guide/"
    page = save(OUT / "tymc" / "departure.html", lambda: get(base + "departure.html")).decode("utf-8", "replace")
    sids = list(dict.fromkeys(re.findall(r'<option value="(A\d+a?)"', page)))
    for sid in sids:
        save(OUT / "tymc" / f"dep-{sid}.html", lambda: get(base + "dep-" + sid))
    for tag, wd in TYMC_DAYS.items():
        day = next_day(wd)
        if all((OUT / "tymc" / f"tt-{tag}-{sid}.html").exists() for sid in sids): continue
        for sid in sids:
            path = OUT / "tymc" / f"tt-{tag}-{sid}.html"
            if path.exists(): continue
            for _ in range(3):      # the date sits in the session and is sometimes lost: set it for every page
                get(base + "station-timetable-date.php", data={"date": day})
                body = get(base + "timetable-" + sid)
                if f'value="{day}"' in body.decode("utf-8", "replace"): break
            else: raise SystemExit(f"{sid}: the page did not take the date {day}")
            save(path, lambda: body)


# 高雄捷運: 平常日 (Monday–Thursday), 假日前一日 (Friday), 週六, 週日; 高雄輕軌: 平常日, 假日
KRTC_DAYS = {"wk": "train_times", "fri": "train_times_before_holiday", "sat": "train_times_holiday", "sun": "train_times_sunday"}
KLRT_DAYS = {"wk": "train_timesLRT", "hol": "train_timesLRT_holiday"}


def krtc():
    for line in ("R", "O"):
        opts = save(OUT / "krtc" / f"line-{line}.html", lambda: get("https://www.krtc.com.tw/Home/GetLineList?id=" + line)).decode("utf-8")
        for sid in re.findall(r'value="(\w+)"', opts):
            if not sid: continue
            save(OUT / "krtc" / f"fl-{sid}.html", lambda: get(f"https://www.krtc.com.tw/Guide/first_and_last_train?KRTCSLLine={line}&KRTCStation={sid}"))
            for tag, path in KRTC_DAYS.items():
                save(OUT / "krtc" / f"tt-{tag}-{sid}.html", lambda: get(f"https://www.krtc.com.tw/Guide/{path}?n={sid}"))


def klrt():
    page = save(OUT / "klrt" / "index.html", lambda: get("https://www.krtc.com.tw/KLRT/first_and_last_train")).decode("utf-8")
    for sid in dict.fromkeys(re.findall(r'<option value="(C\d+A?)"', page)):
        save(OUT / "klrt" / f"fl-{sid}.html", lambda: get("https://www.krtc.com.tw/KLRT/first_and_last_train?KRTCStation=" + sid))
        for tag, path in KLRT_DAYS.items():
            save(OUT / "klrt" / f"tt-{tag}-{sid}.html", lambda: get(f"https://www.krtc.com.tw/KLRT/{path}?n={sid}"))


def tmrt():
    save(OUT / "tmrt" / "first-last-train.html", lambda: get("https://www.tmrt.com.tw/metro-life/first-last-train"))


def ntdlrt():
    for node in range(447, 461):
        page = save(OUT / "ntdlrt" / f"node-{node}.html", lambda: get(f"https://www.ntmetro.com.tw/basic/?mode=detail&node={node}")).decode("utf-8", "replace")
        # each page links the timetable twice: a PDF whose text extracts garbled, and an .odt (a zipped XML table)
        links = re.findall(r'<a href="(/archive/file/[^"]+\.odt)"[^>]*>[^<]*?(V\d\d)[^<]*</a>', page, flags=re.I)
        if not links: print(f"  node {node}: no station timetable"); continue
        for u, sid in links:
            save(OUT / "ntdlrt" / f"{sid}.odt", lambda: get("https://www.ntmetro.com.tw" + html.unescape(u)))


JOBS = {"trtc": trtc, "tymc": tymc, "krtc": krtc, "klrt": klrt, "tmrt": tmrt, "ntdlrt": ntdlrt}

if __name__ == "__main__":
    for name in sys.argv[1:] or JOBS:
        print(name, flush=True); JOBS[name]()
