// ===== 設定：LIFF ID 與 API 網址。正式網址（GitHub Pages）一律用真資料；本機預覽才載入 mock.js 的模擬資料 =====
// 拍照、待確認、確認存入都送到同一個 Make 情境「名片」，用欄位 a 分辨動作
const CONFIG = { liffId: "2012132715-XYXSuHpi", apiUrl: "https://hook.us2.make.com/0fc7kjyq1dx7ke1lxvly82lwfng96gci" };
// 只有在正式網址（GitHub Pages）才啟動 LIFF；本機預覽時略過
const IN_LIFF_HOST = location.hostname.endsWith("github.io");

// 名片欄位：頁面用的代號 → Notion 欄位名稱（Make 依名稱讀寫，名稱不能改）
const FIELDS = [
  ["name", "姓名"], ["company", "公司"], ["title", "職稱"], ["dept", "部門"],
  ["mobile", "手機"], ["phone", "電話"], ["email", "Email"], ["address", "地址"],
  ["web", "網站"], ["other", "其他聯絡方式"], ["place", "認識場合"], ["note", "備註"],
];
const TAGS = ["客戶", "合作夥伴", "廠商", "其他"];
// Make 建立名片時先放的暫時姓名（tools/make_blueprint.py 的 PENDING_NAME），頁面上當成空白
const PENDING_NAME = "（待辨識）";
const STATUS = { "處理中": ["run", "辨識中"], "待確認": ["wait", "待確認"], "辨識失敗": ["fail", "請手動填寫"], "已確認": ["done", "已確認"] };
// 照片先在手機上縮小再送出：Make 的 webhook 一次最多收 5MB，名片字也夠清楚
const MAX_EDGE = 1600, JPEG_Q = 0.82;

