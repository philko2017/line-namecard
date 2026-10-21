# LINE 名片模組

在 LINE 裡拍名片和合照，AI 辨識名片文字後存進 Notion。架構沿用苗栗收容所系統（LINE 官方帳號 + LIFF + Make.com + Notion）。

## 使用流程

1. 圖文選單「拍名片」打開 LIFF 頁面。
2. 按 ① 拍名片、按 ② 拍合照（可不拍），填「認識場合」（會記住），按送出。
3. 畫面立刻清空，可以拍下一位；照片在背景上傳。
4. Make 收到後先回應頁面，接著請 Gemini 讀名片、把照片存到 Google 雲端硬碟（檔名「人名_公司_名片.jpg」「人名_公司_合照.jpg」）、寫進 Notion，狀態從「處理中」變成「待確認」。辨識失敗時照片照樣存，檔名改用請求編號。
5. 有空時打開「待確認」分頁，看照片、修改欄位、加標籤，按「確認存入」，狀態變成「已確認」。

整個流程不發任何 LINE 訊息，不佔官方帳號的訊息量。每張名片約用 Make 10～12 點。

## 組成

| 部分 | 位置 | 說明 |
|---|---|---|
| LIFF 頁面 | `liff/namecard/` | `index.html` 版面、`app.js` 程式、`mock.js` 本機預覽用的模擬資料 |
| Make 情境「名片」 | `tools/make_blueprint.py` 產生 `make/名片.blueprint.json` | 一個 webhook，欄位 `a` 分辨動作：`submit`、`list`、`save` |
| Notion 資料庫「名片」 | | 欄位名稱要和 `make_blueprint.py` 的 `FIELDS` 一字不差；建好後鎖定資料庫 |
| Google 雲端硬碟資料夾 | | 存名片照片與合照；資料夾設成「知道連結的人都能檢視」，Notion 和頁面才看得到照片 |

## 後端動作

| 動作 | 做什麼 | 回應 |
|---|---|---|
| `submit` | 欄位 `rid` 請求編號、`card` 名片照片（JPEG base64）、`photo` 合照（可空白）、`place` 認識場合、`note` 備註。請求編號重複就不再寫 | 驗證身分後立刻回 `{ok}`，之後才處理 |
| `list` | 自己拍的名片，最多 100 筆，最新的在前 | `{ok, cards:[{id, created_time, properties_value}]}` |
| `save` | `id` 加上各欄位與 `tags`（逗號分隔）；只能改自己拍的 | `{ok}`；403 `not_yours` |

身分：頁面送 LIFF 的 Access Token，Make 向 LINE 確認它屬於本系統的 LINE Login channel，再取得使用者編號。

## 部署

1. 複製 `tools/config.example.json` 成 `tools/config.local.json`，填入 ID。
2. `python tools/make_blueprint.py` 產生藍圖，匯入 Make（或請 Claude 用 Make 連接器建立）。
3. 把 `liff/namecard/app.js` 開頭 `CONFIG` 的 `liffId`、`apiUrl` 換成自己的，`index.html` 的 CSP `connect-src` 換成 webhook 的網域。
4. 把 `liff/namecard/` 放上 GitHub Pages，網址填到 LIFF app 的 Endpoint URL。

## 本機預覽

```bash
python -m http.server 5191 --directory liff/namecard
```

打開 http://localhost:5191 會用 `mock.js` 的模擬資料，不連 LINE 和 Make。`?v=review` 直接打開待確認分頁。

## Make 的地雷（沿用苗栗的經驗）

- 用 API 建立的 HTTP 模組要補上預設值（`HTTP_DEFAULTS`），否則請求不會送出。
- HTTP 模組遇到 4xx 會中斷整個執行；要在錯誤處理路線放 Webhook response＋Ignore，頁面才收得到錯誤。
- 模組上的篩選沒通過，後面整條都會停，所以「有沒有合照」分成兩條路線。
- Make 遇到空字串會略過不寫：在確認畫面把欄位清空，Notion 裡的舊值不會被清掉。
