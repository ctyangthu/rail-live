"""Download the metro open data from TDX into raw/metro/.

    python3 tools/fetch_metro.py [operator ...]

Operators: TRTC 台北捷運, NTMC 新北捷運環狀線, TYMC 桃園機場捷運, TMRT 臺中捷運, KRTC 高雄捷運,
and the light rails NTDLRT 淡海, NTALRT 安坑, KLRT 高雄. Files already in raw/metro/ are kept, so a run
that stops at the daily limit can be continued the next day; delete a file to refresh it.
Without a key TDX allows only a few requests a day per address; set TDX_TOKEN to an access token
from your own TDX account to lift the limit.
"""
import gzip, os, pathlib, sys, time, urllib.error, urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "raw" / "metro"
BASE = "https://tdx.transportdata.tw/api/basic/v2/Rail/Metro"
OPS = ("TRTC", "NTMC", "TMRT", "TYMC", "KRTC", "NTDLRT", "NTALRT", "KLRT")
EPS = ("StationTimeTable", "Station", "S2STravelTime", "Frequency", "FirstLastTimetable", "StationOfRoute", "Shape")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json", "Accept-Encoding": "gzip"}
    if os.environ.get("TDX_TOKEN"): headers["Authorization"] = "Bearer " + os.environ["TDX_TOKEN"]
    ops = sys.argv[1:] or OPS
    for ep in EPS:
        for op in ops:
            path = OUT / f"{ep}-{op}.json"
            if path.exists(): continue
            req = urllib.request.Request(f"{BASE}/{ep}/{op}?%24format=JSON", headers=headers)
            try:
                with urllib.request.urlopen(req, timeout=180) as r:
                    body = r.read()
                    if r.headers.get("Content-Encoding") == "gzip": body = gzip.decompress(body)
            except urllib.error.HTTPError as e:
                msg = e.read()
                if msg[:2] == b"\x1f\x8b": msg = gzip.decompress(msg)
                if e.code == 400: print(f"{ep}/{op}: not published ({msg[:120].decode('utf-8', 'replace')})", flush=True); time.sleep(1.5); continue
                sys.exit(f"{ep}/{op}: HTTP {e.code} {msg[:200]!r}")
            if not body.lstrip().startswith(b"["): sys.exit(f"{ep}/{op}: unexpected reply {body[:200]!r}")
            path.write_bytes(body)
            print(f"{path.name} {len(body) / 1024:.0f} KB", flush=True)
            time.sleep(1.5)


if __name__ == "__main__":
    main()
