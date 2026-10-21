// 本機預覽用的模擬後端：不連 LINE、不連 Make。網址加 ?state=pending｜member｜banned 可以直接看各身分的畫面
(() => {
  const wait = ms => new Promise(r => setTimeout(r, ms));
  const st = new URLSearchParams(location.search).get("state") || "guest";
  let me = { ok: true, state: st, line: "Phil Ko", name: st === "guest" ? "" : "柯小明", phone: st === "guest" ? "" : "0912-345-678",
             email: st === "guest" ? "" : "ming@example.com", company: st === "guest" ? "" : "晨光設計", title: st === "guest" ? "" : "設計總監", note: "" };
  window.MOCK_API = {
    async me() { await wait(400); return { ...me }; },
    async apply(f) { await wait(700); me = { ...me, ...f, state: me.state === "member" ? "member" : "pending" }; return { ...me }; },
  };
})();
