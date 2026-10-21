"""產生會員模組（選單切換）的 Make 藍圖，輸出到 make/：

- 會員_API.blueprint.json：「朕宏｜會員 API」
    LIFF 會員頁面：a=me 我的身分（順便校正選單）｜a=apply 申請入會（欄位 t 是 LINE Access Token）
    Notion 核准連結：a=approve 核准入會｜a=sync 依身分套用選單（欄位 k 是密鑰、id 是名冊頁面 ID）
- 會員_LINE事件.blueprint.json：「朕宏｜會員：LINE 事件」加好友就建一筆潛在會員；封鎖時標記
- 會員_建立圖文選單.blueprint.json：「朕宏｜會員：建立圖文選單」訪客選單設為預設、會員選單設別名 member，
    清掉舊選單後把所有正式會員重新綁到新的會員選單

身分與選單：潛在會員、審核中、停權 → 訪客選單（預設，不綁個人）；正式會員 → 會員選單（別名 member，綁個人）。
所有換選單的動作最後都把「目前選單」「選單同步時間」寫回 Notion，打開會員頁面時發現對不上就自動校正。

執行：python tools/make_member_blueprint.py
"""
import json
import sys

from make_blueprint import (CFG, CONN_NOTION, HTTP_DEFAULTS, LN, ORIGIN, PREFIX, ROOT, blueprint, c, cut, flt, fv,
                            sp, webhook)

M = CFG["member"]
DS = M["data_source_id"]
KEY = M["approve_key"]
CHANNEL = LN["login_channel_id"]
CONN_LINE = LN["messaging_connection_id"]
MEMBER_LIFF = f"https://liff.line.me/{M['liff_id']}"
NAMECARD_LIFF = f"https://liff.line.me/{LN['liff_id']}"
ALIAS = "member"
PANEL = 620   # 選單左側協會標誌區的寬度，和 tools/make_member_richmenu.py 一致
# 身分 → 頁面上的狀態代號
STATE = '{{switch(%s; "審核中"; "pending"; "正式會員"; "member"; "停權"; "banned"; "guest")}}'
# 申請表單欄位：頁面代號、Notion 欄位、型別、長度上限（和 liff/member/app.js 的 FIELDS 對應）
APPLY_FIELDS = [("name", "姓名", "title", 60), ("phone", "電話", "phone_number", 40), ("email", "Email", "email", 120),
                ("company", "公司／事務所", "rich_text", 120), ("title", "職稱", "rich_text", 60),
                ("note", "申請說明", "rich_text", 1000)]
LINE_META = [{"name": "__IMTCONN__", "type": "account:line2", "label": "Connection", "required": True}]
NOTION_META = [{"name": "__IMTCONN__", "type": "account:notion2,notion3", "label": "Connection", "required": True}]


def enc(expr):
    """自由文字放進回應 JSON 前先 URL 編碼，頁面收到後解碼（Make 沒有 JSON 跳脫函式）"""
    return "{{encodeURL(" + expr[2:-2] + ")}}"


