/* AI Avatar Studio — operator UI (Vietnamese). Vanilla JS, no framework. */
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const api = async (path, opts = {}) => {
  const r = await fetch(path, { headers: { "Content-Type": "application/json" }, ...opts });
  let data = {};
  try { data = await r.json(); } catch (e) { /* empty */ }
  if (!r.ok && !data.error) data.error = `HTTP ${r.status}`;
  return data;
};
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, c =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const fmtDur = (sec) => {
  sec = Math.round(sec || 0);
  if (sec < 60) return `${sec}s`;
  const m = Math.floor(sec / 60), s = sec % 60;
  return `${m}m ${s}s`;
};
const toast = (msg, kind = "") => {
  const t = document.createElement("div");
  t.className = `toast ${kind}`;
  t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(() => t.remove(), kind === "bad" ? 7000 : 4200);
};

// Vietnamese job/technical states. Internal enums stay English in the backend.
const STATUS_LABEL = {
  queued: "Đang chờ", preparing_audio: "Đang tạo giọng đọc", preparing_avatar: "Đang chuẩn bị AI Avatar",
  rendering: "Đang tạo video", encoding: "Đang xử lý video", verifying: "Đang kiểm tra kết quả",
  complete: "Hoàn tất", failed: "Lỗi", cancelled: "Đã hủy", timed_out: "Quá thời gian",
  "done": "Hoàn tất", "failed": "Lỗi",
};
const statusLabel = (s) => STATUS_LABEL[s] || s || "";

// Avatar type → Vietnamese.
const TYPE_VI = { "Close Up": "Cận cảnh", "Full Body": "Toàn thân", Unknown: "Không rõ" };

// Quality level → {label, css class, rank}.
const QLEVEL = {
  "RẤT TỐT": { cls: "accent", rank: 5, short: "Rất tốt" },
  "TỐT": { cls: "good", rank: 4, short: "Tốt" },
  "CẢNH BÁO": { cls: "warn", rank: 2, short: "Cảnh báo" },
  "KHÔNG KHUYẾN NGHỊ": { cls: "bad", rank: 1, short: "Không khuyến nghị" },
  "CHƯA ĐỦ DỮ LIỆU": { cls: "muted", rank: 0, short: "Chưa đủ dữ liệu" },
  "CHƯA CÓ DỮ LIỆU": { cls: "muted", rank: 0, short: "Chưa có dữ liệu" },
};
const qMeta = (q) => QLEVEL[q] || QLEVEL["CHƯA CÓ DỮ LIỆU"];
// Production confidence (from REAL render history — separate from source quality).
const PROD_VI = {
  "CAO": { cls: "good", short: "Production: cao" },
  "TRUNG BÌNH": { cls: "warn", short: "Production: trung bình" },
  "CHƯA KIỂM CHỨNG": { cls: "muted", short: "Chưa kiểm chứng" },
};

// Tiny localStorage helpers.
const ls = {
  get: (k, d) => { try { return localStorage.getItem(k) || d; } catch (e) { return d; } },
  set: (k, v) => { try { localStorage.setItem(k, v); } catch (e) {} },
};

const state = {
  view: "quick", status: null, avatars: [], selectedAvatar: null,
  scriptText: "", scriptInfo: null, voiceId: "", voiceMeta: null, voiceChecked: false,
  splitMode: "full", prepState: null, jobFilter: "all",
  libFilter: "all", libSort: "quality", libSearch: "",
};

// --------------------------------------------------------------------------- //
async function loadStatus() {
  state.status = await api("/api/system/status");
  renderTopbar(); renderSysstatMini();
}
function renderTopbar() {
  const s = state.status; if (!s) return;
  let cls = "bad", txt = "CHƯA SẴN SÀNG";
  if (s.truth_valid && s.renderer_ready && s.musetalk_ready) { cls = "good"; txt = "SẴN SÀNG"; }
  else if (s.truth_valid) { cls = "warn"; txt = "MỘT PHẦN"; }
  $("#statusDot").className = "dot " + cls;
  $("#statusText").textContent = txt;
}
function renderSysstatMini() {
  const s = state.status; if (!s) return;
  const g = (s.gpus || []).map(x => `GPU${x.id} ${x.state === "BUSY" ? "đang chạy" : "sẵn sàng"}`).join(" · ") || "—";
  $("#sysstatMini").innerHTML = `
    <div class="r"><span>Bộ máy tạo video</span><span>${s.renderer_ready ? "Sẵn sàng" : "—"}</span></div>
    <div class="r"><span>MuseTalk</span><span>${s.musetalk_ready ? "Sẵn sàng" : "—"}</span></div>
    <div class="r"><span>ElevenLabs</span><span>${s.elevenlabs_connected ? "Đã kết nối" : "Chưa kết nối"}</span></div>
    <div class="r"><span>${esc(g)}</span><span></span></div>
    <div class="r"><span>Cấu hình chất lượng</span><span>${s.truth_valid ? "Hợp lệ" : "Lỗi"}</span></div>`;
}
async function loadAvatars() {
  const r = await api("/api/avatars");
  state.avatars = r.avatars || [];
}

// Navigation
function switchView(v) {
  state.view = v;
  $$(".nav-item").forEach(b => b.classList.toggle("active", b.dataset.view === v));
  if (v === "quick") renderQuick();
  if (v === "create") renderCreate();
  if (v === "library") renderLibrary();
  if (v === "history") renderHistory();
  if (v === "settings") renderSettings();
}

