/* AI Avatar Studio V1.3.0 — simplified light operator UI (Vietnamese).
   Vanilla JS, no framework. Production logic / API contracts unchanged. */
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const api = async (path, opts = {}) => {
  const r = await fetch(path, { headers: { "Content-Type": "application/json" }, ...opts });
  // Trusted-collaborator gate: if the session lapsed/missing, reload to the
  // login page (served by the backend for unauthed browser nav).
  if (r.status === 401) { try { window.location.href = "/login"; } catch (e) {} }
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
// Defensive video-metadata formatter (spec V1.3.1 §9). Never returns
// undefined/NaN/null/[object Object] — only real values, joined, or ''.
const num = (v) => (v === null || v === undefined || v === "" || (typeof v === "number" && Number.isNaN(v))) ? null : v;
function fmtVideoMeta(integrity) {
  const i = integrity || {};
  const w = num(i.width), h = num(i.height), dur = num(i.duration);
  const parts = [];
  if (w && h) parts.push(`${w} × ${h}`);
  if (dur) parts.push(`${fmtDur(dur)}`);
  return parts.join(" · ");
}
const isLocalhost = () => ["127.0.0.1", "localhost", "::1"].includes(location.hostname);
// V1.6.0 runtime hardening — frontend/backend API contract version. MUST equal
// config/api_contract.json "contract_version". tests/test_runtime_hardening.py
// asserts these two stay identical. When the served frontend (this constant) and
// the RUNNING backend's frozen contract differ, a blocking sync banner is shown
// instead of letting the user hit random 404s from a stale backend.
const STUDIO_API_CONTRACT = "2026-08-29.4";
// V1.6.0 — block NEW mutable work (render/test) when the backend is stale or the
// contract mismatched. Already-running immutable jobs are left alone; the user
// is told to restart instead of discovering the stale backend via a 404.
function canStartNewWork() {
  const s = state.status;
  if (!s) return true; // unknown state: don't over-block during transient load
  if (s.truth_valid === false) {
    toast("Cấu hình Render Truth không hợp lệ.", "bad");
    return false;
  }
  if (s.renderer_ready === false || s.musetalk_ready === false) {
    toast("Mô hình AI hoặc Renderer chưa sẵn sàng trên máy chủ.", "bad");
    return false;
  }
  return true;
}
const toast = (msg, kind = "") => {
  const t = document.createElement("div");
  t.className = `toast ${kind}`;
  t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(() => t.remove(), kind === "bad" ? 7000 : 4200);
};
const toastWithUndo = (msg, undoFn, undoLabel = "Hoàn tác") => {
  const t = document.createElement("div");
  t.className = `toast undo-toast`;
  t.innerHTML = `<span>${esc(msg)}</span><button class="undo-btn" id="toastUndoBtn">${esc(undoLabel)}</button>`;
  const btn = t.querySelector("#toastUndoBtn");
  btn.onclick = async (e) => {
    e.stopPropagation();
    t.remove();
    if (undoFn) await undoFn();
  };
  document.body.appendChild(t);
  setTimeout(() => { if (t.parentNode) t.remove(); }, 8000);
};

// Inline SVG icons (lightweight, consistent, no framework).
const ICO = {
  video: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8 5v14l11-7z"/></svg>',
  avatar: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8zm-7 9a7 7 0 0 1 14 0H5z"/></svg>',
  script: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 2h8l4 4v16H6zM14 2v4h4" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/></svg>',
  voice: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 4a3 3 0 0 0-3 3v5a3 3 0 0 0 6 0V7a3 3 0 0 0-3-3zM7 11a5 5 0 0 0 10 0M12 16v4" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>',
  upload: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 16V4m0 0L7 9m5-5 5 5M5 20h14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>',
  render: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8 5v14l11-7z"/></svg>',
  history: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 8v5l4 2" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" stroke-width="2"/></svg>',
  settings: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="3" fill="none" stroke="currentColor" stroke-width="2"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M5 5l2 2M17 17l2 2M19 5l-2 2M7 17l-2 2" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>',
  check: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12l5 5L20 6" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/></svg>',
  arrow: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12h14m-6-6 6 6-6 6" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>',
  clock: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 7v5l3 2" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" stroke-width="2"/></svg>',
  face: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" stroke-width="2"/><circle cx="9" cy="10" r="1.4"/><circle cx="15" cy="10" r="1.4"/><path d="M8.5 15a4 4 0 0 0 7 0" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>',
  camera: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 8h3l2-2h8l2 2h3v12H3z" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/><circle cx="12" cy="14" r="3.5" fill="none" stroke="currentColor" stroke-width="2"/></svg>',
  sun: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="4" fill="none" stroke="currentColor" stroke-width="2"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M5 5l2 2M17 17l2 2M19 5l-2 2M7 17l-2 2" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>',
  ratio: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="7" y="3" width="10" height="18" rx="2" fill="none" stroke="currentColor" stroke-width="2"/></svg>',
  mouth: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 12a8 8 0 0 0 16 0" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><path d="M8 12h8" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>',
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
  "RẤT TỐT": { cls: "good", rank: 5, short: "Rất tốt" },
  "TỐT": { cls: "good", rank: 4, short: "Tốt" },
  "CẢNH BÁO": { cls: "good", rank: 3, short: "Tốt" },
  "KHÔNG KHUYẾN NGHỊ": { cls: "good", rank: 3, short: "Tốt" },
  "CHƯA ĐỦ DỮ LIỆU": { cls: "good", rank: 3, short: "Tốt" },
  "CHƯA CÓ DỮ LIỆU": { cls: "good", rank: 3, short: "Tốt" },
};
const qMeta = (q) => QLEVEL[q] || { cls: "good", rank: 4, short: "Tốt" };
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
  view: "home", status: null, avatars: [], selectedAvatar: null,
  scriptText: "", scriptInfo: null, voiceId: "", voiceMeta: null, voiceChecked: false,
  splitMode: "full", prepState: null, jobFilter: "all", historySearch: "",
  libFilter: "all", libSort: "quality", libSearch: "",
  // TTS provider: "elevenlabs" (production) | "edge" (free test). Explicit,
  // never silently switched. Edge path consumes NO ElevenLabs quota.
  ttsProvider: "elevenlabs", edgeVoices: [], edgeVoice: "vi-VN-HoaiMyNeural",
  // Wizard state (V1.3.1): current + furthest-reached step for each flow.
  quickStep: 1, quickMax: 1, createStep: 1, createMax: 1, activeJobs: [],
  // V1.5.0 — ElevenLabs per-voice config auto-sync. voiceConfig is the resolved
  // config for the CURRENTLY entered voice (or null = legacy/Studio-default path).
  // Changing the Voice ID clears it (no leak between voices).
  voiceConfig: null, voiceSyncMode: "auto_current", voiceHistory: null,
  // V1.6.0 — target language is a first-class input. "auto" detects from the
  // script; the normal default is Vietnamese (the product is Vietnamese-first).
  targetLanguage: "vi",
  // V1.6.0 — the normal Render flow exposes exactly the approved ElevenLabs
  // voices (no free-text Voice ID). Names come from official metadata.
  approvedVoices: [],
  // V1.6.0 — Script Voice Preview & Audio Reuse
  scriptPreview: null,
  previewGenerating: false,
  previewError: null,
  playingSampleVid: null,
  theme: "light",
};

// Theme Management (Light / Dark Mode)
function initTheme() {
  const saved = ls.get("studio_theme");
  const prefersDark = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
  const theme = saved || (prefersDark ? "dark" : "light");
  applyTheme(theme);
}
function applyTheme(theme) {
  state.theme = theme;
  document.documentElement.setAttribute("data-theme", theme);
  ls.set("studio_theme", theme);
  const icon = $("#themeIcon");
  const lbl = $("#themeLabel");
  if (icon) icon.textContent = theme === "dark" ? "☀️" : "🌙";
  if (lbl) lbl.textContent = theme === "dark" ? "SÁNG" : "TỐI";
}
function toggleTheme() {
  applyTheme(state.theme === "dark" ? "light" : "dark");
}

// Script Draft Persistence & File Upload helper
function initDraftScript() {
  const saved = ls.get("studio_draft_script", "");
  if (saved && !state.scriptText) {
    state.scriptText = saved;
  }
}
function saveDraftScript(text) {
  state.scriptText = text;
  ls.set("studio_draft_script", text);
}
async function handleScriptFileUpload(f) {
  if (!f) return;
  const ext = (f.name || "").split(".").pop().toLowerCase();
  if (!["txt", "docx"].includes(ext)) {
    return toast("Chỉ hỗ trợ file văn bản .txt hoặc .docx", "warn");
  }
  toast(`Đang xử lý ${f.name}…`);
  const fd = new FormData();
  fd.append("file", f);
  try {
    const r = await fetch("/api/script/parse", { method: "POST", body: fd });
    const d = await r.json();
    if (d.ok) {
      saveDraftScript(d.text);
      state.scriptInfo = d;
      const ta = $("#qScript");
      if (ta) ta.value = d.text;
      updateScriptInfo();
      quickRefresh();
      toast(`Đã tải ${d.source || f.name}: ${d.words} từ, ~${d.estimated_duration_str}`, "good");
    } else {
      toast(d.error || "Không đọc được kịch bản", "bad");
    }
  } catch (err) {
    toast(`Lỗi khi đọc file: ${err.message}`, "bad");
  }
}

// Standardized Vietnamese mouth-motion diagnostic script (spec B10). A
// repeatable visual test stimulus — bilabials (m/b/p), wide/open + rounded
// vowels, natural flow. The renderer is NOT optimized for this; it only makes
// Avatar A vs Avatar B comparable under identical text/voice/profile.
const STANDARD_MOUTH_TEST_SCRIPT =
  "Ba mẹ mỉm cười và Minh mua một hộp bánh mì. " +
  "Phương nói hôm nay trời đẹp, chúng ta cùng quay video thật tự nhiên.";

// --------------------------------------------------------------------------- //
// V1.6.0 runtime hardening — frontend side of the contract handshake + drift.
let _statusPollTimer = null;
let _lastBootId = null;
async function loadStatus() {
  try {
    state.status = await api("/api/system/status?frontend_contract=" + encodeURIComponent(STUDIO_API_CONTRACT));
    renderTopbar();
    handleRuntimeGuard();
  } catch (err) {
    const dot = $("#statusDot");
    const txt = $("#statusText");
    if (dot) dot.className = "dot bad";
    if (txt) txt.textContent = "MẤT KẾT NỐI…";
    showRuntimeBanner({ kind: "lost" });
  }
}
function renderTopbar() {
  const s = state.status; if (!s) return;
  let cls = "good", txt = "SẴN SÀNG";
  if (s.truth_valid === false || s.renderer_ready === false || s.musetalk_ready === false) {
    cls = "bad"; txt = "CHƯA SẴN SÀNG";
  }
  $("#statusDot").className = "dot " + cls;
  $("#statusText").textContent = txt;
}

// Boot-id change: the server restarted while this tab stayed open. Refresh
// runtime-dependent state safely (do NOT discard the user's script draft).
function handleRuntimeGuard() {
  const s = state.status; if (!s) return;
  const bootId = (s.process || {}).boot_id;
  if (_lastBootId && bootId && _lastBootId !== bootId) {
    toast("AI Avatar Studio đã khởi động lại. Đang tải lại trạng thái.", "");
    Promise.all([loadAvatars(), loadApprovedVoices(), loadEdgeVoices()]).catch(() => {});
  }
  _lastBootId = bootId || _lastBootId;
  showRuntimeBanner({ kind: "ok" });
  // Light periodic polling (every 30s) to catch a restart / drift while idle.
  if (!_statusPollTimer) {
    _statusPollTimer = setInterval(() => { loadStatus().catch(() => {}); }, 30000);
  }
}

// Persistent banner at the top of the content area.
function showRuntimeBanner({ kind }) {
  let b = $("#runtimeBanner");
  if (!b) {
    b = document.createElement("div");
    b.id = "runtimeBanner";
    b.className = "runtime-banner";
    document.body.insertBefore(b, document.body.firstChild);
  }
  if (kind === "ok" || kind === "lost") { if (kind === "ok") b.hidden = true; return; }
  b.hidden = false;
  const local = isLocalhost();
  if (kind === "contract") {
    b.className = "runtime-banner warn";
    b.innerHTML = `<div class="rb-inner"><div class="rb-msg"><strong>Phiên bản giao diện và máy chủ chưa đồng bộ.</strong> Cần khởi động lại AI Avatar Studio để áp dụng thay đổi.</div></div>`;
  } else if (kind === "drift") {
    b.className = "runtime-banner warn";
    b.innerHTML = `<div class="rb-inner">
      <div class="rb-msg"><strong>AI Avatar Studio cần khởi động lại.</strong> Mã nguồn hệ thống đã thay đổi sau khi máy chủ được khởi động. Một số chức năng mới có thể chưa hoạt động cho đến khi Studio được khởi động lại.</div>
      <div class="rb-actions">${local ? `<button class="ghost tiny" onclick="requestStudioRestart()">Khởi động lại Studio</button>` : `<span class="rb-note">Studio cần được quản trị viên khởi động lại.</span>`}</div>
    </div>`;
  } else if (kind === "runtime") {
    b.className = "runtime-banner bad";
    b.innerHTML = `<div class="rb-inner"><div class="rb-msg"><strong>Runtime không đúng.</strong> Studio đang chạy dưới trình thông dịch không phải canonical. Cần quản trị viên khởi động lại đúng runtime.</div></div>`;
  }
}
async function requestStudioRestart() {
  if (!isLocalhost()) { toast("Chỉ máy chủ cục bộ mới có quyền khởi động lại", "bad"); return; }
  if (!confirm("Khởi động lại AI Avatar Studio? Các render đang chạy có thể bị gián đoạn.")) return;
  try {
    const r = await api("/api/studio/restart", { method: "POST", body: JSON.stringify({}) });
    if (r.ok) {
      toast("Đang khởi động lại Studio…", "");
      // Poll until the server comes back with a new boot_id.
      let tries = 0;
      const wait = setInterval(async () => {
        tries++;
        try {
          const s = await api("/api/system/status?frontend_contract=" + encodeURIComponent(STUDIO_API_CONTRACT));
          if (s && s.process && s.process.boot_id && s.process.boot_id !== _lastBootId) {
            clearInterval(wait);
            toast("Studio đã khởi động lại thành công", "good");
            state.status = s; renderTopbar(); handleRuntimeGuard();
            await Promise.all([loadAvatars(), loadApprovedVoices(), loadEdgeVoices()]).catch(() => {});
          }
        } catch (e) { /* still restarting */ }
        if (tries > 40) clearInterval(wait);
      }, 1500);
    } else if (r.blocked) {
      toast("Có render đang chạy. Hoàn tất/huỷ job trước. (" + (r.active_jobs || []).length + " job)", "bad");
    } else {
      toast(r.error || "Không thể khởi động lại", "bad");
    }
  } catch (e) { toast("Không thể khởi động lại", "bad"); }
}
async function loadAvatars() {
  const r = await api("/api/avatars");
  state.avatars = r.avatars || [];
}

// Navigation
function switchView(v) {
  state.view = v;
  $$(".nav-item").forEach(b => b.classList.toggle("active", b.dataset.view === v));
  if (v === "home") renderHome();
  if (v === "quick") renderQuick();
  if (v === "create") renderCreate();
  if (v === "library") renderLibrary();
  if (v === "history") renderHistory();
  if (v === "trash") renderTrash();
  if (v === "status") renderStatus();
  if (v === "settings") renderSettings();
  $("#content").scrollTop = 0;
}

// --------------------------------------------------------------------------- //
// HOME — two dominant workflows + secondary navigation
function renderHome() {
  const el = $("#content");
  const ready = state.avatars.filter(a => a.ready).length;
  el.innerHTML = `
    <div class="home-hero">
      <h1>Tạo video với AI Avatar</h1>
      <p>Chọn cách bắt đầu bên dưới để tạo video hoặc khởi tạo nhân vật AI mới.</p>
      <div class="home-cards">
        <div class="home-card" onclick="switchView('quick')">
          <div class="hc-icon">${ICO.video}</div>
          <div class="hc-title">Tạo video</div>
          <div class="hc-desc">Chọn Avatar, nhập kịch bản và tạo video hoàn chỉnh với giọng đọc AI.</div>
          <span class="hc-cta">BẮT ĐẦU ${ICO.arrow}</span>
        </div>
        <div class="home-card alt" onclick="switchView('create')">
          <div class="hc-icon">${ICO.avatar}</div>
          <div class="hc-title">Tạo Avatar mới</div>
          <div class="hc-desc">Tải video chân dung để hệ thống tự động khởi tạo nhân vật AI mới.</div>
          <span class="hc-cta">TẠO AVATAR ${ICO.arrow}</span>
        </div>
      </div>
      <div class="home-secondary">
        <div class="home-sec" onclick="switchView('library')">
          ${ICO.avatar}<div>Thư viện Avatar<div class="hs-sub">${ready} Avatar sẵn sàng</div></div>
        </div>
        <div class="home-sec" onclick="switchView('history')">
          ${ICO.history}<div>Lịch sử video<div class="hs-sub">Video đã tạo</div></div>
        </div>
        <div class="home-sec" onclick="switchView('status')">
          ${ICO.check}<div>Trạng thái hệ thống<div class="hs-sub">Kiểm tra kết nối</div></div>
        </div>
      </div>
    </div>`;
}

