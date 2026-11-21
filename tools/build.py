"""Build the site into dist/.

    python3 tools/build.py

dist/index.html     高鐵, 臺鐵 and the five metro systems with their light rails on one map
dist/artifact.html  index.html's body only, for hosts that add their own document skeleton
"""
import json, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
load = lambda p: json.loads(p.read_text(encoding="utf-8"))
compact = lambda o: json.dumps(o, ensure_ascii=False, separators=(",", ":"))
DESCRIPTION = ("台灣軌道動態系統：台灣高鐵、臺鐵全車種，加上台北捷運、新北捷運、桃園機場捷運、臺中捷運、高雄捷運與淡海、安坑、高雄環狀輕軌，"
               "在同一張地圖上依時刻表推算每一班列車的位置，並提供車站看板、轉乘查詢與時刻表。非官方展示。")


def page(body, description):
    """title, fonts and styles come before the app markup; they belong in <head>"""
    split = body.index('<div class="app">')
    return ('<!doctype html>\n<html lang="zh-Hant">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
            f'<meta name="description" content="{description}">\n'
            + body[:split] + "</head>\n<body>\n" + body[split:] + "\n</body>\n</html>\n")


regular = sorted(DATA.glob("thsr-timetable-*.json"))[-1]
reg_from = regular.stem.removeprefix("thsr-timetable-")
hsr = {"regular": {"name": f"{int(reg_from[:4])}/{int(reg_from[5:7])}/{int(reg_from[8:])} 起適用時刻表", "from": reg_from, "trains": load(regular)},
       "special": [load(p) for p in sorted(DATA.glob("thsr-special-*.json"))]}
# extra trains announced on their own (11/27 紅眼班次, the same file as thsr-live's
# data/special-2026-11-27-redeye.json) join the special period they run in, tagged, with a note
THSR_EXTRAS = [{"file": "thsr-extra-2026-11-27-redeye.json", "tag": "紅眼",
                "note": "11/27 深夜紅眼班次，標準車廂對號座全面 77 折",
                "addedStops": ["1577", "1579"], "addedStopsNote": "本班次 11/27 新增停靠站",
                "url": "https://www.thsrc.com.tw/ArticleContent/25425adb-288e-4a11-95ea-71e45184c4be"}]
for ex in THSR_EXTRAS:
    for t in load(DATA / ex["file"])["trains"]:
        sp = next(s for s in hsr["special"] if all(s["from"] <= d <= s["to"] for d in t["dates"]))
        note = ex["note"] + ("；" + ex["addedStopsNote"] if t["no"] in ex["addedStops"] else "")
        sp["trains"].append({**t, "tag": ex["tag"], "note": f'{note}（<a href="{ex["url"]}" target="_blank" rel="noopener">高鐵公告</a>）'})
for s in hsr["special"]:
    for d in {d for t in s["trains"] for d in (t["dates"] or [s["from"]])}:
        nos = [t["no"] for t in s["trains"] if t["dates"] is None or d in t["dates"]]
        assert len(nos) == len(set(nos)), f"duplicate 高鐵 train numbers on {d}"
tra = load(DATA / "tra-trains.json")
metro = load(DATA / "metro.json")
body = (ROOT / "src" / "app.html").read_text(encoding="utf-8")
for mark, value in {"__HSR_JSON__": hsr, "__TRA_JSON__": tra, "__MAP_JSON__": load(DATA / "map.json"), "__METRO_JSON__": metro}.items():
    assert mark in body, mark
    body = body.replace(mark, compact(value))

dist = ROOT / "dist"
dist.mkdir(exist_ok=True)
(dist / "index.html").write_text(page(body, DESCRIPTION), encoding="utf-8")
(dist / "artifact.html").write_text(body, encoding="utf-8")
print(f"dist/index.html {len(body.encode('utf-8')) / 1024:.0f} KB · 捷運 {len(metro['lines'])} lines, {len(metro['stations'])} stations, {len(metro['trips'])} runs · "
      f"高鐵 {len(hsr['regular']['trains'])} · 臺鐵 {len(tra['trains'])} schedules {tra['dates'][0]}–{tra['dates'][1]}")