// --------------------------------------------------------------------------- //
// QUICK RENDER
function productionProfileHTML() {
  const t = state.status?.truth; if (!t) return "";
  return `<div class="profile-banner">
    <div class="pl"><b>MuseTalk v1.5</b> · ${t.resolution_width}×${t.resolution_height} · ${t.fps} FPS</div>
    <div class="pl">Đồng bộ môi: <b>ĐÃ KHÓA</b></div>
    <div class="pl">Trạng thái: <b>Đã xác thực</b></div>
    <div class="locked">🔒 ĐÃ KHÓA</div>
  </div>`;
}
async function renderQuick() {
  const el = $("#content");
  const readyAvs = state.avatars.filter(a => a.ready);
  el.innerHTML = `
    <h1 class="view-title">Tạo video nhanh</h1>
    <p class="view-sub">AI Avatar → Kịch bản → Giọng đọc → Kiểm tra → Tạo video</p>
    ${productionProfileHTML()}
    <div class="card">
      <h2>AI Avatar</h2>
      <div class="avatar-select">
        <select id="qAvatar"></select>
        <button class="ghost" onclick="switchView('create')">＋ Thêm AI Avatar mới</button>
      </div>
      <div id="qAvatarPick"></div>
    </div>

    <div class="card">
      <h2>Kịch bản</h2>
      <div class="row">
        <label style="flex:1">Tải lên file .docx hoặc .txt
          <input type="file" id="qFile" accept=".txt,.docx" />
        </label>
        ${state.scriptText ? `<button class="tiny ghost" onclick="clearScript()">Xóa</button>` : ""}
      </div>
      <div class="section-label">hoặc dán nội dung kịch bản</div>
      <textarea id="qScript" rows="6" placeholder="Dán kịch bản vào đây…"></textarea>
      <div id="qScriptInfo" class="muted" style="margin-top:8px;font-size:12px"></div>
    </div>

    <div class="card">
      <h2>ElevenLabs Voice ID</h2>
      <label>Copy Voice ID từ ElevenLabs và dán vào đây — ghi nhớ trên máy này</label>
      <div class="row">
        <input id="qVoice" placeholder="ElevenLabs Voice ID" style="flex:1" />
        <button id="qCheckVoice" onclick="checkVoice()">Kiểm tra giọng</button>
        <button class="ghost" onclick="previewVoice()">▶ Nghe thử giọng</button>
      </div>
      <div id="qVoiceInfo" style="margin-top:8px;font-size:12px"></div>
      <audio id="qPreview" style="display:none;margin-top:8px;width:100%" controls></audio>
    </div>

    <div class="card">
      <h2>Thời lượng</h2>
      <label>Độ dài video</label>
      <select id="qSplit">
        <option value="full">Toàn bộ kịch bản</option>
        <option value="30s">30 giây đầu</option>
        <option value="1min">1 phút đầu</option>
        <option value="3min">3 phút đầu</option>
        <option value="auto">Tự động chia phần (giữ nguyên câu)</option>
      </select>
      <div id="qSegPreview"></div>
    </div>

    <div class="actions">
      <button class="secondary" id="qTestBtn" onclick="renderTest10s()">⏱ KIỂM TRA 10 GIÂY</button>
      <button class="primary big" id="qRenderBtn" onclick="renderFull()">⬇ TẠO VIDEO</button>
      <span class="muted" style="font-size:11px;align-self:center">Ctrl+Enter = tạo video</span>
    </div>`;
  const sel = $("#qAvatar");
  if (!readyAvs.length) {
    sel.innerHTML = `<option value="">Chưa có AI Avatar</option>`;
    $("#qAvatarPick").innerHTML = `<div class="avatar-pick empty">Chưa có AI Avatar nào sẵn sàng.<br>
      <button class="ghost" style="margin-top:8px" onclick="switchView('create')">＋ Tạo AI Avatar trước</button></div>`;
  } else {
    sel.innerHTML = `<option value="">— Chọn AI Avatar —</option>` +
      readyAvs.map(a => {
        const q = qMeta(a.quality_status).short;
        return `<option value="${esc(a.avatar_id)}">${esc(a.avatar_id)} · ${q} · ${esc(TYPE_VI[a.avatar_type] || a.avatar_type)}</option>`;
      }).join("");
  }
  sel.onchange = () => {
    const a = state.avatars.find(x => x.avatar_id === sel.value);
    state.selectedAvatar = a; ls.set("studio_avatar", sel.value);
    renderAvatarPick(a);
  };
  const lastAid = ls.get("studio_avatar", "");
  if (lastAid && readyAvs.some(a => a.avatar_id === lastAid)) { sel.value = lastAid; sel.onchange(); }
  else if (state.selectedAvatar && readyAvs.some(a => a.avatar_id === state.selectedAvatar.avatar_id)) { sel.value = state.selectedAvatar.avatar_id; sel.onchange(); }
  $("#qScript").value = state.scriptText;
  $("#qScript").oninput = (e) => { state.scriptText = e.target.value; updateScriptInfo(); };
  $("#qVoice").value = state.voiceId;
  $("#qVoice").oninput = (e) => { state.voiceId = e.target.value; state.voiceChecked = false; state.voiceMeta = null; ls.set("studio_voiceId", e.target.value); };
  $("#qSplit").value = state.splitMode;
  $("#qSplit").onchange = (e) => { state.splitMode = e.target.value; updateSegPreview(); };
  $("#qFile").onchange = async (e) => {
    const f = e.target.files[0]; if (!f) return;
    const fd = new FormData(); fd.append("file", f);
    const r = await fetch("/api/script/parse", { method: "POST", body: fd });
    const d = await r.json();
    if (d.ok) {
      state.scriptText = d.text; state.scriptInfo = d;
      $("#qScript").value = d.text; updateScriptInfo();
      toast(`Đã tải ${d.source}: ${d.words} từ, ${d.estimated_duration_str}`, "good");
    } else toast(d.error || "Không đọc được kịch bản", "bad");
  };
  updateScriptInfo(); updateSegPreview();
}
function renderAvatarPick(a) {
  const box = $("#qAvatarPick"); if (!box) return;
  if (!a) { box.innerHTML = ""; return; }
  const q = a.quality_status;
  const qm = qMeta(q);
  const strengths = (a.quality_strengths || []).slice(0, 2).map(s => `✓ ${esc(s)}`).join("  ");
  box.innerHTML = `<div class="avatar-pick">
    <img src="/api/avatars/${esc(a.avatar_id)}/thumbnail" onerror="this.style.opacity=.3" />
    <div class="ap-meta">
      <div class="ap-name">${esc(a.avatar_id)} <span class="tag ${qm.cls}">${esc(qm.short)}</span></div>
      <div class="ap-sub"><span class="tag good">SẴN SÀNG</span> ${esc(TYPE_VI[a.avatar_type] || a.avatar_type)} · ${a.frame_count} khung hình</div>
      ${strengths ? `<div class="ap-sub" style="margin-top:4px">${strengths}</div>` : ""}
    </div>
  </div>`;
}
function clearScript() {
  state.scriptText = ""; state.scriptInfo = null;
  renderQuick();
}
async function updateSegPreview() {
  const box = $("#qSegPreview"); if (!box) return;
  const txt = state.scriptText.trim();
  if (!txt || state.splitMode === "full") { box.innerHTML = ""; return; }
  if (state.splitMode === "auto") {
    box.innerHTML = `<div class="seg-preview"><span class="seg-chip">Đang tính số phần…</span></div>`;
    const r = await api("/api/script/split", { method: "POST", body: JSON.stringify({ script_text: txt, mode: "auto" }) });
    if (!r.ok) { box.innerHTML = ""; return; }
    const chips = r.parts.map(p => `<span class="seg-chip"><b>${esc(p.label)}</b> ${p.words} từ · ${esc(p.duration_str)}</span>`).join("");
    box.innerHTML = `<div class="hint">Tự động chia thành <b>${r.total_parts}</b> phần:</div><div class="seg-preview">${chips}</div>`;
  } else {
    const label = { "30s": "30 giây đầu", "1min": "1 phút đầu", "3min": "3 phút đầu" }[state.splitMode];
    box.innerHTML = `<div class="hint">Chỉ tạo <b>${label}</b> của kịch bản.</div>`;
  }
}
function updateScriptInfo() {
  const txt = state.scriptText; const info = $("#qScriptInfo");
  if (!txt) { if (info) info.textContent = ""; return; }
  const words = txt.split(/\s+/).filter(Boolean).length;
  const dur = words / 3.0;
  if (info) info.textContent = `${words} từ · ~${fmtDur(dur)} giọng đọc`;
  updateSegPreview();
}
async function checkVoice() {
  const vid = $("#qVoice").value.trim();
  if (!vid) return toast("Nhập Voice ID trước", "warn");
  const info = $("#qVoiceInfo"); info.innerHTML = `<span class="muted">Đang kiểm tra…</span>`;
  const r = await api("/api/voice/check", { method: "POST", body: JSON.stringify({ voice_id: vid }) });
  if (r.ok) {
    state.voiceChecked = true; state.voiceMeta = r;
    const name = r.name ? `<b>${esc(r.name)}</b>` : `<span class="muted">(tên không hiển thị với tài khoản này)</span>`;
    const labels = r.labels || {};
    const lang = labels.language ? ` · ${esc(labels.language)}` : "";
    info.innerHTML = `<span class="tag good">✓ Đã tìm thấy giọng</span> ${name}${lang}`;
  } else {
    state.voiceChecked = false; state.voiceMeta = null;
    info.innerHTML = `<span class="tag bad">✗ Không hợp lệ</span> <span class="muted">${esc(r.error || "Không tìm thấy Voice ID này hoặc giọng không khả dụng.")}</span>`;
  }
}
async function previewVoice() {
  const vid = $("#qVoice").value.trim();
  const txt = state.scriptText;
  if (!vid) return toast("Nhập Voice ID trước", "warn");
  if (!txt) return toast("Nhập kịch bản trước", "warn");
  toast("Đang tạo thử ~9 giây giọng đọc…");
  const r = await api("/api/voice/preview", { method: "POST", body: JSON.stringify({ voice_id: vid, script_text: txt }) });
  if (r.ok) {
    const a = $("#qPreview"); a.src = r.preview_url; a.style.display = "block"; a.play();
  } else toast(r.error || "Không nghe thử được (không dùng giọng thay thế)", "bad");
}
async function renderTest10s() {
  const av = $("#qAvatar").value, vid = $("#qVoice").value.trim(), txt = state.scriptText;
  if (!av) return toast("Chọn AI Avatar", "warn");
  if (!vid) return toast("Nhập Voice ID", "warn");
  if (!txt) return toast("Nhập kịch bản", "warn");
  ls.set("studio_voiceId", vid);
  $("#qTestBtn").disabled = true;
  const r = await api("/api/render/test", { method: "POST", body: JSON.stringify({ avatar_id: av, voice_id: vid, script_text: txt, voice_meta: state.voiceMeta }) });
  $("#qTestBtn").disabled = false;
  if (r.ok) { toast("Đã đưa kiểm tra 10 giây vào hàng đợi", "good"); switchView("history"); }
  else toast(r.error || "Không xếp hàng được", "bad");
}
async function renderFull() {
  const av = $("#qAvatar").value, vid = $("#qVoice").value.trim(), txt = state.scriptText;
  if (!av) return toast("Chọn AI Avatar", "warn");
  if (!vid) return toast("Nhập Voice ID", "warn");
  if (!txt) return toast("Nhập kịch bản", "warn");
  ls.set("studio_voiceId", vid);
  $("#qRenderBtn").disabled = true;
  const r = await api("/api/render", { method: "POST", body: JSON.stringify({ avatar_id: av, voice_id: vid, script_text: txt, split_mode: state.splitMode, voice_meta: state.voiceMeta }) });
  $("#qRenderBtn").disabled = false;
  if (r.ok) { toast(`Đã xếp hàng (${(r.job_ids || []).length} phần)`, "good"); switchView("history"); }
  else toast(r.error || "Không xếp hàng được", "bad");
}

