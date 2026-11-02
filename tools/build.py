"""Inline both timetables and the map into src/app.html and write the site into dist/.

    python3 tools/build.py

dist/index.html     standalone page (GitHub Pages, or open directly in a browser)
dist/artifact.html  page body only, for hosts that add their own document skeleton
"""
import json, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
load = lambda p: json.loads(p.read_text(encoding="utf-8"))

src = (ROOT / "src" / "app.html").read_text(encoding="utf-8")
# 高鐵: the regular timetable (weekday based) plus any special periods that replace it on given dates
regular = sorted(DATA.glob("thsr-timetable-*.json"))[-1]
reg_from = regular.stem.removeprefix("thsr-timetable-")
hsr = {
    "regular": {"name": f"{int(reg_from[:4])}/{int(reg_from[5:7])}/{int(reg_from[8:])} 起適用時刻表", "from": reg_from,
                "trains": load(regular)},
    "special": [load(p) for p in sorted(DATA.glob("thsr-special-*.json"))],
}
tra = load(DATA / "tra-trains.json")
geo = load(DATA / "map.json")

compact = lambda o: json.dumps(o, ensure_ascii=False, separators=(",", ":"))
body = (src.replace("__HSR_JSON__", compact(hsr)).replace("__TRA_JSON__", compact(tra))
        .replace("__MAP_JSON__", compact(geo)))
assert "__HSR_JSON__" not in body and "__TRA_JSON__" not in body and "__MAP_JSON__" not in body

# title, fonts and styles come before the app markup; they belong in <head>
split = body.index('<div class="app">')
standalone = (
    '<!doctype html>\n<html lang="zh-Hant">\n<head>\n<meta charset="utf-8">\n'
    '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
    '<meta name="description" content="在同一張台灣地圖上推算台灣高鐵 N700ST 與臺鐵自強號 EMU3000 的即時位置；高鐵依星期與疏運時刻表、臺鐵依每日公告時刻表，並可查詢高鐵與臺鐵轉乘。">\n'
    + body[:split] + "</head>\n<body>\n" + body[split:] + "\n</body>\n</html>\n"
)
dist = ROOT / "dist"
dist.mkdir(exist_ok=True)
(dist / "index.html").write_text(standalone, encoding="utf-8")
(dist / "artifact.html").write_text(body, encoding="utf-8")
sp = ", ".join(f"{s['name']} {s['from']}–{s['to']}" for s in hsr["special"]) or "none"
print(f"dist/index.html + dist/artifact.html written: {len(body.encode('utf-8')) / 1024:.1f} KB · "
      f"高鐵 {len(hsr['regular']['trains'])} trains (special: {sp}) · "
      f"臺鐵 {len(tra['trains'])} schedules {tra['dates'][0]}–{tra['dates'][1]}")
