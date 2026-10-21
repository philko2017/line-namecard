# LINE 設定步驟：新的官方帳號＋LIFF

名片頁面要在 LINE 裡打開，需要三樣東西：**官方帳號**（大家加好友、按選單）、**LINE Login channel**（讓頁面知道是誰在用）、**LIFF app**（頁面本身在 LINE 裡的入口）。照下面順序做，全部大約 20 分鐘。

> 先準備：GitHub 帳號名稱（頁面網址會是 `https://<帳號名稱>.github.io/line-namecard/liff/namecard/`）。

## 一、建立官方帳號

1. 打開 https://tw.linebiz.com/ → 右上角「登入管理頁面」→ 選「LINE Official Account Manager」，用你的 LINE 帳號登入。
2. 按「建立新帳號」（或「建立 LINE 官方帳號」）。
3. 填寫：
   - 帳號名稱：例如「Gemhorn 名片」（之後可改）
   - 電子郵件、公司名稱、業種（例如「資訊服務」）
4. 按「確定」→「完成」。這時會進到帳號的管理畫面。

## 二、開啟 Messaging API（同時建立 Provider）

1. 在官方帳號管理畫面，右上角「設定」（齒輪）→ 左邊「Messaging API」→ 按「啟用 Messaging API」。
2. 第一次會要你選 **Provider（服務提供者）**：選「建立新的服務提供者」，名稱例如「Gemhorn」。
   - ⚠ Provider 名稱之後**不能改到別的帳號底下**，LINE Login channel 一定要建在同一個 Provider，頁面才拿得到同一個使用者編號。
3. 隱私權政策、服務條款網址可以先留空，按「確定」。

## 三、建立 LINE Login channel

1. 打開 https://developers.line.biz/console/ ，用同一個 LINE 帳號登入。
2. 點剛剛建立的 Provider（例如「Gemhorn」）。這裡會看到一個 Messaging API channel（就是你的官方帳號）。
3. 按「Create a new channel」→ 選「**LINE Login**」。
4. 填寫：
   - Region：Taiwan
   - Channel name：例如「Gemhorn 名片頁面」
   - Channel description：例如「拍名片存進 Notion」
   - App types：勾「**Web app**」
   - Email address：你的信箱
   - 勾同意條款 → 「Create」。
5. 建好後在「Basic settings」分頁找到 **Channel ID**（一串數字）→ 抄下來給 Claude。
6. 同一頁往下找「**Linked LINE Official Account**」→ 按「Edit」→ 選你剛建的官方帳號 → 存檔。（這樣第一次打開頁面時，會提示加官方帳號好友。）

## 四、新增 LIFF app

1. 在 LINE Login channel 裡點「**LIFF**」分頁 →「Add」。
2. 填寫：
   - LIFF app name：名片
   - Size：**Full**
   - Endpoint URL：`https://<GitHub 帳號名稱>.github.io/line-namecard/liff/namecard/`（還沒推上 GitHub 也可以先填，之後再改）
   - Scopes：勾 **openid**、**profile**
   - Add friend option：**On (Normal)**
   - Scan QR：不用勾
   - Module mode：不用開
3. 按「Add」。列表上會出現 **LIFF ID**（像 `2012345678-AbCdEfGh`）和 LIFF URL（`https://liff.line.me/...`）→ 抄下 LIFF ID 給 Claude。

## 五、把 channel 改成「公開」

LINE Login channel 一開始是「Developing」，只有你自己能用。

1. 回到 LINE Login channel 頁面最上方，狀態旁邊按「**Publish**」→ 確認。
2. 狀態變成「Published」之後，其他同仁也可以打開頁面。

## 六、圖文選單（之後做也可以）

在 LINE Official Account Manager →「圖文選單」→「建立」：

1. 版型選一格或兩格（例如左「📷 拍名片」、右「✅ 待確認」）。
2. 動作選「連結」：
   - 拍名片：`https://liff.line.me/<LIFF ID>`
   - 待確認：`https://liff.line.me/<LIFF ID>?v=review`
3. 顯示期間設長一點，按「儲存」。

## 要給 Claude 的資料

| 項目 | 在哪裡 |
|---|---|
| GitHub 帳號名稱 | GitHub 右上角頭像 → 帳號名稱（不是 email） |
| LINE Login Channel ID | LINE Developers → LINE Login channel →「Basic settings」 |
| LIFF ID | LINE Developers → LINE Login channel →「LIFF」分頁 |