class B:
    """藍圖組裝器：依序配發模組編號和畫布座標。"""

    def __init__(self, start=100):
        self.next_id = start
        self.y = 0

    def nid(self):
        self.next_id += 1
        return self.next_id

    def meta(self, name, params=None):
        self.y += 150
        m = {"designer": {"x": 900, "y": self.y, "name": name}}
        if params:
            m["parameters"] = params
        return m

    def ignore(self):
        return {"id": self.nid(), "module": "builtin:Ignore", "version": 1, "mapper": None,
                "metadata": {"designer": {"x": 1200, "y": self.y}}}

    def respond(self, name, body, status="200", html=False):
        ctype = "text/html; charset=utf-8" if html else "application/json; charset=utf-8"
        headers = [{"key": "Content-Type", "value": ctype}]
        if not html:
            headers.append({"key": "Access-Control-Allow-Origin", "value": ORIGIN})
        return {"id": self.nid(), "module": "gateway:WebhookRespond", "version": 1, "parameters": {},
                "mapper": {"status": status, "body": body, "headers": headers}, "metadata": self.meta(name)}

    def notion(self, module, name, mapper, onerror=None):
        d = {"id": self.nid(), "module": f"notion:{module}", "version": 1, "mapper": mapper,
             "metadata": self.meta(name, NOTION_META), "parameters": {"__IMTCONN__": CONN_NOTION}}
        if onerror:
            d["onerror"] = onerror
        return d

    def find_member(self, name, uid):
        return self.notion("searchObjects1", name, {"limit": "1", "select": "data_source_item", "data_source": DS,
                                                     "filter": [[c("LINE User ID |&*^%$#@| rich_text", "text:equals", uid)]]})

    def get(self, name, page, onerror=None):
        return self.notion("getADatabaseItem", name, {"page": page, "getBy": "data_source", "select": "map"}, onerror)

    def create(self, name, fields):
        return self.notion("createDataSourceItem", name, {"fields": fields, "select": "map", "data_source": DS})

    def update(self, name, page, fields):
        return self.notion("updateADatabaseItem", name,
                           {"page": page, "fields": fields, "select": "map", "updateBy": "data_source", "data_source": DS})

    def line(self, name, url, method="GET", body=None, onerror=None):
        mapper = {"url": url, "method": method, "headers": []}
        if body is not None:
            mapper["body"] = json.dumps(body)
            mapper["headers"] = [{"key": "Content-Type", "value": "application/json"}]
        d = {"id": self.nid(), "module": "line:makeApiCall", "version": 1, "parameters": {"__IMTCONN__": CONN_LINE},
             "mapper": mapper, "metadata": self.meta(name, LINE_META)}
        if onerror:
            d["onerror"] = onerror
        return d

    def router(self, name, routes):
        mid = self.nid()
        rs = []
        for f, mods in routes:
            mods = [dict(m) for m in mods]
            mods[0]["filter"] = f
            rs.append({"flow": mods})
        self.y += 150
        return {"id": mid, "module": "builtin:BasicRouter", "version": 1, "mapper": None,
                "metadata": {"designer": {"x": 600, "y": self.y, "name": name}}, "routes": rs}


def now(k):
    return {"key": k, "type": "date", "date": {"start": "{{now}}", "includeTime": True}}


def html(title, text):
    return ('<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            '<body style="font-family:system-ui,sans-serif;max-width:520px;margin:40px auto;padding:0 20px;line-height:1.6">'
            f"<h2>{title}</h2><p>{text}</p><p style=\"color:#888\">可以關閉這個分頁，回到 Notion。</p></body>")


def link_member(b, uid, page, label, onfail_html=False):
    """綁定會員選單：先用別名取得選單編號，再綁給這個人；成功後把「目前選單」寫回 Notion。"""
    fail = [b.respond(f"回傳換選單失敗（{label}）", html("⚠ 選單沒有換成功", "LINE 上找不到會員選單。請先在 Make 執行「建立圖文選單」，再點一次「套用身分」。"), "500", True), b.ignore()] \
        if onfail_html else [b.ignore()]
    alias = b.line(f"取得會員選單編號（{label}）", f"/v2/bot/richmenu/alias/{ALIAS}", onerror=fail)
    return [alias,
            b.line(f"綁定會員選單（{label}）", f"/v2/bot/user/{uid}/richmenu/{{{{{alias['id']}.body.richMenuId}}}}", "POST"),
            b.update(f"記下目前選單：會員（{label}）", page, [fv("目前選單", "select", "會員"), now("選單同步時間")])]


def unlink(b, uid, page, label):
    """解除個人綁定，回到預設的訪客選單（本來就沒有綁定時 LINE 會回錯誤，略過）"""
    return [b.update(f"記下目前選單：訪客（{label}）", page, [fv("目前選單", "select", "訪客"), now("選單同步時間")]),
            b.line(f"解除會員選單（{label}）", f"/v2/bot/user/{uid}/richmenu", "DELETE", onerror=[b.ignore()])]