// --------------------------------------------------------------------------- //
// CREATE AVATAR
let createState = { videoPath: null, quality: null, override: false, prepAvatarId: null };
async function renderCreate() {
  const el = $("#content");
  el.innerHTML = `
    <h1 class="view-title">Tạo AI Avatar mới</h1>
    <p class="view-sub">Thêm video gốc → hệ thống kiểm tra → đánh giá → chuẩn bị → sẵn sàng</p>
    <div class="card">
      <h2>1. Tải video lên</h2>
      <div class="dropzone" id="cDrop">
        <div class="big">⬆</div>
        <div>Kéo thả video vào đây hoặc bấm để chọn<br><span class="muted2">.mp4 .mov .avi .mkv .webm — tự động kiểm tra khi tải lên</span></div>
        <input type="file" id="cFile" accept="video/*,.mp4,.mov,.avi,.mkv,.webm" hidden />
      </div>
      <div id="cFileLabel" class="muted" style="margin-top:8px;font-size:12px"></div>
    </div>
    <div id="cQuality"></div>
    <div id="cPrepare"></div>`;
  const dz = $("#cDrop");
  dz.onclick = () => $("#cFile").click();
  dz.ondragover = (e) => { e.preventDefault(); dz.classList.add("drag"); };
  dz.ondragleave = () => dz.classList.remove("drag");
  dz.ondrop = (e) => { e.preventDefault(); dz.classList.remove("drag"); if (e.dataTransfer.files[0]) handleCreateFile(e.dataTransfer.files[0]); };
  $("#cFile").onchange = (e) => { if (e.target.files[0]) handleCreateFile(e.target.files[0]); };
  if (createState.prepAvatarId) pollPrep();
}
async function handleCreateFile(f) {
  const fd = new FormData(); fd.append("video", f);
  $("#cFileLabel").innerHTML = `Đang kiểm tra <b>${esc(f.name)}</b>…`;
  const r = await fetch("/api/avatar/analyze", { method: "POST", body: fd });
  const d = await r.json();
  $("#cFileLabel").innerHTML = `${esc(f.name)} · ${d.integrity ? d.integrity.width + "×" + d.integrity.height + " · " + d.integrity.duration + " giây" : ""}`;
  if (d.technical_failure) {
    createState = { videoPath: null, quality: null, override: false, prepAvatarId: null };
    $("#cQuality").innerHTML = `<div class="card"><h2>Lỗi kỹ thuật</h2>
      <div class="bad-box">${esc(d.error || "Không xử lý được video này.")}</div>
      <div class="qhint">Đây là lỗi kỹ thuật, không phải cảnh báo chất lượng — không thể dùng video này.</div></div>`;
    return;
  }
  createState.videoPath = d.video_path;
  createState.quality = d;
  renderQuality(d);
}
function renderQuality(d) {
  const ic = (s) => s === "PASS" ? `<span class="ic pass">✓</span>` :
    s === "WARN" ? `<span class="ic warn">⚠</span>` : `<span class="ic fail">✗</span>`;
  const rows = (d.categories || []).map(c =>
    `<div class="qrow"><span class="ql">${ic(c.status)} ${esc(c.message)}</span></div>`).join("");
  const overallCls = d.overall === "PASS" ? "pass" : d.overall === "WARN" ? "warn" : "fail";
  const overallTxt = d.overall === "PASS" ? "TỐT — nguồn phù hợp." :
    d.overall === "WARN" ? "CẢNH BÁO — dùng được, nhưng chất lượng khẩu hình có thể thấp hơn." : "KÉM — chất lượng thấp; vẫn có thể dùng nếu cần.";
  $("#cQuality").innerHTML = `<div class="card">
    <h2>Đánh giá chất lượng nguồn</h2>${rows}
    <div class="qoverall ${overallCls}">${overallTxt}</div>
    <div class="qhint">${d.overall === "PASS" ? "" : "Cảnh báo chất lượng không chặn việc sử dụng. Bạn vẫn có thể dùng nguồn này."}</div>
    <div class="actions">
      <button class="ghost" onclick="resetCreate()">Chọn video khác</button>
      <button class="primary" onclick="showPrepare()">${d.overall === "PASS" ? "Tiếp tục" : "Vẫn sử dụng video này"}</button>
    </div>
  </div>`;
  if (d.overall !== "PASS") createState.override = true;
}
function resetCreate() { createState = { videoPath: null, quality: null, override: false, prepAvatarId: null }; renderCreate(); }
function showPrepare() {
  const d = createState.quality || {};
  $("#cPrepare").innerHTML = `<div class="card">
    <h2>Chuẩn bị AI Avatar</h2>
    <label>Tên AI Avatar</label>
    <input id="cName" placeholder="vd: doTrang_closeup" value="${esc((d.face_h_ratio||0) >= 0.16 ? "closeup" : "avatar")}" />
    <div class="qhint" style="margin:8px 0">Tên an toàn được tạo tự động. Không ghi đè avatar đã có.</div>
    <div class="actions">
      <button class="primary" id="cPrepBtn" onclick="prepareAvatar()">Chuẩn bị AI Avatar</button>
    </div>
    <div id="cPrepProgress"></div>
  </div>`;
}
async function prepareAvatar() {
  const name = $("#cName").value.trim();
  if (!name) return toast("Nhập tên AI Avatar", "warn");
  const q = createState.quality || {};
  const r = await api("/api/avatar/prepare", { method: "POST", body: JSON.stringify({ video_path: createState.videoPath, avatar_name: name, allow_warning_override: createState.override, quality_result: q.raw, quality_warnings: q.warnings, overall: q.overall }) });
  if (!r.ok) return toast(r.error || "Không chuẩn bị được", "bad");
  createState.prepAvatarId = r.avatar_id;
  $("#cPrepBtn").disabled = true;
  toast("Đang chuẩn bị AI Avatar…", "good");
  pollPrep();
}
async function pollPrep() {
  const aid = createState.prepAvatarId; if (!aid) return;
  const r = await api(`/api/avatar/prepare/${aid}/status`);
  const box = $("#cPrepProgress"); if (!box) return;
  const pct = r.done ? 100 : 35;
  box.innerHTML = `<div class="stage">${esc(r.stage || "Đang xử lý…")}</div>
    <div class="progress"><div style="width:${pct}%"></div></div>
    ${r.error ? `<div class="bad-box">${esc(r.error)}</div>` : ""}
    ${r.done && r.ready ? `<div class="qoverall pass">AI Avatar đã sẵn sàng</div>
      <div class="actions"><button class="primary" onclick="usePrepared('${esc(aid)}')">Dùng AI Avatar này</button></div>` : ""}`;
  if (r.done && r.ready) { await loadAvatars(); return; }
  if (r.done && r.error && !r.ready) return;
  setTimeout(pollPrep, 1500);
}
function usePrepared(aid) {
  const a = state.avatars.find(x => x.avatar_id === aid);
  if (a && a.ready) { state.selectedAvatar = a; toast(`${aid} đã sẵn sàng — đã chọn`, "good"); }
  else toast(`${aid} chưa sẵn sàng`, "warn");
  switchView("quick");
  setTimeout(() => { const sel = $("#qAvatar"); if (sel) { sel.value = aid; sel.onchange(); } }, 50);
}