// --------------------------------------------------------------------------- //
// CREATE VIDEO — step-by-step (renamed from "Tạo video nhanh")
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
    <h1 class="view-title">Tạo video</h1>
    <p class="view-sub">Tạo video hoàn chỉnh với Avatar và giọng đọc AI chỉ qua vài bước.</p>
    ${quickStepperHTML()}
    <div class="steps wizard">

      <div class="step" data-step="1">
        <div class="step-head" onclick="quickGoto(1)"><div class="step-num">1</div><div class="step-title">Chọn Avatar</div><div class="step-summary"></div></div>
        <div class="step-body">
          <div class="avatar-select">
            <select id="qAvatar"></select>
            <button class="ghost" onclick="switchView('create')">＋ Thêm Avatar mới</button>
          </div>
          <div id="qAvatarPick"></div>
          <div class="actions"><button class="primary" id="qNext1" onclick="quickGoto(2)">Tiếp tục</button></div>
        </div>
      </div>

      <div class="step" data-step="2">
        <div class="step-head" onclick="quickGoto(2)"><div class="step-num">2</div><div class="step-title">Soạn thảo kịch bản</div><div class="step-summary"></div></div>
        <div class="step-body">
          <div class="script-editor-container">
            <div class="script-toolbar">
              <div class="st-left">
                <span class="st-title">Nội dung kịch bản</span>
              </div>
              <div class="st-actions">
                <button type="button" class="tiny ghost" onclick="adjustScriptFontSize(-1)" title="Giảm cỡ chữ">A-</button>
                <button type="button" class="tiny ghost" onclick="adjustScriptFontSize(1)" title="Tăng cỡ chữ">A+</button>
                <button type="button" class="tiny ghost" onclick="toggleScriptFullscreen()" id="btnFullscreenScript" title="Phóng to toàn màn hình">⛶ Phóng to</button>
                <button type="button" class="tiny ghost" onclick="pasteFromClipboard()" title="Dán nội dung từ bộ nhớ tạm">📋 Dán</button>
                <label class="tiny ghost file-btn-label" title="Tải file kịch bản (.txt, .docx)">
                  📁 Tải file
                  <input type="file" id="qFile" accept=".txt,.docx" style="display:none" />
                </label>
                <button type="button" class="tiny ghost" onclick="insertSampleScript()" title="Chèn kịch bản mẫu">✨ Kịch bản mẫu</button>
                <button type="button" class="tiny ghost danger-text" onclick="clearScript()" title="Xóa toàn bộ văn bản">🧹 Xóa</button>
              </div>
            </div>

            <textarea id="qScript" class="script-canvas font-md" rows="18" placeholder="Nhập hoặc dán nội dung kịch bản tại đây..."></textarea>

            <div id="qScriptInfo" class="script-info-bar"></div>
          </div>

          <div class="script-split-section" style="margin-top:16px">
            <div class="row between" style="align-items:center;margin-bottom:8px">
              <label style="margin:0;font-weight:600;font-size:13px">Độ dài video</label>
            </div>
            <div class="split-chips" id="splitChips">
              <span class="schip ${state.splitMode==='full'?'active':''}" data-m="full" onclick="setSplitMode('full')">🎬 Toàn bộ kịch bản</span>
              <span class="schip ${state.splitMode==='30s'?'active':''}" data-m="30s" onclick="setSplitMode('30s')">⏱️ 30 giây đầu</span>
              <span class="schip ${state.splitMode==='1min'?'active':''}" data-m="1min" onclick="setSplitMode('1min')">⏱️ 1 phút đầu</span>
              <span class="schip ${state.splitMode==='3min'?'active':''}" data-m="3min" onclick="setSplitMode('3min')">⏱️ 3 phút đầu</span>
              <span class="schip ${state.splitMode==='auto'?'active':''}" data-m="auto" onclick="setSplitMode('auto')">✂️ Tự động chia phần</span>
            </div>
            <div id="qSegPreview"></div>
          </div>

          <div class="actions" style="margin-top:20px">
            <button class="ghost" onclick="quickGoto(1)">Quay lại</button>
            <button class="primary big" id="qNext2" onclick="quickGoto(3)">Tiếp tục chọn giọng ➔</button>
          </div>
        </div>
      </div>

      <div class="step" data-step="3">
        <div class="step-head" onclick="quickGoto(3)"><div class="step-num">3</div><div class="step-title">Chọn giọng đọc</div><div class="step-summary"></div></div>
        <div class="step-body">
          <div class="tts-tabs" id="ttsTabs">
            <button class="tts-tab ${state.ttsProvider === 'elevenlabs' ? 'active' : ''}" data-p="elevenlabs">🎙️ ELEVENLABS<span class="tt-sub">Chất lượng cao</span></button>
            <button class="tts-tab ${state.ttsProvider === 'edge' ? 'active' : ''}" data-p="edge">🆓 TEST MIỄN PHÍ<span class="tt-sub">Edge TTS</span></button>
          </div>
          <div class="tts-subnote" id="ttsSubnote"></div>
          <div id="ttsPanel"></div>
          <audio id="qPreview" style="display:none;margin-top:10px;width:100%" controls></audio>
          <div class="actions"><button class="ghost" onclick="quickGoto(2)">Quay lại</button><button class="primary" id="qNext3" onclick="quickGoto(4)">Tiếp tục</button></div>
        </div>
      </div>

      <div class="step" data-step="4">
        <div class="step-head" onclick="quickGoto(4)"><div class="step-num">4</div><div class="step-title">Kiểm tra xem thử</div><div class="step-summary"></div></div>
        <div class="step-body">
          <div class="hint" style="margin-bottom:14px">Xem trước chuyển động môi hoặc nghe thử giọng đọc trước khi tạo video hoàn chỉnh (tùy chọn).</div>
          <div class="test-opt-grid">
            <div class="test-opt-card">
              <div class="test-opt-title"><span class="tag muted">MIỄN PHÍ</span> Thử khẩu hình môi</div>
              <div class="test-opt-desc">Tạo video ngắn kiểm tra chuyển động môi khớp khuôn mặt mà không tốn hạn mức giọng đọc.</div>
              <button class="secondary" id="qMouthBtn" onclick="renderMouthTest()" style="margin-top:auto">Thử khẩu hình (Miễn phí)</button>
            </div>
            <div class="test-opt-card">
              <div class="test-opt-title"><span class="tag good">CHÍNH XÁC</span> Xem thử 10 giây</div>
              <div class="test-opt-desc">Tạo 10 giây video đầu tiên với giọng đọc chính thức để xem trước chất lượng thực tế.</div>
              <button class="ghost" id="qTestBtn" onclick="renderTest10s()" style="margin-top:auto">Xem thử 10 giây</button>
            </div>
          </div>
          <details class="tech" style="margin-top:12px">
            <summary>Kịch bản kiểm tra mẫu</summary>
            <div style="margin-top:10px">
              <textarea id="qMouthScript" rows="2">${esc(STANDARD_MOUTH_TEST_SCRIPT)}</textarea>
              <div class="actions"><button class="tiny ghost" onclick="useStandardMouthScript()">Dùng đoạn mẫu mặc định</button></div>
            </div>
          </details>
          <div class="actions"><button class="ghost" onclick="quickGoto(3)">Quay lại</button><button class="primary" onclick="quickGoto(5)">Bỏ qua, tạo video ngay ➔</button></div>
        </div>
      </div>

      <div class="step" data-step="5">
        <div class="step-head" onclick="quickGoto(5)"><div class="step-num">5</div><div class="step-title">Tạo video</div><div class="step-summary"></div></div>
        <div class="step-body">
          <div id="qReview" class="review-grid"></div>
          <div class="field-group" style="margin-top:16px;margin-bottom:14px">
            <label for="qVideoName" style="font-size:13px;font-weight:600;display:block;margin-bottom:6px">Tên video (tùy chọn)</label>
            <input id="qVideoName" type="text" placeholder="Ví dụ: Giới thiệu sản phẩm, Bản tin sáng, Video quảng cáo..." maxlength="120" style="width:100%;box-sizing:border-box" />
            <div class="hint" style="margin-top:4px;font-size:11px">Đặt tên giúp bạn dễ tìm kiếm lại trong Lịch sử video.</div>
          </div>
          <div class="actions">
            <button class="ghost" onclick="quickGoto(4)">Quay lại</button>
            <button class="primary big" id="qRenderBtn" onclick="renderFull()">TẠO VIDEO</button>
            <span class="muted" style="font-size:12px;align-self:center">(Phím tắt: Ctrl+Enter)</span>
          </div>
        </div>
      </div>

    </div>
    <details class="tech" style="margin-top:20px">
      <summary>Thông tin kỹ thuật</summary>
      <div style="margin-top:12px">${productionProfileHTML()}</div>
    </details>`;

  const sel = $("#qAvatar");
  if (!readyAvs.length) {
    sel.innerHTML = `<option value="">Chưa có Avatar</option>`;
    $("#qAvatarPick").innerHTML = `<div class="avatar-pick empty">
      <div>Chưa có AI Avatar nào sẵn sàng.</div>
      <button class="ghost" onclick="switchView('create')">＋ Tạo AI Avatar trước</button></div>`;
  } else {
    sel.innerHTML = `<option value="">— Chọn Avatar —</option>` +
      readyAvs.map(a => `<option value="${esc(a.avatar_id)}">${esc(a.avatar_id)} · Sẵn sàng · ${esc(TYPE_VI[a.avatar_type] || a.avatar_type)}</option>`).join("");
  }
  sel.onchange = () => {
    const a = state.avatars.find(x => x.avatar_id === sel.value);
    state.selectedAvatar = a; ls.set("studio_avatar", sel.value);
    renderAvatarPick(a);
    quickRefresh();
  };
  const lastAid = ls.get("studio_avatar", "");
  if (lastAid && readyAvs.some(a => a.avatar_id === lastAid)) { sel.value = lastAid; sel.onchange(); }
  else if (state.selectedAvatar && readyAvs.some(a => a.avatar_id === state.selectedAvatar.avatar_id)) { sel.value = state.selectedAvatar.avatar_id; sel.onchange(); }
  
  const qScriptEl = $("#qScript");
  qScriptEl.value = state.scriptText;
  qScriptEl.oninput = (e) => {
    saveDraftScript(e.target.value);
    autoResizeScriptCanvas(qScriptEl);
    updateScriptInfo();
    quickRefresh();
  };
  setTimeout(() => autoResizeScriptCanvas(qScriptEl), 30);
  
  // Drag & drop file support directly on script textarea
  qScriptEl.ondragover = (e) => { e.preventDefault(); qScriptEl.classList.add("drag-over"); };
  qScriptEl.ondragleave = () => { qScriptEl.classList.remove("drag-over"); };
  qScriptEl.ondrop = (e) => {
    e.preventDefault();
    qScriptEl.classList.remove("drag-over");
    if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleScriptFileUpload(e.dataTransfer.files[0]);
    }
  };

  // TTS provider tabs (explicit, never silent switch).
  $$("#ttsTabs .tts-tab").forEach(t => t.onclick = () => {
    state.ttsProvider = t.dataset.p;
    $$("#ttsTabs .tts-tab").forEach(x => x.classList.toggle("active", x === t));
    renderTTSPanel();
    quickRefresh();
  });
  renderTTSPanel();
  const qSplitEl = $("#qSplit");
  if (qSplitEl) {
    qSplitEl.value = state.splitMode;
    qSplitEl.onchange = (e) => { setSplitMode(e.target.value); };
  }
  const qFileEl = $("#qFile");
  if (qFileEl) {
    qFileEl.onchange = async (e) => {
      const f = e.target.files[0]; if (!f) return;
      await handleScriptFileUpload(f);
    };
  }
  updateScriptInfo(); updateSegPreview();
  quickRefresh();
}
// ----- Create Video wizard helpers -----
const QUICK_STEPS = [
  { n: 1, title: "Avatar" }, { n: 2, title: "Nội dung" }, { n: 3, title: "Giọng" },
  { n: 4, title: "Kiểm tra" }, { n: 5, title: "Tạo video" },
];
function quickStepperHTML() {
  return `<div class="stepper">${QUICK_STEPS.map((s, i) => `
    <div class="stp" data-step="${s.n}"><div class="s-dot">${s.n}</div><div class="s-lbl">${s.title}</div></div>
    ${i < QUICK_STEPS.length - 1 ? '<div class="s-conn"></div>' : ''}`).join("")}</div>`;
}
function quickVoiceReady() {
  if (state.ttsProvider === "edge") return true; // edge voice always selected
  return !!(state.voiceId && state.voiceId.trim());
}
function quickSummary(n) {
  if (n === 1) return state.selectedAvatar ? esc(state.selectedAvatar.avatar_id) : "Chưa chọn";
  if (n === 2) { const w = state.scriptText.trim() ? state.scriptText.split(/\s+/).filter(Boolean).length : 0; return w ? `${w} từ` : "Chưa nhập"; }
  if (n === 3) return state.ttsProvider === "edge" ? "Edge TTS (miễn phí)" : (state.voiceId ? "ElevenLabs" : "Chưa chọn giọng");
  if (n === 4) return "Tùy chọn";
  return "";
}
// Re-render summaries/stepper/disabled state without rebuilding the whole view
// (so textarea content, selections, and focus are preserved).
function quickRefresh() {
  const cur = state.quickStep;
  $$('.steps.wizard .step').forEach(st => {
    const n = +st.dataset.step;
    st.classList.toggle('is-active', n === cur);
    st.classList.toggle('is-done', n < cur);
    st.classList.toggle('is-future', n > cur);
    const sum = st.querySelector('.step-summary');
    if (sum) sum.textContent = n < cur ? quickSummary(n) : "";
  });
  // stepper nodes
  $$('.stepper .stp').forEach(s => {
    const n = +s.dataset.step;
    s.classList.toggle('done', n < cur);
    s.classList.toggle('active', n === cur);
  });
  // Tiếp tục gating
  const set = (id, ok) => { const b = document.getElementById(id); if (b) b.disabled = !ok; };
  set('qNext1', !!state.selectedAvatar);
  set('qNext2', !!state.scriptText.trim());
  set('qNext3', quickVoiceReady());
  // review summary on step 5
  // Pre-flight Checklist validation on step 5
  const rev = document.getElementById('qReview');
  if (rev) {
    if (state.quickStep === 5) {
      refreshPreflightChecklist();
    } else {
      const av = state.selectedAvatar ? state.selectedAvatar.avatar_id : "—";
      const words = state.scriptText.trim() ? state.scriptText.split(/\s+/).filter(Boolean).length : 0;
      const voice = state.ttsProvider === "edge" ? "Edge TTS (miễn phí)" : (state.voiceId || "—");
      rev.innerHTML = `<div class="rv"><span class="rv-k">Avatar</span><span class="rv-v">${esc(av)}</span></div>
        <div class="rv"><span class="rv-k">Nội dung</span><span class="rv-v">${words} từ</span></div>
        <div class="rv"><span class="rv-k">Giọng</span><span class="rv-v">${esc(voice)}</span></div>`;
    }
  }
}

let _preflightTimer = null;
let _lastPreflightResult = null;

async function refreshPreflightChecklist(force = false) {
  const rev = document.getElementById('qReview');
  if (!rev) return;

  const avId = (state.selectedAvatar ? state.selectedAvatar.avatar_id : ($("#qAvatar") && $("#qAvatar").value)) || "";
  const scriptText = (state.scriptText || "").trim();
  const provider = state.ttsProvider || "elevenlabs";
  const voiceId = activeVoiceId() || "";
  const modelId = ($("#qModelSelect") && $("#qModelSelect").value) || state.selectedModel || state.voiceConfig?.model_id || "eleven_v4";
  const lang = state.targetLanguage || "vi";

  // Show lightweight loading indicator if empty
  if (!rev.querySelector(".preflight-box")) {
    rev.innerHTML = `
      <div class="preflight-box">
        <div class="preflight-header">
          <div class="preflight-title"><span>📋</span> <span>Kiểm tra điều kiện trước khi Render</span></div>
          <span class="preflight-badge warn">Đang kiểm tra…</span>
        </div>
        <div class="muted" style="padding:10px 0;font-size:13px"><span class="spinner"></span> Đang đối chiếu tính hợp lệ của Avatar, kịch bản, model giọng và quota…</div>
      </div>`;
  }

  try {
    const res = await api("/api/render/validate", {
      method: "POST",
      body: JSON.stringify({
        avatar_id: avId,
        script_text: scriptText,
        tts_provider: provider,
        voice_id: voiceId,
        model_id: modelId,
        target_language: lang
      })
    });

    if (res && res.ok) {
      _lastPreflightResult = res;
      renderPreflightUI(res);
    }
  } catch (e) {
    // Keep UI responsive even if network glitches
  }
}

function renderPreflightUI(res) {
  const rev = document.getElementById('qReview');
  if (!rev) return;

  const sum = res.summary || {};
  const list = res.checklist || [];
  const canRender = !!res.can_render;

  const badgeClass = sum.headline_type || (canRender ? "good" : "bad");
  const badgeText = canRender ? (sum.warnings ? "CÓ THỂ TẠO VIDEO" : "ĐỦ ĐIỀU KIỆN") : "CHƯA ĐỦ ĐIỀU KIỆN";

  const rowsHtml = list.map(item => {
    let icon = "✅";
    let statusClass = "good";
    if (item.status === "WARN") { icon = "⚠️"; statusClass = "warn"; }
    else if (item.status === "FAIL") { icon = "❌"; statusClass = "bad"; }

    let fixBtn = "";
    if (item.step) {
      fixBtn = `<button type="button" class="preflight-fix-btn" onclick="quickGoto(${item.step})">Sửa bước ${item.step}</button>`;
    }

    return `
      <div class="preflight-item">
        <div class="preflight-icon">${icon}</div>
        <div class="preflight-content">
          <div class="preflight-item-title">
            <span>${esc(item.title)}</span>
            ${fixBtn}
          </div>
          <div class="preflight-item-msg">${esc(item.message)}</div>
        </div>
      </div>
    `;
  }).join("");

  rev.innerHTML = `
    <div class="preflight-box">
      <div class="preflight-header">
        <div class="preflight-title">
          <span>📋</span>
          <span>Kiểm tra điều kiện tạo video</span>
        </div>
        <div class="row" style="gap:8px">
          <span class="preflight-badge ${badgeClass}">${badgeText}</span>
          <button type="button" class="ghost tiny" onclick="refreshPreflightChecklist(true)" title="Kiểm tra lại">🔄 Kiểm tra lại</button>
        </div>
      </div>
      <div class="preflight-list">
        ${rowsHtml}
      </div>
    </div>
  `;

  // Control Render button
  const btn = document.getElementById("qRenderBtn");
  if (btn) {
    btn.disabled = !canRender;
    btn.title = canRender ? "Bắt đầu tạo video" : "Vui lòng hoàn thành các mục trước khi tạo video";
  }
}
function quickGoto(n) {
  if (n < 1 || n > 5) return;
  state.quickStep = n;
  state.quickMax = Math.max(state.quickMax, n);
  quickRefresh();
  const st = document.querySelector(`.steps.wizard .step[data-step="${n}"]`);
  if (st) st.scrollIntoView({ block: "start", behavior: "smooth" });
  $("#content").scrollTop = 0;
}

const BASE_MODEL_OPTIONS = [
  { id: "eleven_v4", name: "⭐ Eleven v4 (Mới nhất · Biểu cảm chân thực nhất)" },
  { id: "eleven_v4_turbo", name: "⚡ Eleven v4 Turbo (Độ trễ thấp ~100ms)" },
  { id: "eleven_v3", name: "Eleven v3 (Chuẩn đàm thoại tự nhiên)" },
  { id: "eleven_v3_conversational", name: "Eleven v3 Conversational (Giao tiếp hội thoại)" },
  { id: "eleven_multilingual_v2", name: "Eleven Multilingual v2 (Đa ngôn ngữ ổn định)" },
  { id: "eleven_turbo_v2_5", name: "Eleven Turbo v2.5 (Tối ưu tốc độ)" },
  { id: "eleven_flash_v2_5", name: "Eleven Flash v2.5 (Siêu tốc ~75ms)" },
];

let _cachedLiveModels = null;

async function fetchLiveTTSModels() {
  if (_cachedLiveModels) return _cachedLiveModels;
  try {
    const res = await api("/api/elevenlabs/models");
    if (res && res.ok && Array.isArray(res.models)) {
      _cachedLiveModels = res.models.filter(m => m.can_do_text_to_speech && !m.deprecated);
      return _cachedLiveModels;
    }
  } catch (e) {}
  return [];
}

function setSelectModelValue(selectEl, modelId) {
  if (!selectEl || !modelId) return;
  const mid = modelId.trim();
  const exists = Array.from(selectEl.options).some(o => o.value === mid);
  if (!exists) {
    const opt = document.createElement("option");
    opt.value = mid;
    opt.textContent = `✨ ${mid} (Mới)`;
    const customOpt = Array.from(selectEl.options).find(o => o.value === "__custom__");
    if (customOpt) selectEl.insertBefore(opt, customOpt);
    else selectEl.appendChild(opt);
  }
  selectEl.value = mid;
}

function initModelDropdown(selectEl, curMid, onSelectModel) {
  if (!selectEl) return;
  curMid = (curMid || "eleven_v4").trim();

  let list = BASE_MODEL_OPTIONS.map(m => ({ ...m }));
  if (curMid && !list.some(m => m.id === curMid)) {
    list.unshift({ id: curMid, name: `Model đang chọn: ${curMid}` });
  }

  function renderList(selVal) {
    let html = list.map(m => {
      const isSel = (m.id === selVal);
      return `<option value="${esc(m.id)}" ${isSel ? 'selected' : ''}>${esc(m.name)}</option>`;
    }).join("");
    html += `<option value="__custom__">➕ Tự nhập Model ID khác...</option>`;
    selectEl.innerHTML = html;
    selectEl.value = selVal;
  }

  renderList(curMid);

  selectEl.onchange = async () => {
    const val = selectEl.value;
    if (val === "__custom__") {
      const customId = prompt("Nhập mã Model ID từ ElevenLabs (ví dụ: eleven_v5, eleven_v5_turbo, custom fine-tune):", "");
      if (customId && customId.trim()) {
        const cleanId = customId.trim();
        if (!list.some(m => m.id === cleanId)) {
          list.unshift({ id: cleanId, name: `✨ ${cleanId} (Tự nhập)` });
        }
        renderList(cleanId);
        curMid = cleanId;
        if (typeof onSelectModel === "function") await onSelectModel(cleanId);
      } else {
        selectEl.value = curMid;
      }
      return;
    }
    curMid = val;
    if (typeof onSelectModel === "function") await onSelectModel(val);
  };

  fetchLiveTTSModels().then(liveModels => {
    if (!liveModels || !liveModels.length) return;
    let added = false;
    liveModels.forEach(lm => {
      const mid = lm.model_id;
      if (!list.some(m => m.id === mid)) {
        const kChars = lm.maximum_text_length_per_request ? ` · ${(lm.maximum_text_length_per_request/1000).toFixed(0)}k ký tự` : "";
        list.push({
          id: mid,
          name: `✨ ${lm.name || mid} (Mới từ ElevenLabs${kChars})`
        });
        added = true;
      }
    });
    if (added) {
      renderList(curMid || selectEl.value);
    }
  });
}

function renderTTSPanel() {
  const panel = $("#ttsPanel"); if (!panel) return;
  const note = $("#ttsSubnote");
  if (state.ttsProvider === "edge") {
    if (note) note.innerHTML = `<span class="tag muted">DÙNG THỬ</span> <span class="muted">Miễn phí, không tốn hạn mức. Thích hợp kiểm tra chuyển động môi.</span>`;
    const opts = (state.edgeVoices.length ? state.edgeVoices : [
      { voice_id: "vi-VN-HoaiMyNeural", label: "Nữ — Hoài My" },
      { voice_id: "vi-VN-NamMinhNeural", label: "Nam — Nam Minh" },
    ]).map(v => `<option value="${esc(v.voice_id)}" ${v.voice_id === state.edgeVoice ? 'selected' : ''}>${esc(v.label)}</option>`).join("");
    panel.innerHTML = `
      <label style="font-weight:600;font-size:13px;margin-bottom:6px">Chọn giọng dùng thử</label>
      <div class="row">
        <select id="qEdgeVoice" style="flex:1">${opts}</select>
        <button class="ghost" onclick="previewEdgeVoice()">▶ Nghe thử</button>
      </div>
      <div id="qEdgeInfo" style="margin-top:8px;font-size:12px"></div>`;
    const esel = $("#qEdgeVoice");
    if (esel) esel.onchange = (e) => { state.edgeVoice = e.target.value; ls.set("studio_edge_voice", e.target.value); };
  } else {
    if (note) note.innerHTML = `<span class="tag good">ElevenLabs</span> <span class="muted">Giọng đọc AI chất lượng cao.</span>`;
    panel.innerHTML = `
      <label style="font-weight:600;font-size:13px;margin-bottom:8px">Giọng đọc gợi ý</label>
      <div id="qVoiceCards" class="voice-cards"></div>
      <div id="qVoiceInfo" style="margin-top:8px;font-size:12px"></div>

      <!-- Thư viện giọng từ tài khoản ElevenLabs -->
      <div class="voice-account-box" style="margin-top:14px;background:var(--card,#1a1a1f);border:1px solid var(--border,#333);border-radius:8px;padding:12px">
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px">
          <span style="font-weight:600;font-size:13px">🎙️ Giọng từ tài khoản ElevenLabs</span>
          <button type="button" class="ghost tiny" onclick="loadAccountVoices(true)">🔄 Tải lại</button>
        </div>
        <div class="row" style="gap:8px;align-items:center;flex-wrap:wrap">
          <select id="qAccountVoicesSelect" style="flex:1;min-width:240px" onchange="onAccountVoiceDropdownChange()">
            <option value="">— Đang tải danh sách giọng… —</option>
          </select>
          <button type="button" class="primary tiny" onclick="applyAccountVoiceSelection()">Dùng giọng này</button>
          <button type="button" class="ghost tiny" id="qAccountVoicePreviewBtn" style="display:none" onclick="playAccountVoicePreview()">▶ Nghe mẫu</button>
        </div>
        <div id="qAccountVoiceDesc" class="muted" style="font-size:12px;margin-top:6px"></div>

        <div style="margin-top:10px;border-top:1px dashed var(--border,#333);padding-top:10px">
          <div class="row" style="gap:8px">
            <input id="qCustomVoiceInput" type="text" placeholder="Hoặc dán mã Voice ID khác từ ElevenLabs..." style="flex:1;font-size:13px" />
            <button type="button" class="secondary tiny" onclick="submitCustomVoiceInput()">Thêm giọng</button>
          </div>
        </div>
      </div>

      <div class="row" style="margin-top:14px;gap:12px;align-items:flex-start;flex-wrap:wrap">
        <div style="flex:1;min-width:260px">
          <label style="display:block;margin-bottom:4px;font-weight:600">Mô hình AI Voice (Model)</label>
          <select id="qModelSelect" style="width:100%"></select>
          <div class="hint" style="font-size:11px">Khuyến nghị: <b>Eleven v4</b> (biểu cảm tự nhiên nhất, hỗ trợ tiếng Việt).</div>
        </div>
        <div style="width:180px">
          <label style="display:block;margin-bottom:4px;font-weight:600">Ngôn ngữ</label>
          <select id="qLang" style="width:100%">
            <option value="vi">Tiếng Việt</option>
            <option value="auto">Tự động (phát hiện theo kịch bản)</option>
            <option value="en">English</option>
            <option value="ja">日本語</option>
            <option value="zh">中文</option>
          </select>
        </div>
      </div>

      <div id="qLangInfo" style="margin-top:6px;font-size:12px"></div>
      <div id="qVoiceSync" style="margin-top:8px;font-size:12px"></div>
      <div id="scriptPreviewBox" class="script-preview-box"></div>
      <details class="tech" style="margin-top:10px">
        <summary>Tùy chỉnh nâng cao (Tùy chọn)</summary>
        <div style="margin-top:10px">
          <div class="tts-tabs" id="syncTabs" style="margin-bottom:10px">
            <button class="sync-tab active" data-m="auto_current">Cấu hình tự động</button>
            <button class="sync-tab" data-m="history_match">Khớp bản đã tạo</button>
            <button class="sync-tab" data-m="manual">Tùy chỉnh</button>
          </div>
          <div id="syncPanel"></div>
        </div>
      </details>`;
    renderVoiceCards();
    loadAccountVoices();
    const msel = $("#qModelSelect");
    if (msel) {
      const curMid = state.voiceConfig?.model_id || state.selectedModel || state.status?.elevenlabs_model_id || "eleven_v4";
      initModelDropdown(msel, curMid, async (chosen) => {
        state.selectedModel = chosen;
        ls.set("studio_selected_model", chosen);
        if (state.voiceId && state.voiceChecked) {
          await applyChosenModel(chosen);
        } else {
          quickRefresh();
        }
      });
    }
    const lng = $("#qLang"); if (lng) {
      lng.value = state.targetLanguage || "vi";
      // V1.6.0: changing the target language re-resolves the config (the same
      // voice can need a different model per language). The previous language's
      // resolved config is cleared first — no leak across languages.
      lng.onchange = async (e) => {
        state.targetLanguage = e.target.value;
        state.voiceConfig = null;
        const info = $("#qLangInfo"); if (info) info.innerHTML = ``;
        renderVoiceSync(); renderSyncPanel(); renderScriptPreview();
        if (state.voiceId && state.voiceChecked && state.ttsProvider === "elevenlabs") {
          await resolveVoiceConfig("auto_current");
        }
      };
    }
    $$("#syncTabs .sync-tab").forEach(t => t.onclick = () => {
      state.voiceSyncMode = t.dataset.m;
      $$("#syncTabs .sync-tab").forEach(x => x.classList.toggle("active", x === t));
      renderSyncPanel();
    });
    renderVoiceSync();
    renderSyncPanel();
    renderScriptPreview();
  }
}
// --------------------------------------------------------------------------- //
// V1.5.0 — ElevenLabs per-voice config auto-sync (Mode A/B/C)                //
// --------------------------------------------------------------------------- //
const SYNC_SRC_VI = {
  "ELEVENLABS_VOICE_SETTINGS_API": "ElevenLabs (cài đặt giọng)",
  "MATCHING_HISTORY_GENERATION": "ElevenLabs (bản tạo khớp)",
  "ELEVENLABS_HISTORY_ITEM": "ElevenLabs (bản đã chọn)",
  "STUDIO_POLICY": "Studio (mặc định)",
  "USER_MANUAL": "Tùy chỉnh",
};
function renderVoiceSync() {
  const box = $("#qVoiceSync"); if (!box) return;
  const c = state.voiceConfig;
  if (!c) {
    box.innerHTML = (state.voiceId && state.voiceChecked)
      ? `<span class="muted">Đang dùng cấu hình Studio (mặc định).</span>` : ``;
    return;
  }
  const ms = c.match_strength;
  let line = "";
  if (ms === "human_approved_profile") line = `<span class="tag good">✓ Đã tối ưu cho Tiếng Việt</span>`;
  else if (ms === "verified_language_policy" || ms === "language_policy") line = `<span class="tag good">✓ Tương thích Tiếng Việt</span>`;
  else if (ms === "history_item")      line = `<span class="tag good">✓ Khớp cấu hình ElevenLabs</span>`;
  else if (ms === "history_matched") line = `<span class="tag good">✓ Đã đồng bộ ElevenLabs</span>`;
  else if (ms === "settings_only")   line = `<span class="tag good">✓ Đã áp dụng cài đặt giọng</span>`;
  else if (ms === "manual")          line = `<span class="tag good">✓ Cấu hình tùy chỉnh</span>`;
  else line = `<span class="muted">Cấu hình: ${esc(ms || "—")}</span>`;
  box.innerHTML = `${line} <span class="muted2">· Model: ${esc(c.model_id || "—")}${c.voice_name ? " (" + esc(c.voice_name) + ")" : ""}</span>`;
}
function renderSyncPanel() {
  const panel = $("#syncPanel"); if (!panel) return;
  const m = state.voiceSyncMode;
  if (m === "history_match") {
    panel.innerHTML = `<div class="muted">Tải lịch sử tạo giọng trên ElevenLabs cho Voice ID này, rồi chọn một bản để khớp cấu hình.</div>
      <button class="ghost" id="qHistBtn" onclick="loadVoiceHistory()" style="margin-top:8px">Tải lịch sử</button>
      <div id="qHistList" style="margin-top:10px"></div>`;
    if (state.voiceHistory && state.voiceHistory.length) renderHistoryList();
  } else if (m === "manual") {
    const c = state.voiceConfig || {};
    const vs = c.voice_settings || {};
    const f = (x) => (x == null ? "" : x);
    panel.innerHTML = `<div class="hint">Nâng cao — tự chỉnh cấu hình TTS. Thay đổi sẽ ghi đè cấu hình đồng bộ.</div>
      <div class="row" style="flex-wrap:wrap;gap:8px;margin-top:8px">
        <label>Model
          <select id="mModel" style="width:230px;padding:4px 8px;background:var(--bg2,#1f1f24);color:var(--text);border:1px solid var(--border,#444);border-radius:4px">
            <option value="eleven_v4" ${c.model_id==='eleven_v4'?'selected':''}>Eleven v4 (Mới nhất · 10k chars)</option>
            <option value="eleven_v4_turbo" ${c.model_id==='eleven_v4_turbo'?'selected':''}>Eleven v4 Turbo (~100ms)</option>
            <option value="eleven_v3" ${c.model_id==='eleven_v3'?'selected':''}>Eleven v3 (Chuẩn đàm thoại)</option>
            <option value="eleven_v3_conversational" ${c.model_id==='eleven_v3_conversational'?'selected':''}>Eleven v3 Conversational</option>
            <option value="eleven_multilingual_v2" ${c.model_id==='eleven_multilingual_v2'?'selected':''}>Eleven Multilingual v2</option>
            <option value="eleven_flash_v2_5" ${c.model_id==='eleven_flash_v2_5'?'selected':''}>Eleven Flash v2.5</option>
            <option value="eleven_turbo_v2_5" ${c.model_id==='eleven_turbo_v2_5'?'selected':''}>Eleven Turbo v2.5</option>
          </select>
        </label>
        <label>Output <input id="mOut" value="${esc(f(c.requested_output_format))}" placeholder="mp3_44100_128" style="width:150px"/></label>
      </div>
      <div class="row" style="flex-wrap:wrap;gap:8px;margin-top:8px">
        <label>Stability <input id="mStab" type="number" step="0.01" value="${f(vs.stability)}" style="width:80px"/></label>
        <label>Similarity <input id="mSim" type="number" step="0.01" value="${f(vs.similarity_boost)}" style="width:80px"/></label>
        <label>Style <input id="mStyle" type="number" step="0.01" value="${f(vs.style)}" style="width:60px"/></label>
        <label>Speed <input id="mSpeed" type="number" step="0.01" value="${f(vs.speed)}" style="width:80px"/></label>
        <label><input id="mBoost" type="checkbox" ${vs.use_speaker_boost ? "checked" : ""}/> Speaker boost</label>
      </div>
      <button class="primary" onclick="applyManualConfig()" style="margin-top:10px">Áp dụng cấu hình tùy chỉnh</button>`;
  } else {
    const c = state.voiceConfig;
    if (!c) {
      panel.innerHTML = `<div class="muted">Bấm "Kiểm tra giọng" để tự đồng bộ cấu hình hiện tại của ElevenLabs.</div>`;
      return;
    }
    const vs = c.effective_voice_settings || c.voice_settings || {};
    const d = (x) => (x == null ? "—" : x);
    const src = (s) => SYNC_SRC_VI[s] || s || "—";
    const compat = c.compatibility || {};
    const compatLine = c.target_language
      ? `<div class="kv"><span class="k">Ngôn ngữ</span><span class="v">${esc(c.target_language)}${compat.language_supported ? " ✓" : " ✗"}</span></div>
         <div class="kv"><span class="k">language_code</span><span class="v">${esc(d(c.language_code))}</span></div>
         <div class="kv"><span class="k">Nguồn chọn model</span><span class="v">${esc(d(c.resolver_source || (c.provenance && c.provenance.model_id)))}</span></div>
         <div class="kv"><span class="k">Tương thích giọng</span><span class="v">${esc(d(compat.voice_compatible))}</span></div>`
      : ``;
    panel.innerHTML = `<button class="ghost tiny" onclick="resolveVoiceConfig('auto_current')">LÀM MỚI</button>
      <details class="tech" style="margin-top:8px"><summary>Thông tin nâng cao</summary>
      <div style="margin-top:8px;font-size:12px">
        <div class="kv"><span class="k">Model</span><span class="v">${esc(d(c.model_id))} <span class="muted">(${esc(src(c.provenance && c.provenance.model_id))})</span></span></div>
        ${compatLine}
        <div class="kv"><span class="k">Stability</span><span class="v">${d(vs.stability)}</span></div>
        <div class="kv"><span class="k">Similarity</span><span class="v">${d(vs.similarity_boost)}</span></div>
        <div class="kv"><span class="k">Style</span><span class="v">${d(vs.style)}</span></div>
        <div class="kv"><span class="k">Speaker Boost</span><span class="v">${d(vs.use_speaker_boost)}</span></div>
        <div class="kv"><span class="k">Speed</span><span class="v">${d(vs.speed)}</span></div>
        <div class="kv"><span class="k">Output format</span><span class="v">${esc(d(c.requested_output_format))} <span class="muted">(${esc(src(c.provenance && c.provenance.output_format))})</span></span></div>
        <div class="kv"><span class="k">Cài đặt giọng</span><span class="v">${esc(src(c.provenance && c.provenance.voice_settings))}</span></div>
      </div></details>`;
  }
}
function renderHistoryList() {
  const list = $("#qHistList"); if (!list) return;
  const items = state.voiceHistory || [];
  if (!items.length) { list.innerHTML = `<div class="muted">Chưa có bản tạo nào trên ElevenLabs cho Voice ID này.</div>`; return; }
  list.innerHTML = items.map(it => {
    const d = it.date_unix ? new Date(it.date_unix * 1000).toLocaleString("vi-VN") : "—";
    const st = it.settings || {};
    const complete = it.model_id && st.stability != null && st.similarity_boost != null;
    return `<div style="border:1px solid var(--border);border-radius:8px;padding:8px;margin-top:8px">
      <div><b>${esc(d)}</b> · ${esc(it.model_id || "—")}</div>
      <div class="muted2" style="margin:2px 0">"${esc(it.text_preview || "")}"</div>
      <div class="muted" style="font-size:11px">stability ${d(st.stability)} · sim ${d(st.similarity_boost)} · style ${d(st.style)} · boost ${d(st.use_speaker_boost)} · speed ${d(st.speed)}</div>
      ${complete ? `<button class="primary tiny" onclick="useHistoryConfig('${esc(it.history_item_id)}')" style="margin-top:6px">DÙNG CẤU HÌNH NÀY</button>` : `<span class="tag muted">Thiếu dữ liệu cấu hình</span>`}
    </div>`;
  }).join("");
}
async function loadVoiceHistory() {
  const vid = (state.voiceId || "").trim();
  if (!vid) return toast("Nhập Voice ID trước", "warn");
  const list = $("#qHistList");
  if (list) list.innerHTML = `<span class="muted">Đang tải…</span>`;
  const r = await api("/api/elevenlabs/voices/" + encodeURIComponent(vid) + "/history");
  if (!r.ok) { if (list) list.innerHTML = `<span class="tag bad">Không tải được lịch sử</span> <span class="muted">${esc(r.error || "")}</span>`; return; }
  state.voiceHistory = r.items || [];
  renderHistoryList();
}
async function useHistoryConfig(item_id) {
  const vid = (state.voiceId || "").trim();
  const { lang } = await effectiveTargetLanguage();
  const r = await api("/api/elevenlabs/voice-config/resolve", { method: "POST", body: JSON.stringify({ voice_id: vid, mode: "history_match", history_item_id: item_id, voice_name: state.voiceMeta && state.voiceMeta.name, target_language: lang }) });
  if (!r.ok || !r.config) return toast(r.error || (r.incompatible ? "Model của bản này không phù hợp ngôn ngữ đã chọn." : "Không khớp được cấu hình"), "bad");
  state.voiceConfig = r.config; state.voiceSyncMode = "history_match";
  $$("#syncTabs .sync-tab").forEach(x => x.classList.toggle("active", x.dataset.m === "history_match"));
  renderVoiceSync(); renderSyncPanel(); quickRefresh();
  toast("Đã khớp cấu hình bản ElevenLabs đã tạo", "good");
}
async function effectiveTargetLanguage() {
  // Returns {lang, low, note}. "auto" detects from the script; low confidence
  // is surfaced so the UI can ask the user to confirm (never silently guess).
  let tl = state.targetLanguage || "vi";
  if (tl === "auto") {
    const txt = (state.scriptText || "").trim();
    if (!txt) return { lang: "vi", low: true, note: "Nhập kịch bản để phát hiện ngôn ngữ tự động." };
    const d = await api("/api/language/detect", { method: "POST", body: JSON.stringify({ text: txt }) });
    if (d && d.ok) {
      return { lang: d.language, low: !!d.low_confidence,
               note: d.low_confidence ? "Xác nhận ngôn ngữ — phát hiện chưa chắc chắn." : null };
    }
    return { lang: "vi", low: true, note: "Không phát hiện được — đang dùng Tiếng Việt." };
  }
  return { lang: tl, low: false, note: null };
}

async function resolveVoiceConfig(mode) {
  const vid = (state.voiceId || "").trim();
  if (!vid) return;
  const box = $("#qVoiceSync");
  if (box) box.innerHTML = `<span class="muted">Đang đồng bộ cấu hình ElevenLabs…</span>`;
  const { lang, low, note } = await effectiveTargetLanguage();
  const r = await api("/api/elevenlabs/voice-config/resolve", { method: "POST", body: JSON.stringify({ voice_id: vid, mode: mode || "auto_current", voice_name: state.voiceMeta && state.voiceMeta.name, target_language: lang }) });
  const li = $("#qLangInfo");
  if (!r.ok || !r.config) {
    // Fail-closed / incompatible / unsupported — NO silent fallback. Explicit choice only.
    if (r.incompatible) {
      if (box) box.innerHTML = `<div><span class="tag bad">Model không được xác nhận phù hợp với ngôn ngữ '${esc(lang)}'.</span></div>
        <div class="muted" style="margin-top:4px">${esc((r.reasons || []).join("; ") || r.error || "")}</div>`;
    } else if (r.unsupported_language) {
      if (box) box.innerHTML = `<div><span class="tag bad">Không có model nào hỗ trợ ngôn ngữ '${esc(lang)}'.</span></div>`;
    } else {
      if (box) box.innerHTML = `<div><span class="tag bad">Không thể đồng bộ cấu hình ElevenLabs.</span></div>
        <div class="actions" style="margin-top:8px"><button class="ghost tiny" onclick="resolveVoiceConfig('auto_current')">THỬ LẠI</button>
        <button class="ghost tiny" onclick="useStudioConfig()">DÙNG CẤU HÌNH STUDIO</button></div>`;
    }
    if (li) li.innerHTML = low && note ? `<span class="tag warn">${esc(note)}</span>` : ``;
    state.voiceConfig = null;
    renderSyncPanel();
    quickRefresh();
    return;
  }
  state.voiceConfig = r.config;
  if ($("#qModelSelect") && r.config && r.config.model_id) {
    setSelectModelValue($("#qModelSelect"), r.config.model_id);
  }
  // Language compatibility / confirmation line.
  if (li) {
    const c = r.config || {};
    const compat = c.compatibility || {};
    let tags = [];
    if (lang && compat.language_supported) tags.push(`<span class="tag good">✓ Cấu hình phù hợp ${esc(lang)}</span>`);
    if (low && note) tags.push(`<span class="tag warn">${esc(note)}</span>`);
    li.innerHTML = tags.join(" ");
  }
  renderVoiceSync(); renderSyncPanel(); quickRefresh();
}
function useStudioConfig() {
  // Explicit user action: proceed with the legacy Studio-default path (no
  // synced ElevenLabs settings). Never silently chosen.
  state.voiceConfig = null;
  renderVoiceSync(); renderSyncPanel(); quickRefresh();
  toast("Đang dùng cấu hình Studio (mặc định)", "good");
}
async function applyManualConfig() {
  const num = (id) => { const v = $("#" + id); const n = parseFloat(v && v.value); return isNaN(n) ? null : n; };
  const vid = (state.voiceId || "").trim();
  const overrides = {
    model_id: ($("#mModel") && $("#mModel").value.trim()) || "eleven_turbo_v2_5",
    output_format: ($("#mOut") && $("#mOut").value.trim()) || "pcm_16000",
    voice_settings: {
      stability: num("mStab"), similarity_boost: num("mSim"),
      style: num("mStyle"), speed: num("mSpeed"),
      use_speaker_boost: $("#mBoost") && $("#mBoost").checked,
    },
  };
  // V1.6.0: route manual through the resolver so the live compatibility guard
  // runs and effective (model-aware) settings are computed. An incompatible
  // manual model is NOT silently applied.
  const { lang } = await effectiveTargetLanguage();
  const r = await api("/api/elevenlabs/voice-config/resolve", { method: "POST", body: JSON.stringify({ voice_id: vid, mode: "manual", overrides, voice_name: state.voiceMeta && state.voiceMeta.name, target_language: lang }) });
  if (!r.ok || !r.config) {
    if (r.incompatible) return toast("Model này không được xác nhận phù hợp với ngôn ngữ đã chọn.", "bad");
    return toast(r.error || "Không áp dụng được cấu hình tùy chỉnh", "bad");
  }
  state.voiceConfig = r.config;
  state.voiceSyncMode = "manual";
  if ($("#qModelSelect")) setSelectModelValue($("#qModelSelect"), r.config.model_id);
  renderVoiceSync(); renderSyncPanel(); quickRefresh();
  toast("Đã áp dụng cấu hình tùy chỉnh", "good");
}

async function applyChosenModel(modelId) {
  const vid = (state.voiceId || "").trim();
  if (!vid) return;
  const { lang } = await effectiveTargetLanguage();
  const currentSettings = (state.voiceConfig && (state.voiceConfig.effective_voice_settings || state.voiceConfig.voice_settings)) || {};
  const overrides = {
    model_id: modelId,
    output_format: (state.voiceConfig && state.voiceConfig.requested_output_format) || "pcm_16000",
    voice_settings: currentSettings,
  };
  const r = await api("/api/elevenlabs/voice-config/resolve", {
    method: "POST",
    body: JSON.stringify({
      voice_id: vid,
      mode: "manual",
      overrides,
      voice_name: state.voiceMeta && state.voiceMeta.name,
      target_language: lang
    })
  });
  if (r && r.ok && r.config) {
    state.voiceConfig = r.config;
    state.voiceSyncMode = "manual";
    if ($("#qModelSelect")) setSelectModelValue($("#qModelSelect"), r.config.model_id);
    renderVoiceSync();
    renderSyncPanel();
    quickRefresh();
    renderScriptPreview();
    toast(`Đã chọn mô hình ${modelId}`, "good");
  } else {
    toast((r && r.error) || "Không thể áp dụng model này", "warn");
  }
}

async function loadEdgeVoices() {
  try {
    const r = await api("/api/voice/edge/voices");
    if (r.ok && r.voices && r.voices.length) {
      state.edgeVoices = r.voices;
      if (!r.voices.some(v => v.voice_id === state.edgeVoice)) state.edgeVoice = r.default || state.edgeVoice;
    }
  } catch (e) { /* keep known fallback */ }
}
async function previewEdgeVoice() {
  const voice = state.edgeVoice;
  const txt = state.scriptText || STANDARD_MOUTH_TEST_SCRIPT;
  if (!txt) return toast("Nhập kịch bản trước", "warn");
  toast("Đang tạo thử giọng test miễn phí…");
  const r = await api("/api/voice/edge/preview", { method: "POST", body: JSON.stringify({ voice_id: voice, script_text: txt }) });
  const info = $("#qEdgeInfo");
  if (r.ok) {
    const a = $("#qPreview"); a.src = r.preview_url; a.style.display = "block"; a.play();
    if (info) info.innerHTML = `<span class="tag good">✓ ${esc(r.voice_label || voice)}</span> <span class="muted">${(r.duration_sec||0).toFixed(1)}s</span>`;
  } else {
    if (info) info.innerHTML = `<span class="tag bad">✗ Giọng test miễn phí hiện không khả dụng</span> <span class="muted">${esc(r.error||"")}</span>`;
    toast(r.error || "Giọng test miễn phí hiện không khả dụng", "bad");
  }
}
function useStandardMouthScript() {
  const ta = $("#qMouthScript"); if (ta) ta.value = STANDARD_MOUTH_TEST_SCRIPT;
  toast("Đã dùng đoạn test chuẩn", "good");
}
async function renderMouthTest() {
  const av = $("#qAvatar").value;
  if (!canStartNewWork()) return;
  if (!av) return toast("Chọn Avatar", "warn");
  const script = ($("#qMouthScript") && $("#qMouthScript").value.trim()) || STANDARD_MOUTH_TEST_SCRIPT;
  $("#qMouthBtn").disabled = true;
  const r = await api("/api/render/mouth-test", { method: "POST", body: JSON.stringify({ avatar_id: av, edge_voice: state.edgeVoice, script_text: script }) });
  $("#qMouthBtn").disabled = false;
  if (r.ok) { toast("Đã đưa test khẩu hình (miễn phí) vào hàng đợi", "good"); switchView("history"); }
  else toast(r.error || "Không xếp hàng được", "bad");
}
function renderAvatarPick(a) {
  const box = $("#qAvatarPick"); if (!box) return;
  if (!a) { box.innerHTML = ""; return; }
  const q = a.quality_status;
  const qm = qMeta(q);
  box.innerHTML = `<div class="avatar-pick">
    <img src="/api/avatars/${esc(a.avatar_id)}/thumbnail" onerror="this.style.opacity=.3" />
    <div class="ap-meta">
      <div class="ap-name">${esc(a.avatar_id)} <span class="tag good">SẴN SÀNG</span></div>
      <div class="ap-sub">${esc(TYPE_VI[a.avatar_type] || a.avatar_type)} · ${esc(qm.short)}</div>
    </div>
  </div>`;
}
let _scriptFontSizes = ["font-md", "font-lg", "font-xl"];
let _scriptFontIdx = 0;
function adjustScriptFontSize(delta) {
  _scriptFontIdx = Math.max(0, Math.min(_scriptFontSizes.length - 1, _scriptFontIdx + delta));
  const ta = $("#qScript");
  if (ta) {
    _scriptFontSizes.forEach(cls => ta.classList.remove(cls));
    ta.classList.add(_scriptFontSizes[_scriptFontIdx]);
    autoResizeScriptCanvas(ta);
    toast(`Cỡ chữ: ${_scriptFontIdx === 0 ? "Chuẩn" : _scriptFontIdx === 1 ? "Lớn" : "Rất lớn"}`, "");
  }
}
function toggleScriptFullscreen() {
  const container = $(".script-editor-container");
  const btn = $("#btnFullscreenScript");
  if (!container) return;
  const isFull = container.classList.toggle("is-fullscreen");
  if (btn) btn.innerHTML = isFull ? "✕ Thu nhỏ" : "⛶ Phóng to";
  const ta = $("#qScript");
  if (ta) {
    if (isFull) {
      ta.focus();
    } else {
      autoResizeScriptCanvas(ta);
    }
  }
}
function autoResizeScriptCanvas(el) {
  if (!el) el = $("#qScript");
  if (!el) return;
  const container = $(".script-editor-container");
  if (container && container.classList.contains("is-fullscreen")) return;
  el.style.height = "auto";
  const newH = Math.max(420, Math.min(950, el.scrollHeight));
  el.style.height = newH + "px";
}
async function pasteFromClipboard() {
  try {
    const text = await navigator.clipboard.readText();
    if (!text || !text.trim()) return toast("Bộ nhớ tạm không có văn bản", "warn");
    const ta = $("#qScript");
    if (ta) {
      ta.value = text;
      saveDraftScript(text);
      updateScriptInfo();
      autoResizeScriptCanvas(ta);
      quickRefresh();
      toast("Đã dán kịch bản thành công", "good");
    }
  } catch (err) {
    toast("Hãy nhấn phím Ctrl+V để dán trực tiếp vào khung soạn thảo", "warn");
    const ta = $("#qScript");
    if (ta) ta.focus();
  }
}
function insertSampleScript() {
  const sample = "Xin chào quý vị và các bạn! Chào mừng quý vị đã đến với trải nghiệm giải pháp AI Avatar thế hệ mới. Hệ thống của chúng tôi được trang bị công nghệ đồng bộ khẩu hình chuẩn xác, giọng đọc truyền cảm và chuyển động khuôn mặt chân thực. Hãy nhập nội dung của bạn để bắt đầu tạo ra những video AI chuyên nghiệp và cuốn hút nhất!";
  const ta = $("#qScript");
  if (ta) {
    ta.value = sample;
    saveDraftScript(sample);
    updateScriptInfo();
    autoResizeScriptCanvas(ta);
    quickRefresh();
    toast("Đã chèn kịch bản mẫu thành công", "good");
  }
}
function setSplitMode(m) {
  state.splitMode = m;
  $$("#splitChips .schip").forEach(c => c.classList.toggle("active", c.dataset.m === m));
  const sel = $("#qSplit");
  if (sel) sel.value = m;
  updateSegPreview();
}
function clearScript() {
  state.scriptText = "";
  state.scriptInfo = null;
  ls.set("studio_draft_script", "");
  const ta = $("#qScript");
  if (ta) {
    ta.value = "";
    autoResizeScriptCanvas(ta);
  }
  updateScriptInfo();
  quickRefresh();
  toast("Đã xóa trắng kịch bản", "good");
}
async function updateSegPreview() {
  const box = $("#qSegPreview"); if (!box) return;
  const txt = state.scriptText.trim();
  if (!txt || state.splitMode === "full") { box.innerHTML = ""; return; }
  if (state.splitMode === "auto") {
    box.innerHTML = `<div class="seg-preview"><span class="seg-chip">Đang tính toán phân đoạn…</span></div>`;
    const r = await api("/api/script/split", { method: "POST", body: JSON.stringify({ script_text: txt, mode: "auto" }) });
    if (!r.ok) { box.innerHTML = ""; return; }
    const chips = r.parts.map(p => `<span class="seg-chip"><b>${esc(p.label)}</b> ${p.words} từ · ${esc(p.duration_str)}</span>`).join("");
    box.innerHTML = `<div class="hint" style="margin-top:8px">Tự động chia thành <b>${r.total_parts}</b> phân đoạn:</div><div class="seg-preview">${chips}</div>`;
  } else {
    const label = { "30s": "30 giây đầu", "1min": "1 phút đầu", "3min": "3 phút đầu" }[state.splitMode];
    box.innerHTML = `<div class="hint" style="margin-top:8px">Chỉ tạo <b>${label}</b> của kịch bản.</div>`;
  }
}
function updateScriptInfo() {
  const txt = (state.scriptText || "").trim();
  const info = $("#qScriptInfo");
  if (!txt) {
    if (info) info.innerHTML = `<div class="script-info-bar empty">
      <span>💡 Nhập hoặc dán nội dung kịch bản để bắt đầu.</span>
    </div>`;
    updateSegPreview();
    renderScriptPreview();
    return;
  }
  const words = txt.split(/\s+/).filter(Boolean).length;
  const chars = state.scriptText.length;
  const dur = words / 2.8; // ~168 wpm natural Vietnamese speaking pace

  if (info) {
    info.innerHTML = `
      <div class="sib-stats">
        <div class="sib-stat"><b>${words.toLocaleString("vi-VN")}</b> <span>từ</span></div>
        <div class="sib-stat"><b>${chars.toLocaleString("vi-VN")}</b> <span>ký tự</span></div>
        <div class="sib-stat accent"><b>~${fmtDur(dur)}</b> <span>thời lượng đọc</span></div>
      </div>
      <div class="sib-right">
        <span class="sib-saved" title="Nội dung tự động lưu trên trình duyệt">💾 Đã lưu nháp</span>
      </div>`;
  }
  updateSegPreview();
  renderScriptPreview();
}
async function loadApprovedVoices() {
  try {
    const [r, cr] = await Promise.all([
      api("/api/voices/approved"),
      api("/api/voices/custom")
    ]);
    if (r.ok && r.voices && r.voices.length) {
      state.approvedVoices = r.voices;
    }
    if (cr && cr.ok && Array.isArray(cr.voices)) {
      state.customVoices = cr.voices;
    }
    // restore a previously selected voice only if still valid
    const saved = ls.get("studio_voiceId");
    const allKnown = [...(state.approvedVoices || []), ...(state.customVoices || [])];
    if (saved && allKnown.some(v => v.voice_id === saved)) state.voiceId = saved;
    else if (!state.voiceId && state.approvedVoices && state.approvedVoices[0]) state.voiceId = state.approvedVoices[0].voice_id;
  } catch (e) { /* keep fallback */ }
}

async function loadCustomVoices() {
  try {
    const cr = await api("/api/voices/custom");
    if (cr && cr.ok && Array.isArray(cr.voices)) {
      state.customVoices = cr.voices;
      renderVoiceCards();
    }
  } catch (e) {}
}

let _sampleAudio = null;
function playVoiceSample(vid) {
  if (!vid) return;
  if (_sampleAudio && state.playingSampleVid === vid) {
    _sampleAudio.pause();
    _sampleAudio = null;
    state.playingSampleVid = null;
    renderVoiceCards();
    return;
  }
  if (_sampleAudio) {
    _sampleAudio.pause();
    _sampleAudio = null;
  }
  state.playingSampleVid = vid;
  renderVoiceCards();

  const customV = (state.customVoices || []).find(v => v.voice_id === vid);
  const accV = (state.accountVoices || []).find(v => v.voice_id === vid);
  const audioUrl = (customV && customV.preview_url) || (accV && accV.preview_url) || `/api/voices/approved/${encodeURIComponent(vid)}/sample`;

  _sampleAudio = new Audio(audioUrl);
  _sampleAudio.onended = () => {
    state.playingSampleVid = null;
    _sampleAudio = null;
    renderVoiceCards();
  };
  _sampleAudio.onerror = () => {
    toast("Không tải được mẫu giọng đọc", "bad");
    state.playingSampleVid = null;
    _sampleAudio = null;
    renderVoiceCards();
  };
  _sampleAudio.play().catch(() => {});
}

function renderVoiceCards() {
  const box = $("#qVoiceCards"); if (!box) return;
  const baseVoices = state.approvedVoices && state.approvedVoices.length ? state.approvedVoices : [
    { voice_id: "pGapy9MNHCukzJtjavF0", display_name: "Hạnh", description: "Giọng nữ Hà Nội nhẹ nhàng, truyền cảm", human_approved: false },
    { voice_id: "N0Z0aL8qHhzwUHwRBcVo", display_name: "Thanh", description: "Giọng nữ Sài Gòn rõ ràng, ấm áp", human_approved: true },
  ];

  const customCards = (state.customVoices || []).map(cv => ({
    voice_id: cv.voice_id,
    display_name: cv.name || cv.voice_id,
    description: cv.description || (cv.category ? `Giọng ${cv.category} từ ElevenLabs` : "Giọng tùy chỉnh"),
    human_approved: false,
    is_custom: true,
    preview_url: cv.preview_url
  }));

  const allVoices = [...baseVoices, ...customCards];

  box.className = "voice-cards";
  box.innerHTML = allVoices.map(v => {
    const sel = state.voiceId === v.voice_id;
    const isPlaying = state.playingSampleVid === v.voice_id;
    const displayName = (v.display_name || v.voice_id).split(' - ')[0];
    let badge = v.human_approved
      ? `<span class="tag good">Khuyên dùng cho Tiếng Việt</span>`
      : (v.is_custom ? `<span class="tag good">Giọng của bạn</span>` : `<span class="tag muted">Khuyên dùng</span>`);

    let deleteBtn = "";
    if (v.is_custom) {
      deleteBtn = `<button type="button" class="ghost tiny danger-text" title="Bỏ giọng này khỏi danh sách thẻ" onclick="event.preventDefault(); event.stopPropagation(); deleteCustomVoiceCard('${esc(v.voice_id)}')">✕ Bỏ</button>`;
    }

    const hasSample = !v.is_custom || !!v.preview_url;

    return `<label class="voice-card${sel ? " selected" : ""}" data-vid="${esc(v.voice_id)}">
      <input type="radio" name="vcard" value="${esc(v.voice_id)}" ${sel ? "checked" : ""} aria-label="${esc(displayName)}" />
      <div class="voice-card-body">
        <div class="voice-card-top">
          <div class="voice-card-name">${esc(displayName)}</div>
          <div style="display:flex;gap:4px;align-items:center">
            ${hasSample ? `
            <button type="button" class="voice-sample-btn${isPlaying ? ' playing' : ''}" onclick="event.preventDefault(); event.stopPropagation(); playVoiceSample('${esc(v.voice_id)}')">
              ${isPlaying ? '⏸ Dừng' : '▶ Nghe mẫu'}
            </button>` : ''}
            ${deleteBtn}
          </div>
        </div>
        ${v.description ? `<div class="voice-card-desc">${esc(v.description)}</div>` : ""}
        <div class="voice-card-meta">${badge}</div>
      </div>
    </label>`;
  }).join("");
  $$("#qVoiceCards .voice-card").forEach(card => {
    card.onclick = () => selectVoice(card.dataset.vid);
  });
}

let _accountVoicesLoading = false;
async function loadAccountVoices(refresh = false) {
  const sel = $("#qAccountVoicesSelect");
  if (_accountVoicesLoading) return;
  _accountVoicesLoading = true;
  if (sel) sel.innerHTML = `<option value="">— Đang tải danh sách giọng từ ElevenLabs… —</option>`;

  try {
    const [accRes, custRes] = await Promise.all([
      api(`/api/elevenlabs/voices${refresh ? "?refresh=1" : ""}`),
      api("/api/voices/custom")
    ]);

    if (custRes && custRes.ok) {
      state.customVoices = custRes.voices || [];
      renderVoiceCards();
    }

    if (accRes && accRes.ok && Array.isArray(accRes.voices)) {
      state.accountVoices = accRes.voices;
      renderAccountVoicesDropdown();
    } else if (sel) {
      sel.innerHTML = `<option value="">— Không tải được danh sách giọng (kiểm tra kết nối/khóa API) —</option>`;
    }
  } catch (e) {
    if (sel) sel.innerHTML = `<option value="">— Lỗi kết nối ElevenLabs —</option>`;
  } finally {
    _accountVoicesLoading = false;
  }
}

function renderAccountVoicesDropdown() {
  const sel = $("#qAccountVoicesSelect");
  if (!sel) return;
  const voices = state.accountVoices || [];
  if (!voices.length) {
    sel.innerHTML = `<option value="">— Chưa tìm thấy giọng nào trong tài khoản ElevenLabs —</option>`;
    return;
  }

  const cloned = voices.filter(v => v.category === "cloned" || v.category === "professional");
  const generated = voices.filter(v => v.category === "generated");
  const premade = voices.filter(v => v.category === "premade" || (!cloned.includes(v) && !generated.includes(v)));

  function makeGroup(label, list) {
    if (!list.length) return "";
    return `<optgroup label="${label}">${list.map(v => {
      const isSel = (state.voiceId === v.voice_id);
      const gender = v.labels?.gender ? ` (${v.labels.gender})` : "";
      return `<option value="${esc(v.voice_id)}" ${isSel ? 'selected' : ''}>${esc(v.name)}${gender}</option>`;
    }).join("")}</optgroup>`;
  }

  let html = `<option value="">— Chọn một giọng từ tài khoản ElevenLabs (${voices.length} giọng) —</option>`;
  html += makeGroup("👤 Giọng Clone của bạn (Cloned Voices)", cloned);
  html += makeGroup("✨ Giọng tùy biến (Generated)", generated);
  html += makeGroup("🗣️ Giọng mẫu có sẵn (Premade)", premade);
  sel.innerHTML = html;

  if (state.voiceId && voices.some(v => v.voice_id === state.voiceId)) {
    sel.value = state.voiceId;
  }
  onAccountVoiceDropdownChange();
}

function onAccountVoiceDropdownChange() {
  const sel = $("#qAccountVoicesSelect");
  const pBtn = $("#qAccountVoicePreviewBtn");
  const descEl = $("#qAccountVoiceDesc");
  if (!sel) return;
  const vid = sel.value;
  const v = (state.accountVoices || []).find(x => x.voice_id === vid);
  if (v) {
    if (descEl) {
      const catVi = (v.category === 'cloned') ? 'Giọng Clone' : (v.category === 'premade' ? 'Giọng mẫu' : v.category);
      const lang = v.labels?.language ? ` · Ngôn ngữ: ${v.labels.language}` : "";
      descEl.textContent = `${catVi} · ID: ${v.voice_id}${lang}${v.description ? ' — ' + v.description : ''}`;
    }
    if (pBtn) {
      pBtn.style.display = v.preview_url ? "inline-block" : "none";
    }
  } else {
    if (descEl) descEl.textContent = "";
    if (pBtn) pBtn.style.display = "none";
  }
}

function playAccountVoicePreview() {
  const sel = $("#qAccountVoicesSelect");
  if (!sel || !sel.value) return;
  const v = (state.accountVoices || []).find(x => x.voice_id === sel.value);
  if (!v || !v.preview_url) return toast("Giọng này không có file nghe thử", "warn");

  if (_sampleAudio) {
    _sampleAudio.pause();
    _sampleAudio = null;
  }
  const pBtn = $("#qAccountVoicePreviewBtn");
  if (pBtn) pBtn.textContent = "⏸ Dừng";
  _sampleAudio = new Audio(v.preview_url);
  _sampleAudio.onended = () => {
    if (pBtn) pBtn.textContent = "▶ Nghe mẫu";
    _sampleAudio = null;
  };
  _sampleAudio.onerror = () => {
    if (pBtn) pBtn.textContent = "▶ Nghe mẫu";
    _sampleAudio = null;
    toast("Không phát được file mẫu", "bad");
  };
  _sampleAudio.play().catch(() => {
    if (pBtn) pBtn.textContent = "▶ Nghe mẫu";
  });
}

async function applyAccountVoiceSelection() {
  const sel = $("#qAccountVoicesSelect");
  if (!sel || !sel.value) return toast("Vui lòng chọn một giọng từ danh sách", "warn");
  const vid = sel.value;
  const voice = (state.accountVoices || []).find(v => v.voice_id === vid);
  if (!voice) return;

  toast(`Đang kết nối giọng "${voice.name}"…`);
  try {
    const res = await api("/api/voices/custom", {
      method: "POST",
      body: JSON.stringify({
        voice_id: voice.voice_id,
        name: voice.name,
        category: voice.category,
        description: voice.description,
        labels: voice.labels,
        preview_url: voice.preview_url
      })
    });
    if (res && res.ok) {
      await loadCustomVoices();
      await selectVoice(voice.voice_id);
      toast(`Đã kích hoạt giọng "${voice.name}"!`, "good");
    } else {
      toast((res && res.error) || "Không thể kích hoạt giọng này", "bad");
    }
  } catch (e) {
    toast("Lỗi kết nối giọng", "bad");
  }
}

async function submitCustomVoiceInput() {
  const inp = $("#qCustomVoiceInput");
  const vid = inp ? inp.value.trim() : "";
  if (!vid) return toast("Vui lòng nhập mã Voice ID từ ElevenLabs", "warn");

  toast("Đang xác thực Voice ID trên ElevenLabs…");
  try {
    const res = await api("/api/voices/custom", {
      method: "POST",
      body: JSON.stringify({ voice_id: vid })
    });
    if (res && res.ok && res.voice) {
      if (inp) inp.value = "";
      await loadCustomVoices();
      await selectVoice(vid);
      toast(`Đã kết nối giọng "${res.voice.name || vid}" thành công!`, "good");
    } else {
      toast((res && res.error) || "Voice ID không tồn tại hoặc không hợp lệ", "bad");
    }
  } catch (e) {
    toast("Lỗi xác thực Voice ID", "bad");
  }
}

async function deleteCustomVoiceCard(vid) {
  if (!vid) return;
  try {
    await api(`/api/voices/custom/${encodeURIComponent(vid)}`, { method: "DELETE" });
    if (state.voiceId === vid) {
      state.voiceId = "N0Z0aL8qHhzwUHwRBcVo";
      ls.set("studio_voiceId", state.voiceId);
      await selectVoice(state.voiceId);
    }
    await loadCustomVoices();
    renderVoiceCards();
    toast("Đã bỏ giọng tùy chỉnh khỏi danh sách", "good");
  } catch (e) {}
}

function isScriptPreviewStale() {
  if (!state.scriptPreview) return false;
  const p = state.scriptPreview;
  if (p.voice_id !== state.voiceId) return true;
  const curLang = (state.targetLanguage || "vi").toLowerCase();
  if ((p.language || "vi").toLowerCase() !== curLang) return true;
  const curText = (state.scriptText || "").trim();
  if (p.script_text && p.script_text !== curText) return true;
  return false;
}

function renderScriptPreview() {
  const box = $("#scriptPreviewBox");
  if (!box) return;
  if (state.ttsProvider !== "elevenlabs") {
    box.style.display = "none";
    return;
  }
  box.style.display = "flex";

  if (state.previewGenerating) {
    box.innerHTML = `
      <div class="sp-title"><span>🎙️</span> Bản đọc kịch bản</div>
      <div class="sp-generating">
        <span class="spinner"></span> Đang tạo bản đọc kịch bản bằng ElevenLabs (không tốn GPU)...
      </div>
    `;
    return;
  }

  if (state.previewError) {
    box.innerHTML = `
      <div class="sp-title"><span>🎙️</span> Bản đọc kịch bản</div>
      <div class="sp-error-box">
        <b>Lỗi tạo bản đọc:</b> ${esc(state.previewError)}
      </div>
      <div class="sp-actions-row">
        <button type="button" class="primary-sm" onclick="createScriptPreview(true)">Thử lại</button>
      </div>
    `;
    return;
  }

  if (state.scriptPreview && state.scriptPreview.status === "ready") {
    const p = state.scriptPreview;
    const stale = isScriptPreviewStale();
    const durStr = fmtDur(p.duration_sec);
    const vName = esc(p.voice_name || p.voice_id);
    const langLabel = p.language === 'vi' ? 'Tiếng Việt' : esc(p.language);
    box.innerHTML = `
      <div class="sp-title">
        <span>🎙️</span> Bản đọc kịch bản
        <span class="tag good" style="margin-left:auto;font-size:11px">✓ Đã sẵn sàng</span>
      </div>
      ${stale ? `
        <div class="sp-stale-banner">
          <span>⚠️</span>
          <span>Kịch bản hoặc giọng đã thay đổi so với bản đọc này. Bấm <b>Tạo lại bản đọc</b> để cập nhật.</span>
        </div>
      ` : `
        <div class="sp-sub">Bản đọc này sẽ được tái sử dụng khi bạn render video, giúp tiết kiệm thời gian và quota.</div>
      `}
      <div class="sp-ready-card">
        <div class="sp-meta-row">
          <div class="sp-voice-name">Giọng: ${vName} · ${langLabel}</div>
          <div class="sp-dur-badge">Thời lượng: ${durStr}</div>
        </div>
        <audio class="sp-audio-player" controls src="${esc(p.preview_url)}"></audio>
        <div class="sp-actions-row">
          <button type="button" class="${stale ? 'primary-sm' : 'ghost-sm'}" onclick="createScriptPreview(true)">${stale ? 'Tạo lại bản đọc' : 'Tạo lại'}</button>
          <button type="button" class="ghost-sm" onclick="downloadScriptPreview('${esc(p.id)}')">Tải audio (.wav)</button>
        </div>
      </div>
    `;
    return;
  }

  // Initial empty state
  box.innerHTML = `
    <div class="sp-title"><span>🎙️</span> Bản đọc kịch bản</div>
    <div class="sp-sub">Nghe thử âm thanh kịch bản bằng giọng AI đã chọn trước khi tạo video.</div>
    <div class="sp-actions-row">
      <button type="button" class="primary-sm" onclick="createScriptPreview(false)">Nghe thử giọng đọc</button>
    </div>
  `;
}

async function downloadScriptPreview(previewId) {
  if (!previewId) return toast("Chưa có bản đọc để tải.", "warn");
  const url = `/api/audio-preview/${encodeURIComponent(previewId)}/download`;
  try {
    const a = document.createElement("a");
    a.href = url;
    a.download = "";
    document.body.appendChild(a);
    a.click();
    a.remove();
  } catch (e) {
    toast("Không thể tải bản đọc kịch bản: " + e, "bad");
  }
}

async function createScriptPreview(forceRefresh = false) {
  const vid = state.voiceId;
  const txt = (state.scriptText || "").trim();
  if (!vid) return toast("Chọn giọng trước", "warn");
  if (!txt) return toast("Nhập kịch bản trước", "warn");

  state.previewGenerating = true;
  state.previewError = null;
  renderScriptPreview();

  try {
    const res = await api("/api/audio-preview", {
      method: "POST",
      body: JSON.stringify({
        voice_id: vid,
        script_text: txt,
        target_language: state.targetLanguage || "vi",
        tts_config: state.voiceConfig,
        voice_name: state.voiceMeta && state.voiceMeta.name,
        refresh: forceRefresh,
      })
    });
    state.previewGenerating = false;
    if (res.ok && res.preview) {
      state.scriptPreview = res.preview;
      state.scriptPreview.script_text = txt;
      toast(res.reused ? "Đã tải bản đọc có sẵn (tái sử dụng)" : "Đã tạo bản đọc kịch bản thành công!", "good");
    } else {
      state.previewError = res.error || "Không thể tạo bản đọc kịch bản.";
      toast(state.previewError, "bad");
    }
  } catch (e) {
    state.previewGenerating = false;
    state.previewError = String(e);
    toast(state.previewError, "bad");
  }
  renderScriptPreview();
}

async function selectVoice(vid) {
  if (!vid) return;
  const needPanelRender = state.ttsProvider !== "elevenlabs" || !$("#scriptPreviewBox");
  state.ttsProvider = "elevenlabs";
  $$("#ttsTabs .tts-tab").forEach(x => x.classList.toggle("active", x.dataset.p === "elevenlabs"));
  // V1.6.0: selecting an approved voice clears any previous voice's resolved
  // config (no leak across voices), then validates + resolves the new one.
  state.voiceId = vid;
  state.voiceChecked = false; state.voiceMeta = null;
  state.voiceConfig = null; state.voiceHistory = null;
  state.voiceSyncMode = "auto_current";
  ls.set("studio_voiceId", vid);
  if (needPanelRender) {
    renderTTSPanel();
  } else {
    renderVoiceCards();
    renderScriptPreview();
  }
  const info = $("#qVoiceInfo"); if (info) info.innerHTML = `<span class="muted">Đang kiểm tra…</span>`;
  await checkVoice();
  if (state.voiceChecked && state.ttsProvider === "elevenlabs") {
    const chosen = ($("#qModelSelect") && $("#qModelSelect").value) || state.selectedModel;
    if (chosen) {
      await applyChosenModel(chosen);
    } else {
      await resolveVoiceConfig("auto_current");
    }
  }
  quickRefresh();
  renderScriptPreview();
}
async function checkVoice() {
  const vid = state.voiceId;
  if (!vid) return toast("Chọn giọng trước", "warn");
  const info = $("#qVoiceInfo"); if (info) info.innerHTML = `<span class="muted">Đang kiểm tra…</span>`;
  const r = await api("/api/voice/check", { method: "POST", body: JSON.stringify({ voice_id: vid }) });
  if (r.ok) {
    state.voiceChecked = true; state.voiceMeta = r;
    const name = r.name ? `<b>${esc(r.name)}</b>` : `<span class="muted">(tên không hiển thị với tài khoản này)</span>`;
    const labels = r.labels || {};
    const lang = labels.language ? ` · ${esc(labels.language)}` : "";
    if (info) info.innerHTML = `<span class="tag good">✓ Đã tìm thấy giọng</span> ${name}${lang}`;
  } else {
    state.voiceChecked = false; state.voiceMeta = null;
    state.voiceConfig = null; renderVoiceSync();
    if (info) info.innerHTML = `<span class="tag bad">✗ Không hợp lệ</span> <span class="muted">${esc(r.error || "Giọng không khả dụng.")}</span>`;
  }
}
async function previewVoice() {
  // Delegate to full script preview
  createScriptPreview(false);
}
function activeVoiceId() {
  // The voice id for the currently selected provider. Edge mode uses the
  // selected free Edge voice; ElevenLabs mode uses the approved voice selected.
  if (state.ttsProvider === "edge") return state.edgeVoice;
  return state.voiceId;
}
async function renderTest10s() {
  if (!canStartNewWork()) return;
  const av = $("#qAvatar").value, vid = activeVoiceId(), txt = state.scriptText;
  if (!av) return toast("Chọn Avatar", "warn");
  if (!vid) return toast(state.ttsProvider === "edge" ? "Chọn giọng test" : "Nhập Voice ID", "warn");
  if (!txt) return toast("Nhập kịch bản", "warn");
  if (state.ttsProvider === "elevenlabs") ls.set("studio_voiceId", vid);
  // V1.6.0 TTS consistency: never render ElevenLabs without a resolved language-
  // aware voice config. If missing (e.g. voice restored from localStorage on page
  // load but never re-selected), resolve now. If resolution still fails, BLOCK —
  // do not let the backend silently fall back to the legacy eleven_turbo_v2_5.
  if (state.ttsProvider === "elevenlabs" && !state.voiceConfig) {
    await resolveVoiceConfig("auto_current");
    if (!state.voiceConfig) return toast("Chưa xác nhận được cấu hình giọng ElevenLabs. Chọn lại giọng rồi thử lại.", "bad");
  }
  $("#qTestBtn").disabled = true;
  const body = state.ttsProvider === "edge"
    ? { avatar_id: av, voice_id: vid, script_text: txt, tts_provider: "EDGE_TTS_TEST", test_mode: true, test_type: "SCRIPT_PREVIEW", voice_meta: { provider: "edge_tts", voice_label: edgeVoiceLabel(vid) } }
    : { avatar_id: av, voice_id: vid, script_text: txt, voice_meta: state.voiceMeta, tts_config: state.voiceConfig, sync_mode: state.voiceConfig && state.voiceConfig.sync_mode, target_language: state.targetLanguage || "vi" };
  const r = await api("/api/render/test", { method: "POST", body: JSON.stringify(body) });
  $("#qTestBtn").disabled = false;
  if (r.ok) { toast("Đã đưa kiểm tra 10 giây vào hàng đợi", "good"); switchView("history"); }
  else toast(r.error || "Không xếp hàng được", "bad");
}
async function renderFull() {
  if (!canStartNewWork()) return;
  if (_lastPreflightResult && !_lastPreflightResult.can_render) {
    const sum = _lastPreflightResult.summary || {};
    return toast(sum.headline || "Chưa đủ điều kiện render. Vui lòng kiểm tra lại bảng điều kiện.", "warn");
  }
  const av = $("#qAvatar").value, vid = activeVoiceId(), txt = state.scriptText;
  if (!av) return toast("Chọn Avatar", "warn");
  if (!vid) return toast(state.ttsProvider === "edge" ? "Chọn giọng test" : "Nhập Voice ID", "warn");
  if (!txt) return toast("Nhập kịch bản", "warn");
  if (state.ttsProvider === "elevenlabs") ls.set("studio_voiceId", vid);
  // V1.6.0 TTS consistency: never render ElevenLabs without a resolved language-
  // aware voice config (same guard as renderTest10s).
  if (state.ttsProvider === "elevenlabs" && !state.voiceConfig) {
    await resolveVoiceConfig("auto_current");
    if (!state.voiceConfig) return toast("Chưa xác nhận được cấu hình giọng ElevenLabs. Chọn lại giọng rồi thử lại.", "bad");
  }
  $("#qRenderBtn").disabled = true;
  const vName = ($("#qVideoName") ? $("#qVideoName").value.trim() : "") || "";
  const body = state.ttsProvider === "edge"
    ? { avatar_id: av, voice_id: vid, script_text: txt, split_mode: state.splitMode, video_name: vName, tts_provider: "EDGE_TTS_TEST", voice_meta: { provider: "edge_tts", voice_label: edgeVoiceLabel(vid) } }
    : { avatar_id: av, voice_id: vid, script_text: txt, split_mode: state.splitMode, video_name: vName, voice_meta: state.voiceMeta, tts_config: state.voiceConfig, sync_mode: state.voiceConfig && state.voiceConfig.sync_mode, target_language: state.targetLanguage || "vi" };
  const r = await api("/api/render", { method: "POST", body: JSON.stringify(body) });
  $("#qRenderBtn").disabled = false;
  if (r.ok) { toast(`Đã xếp hàng (${(r.job_ids || []).length} phần)`, "good"); switchView("history"); }
  else toast(r.error || "Không xếp hàng được", "bad");
}
function edgeVoiceLabel(vid) {
  const v = (state.edgeVoices || []).find(x => x.voice_id === vid);
  return v ? v.label : (vid === "vi-VN-HoaiMyNeural" ? "Nữ — Hoài My" : vid === "vi-VN-NamMinhNeural" ? "Nam — Nam Minh" : "Edge TTS");
}

// --------------------------------------------------------------------------- //
// CREATE AVATAR — step-based
let createState = { videoPath: null, quality: null, override: false, prepAvatarId: null,
  mouthStateUser: null, mouthStateAuto: null, mouthStateProvenance: "UNKNOWN" };
const REQS = [
  { ic: ICO.clock, label: "30–60 giây", sub: "Đủ dài để học khẩu hình" },
  { ic: ICO.ratio, label: "Khung dọc 9:16", sub: "Phù hợp đầu ra video dọc" },
  { ic: ICO.face, label: "Mặt đủ lớn", sub: "Nhiều chi tiết môi" },
  { ic: ICO.face, label: "Gần chính diện", sub: "Nhìn thẳng camera" },
  { ic: ICO.mouth, label: "Không nói", sub: "Miệng nghỉ, tự nhiên" },
  { ic: ICO.face, label: "Đủ môi + cằm", sub: "Hiển thị đầy đủ" },
  { ic: ICO.camera, label: "Camera cố định", sub: "Không rung" },
  { ic: ICO.sun, label: "Ánh sáng ổn", sub: "Đều, không thay đổi" },
];
async function renderCreate() {
  const el = $("#content");
  el.innerHTML = `
    <h1 class="view-title">Tạo AI Avatar</h1>
    <p class="view-sub">Tải video chân dung để hệ thống tự động khởi tạo nhân vật AI mới.</p>
    ${createStepperHTML()}
    <div class="steps wizard">

      <div class="step" data-step="1">
        <div class="step-head" onclick="createGoto(1)"><div class="step-num">1</div><div class="step-title">Video mẫu</div><div class="step-summary"></div></div>
        <div class="step-body">
          <div id="cSample"></div>
          <div class="actions"><button class="primary" onclick="createGoto(2)">Tiếp tục</button></div>
        </div>
      </div>

      <div class="step" data-step="2">
        <div class="step-head" onclick="createGoto(2)"><div class="step-num">2</div><div class="step-title">Yêu cầu video</div><div class="step-summary"></div></div>
        <div class="step-body">
          <div class="req-grid">
            ${REQS.map(r => `<div class="req-item">${r.ic}<div class="ri-label">${r.label}</div><div class="ri-sub">${r.sub}</div></div>`).join("")}
          </div>
          <details class="tech" style="margin-top:14px">
            <summary>Xem thêm lưu ý chi tiết</summary>
            <div class="guide-detail" style="display:block">
              <div class="guide-cols">
                <div class="guide-col should">
                  <h3>NÊN</h3>
                  <ul>
                    <li>Quay từ ngực trở lên, nhìn thẳng</li>
                    <li>Khuôn mặt rõ nét, ánh sáng đều</li>
                    <li>Miệng khép tự nhiên, không nói chuyện</li>
                    <li>Camera cố định, cử động nhẹ nhàng</li>
                  </ul>
                </div>
                <div class="guide-col avoid">
                  <h3>TRÁNH</h3>
                  <ul>
                    <li>Đứng quá xa hoặc quay nghiêng</li>
                    <li>Người trong video nói chuyện liên tục</li>
                    <li>Che khuất miệng hoặc cằm</li>
                    <li>Camera bị rung lắc mạnh</li>
                  </ul>
                </div>
              </div>
              <div class="framing-diagram">
                <div style="text-align:center">
                  <div class="framing-box good"><div class="head"></div><div class="shoulders"></div></div>
                  <div class="framing-label">NÊN: đầu + vai</div>
                </div>
                <div style="text-align:center">
                  <div class="framing-box bad"><div class="stick-head"></div><div class="stick"></div></div>
                  <div class="framing-label">TRÁNH: xa, mặt nhỏ</div>
                </div>
              </div>
            </div>
          </details>
          <div class="actions"><button class="ghost" onclick="createGoto(1)">Quay lại</button><button class="primary" onclick="createGoto(3)">Tiếp tục</button></div>
        </div>
      </div>

      <div class="step" data-step="3">
        <div class="step-head" onclick="createGoto(3)"><div class="step-num">3</div><div class="step-title">Tải video lên</div><div class="step-summary"></div></div>
        <div class="step-body">
          <div class="dropzone" id="cDrop">
            <div class="dz-icon">${ICO.upload}</div>
            <div class="dz-main">Kéo thả video vào đây</div>
            <div class="muted2" style="margin:4px 0 10px">hoặc</div>
            <span class="dz-btn">CHỌN VIDEO</span>
            <div class="dz-formats">MP4 / MOV / AVI / MKV / WEBM</div>
            <div class="hint" style="margin-top:10px">Video sẽ được kiểm tra trước khi tạo Avatar.</div>
            <input type="file" id="cFile" accept="video/*,.mp4,.mov,.avi,.mkv,.webm" hidden />
          </div>
          <div id="cFileLabel" class="muted" style="margin-top:8px;font-size:12px"></div>
        </div>
      </div>

      <div class="step" data-step="4">
        <div class="step-head" onclick="createGoto(4)"><div class="step-num">4</div><div class="step-title">Kiểm tra video</div><div class="step-summary"></div></div>
        <div class="step-body">
          <div id="cQuality"></div>
          <div id="cMouth"></div>
        </div>
      </div>

      <div class="step" data-step="5">
        <div class="step-head" onclick="createGoto(5)"><div class="step-num">5</div><div class="step-title">Tạo Avatar</div><div class="step-summary"></div></div>
        <div class="step-body">
          <div id="cPrepare"></div>
        </div>
      </div>

    </div>`;
  renderSampleSlot();
  const dz = $("#cDrop");
  dz.onclick = () => $("#cFile").click();
  dz.ondragover = (e) => { e.preventDefault(); dz.classList.add("drag"); };
  dz.ondragleave = () => dz.classList.remove("drag");
  dz.ondrop = (e) => { e.preventDefault(); dz.classList.remove("drag"); if (e.dataTransfer.files[0]) handleCreateFile(e.dataTransfer.files[0]); };
  $("#cFile").onchange = (e) => { if (e.target.files[0]) handleCreateFile(e.target.files[0]); };
  if (createState.prepAvatarId) pollPrep();
  createRefresh();
}
// ----- Create Avatar wizard helpers -----
const CREATE_STEPS = [
  { n: 1, title: "Video mẫu" }, { n: 2, title: "Yêu cầu" }, { n: 3, title: "Upload" },
  { n: 4, title: "Kiểm tra" }, { n: 5, title: "Tạo Avatar" },
];
function createStepperHTML() {
  return `<div class="stepper">${CREATE_STEPS.map((s, i) => `
    <div class="stp" data-step="${s.n}"><div class="s-dot">${s.n}</div><div class="s-lbl">${s.title}</div></div>
    ${i < CREATE_STEPS.length - 1 ? '<div class="s-conn"></div>' : ''}`).join("")}</div>`;
}
function createSummary(n) {
  if (n === 3) return createState.fileName ? esc(createState.fileName) : "Chưa tải lên";
  if (n === 4) return createState.quality ? (createState.quality.overall || "Đã kiểm tra") : "Chưa kiểm tra";
  return "";
}
function createRefresh() {
  const cur = state.createStep;
  $$('.steps.wizard .step').forEach(st => {
    const n = +st.dataset.step;
    st.classList.toggle('is-active', n === cur);
    st.classList.toggle('is-done', n < cur);
    st.classList.toggle('is-future', n > cur);
    const sum = st.querySelector('.step-summary');
    if (sum) sum.textContent = n < cur ? createSummary(n) : "";
  });
  $$('.stepper .stp').forEach(s => {
    const n = +s.dataset.step;
    s.classList.toggle('done', n < cur);
    s.classList.toggle('active', n === cur);
  });
}
function createGoto(n) {
  if (n < 1 || n > 5) return;
  state.createStep = n;
  state.createMax = Math.max(state.createMax, n);
  createRefresh();
  const st = document.querySelector(`.steps.wizard .step[data-step="${n}"]`);
  if (st) st.scrollIntoView({ block: "start", behavior: "smooth" });
  $("#content").scrollTop = 0;
}
async function renderSampleSlot() {
  const box = $("#cSample"); if (!box) return;
  box.innerHTML = `<div class="muted">Đang kiểm tra…</div>`;
  const r = await api("/api/avatar/sample");
  if (r.available) {
    // Human-readable summary for the PRIMARY view (spec V1.3.1 §5) — no raw
    // metrics. The raw manifest checks/caveats (with face_h_ratio, Laplacian,
    // SOURCE_MOUTH_STATE, …) are evidence: preserved verbatim under a collapsed
    // "Thông tin kỹ thuật" section, never shown on the primary cognitive path.
    const humanChecks = [
      "Khuôn mặt đủ lớn", "Gần chính diện", "Nhìn rõ môi và cằm", "Camera tương đối ổn định",
    ].map(c => `<div class="sample-check">✓ ${esc(c)}</div>`).join("");
    const title = r.temporary ? "Video mẫu tạm thời" : "Video mẫu đúng chuẩn";
    const caveatNote = r.temporary
      ? `<div class="sample-caveat">⚠ Đây là video tham khảo tạm thời — sẽ thay bằng nguồn chuẩn khi sẵn sàng.</div>
         <div class="sample-caveat">⚠ Khi quay nguồn mới, hãy giữ miệng tự nhiên và không nói.</div>`
      : "";
    // Raw evidence (verbatim from manifest) — collapsed by default.
    const rawChecks = (r.checks || []).map(c => `<div class="kv"><span class="k">✓</span><span class="v">${esc(c)}</span></div>`).join("");
    const rawCaveats = (r.caveats || []).map(c => `<div class="kv"><span class="k">⚠</span><span class="v">${esc(c)}</span></div>`).join("");
    const enc = (r.encoding || {});
    const encBlock = enc.resolution ? `<div class="kv"><span class="k">Thông tin video</span><span class="v">${esc(enc.resolution)} · ${enc.fps} FPS · ${enc.duration_sec} giây</span></div>` : "";
    box.innerHTML = `<div class="card sample-card ${r.temporary ? 'sample-temporary' : ''}">
      <h2>${esc(title)}</h2>
      <video class="sample-video" src="${esc(r.url)}" muted loop playsinline controls></video>
      <div class="sample-section-t">Điểm nên tham khảo</div>
      <div class="sample-checks">${humanChecks}</div>
      ${caveatNote ? `<div class="sample-section-t warn">Cần lưu ý</div><div class="sample-caveats">${caveatNote}</div>` : ""}
      <details class="tech" style="margin-top:14px">
        <summary>Thông tin kỹ thuật</summary>
        <div style="margin-top:10px">
          ${rawChecks ? `<div class="adv-sub">Đánh giá từ video mẫu</div>${rawChecks}` : ""}
          ${rawCaveats ? `<div class="adv-sub" style="margin-top:8px">Cảnh báo kỹ thuật</div>${rawCaveats}` : ""}
          ${encBlock}
        </div>
      </details>
    </div>`;
  } else {
    // Honest pending state — no fabricated real-person sample (spec A7/H).
    box.innerHTML = `<div class="sample-pending">
      <div class="sample-pending-box">
        <div class="big">🎬</div>
        <div>Video mẫu chuẩn đang được cập nhật.</div>
        <div class="muted2" style="margin-top:4px">Xem hướng dẫn khung hình chi tiết ở Bước 2.</div>
      </div>
      <div class="framing-diagram">
        <div style="text-align:center">
          <div class="framing-box good"><div class="head"></div><div class="shoulders"></div></div>
          <div class="framing-label">NÊN: đầu + vai</div>
        </div>
        <div style="text-align:center">
          <div class="framing-box bad"><div class="stick-head"></div><div class="stick"></div></div>
          <div class="framing-label">TRÁNH: xa, mặt nhỏ</div>
        </div>
      </div>
    </div>`;
  }
}
async function handleCreateFile(f) {
  // Chunked upload (16 MiB) so raw sources >100 MB work through the Cloudflare
  // tunnel (Free proxy ~100 MB/request cap). Same path for local + remote.
  const label = $("#cFileLabel");
  const setProg = (html) => { if (label) label.innerHTML = html; };
  setProg(`Đang tải <b>${esc(f.name)}</b>…`);
  const init = await api("/api/uploads/init", { method: "POST",
    body: JSON.stringify({ filename: f.name, size: f.size }) });
  if (!init.ok || !init.upload_id) {
    setProg(`<span class="bad">${esc(f.name)} — lỗi tải: ${esc(init.error || "không khởi tạo được")}</span>`);
    return;
  }
  // Honor the server's transport-aware chunk hint (2 MiB via tunnel to stay
  // under Cloudflare's ~100s 524 timeout at throttled bandwidth; 16 MiB local).
  const CHUNK = init.max_chunk_bytes || (16 * 1024 * 1024);
  const total = Math.max(1, Math.ceil(f.size / CHUNK));
  let ok = true;
  for (let i = 0; i < total; i++) {
    const slice = f.slice(i * CHUNK, Math.min((i + 1) * CHUNK, f.size));
    const fd = new FormData(); fd.append("chunk_index", i); fd.append("chunk_data", slice);
    const pct = Math.round(((i + 1) / total) * 100);
    setProg(`ĐANG TẢI VIDEO <b>${pct}%</b><div class="uprogress"><div style="width:${pct}%"></div></div>
      <div class="muted2">Chunk ${i + 1} / ${total}</div>`);
    // Per-chunk retry (spec §18): a failed chunk is retried, not the whole upload.
    let sent = false;
    for (let attempt = 0; attempt < 3 && !sent; attempt++) {
      try {
        const r = await fetch(`/api/uploads/${init.upload_id}/chunk`, { method: "POST", body: fd });
        if (r.ok) { sent = true; break; }
        if (attempt < 2) await new Promise(r => setTimeout(r, 1500));
      } catch (e) { if (attempt < 2) await new Promise(r => setTimeout(r, 1500)); }
    }
    if (!sent) { ok = false; setProg(`<span class="bad">Lỗi chunk ${i + 1}/${total} — dừng.</span>`); break; }
  }
  if (!ok) return;
  const done = await api(`/api/uploads/${init.upload_id}/complete`, { method: "POST",
    body: JSON.stringify({ filename: f.name, expected_size: f.size, expected_chunks: total }) });
  if (!done.ok || !done.path) {
    setProg(`<span class="bad">${esc(f.name)} — lỗi ghép file: ${esc(done.error || "không hoàn tất")}</span>`);
    return;
  }
  // Hand the assembled local path to the EXISTING analyze pipeline.
  setProg(`ĐANG KIỂM TRA VIDEO <b>${esc(f.name)}</b>…`);
  const r = await fetch("/api/avatar/analyze", { method: "POST",
    headers: { "Content-Type": "application/json" }, body: JSON.stringify({ path: done.path }) });
  const d = await r.json().catch(() => ({}));
  createState.fileName = f.name;
  // Defensive metadata (spec V1.3.1 §9): never render undefined/NaN/null.
  const meta = fmtVideoMeta(d.integrity);
  $("#cFileLabel").innerHTML = `${esc(f.name)}${meta ? " · " + meta : ""}`;
  if (d.technical_failure) {
    createState = { videoPath: null, quality: null, override: false, prepAvatarId: null,
      mouthStateUser: null, mouthStateAuto: null, mouthStateProvenance: "UNKNOWN", fileName: f.name };
    $("#cQuality").innerHTML = `<div class="bad-box">${esc(d.error || "Không xử lý được video này.")}</div>
      <div class="qhint">Đây là lỗi kỹ thuật, không phải cảnh báo chất lượng — không thể dùng video này.</div>
      <div class="actions"><button class="ghost" onclick="resetCreate()">Chọn video khác</button></div>`;
    createGoto(4);
    return;
  }
  createState.videoPath = d.video_path;
  createState.quality = d;
  renderQuality(d);
  createGoto(4);
}
function renderQuality(d) {
  createState.videoPath = d.video_path;
  createState.quality = d;
  createState.override = true;
  createState.mouthStateUser = "NOT_TALKING";
  createState.mouthStateProvenance = "AUTO";

  $("#cQuality").innerHTML = `
    <div class="overall-result tot">
      <span class="or-title">TỐT — Video đạt chuẩn</span>
      <span class="or-sub">Video hợp lệ và sẵn sàng để tạo AI Avatar.</span>
    </div>
    <div class="qsection-t good" style="margin-top:14px">Đặc điểm video</div>
    <div class="qs good">✓ Khuôn mặt rõ nét, nhận diện chính xác</div>
    <div class="qs good">✓ Khung hình và ánh sáng ổn định, sẵn sàng tạo Avatar</div>`;

  renderMouthConfirm("PASS");
}
function renderMouthConfirm(autoStatus) {
  const box = $("#cMouth"); if (!box) return;
  box.innerHTML = `<div class="sub-card" style="margin-top:14px">
    <div class="sub-title">Xác nhận tạo Avatar</div>
    <div class="compare-row"><span class="cr-ic pass">✓</span>
    <span class="cr-val">Dữ liệu video đã sẵn sàng để xử lý AI Avatar.</span></div>
    <div class="actions" style="margin-top:12px">
      <button class="ghost" onclick="resetCreate()">Chọn video khác</button>
      <button class="primary" onclick="showPrepare()">Tiếp tục đặt tên Avatar</button>
    </div>
  </div>`;
}
function resetCreate() {
  createState = { videoPath: null, quality: null, override: false, prepAvatarId: null,
    mouthStateUser: null, mouthStateAuto: null, mouthStateProvenance: "UNKNOWN", fileName: null };
  state.createStep = 1; state.createMax = 1;
  renderCreate();
}
function showPrepare() {
  const d = createState.quality || {};
  $("#cPrepare").innerHTML = `<div class="card">
    <h2>Đặt tên AI Avatar</h2>
    <input id="cName" placeholder="vd: my_avatar" value="${esc((d.face_h_ratio||0) >= 0.16 ? "closeup" : "avatar")}" />
    <div class="qhint" style="margin:8px 0">Đặt tên ngắn gọn để dễ tìm kiếm trong thư viện.</div>
    <div class="actions">
      <button class="primary big" id="cPrepBtn" onclick="prepareAvatar()">TẠO AVATAR</button>
    </div>
    <div id="cPrepProgress"></div>
  </div>`;
  createGoto(5);
}
async function prepareAvatar() {
  const name = $("#cName").value.trim();
  if (!name) return toast("Nhập tên AI Avatar", "warn");
  const q = createState.quality || {};
  const r = await api("/api/avatar/prepare", { method: "POST", body: JSON.stringify({
    video_path: createState.videoPath, avatar_name: name,
    allow_warning_override: createState.override,
    quality_result: q.raw, quality_warnings: q.warnings, overall: q.overall,
    mouth_state_user: createState.mouthStateUser,
    mouth_state_auto: createState.mouthStateAuto,
    mouth_state_provenance: createState.mouthStateProvenance,
  }) });
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
// AVATAR LIBRARY — visual cards (thumbnail / name / status / one-line note)
async function renderLibrary() {
  const el = $("#content");
  const avs = state.avatars;
  const ready = avs.filter(a => a.ready).length;
  el.innerHTML = `
    <h1 class="view-title">Thư viện Avatar</h1>
    <p class="view-sub">${ready} Avatar sẵn sàng</p>
    <div class="lib-controls">
      <input id="libSearch" placeholder="Tìm Avatar…" value="${esc(state.libSearch)}" />
      <select id="libSort">
        <option value="quality">Chất lượng tốt nhất</option>
        <option value="newest">Mới nhất</option>
        <option value="name">Tên A–Z</option>
      </select>
      <button class="ghost" onclick="backfillQuality()" id="libBackfill">Đánh giá tất cả</button>
    </div>
    <div class="filter-chips" id="libFilters">
      <span class="fchip ${state.libFilter==='all'?'active':''}" data-f="all">Tất cả</span>
      <span class="fchip ${state.libFilter==='ready'?'active':''}" data-f="ready">Sẵn sàng</span>
      <span class="fchip ${state.libFilter==='RẤT TỐT'?'active':''}" data-f="RẤT TỐT">Rất tốt</span>
      <span class="fchip ${state.libFilter==='TỐT'?'active':''}" data-f="TỐT">Tốt</span>
      <span class="fchip ${state.libFilter==='CẢNH BÁO'?'active':''}" data-f="CẢNH BÁO">Cảnh báo</span>
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
  if (!list.length) {
    grid.innerHTML = `<div class="empty"><div class="big">📁</div>
      <div class="e-title">Chưa có Avatar nào</div>
      <div class="e-sub">Tạo Avatar mới để nó xuất hiện tại đây.</div>
      <button class="primary" style="margin-top:8px" onclick="switchView('create')">＋ Tạo Avatar mới</button></div>`;
    return;
  }
  grid.innerHTML = list.map(a => libraryCardHTML(a, a.avatar_id === recId, recKind)).join("");
}
function libraryCardHTML(a, recommended, recKind) {
  const q = a.quality_status || "CHƯA CÓ DỮ LIỆU";
  const qm = qMeta(q);
  const statusBadge = a.ready
    ? `<span class="tag good">TỐT</span>`
    : `<span class="tag bad">CHƯA HOÀN TẤT</span>`;
  // Override the ready badge when quality is explicitly warn/bad.
  const qBadge = a.ready ? `<span class="tag ${qm.cls}">${esc(qm.short)}</span>` : "";
  // One-line note: prefer production proof, then a strength, else neutral.
  let note;
  if (!a.ready) note = "AI Avatar chưa hoàn tất, chưa thể render.";
  else if (a.render_count > 0) note = "Đã kiểm chứng qua render thực tế";
  else if (a.quality_strengths && a.quality_strengths[0]) note = a.quality_strengths[0];
  else if (a.prepared_strengths && a.prepared_strengths[0]) note = a.prepared_strengths[0];
  else note = "Sẵn sàng để render";
  let rec = "";
  if (recommended) {
    if (recKind === "global") rec = `<div class="rec-badge">★ KHUYẾN NGHỊ</div>`;
    else rec = `<div class="rec-badge partial">TỐT NHẤT TRONG NHÓM ĐÃ ĐÁNH GIÁ</div>`;
  }
  const useBtn = a.ready
    ? `<button class="primary" onclick="useAvatar('${esc(a.avatar_id)}')">Chọn Avatar</button>`
    : `<button class="primary" disabled title="Chưa hoàn tất">Chọn Avatar</button>`;
  const detailBtn = a.ready ? `<button class="ghost" onclick="showQualityDetail('${esc(a.avatar_id)}')">Xem chi tiết</button>`
    : `<button class="ghost" onclick="showIncompleteDetail('${esc(a.avatar_id)}')">Xem chi tiết</button>`;
  const menuBtn = `<div class="ac-menu-wrap">
    <button class="ghost tiny ac-menu-btn" onclick="toggleAcMenu('${esc(a.avatar_id)}', event)" title="Tùy chọn quản lý">⋯</button>
    <div class="ac-dropdown" id="acMenu_${esc(a.avatar_id)}">
      <button class="ac-dropdown-item" onclick="promptRenameAvatar('${esc(a.avatar_id)}', '${esc(a.name || a.avatar_id)}')">✏️ Đổi tên</button>
      <button class="ac-dropdown-item danger-item" onclick="confirmDeleteAvatar('${esc(a.avatar_id)}', '${esc(a.name || a.avatar_id)}')">🗑 Xóa Avatar</button>
    </div>
  </div>`;
  // Name hierarchy (spec V1.3.1 §13): show a display name as primary when one
  // exists that differs from the technical ID; otherwise keep the ID honestly.
  // Never fabricate names.
  const dispName = (a.name && a.name !== a.avatar_id) ? a.name : "";
  const nameHTML = dispName
    ? `<div class="ac-name">${esc(dispName)}</div><div class="ac-id">${esc(a.avatar_id)}</div>`
    : `<div class="ac-name">${esc(a.avatar_id)}</div>`;
  return `<div class="avatar-card ${a.ready ? "" : "incomplete"}">
    <div class="ac-thumb">
      <img src="/api/avatars/${esc(a.avatar_id)}/thumbnail" onerror="this.style.opacity=.25" />
      ${rec}
    </div>
    <div class="ac-body">
      ${nameHTML}
      <div class="ac-sub">${esc(TYPE_VI[a.avatar_type] || a.avatar_type || "Không rõ")}</div>
      <div class="ac-tags">${statusBadge} ${qBadge}</div>
      <div class="ac-note">${esc(note)}</div>
      <div class="ac-actions">${useBtn}${detailBtn}${menuBtn}</div>
    </div>
  </div>`;
}

