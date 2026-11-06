# 台灣雙鐵動態系統

線上版：<https://ctyangthu.github.io/rail-live/>

把[台灣高鐵動態系統](https://ctyangthu.github.io/thsr-live/)與[台鐵環島動態系統](https://ctyangthu.github.io/tra-live/)合在同一張台灣地圖上：高鐵南港—左營 12 站以 N700ST 呈現；臺鐵與 tra-live 相同，包含每一班客運列車：自強號（EMU3000 新自強、普悠瑪、太魯閣、推拉式、柴聯、專開列車如環島之星）、莒光號、區間快車、區間車與普快車，涵蓋環島鐵路與平溪、深澳、內灣、六家、集集、沙崙等支線。兩者共用時間軸，並可查詢高鐵與臺鐵之間的轉乘。

## 功能

- **依日期與星期套用班表**
  - 高鐵：依〈2026/2/2 起適用時刻表〉按星期套用，每日固定 131 班，其餘只在指定星期行駛（一 156、二 149、三 149、四 158、五 179、六 161、日 182）。疏運期間改用另行公告的時刻表，目前收錄〈2026 選舉疏運時刻表〉（11/27–11/30，各日 195、171、192、160 班）。
  - 臺鐵：使用臺鐵每日公告的時刻表（約未來 60 天），每天約 900 班，其中區間車約 680 班、自強號約 130–160 班；超出公告範圍的日期，暫以最近一個同星期的日期推算。
  - 概況卡的「一週班次」分列週一到週日兩鐵各日班次（兩列比例尺不同），點選即可切換日期；疏運日另外標示。
- **即時與模擬**：預設使用台灣現在時間；可切換日期、拖曳時間軸，並以 1×–900× 播放。跨午夜仍在行駛的前一天列車會繼續顯示。
- **地圖**：高鐵為橘色路線與方形車站，臺鐵為黑白相間的鐵路符號、支線為虛線。列車沿實際路徑靠左行駛、車頭朝行進方向，虛框表示停靠中；點選列車會標出全程路線。區間車與區間快車畫得較小並位於城際列車下方，放大地圖後才顯示車次。
- **車種篩選**：圖例可逐一顯示或隱藏高鐵與臺鐵各車種（例如只看高鐵與自強號），地圖、統計、看板、轉乘查詢與時刻表一起套用；全日在線列車數依車種堆疊。
- **轉乘查詢**：任選高鐵站或臺鐵車站（含支線），用兩鐵的時刻表找出直達與轉乘行程，最多搭 4 班車。只保留沒有其他行程更晚出發又更早抵達的選項，每多轉乘一次至少要早 10 分鐘。同一站內換車預留 5 分鐘，兩鐵之間的轉乘點與估計時間：

  | 高鐵站 | 臺鐵站 | 估計 | 方式 |
  | --- | --- | --- | --- |
  | 南港、台北、板橋 | 同名站 | 10–12 分 | 同站轉乘 |
  | 新竹 | 六家 | 8 分 | 車站相連 |
  | 苗栗 | 豐富 | 8 分 | 車站相連 |
  | 台中 | 新烏日 | 10 分 | 車站相連 |
  | 台南 | 沙崙 | 8 分 | 車站相連 |
  | 左營 | 新左營 | 10 分 | 車站相連 |
  | 嘉義 | 嘉義 | 40 分 | BRT 接駁 |

  高鐵桃園、彰化、雲林附近沒有相連的臺鐵車站，未列入轉乘點。
- **列車詳情**：車種與車型說明、停靠與通過車站、可轉乘站、下一站、估算時速；高鐵顯示行駛星期或疏運日期，臺鐵顯示車廂設施、60 天行駛日曆與臺鐵備註。
- **車站看板**：選一站（含支線車站）即顯示該站兩鐵各方向接下來的班次，並可一鍵跳到轉乘的另一站。
- **時刻表**：高鐵為站別時刻矩陣（南下／北上、只列本日行駛），臺鐵為班次列表（順逆行、路線含支線、車次搜尋）。

## 臺鐵車種

車種依[臺鐵時刻查詢](https://www.railway.gov.tw/tra-tip-web/tip)的標示對照，與 tra-live 相同：

| 車種代碼 | 臺鐵標示 | 本系統 |
| --- | --- | --- |
| 110G、110H、110K、110M | 自強(3000) | 新自強（EMU3000） |
| 1107 | 普悠瑪 | 普悠瑪（TEMU2000） |
| 1101 | 太魯閣 | 太魯閣（TEMU1000） |
| 1108、1109、110A | 自強 | 推拉式自強（1109 附親子車廂，110A 附自行車車廂） |
| 110F | 自強 | 柴聯自強，歸入「其他」 |
| 1104、1106 | 自強(專) | 專開列車（加開班次、環島之星），歸入「其他」 |
| 1110、1112 | 莒光、莒光(專) | 莒光 |
| 1132 | 區間快 | 區間快 |
| 1131、1130、1134 | 區間、區間(專) | 區間 |
| 1150 | 普快(專) | 普快，歸入「其他」 |

日後若出現新代碼，會先依開頭歸類（110 自強、111 莒光、113 區間，其餘為「列車」），整理程式也會提出警告。地圖顏色也與 tra-live 相同，只有推拉式自強改為棕色，避免和高鐵的橘色混淆。

## 限制

- 列車位置依時刻表推算，不含誤點等即時資訊；臺鐵車站之間以直線相連。
- 轉乘的步行與等候時間為估計值，BRT 班次未納入。
- 高鐵國定假日與連假另行公告的時刻表，目前只收錄選舉疏運。新的疏運時刻表公告後，以 `tools/parse_thsr_special.py` 加入。
- N700ST 依新聞報導預計 2027 年 7 月 1 日投入營運；本系統以 N700ST 呈現所有高鐵車次。
- 本系統為非官方展示，實際行車以兩公司公告為準。

## 專案結構

```
src/app.html                          網頁原始碼（資料以佔位字串嵌入）
data/thsr-timetable-2026-02-02.json   高鐵一般時刻表：214 個車次與行駛星期
data/thsr-special-2026-11-27.json     高鐵選舉疏運時刻表：228 個車次與行駛日期
data/tra-stations.json                臺鐵車站基本資料（代碼、站名、GPS）
data/tra-trains.json                  臺鐵每日時刻表整理出的全車種班表、車站與軌道圖
data/counties-10t.json, map.json      縣市界 TopoJSON 與投影後的地圖路徑
tools/parse_thsr_timetable.py         解析高鐵一般時刻表 PDF（需要 pdfplumber）
tools/parse_thsr_special.py           解析高鐵疏運時刻表 PDF（需要 pdfplumber）
tools/fetch_tra_timetable.py          下載臺鐵目前公告的所有每日時刻表 JSON
tools/extract_tra_trains.py           整理全車種班表，並推出軌道相鄰關係（與 tra-live 同步）
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