// --------------------------------------------------------------------------- //
// AVATAR LIBRARY (quality UX)
async function renderLibrary() {
  const el = $("#content");
  const avs = state.avatars;
  // compute real counts
  const ready = avs.filter(a => a.ready).length;
  const counts = { "RẤT TỐT": 0, "TỐT": 0, "CẢNH BÁO": 0, "KHÔNG KHUYẾN NGHỊ": 0, "CHƯA CÓ DỮ LIỆU": 0, "CHƯA ĐỦ DỮ LIỆU": 0 };
  let incomplete = 0, verified = 0;
  avs.forEach(a => { if (!a.ready) incomplete++; else { counts[a.quality_status || "CHƯA CÓ DỮ LIỆU"]++; if (a.render_count > 0) verified++; } });
  el.innerHTML = `
    <h1 class="view-title">Thư viện AI Avatar</h1>
    <p class="view-sub">${ready} AI Avatar sẵn sàng${incomplete ? ` · ${incomplete} chưa hoàn tất` : ""}</p>
    <div class="lib-summary">
      <span><b>${ready}</b> sẵn sàng</span>
      ${counts["RẤT TỐT"] ? `<span class="good"><b>${counts["RẤT TỐT"]}</b> rất tốt</span>` : ""}
      ${counts["TỐT"] ? `<span class="good"><b>${counts["TỐT"]}</b> tốt</span>` : ""}
      ${counts["CẢNH BÁO"] ? `<span class="warn"><b>${counts["CẢNH BÁO"]}</b> có cảnh báo</span>` : ""}
      ${counts["KHÔNG KHUYẾN NGHỊ"] ? `<span class="bad"><b>${counts["KHÔNG KHUYẾN NGHỊ"]}</b> không khuyến nghị</span>` : ""}
      ${(counts["CHƯA CÓ DỮ LIỆU"]+counts["CHƯA ĐỦ DỮ LIỆU"]) ? `<span class="muted"><b>${counts["CHƯA CÓ DỮ LIỆU"]+counts["CHƯA ĐỦ DỮ LIỆU"]}</b> chưa đủ dữ liệu nguồn</span>` : ""}
      ${verified ? `<span class="good"><b>${verified}</b> đã kiểm chứng production</span>` : ""}
      ${incomplete ? `<span class="bad"><b>${incomplete}</b> chưa hoàn tất</span>` : ""}
    </div>
    <div class="lib-controls">
      <input id="libSearch" placeholder="Tìm AI Avatar…" value="${esc(state.libSearch)}" />
      <select id="libSort">
        <option value="quality">Chất lượng tốt nhất</option>
        <option value="newest">Mới nhất</option>
        <option value="name">Tên A–Z</option>
      </select>
      <button class="ghost" onclick="backfillQuality()" id="libBackfill">Đánh giá tất cả</button>
    </div>
    <div class="filter-chips" id="libFilters">
      <span class="fchip ${state.libFilter==='all'?'active':''}" data-f="all">Tất cả</span>
      <span class="fchip ${state.libFilter==='RẤT TỐT'?'active':''}" data-f="RẤT TỐT">Rất tốt</span>
      <span class="fchip ${state.libFilter==='TỐT'?'active':''}" data-f="TỐT">Tốt</span>
      <span class="fchip ${state.libFilter==='CẢNH BÁO'?'active':''}" data-f="CẢNH BÁO">Có cảnh báo</span>
      <span class="fchip ${state.libFilter==='KHÔNG KHUYẾN NGHỊ'?'active':''}" data-f="KHÔNG KHUYẾN NGHỊ">Không khuyến nghị</span>
      <span class="fchip ${state.libFilter==='CHƯA CÓ DỮ LIỆU'?'active':''}" data-f="CHƯA CÓ DỮ LIỆU">Chưa có dữ liệu</span>
      <span class="fchip ${state.libFilter==='ready'?'active':''}" data-f="ready">Sẵn sàng</span>
      <span class="fchip ${state.libFilter==='incomplete'?'active':''}" data-f="incomplete">Chưa hoàn tất</span>
    </div>
    <div class="grid" id="libGrid"></div>`;
  $("#libSort").value = state.libSort;
  $("#libSort").onchange = (e) => { state.libSort = e.target.value; renderLibGrid(); };
  const si = $("#libSearch");
  si.oninput = (e) => { state.libSearch = e.target.value; renderLibGrid(); };
  $$("#libFilters .fchip").forEach(c => c.onclick = () => {
    $$("#libFilters .fchip").forEach(x => x.classList.remove("active"));
    c.classList.add("active"); state.libFilter = c.dataset.f; renderLibGrid();
  });
  renderLibGrid();
}
function renderLibGrid() {
  const grid = $("#libGrid"); if (!grid) return;
  let list = [...state.avatars];
  const q = state.libSearch.trim().toLowerCase();
  if (q) list = list.filter(a => a.avatar_id.toLowerCase().includes(q));
  const f = state.libFilter;
  if (f !== "all") {
    if (f === "ready") list = list.filter(a => a.ready);
    else if (f === "incomplete") list = list.filter(a => !a.ready);
    else list = list.filter(a => (a.quality_status || "CHƯA CÓ DỮ LIỆU") === f);
  }
  // sort
  if (state.libSort === "quality") list.sort((a, b) => (qMeta(b.quality_status).rank - qMeta(a.quality_status).rank) || (b.ready - a.ready));
  else if (state.libSort === "name") list.sort((a, b) => a.avatar_id.localeCompare(b.avatar_id));
  else if (state.libSort === "newest") list.sort((a, b) => (b.created_at || 0) - (a.created_at || 0));
  // recommended: only a GLOBAL recommendation when ALL ready avatars have real
  // source-quality data. If some ready avatars lack quality data, the best
  // evaluated one gets "TỐT NHẤT TRONG NHÓM ĐÃ ĐÁNH GIÁ" — never a global ★.
  const readyAll = state.avatars.filter(a => a.ready);
  const readyWithQuality = readyAll.filter(a => ["RẤT TỐT", "TỐT", "CẢNH BÁO", "KHÔNG KHUYẾN NGHỊ"].includes(a.quality_status));
  const allHaveData = readyAll.length > 0 && readyWithQuality.length === readyAll.length;
  const recCands = readyWithQuality.filter(a => ["RẤT TỐT", "TỐT"].includes(a.quality_status));
  let recId = null, recKind = "";
  if (recCands.length) {
    recId = recCands.sort((a, b) => qMeta(b.quality_status).rank - qMeta(a.quality_status).rank
      || (b.face_h_ratio || 0) - (a.face_h_ratio || 0))[0].avatar_id;
    recKind = allHaveData ? "global" : "partial";
  }
  grid.innerHTML = list.map(a => libraryCardHTML(a, a.avatar_id === recId, recKind)).join("")
    || `<div class="empty"><div class="big">📁</div>Không có AI Avatar phù hợp.</div>`;
}
function libraryCardHTML(a, recommended, recKind) {
  const q = a.quality_status || "CHƯA CÓ DỮ LIỆU";
  const qm = qMeta(q);
  const techBadge = a.ready
    ? `<span class="tag good">SẴN SÀNG</span>`
    : `<span class="tag bad">CHƯA HOÀN TẤT</span>`;
  const prod = PROD_VI[a.production_confidence] || PROD_VI["CHƯA KIỂM CHỨNG"];
  const prodBadge = a.ready && a.render_count > 0
    ? `<span class="tag ${prod.cls}" title="${a.render_count} render thực tế">Đã kiểm chứng (${a.render_count})</span>` : "";
  const strengths = (a.quality_strengths || []).slice(0, 3).map(s => `<div class="qs good">✓ ${esc(s)}</div>`).join("");
  const warns = (a.quality_warnings || []).slice(0, 2).map(s => `<div class="qs warn">⚠ ${esc(s)}</div>`).join("");
  let rec = "";
  if (recommended) {
    if (recKind === "global") rec = `<div class="rec-badge">★ KHUYẾN NGHỊ</div>`;
    else rec = `<div class="rec-badge partial">TỐT NHẤT TRONG NHÓM ĐÃ ĐÁNH GIÁ</div>`;
  }
  const useBtn = a.ready
    ? `<button class="primary" onclick="useAvatar('${esc(a.avatar_id)}')">Sử dụng Avatar</button>`
    : `<button class="primary" disabled title="Chưa hoàn tất">Sử dụng Avatar</button>`;
  const detailBtn = a.ready ? `<button class="ghost" onclick="showQualityDetail('${esc(a.avatar_id)}')">Xem đánh giá chi tiết</button>`
    : `<button class="ghost" onclick="showIncompleteDetail('${esc(a.avatar_id)}')">Chi tiết</button>`;
  return `<div class="avatar-card ${a.ready ? "" : "incomplete"}">
    <div class="ac-thumb">
      <img src="/api/avatars/${esc(a.avatar_id)}/thumbnail" onerror="this.style.opacity=.25" />
      ${rec}
    </div>
    <div class="ac-body">
      <div class="ac-name">${esc(a.avatar_id)}</div>
      <div class="ac-sub">${esc(TYPE_VI[a.avatar_type] || a.avatar_type || "Không rõ")}</div>
      <div class="ac-tags">${techBadge} <span class="tag ${qm.cls}">${esc(qm.short)}</span> ${prodBadge}</div>
      ${strengths}${warns}
      ${!a.ready ? `<div class="qs muted">AI Avatar này thiếu dữ liệu cần thiết, chưa thể render.</div>` : ""}
      <div class="ac-actions">
        ${useBtn}
        ${detailBtn}
      </div>
    </div>
  </div>`;
}
function useAvatar(aid) {
  const a = state.avatars.find(x => x.avatar_id === aid);
  if (!a || !a.ready) return toast("AI Avatar chưa sẵn sàng", "warn");
  state.selectedAvatar = a; ls.set("studio_avatar", aid);
  switchView("quick");
  setTimeout(() => { const sel = $("#qAvatar"); if (sel) { sel.value = aid; sel.onchange(); } }, 50);
  toast(`Đã chọn ${aid}`, "good");
}
async function backfillQuality() {
  const btn = $("#libBackfill"); if (btn) { btn.disabled = true; btn.textContent = "Đang đánh giá…"; }
  toast("Đang đánh giá tất cả avatar có video nguồn…");
  const r = await api("/api/avatars/quality/backfill", { method: "POST", body: JSON.stringify({ force: false }) });
  await loadAvatars();
  if (btn) { btn.disabled = false; btn.textContent = "Đánh giá tất cả"; }
  toast(`Đã đánh giá ${(r.results || []).length} avatar`, "good");
  renderLibrary();
}
async function showIncompleteDetail(aid) {
  modal(`<h2>${esc(aid)}</h2>
    <div class="bad-box">AI Avatar này ở trạng thái <b>CHƯA HOÀN TẤT</b> — thiếu dữ liệu cần thiết (full_imgs, mask, latents, hoặc avator_info.json) và chưa thể render.</div>
    <div class="hint">Trạng thái kỹ thuật tách biệt với chất lượng. Không hiển thị đánh giá chất lượng khi chưa hoàn tất chuẩn bị.</div>
    <div class="actions"><button class="ghost" onclick="closeModal()">Đóng</button></div>`);
}
async function showQualityDetail(aid) {
  modal(`<h2>Đánh giá AI Avatar: ${esc(aid)}</h2><div class="muted">Đang phân tích video nguồn…</div>`);
  const q = await api(`/api/avatars/${aid}/quality`, { method: "POST", body: JSON.stringify({}) });
  if (!q || q.error) { modal(`<h2>Đánh giá: ${esc(aid)}</h2><div class="bad-box">${esc(q?.error || "Không đánh giá được.")}</div><div class="actions"><button class="ghost" onclick="closeModal()">Đóng</button></div>`); return; }
  renderQualityModal(aid, q);
}
function renderQualityModal(aid, q) {
  const qm = qMeta(q.quality_status);
  const dims = (q.dimensions || []).map(d => `
    <div class="dim-row">
      <div class="dim-label">${esc(d.label)}</div>
      <div class="dim-level ${qMeta(d.level).cls}">${esc(qMeta(d.level).short || d.level)}</div>
      <div class="dim-explain">${esc(d.explanation || "")}</div>
    </div>`).join("");
  const strengths = (q.strengths || []).map(s => `<div class="qs good">✓ ${esc(s)}</div>`).join("");
  const warns = (q.warnings || []).map(s => `<div class="qs warn">⚠ ${esc(s)}</div>`).join("");
  const v = q.video || {};
  const videoInfo = v.width ? `<div class="hint">Video nguồn: ${v.width}×${v.height} · ${v.fps} FPS · ${v.duration} giây</div>` : "";
  const provMap = { "RAW_VALIDATOR": "Đánh giá từ video nguồn (validator)", "PREPARED_ANALYSIS": "Phân tích từ dữ liệu đã chuẩn bị", "HISTORICAL_AUDIT": "Báo cáo kiểm chứng cũ", "UNKNOWN": "Chưa rõ nguồn đánh giá" };
  const prov = provMap[q.quality_source] || "Chưa rõ";
  const rh = q.render_history || {};
  const prod = PROD_VI[q.production_confidence] || PROD_VI["CHƯA KIỂM CHỨNG"];
  const prodSection = `<div class="qsection"><div class="qsection-t ${prod.cls}">Độ tin cậy production (từ render thực tế)</div>
    <div class="hint">${q.production_confidence === "CHƯA KIỂM CHỨNG" ? "Chưa có render thực tế nào được ghi nhận." : `Đã có ${rh.total||0} render hoàn tất (DB: ${rh.db_complete||0}, file: ${rh.external||0}).`}</div></div>`;
  const dimsBlock = dims ? `<div class="dims">${dims}</div>` : `<div class="hint">Không đo được chất lượng nguồn (video nguồn gốc không còn).</div>`;
  const advanced = (q.face_h_ratio != null || (q.dimensions || []).some(d => d.value != null)) ? `
    <details class="advanced"><summary>Thông tin kỹ thuật</summary>
      ${q.face_h_ratio != null ? `<div class="kv"><span class="k">face_h_ratio</span><span class="v">${q.face_h_ratio}</span></div>` : ""}
      ${(q.dimensions || []).map(d => d.value != null ? `<div class="kv"><span class="k">${esc(d.key)}</span><span class="v">${esc(d.value)}</span></div>` : "").join("")}
    </details>` : "";
  modal(`<h2>Đánh giá AI Avatar: ${esc(aid)}</h2>
    <div class="dim-overall">Chất lượng nguồn: <span class="tag ${qm.cls}">${esc(qm.short || q.quality_status)}</span></div>
    <div class="hint">Nguồn đánh giá: ${prov}</div>
    <div class="hint">${esc(q.recommendation || "")}</div>
    ${videoInfo}
    ${dimsBlock}
    <div class="qsection"><div class="qsection-t good">Điểm tốt</div>${strengths || `<div class="muted">—</div>`}</div>
    <div class="qsection"><div class="qsection-t warn">Điểm cần lưu ý</div>${warns || `<div class="muted">—</div>`}</div>
    ${prodSection}
    ${advanced}
    <div class="actions">
      <button class="primary" onclick="useAvatarFromModal('${esc(aid)}')">Sử dụng AI Avatar</button>
      <button class="ghost" onclick="closeModal()">Đóng</button>
    </div>`);
}
function useAvatarFromModal(aid) { closeModal(); useAvatar(aid); }
function modal(html) {
  let m = $("#modal"); if (m) m.remove();
  m = document.createElement("div"); m.id = "modal"; m.className = "modal-bg";
  m.innerHTML = `<div class="modal-card"><div class="modal-close" onclick="closeModal()">✕</div>${html}</div>`;
  m.onclick = (e) => { if (e.target === m) closeModal(); };
  document.body.appendChild(m);
}
function closeModal() { const m = $("#modal"); if (m) m.remove(); }