def build_api():
    b = B()
    respond_json = lambda name, body, status="200": b.respond(name, body, status)

    # ==== Notion 核准連結：GET ?a=approve|sync&k=密鑰&id=名冊頁面 ====
    def admin_flow(action):
        g = b.get(f"讀名冊（{action}）", "{{1.id}}",
                  onerror=[b.respond(f"回傳找不到（{action}）", html("⚠ 找不到這筆名冊", "連結可能不完整，請從 Notion 重新點一次。"), "404", True), b.ignore()])
        G = g["id"]
        ident, name, uid, page = sp(G, "身分", ".name"), sp(G, "姓名", "[].plain_text"), sp(G, "LINE User ID", "[].plain_text"), f"{{{{{G}.id}}}}"
        no_line = (flt(f"沒有 LINE 帳號（{action}）", [[c(uid, "notexist")]]), [
            b.respond(f"回傳沒有 LINE（{action}）", html("⚠ 這筆沒有 LINE 帳號", "這位不是從 LINE 加入的，無法換選單。"), "400", True)])
        if action == "approve":
            return [g, b.router("可否核准", [
                (flt("審核中，核准", [[c(ident, "text:equal", "審核中"), c(uid, "exist")]]), [
                    b.update("改成正式會員", page, [fv("身分", "select", "正式會員"), now("核准時間")]),
                    *link_member(b, uid, page, "核准", onfail_html=True),
                    b.respond("回傳已核准", html(f"✅ 已核准 {name}", "身分已改成正式會員，LINE 選單已換成會員版。"), "200", True)]),
                (flt("不是審核中", [[c(ident, "text:notequal", "審核中"), c(uid, "exist")]]), [
                    b.respond("回傳不需核准", html("ℹ️ 不需要核准", f"{name} 目前的身分是「{ident}」。"), "200", True)]),
                no_line])]
        return [g, b.router("依身分套用選單", [
            (flt("正式會員：會員選單", [[c(ident, "text:equal", "正式會員"), c(uid, "exist")]]), [
                *link_member(b, uid, page, "套用", onfail_html=True),
                b.respond("回傳已套用會員選單", html(f"✅ {name}：會員選單", "LINE 選單已換成會員版。"), "200", True)]),
            (flt("其他身分：訪客選單", [[c(ident, "text:notequal", "正式會員"), c(uid, "exist")]]), [
                b.respond("回傳已套用訪客選單", html(f"✅ {name}：訪客選單", f"身分是「{ident}」，LINE 選單已換回訪客版。"), "200", True),
                *unlink(b, uid, page, "套用")]),
            no_line])]

    # ==== LIFF：先驗證 Access Token（屬於本系統的 LINE Login channel）再取得使用者編號 ====
    def line_get(mid, url, name, headers=()):
        return {"id": mid, "module": "http:ActionSendData", "version": 3, "parameters": {"handleErrors": False},
                "mapper": {"url": url, "method": "get", "serializeUrl": False, "shareCookies": False,
                           "parseResponse": True, "headers": list(headers), "qs": [], **HTTP_DEFAULTS},
                "metadata": {"designer": {"x": 0 if mid == 2 else 150, "y": 0 if mid == 2 else 150, "name": name}},
                "onerror": [respond_json(f"回傳驗證失敗（{name}）", '{"ok":false,"error":"auth"}', "401"), b.ignore()]}
    verify = line_get(2, "https://api.line.me/oauth2/v2.1/verify?access_token={{encodeURL(1.t)}}", "向 LINE 驗證 Access Token")
    profile = line_get(4, "https://api.line.me/v2/profile", "向 LINE 取得使用者編號", [{"name": "Authorization", "value": "Bearer {{1.t}}"}])
    UID, DISPLAY = "{{4.data.userId}}", "{{4.data.displayName}}"
    w = b.find_member("找我的名冊", UID)
    W = w["id"]
    w_ident, w_menu, w_page = sp(W, "身分", ".name"), sp(W, "目前選單", ".name"), f"{{{{{W}.id}}}}"
    exist, none = c(f"{{{{{W}.id}}}}", "exist"), c(f"{{{{{W}.id}}}}", "notexist")

    def body(state, src):
        """回應頁面的會員資料。src(k) 給出欄位的 Make 運算式；潛在會員不回姓名（那是 LINE 名稱，不是本名）"""
        parts = ['"ok":true', f'"state":"{state}"', f'"line":"{{{{encodeURL({DISPLAY[2:-2]})}}}}"']
        parts += [f'"{k}":"{enc(src(k)) if src(k) else ""}"' for k, *_ in APPLY_FIELDS]
        return "{" + ",".join(parts) + "}"
    from_w = lambda k: sp(W, dict((a, n) for a, n, *_ in APPLY_FIELDS)[k], "" if k in ("phone", "email") else "[].plain_text")
    w_state = STATE % w_ident[2:-2]
    me_body = body(w_state, lambda k: ('{{if(' + w_ident[2:-2] + ' = "潛在會員"; ""; ' + from_w(k)[2:-2] + ')}}') if k == "name" else from_w(k))
    is_member, not_member = c(w_ident, "text:equal", "正式會員"), c(w_ident, "text:notequal", "正式會員")

    me_flow = [b.router("我的身分（順便校正選單）", [
        (flt("還沒有名冊", [[none]]), [
            b.create("新增潛在會員（頁面）", [fv("姓名", "title", "（LINE）" + DISPLAY), fv("身分", "select", "潛在會員"),
                                        fv("LINE 顯示名稱", "rich_text", DISPLAY), fv("LINE User ID", "rich_text", UID),
                                        fv("目前選單", "select", "訪客")]),
            respond_json("回傳訪客", body("guest", lambda k: ""))]),
        # 先回應頁面再換選單：換選單出錯也不會讓頁面卡住
        (flt("正式會員但選單不是會員", [[exist, is_member, c(w_menu, "text:notequal", "會員")]]), [
            respond_json("回傳我的身分（校正成會員選單）", me_body), *link_member(b, UID, w_page, "校正")]),
        (flt("不是會員但選單是會員", [[exist, not_member, c(w_menu, "text:equal", "會員")]]), [
            respond_json("回傳我的身分（校正成訪客選單）", me_body), *unlink(b, UID, w_page, "校正")]),
        (flt("選單正確", [[exist, is_member, c(w_menu, "text:equal", "會員")], [exist, not_member, c(w_menu, "text:notequal", "會員")]]), [
            respond_json("回傳我的身分", me_body)]),
    ])]

    apply_fields = [fv(n, t, cut(f"1.{k}", ln)) for k, n, t, ln in APPLY_FIELDS]
    apply_fields += [fv("身分", "select", "審核中"), now("申請時間"), fv("LINE 顯示名稱", "rich_text", DISPLAY)]
    pending_body = body("pending", lambda k: f"{{{{1.{k}}}}}")
    can_apply = [c(w_ident, "text:equal", "潛在會員")], [c(w_ident, "text:equal", "審核中")]
    apply_flow = [b.router("申請入會", [
        (flt("新申請（還沒有名冊）", [[none]]), [
            b.create("新增名冊（審核中）", apply_fields + [fv("LINE User ID", "rich_text", UID), fv("目前選單", "select", "訪客")]),
            respond_json("回傳審核中（新）", pending_body)]),
        (flt("潛在會員或審核中：更新申請", [[exist] + g for g in can_apply]), [
            b.update("更新申請資料（審核中）", w_page, apply_fields), respond_json("回傳審核中", pending_body)]),
        (flt("已是會員或停權", [[exist, c(w_ident, "text:notequal", "潛在會員"), c(w_ident, "text:notequal", "審核中")]]), [
            respond_json("回傳目前身分（申請）", me_body)]),
    ])]

    act = lambda a: c("{{1.a}}", "text:equal", a)
    key_ok = c("{{1.k}}", "text:equal", KEY)
    flow = [
        webhook(M["hook_id"], "會員頁面與核准連結送來的請求"),
        b.router("請求種類", [
            (flt("核准連結：核准", [[act("approve"), key_ok, c("{{1.id}}", "exist")]]), admin_flow("approve")),
            (flt("核准連結：套用身分", [[act("sync"), key_ok, c("{{1.id}}", "exist")]]), admin_flow("sync")),
            (flt("核准連結：密鑰不對", [[act("approve"), c("{{1.k}}", "text:notequal", KEY)], [act("sync"), c("{{1.k}}", "text:notequal", KEY)]]), [
                b.respond("回傳密鑰不對", html("⛔ 連結無效", "請從 Notion 會員名冊重新點連結。"), "403", True)]),
            (flt("會員頁面", [[c("{{1.t}}", "exist"), act("me")], [c("{{1.t}}", "exist"), act("apply")]]), [
                verify,
                b.router("身分驗證", [
                    (flt("不是本系統的憑證", [[c("{{2.data.client_id}}", "text:notequal", CHANNEL)]]), [
                        respond_json("回傳驗證失敗", '{"ok":false,"error":"auth"}', "401")]),
                    (flt("身分驗證成功", [[c("{{2.data.client_id}}", "text:equal", CHANNEL)]]), [profile, w, b.router("依動作分流", [
                        (flt("我的身分", [[act("me")]]), me_flow),
                        (flt("申請入會", [[act("apply")]]), apply_flow),
                    ])]),
                ])]),
            (flt("格式不對", [[c("{{1.a}}", "notexist")],
                              [c("{{1.a}}", "text:notequal", a) for a in ("approve", "sync", "me", "apply")],
                              [act("me"), c("{{1.t}}", "notexist")], [act("apply"), c("{{1.t}}", "notexist")]]), [
                respond_json("回傳格式不對", '{"ok":false,"error":"bad_request"}', "400")]),
        ]),
    ]
    return blueprint(PREFIX + "會員 API", flow)