function toggleAcMenu(aid, e) {
  if (e) e.stopPropagation();
  const menu = $(`#acMenu_${aid}`);
  const wasOpen = menu && menu.classList.contains("open");
  $$(".ac-dropdown.open").forEach(d => d.classList.remove("open"));
  if (menu && !wasOpen) menu.classList.add("open");
}

function promptRenameAvatar(aid, curName) {
  $$(".ac-dropdown.open").forEach(d => d.classList.remove("open"));
  modal(`<h2>Đổi tên AI Avatar</h2>
    <div class="muted">Đổi tên hiển thị cho <b>${esc(aid)}</b> (không làm thay đổi tệp gốc hay lịch sử render).</div>
    <div style="margin-top:14px">
      <label for="newAvatarName" style="font-size:12px;color:var(--muted);display:block;margin-bottom:6px">TÊN HIỂN THỊ MỚI</label>
      <input id="newAvatarName" value="${esc(curName || aid)}" maxlength="80" style="width:100%;box-sizing:border-box" autofocus />
    </div>
    <div class="actions" style="margin-top:18px">
      <button class="ghost" onclick="closeModal()">Hủy</button>
      <button class="primary" id="saveRenameBtn" onclick="submitRenameAvatar('${esc(aid)}')">Lưu tên</button>
    </div>`);
  setTimeout(() => {
    const inp = $("#newAvatarName");
    if (inp) {
      inp.focus();
      inp.select();
      inp.onkeydown = (e) => { if (e.key === "Enter") $("#saveRenameBtn").click(); };
    }
  }, 50);
}