// --------------------------------------------------------------------------- //
// RENDER HISTORY
async function renderHistory() {
  const el = $("#content");
  el.innerHTML = `<h1 class="view-title">Lịch sử render</h1><p class="view-sub">Tất cả job render</p>
    <div class="filter-chips" id="jobFilters">
      <span class="fchip ${state.jobFilter==='all'?'active':''}" data-f="all">Tất cả</span>
      <span class="fchip ${state.jobFilter==='complete'?'active':''}" data-f="complete">Hoàn tất</span>
      <span class="fchip ${state.jobFilter==='active'?'active':''}" data-f="active">Đang chạy</span>
      <span class="fchip ${state.jobFilter==='failed'?'active':''}" data-f="failed">Lỗi / Đã hủy</span>
    </div>
    <div class="jobs" id="jobsList"></div><div class="muted" id="jobsEmpty"></div>`;
  $$("#jobFilters .fchip").forEach(c => c.onclick = () => {
    $$("#jobFilters .fchip").forEach(x => x.classList.remove("active"));
    c.classList.add("active"); state.jobFilter = c.dataset.f; refreshJobs();
  });
  await refreshJobs();
}
async function refreshJobs() {
  const r = await api("/api/render/jobs?limit=100");
  const list = $("#jobsList"); if (!list) return;
  let jobs = r.jobs || [];
  const f = state.jobFilter;
  if (f === "complete") jobs = jobs.filter(j => j.status === "complete");
  else if (f === "active") jobs = jobs.filter(j => ["queued","preparing_audio","rendering","encoding","verifying"].includes(j.status));
  else if (f === "failed") jobs = jobs.filter(j => ["failed","cancelled","timed_out"].includes(j.status));
  if (!jobs.length) { $("#jobsEmpty").textContent = r.jobs && r.jobs.length ? "Không có job phù hợp." : "Chưa có job render nào."; list.innerHTML = ""; return; }
  $("#jobsEmpty").textContent = "";
  list.innerHTML = jobs.map(j => jobCardHTML(j)).join("");
}
function jobCardHTML(j) {
  const stageTxt = j.error ? esc(j.error).slice(0, 160) : statusLabel(j.stage || j.status);
  const thumb = j.status === "complete" && j.output_path
    ? `<video class="jthumb" src="/api/render/jobs/${j.job_id}/preview" muted preload="metadata" playsinline></video>`
    : `<div class="jthumb" style="display:flex;align-items:center;justify-content:center;color:var(--muted2);font-size:18px">${j.status === "failed" ? "✗" : j.status === "timed_out" ? "⏱" : "—"}</div>`;
  let actions = "";
  if (j.status === "complete") actions = `<button class="ghost" onclick="openFolder('${j.job_id}')">Mở thư mục</button>`;
  else if (["failed","cancelled","timed_out"].includes(j.status)) actions = `<button class="ghost" onclick="retryJob('${j.job_id}')">Thử lại</button>`;
  else if (j.status !== "complete") actions = `<button class="danger" onclick="cancelJob('${j.job_id}')">Hủy</button>`;
  const voiceName = j.voice_meta ? (() => { try { return JSON.parse(j.voice_meta).name || ""; } catch (e) { return ""; } })() : "";
  const kindLabel = j.kind === "test10s" ? "Kiểm tra 10s" : (j.script_name || "Đầy đủ");
  return `<div class="job" data-job="${j.job_id}">
    ${thumb}
    <div class="jbody">
      <div class="jtitle">${esc(kindLabel)} · ${esc(j.avatar_id)}${j.gpu_id !== null ? ` · GPU${j.gpu_id}` : ""}</div>
      <div class="jsub">Giọng: ${esc(j.voice_id)}${voiceName ? " · " + esc(voiceName) : ""} · ${fmtDur(j.duration_sec)}</div>
      <div class="fstatus ${j.status}">${statusLabel(j.status)}${j.error ? " · " + stageTxt : ""}</div>
      ${["rendering","encoding","verifying","preparing_audio"].includes(j.status) && j.progress != null ? `<div class="progress" style="margin-top:6px"><div style="width:${j.progress}%"></div></div>` : ""}
    </div>
    <div class="row" style="flex-wrap:nowrap">${actions}
      ${j.status === "complete" ? `<button class="primary" onclick="playJob('${j.job_id}')">▶ Xem video</button>` : ""}
    </div>
  </div>`;
}
async function playJob(id) {
  const j = await api(`/api/render/jobs/${id}`);
  if (!j.output_path) return toast("Không có file", "warn");
  let v = $("#playerModal"); if (v) v.remove();
  v = document.createElement("div"); v.id = "playerModal";
  v.style.cssText = "position:fixed;inset:0;background:rgba(0,0,0,.8);display:flex;align-items:center;justify-content:center;z-index:2000";
  v.innerHTML = `<div style="max-width:90vw"><video class="preview" style="max-width:90vw;max-height:85vh" src="/api/render/jobs/${id}/preview" controls autoplay></video><div style="text-align:center;margin-top:10px"><button class="ghost" onclick="this.closest('#playerModal').remove()">Đóng</button></div></div>`;
  v.onclick = (e) => { if (e.target === v) v.remove(); };
  document.body.appendChild(v);
}
async function openFolder(id) { await api(`/api/render/jobs/${id}/open-folder`, { method: "POST" }); }
async function retryJob(id) { const r = await api(`/api/render/jobs/${id}/retry`, { method: "POST" }); toast(r.ok ? "Đã xếp lại" : (r.error || "Lỗi"), r.ok ? "good" : "bad"); refreshJobs(); }
async function cancelJob(id) { const r = await api(`/api/render/jobs/${id}/cancel`, { method: "POST" }); toast(r.ok ? "Đã hủy" : (r.error || "Lỗi"), r.ok ? "good" : "bad"); refreshJobs(); }

