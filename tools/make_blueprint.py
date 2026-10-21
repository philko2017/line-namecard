"""產生 Make 情境「名片」的藍圖（make/名片.blueprint.json）。

做法沿用苗栗收容所系統的 tools/make_blueprints.py：
- LIFF 頁面用表單格式送到同一個 webhook，欄位 a 是動作：submit 送出照片｜list 待確認清單｜save 確認存入。
- 每次都先向 LINE 驗證 Access Token（屬於本系統的 LINE Login channel），再取得使用者編號。
- submit 驗證完立刻回應頁面，之後才存照片、跑 AI 辨識、寫 Notion，現場不用等。

執行：python tools/make_blueprint.py      （讀 tools/config.local.json）
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CFG = json.loads((ROOT / "tools" / ("config.example.json" if "--example" in sys.argv else "config.local.json")).read_text(encoding="utf-8"))
MK, LN = CFG["make"], CFG["line"]
HOOK = MK["hook_id"]
CONN_NOTION, CONN_GEMINI, CONN_DRIVE = MK["notion_connection_id"], MK["gemini_connection_id"], MK["drive_connection_id"]
DRIVE_FOLDER = MK["drive_folder_id"]
DS = CFG["notion"]["data_source_id"]
CHANNEL = LN["login_channel_id"]
# 可用的模型清單會變（2.5 系列已在 2026-10-16 停用），換模型時用 Make 的 Gemini 模組下拉選單確認名稱
MODEL = CFG.get("gemini_model", "gemini-3.8-flash")
ORIGIN = CFG.get("page_origin") or "*"
# 建立時的暫時姓名；頁面看到這個值會當成空白（liff/namecard/app.js 的 PENDING_NAME）
PENDING_NAME = "（待辨識）"

# HTTP「Make a request」模組的必填設定。用 API 建立時不會自動帶入，少了會報 BundleValidationError（苗栗踩過）
HTTP_DEFAULTS = {"rejectUnauthorized": True, "followRedirect": True, "followAllRedirects": False, "useQuerystring": False,
                 "gzip": True, "useMtls": False}

# 頁面欄位代號 → Notion 欄位名稱、型別、長度上限（和 app.js 的 FIELDS 對應）
FIELDS = [
    ("name", "姓名", "title", 80), ("company", "公司", "rich_text", 120), ("title", "職稱", "rich_text", 80),
    ("dept", "部門", "rich_text", 80), ("mobile", "手機", "phone_number", 60), ("phone", "電話", "phone_number", 60),
    ("email", "Email", "email", 120), ("address", "地址", "rich_text", 200), ("web", "網站", "url", 200),
    ("other", "其他聯絡方式", "rich_text", 300), ("place", "認識場合", "rich_text", 120), ("note", "備註", "rich_text", 1000),
]
AI_FIELDS = [f for f in FIELDS if f[0] not in ("place", "note")]   # AI 從名片讀的欄位
TAGS = ["客戶", "合作夥伴", "廠商", "其他"]


def c(a, o, b=None):
    d = {"a": a, "o": o}
    if b is not None:
        d["b"] = b
    return d


def flt(name, groups):
    return {"name": name, "conditions": groups}


def sp(mod, prop, suffix=""):
    return "{{" + f"{mod}.properties_value.`{prop}`{suffix}" + "}}"


def cut(field, n):
    """頁面送來的文字限制長度（Notion 文字欄位上限 2000 字，也避免被灌大量內容）"""
    return "{{substring(" + field + "; 0; " + str(n) + ")}}"


def fv(k, typ, v):
    return {"key": k, "type": typ, "value": v}


class B:
    """藍圖組裝器：依序配發模組編號和畫布座標。"""

    def __init__(self):
        self.next_id = 10
        self.y = 0

    def nid(self):
        self.next_id += 1
        return self.next_id

    def meta(self, name, conn_type=None):
        self.y += 150
        m = {"designer": {"x": 900, "y": self.y, "name": name}}
        if conn_type:
            m["parameters"] = [{"name": "__IMTCONN__", "type": conn_type, "label": "Connection", "required": True}]
        return m

    def respond(self, name, body, status="200"):
        return {"id": self.nid(), "module": "gateway:WebhookRespond", "version": 1, "parameters": {},
                "mapper": {"status": status, "body": body, "headers": [
                    {"key": "Content-Type", "value": "application/json; charset=utf-8"},
                    {"key": "Access-Control-Allow-Origin", "value": ORIGIN}]},
                "metadata": self.meta(name)}

    def ignore(self):
        return {"id": self.nid(), "module": "builtin:Ignore", "version": 1, "mapper": None,
                "metadata": {"designer": {"x": 1200, "y": self.y}}}

    def notion(self, module, name, mapper, f=None, onerror=None):
        d = {"id": self.nid(), "module": f"notion:{module}", "version": 1, "mapper": mapper,
             "metadata": self.meta(name, "account:notion2,notion3"), "parameters": {"__IMTCONN__": CONN_NOTION}}
        if f:
            d["filter"] = f
        if onerror:
            d["onerror"] = onerror
        return d

    def search(self, name, filters, limit="1", newest=False):
        m = {"limit": limit, "filter": [filters], "select": "data_source_item", "data_source": DS}
        if newest:
            m["sorts"] = [{"select": "timestamp", "direction": "descending", "timestamp": "created_time"}]
        return self.notion("searchObjects1", name, m)

    def get(self, name, page):
        return self.notion("getADatabaseItem", name, {"page": page, "getBy": "data_source", "select": "map"})

    def create(self, name, fields):
        return self.notion("createDataSourceItem", name, {"fields": fields, "select": "map", "data_source": DS})

    def update(self, name, page, fields, onerror=None):
        return self.notion("updateADatabaseItem", name,
                           {"page": page, "fields": fields, "select": "map", "updateBy": "data_source", "data_source": DS},
                           onerror=onerror)

    def notion_api(self, name, url, method, body):
        return self.notion("makeApiCall", name, {
            "url": url, "method": method, "version": "2022-06-28",
            "headers": [{"key": "Content-Type", "value": "application/json"}], "qs": [], "body": body})

    def drive_upload(self, name, filename, b64_field):
        return {"id": self.nid(), "module": "google-drive:uploadAFile", "version": 4,
                "parameters": {"__IMTCONN__": CONN_DRIVE},
                "mapper": {"select": "map", "folderId": DRIVE_FOLDER, "filename": filename,
                           "data": "{{toBinary(" + b64_field + "; \"base64\")}}", "convert": False},
                "metadata": self.meta(name, "account:google-restricted,google-drive")}

    def router(self, name, routes):
        """routes: [(filter, [modules...])]；filter 放在每條路線的第一個模組上。"""
        mid = self.nid()
        rs = []
        for f, mods in routes:
            mods = [dict(m) for m in mods]
            mods[0]["filter"] = f
            rs.append({"flow": mods})
        self.y += 150
        return {"id": mid, "module": "builtin:BasicRouter", "version": 1, "mapper": None,
                "metadata": {"designer": {"x": 600, "y": self.y, "name": name}}, "routes": rs}


def gemini_body():
    """請 Gemini 看名片照片，直接回傳固定欄位的 JSON，不用再從文字裡挖資料。"""
    prompt = ("這是一張名片的照片。請讀出名片上的資訊填入欄位，讀不到的欄位一律給空字串，不要猜。"
              "姓名只放人名。電話和手機保留名片上的寫法，有多支就用「、」分隔；09 開頭或標示 Mobile 的放手機。"
              "其他聯絡方式放 LINE ID、傳真、統一編號、社群帳號，每項前面寫上名稱。"
              "雙語名片以中文為主，英文名字可以接在中文姓名後面的括號裡。raw 放名片上看得到的全部文字。")
    # 不用 responseSchema：2026-10-21 實測 gemini-3.8-flash 帶 responseSchema 時一直卡住不回應；
    # 改成只要求回 JSON，欄位名稱寫在提示裡
    keys = "、".join(f"{k}（{n}）" for k, n, *_ in AI_FIELDS)
    prompt += f"只回傳一個 JSON 物件，欄位固定為：{keys}、raw（全部文字），值一律是字串。"
    body = {
        "contents": [{"role": "user", "parts": [
            {"text": prompt},
            {"inline_data": {"mime_type": "image/jpeg", "data": "{{1.card}}"}}]}],
        "generationConfig": {"responseMimeType": "application/json"},
    }
    # 直接給物件（不是 JSON 字串）：Make 會自己轉成 JSON，照片的 base64 和中文提示都不用擔心跳脫
    return body


def build(test_hook=None):
    """test_hook：產生測試用情境，只跑「存照片 → 辨識 → 寫入」那一段，不做 LINE 身分驗證。
    用來在 LINE 帳號還沒好之前驗證 Gemini 和雲端硬碟；測完就刪掉情境和 webhook。"""
    b = B()
    b.next_id = 100

    # ---- 身分：Access Token 屬於本系統的 LINE Login channel → 取得使用者編號 ----
    def line_get(mid, url, name, headers=()):
        return {"id": mid, "module": "http:ActionSendData", "version": 3, "parameters": {"handleErrors": False},
                "mapper": {"url": url, "method": "get", "serializeUrl": False, "shareCookies": False,
                           "parseResponse": True, "headers": list(headers), "qs": [], **HTTP_DEFAULTS},
                "metadata": {"designer": {"x": 0 if mid == 2 else 150, "y": 0 if mid == 2 else 150, "name": name}},
                # 憑證無效時 LINE 回 400／401，Make 會中斷整個執行、webhook 只回「Accepted」；在錯誤路線回 401，頁面才知道
                "onerror": [b.respond(f"回傳驗證失敗（{name}）", '{"ok":false,"error":"auth"}', "401"), b.ignore()]}
    verify = line_get(2, "https://api.line.me/oauth2/v2.1/verify?access_token={{encodeURL(1.t)}}", "向 LINE 驗證 Access Token")
    profile = line_get(4, "https://api.line.me/v2/profile", "向 LINE 取得使用者編號",
                       [{"name": "Authorization", "value": "Bearer {{1.t}}"}])
    USER, DISPLAY = ("test-user", "（測試）") if test_hook else ("{{4.data.userId}}", "{{4.data.displayName}}")
    auth_ok = c("{{2.data.client_id}}", "text:equal", CHANNEL)
    act = lambda a: c("{{1.a}}", "text:equal", a)
    ACTS = ["submit", "list", "save"]

    # ==== submit：先回應頁面，再存照片 → 辨識 → 寫入 ====
    dup = b.search("請求編號是否已送過", [c("請求編號 |&*^%$#@| rich_text", "text:equals", "{{1.rid}}")])
    D = dup["id"]
    new = b.create("新增名片（處理中）", [
        fv("姓名", "title", PENDING_NAME), fv("狀態", "select", "處理中"), fv("請求編號", "rich_text", cut("1.rid", 40)),
        fv("拍攝者", "rich_text", DISPLAY), fv("拍攝者 LINE ID", "rich_text", USER),
        fv("認識場合", "rich_text", cut("1.place", 120)), fv("備註", "rich_text", cut("1.note", 1000))])
    N = new["id"]
    thumb = lambda m: "https://drive.google.com/thumbnail?id={{" + f"{m}.id" + "}}&sz=w1600"

    def tail(with_photo):
        """存照片 → 照片放進 Notion → Gemini 辨識 → 寫回欄位。有沒有合照分成兩條，因為模組上的篩選擋下就會停掉後面整條。"""
        mods = []
        card = b.drive_upload("名片照片存到雲端硬碟", "{{1.rid}}_名片.jpg", "1.card")
        mods.append(card)
        props = {"名片照片": {"files": [{"name": "名片.jpg", "type": "external", "external": {"url": thumb(card["id"])}}]},
                 "名片照片連結": {"url": "{{" + f"{card['id']}.webViewLink" + "}}"}}
        if with_photo:
            ph = b.drive_upload("合照存到雲端硬碟", "{{1.rid}}_合照.jpg", "1.photo")
            mods.append(ph)
            props["合照"] = {"files": [{"name": "合照.jpg", "type": "external", "external": {"url": thumb(ph["id"])}}]}
            props["合照連結"] = {"url": "{{" + f"{ph['id']}.webViewLink" + "}}"}
        # 照片網址只有英數字，可以直接組 JSON；文字欄位交給 Notion 模組寫，Make 會處理跳脫
        mods.append(b.notion_api("照片放進名片", "/v1/pages/{{" + f"{N}.id" + "}}", "PATCH",
                                 json.dumps({"properties": props}, ensure_ascii=False)))
        failed = [b.update("標成辨識失敗", f"{{{{{N}.id}}}}", [fv("狀態", "select", "辨識失敗")]), b.ignore()]
        ai = {"id": b.nid(), "module": "gemini-ai:makeApiCall", "version": 1, "parameters": {"__IMTCONN__": CONN_GEMINI},
              "mapper": {"url": f"/v1beta/models/{MODEL}:generateContent", "method": "POST",
                         "headers": [{"key": "Content-Type", "value": "application/json"}], "qs": [], "body": gemini_body()},
              "metadata": b.meta("Gemini 辨識名片", "account:gemini-ai-q9zyjp"), "onerror": failed}
        mods.append(ai)
        parse = {"id": b.nid(), "module": "json:ParseJSON", "version": 1, "parameters": {"type": ""},
                 "mapper": {"json": "{{" + f"{ai['id']}.body.candidates[1].content.parts[1].text" + "}}"},
                 "metadata": b.meta("解析辨識結果"),
                 "onerror": [b.update("標成辨識失敗（解析）", f"{{{{{N}.id}}}}", [fv("狀態", "select", "辨識失敗")]), b.ignore()]}
        mods.append(parse)
        P = parse["id"]
        fields = [fv(n, t, "{{" + f"substring({P}.{k}; 0; {ln})" + "}}") for k, n, t, ln in AI_FIELDS]
        fields[0] = fv("姓名", "title", "{{ifempty(" + f"substring({P}.name; 0; 80)" + f'; "{PENDING_NAME}")' + "}}")
        fields += [fv("辨識原文", "rich_text", "{{" + f"substring({P}.raw; 0; 1900)" + "}}"), fv("狀態", "select", "待確認")]
        mods.append(b.update("寫入辨識結果（待確認）", f"{{{{{N}.id}}}}", fields))
        return mods

    photo_router = lambda: b.router("有沒有合照", [
        (flt("有合照", [[c("{{1.photo}}", "exist")]]), tail(True)),
        (flt("沒有合照", [[c("{{1.photo}}", "notexist")]]), tail(False)),
    ])
    if test_hook:
        return blueprint("名片（測試，可刪除）", [webhook(test_hook, "測試請求"),
                                            b.respond("先回應", '{"ok":true}'), new, photo_router()])

    submit_flow = [dup, b.router("是否重複送出", [
        (flt("已送過", [[c(f"{{{{{D}.id}}}}", "exist")]]), [b.respond("回傳重複", '{"ok":true,"duplicate":true}')]),
        (flt("新的名片", [[c(f"{{{{{D}.id}}}}", "notexist"), c("{{1.card}}", "exist")]]), [
            b.respond("先回應頁面（現場不用等）", '{"ok":true}'), new, photo_router()]),
        (flt("沒有名片照片", [[c(f"{{{{{D}.id}}}}", "notexist"), c("{{1.card}}", "notexist")]]), [
            b.respond("回傳缺名片照片", '{"ok":false,"error":"no_card"}', "400")]),
    ])]

    # ==== list：自己拍的名片（最新的在前），頁面只顯示還沒確認的 ====
    mine = b.search("找我拍的名片", [c("拍攝者 LINE ID |&*^%$#@| rich_text", "text:equals", USER)], limit="100", newest=True)
    M = mine["id"]
    agg = {"id": b.nid(), "module": "builtin:BasicAggregator", "version": 1, "parameters": {"feeder": M},
           "mapper": {"id": f"{{{{{M}.id}}}}", "created_time": f"{{{{{M}.created_time}}}}",
                      "properties_value": f"{{{{{M}.properties_value}}}}"},
           "metadata": b.meta("彙整名片")}
    js = {"id": b.nid(), "module": "json:TransformToJSON", "version": 1, "parameters": {"space": ""},
          "mapper": {"object": f"{{{{{agg['id']}.array}}}}"}, "metadata": b.meta("名片轉成 JSON")}
    list_flow = [mine, agg, js, b.respond("回傳名片清單", '{"ok":true,"cards":' + f"{{{{{js['id']}.json}}}}" + "}")]

    # ==== save：確認存入（只能改自己拍的） ====
    g = b.get("讀這張名片", "{{1.id}}")
    G = g["id"]
    owner = sp(G, "拍攝者 LINE ID", "[].plain_text")
    save_fields = [fv(n, t, cut(f"1.{k}", ln)) for k, n, t, ln in FIELDS]
    save_fields += [
        {"key": "標籤", "type": "multi_select", "value": '{{if(1.tags; split(1.tags; ","); emptyarray)}}'},
        fv("狀態", "select", "已確認"), {"key": "確認時間", "type": "date", "date": {"start": "{{now}}", "includeTime": True}}]
    save_flow = [g, b.router("是不是自己拍的", [
        (flt("自己拍的", [[c(owner, "text:equal", USER), c("{{1.name}}", "exist")]]), [
            b.update("確認存入", "{{1.id}}", save_fields), b.respond("回傳已存入", '{"ok":true}')]),
        (flt("別人拍的", [[c(owner, "text:notequal", USER)]]), [
            b.respond("回傳不是你的", '{"ok":false,"error":"not_yours"}', "403")]),
    ])]

    flow = [
        webhook(HOOK, "名片頁面送來的請求"),
        b.router("請求格式", [
            # 格式不對就直接擋下，不先問 LINE，減少被亂打時消耗的額度
            (flt("格式不對", [[c("{{1.t}}", "notexist")], [c("{{1.a}}", "text:notequal", a) for a in ACTS]]), [
                b.respond("回傳格式不對", '{"ok":false,"error":"bad_request"}', "400")]),
            (flt("格式正確", [[c("{{1.t}}", "exist"), act(a)] for a in ACTS]), [
                verify,
                b.router("身分驗證", [
                    (flt("不是本系統的憑證", [[c("{{2.data.client_id}}", "text:notequal", CHANNEL)]]), [
                        b.respond("回傳驗證失敗", '{"ok":false,"error":"auth"}', "401")]),
                    (flt("身分驗證成功", [[auth_ok]]), [profile, b.router("依動作分流", [
                        (flt("送出照片", [[act("submit")]]), submit_flow),
                        (flt("待確認清單", [[act("list")]]), list_flow),
                        (flt("確認存入", [[act("save")]]), save_flow),
                    ])]),
                ])]),
        ]),
    ]
    return blueprint("名片", flow)


def webhook(hook, name):
    return {"id": 1, "module": "gateway:CustomWebHook", "version": 1, "parameters": {"hook": hook, "maxResults": 1},
            "mapper": {}, "metadata": {"designer": {"x": -300, "y": 0, "name": name}, "parameters": [
                {"name": "hook", "type": "hook:gateway-webhook", "label": "Webhook", "required": True},
                {"name": "maxResults", "type": "number", "label": "Maximum number of results"}]}}


def blueprint(name, flow):
    return {"name": name, "flow": flow, "metadata": {
        "instant": True, "version": 1, "designer": {"orphans": []},
        "scenario": {"dlq": True, "slots": None, "dataloss": False, "maxErrors": 3, "autoCommit": True,
                     "roundtrips": 1, "sequential": False, "confidential": False,
                     "freshVariables": False, "autoCommitTriggerLast": True}}}


def main():
    out = ROOT / "make" / ("example" if "--example" in sys.argv else "")
    out.mkdir(parents=True, exist_ok=True)
    p = out / "名片.blueprint.json"
    p.write_text(json.dumps(build(), ensure_ascii=False, indent=1), encoding="utf-8")
    print(p, p.stat().st_size)
    if "--test-hook" in sys.argv:
        t = out / "名片_測試.blueprint.json"
        t.write_text(json.dumps(build(int(sys.argv[sys.argv.index("--test-hook") + 1])), ensure_ascii=False, indent=1),
                     encoding="utf-8")
        print(t, t.stat().st_size)


if __name__ == "__main__":
    main()