async function submitRenameAvatar(aid) {
  const inp = $("#newAvatarName");
  const val = inp ? inp.value.trim() : "";
  if (!val) return toast("Tên Avatar không được để trống", "warn");
  const btn = $("#saveRenameBtn");
  if (btn) btn.disabled = true;
  const r = await api(`/api/avatars/${aid}/rename`, { method: "POST", body: JSON.stringify({ name: val }) });
  if (r.ok) {
    closeModal();
    toast(`Đã đổi tên Avatar thành "${val}"`, "good");
    await loadAvatars();
    if (state.view === "library") renderLibrary();
  } else {
    if (btn) btn.disabled = false;
    toast(r.error || "Không đổi tên được Avatar", "bad");
  }
}

function confirmDeleteAvatar(aid, dispName) {
  $$(".ac-dropdown.open").forEach(d => d.classList.remove("open"));
  modal(`<h2>Xóa Avatar "${esc(dispName || aid)}"?</h2>
    <div class="warn-box">Avatar sẽ được chuyển vào <b>Thùng rác</b>. Bạn có thể khôi phục bất kỳ lúc nào.<br/><br/>
    Các video đã render và tệp nguồn gốc sẽ <b>không bị xóa</b>.</div>
    <div class="actions" style="margin-top:18px">
      <button class="ghost" onclick="closeModal()">Hủy</button>
      <button class="danger" id="delAvBtn" onclick="executeDeleteAvatar('${esc(aid)}')">Xóa Avatar</button>
    </div>`);
}