// --------------------------------------------------------------------------- //
// SETTINGS
async function renderSettings() {
  const s = state.status || {};
  const el = $("#content");
  el.innerHTML = `<h1 class="view-title">Cài đặt</h1>
    <div class="card">
      <h2>ElevenLabs</h2>
      <div class="kv"><span class="k">Trạng thái</span><span class="v">${s.elevenlabs_connected ? '<span style="color:var(--good)">● Đã kết nối</span>' : '<span style="color:var(--bad)">● Chưa kết nối</span>'}</span></div>
      <div class="kv"><span class="k">API Key</span><span class="v">${esc(s.elevenlabs_key_masked)}</span></div>
      <div class="kv"><span class="k">Model TTS</span><span class="v">${esc(el_model_id())}</span></div>
      <div id="quotaRow" class="kv"><span class="k">Hạn mức tài khoản</span><span class="v muted">đang kiểm tra…</span></div>
      <div style="margin-top:14px">
        <label>Cập nhật API Key (lưu trong .env, không ghi log)</label>
        <div class="row"><input id="sKey" type="password" placeholder="API key ElevenLabs mới" style="flex:1" />
        <button class="primary" onclick="saveKey()">Cập nhật Key</button></div>
      </div>
    </div>
    <div class="card">
      <h2>Trạng thái hệ thống (chỉ xem)</h2>
      <div class="kv"><span class="k">Bộ máy tạo video</span><span class="v">${s.renderer_ready ? "Sẵn sàng" : "—"}</span></div>
      <div class="kv"><span class="k">MuseTalk v1.5</span><span class="v">${s.musetalk_ready ? "Sẵn sàng" : "—"}</span></div>
      <div class="kv"><span class="k">ElevenLabs</span><span class="v">${s.elevenlabs_connected ? "Đã kết nối" : "Chưa kết nối"}</span></div>
      ${(s.gpus || []).map(g => `<div class="kv"><span class="k">GPU ${g.id} (${esc(g.name)})</span><span class="v">${g.state === "BUSY" ? "Đang chạy" : "Sẵn sàng"}</span></div>`).join("")}
      <div class="kv"><span class="k">Ổ lưu video</span><span class="v">${s.renders_dir_writable ? "Sẵn sàng" : "—"}</span></div>
      <div class="kv"><span class="k">Cấu hình chất lượng</span><span class="v">${s.truth_valid ? "Đã khóa / Hợp lệ" : "Lỗi"}</span></div>
      <div class="kv"><span class="k">Thư mục render</span><span class="v">${esc(s.renders_dir)}</span></div>
    </div>
    <div class="card">
      <h2>Cấu hình chất lượng đã khóa (chỉ xem)</h2>
      ${s.truth ? `<div class="kv"><span class="k">Pipeline</span><span class="v">MuseTalk v1.5</span></div>
      <div class="kv"><span class="k">Độ phân giải</span><span class="v">${s.truth.resolution_width}×${s.truth.resolution_height}</span></div>
      <div class="kv"><span class="k">FPS</span><span class="v">${s.truth.fps}</span></div>
      <div class="kv"><span class="k">CUDA Graph</span><span class="v">${s.truth.cuda_graph ? "Bật" : "Tắt"}</span></div>
      <div class="kv"><span class="k">WOLA (audio dài)</span><span class="v">${s.truth.long_audio_wola ? "Bật" : "Tắt"}</span></div>
      <div class="kv"><span class="k">Feature Coverage Guard</span><span class="v">${s.truth.feature_coverage_assertion ? "Bật" : "Tắt"}</span></div>` : `<div class="muted">Không có dữ liệu cấu hình</div>`}
    </div>`;
  fetch("/api/elevenlabs/quota").then(r => r.json()).then(q => {
    const row = $("#quotaRow"); if (!row) return;
    if (!q.ok) { row.querySelector(".v").textContent = q.error || "không có"; return; }
    const rem = (q.remaining == null) ? "—" : q.remaining.toLocaleString("vi-VN");
    const reset = q.reset_date_utc ? ` · đặt lại ${q.reset_date_utc}` : "";
    row.querySelector(".v").innerHTML = `gói ${esc(q.tier||"—")} · ${q.character_count.toLocaleString("vi-VN")}/${q.character_limit.toLocaleString("vi-VN")} ký tự · <b style="color:${q.remaining>0?'var(--good)':'var(--bad)'}">${rem} còn lại</b>${reset}`;
  }).catch(() => { const row = $("#quotaRow"); if (row) row.querySelector(".v").textContent = "không có"; });
}
function el_model_id() { return state.status?.elevenlabs_model_id || "—"; }
async function saveKey() {
  const key = $("#sKey").value.trim();
  if (!key) return toast("Nhập API key", "warn");
  const r = await api("/api/settings/elevenlabs", { method: "POST", body: JSON.stringify({ api_key: key }) });
  if (r.ok) { toast("Đã lưu key — ElevenLabs đã kết nối", "good"); $("#sKey").value = ""; await loadStatus(); renderSettings(); }
  else toast(r.error || "Lỗi lưu", "bad");
}