const $ = s => document.querySelector(s);
const esc = s => String(s == null ? "" : s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const wait = ms => new Promise(r => setTimeout(r, ms));

// ===== 正式後端：Make 情境「名片」。用表單格式送出，瀏覽器不會先送 CORS 預檢 =====
class ApiError extends Error { constructor(code) { super(code); this.code = code; } }
async function post(fields) {
  // 送 Access Token：每次開啟 LIFF 都會更新、有效 12 小時；Make 會向 LINE 確認它屬於本系統並取得使用者編號
  const token = liff.getAccessToken();
  if (!token) throw new ApiError("no_token");
  const body = new URLSearchParams({ ...fields, t: token });
  const res = await fetch(CONFIG.apiUrl, { method: "POST", body });
  let data;
  try { data = await res.json(); } catch (e) { throw new ApiError("server"); }
  if (!data.ok) throw new ApiError(data.error || "server");
  return data;
}
// Notion 欄位值（Make 原樣轉出的 properties_value）轉成一般文字
const txt = v => Array.isArray(v) ? v.map(x => x.plain_text || (x.text && x.text.content) || x.name || "").join("") : (v && v.name) || (typeof v === "string" ? v : "");
const photo = v => { const f = Array.isArray(v) && v[0]; return f ? ((f.file && f.file.url) || (f.external && f.external.url) || f.url || "") : ""; };
const real = {
  submit: f => post({ a: "submit", ...f }),
  async list() {
    const d = await post({ a: "list" });
    return (d.cards || []).map(r => {
      const p = r.properties_value || {}, c = { id: r.id, status: txt(p["狀態"]) || "處理中" };
      for (const [k, n] of FIELDS) c[k] = txt(p[n]);
      if (c.name === PENDING_NAME) c.name = "";
      c.tags = Array.isArray(p["標籤"]) ? p["標籤"].map(x => x.name) : [];
      c.card = photo(p["名片照片"]); c.photo = photo(p["合照"]); c.time = r.created_time || "";
      return c;
    }).sort((a, b) => b.time.localeCompare(a.time));
  },
  save: (id, f) => post({ a: "save", id, ...f }),
};
let api = real;

// ===== 狀態 =====
const params = new URLSearchParams(location.search);
const S = {
  tab: params.get("v") === "review" ? "review" : "shoot",
  shot: { card: null, photo: null },   // { b64, url }
  place: "", note: "",
  queue: [],                            // 背景上傳中的 { rid, thumb, f, state: sending|fail }
  cards: null, edit: null, busy: false,
};
try { S.place = localStorage.getItem("place") || ""; } catch (e) {}

// ===== 照片：開相機 → 縮小 → JPEG（base64） =====
async function shrink(file) {
  const url = URL.createObjectURL(file);
  try {
    const img = await new Promise((ok, fail) => { const i = new Image(); i.onload = () => ok(i); i.onerror = fail; i.src = url; });
    const k = Math.min(1, MAX_EDGE / Math.max(img.naturalWidth, img.naturalHeight));
    const c = document.createElement("canvas");
    c.width = Math.round(img.naturalWidth * k); c.height = Math.round(img.naturalHeight * k);
    c.getContext("2d").drawImage(img, 0, 0, c.width, c.height);
    const data = c.toDataURL("image/jpeg", JPEG_Q);
    return { b64: data.slice(data.indexOf(",") + 1), url: data };
  } finally { URL.revokeObjectURL(url); }
}
function newRid() {
  const r = new Uint32Array(2); crypto.getRandomValues(r);
  return "R" + Date.now().toString(36) + r[0].toString(36) + r[1].toString(36);
}

// ===== 送出：馬上清空畫面讓現場拍下一位，上傳在背景跑 =====
function submitShot() {
  if (!S.shot.card) return;
  const f = { rid: newRid(), card: S.shot.card.b64, photo: S.shot.photo ? S.shot.photo.b64 : "", place: S.place.trim(), note: S.note.trim() };
  S.queue.push({ rid: f.rid, thumb: S.shot.card.url, f, state: "sending" });
  S.shot = { card: null, photo: null }; S.note = "";
  toast("已送出，可以拍下一位");
  render(); upload(f.rid);
}
async function upload(rid) {
  const q = S.queue.find(x => x.rid === rid); if (!q) return;
  q.state = "sending"; render();
  for (let i = 0; i < 2; i++) {
    try {
      await api.submit(q.f);
      S.queue = S.queue.filter(x => x.rid !== rid); render();
      api.list().then(c => { S.cards = c; render(); }).catch(() => {});   // 更新「待確認」的數字
      return;
    } catch (e) {
      if (e instanceof ApiError && (e.code === "auth" || e.code === "no_token")) { handleApiError(e); return; }
      await wait(1500);
    }
  }
  q.state = "fail"; render();
}
// 還有照片在上傳時，提醒不要關掉頁面
window.addEventListener("beforeunload", e => { if (S.queue.some(q => q.state === "sending")) { e.preventDefault(); e.returnValue = ""; } });

// ===== 畫面 =====
function render() {
  document.querySelectorAll(".tabs button").forEach(b => {
    b.classList.toggle("on", b.dataset.tab === S.tab);
    if (b.dataset.tab === "review") {
      const n = (S.cards || []).filter(c => c.status !== "已確認").length;
      b.innerHTML = `✅ 待確認${n ? `<span class="badge">${n}</span>` : ""}`;
    }
  });
  if (S.tab === "shoot") renderShoot();
  else if (S.edit) renderEdit();
  else renderList();
}
function shotBox(kind, label, sub, icon) {
  const s = S.shot[kind];
  return `<label class="shot ${kind === "card" ? "card" : ""} ${s ? "has" : ""}">
    <input type="file" accept="image/*" capture="environment" data-shot="${kind}">
    ${s ? `<img src="${s.url}" alt=""><span class="redo">重拍</span>`
        : `<span class="big">${icon}</span><b>${label}</b><small>${sub}</small>`}
  </label>`;
}
function renderShoot() {
  $("#app").innerHTML = `
    <div class="shots">
      ${shotBox("card", "① 拍名片", "名片放平、四邊入鏡", "🪪")}
      ${shotBox("photo", "② 拍合照", "可以不拍", "🤝")}
    </div>
    <label class="f">認識場合（會記住，下一位自動帶入）<input id="place" value="${esc(S.place)}" placeholder="例如：2026 智慧城市展"></label>
    <label class="f">備註（可不填）<textarea id="note" placeholder="例如：對 AI 客服有興趣">${esc(S.note)}</textarea></label>
    ${S.queue.length ? `<div class="queue">${S.queue.map(q => `
      <div class="q ${q.state === "fail" ? "fail" : ""}"><img src="${q.thumb}" alt="">
        <span>${q.state === "fail" ? "上傳失敗" : "上傳中…請先不要關閉頁面"}</span>
        ${q.state === "fail" ? `<button data-retry="${q.rid}">重送</button>` : ""}</div>`).join("")}</div>` : ""}
    <p class="hint">送出後就可以拍下一位。辨識在背景進行，有空時到「待確認」檢查。</p>`;
  $("#bar").hidden = false;
  $("#barIn").innerHTML = `<button class="primary" id="send" ${S.shot.card ? "" : "disabled"}>送出</button>`;
}
function renderList() {
  $("#bar").hidden = true;
  if (!S.cards) { $("#app").innerHTML = `<p class="empty">讀取中…</p>`; loadList(); return; }
  const todo = S.cards.filter(c => c.status !== "已確認");
  if (!todo.length) { $("#app").innerHTML = `<p class="empty">沒有待確認的名片 🎉<br><button class="back" id="reload">重新整理</button></p>`; return; }
  $("#app").innerHTML = `<div class="list">${todo.map(c => {
    const [cls, label] = STATUS[c.status] || STATUS["處理中"];
    return `<button class="item" data-open="${c.id}" ${c.status === "處理中" ? "disabled" : ""}>
      ${c.card ? `<img src="${esc(c.card)}" alt="">` : `<span class="ph"></span>`}
      <div><b>${esc(c.name || "（還沒有姓名）")}</b><small>${esc([c.company, c.title].filter(Boolean).join("・") || c.place)}</small></div>
      <span class="st ${cls}">${label}</span></button>`;
  }).join("")}</div>
  <p class="hint">「辨識中」通常不到一分鐘。<button class="back" id="reload">重新整理</button></p>`;
}
function renderEdit() {
  const c = S.edit;
  $("#app").innerHTML = `
    <button class="back" id="backList">← 回清單</button>
    <div class="photos">
      ${c.card ? `<img src="${esc(c.card)}" data-zoom alt="名片">` : `<span></span>`}
      ${c.photo ? `<img src="${esc(c.photo)}" data-zoom alt="合照">` : `<span></span>`}
    </div>
    ${c.status === "辨識失敗" ? `<p class="hint" style="color:var(--red)">AI 沒有讀出這張名片，請看照片手動填寫。</p>` : ""}
    ${FIELDS.map(([k, n]) => `<label class="f">${n}${k === "note" || k === "address" || k === "other"
        ? `<textarea data-k="${k}">${esc(c[k])}</textarea>`
        : `<input data-k="${k}" value="${esc(c[k])}" ${k === "email" ? 'type="email"' : k === "mobile" || k === "phone" ? 'type="tel"' : ""}>`}</label>`).join("")}
    <label class="f">標籤</label>
    <div class="chips">${TAGS.map(t => `<button data-tag="${t}" class="${c.tags.includes(t) ? "on" : ""}">${t}</button>`).join("")}</div>`;
  $("#bar").hidden = false;
  $("#barIn").innerHTML = `<button class="primary" id="save" ${S.busy ? "disabled" : ""}>${S.busy ? "存入中…" : "確認存入"}</button>`;
}
async function loadList() {
  try { S.cards = await api.list(); render(); }
  catch (e) { if (!handleApiError(e)) $("#app").innerHTML = `<div class="blocked"><h2>暫時無法讀取</h2><p>請稍後按重新整理。</p><button class="back" id="reload">重新整理</button></div>`; }
}
function toast(msg) {
  const t = document.createElement("div"); t.className = "toast"; t.textContent = msg;
  document.body.append(t); setTimeout(() => t.remove(), 2200);
}

// ===== 操作 =====
document.addEventListener("change", async e => {
  const k = e.target.dataset && e.target.dataset.shot;
  if (!k || !e.target.files[0]) return;
  try { S.shot[k] = await shrink(e.target.files[0]); } catch (x) { toast("這張照片讀不到，請重拍"); }
  render();
});
document.addEventListener("input", e => {
  if (e.target.id === "place") { S.place = e.target.value; try { localStorage.setItem("place", S.place); } catch (x) {} }
  if (e.target.id === "note") S.note = e.target.value;
  if (e.target.dataset.k && S.edit) S.edit[e.target.dataset.k] = e.target.value;
});
document.addEventListener("click", async e => {
  const t = e.target.closest("button,[data-zoom],.zoom"); if (!t) return;
  if (t.classList.contains("zoom")) { t.remove(); return; }
  if (t.dataset.tab) { S.tab = t.dataset.tab; S.edit = null; if (S.tab === "review") S.cards = null; render(); return; }
  if (t.id === "send") return submitShot();
  if (t.dataset.retry) return upload(t.dataset.retry);
  if (t.id === "reload") { S.cards = null; render(); return; }
  if (t.dataset.open) { S.edit = { ...S.cards.find(c => c.id === t.dataset.open) }; S.edit.tags = [...S.edit.tags]; render(); scrollTo(0, 0); return; }
  if (t.id === "backList") { S.edit = null; render(); return; }
  if (t.dataset.zoom !== undefined && t.tagName === "IMG") {
    const z = document.createElement("div"); z.className = "zoom"; z.innerHTML = `<img src="${esc(t.src)}" alt="">`; document.body.append(z); return;
  }
  if (t.dataset.tag && S.edit) {
    const i = S.edit.tags.indexOf(t.dataset.tag);
    i < 0 ? S.edit.tags.push(t.dataset.tag) : S.edit.tags.splice(i, 1); render(); return;
  }
  if (t.id === "save" && !S.busy) {
    const c = S.edit;
    if (!c.name.trim()) { toast("請填姓名"); return; }
    const f = { tags: c.tags.join(",") };
    for (const [k] of FIELDS) f[k] = (c[k] || "").trim();
    S.busy = true; render();
    try { await api.save(c.id, f); S.busy = false; S.edit = null; S.cards = null; toast(`${c.name} 已存入`); render(); }
    catch (x) { S.busy = false; if (!handleApiError(x)) { toast(x.code === "not_yours" ? "這張不是你拍的，不能修改" : "存入失敗，請再按一次"); render(); } }
  }
});

// ===== LIFF 與錯誤處理（沿用苗栗現場頁面的做法） =====
async function initLiff() {
  await liff.init({ liffId: CONFIG.liffId });
  if (!liff.isLoggedIn()) { liff.login({ redirectUri: location.href }); return false; }
  return true;
}
function handleApiError(e) {
  if (!(e instanceof ApiError)) return false;
  if (e.code === "auth" || e.code === "no_token") {
    // 只自動重新登入一次；兩分鐘內又失敗就停下來顯示原因，避免無限重新整理、一直消耗 Make 額度
    let last = 0;
    try { last = +sessionStorage.getItem("relogin") || 0; } catch (x) {}
    if (e.code === "auth" && Date.now() - last > 120000) {
      try { sessionStorage.setItem("relogin", String(Date.now())); } catch (x) {}
      if (liff.isInClient()) location.reload(); else { liff.logout(); liff.login({ redirectUri: location.href }); }
      return true;
    }
    $("#bar").hidden = true;
    $("#app").innerHTML = `<div class="blocked"><h2>無法確認您的身分</h2><p>${e.code === "no_token" ? "LINE 沒有提供身分憑證。請關閉頁面，從 LINE 重新開啟。" : "LINE 身分驗證沒有通過。"}</p></div>`;
    return true;
  }
  if (e.code === "not_allowed") {
    $("#bar").hidden = true;
    $("#app").innerHTML = `<div class="blocked"><h2>尚未開通</h2><p>名片功能限內部同仁使用，請洽管理者開通。</p></div>`;
    return true;
  }
  return false;
}
function loadScript(src) {
  return new Promise((ok, fail) => { const s = document.createElement("script"); s.src = src; s.onload = ok; s.onerror = fail; document.body.append(s); });
}
(async () => {
  if (IN_LIFF_HOST) {
    try { if (!(await initLiff())) return; }
    catch (e) { $("#app").innerHTML = `<div class="blocked"><h2>無法開啟</h2><p>請從 LINE 開啟這個頁面。</p></div>`; return; }
  } else {
    await loadScript("mock.js"); api = window.MOCK_API;
  }
  render();
  if (S.tab === "shoot") api.list().then(c => { S.cards = c; render(); }).catch(() => {});
})();
