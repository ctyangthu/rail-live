# 台灣雙鐵動態系統

把[台灣高鐵動態系統](https://ctyangthu.github.io/thsr-live/)與[台鐵環島動態系統](https://ctyangthu.github.io/tra-live/)合在同一張台灣地圖上：高鐵南港—左營 12 站以 N700ST 呈現，臺鐵環島鐵路以自強號（EMU3000 新自強、普悠瑪、太魯閣、推拉式等）呈現，兩者共用時間軸，並可查詢高鐵與臺鐵之間的轉乘。

## 功能

- **依日期與星期套用班表**
  - 高鐵：依〈2026/2/2 起適用時刻表〉按星期套用，每日固定 131 班，其餘只在指定星期行駛（一 156、二 149、三 149、四 158、五 179、六 161、日 182）。疏運期間改用另行公告的時刻表，目前收錄〈2026 選舉疏運時刻表〉（11/27–11/30，各日 195、171、192、160 班）。
  - 臺鐵：使用臺鐵每日公告的時刻表（約未來 60 天），每天班次不同；超出公告範圍的日期，暫以最近一個同星期的日期推算。
  - 概況卡的「一週班次」並列週一到週日兩鐵各日班次，點選即可切換日期；疏運日另外標示。
- **即時與模擬**：預設使用台灣現在時間；可切換日期、拖曳時間軸，並以 1×–900× 播放。跨午夜仍在行駛的前一天列車會繼續顯示。
- **地圖**：高鐵為橘色路線與方形車站，臺鐵為黑白相間的鐵路符號、支線為虛線。列車沿實際路徑靠左行駛、車頭朝行進方向，虛框表示停靠中；點選列車會標出全程路線。圖例可逐一顯示或隱藏高鐵與各種自強號，地圖、統計、看板、轉乘查詢與時刻表一起套用。
- **轉乘查詢**：任選高鐵站或自強號停靠站，列出直達與一次轉乘的行程，只保留沒有其他行程「更晚出發、更早抵達且轉乘不更多」的選項。轉乘點與估計時間：

  | 高鐵站 | 臺鐵站 | 估計 | 方式 |
  | --- | --- | --- | --- |
  | 南港、台北、板橋 | 同名站 | 10–12 分 | 同站轉乘 |
  | 台中 | 新烏日 | 10 分 | 車站相連 |
  | 左營 | 新左營 | 10 分 | 車站相連 |
  | 苗栗 | 苗栗 | 20 分 | 豐富站轉區間車 |
  | 台中 | 臺中 | 25 分 | 新烏日站轉區間車 |
  | 新竹 | 新竹 | 30 分 | 六家站轉六家線區間車 |
  | 台南 | 臺南 | 35 分 | 沙崙站轉沙崙線區間車 |
  | 嘉義 | 嘉義 | 40 分 | BRT 接駁 |

- **列車詳情**：停靠與通過車站、可轉乘站、下一站、估算時速；高鐵顯示行駛星期或疏運日期，臺鐵顯示車廂設施、60 天行駛日曆與臺鐵備註。
- **車站看板**：選一站即顯示該站兩鐵各方向接下來的班次，並可一鍵跳到轉乘的另一站。
- **時刻表**：高鐵為站別時刻矩陣（南下／北上、只列本日行駛），臺鐵為班次列表（順逆行、路線、車次搜尋）。

## 限制

- 列車位置依時刻表推算，不含誤點等即時資訊；臺鐵車站之間以直線相連。
- 轉乘時間為估計值，區間車與 BRT 的班次未納入。
- 高鐵國定假日與連假另行公告的時刻表，目前只收錄選舉疏運。新的疏運時刻表公告後，以 `tools/parse_thsr_special.py` 加入。
- N700ST 依新聞報導預計 2027 年 7 月 1 日投入營運；本系統以 N700ST 呈現所有高鐵車次。
- 本系統為非官方展示，實際行車以兩公司公告為準。

## 專案結構

```
src/app.html                          網頁原始碼（資料以佔位字串嵌入）
data/thsr-timetable-2026-02-02.json   高鐵一般時刻表：214 個車次與行駛星期
data/thsr-special-2026-11-27.json     高鐵選舉疏運時刻表：228 個車次與行駛日期
data/tra-stations.json                臺鐵車站基本資料（代碼、站名、GPS）
data/tra-trains.json                  臺鐵每日時刻表整理出的自強號班表、車站與軌道圖
data/counties-10t.json, map.json      縣市界 TopoJSON 與投影後的地圖路徑
tools/parse_thsr_timetable.py         解析高鐵一般時刻表 PDF（需要 pdfplumber）
tools/parse_thsr_special.py           解析高鐵疏運時刻表 PDF（需要 pdfplumber）
tools/fetch_tra_timetable.py          下載臺鐵目前公告的所有每日時刻表 JSON
tools/extract_tra_trains.py           整理自強號班表，並推出軌道相鄰關係
tools/build_map.py                    產生 data/map.json
tools/build.py                        組出 dist/index.html
```

## 建置

```bash
python3 tools/build.py
```

產出的 `dist/index.html` 可直接用瀏覽器開啟。推送到 `main` 後，GitHub Actions 會建置並部署到 GitHub Pages，並在每天 04:30（台灣時間）重新下載臺鐵時刻表。

更新高鐵時刻表：

```bash
python3 tools/parse_thsr_timetable.py 新時刻表.pdf data/thsr-timetable-YYYY-MM-DD.json
python3 tools/parse_thsr_special.py 疏運時刻表.pdf data/thsr-special-YYYY-MM-DD.json "疏運名稱"
python3 tools/build.py
```

`build.py` 取日期最新的 `thsr-timetable-*.json` 為一般時刻表，所有 `thsr-special-*.json` 為疏運期間。

在本機更新臺鐵時刻表（原始檔約 120 MB，放在 `raw/`，不納入版本控制）：

```bash
python3 tools/fetch_tra_timetable.py raw
python3 tools/extract_tra_trains.py raw data/tra-trains.json
python3 tools/build.py
```

## 資料來源

- 高鐵時刻表：[台灣高鐵〈2026/2/2 起適用時刻表〉〈2026 選舉疏運時刻表〉](https://www.thsrc.com.tw/ArticleContent/a3b630bb-1066-4352-a1ef-58c7b4e8ef7c)
- 臺鐵時刻表：[臺鐵開放資料〈鐵路時刻表 JSON〉](https://ods.railway.gov.tw/tra-ods-web/ods/download/dataResource/railway_schedule/JSON/list)；車種對照：[臺鐵時刻查詢](https://www.railway.gov.tw/tra-tip-web/tip)
- 地圖：[taiwan-atlas](https://github.com/dkaoster/taiwan-atlas)（原始資料為內政部國土測繪中心開放資料）
- 參考：[台灣高鐵動態系統](https://ctyangthu.github.io/thsr-live/)、[台鐵環島動態系統](https://ctyangthu.github.io/tra-live/)、[火車時刻查詢](https://traintime.jsy.tw/)