def build_events():
    """LINE 事件：加好友（follow）就在名冊建一筆潛在會員；封鎖（unfollow）時標記。只處理每次送來的第一個事件。"""
    b = B()
    uid, typ = "{{1.events[1].source.userId}}", "{{1.events[1].type}}"
    w = b.find_member("找名冊", uid)
    w["filter"] = flt("只處理加好友、封鎖", [[c(typ, "text:equal", "follow")], [c(typ, "text:equal", "unfollow")]])
    W = w["id"]
    exist, none = c(f"{{{{{W}.id}}}}", "exist"), c(f"{{{{{W}.id}}}}", "notexist")
    prof = b.line("取得 LINE 名稱", f"/v2/bot/profile/{uid}")
    flow = [
        {"id": 1, "module": "line:watchMessages", "version": 1, "mapper": {},
         "metadata": {"designer": {"x": -300, "y": 0, "name": "LINE 事件"},
                      "parameters": [{"name": "__IMTHOOK__", "type": "hook:line", "label": "Webhook", "required": True}]},
         "parameters": {"__IMTHOOK__": M["events_hook_id"]}},
        w,
        b.router("依事件分流", [
            (flt("新好友", [[c(typ, "text:equal", "follow"), none]]), [
                prof,
                b.create("新增潛在會員", [fv("姓名", "title", f"（LINE）{{{{{prof['id']}.body.displayName}}}}"),
                                      fv("身分", "select", "潛在會員"), fv("好友狀態", "select", "好友中"),
                                      fv("LINE 顯示名稱", "rich_text", f"{{{{{prof['id']}.body.displayName}}}}"),
                                      fv("LINE User ID", "rich_text", uid), fv("目前選單", "select", "訪客"), now("加入好友時間")])]),
            (flt("重新加好友", [[c(typ, "text:equal", "follow"), exist]]), [
                b.update("改回好友中", f"{{{{{W}.id}}}}", [fv("好友狀態", "select", "好友中")])]),
            (flt("封鎖", [[c(typ, "text:equal", "unfollow"), exist]]), [
                b.update("標記已封鎖", f"{{{{{W}.id}}}}", [fv("好友狀態", "select", "已封鎖")])]),
        ]),
    ]
    bp = blueprint(PREFIX + "會員：LINE 事件", flow)
    return bp