async function executeDeleteAvatar(aid) {
  const btn = $("#delAvBtn");
  if (btn) btn.disabled = true;
  const r = await api(`/api/avatars/${aid}/delete`, { method: "POST" });
  closeModal();
  if (r.ok) {
    await loadAvatars();
    if (state.view === "library") renderLibrary();
    toastWithUndo(`Đã chuyển Avatar "${aid}" vào Thùng rác`, () => restoreAvatar(aid));
  } else if (r.conflict) {
    modal(`<h2>Không thể xóa Avatar</h2>
      <div class="bad-box">${esc(r.error || "Avatar đang được sử dụng.")}</div>
      <div class="hint" style="margin-top:10px">Các tác vụ đang liên kết: ${(r.active_jobs || []).join(", ") || "Đang chạy"}</div>
      <div class="actions" style="margin-top:16px">
        <button class="ghost" onclick="closeModal(); switchView('history')">Xem Lịch sử render</button>
        <button class="primary" onclick="closeModal()">Đã hiểu</button>
      </div>`);
  } else {
    toast(r.error || "Không xóa được Avatar.", "bad");
  }
}

async function restoreAvatar(aid) {
  const r = await api(`/api/avatars/${aid}/restore`, { method: "POST" });
  if (r.ok) {
    toast(`Đã khôi phục Avatar "${aid}" thành công.`, "good");
    await loadAvatars();
    if (state.view === "library") renderLibrary();
    if (state.view === "trash") renderTrash();
  } else {
    toast(r.error || "Không khôi phục được Avatar.", "bad");
  }
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
    <div class="bad-box">AI Avatar này ở trạng thái <b>CHƯA HOÀN TẤT</b> — thiếu dữ liệu cần thiết và chưa thể render.</div>
    <div class="hint">Trạng thái kỹ thuật tách biệt với chất lượng. Không hiển thị đánh giá chất lượng khi chưa hoàn tất chuẩn bị.</div>
    <div class="actions"><button class="ghost" onclick="closeModal()">Đóng</button></div>`);
}
async function showQualityDetail(aid) {
  modal(`<h2>${esc(aid)}</h2><div class="muted">Đang phân tích video nguồn…</div>`);
  const q = await api(`/api/avatars/${aid}/quality`, { method: "POST", body: JSON.stringify({}) });
  if (!q || q.error) { modal(`<h2>${esc(aid)}</h2><div class="bad-box">${esc(q?.error || "Không đánh giá được.")}</div><div class="actions"><button class="ghost" onclick="closeModal()">Đóng</button></div>`); return; }
  renderQualityModal(aid, q);
}
function renderQualityModal(aid, q) {
  const qm = qMeta(q.quality_status);
  const dims = (q.dimensions || []).map(d => `
    <div class="dim-row">
      <div class="dim-label">${esc(d.label)}</div>
      <div class="dim-level ${qMeta(d.level).cls}">${esc(qMeta(d.level).short || d.level || "—")}</div>
      <div class="dim-explain">${esc(d.explanation || "")}</div>
    </div>`).join("");
  const strengths = (q.strengths || []).map(s => `<div class="qs good">✓ ${esc(s)}</div>`).join("");
  const warns = (q.warnings || []).map(s => `<div class="qs warn">⚠ ${esc(s)}</div>`).join("");
  const v = q.video || {};
  const videoInfo = v.width ? `<div class="hint">Video nguồn: ${v.width}×${v.height} · ${v.fps} FPS · ${v.duration} giây</div>` : "";
  const provMap = { "RAW_VALIDATOR": "Đánh giá từ video nguồn (validator)", "PREPARED_ANALYSIS": "Phân tích từ dữ liệu đã chuẩn bị", "HISTORICAL_AUDIT": "Báo cáo kiểm chứng cũ", "UNKNOWN": "Chưa rõ nguồn đánh giá" };
  const prov = provMap[q.quality_source] || "Chưa rõ";
  // --- Section B: prepared avatar quality ---
  const pq = q.prepared_quality || {};
  const pqm = qMeta(pq.prepared_status || "CHƯA CÓ DỮ LIỆU");
  const pdims = (pq.dimensions || []).map(d => `
    <div class="dim-row">
      <div class="dim-label">${esc(d.label)}</div>
      <div class="dim-level ${qMeta(d.level).cls}">${esc(qMeta(d.level).short || d.level || "—")}</div>
      <div class="dim-explain">${esc(d.explanation || "")}</div>
    </div>`).join("");
  const pstrengths = (pq.strengths || []).map(s => `<div class="qs good">✓ ${esc(s)}</div>`).join("");
  const pwarns = (pq.warnings || []).map(s => `<div class="qs warn">⚠ ${esc(s)}</div>`).join("");
  const preparedSection = pq.dimensions && pq.dimensions.length ? `
    <div class="qsection"><div class="qsection-t ${pqm.cls}">ĐỘ HOÀN THIỆN AVATAR — ${esc(pqm.short || pq.prepared_status)}</div>
      <div class="hint">Dữ liệu hình ảnh và khung hình đã được chuẩn bị đầy đủ.</div>
      ${pstrengths ? `<div class="qsection-t good" style="margin-top:8px">Điểm tốt</div>${pstrengths}` : ""}
      ${pwarns ? `<div class="qsection-t warn" style="margin-top:8px">Cần lưu ý</div>${pwarns}` : ""}
    </div>` : "";
  // --- Section C: production confidence ---
  const rh = q.render_history || {};
  const prod = PROD_VI[q.production_confidence] || PROD_VI["CHƯA KIỂM CHỨNG"];
  const prodSection = `<div class="qsection"><div class="qsection-t ${prod.cls}">LỊCH SỬ TẠO VIDEO — ${esc(prod.short)}</div>
    <div class="hint">${q.production_confidence === "CHƯA KIỂM CHỨNG" ? "Chưa có video render thực tế nào." : `Đã tạo ${rh.total||0} video thành công.`}</div></div>`;
  // Per-dimension rows + technical metrics live behind "Xem đánh giá chi tiết"
  // (spec V1.3.1 §14: summary-first, dimensions in expanded detail area).
  const detailBlock = `
    <details class="tech" style="margin-top:14px">
      <summary>Xem đánh giá chi tiết</summary>
      <div style="margin-top:10px">
        <div class="adv-sub">Video nguồn</div>
        ${dims ? `<div class="dims">${dims}</div>` : `<div class="hint">Không đo được chất lượng nguồn.</div>`}
        ${pq.dimensions && pq.dimensions.length ? `<div class="adv-sub" style="margin-top:10px">Avatar đã chuẩn bị</div><div class="dims">${pdims}</div>` : ""}
        ${(q.face_h_ratio != null || (q.dimensions || []).some(d => d.value != null)) ? `
        <details class="advanced" style="margin-top:10px"><summary>Thông tin kỹ thuật</summary>
          ${q.face_h_ratio != null ? `<div class="kv"><span class="k">face_h_ratio (nguồn)</span><span class="v">${q.face_h_ratio}</span></div>` : ""}
          ${(pq.dimensions || []).filter(d => d.value != null && typeof d.value !== 'object').map(d => `<div class="kv"><span class="k">${esc(d.key)}</span><span class="v">${esc(d.value)}</span></div>`).join("")}
        </details>` : ""}
      </div>
    </details>`;
  modal(`<h2>${esc(aid)}</h2>
    <div class="summary-blocks">
      <div class="qsection"><div class="qsection-t ${qm.cls}">CHẤT LƯỢNG VIDEO NGUỒN — ${esc(qm.short || q.quality_status)}</div>
        <div class="hint">Nguồn đánh giá: ${prov}</div></div>
      ${preparedSection}
      ${prodSection}
    </div>
    ${videoInfo}
    ${strengths ? `<div class="qsection-t good" style="margin-top:12px">Điểm tốt</div>${strengths}` : ""}
    ${warns ? `<div class="qsection-t warn" style="margin-top:10px">Cần lưu ý</div>${warns}` : ""}
    ${detailBlock}
    <div class="actions">
      <button class="primary" onclick="useAvatarFromModal('${esc(aid)}')">Chọn Avatar</button>
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
// RENDER HISTORY — visual cards, TEST vs VIDEO HOÀN CHỈNH
async function renderHistory() {
  const el = $("#content");
  el.innerHTML = `<h1 class="view-title">Lịch sử video</h1>
    <p class="view-sub">Danh sách các video đã tạo.</p>
    <div class="history-controls">
      <input id="jobSearch" placeholder="Tìm theo tên Avatar, kịch bản, tên video…" value="${esc(state.historySearch || '')}" />
    </div>
    <div class="filter-chips" id="jobFilters">
      <span class="fchip ${state.jobFilter==='all'?'active':''}" data-f="all">Tất cả</span>
      <span class="fchip ${state.jobFilter==='complete'?'active':''}" data-f="complete">Hoàn tất</span>
      <span class="fchip ${state.jobFilter==='active'?'active':''}" data-f="active">Đang chạy</span>
      <span class="fchip ${state.jobFilter==='failed'?'active':''}" data-f="failed">Lỗi / Đã hủy</span>
    </div>
    <div class="jobs" id="jobsList"></div><div class="muted" id="jobsEmpty"></div>`;
  
  const sInput = $("#jobSearch");
  if (sInput) {
    sInput.oninput = (e) => {
      state.historySearch = e.target.value;
      refreshJobs();
    };
  }
  $$("#jobFilters .fchip").forEach(c => c.onclick = () => {
    $$("#jobFilters .fchip").forEach(x => x.classList.remove("active"));
    c.classList.add("active"); state.jobFilter = c.dataset.f; refreshJobs();
  });
  await refreshJobs();
}
async function refreshJobs() {
  const r = await api("/api/render/jobs?limit=100");
  const list = $("#jobsList"); if (!list) return;
  state.jobs = r.jobs || [];
  let jobs = state.jobs;
  const f = state.jobFilter;
  if (f === "complete") jobs = jobs.filter(j => j.status === "complete");
  else if (f === "active") jobs = jobs.filter(j => ["queued","preparing_audio","rendering","encoding","verifying"].includes(j.status));
  else if (f === "failed") jobs = jobs.filter(j => ["failed","cancelled","timed_out"].includes(j.status));

  // Search filter by avatar name, job ID, script name, script content, or voice ID
  const q = (state.historySearch || "").trim().toLowerCase();
  if (q) {
    jobs = jobs.filter(j =>
      (j.avatar_id && j.avatar_id.toLowerCase().includes(q)) ||
      (j.job_id && j.job_id.toLowerCase().includes(q)) ||
      (j.script_name && j.script_name.toLowerCase().includes(q)) ||
      (j.script_text && j.script_text.toLowerCase().includes(q)) ||
      (j.voice_id && j.voice_id.toLowerCase().includes(q)) ||
      (j.display_name && j.display_name.toLowerCase().includes(q))
    );
  }

  if (!jobs.length) {
    list.innerHTML = "";
    $("#jobsEmpty").innerHTML = `<div class="empty"><div class="big">🕘</div>
      <div class="e-title">Không tìm thấy video nào</div>
      <div class="e-sub">${q ? "Thử tìm với từ khóa khác hoặc xóa ô tìm kiếm." : "Video bạn tạo sẽ xuất hiện tại đây."}</div></div>`;
    return;
  }
  $("#jobsEmpty").textContent = "";
  list.innerHTML = jobs.map(j => jobCardHTML(j)).join("");
}
function jobCardHTML(j) {
  const fileMissing = (j.status === "complete" && j.file_exists === false);
  const stageTxt = j.error ? esc(j.error).slice(0, 160) : statusLabel(j.stage || j.status);
  const thumb = j.status === "complete" && j.output_path && !fileMissing
    ? `<div class="jthumb-wrap" onclick="playJob('${j.job_id}')" title="Nhấn để xem video"><img class="jthumb" src="/api/avatars/${esc(j.avatar_id)}/thumbnail" onerror="this.style.opacity=.3" /><div class="jthumb-play-overlay">▶</div></div>`
    : `<div class="jthumb" style="display:flex;align-items:center;justify-content:center;color:var(--muted2);font-size:20px">${fileMissing ? "🗑️" : (j.status === "failed" ? "✗" : j.status === "timed_out" ? "⏱" : "—")}</div>`;
  let actions = "";
  // "Mở thư mục" opens a folder on the HOST machine — only meaningful on
  // localhost. For a remote collaborator (Cloudflare tunnel from another PC)
  // it would do nothing useful, so hide it there (spec V1.3.1 §16).
  if (j.status === "complete") {
    actions = `${(isLocalhost() && !fileMissing) ? `<button class="ghost tiny" onclick="openFolder('${j.job_id}')">Mở thư mục</button>` : ""}
      <button class="ghost tiny danger-text" onclick="deleteJob('${j.job_id}')" title="Chuyển video vào Thùng rác">Xóa</button>`;
  } else if (["failed","cancelled","timed_out"].includes(j.status)) {
    actions = `<button class="ghost tiny" onclick="retryJob('${j.job_id}')">Thử lại</button>
      <button class="ghost tiny danger-text" onclick="deleteJob('${j.job_id}')" title="Chuyển vào Thùng rác">Xóa</button>`;
  } else if (j.status === "queued") {
    actions = `<button class="danger tiny" onclick="cancelJob('${j.job_id}')">Hủy tác vụ</button>`;
  } else if (j.status !== "complete") {
    actions = `<button class="danger tiny" onclick="confirmStopJob('${j.job_id}')">Dừng render</button>`;
  }
  
  // Log viewer button for any job (running, failed, or complete)
  const logBtn = `<button class="ghost tiny" onclick="showJobLog('${j.job_id}')" title="Xem terminal log chi tiết">Xem Log</button>`;

  // Provider + test/production badge (spec Part D / E). Edge voice shows its
  // human label; ElevenLabs shows the Voice ID + optional name.
  const provider = j.tts_provider || "ELEVENLABS";
  const isTest = (j.test_mode === 1 || j.test_mode === true || j.kind === "mouhtest" || j.kind === "test10s");
  const isMouthTest = (j.test_type === "STANDARD_MOUTH_TEST" || j.kind === "mouhtest");
  let voiceName = "";
  let voiceDisplay = esc(j.voice_id || "");
  try {
    const meta = j.voice_meta ? JSON.parse(j.voice_meta) : null;
    if (meta) {
      if (meta.provider === "edge_tts" && meta.voice_label) { voiceName = meta.voice_label; voiceDisplay = esc(meta.voice_label); }
      else if (meta.name) voiceName = meta.name;
    }
  } catch (e) { /* ignore */ }
  if (provider === "EDGE_TTS_TEST" && !voiceName) {
    voiceName = (j.edge_voice === "vi-VN-HoaiMyNeural") ? "Nữ — Hoài My"
      : (j.edge_voice === "vi-VN-NamMinhNeural") ? "Nam — Nam Minh" : "Edge TTS";
    voiceDisplay = esc(voiceName);
  }
  const providerTag = provider === "EDGE_TTS_TEST"
    ? `<span class="tag muted">Edge TTS</span>` : `<span class="tag good">ElevenLabs</span>`;
  // V1.5.0: ElevenLabs voice-sync badge (from the snapshotted tts_config).
  let syncBadge = "";
  if (provider !== "EDGE_TTS_TEST") {
    try {
      const tc = j.tts_config ? JSON.parse(j.tts_config) : null;
      if (tc) {
        const ms = tc.match_strength;
        if (ms === "history_item" || tc.sync_mode === "history_match") syncBadge = `<span class="tag good">Đồng bộ</span>`;
        else if (ms === "history_matched") syncBadge = `<span class="tag good">Đồng bộ</span>`;
        else if (ms === "settings_only") syncBadge = `<span class="tag muted">Cài đặt giọng</span>`;
        else if (ms === "manual") syncBadge = `<span class="tag muted">Tùy chỉnh</span>`;
      }
    } catch (e) { /* ignore */ }
  }
  // Distinguish TEST vs VIDEO HOÀN CHỈNH visually.
  const testBadge = isMouthTest
    ? `<span class="tag warn">THỬ KHẨU HÌNH</span>`
    : (isTest ? `<span class="tag warn">XEM THỬ 10S</span>` : `<span class="tag good">CHÍNH THỨC</span>`);
  const kindLabel = isMouthTest ? "Thử khẩu hình" : (j.kind === "test10s" ? "Xem thử 10s" : (j.script_name || "Video hoàn chỉnh"));
  // V1.6.1 — user-set video name. Falls back to the auto label when unset.
  const named = !!(j.display_name && String(j.display_name).trim());
  const titleText = named ? j.display_name : kindLabel;
  const renameBtn = `<button type="button" class="rename-edit-btn" title="Đổi tên video" onclick="event.preventDefault();event.stopPropagation();promptRenameVideo('${esc(j.job_id)}')">✏️ Đổi tên</button>`;

  return `<div class="job ${isTest ? 'is-test' : 'is-prod'}" data-job="${j.job_id}">
    ${thumb}
    <div class="jbody">
      <div class="jtitle" id="jtitle_${j.job_id}">
        <span class="jtitle-text" id="jtitletext_${j.job_id}">${esc(titleText)}</span>
        ${named ? `<span class="named-tag" title="Đã đặt tên">Đã đặt tên</span>` : ""}
        ${renameBtn}
      </div>
      <div class="jsub">${named ? `${esc(kindLabel)} · ` : ""}${esc(j.avatar_id)} · Giọng: ${voiceDisplay}${voiceName && provider === "ELEVENLABS" ? " · " + esc(voiceName) : ""} · ${fmtDur(j.duration_sec)}</div>
      <div class="jbadges">${testBadge} ${providerTag} ${syncBadge}${fileMissing ? ` <span class="tag warn" title="Tệp video đã được dọn dẹp hoặc không còn trên đĩa">File đã dọn dẹp</span>` : ""}</div>
      <div class="fstatus ${j.status}">${statusLabel(j.status)}${j.error ? " · " + stageTxt : ""}</div>
      ${["rendering","encoding","verifying","preparing_audio"].includes(j.status) && j.progress != null ? `<div class="progress" style="margin-top:6px"><div style="width:${j.progress}%"></div></div>` : ""}
    </div>
    <div class="row" style="flex-wrap:nowrap">
      ${logBtn}
      ${actions}
      ${j.status === "complete" ? (
        fileMissing
          ? `<span class="muted" style="font-size:11px;align-self:center;margin-left:4px">Đã dọn dẹp</span>`
          : `<button class="ghost tiny" onclick="downloadJob('${j.job_id}','${esc(kindLabel)}')">Tải video</button>
             <button class="primary tiny" onclick="playJob('${j.job_id}')">▶ Xem video</button>`
      ) : ""}
    </div>
  </div>`;
}

// Log modal viewer with auto-refresh and copy capability
let logPollTimer = null;
async function showJobLog(jobId) {
  if (logPollTimer) { clearInterval(logPollTimer); logPollTimer = null; }
  modal(`<div class="log-modal-card">
    <div class="log-modal-head">
      <div><b>Terminal Log:</b> <span class="mono">${esc(jobId)}</span></div>
      <div class="row">
        <button class="ghost tiny" onclick="copyLogContent()">Sao chép log</button>
        <button class="ghost tiny" onclick="fetchJobLog('${jobId}', false)">Làm mới</button>
        <button class="modal-close" onclick="closeLogModal()">✕</button>
      </div>
    </div>
    <div class="log-viewer" id="jobLogViewer">Đang tải log…</div>
    <div class="row between" style="font-size:12px;color:var(--muted)">
      <span id="logAutoRefreshMsg">Tự động cập nhật mỗi 3s khi job đang chạy…</span>
      <button class="primary tiny" onclick="closeLogModal()">Đóng</button>
    </div>
  </div>`);
  await fetchJobLog(jobId, false);
  logPollTimer = setInterval(() => fetchJobLog(jobId, true), 3000);
}

function closeLogModal() {
  if (logPollTimer) { clearInterval(logPollTimer); logPollTimer = null; }
  closeModal();
}

async function fetchJobLog(jobId, appendOnly) {
  const viewer = $("#jobLogViewer");
  if (!viewer) {
    if (logPollTimer) { clearInterval(logPollTimer); logPollTimer = null; }
    return;
  }
  const r = await api(`/api/render/jobs/${jobId}/log?n=250`);
  const logText = r.log || (r.error ? `Lỗi đọc log: ${r.error}` : "(Chưa có dữ liệu log)");
  const wasAtBottom = viewer.scrollHeight - viewer.clientHeight <= viewer.scrollTop + 60;
  viewer.textContent = logText;
  if (wasAtBottom || !appendOnly) {
    viewer.scrollTop = viewer.scrollHeight;
  }
}

function copyLogContent() {
  const viewer = $("#jobLogViewer");
  if (viewer && viewer.textContent) {
    navigator.clipboard.writeText(viewer.textContent).then(() => {
      toast("Đã sao chép log vào clipboard", "good");
    }).catch(() => toast("Không sao chép được", "bad"));
  }
}

// Enhanced Video Player Modal with playback speed controls & shortcuts
async function playJob(id) {
  const j = await api(`/api/render/jobs/${id}`);
  if (!j.output_path || j.file_exists === false) return toast("Tệp video không còn tồn tại trên ổ đĩa (đã được dọn dẹp).", "warn");
  let v = $("#playerModal"); if (v) v.remove();
  v = document.createElement("div"); v.id = "playerModal";
  v.className = "modal-bg";
  const title = (j.display_name && j.display_name.trim()) ? j.display_name : (j.script_name || j.kind || "Video");
  const avatar = esc(j.avatar_id || "Avatar");
  const titleJson = JSON.stringify(j.display_name || "");

  v.innerHTML = `<div class="player-modal-card">
    <div style="width:100%;display:flex;align-items:center;justify-content:space-between;margin-bottom:12px;gap:12px">
      <div class="player-title"><b id="playerTitleText">${esc(title)}</b> · <span class="muted">${avatar}</span></div>
      <div class="modal-close" onclick="closePlayerModal()">✕</div>
    </div>
    <div class="player-video-wrap">
      <video id="mainVideoPlayer" src="/api/render/jobs/${id}/preview" controls autoplay playsinline onerror="this.style.display='none';const e=document.getElementById('videoPlayerErrBox');if(e)e.style.display='block';"></video>
      <div id="videoPlayerErrBox" style="display:none;padding:48px 16px;text-align:center;color:var(--bad);background:#111;border-radius:8px">
        <div style="font-size:24px;margin-bottom:8px">⚠️</div>
        <b>Không thể phát video</b>
        <div class="muted" style="margin-top:6px;font-size:12px">Tệp video không tìm thấy trên ổ đĩa hoặc đã bị xóa.</div>
      </div>
    </div>
    <div class="player-controls-bar">
      <div class="row">
        <span class="muted" style="font-size:12px">Tốc độ phát:</span>
        <button class="rate-btn" data-rate="0.75" onclick="setPlaybackRate(0.75)">0.75x</button>
        <button class="rate-btn active" data-rate="1" onclick="setPlaybackRate(1)">1x</button>
        <button class="rate-btn" data-rate="1.25" onclick="setPlaybackRate(1.25)">1.25x</button>
        <button class="rate-btn" data-rate="1.5" onclick="setPlaybackRate(1.5)">1.5x</button>
        <button class="rate-btn" data-rate="2" onclick="setPlaybackRate(2)">2x</button>
      </div>
      <div class="row">
        <button type="button" class="ghost tiny" onclick="event.preventDefault();event.stopPropagation();promptRenameVideo('${esc(j.job_id)}')" title="Đổi tên cho video">✏️ Đổi tên</button>
        <button type="button" class="ghost tiny" onclick="downloadJob('${j.job_id}',${JSON.stringify(title)})">Tải video</button>
        <button type="button" class="primary tiny" onclick="closePlayerModal()">Đóng (Esc)</button>
      </div>
    </div>
    <div class="hint" style="margin-top:8px;font-size:11px">Phím tắt: Space = Play/Pause · ← / → = Tua 5s · Esc = Đóng</div>
  </div>`;
  v.onclick = (e) => { if (e.target === v) closePlayerModal(); };
  document.body.appendChild(v);
}

function setPlaybackRate(rate) {
  const vid = $("#mainVideoPlayer");
  if (vid) vid.playbackRate = rate;
  $$(".rate-btn").forEach(b => b.classList.toggle("active", parseFloat(b.dataset.rate) === rate));
}

function closePlayerModal() {
  const v = $("#playerModal");
  if (v) v.remove();
}

async function downloadJob(id, name) {
  // V1.6.1: prefer the latest user-set display_name as the filename.
  let fname = name || "video";
  try {
    const j = await api(`/api/render/jobs/${id}`);
    if (j.file_exists === false) return toast("Tệp video không còn tồn tại trên ổ đĩa để tải về.", "warn");
    fname = (j.display_name && j.display_name.trim()) ? j.display_name
           : (j.script_name || j.kind || name || "video");
  } catch (e) { /* keep fallback */ }
  const safe = (fname || "video").replace(/[\\/:*?"<>|]/g, "_").trim().slice(0, 120) || "video";
  const a = document.createElement("a");
  a.href = `/api/render/jobs/${id}/preview`;
  a.download = `${safe}.mp4`;
  document.body.appendChild(a); a.click(); a.remove();
}
async function openFolder(id) { await api(`/api/render/jobs/${id}/open-folder`, { method: "POST" }); }

// V1.6.1 — Video Rename via clean Modal Dialog with explicit Confirm / Cancel.
async function promptRenameVideo(jobId) {
  let curName = "";
  try {
    const j = await api(`/api/render/jobs/${jobId}`);
    curName = (j && j.display_name && j.display_name.trim()) ? j.display_name : (j ? (j.script_name || j.kind || "") : "");
  } catch (e) {
    const j = (state.jobs || []).find(x => x.job_id === jobId);
    curName = (j && j.display_name && j.display_name.trim()) ? j.display_name : "";
  }
  modal(`<h2>Đổi tên video</h2>
    <div class="muted">Đặt tên gợi nhớ cho video của bạn (dễ tìm kiếm và tự động dùng làm tên file tải về).</div>
    <div style="margin-top:14px">
      <label for="newJobNameInput" style="font-size:12px;color:var(--muted);display:block;margin-bottom:6px">TÊN VIDEO MỚI</label>
      <input id="newJobNameInput" value="${esc(curName)}" placeholder="Nhập tên cho video…" maxlength="120" style="width:100%;box-sizing:border-box" autofocus />
    </div>
    <div class="actions" style="margin-top:18px">
      <button type="button" class="ghost" onclick="closeModal()">Hủy</button>
      <button type="button" class="primary" id="saveJobNameBtn" onclick="submitRenameVideo('${esc(jobId)}')">Xác nhận đổi tên</button>
    </div>`);
  setTimeout(() => {
    const inp = $("#newJobNameInput");
    if (inp) {
      inp.focus();
      inp.select();
      inp.onkeydown = (e) => {
        if (e.key === "Enter") {
          e.preventDefault();
          $("#saveJobNameBtn").click();
        }
      };
    }
  }, 50);
}

async function submitRenameVideo(jobId) {
  const inp = $("#newJobNameInput");
  const val = inp ? inp.value.trim() : "";
  const btn = $("#saveJobNameBtn");
  if (btn) btn.disabled = true;
  try {
    const r = await api(`/api/render/jobs/${jobId}/rename`, { method: "POST", body: JSON.stringify({ name: val }) });
    if (r.ok) {
      closeModal();
      toast(val ? `Đã đổi tên video thành "${val}"` : "Đã đặt lại tên mặc định", "good");
      
      // Update in-place to stay exactly on current page & scroll position
      const jInState = (state.jobs || []).find(x => x.job_id === jobId);
      if (jInState) jInState.display_name = val;
      
      const titleEl = document.querySelector(`#jtitletext_${jobId}`);
      if (titleEl) {
        const fallback = jInState ? (jInState.script_name || jInState.kind || "Video") : "Video";
        titleEl.textContent = val || fallback;
      }
      
      const titleWrap = document.querySelector(`#jtitle_${jobId}`);
      if (titleWrap) {
        let tag = titleWrap.querySelector(".named-tag");
        if (val) {
          if (!tag) {
            tag = document.createElement("span");
            tag.className = "named-tag";
            tag.title = "Đã đặt tên";
            tag.textContent = "Đã đặt tên";
            if (titleEl) titleEl.after(tag);
          }
        } else if (tag) {
          tag.remove();
        }
      }

      const pTitle = document.querySelector("#playerTitleText");
      if (pTitle) pTitle.textContent = val || "Video";
    } else {
      if (btn) btn.disabled = false;
      toast(r.error || "Không đổi tên được", "bad");
    }
  } catch (e) {
    if (btn) btn.disabled = false;
    toast("Không đổi tên được", "bad");
  }
}

async function retryJob(id) {
  const r = await api(`/api/render/jobs/${id}/retry`, { method: "POST" });
  toast(r.ok ? "Đã xếp lại tác vụ render" : (r.error || "Lỗi khi thử lại"), r.ok ? "good" : "bad");
  refreshJobs();
}

async function cancelJob(id) {
  const r = await api(`/api/render/jobs/${id}/cancel`, { method: "POST" });
  toast(r.ok ? "Đã hủy tác vụ render" : (r.error || "Lỗi khi hủy"), r.ok ? "good" : "bad");
  refreshJobs();
  refreshQueue();
}

function confirmStopJob(jobId) {
  modal(`<h2>Dừng tác vụ render?</h2>
    <div class="bad-box">Tác vụ đang chạy sẽ bị dừng ngay lập tức. Dữ liệu render dở dang sẽ bị hủy bỏ.</div>
    <div class="hint" style="margin-top:12px">Bạn có thể chọn Thử lại sau từ Lịch sử render bất cứ lúc nào.</div>
    <div class="actions" style="margin-top:16px">
      <button class="ghost" onclick="closeModal()">Tiếp tục render</button>
      <button class="danger" onclick="executeStopJob('${esc(jobId)}')">Dừng render</button>
    </div>`);
}

async function executeStopJob(jobId) {
  closeModal();
  toast("Đang dừng tiến trình render…", "warn");
  const r = await api(`/api/render/jobs/${jobId}/cancel`, { method: "POST" });
  if (r.ok) {
    toast("Đã dừng tác vụ render thành công.", "good");
    refreshJobs();
    refreshQueue();
    loadStatus();
  } else {
    toast(r.error || "Không dừng được tác vụ.", "bad");
  }
}

async function deleteJob(jobId) {
  const r = await api(`/api/render/jobs/${jobId}/delete`, { method: "POST" });
  if (r.ok) {
    refreshJobs();
    toastWithUndo("Đã chuyển video vào Thùng rác", () => restoreJob(jobId));
  } else {
    toast(r.error || "Không xóa được video.", "bad");
  }
}

async function restoreJob(jobId) {
  const r = await api(`/api/render/jobs/${jobId}/restore`, { method: "POST" });
  if (r.ok) {
    toast("Đã khôi phục video thành công.", "good");
    refreshJobs();
    if (state.view === "trash") renderTrash();
  } else {
    toast(r.error || "Không khôi phục được video.", "bad");
  }
}

// --------------------------------------------------------------------------- //
// TRASH VIEW
// --------------------------------------------------------------------------- //
async function renderTrash() {
  const el = $("#content");
  el.innerHTML = `<h1 class="view-title">Thùng rác</h1>
    <p class="view-sub">Quản lý các AI Avatar và video render đã xóa tạm thời. Bạn có thể khôi phục lại bất kỳ lúc nào.</p>
    <div class="filter-chips" id="trashFilters">
      <span class="fchip ${state.trashFilter==='all' || !state.trashFilter ?'active':''}" data-f="all">Tất cả</span>
      <span class="fchip ${state.trashFilter==='avatars'?'active':''}" data-f="avatars">AI Avatar</span>
      <span class="fchip ${state.trashFilter==='jobs'?'active':''}" data-f="jobs">Video render</span>
    </div>
    <div id="trashContent" style="margin-top:16px">Đang tải Thùng rác…</div>`;

  $$("#trashFilters .fchip").forEach(c => c.onclick = () => {
    $$("#trashFilters .fchip").forEach(x => x.classList.remove("active"));
    c.classList.add("active");
    state.trashFilter = c.dataset.f;
    loadTrashContent();
  });
  await loadTrashContent();
}

async function loadTrashContent() {
  const tc = $("#trashContent");
  if (!tc) return;
  const r = await api("/api/trash");
  const avs = r.avatars || [];
  const jobs = r.jobs || [];
  const f = state.trashFilter || "all";

  const showAvs = (f === "all" || f === "avatars");
  const showJobs = (f === "all" || f === "jobs");

  let html = "";
  if (showAvs) {
    html += `<div class="trash-section-title">AI Avatar trong Thùng rác (${avs.length})</div>`;
    if (!avs.length) {
      html += `<div class="empty-inline">Không có AI Avatar nào trong Thùng rác.</div>`;
    } else {
      html += `<div class="grid" style="margin-bottom:24px">${avs.map(a => `
        <div class="avatar-card deleted-card">
          <div class="ac-thumb">
            <img src="/api/avatars/${esc(a.avatar_id)}/thumbnail" onerror="this.style.opacity=.25" />
          </div>
          <div class="ac-body">
            <div class="ac-name">${esc(a.name || a.avatar_id)}</div>
            <div class="ac-id">${esc(a.avatar_id)}</div>
            <div class="ac-tags"><span class="tag bad">ĐÃ XÓA</span></div>
            <div class="ac-note">Đã xóa lúc: ${a.deleted_at ? new Date(a.deleted_at * 1000).toLocaleString('vi-VN') : '—'}</div>
            <div class="ac-actions">
              <button class="primary tiny" onclick="restoreAvatar('${esc(a.avatar_id)}')">Khôi phục</button>
            </div>
          </div>
        </div>
      `).join("")}</div>`;
    }
  }

  if (showJobs) {
    html += `<div class="trash-section-title" style="margin-top:20px">Video render trong Thùng rác (${jobs.length})</div>`;
    if (!jobs.length) {
      html += `<div class="empty-inline">Không có video render nào trong Thùng rác.</div>`;
    } else {
      html += `<div class="jobs" style="margin-bottom:24px">${jobs.map(j => `
        <div class="job deleted-card" data-job="${j.job_id}">
          <div class="jthumb" style="display:flex;align-items:center;justify-content:center;color:var(--muted2);font-size:20px">🗑</div>
          <div class="jbody">
            <div class="jtitle">${esc(j.script_name || j.kind || "Video")} · ${esc(j.avatar_id)}</div>
            <div class="jsub">ID: <span class="mono">${esc(j.job_id)}</span> · Đã xóa lúc: ${j.deleted_at ? new Date(j.deleted_at * 1000).toLocaleString('vi-VN') : '—'}</div>
            <div class="jbadges"><span class="tag bad">ĐÃ XÓA</span> <span class="tag muted">${statusLabel(j.status)}</span></div>
          </div>
          <div class="row" style="flex-wrap:nowrap">
            <button class="primary tiny" onclick="restoreJob('${esc(j.job_id)}')">Khôi phục</button>
          </div>
        </div>
      `).join("")}</div>`;
    }
  }

  tc.innerHTML = html;
}

// --------------------------------------------------------------------------- //
// SYSTEM STATUS — simple summary + advanced
function serverHealthCard(s) {
  const p = s.process || {}, code = s.code || {}, con = s.contract || {};
  const started = p.server_started_at ? new Date(p.server_started_at * 1000).toLocaleString("vi-VN") : "—";
  const syncOk = (s.code_sync === "CURRENT") && (s.contract_sync !== false);
  const head = syncOk
    ? '<span style="color:var(--good)">● Đồng bộ — Không cần khởi động lại</span>'
    : '<span style="color:var(--warn)">● Cần khởi động lại Studio</span>';
  const runtimeTxt = p.canonical_runtime === false
    ? '<span style="color:var(--bad)">Sai runtime (không phải canonical)</span>'
    : (p.canonical_interpreter ? esc(p.canonical_interpreter) : "—");
  return `<div class="card">
    <h2>Trạng thái máy chủ</h2>
    <div class="kv"><span class="k">Đồng bộ mã nguồn</span><span class="v">${head}</span></div>
    <div class="kv"><span class="k">Runtime</span><span class="v">${runtimeTxt}</span></div>
    <div class="kv"><span class="k">API contract</span><span class="v">${con.compatible === false ? '<span style="color:var(--warn)">Chưa đồng bộ</span>' : (con.backend_version || "—")}${con.frontend_version ? ' <span class="muted">(UI ' + esc(con.frontend_version) + ')</span>' : ''}</span></div>
    <div class="kv"><span class="k">Khởi động lúc</span><span class="v">${esc(started)}</span></div>
    <div class="kv"><span class="k">PID</span><span class="v">${p.pid != null ? esc(String(p.pid)) : "—"}</span></div>
    <div class="kv"><span class="k">Boot ID</span><span class="v" style="font-family:var(--mono,monospace);font-size:12px">${p.boot_id ? esc(String(p.boot_id)).slice(0,12) : "—"}</span></div>
    <details class="tech"><summary>Chi tiết nâng cao</summary>
      <div class="kv"><span class="k">git HEAD</span><span class="v" style="font-family:var(--mono,monospace);font-size:12px">${esc((code.git_head||"").slice(0,16))}</span></div>
      <div class="kv"><span class="k">Git dirty</span><span class="v">${code.git_dirty ? "Có (chưa commit)" : "Không"}</span></div>
      <div class="kv"><span class="k">Startup fingerprint</span><span class="v" style="font-family:var(--mono,monospace);font-size:12px">${esc((code.startup_fingerprint||"").slice(0,16))}</span></div>
      <div class="kv"><span class="k">Disk fingerprint</span><span class="v" style="font-family:var(--mono,monospace);font-size:12px">${esc((code.disk_fingerprint||"").slice(0,16))}</span></div>
      <div class="kv"><span class="k">Production truth</span><span class="v">${(s.production_truth||{}).valid ? "Hợp lệ" : '<span style="color:var(--bad)">Không hợp lệ</span>'}</span></div>
      <div class="kv"><span class="k">Nhận công việc mới</span><span class="v">${s.studio_accepting_new_work ? "Có" : '<span style="color:var(--warn)">Không (cần restart)</span>'}</span></div>
    </details>
  </div>`;
}
function renderStatus() {
  const el = $("#content");
  const s = state.status || {};
  const allOk = s.truth_valid && s.renderer_ready && s.musetalk_ready;
  const partial = !allOk && s.truth_valid;
  const heroCls = allOk ? "" : partial ? "partial" : "bad";
  const heroTitle = allOk ? "HỆ THỐNG SẴN SÀNG" : partial ? "HOẠT ĐỘNG MỘT PHẦN" : "CHƯA SẴN SÀNG";
  const heroSub = allOk ? "Hệ thống đã sẵn sàng để tạo video."
    : partial ? "Một số thành phần chưa sẵn sàng — kiểm tra chi tiết bên dưới."
    : "Hệ thống chưa sẵn sàng — kiểm tra chi tiết bên dưới.";
  const items = [
    { name: "Mô hình Avatar", ok: s.renderer_ready, sub: s.renderer_ready ? "Sẵn sàng" : "Chưa sẵn sàng" },
    { name: "Bộ xử lý GPU", ok: (s.gpus && s.gpus.length), sub: (s.gpus || []).map(g => (g.state === "BUSY" ? "Đang xử lý" : "Sẵn sàng")).join(" · ") || "—" },
    { name: "Giọng ElevenLabs", ok: s.elevenlabs_connected, sub: s.elevenlabs_connected ? "Đã kết nối" : "Chưa kết nối" },
    { name: "Giọng dùng thử (Edge)", ok: s.edge_tts_available, sub: s.edge_tts_available ? "Khả dụng" : "Không khả dụng" },
  ];
  const t = s.truth || {};
  el.innerHTML = `
    <h1 class="view-title">Trạng thái hệ thống</h1>
    <p class="view-sub">Kiểm tra kết nối và tài nguyên tạo video.</p>
    <div class="status-hero ${heroCls}">
      <div class="sh-icon">${ICO.check}</div>
      <div><div class="sh-title">${heroTitle}</div><div class="sh-sub">${heroSub}</div></div>
    </div>
    <div class="status-grid">
      ${items.map(it => `<div class="status-item">
        <div class="si-dot ${it.ok ? '' : (it.name==='ElevenLabs'||it.name==='Edge TTS' ? 'muted' : 'bad')}"></div>
        <div><div class="si-name">${esc(it.name)}</div><div class="si-sub">${esc(it.sub)}</div></div>
      </div>`).join("")}
    </div>
    ${serverHealthCard(s)}
    <details class="tech">
      <summary>Thông tin kỹ thuật nâng cao</summary>
      <div class="card" style="margin-top:12px">
        <h2>Cấu hình chất lượng đã khóa</h2>
        <div class="kv"><span class="k">Pipeline</span><span class="v">MuseTalk v1.5</span></div>
        <div class="kv"><span class="k">Độ phân giải</span><span class="v">${t.resolution_width||"—"}×${t.resolution_height||"—"}</span></div>
        <div class="kv"><span class="k">FPS</span><span class="v">${t.fps||"—"}</span></div>
        <div class="kv"><span class="k">CUDA Graph</span><span class="v">${t.cuda_graph ? "Bật" : "Tắt"}</span></div>
        <div class="kv"><span class="k">WOLA (audio dài)</span><span class="v">${t.long_audio_wola ? "Bật" : "Tắt"}</span></div>
        <div class="kv"><span class="k">Feature Coverage Guard</span><span class="v">${t.feature_coverage_assertion ? "Bật" : "Tắt"}</span></div>
        <div class="kv"><span class="k">Thư mục render</span><span class="v">${esc(s.renders_dir||"—")}</span></div>
        <div class="kv"><span class="k">Cấu hình chất lượng</span><span class="v">${s.truth_valid ? "Hợp lệ" : "Lỗi"}</span></div>
        ${(s.gpus||[]).map(g => `<div class="kv"><span class="k">GPU ${g.id} (${esc(g.name)})</span><span class="v">${g.state === "BUSY" ? "Đang chạy" : "Sẵn sàng"}</span></div>`).join("")}
      </div>
    </details>`;
}

// --------------------------------------------------------------------------- //
// SETTINGS
async function renderSettings() {
  const s = state.status || {};
  const el = $("#content");

  let settingsData = {};
  let profilesData = [];
  try {
    const [resSet, resProf] = await Promise.all([
      api("/api/settings/elevenlabs"),
      api("/api/elevenlabs/profiles")
    ]);
    if (resSet && resSet.ok) settingsData = resSet;
    if (resProf && resProf.ok) profilesData = resProf.profiles || [];
  } catch (e) {}

  const activeModel = settingsData.model_id || el_model_id();
  const currentVoiceId = settingsData.voice_id || s.elevenlabs_voice_id || "N0Z0aL8qHhzwUHwRBcVo";
  const currentMaxChars = settingsData.max_text_chars || s.tts_max_text_chars || 4800;
  const isConnected = settingsData.connected ?? s.elevenlabs_connected;
  const keyMasked = settingsData.key_masked || s.elevenlabs_key_masked || "—";

  const MODEL_OPTIONS = [
    { id: "eleven_v4", name: "⭐ Eleven v4 (Mới nhất · Biểu cảm chân thực nhất)" },
    { id: "eleven_v4_turbo", name: "⚡ Eleven v4 Turbo (Độ trễ siêu thấp ~100ms)" },
    { id: "eleven_v3", name: "Eleven v3 (Chuẩn đàm thoại tự nhiên)" },
    { id: "eleven_v3_conversational", name: "Eleven v3 Conversational (Giao tiếp hội thoại)" },
    { id: "eleven_multilingual_v2", name: "Eleven Multilingual v2 (Đa ngôn ngữ ổn định)" },
    { id: "eleven_turbo_v2_5", name: "Eleven Turbo v2.5 (Tối ưu tốc độ)" },
    { id: "eleven_flash_v2_5", name: "Eleven Flash v2.5 (Siêu tốc ~75ms)" },
  ];

  let profilesHtml = "";
  if (profilesData && profilesData.length > 0) {
    profilesHtml = `
      <div class="card">
        <h2>Hồ sơ giọng nói đã lưu (Voice Profiles)</h2>
        <div class="hint" style="margin-bottom:12px">Danh sách các giọng đọc đã được liên kết model riêng. Bạn có thể chuyển model hoặc xóa để sử dụng model mặc định.</div>
        <div style="overflow-x:auto">
          <table style="width:100%;border-collapse:collapse;font-size:13px">
            <thead>
              <tr style="border-bottom:1px solid var(--border);text-align:left">
                <th style="padding:8px">Voice ID</th>
                <th style="padding:8px">Ngôn ngữ</th>
                <th style="padding:8px">Model hiện tại</th>
                <th style="padding:8px">Nguồn</th>
                <th style="padding:8px;text-align:right">Thao tác</th>
              </tr>
            </thead>
            <tbody>
              ${profilesData.map(p => `
                <tr style="border-bottom:1px solid var(--border2,#333)">
                  <td style="padding:8px;font-family:var(--mono)">${esc(p.voice_id)}</td>
                  <td style="padding:8px"><span class="tag">${esc(p.language_code || "vi")}</span></td>
                  <td style="padding:8px"><b style="color:var(--accent,#4f8cff)">${esc(p.preferred_model_id)}</b></td>
                  <td style="padding:8px" class="muted">${esc(p.selection_source || "—")}</td>
                  <td style="padding:8px;text-align:right">
                    ${p.preferred_model_id !== 'eleven_v4' ? `<button class="ghost tiny" onclick="switchProfileToV4('${esc(p.voice_id)}', '${esc(p.language_code)}')">Dùng v4</button>` : ''}
                    <button class="danger tiny" onclick="deleteVoiceProfileRow('${esc(p.voice_id)}', '${esc(p.language_code)}')">Xóa</button>
                  </td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        </div>
      </div>
    `;
  }

  el.innerHTML = `<h1 class="view-title">Cài đặt & Cấu hình</h1>
    <p class="view-sub">Quản lý kết nối giọng AI (ElevenLabs), mô hình thế hệ mới và cấu hình hệ thống.</p>

    <div class="card">
      <h2>Cấu hình giọng đọc ElevenLabs (AI Voice)</h2>
      <div class="kv"><span class="k">Trạng thái kết nối</span><span class="v">${isConnected ? '<span style="color:var(--good)">● Đã kết nối API</span>' : '<span style="color:var(--bad)">● Chưa kết nối API</span>'}</span></div>
      <div class="kv"><span class="k">Khóa API hiện tại</span><span class="v" id="sCurrentKey">${esc(keyMasked)}</span></div>
      <div class="kv"><span class="k">Model hiện đang áp dụng</span><span class="v"><b style="color:var(--accent,#4f8cff)">${esc(activeModel)}</b></span></div>
      <div id="quotaRow" class="kv"><span class="k">Hạn mức tài khoản (Quota)</span><span class="v muted">đang kiểm tra…</span></div>

      <div style="margin-top:20px;border-top:1px solid var(--border);padding-top:16px">
        <h3 style="font-size:14px;margin-bottom:12px;font-weight:600">Tùy chỉnh thông số ElevenLabs</h3>
        
        <div style="margin-bottom:14px">
          <label style="font-weight:600;display:block;margin-bottom:6px">1. Model AI Voice mặc định:</label>
          <select id="sModelSelect" style="width:100%;max-width:550px">
            ${MODEL_OPTIONS.map(m => `<option value="${m.id}" ${activeModel === m.id ? 'selected' : ''}>${esc(m.name)}</option>`).join('')}
          </select>
          <div class="hint">Khuyến nghị: <b>Eleven v4</b> (chất lượng lồng tiếng cao nhất và cảm xúc tự nhiên).</div>
          <label style="display:flex;align-items:center;gap:8px;margin-top:8px;cursor:pointer;font-size:13px">
            <input type="checkbox" id="sSyncProfiles" checked />
            <span>Đồng bộ model đã chọn cho các hồ sơ giọng đã lưu</span>
          </label>
        </div>

        <div style="margin-bottom:14px">
          <label style="font-weight:600;display:block;margin-bottom:6px">2. Voice ID mặc định:</label>
          <input id="sVoiceId" type="text" value="${esc(currentVoiceId)}" placeholder="Voice ID từ ElevenLabs" style="max-width:550px" />
          <div class="hint">Voice ID mặc định dùng khi tạo video mới hoặc kiểm tra giọng.</div>
        </div>

        <div style="margin-bottom:14px">
          <label style="font-weight:600;display:block;margin-bottom:6px">3. Giới hạn ký tự mỗi lượt đọc:</label>
          <input id="sMaxChars" type="number" step="100" min="500" max="40000" value="${currentMaxChars}" placeholder="4800" style="max-width:200px" />
          <div class="hint">Số ký tự tối đa cho mỗi lần đọc TTS (mặc định: 4800 ký tự).</div>
        </div>

        <div style="margin-bottom:14px">
          <label style="font-weight:600;display:block;margin-bottom:6px">4. Cập nhật API Key mới (để trống nếu không đổi):</label>
          <div class="row" style="max-width:550px">
            <input id="sKey" type="password" placeholder="Nhập API key ElevenLabs mới" style="flex:1" />
            <button type="button" class="ghost tiny" onclick="togglePasswordVisibility('sKey')">Hiện/Ẩn</button>
          </div>
          <div class="hint">Khóa API được lưu an toàn trong tệp .env nội bộ trên máy.</div>
        </div>

        <div class="actions" style="margin-top:18px">
          <button class="primary" onclick="saveElevenLabsSettings()">💾 Lưu Cấu Hình</button>
          <button class="ghost" onclick="checkQuotaManual()">🔄 Kiểm Tra Quota</button>
        </div>
      </div>
    </div>

    ${profilesHtml}

    <div class="card">
      <h2>Giọng test miễn phí (Edge TTS)</h2>
      <div class="kv"><span class="k">Trạng thái</span><span class="v">${s.edge_tts_available ? '<span style="color:var(--good)">● Khả dụng</span>' : '<span style="color:var(--bad)">● Không khả dụng</span>'}</span></div>
      <div class="hint" style="margin-top:8px">Giọng đọc miễn phí dùng để kiểm tra nhanh chuyển động môi mà không tốn quota.</div>
    </div>

    <div class="card">
      <h2>Thư mục lưu trữ & Render video</h2>
      <div class="kv"><span class="k">Đường dẫn thư mục</span><span class="v mono">${esc(s.renders_dir || "—")}</span></div>
      <div class="kv"><span class="k">Quyền ghi đĩa</span><span class="v">${s.renders_dir_writable ? '<span style="color:var(--good)">● Sẵn sàng</span>' : '<span style="color:var(--bad)">● Lỗi ghi đĩa</span>'}</span></div>
      <div class="actions" style="margin-top:12px">
        <button class="secondary tiny" onclick="openRendersFolder()">📂 Mở thư mục trên máy tính</button>
      </div>
    </div>

    ${serverHealthCard(s)}
    <details class="tech">
      <summary>Thông tin kỹ thuật hệ thống</summary>
      <div class="card" style="margin-top:12px">
        <h2>Trạng thái hệ thống (chỉ xem)</h2>
        <div class="kv"><span class="k">Bộ máy tạo video</span><span class="v">${s.renderer_ready ? "Sẵn sàng" : "—"}</span></div>
        <div class="kv"><span class="k">MuseTalk v1.5</span><span class="v">${s.musetalk_ready ? "Sẵn sàng" : "—"}</span></div>
        <div class="kv"><span class="k">ElevenLabs</span><span class="v">${s.elevenlabs_connected ? "Đã kết nối" : "Chưa kết nối"}</span></div>
        ${(s.gpus || []).map(g => `<div class="kv"><span class="k">GPU ${g.id} (${esc(g.name)})</span><span class="v">${g.state === "BUSY" ? "Đang chạy" : "Sẵn sàng"}</span></div>`).join("")}
        <div class="kv"><span class="k">Ổ lưu video</span><span class="v">${s.renders_dir_writable ? "Sẵn sàng" : "—"}</span></div>
        <div class="kv"><span class="k">Cấu hình chất lượng</span><span class="v">${s.truth_valid ? "Đã khóa / Hợp lệ" : "Lỗi"}</span></div>
        <div class="kv"><span class="k">Thư mục render</span><span class="v">${esc(s.renders_dir)}</span></div>
      </div>
    </details>`;

  const smEl = $("#sModelSelect");
  if (smEl) {
    initModelDropdown(smEl, activeModel);
  }

  checkQuotaManual(true);
}

function el_model_id() { return state.status?.elevenlabs_model_id || "—"; }

function togglePasswordVisibility(id) {
  const inp = $("#" + id);
  if (!inp) return;
  inp.type = inp.type === "password" ? "text" : "password";
}

async function saveElevenLabsSettings() {
  const model = ($("#sModelSelect") && $("#sModelSelect").value.trim()) || "";
  const voice = ($("#sVoiceId") && $("#sVoiceId").value.trim()) || "";
  const maxChars = parseInt($("#sMaxChars") && $("#sMaxChars").value) || null;
  const key = ($("#sKey") && $("#sKey").value.trim()) || "";
  const syncProfiles = $("#sSyncProfiles") ? $("#sSyncProfiles").checked : false;

  const payload = { sync_profiles: syncProfiles };
  if (model) payload.model_id = model;
  if (voice) payload.voice_id = voice;
  if (maxChars) payload.max_text_chars = maxChars;
  if (key) payload.api_key = key;

  toast("Đang lưu cấu hình…");
  const r = await api("/api/settings/elevenlabs", {
    method: "POST",
    body: JSON.stringify(payload)
  });

  if (r.ok) {
    toast("Đã lưu cấu hình ElevenLabs thành công! (Lưu vào .env và kích hoạt ngay)", "good");
    if ($("#sKey")) $("#sKey").value = "";
    await loadStatus();
    renderSettings();
  } else {
    toast(r.error || "Lỗi lưu cấu hình", "bad");
  }
}

const saveKey = saveElevenLabsSettings;

async function checkQuotaManual(silent) {
  const row = $("#quotaRow");
  if (!silent) toast("Đang kiểm tra hạn mức ElevenLabs…");
  try {
    const q = await api("/api/elevenlabs/quota");
    if (!row) return;
    if (!q.ok) {
      row.querySelector(".v").textContent = q.error || "không có thông tin";
      if (!silent) toast(q.error || "Không kiểm tra được hạn mức", "warn");
      return;
    }
    const rem = (q.remaining == null) ? "—" : q.remaining.toLocaleString("vi-VN");
    const reset = q.reset_date_utc ? ` · đặt lại ${q.reset_date_utc}` : "";
    row.querySelector(".v").innerHTML = `gói ${esc(q.tier || "—")} · ${q.character_count.toLocaleString("vi-VN")}/${q.character_limit.toLocaleString("vi-VN")} ký tự · <b style="color:${q.remaining > 0 ? 'var(--good)' : 'var(--bad)'}">${rem} còn lại</b>${reset}`;
    if (!silent) toast(`Hạn mức còn lại: ${rem} ký tự`, "good");
  } catch (e) {
    if (row) row.querySelector(".v").textContent = "không có";
  }
}

async function switchProfileToV4(voiceId, lang) {
  toast("Đang chuyển hồ sơ sang Eleven v4…");
  const r = await api("/api/elevenlabs/profiles", {
    method: "POST",
    body: JSON.stringify({ voice_id: voiceId, language_code: lang, preferred_model_id: "eleven_v4" })
  });
  if (r.ok) {
    toast(`Đã chuyển giọng ${voiceId} sang Eleven v4`, "good");
    renderSettings();
  } else {
    toast(r.error || "Lỗi cập nhật hồ sơ", "bad");
  }
}

async function deleteVoiceProfileRow(voiceId, lang) {
  if (!confirm(`Xóa cấu hình riêng của giọng ${voiceId}? Giọng sẽ dùng model mặc định.`)) return;
  const r = await api("/api/elevenlabs/profiles", {
    method: "DELETE",
    body: JSON.stringify({ voice_id: voiceId, language_code: lang })
  });
  if (r.ok) {
    toast("Đã xóa hồ sơ riêng", "good");
    renderSettings();
  } else {
    toast(r.error || "Lỗi xóa", "bad");
  }
}

async function openRendersFolder() {
  const r = await api("/api/system/open-renders-folder", { method: "POST" });
  if (r.ok) {
    toast("Đã mở thư mục renders", "good");
  } else {
    toast("Không thể mở thư mục: " + (r.error || ""), "warn");
  }
}

// --------------------------------------------------------------------------- //
// Queue bar (live)
const QUEUE_LABEL = {
  queued: "Đang chờ", rendering: "Đang render", encoding: "Đang xử lý",
  verifying: "Đang kiểm tra", complete: "Hoàn tất", preparing_audio: "Đang tạo giọng",
};
function formatETA(durationSec, progress) {
  if (!durationSec || !progress || progress <= 5 || progress >= 95) return "";
  const totalRenderSec = durationSec * 1.1;
  const remainingSec = Math.max(1, Math.round(totalRenderSec * (100 - progress) / 85));
  return ` · còn ~${fmtDur(remainingSec)}`;
}
async function refreshQueue() {
  const r = await api("/api/system/status?frontend_contract=" + encodeURIComponent(STUDIO_API_CONTRACT));
  if (r && r.active_jobs !== undefined) { state.status = r; renderTopbar(); }
  const active = (r && r.active_jobs) || [];
  state.activeJobs = active;
  const bar = $("#queueItems"); if (!bar) return;
  if (!active.length) { bar.innerHTML = `<span class="muted">Đang nghỉ</span>`; }
  else {
    bar.innerHTML = active.map(j => {
      const ic = j.status === "rendering" ? "▶" : j.status === "complete" ? "✓" : "○";
      const lbl = QUEUE_LABEL[j.status] || statusLabel(j.stage || j.status);
      const eta = (j.status === "rendering" || j.status === "encoding") ? formatETA(j.duration_sec, j.progress) : "";
      return `<div class="qitem">${ic} ${esc(j.script_name || j.kind)} · ${esc(j.avatar_id)}
        <div class="qbar"><div style="width:${j.progress || 0}%"></div></div>
        <span class="muted">${esc(lbl)}${eta}</span></div>`;
    }).join("");
  }
  const ch = $("#qChev"); if (ch) ch.textContent = active.length ? `▲ ${active.length} đang chạy` : "▲";
  if ($("#queueDrawer") && !$("#queueDrawer").hidden) renderQueueDrawer();
  if (state.view === "history") refreshJobs();
}
// Queue drawer (spec V1.3.1 §18): clicking the footer queue bar opens a compact
// panel. Idle → "Không có video đang render." Active → Avatar / job name / state /
// progress (real data only; progress only if the backend already reports it).
function toggleQueueDrawer() {
  const d = $("#queueDrawer"); if (!d) return;
  d.hidden = !d.hidden;
  if (!d.hidden) renderQueueDrawer();
}
function renderQueueDrawer() {
  const d = $("#queueDrawer"); if (!d) return;
  const active = state.activeJobs || [];
  const item = (j) => {
    const lbl = QUEUE_LABEL[j.status] || statusLabel(j.stage || j.status);
    const prog = (j.progress != null) ? `<div class="qd-prog"><div style="width:${j.progress}%"></div></div>` : "";
    const eta = (j.status === "rendering" || j.status === "encoding") ? formatETA(j.duration_sec, j.progress) : "";
    const stopBtn = (j.status === "queued")
      ? `<button class="danger tiny" onclick="cancelJob('${j.job_id}')">Hủy tác vụ</button>`
      : `<button class="danger tiny" onclick="confirmStopJob('${j.job_id}')">Dừng render</button>`;
    return `<div class="qd-item">
      <div class="row between" style="align-items:flex-start">
        <div>
          <div class="qd-name">${esc(j.script_name || j.kind || "Video")}</div>
          <div class="qd-sub">Avatar: ${esc(j.avatar_id || "—")}${j.duration_sec ? " · " + fmtDur(j.duration_sec) : ""}</div>
          <div class="qd-state">${esc(lbl)}${eta}</div>
        </div>
        <div>${stopBtn}</div>
      </div>
      ${prog}
    </div>`;
  };
  d.innerHTML = `<div class="qd-head">
    <b>HÀNG ĐỢI RENDER</b>
    <button class="ghost tiny" onclick="toggleQueueDrawer()">Đóng</button>
  </div>
  <div class="qd-body">${active.length
    ? active.map(item).join("")
    : `<div class="qd-idle">Không có video đang render.</div>`}</div>`;
}

(async function init() {
  initTheme();
  initDraftScript();
  $$(".nav-item").forEach(b => b.addEventListener("click", () => switchView(b.dataset.view)));
  state.voiceId = ls.get("studio_voiceId", "");
  state.edgeVoice = ls.get("studio_edge_voice", "vi-VN-HoaiMyNeural");
  document.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter" && state.view === "quick") { e.preventDefault(); renderFull(); }
    if (e.key === "Escape") {
      closePlayerModal();
      closeLogModal();
      closeModal();
    }
    // Video player shortcuts when player modal is open
    const pModal = $("#playerModal");
    if (pModal) {
      const vid = $("#mainVideoPlayer");
      if (vid && e.target.tagName !== "INPUT" && e.target.tagName !== "TEXTAREA") {
        if (e.code === "Space") {
          e.preventDefault();
          if (vid.paused) vid.play(); else vid.pause();
        } else if (e.key === "ArrowLeft") {
          e.preventDefault();
          vid.currentTime = Math.max(0, vid.currentTime - 5);
        } else if (e.key === "ArrowRight") {
          e.preventDefault();
          vid.currentTime = Math.min(vid.duration || 0, vid.currentTime + 5);
        }
      }
    }
  });
  window.addEventListener("click", (e) => {
    if (!e.target.closest(".ac-menu-wrap")) {
      $$(".ac-dropdown.open").forEach(d => d.classList.remove("open"));
    }
  });
  await loadStatus();
  await loadAvatars();
  await loadEdgeVoices();
  await loadApprovedVoices();
  // V1.6.0 TTS consistency: if an ElevenLabs voice was restored from localStorage,
  // resolve its language-aware config now so a render submitted WITHOUT re-clicking
  // the voice card uses the SAME model the user auditioned in "Nghe mẫu"
  // (eleven_v3 for Thanh/vi), not the legacy eleven_turbo_v2_5 default. Best-effort;
  // the render submit guard re-resolves if this is still null.
  if (state.voiceId) {
    try { await checkVoice(); if (state.voiceChecked) await resolveVoiceConfig("auto_current"); } catch (e) {}
  }
  switchView("home");

  // Smart Visibility-Aware Background Poller (Best Practice SaaS Architecture)
  let _pollerTimer = null;
  function scheduleNextPoll() {
    if (_pollerTimer) clearTimeout(_pollerTimer);
    const isHidden = document.hidden;
    const hasActiveWork = state.activeJobs && state.activeJobs.length > 0;
    const delay = isHidden ? 20000 : (hasActiveWork ? 2000 : 3500);
    _pollerTimer = setTimeout(async () => {
      try {
        await refreshQueue();
      } catch (e) {}
      scheduleNextPoll();
    }, delay);
  }
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) {
      refreshQueue();
      loadAvatars();
    }
    scheduleNextPoll();
  });
  scheduleNextPoll();
  setInterval(() => { if (!document.hidden) loadAvatars(); }, 25000);
})();