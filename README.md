# 台股全市場起漲雷達 V1 — GitHub Actions 雲端版

> **狀態：可部署的 V1 測試版，尚未驗證 GitHub 雲端實際抓取成功。** 不含18券商分點、法人、融資與股價還原。絕不使用 4J 網站。

## 目的

使用 TWSE/TPEx 官方逐日整體行情，將 OHLCV 儲存 SQLite，計算 MA5/10/20/60、斜率、乖離、20/60日位置、量比、RSI14、MACD、ADX/DI、Higher Low、10日區間收斂、20日突破與 1/3/5日技術評分變化。以 Excel / CSV / JSON 輸出。**目前尚無週轉率（需要流通股數）、大盤相對強弱RS（需要同步基準指數）、18分點與籌碼共振，不能稱完整最終規格。**

## 安裝（只需要 GitHub 帳號）

1. 在 GitHub 建立 **新的公開 Repository**，例如 `tw-stock-radar-v1`。公開庫的 `docs/report.json` 可供 ChatGPT 網頁讀取；**不要上傳個人持股、成本、API Key或任何私人資料**。如不希望行情DB公開，需改為私人資料庫＋單獨公開匿名報告，V1尚未實作這種隔離。
2. 下載本 ZIP 並解壓縮，將**資料夾內所有檔案**上傳到 Repository 根目錄，包括隱藏資料夾 `.github/workflows/radar.yml`。GitHub網頁 `Add file → Upload files` 可上傳資料夾中的檔案；若隱藏資料夾沒上傳成功，可用 GitHub Desktop 或 Git。
3. Repository → **Settings → Actions → General → Workflow permissions**，選 **Read and write permissions** 並儲存。否則排程無法把 SQLite 和報告 commit 回 Repository。
4. Repository → **Actions → Taiwan Stock Radar V1 → Run workflow**，先手動執行，`max_days=8`。進入執行記錄確認測試通過、資料下載成功且 `data/radar.sqlite`、`docs/report.json` 已出現。**如果 fetch_log 大量顯示 error / empty_unverified，代表官方介面變動或GitHub IP被擋，不能視為成功。**
5. Repository → **Settings → Pages → Build and deployment**：Source 選 `Deploy from a branch`，Branch 選 `main`、Folder 選 `/docs`，Save。稍等Pages發布。報告網址通常是 `https://你的帳號.github.io/tw-stock-radar-v1/report.json`，請以GitHub Pages設定頁實際顯示的網址為準。
6. 把**實際能在瀏覽器開啟的 report.json 網址**貼回ChatGPT，我才能協助修改既有23:00任務的讀取指令。**未提供/未驗證網址之前，ChatGPT排程不會自動讀取雲端報告。**
7. 每個交易日台灣時間18:00、22:40排程嘗試執行；GitHub Actions的cron可能延遲或偶爾略過，不能保證23:00前完成。週末不執行；休市時使用上次成功資料。

## 歷史資料回補

- 第一次執行沒有80根歷史K線，**Excel排名會顯示資料不足**，這是正確行為，不應捏造排名。
- 每次預設最多處理8個未完整擷取的工作日；可在 Actions 手動 `Run workflow` 指定 `max_days=20`，重複回補至 `symbols_with_80_bars` 足夠。回補有官方限流風險，請勿密集執行。
- `lookback=260` 指回溯260個**日曆日**，不是260個交易日。
- SQLite以Git commit保存，適合原型，長期資料增加會讓Git倉庫膨脹；正式版建議遷移至外部雲端資料庫。

## 如何看覆蓋率

`docs/report.json` 包含 `latest_data_date`、`total_symbols_in_database`、`symbols_with_80_bars`、`history_coverage_pct`、`latest_day_symbols_by_market`。這是**資料庫內部覆蓋率**，不是已驗證官方全市場覆蓋率。`complete_full_market_scan` 固定為 `false`，直到另外建成並核對官方完整股票池。

## 技術指標與限制

- 技術分數是0–100的**明確規則分數**，並非已回測的勝率或主力分數；80根K線不足不計分。
- RSI/ADX使用平滑算法，和券商平台數值可能略有差異；沒有復權調整。
- 只接受四位數代號是**V1暫行代理篩選**，可能漏掉其他合法普通股或混入特殊證券；正式版需接入官方證券類別清單。
- TPEx新舊介面回傳欄位可能變動；資料解析採「失敗不寫入」，請核對日誌及實際樣本。
- 沒有使用者持股資料上傳；亞電持股由ChatGPT獨立評估。

## 本機測試（可選）

```bash
python -m pip install -r requirements.txt
pytest -q
python -m radar.main --max-days 8
```

## 來源

- TWSE `https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX`
- TPEx `https://www.tpex.org.tw/www/zh-tw/afterTrading/dailyQuotes`
- TPEx legacy fallback `https://www.tpex.org.tw/web/stock/aftertrading/otc_quotes_no1430/stk_wn1430_result.php`

請遵守各官方網站使用條款與存取限制。若遇403/429，應降低請求頻率或更換合法授權資料來源，不應繞過存取控制。