// --------------------------------------------------------------------------- //
// Queue bar (live)
async function refreshQueue() {
  const r = await api("/api/system/status");
  if (r && r.active_jobs !== undefined) { state.status = r; renderTopbar(); renderSysstatMini(); }
  const active = (r && r.active_jobs) || [];
  const bar = $("#queueItems"); if (!bar) return;
  if (!active.length) { bar.innerHTML = `<span class="muted">Đang nghỉ</span>`; return; }
  bar.innerHTML = active.map(j => {
    const ic = j.status === "rendering" ? "▶" : j.status === "complete" ? "✓" : "○";
    return `<div class="qitem">${ic} ${esc(j.script_name || j.kind)} ${esc(j.avatar_id)}
      <div class="qbar"><div style="width:${j.progress || 0}%"></div></div>
      <span class="muted">${esc(statusLabel(j.stage || j.status).slice(0, 24))}</span></div>`;
  }).join("");
  if (state.view === "history") refreshJobs();
}

(async function init() {
  $$(".nav-item").forEach(b => b.addEventListener("click", () => switchView(b.dataset.view)));
  state.voiceId = ls.get("studio_voiceId", "");
  document.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter" && state.view === "quick") { e.preventDefault(); renderFull(); }
    if (e.key === "Escape") closeModal();
  });
  await loadStatus();
  await loadAvatars();
  switchView("quick");
  setInterval(refreshQueue, 2500);
  setInterval(loadAvatars, 15000);
})();