def build_menu():
    """建立訪客選單（設為所有人的預設）和會員選單（別名 member）；清掉其他舊選單；把所有正式會員重新綁到新的會員選單。
    圖片從 GitHub Pages 下載（tools/make_member_richmenu.py 產生），LINE 規定 2500×843、1MB 以內。"""
    b = B(10)
    uri = lambda u: {"type": "uri", "uri": u}
    box = lambda x, w_: {"x": x, "y": 0, "width": w_, "height": 843}
    about = {"bounds": box(0, PANEL), "action": uri(MEMBER_LIFF + "?v=about")}
    cw = (2500 - PANEL) // 3
    guest_areas = [about, {"bounds": box(PANEL, 2500 - PANEL), "action": uri(MEMBER_LIFF)}]
    member_areas = [about,
                    {"bounds": box(PANEL, cw), "action": uri(NAMECARD_LIFF)},
                    {"bounds": box(PANEL + cw, cw), "action": uri(NAMECARD_LIFF + "?v=review")},
                    {"bounds": box(PANEL + 2 * cw, 2500 - PANEL - 2 * cw), "action": uri(MEMBER_LIFF)}]

    def make(name, img, areas, label):
        g = {"id": b.nid(), "module": "http:ActionGetFile", "version": 3, "parameters": {"handleErrors": False},
             "mapper": {"url": f"{ORIGIN}/line-namecard/assets/{img}", "method": "get", "serializeUrl": False, "shareCookies": False},
             "metadata": b.meta(f"下載{label}圖片")}
        m = {"id": b.nid(), "module": "line:createARichMenu", "version": 1, "parameters": {"__IMTCONN__": CONN_LINE},
             "mapper": {"name": name, "chatBarText": "選單", "selected": True, "height": 843, "areas": areas,
                        "data": f"{{{{{g['id']}.data}}}}", "filename": img},
             "metadata": b.meta(f"建立{label}", LINE_META)}
        return g, m

    gg, gm = make("guest", "richmenu_guest.png", guest_areas, "訪客選單")
    mg, mm = make("member", "richmenu_member.png", member_areas, "會員選單")
    G, Mm = gm["id"], mm["id"]
    lst = b.line("列出所有圖文選單", "/v2/bot/richmenu/list")
    feed = {"id": b.nid(), "module": "builtin:BasicFeeder", "version": 1, "mapper": {"array": f"{{{{{lst['id']}.body.richmenus}}}}"},
            "metadata": b.meta("逐張檢查")}
    F = feed["id"]
    members = b.notion("searchObjects1", "找所有正式會員", {"limit": "1000", "select": "data_source_item", "data_source": DS,
                                                       "filter": [[c("身分 |&*^%$#@| select", "select:equals", "正式會員")]]})
    MB = members["id"]
    flow = [gg, gm, b.line("設為所有人的預設選單（訪客）", f"/v2/bot/user/all/richmenu/{{{{{G}.richMenuId}}}}", "POST"),
            mg, mm,
            b.router("設定會員選單別名", [
                # 已有別名時更新成功、新建失敗；第一次部署時相反，各自出錯就略過
                (flt("更新別名", [[c(f"{{{{{Mm}.richMenuId}}}}", "exist")]]), [
                    b.line(f"更新別名 {ALIAS}", f"/v2/bot/richmenu/alias/{ALIAS}", "POST", {"richMenuId": f"{{{{{Mm}.richMenuId}}}}"}, onerror=[b.ignore()])]),
                (flt("新建別名", [[c(f"{{{{{Mm}.richMenuId}}}}", "exist")]]), [
                    b.line(f"新建別名 {ALIAS}", "/v2/bot/richmenu/alias", "POST",
                           {"richMenuAliasId": ALIAS, "richMenuId": f"{{{{{Mm}.richMenuId}}}}"}, onerror=[b.ignore()])]),
            ]),
            b.router("收尾", [
                # 刪除舊選單時，LINE 會自動解除所有人身上的舊綁定（苗栗 10/14 舊選單卡住的教訓）
                (flt("清掉舊選單", [[c(f"{{{{{Mm}.richMenuId}}}}", "exist")]]), [
                    lst, feed,
                    b.line("刪除舊選單", f"/v2/bot/richmenu/{{{{{F}.richMenuId}}}}", "DELETE", onerror=[b.ignore()])]),
                (flt("正式會員重新綁定", [[c(f"{{{{{Mm}.richMenuId}}}}", "exist")]]), [
                    members,
                    b.line("綁定新的會員選單", "/v2/bot/user/" + sp(MB, "LINE User ID", "[].plain_text") + f"/richmenu/{{{{{Mm}.richMenuId}}}}",
                           "POST", onerror=[b.ignore()]),
                    b.update("記下目前選單：會員（重建）", f"{{{{{MB}.id}}}}", [fv("目前選單", "select", "會員"), now("選單同步時間")])]),
            ])]
    # 刪除舊選單要排除剛建好的兩張
    flow[-1]["routes"][0]["flow"][2]["filter"] = flt("不是新的兩張", [[
        c(f"{{{{{F}.richMenuId}}}}", "text:notequal", f"{{{{{G}.richMenuId}}}}"),
        c(f"{{{{{F}.richMenuId}}}}", "text:notequal", f"{{{{{Mm}.richMenuId}}}}")]])
    bp = blueprint(PREFIX + "會員：建立圖文選單", flow)
    bp["metadata"]["instant"] = False
    return bp


def main():
    out = ROOT / "make"
    out.mkdir(exist_ok=True)
    for fname, bp in (("會員_API.blueprint.json", build_api()), ("會員_LINE事件.blueprint.json", build_events()),
                      ("會員_建立圖文選單.blueprint.json", build_menu())):
        p = out / fname
        p.write_text(json.dumps(bp, ensure_ascii=False, indent=1), encoding="utf-8")
        print(fname, p.stat().st_size)


if __name__ == "__main__":
    main()
