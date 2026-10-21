// 本機預覽用的模擬後端：不連 LINE、不連 Make。正式網址（GitHub Pages）不會載入這個檔案
(() => {
  const svg = (bg, text) => "data:image/svg+xml," + encodeURIComponent(
    `<svg xmlns="http://www.w3.org/2000/svg" width="350" height="200"><rect width="350" height="200" fill="${bg}"/><text x="20" y="110" font-size="26" fill="#333">${text}</text></svg>`);
  const cards = [
    { id: "m1", status: "待確認", name: "王小明", company: "晨光科技股份有限公司", title: "業務經理", dept: "業務部",
      mobile: "0912-345-678", phone: "02-2345-6789", email: "ming@example.com", address: "台北市信義區松仁路 100 號",
      web: "https://example.com", other: "LINE ID：ming88", place: "2026 智慧城市展", note: "", tags: [],
      card: svg("#f6f1e3", "王小明｜晨光科技"), photo: svg("#dfe9f3", "合照"), time: "2026-10-21T03:10:00Z" },
    { id: "m2", status: "辨識失敗", name: "", company: "", title: "", dept: "", mobile: "", phone: "", email: "", address: "",
      web: "", other: "", place: "2026 智慧城市展", note: "名片反光", tags: [], card: svg("#eee", "（模糊）"), photo: "", time: "2026-10-21T03:05:00Z" },
    { id: "m3", status: "處理中", name: "", company: "", title: "", dept: "", mobile: "", phone: "", email: "", address: "",
      web: "", other: "", place: "2026 智慧城市展", note: "", tags: [], card: "", photo: "", time: "2026-10-21T03:12:00Z" },
  ];
  const wait = ms => new Promise(r => setTimeout(r, ms));
  window.MOCK_API = {
    async submit(f) {
      await wait(900);
      cards.unshift({ id: f.rid, status: "處理中", name: "", company: "", title: "", dept: "", mobile: "", phone: "", email: "",
        address: "", web: "", other: "", place: f.place, note: f.note, tags: [], card: "data:image/jpeg;base64," + f.card,
        photo: f.photo ? "data:image/jpeg;base64," + f.photo : "", time: new Date().toISOString() });
      return { ok: true };
    },
    async list() { await wait(400); return cards.map(c => ({ ...c, tags: [...c.tags] })); },
    async save(id, f) {
      await wait(600);
      const c = cards.find(x => x.id === id);
      Object.assign(c, f, { tags: f.tags ? f.tags.split(",") : [], status: "已確認" });
      return { ok: true };
    },
  };
})();
