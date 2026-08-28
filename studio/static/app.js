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
const toast = (msg, kind = "") => {
  const t = document.createElement("div");
  t.className = `toast ${kind}`;
  t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(() => t.remove(), kind === "bad" ? 7000 : 4200);
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
  view: "home", status: null, avatars: [], selectedAvatar: null,
  scriptText: "", scriptInfo: null, voiceId: "", voiceMeta: null, voiceChecked: false,
  splitMode: "full", prepState: null, jobFilter: "all",
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
};

// Standardized Vietnamese mouth-motion diagnostic script (spec B10). A
// repeatable visual test stimulus — bilabials (m/b/p), wide/open + rounded
// vowels, natural flow. The renderer is NOT optimized for this; it only makes
// Avatar A vs Avatar B comparable under identical text/voice/profile.
const STANDARD_MOUTH_TEST_SCRIPT =
  "Ba mẹ mỉm cười và Minh mua một hộp bánh mì. " +
  "Phương nói hôm nay trời đẹp, chúng ta cùng quay video thật tự nhiên.";

// --------------------------------------------------------------------------- //
async function loadStatus() {
  state.status = await api("/api/system/status");
  renderTopbar();
}
function renderTopbar() {
  const s = state.status; if (!s) return;
  let cls = "bad", txt = "CHƯA SẴN SÀNG";
  if (s.truth_valid && s.renderer_ready && s.musetalk_ready) { cls = "good"; txt = "SẴN SÀNG"; }
  else if (s.truth_valid) { cls = "warn"; txt = "MỘT PHẦN"; }
  $("#statusDot").className = "dot " + cls;
  $("#statusText").textContent = txt;
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
      <p>Chọn một trong hai cách bắt đầu bên dưới. Bạn không cần kiến thức kỹ thuật — hệ thống lo phần còn lại.</p>
      <div class="home-cards">
        <div class="home-card" onclick="switchView('quick')">
          <div class="hc-icon">${ICO.video}</div>
          <div class="hc-title">Tạo video từ Avatar có sẵn</div>
          <div class="hc-desc">Chọn Avatar → Nhập nội dung → Chọn giọng → Render video. Dùng khi bạn đã có Avatar phù hợp.</div>
          <span class="hc-cta">BẮT ĐẦU ${ICO.arrow}</span>
        </div>
        <div class="home-card alt" onclick="switchView('create')">
          <div class="hc-icon">${ICO.avatar}</div>
          <div class="hc-title">Tạo AI Avatar mới</div>
          <div class="hc-desc">Upload video của một người để tạo Avatar mới. Hệ thống tự động kiểm tra chất lượng video giúp bạn.</div>
          <span class="hc-cta">TẠO AVATAR ${ICO.arrow}</span>
        </div>
      </div>
      <div class="home-secondary">
        <div class="home-sec" onclick="switchView('library')">
          ${ICO.avatar}<div>Thư viện Avatar<div class="hs-sub">${ready} Avatar sẵn sàng</div></div>
        </div>
        <div class="home-sec" onclick="switchView('history')">
          ${ICO.history}<div>Lịch sử render<div class="hs-sub">Video đã tạo</div></div>
        </div>
        <div class="home-sec" onclick="switchView('status')">
          ${ICO.check}<div>Trạng thái hệ thống<div class="hs-sub">Kiểm tra nhanh</div></div>
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
    <h1 class="view-title">Tạo video từ Avatar có sẵn</h1>
    <p class="view-sub">Làm theo 5 bước — mỗi bước một việc.</p>
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
        <div class="step-head" onclick="quickGoto(2)"><div class="step-num">2</div><div class="step-title">Nội dung</div><div class="step-summary"></div></div>
        <div class="step-body">
          <textarea id="qScript" rows="6" placeholder="Nhập hoặc dán nội dung bạn muốn Avatar nói…"></textarea>
          <div id="qScriptInfo" class="muted" style="margin-top:8px;font-size:12px"></div>
          <details class="tech" style="margin-top:12px">
            <summary>Nhập từ file / chọn độ dài video</summary>
            <div style="margin-top:10px">
              <label>Tải lên file .docx hoặc .txt</label>
              <input type="file" id="qFile" accept=".txt,.docx" />
              ${state.scriptText ? `<button class="tiny ghost" style="margin-top:8px" onclick="clearScript()">Xóa nội dung</button>` : ""}
            </div>
            <div style="margin-top:12px">
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
          </details>
          <div class="actions"><button class="ghost" onclick="quickGoto(1)">Quay lại</button><button class="primary" id="qNext2" onclick="quickGoto(3)">Tiếp tục</button></div>
        </div>
      </div>

      <div class="step" data-step="3">
        <div class="step-head" onclick="quickGoto(3)"><div class="step-num">3</div><div class="step-title">Giọng</div><div class="step-summary"></div></div>
        <div class="step-body">
          <div class="tts-tabs" id="ttsTabs">
            <button class="tts-tab ${state.ttsProvider === 'elevenlabs' ? 'active' : ''}" data-p="elevenlabs">ELEVENLABS<span class="tt-sub">Giọng chất lượng cao</span></button>
            <button class="tts-tab ${state.ttsProvider === 'edge' ? 'active' : ''}" data-p="edge">TEST MIỄN PHÍ<span class="tt-sub">Edge TTS — dùng để kiểm tra</span></button>
          </div>
          <div class="tts-subnote" id="ttsSubnote"></div>
          <div id="ttsPanel"></div>
          <audio id="qPreview" style="display:none;margin-top:10px;width:100%" controls></audio>
          <div class="actions"><button class="ghost" onclick="quickGoto(2)">Quay lại</button><button class="primary" id="qNext3" onclick="quickGoto(4)">Tiếp tục</button></div>
        </div>
      </div>

      <div class="step" data-step="4">
        <div class="step-head" onclick="quickGoto(4)"><div class="step-num">4</div><div class="step-title">Kiểm tra</div><div class="step-summary"></div></div>
        <div class="step-body">
          <div class="hint" style="margin-bottom:12px">Render đoạn ngắn để kiểm tra chuyển động miệng trước khi tạo video đầy đủ. Bước này tùy chọn.</div>
          <div class="row">
            <button class="secondary" id="qMouthBtn" onclick="renderMouthTest()">TEST KHẨU HÌNH (MIỄN PHÍ)</button>
            <button class="ghost" id="qTestBtn" onclick="renderTest10s()">Kiểm tra 10 giây</button>
          </div>
          <details class="tech" style="margin-top:12px">
            <summary>Đoạn test chuẩn</summary>
            <div style="margin-top:10px">
              <textarea id="qMouthScript" rows="2">${esc(STANDARD_MOUTH_TEST_SCRIPT)}</textarea>
              <div class="actions"><button class="tiny ghost" onclick="useStandardMouthScript()">Dùng đoạn test chuẩn</button></div>
              <div class="hint" style="margin-top:6px">Giọng test miễn phí chỉ dùng để kiểm tra chuyển động miệng. Khi render bản chính thức, hãy chuyển sang ElevenLabs.</div>
            </div>
          </details>
          <div class="actions"><button class="ghost" onclick="quickGoto(3)">Quay lại</button><button class="primary" onclick="quickGoto(5)">Bỏ qua, tạo video</button></div>
        </div>
      </div>

      <div class="step" data-step="5">
        <div class="step-head" onclick="quickGoto(5)"><div class="step-num">5</div><div class="step-title">Tạo video</div><div class="step-summary"></div></div>
        <div class="step-body">
          <div id="qReview" class="review-grid"></div>
          <div class="hint" style="margin-bottom:12px">Khi đã hài lòng với bước kiểm tra, tạo video hoàn chỉnh.</div>
          <div class="actions">
            <button class="ghost" onclick="quickGoto(4)">Quay lại</button>
            <button class="primary big" id="qRenderBtn" onclick="renderFull()">TẠO VIDEO</button>
            <span class="muted" style="font-size:11px;align-self:center">Ctrl+Enter = tạo video</span>
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
      readyAvs.map(a => {
        const q = qMeta(a.quality_status).short;
        return `<option value="${esc(a.avatar_id)}">${esc(a.avatar_id)} · ${q} · ${esc(TYPE_VI[a.avatar_type] || a.avatar_type)}</option>`;
      }).join("");
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
  $("#qScript").value = state.scriptText;
  $("#qScript").oninput = (e) => { state.scriptText = e.target.value; updateScriptInfo(); quickRefresh(); };
  // TTS provider tabs (explicit, never silent switch).
  $$("#ttsTabs .tts-tab").forEach(t => t.onclick = () => {
    state.ttsProvider = t.dataset.p;
    $$("#ttsTabs .tts-tab").forEach(x => x.classList.toggle("active", x === t));
    renderTTSPanel();
    quickRefresh();
  });
  renderTTSPanel();
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
  const rev = document.getElementById('qReview');
  if (rev) {
    const av = state.selectedAvatar ? state.selectedAvatar.avatar_id : "—";
    const words = state.scriptText.trim() ? state.scriptText.split(/\s+/).filter(Boolean).length : 0;
    const voice = state.ttsProvider === "edge" ? "Edge TTS (miễn phí)" : (state.voiceId || "—");
    let cfgSrc = "";
    if (state.ttsProvider !== "edge") {
      const c = state.voiceConfig;
      if (!c) cfgSrc = "Cấu hình Studio";
      else if (c.match_strength === "history_item") cfgSrc = "Khớp bản ElevenLabs";
      else if (c.match_strength === "history_matched") cfgSrc = "Đã đồng bộ ElevenLabs";
      else if (c.match_strength === "settings_only") cfgSrc = "Cài đặt giọng (Model Studio)";
      else if (c.match_strength === "manual") cfgSrc = "Tùy chỉnh";
    }
    rev.innerHTML = `<div class="rv"><span class="rv-k">Avatar</span><span class="rv-v">${esc(av)}</span></div>
      <div class="rv"><span class="rv-k">Nội dung</span><span class="rv-v">${words} từ</span></div>
      <div class="rv"><span class="rv-k">Giọng</span><span class="rv-v">${esc(voice)}</span></div>
      ${cfgSrc ? `<div class="rv"><span class="rv-k">Nguồn cấu hình</span><span class="rv-v">${esc(cfgSrc)}</span></div>` : ""}`;
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

function renderTTSPanel() {
  const panel = $("#ttsPanel"); if (!panel) return;
  const note = $("#ttsSubnote");
  if (state.ttsProvider === "edge") {
    if (note) note.innerHTML = `<span class="tag muted">TEST MIỄN PHÍ — EDGE TTS</span> <span class="muted">Giọng test miễn phí, không tốn quota. Chỉ dùng để kiểm tra khẩu hình.</span>`;
    const opts = (state.edgeVoices.length ? state.edgeVoices : [
      { voice_id: "vi-VN-HoaiMyNeural", label: "Nữ — Hoài My" },
      { voice_id: "vi-VN-NamMinhNeural", label: "Nam — Nam Minh" },
    ]).map(v => `<option value="${esc(v.voice_id)}" ${v.voice_id === state.edgeVoice ? 'selected' : ''}>${esc(v.label)}</option>`).join("");
    panel.innerHTML = `
      <label>Giọng test</label>
      <div class="row">
        <select id="qEdgeVoice" style="flex:1">${opts}</select>
        <button class="ghost" onclick="previewEdgeVoice()">▶ Nghe thử</button>
      </div>
      <div id="qEdgeInfo" style="margin-top:8px;font-size:12px"></div>`;
    const esel = $("#qEdgeVoice");
    if (esel) esel.onchange = (e) => { state.edgeVoice = e.target.value; ls.set("studio_edge_voice", e.target.value); };
  } else {
    if (note) note.innerHTML = `<span class="tag good">ELEVENLABS</span> <span class="muted">Giọng production chất lượng cao. Cần Voice ID. Studio tự đồng bộ cấu hình từ ElevenLabs.</span>`;
    panel.innerHTML = `
      <label>Dán Voice ID từ ElevenLabs (ghi nhớ trên máy này)</label>
      <div class="row">
        <input id="qVoice" placeholder="ElevenLabs Voice ID" style="flex:1" />
        <button id="qCheckVoice" onclick="checkVoice()">Kiểm tra giọng</button>
        <button class="ghost" onclick="previewVoice()">▶ Nghe thử</button>
      </div>
      <div id="qVoiceInfo" style="margin-top:8px;font-size:12px"></div>
      <div id="qVoiceSync" style="margin-top:8px;font-size:12px"></div>
      <details class="tech" style="margin-top:10px">
        <summary>Cấu hình giọng — đồng bộ ElevenLabs</summary>
        <div style="margin-top:10px">
          <div class="tts-tabs" id="syncTabs" style="margin-bottom:10px">
            <button class="sync-tab active" data-m="auto_current">Cấu hình hiện tại</button>
            <button class="sync-tab" data-m="history_match">Khớp bản đã tạo</button>
            <button class="sync-tab" data-m="manual">Tùy chỉnh</button>
          </div>
          <div id="syncPanel"></div>
          <div class="hint" style="margin-top:8px">Kết quả có thể có khác biệt nhỏ giữa các lần tạo vì TTS là mô hình sinh nội dung.</div>
        </div>
      </details>`;
    const v = $("#qVoice"); if (v) {
      v.value = state.voiceId;
      // Re-evaluate wizard gating on every keystroke so #qNext3 (Tiếp tục)
      // enables as soon as a Voice ID is present (V1.4.2 fix). V1.5.0: changing
      // the Voice ID clears the previous voice's resolved config (no leak).
      v.oninput = (e) => { state.voiceId = e.target.value; state.voiceChecked = false; state.voiceMeta = null; state.voiceConfig = null; state.voiceHistory = null; state.voiceSyncMode = "auto_current"; ls.set("studio_voiceId", e.target.value); quickRefresh(); renderVoiceSync(); renderSyncPanel(); };
    }
    $$("#syncTabs .sync-tab").forEach(t => t.onclick = () => {
      state.voiceSyncMode = t.dataset.m;
      $$("#syncTabs .sync-tab").forEach(x => x.classList.toggle("active", x === t));
      renderSyncPanel();
    });
    renderVoiceSync();
    renderSyncPanel();
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
  if (ms === "history_item")      line = `<span class="tag good">✓ Đã khớp cấu hình bản ElevenLabs đã tạo</span>`;
  else if (ms === "history_matched") line = `<span class="tag good">✓ Đã đồng bộ cấu hình ElevenLabs</span>`;
  else if (ms === "settings_only")   line = `<span class="tag good">✓ Đã đồng bộ cài đặt giọng</span> <span class="muted">· Model đầu ra đang dùng cấu hình Studio</span>`;
  else if (ms === "manual")          line = `<span class="tag good">✓ Đang dùng cấu hình tùy chỉnh</span>`;
  else line = `<span class="muted">Cấu hình: ${esc(ms || "—")}</span>`;
  box.innerHTML = `${line}<div class="muted2" style="margin-top:2px">Model đang dùng: ${esc(c.model_id || "—")}${c.voice_name ? " · " + esc(c.voice_name) : ""}</div>`;
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
        <label>Model <input id="mModel" value="${esc(f(c.model_id))}" placeholder="eleven_multilingual_v2" style="width:200px"/></label>
        <label>Output <input id="mOut" value="${esc(f(c.requested_output_format))}" placeholder="mp3_44100_128" style="width:160px"/></label>
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
    const vs = c.voice_settings || {};
    const d = (x) => (x == null ? "—" : x);
    const src = (s) => SYNC_SRC_VI[s] || s || "—";
    panel.innerHTML = `<button class="ghost tiny" onclick="resolveVoiceConfig('auto_current')">LÀM MỚI</button>
      <details class="tech" style="margin-top:8px"><summary>Thông tin cấu hình</summary>
      <div style="margin-top:8px;font-size:12px">
        <div class="kv"><span class="k">Model</span><span class="v">${esc(d(c.model_id))} <span class="muted">(${esc(src(c.provenance && c.provenance.model_id))})</span></span></div>
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
  const r = await api("/api/elevenlabs/voice-config/resolve", { method: "POST", body: JSON.stringify({ voice_id: vid, mode: "history_match", history_item_id: item_id, voice_name: state.voiceMeta && state.voiceMeta.name }) });
  if (!r.ok || !r.config) return toast(r.error || "Không khớp được cấu hình", "bad");
  state.voiceConfig = r.config; state.voiceSyncMode = "history_match";
  $$("#syncTabs .sync-tab").forEach(x => x.classList.toggle("active", x.dataset.m === "history_match"));
  renderVoiceSync(); renderSyncPanel(); quickRefresh();
  toast("Đã khớp cấu hình bản ElevenLabs đã tạo", "good");
}
async function resolveVoiceConfig(mode) {
  const vid = (state.voiceId || "").trim();
  if (!vid) return;
  const box = $("#qVoiceSync");
  if (box) box.innerHTML = `<span class="muted">Đang đồng bộ cấu hình ElevenLabs…</span>`;
  const r = await api("/api/elevenlabs/voice-config/resolve", { method: "POST", body: JSON.stringify({ voice_id: vid, mode: mode || "auto_current", voice_name: state.voiceMeta && state.voiceMeta.name }) });
  if (!r.ok || !r.config) {
    // Fail-closed: API failure -> NO silent fallback. Explicit user choice only.
    if (box) box.innerHTML = `<div><span class="tag bad">Không thể đồng bộ cấu hình ElevenLabs.</span></div>
      <div class="actions" style="margin-top:8px"><button class="ghost tiny" onclick="resolveVoiceConfig('auto_current')">THỬ LẠI</button>
      <button class="ghost tiny" onclick="useStudioConfig()">DÙNG CẤU HÌNH STUDIO</button></div>`;
    state.voiceConfig = null;
    renderSyncPanel();
    quickRefresh();
    return;
  }
  state.voiceConfig = r.config;
  renderVoiceSync(); renderSyncPanel(); quickRefresh();
}
function useStudioConfig() {
  // Explicit user action: proceed with the legacy Studio-default path (no
  // synced ElevenLabs settings). Never silently chosen.
  state.voiceConfig = null;
  renderVoiceSync(); renderSyncPanel(); quickRefresh();
  toast("Đang dùng cấu hình Studio (mặc định)", "good");
}
function applyManualConfig() {
  const num = (id) => { const v = $("#" + id); const n = parseFloat(v && v.value); return isNaN(n) ? null : n; };
  state.voiceConfig = {
    voice_id: state.voiceId, voice_name: state.voiceMeta && state.voiceMeta.name,
    model_id: ($("#mModel") && $("#mModel").value.trim()) || "eleven_turbo_v2_5",
    requested_output_format: ($("#mOut") && $("#mOut").value.trim()) || "pcm_16000",
    voice_settings: {
      stability: num("mStab"), similarity_boost: num("mSim"),
      style: num("mStyle"), speed: num("mSpeed"),
      use_speaker_boost: $("#mBoost") && $("#mBoost").checked,
    },
    sync_mode: "manual", match_strength: "manual", history_item_id: null,
    config_ts: (Date.now() / 1000) | 0,
    provenance: { voice_id: "USER_SELECTION", model_id: "USER_MANUAL", voice_settings: "USER_MANUAL", output_format: "USER_MANUAL" },
  };
  state.voiceSyncMode = "manual";
  renderVoiceSync(); renderSyncPanel(); quickRefresh();
  toast("Đã áp dụng cấu hình tùy chỉnh", "good");
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
  const note = (a.render_count > 0) ? "Đã kiểm chứng qua render thực tế"
    : ((a.quality_strengths && a.quality_strengths[0]) ? a.quality_strengths[0] : "Sẵn sàng để render");
  box.innerHTML = `<div class="avatar-pick">
    <img src="/api/avatars/${esc(a.avatar_id)}/thumbnail" onerror="this.style.opacity=.3" />
    <div class="ap-meta">
      <div class="ap-name">${esc(a.avatar_id)} <span class="tag ${qm.cls}">${esc(qm.short)}</span></div>
      <div class="ap-sub"><span class="tag good">SẴN SÀNG</span> ${esc(TYPE_VI[a.avatar_type] || a.avatar_type)}</div>
      <div class="ap-sub" style="margin-top:4px">${esc(note)}</div>
    </div>
  </div>`;
}
function clearScript() {
  state.scriptText = ""; state.scriptInfo = null;
  const ta = $("#qScript"); if (ta) ta.value = "";
  updateScriptInfo();
  quickRefresh();
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
    // V1.5.0: auto-sync the per-voice ElevenLabs config (Mode A) on validation.
    if (state.ttsProvider === "elevenlabs") resolveVoiceConfig("auto_current");
  } else {
    state.voiceChecked = false; state.voiceMeta = null;
    state.voiceConfig = null; renderVoiceSync();
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
function activeVoiceId() {
  // The voice id for the currently selected provider. Edge mode uses the
  // selected free Edge voice; ElevenLabs mode uses the user-entered Voice ID.
  if (state.ttsProvider === "edge") return state.edgeVoice;
  return ($("#qVoice") && $("#qVoice").value.trim()) || state.voiceId;
}
async function renderTest10s() {
  const av = $("#qAvatar").value, vid = activeVoiceId(), txt = state.scriptText;
  if (!av) return toast("Chọn Avatar", "warn");
  if (!vid) return toast(state.ttsProvider === "edge" ? "Chọn giọng test" : "Nhập Voice ID", "warn");
  if (!txt) return toast("Nhập kịch bản", "warn");
  if (state.ttsProvider === "elevenlabs") ls.set("studio_voiceId", vid);
  $("#qTestBtn").disabled = true;
  const body = state.ttsProvider === "edge"
    ? { avatar_id: av, voice_id: vid, script_text: txt, tts_provider: "EDGE_TTS_TEST", test_mode: true, test_type: "SCRIPT_PREVIEW", voice_meta: { provider: "edge_tts", voice_label: edgeVoiceLabel(vid) } }
    : { avatar_id: av, voice_id: vid, script_text: txt, voice_meta: state.voiceMeta, tts_config: state.voiceConfig, sync_mode: state.voiceConfig && state.voiceConfig.sync_mode };
  const r = await api("/api/render/test", { method: "POST", body: JSON.stringify(body) });
  $("#qTestBtn").disabled = false;
  if (r.ok) { toast("Đã đưa kiểm tra 10 giây vào hàng đợi", "good"); switchView("history"); }
  else toast(r.error || "Không xếp hàng được", "bad");
}
async function renderFull() {
  const av = $("#qAvatar").value, vid = activeVoiceId(), txt = state.scriptText;
  if (!av) return toast("Chọn Avatar", "warn");
  if (!vid) return toast(state.ttsProvider === "edge" ? "Chọn giọng test" : "Nhập Voice ID", "warn");
  if (!txt) return toast("Nhập kịch bản", "warn");
  if (state.ttsProvider === "elevenlabs") ls.set("studio_voiceId", vid);
  $("#qRenderBtn").disabled = true;
  const body = state.ttsProvider === "edge"
    ? { avatar_id: av, voice_id: vid, script_text: txt, split_mode: state.splitMode, tts_provider: "EDGE_TTS_TEST", voice_meta: { provider: "edge_tts", voice_label: edgeVoiceLabel(vid) } }
    : { avatar_id: av, voice_id: vid, script_text: txt, split_mode: state.splitMode, voice_meta: state.voiceMeta, tts_config: state.voiceConfig, sync_mode: state.voiceConfig && state.voiceConfig.sync_mode };
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
    <h1 class="view-title">Tạo AI Avatar mới</h1>
    <p class="view-sub">Tải video của một người — hệ thống tự động kiểm tra và tạo Avatar.</p>
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
        <div class="step-head" onclick="createGoto(2)"><div class="step-num">2</div><div class="step-title">Yêu cầu</div><div class="step-summary"></div></div>
        <div class="step-body">
          <div class="req-grid">
            ${REQS.map(r => `<div class="req-item">${r.ic}<div class="ri-label">${r.label}</div><div class="ri-sub">${r.sub}</div></div>`).join("")}
          </div>
          <details class="tech" style="margin-top:14px">
            <summary>Xem hướng dẫn chi tiết</summary>
            <div class="guide-detail" style="display:block">
              <div class="guide-cols">
                <div class="guide-col should">
                  <h3>NÊN</h3>
                  <ul>
                    <li>Quay từ ngực/vai trở lên</li>
                    <li>Khuôn mặt đủ lớn trong khung hình</li>
                    <li>Nhìn gần thẳng vào camera</li>
                    <li>Miệng ở trạng thái tự nhiên, nghỉ</li>
                    <li>Không nói trong video nguồn</li>
                    <li>Nhìn thấy đầy đủ môi và cằm</li>
                    <li>Camera cố định</li>
                    <li>Ánh sáng ổn định</li>
                    <li>Chớp mắt và thở tự nhiên</li>
                    <li>Chỉ chuyển động đầu/vai rất nhẹ</li>
                  </ul>
                </div>
                <div class="guide-col avoid">
                  <h3>TRÁNH</h3>
                  <ul>
                    <li>Đứng quá xa camera</li>
                    <li>Nói liên tục</li>
                    <li>Quay nghiêng quá nhiều</li>
                    <li>Che môi hoặc cằm</li>
                    <li>Camera rung</li>
                    <li>Di chuyển cơ thể mạnh</li>
                    <li>Ánh sáng thay đổi liên tục</li>
                    <li>Motion blur</li>
                    <li>File bị nén mạnh</li>
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
  const catLabel = {
    VIDEO_INTEGRITY: "Tính toàn vẹn", FACE_SIZE: "Khuôn mặt đủ lớn",
    FACE_SHARPNESS: "Độ nét", FRONTALNESS: "Góc mặt",
    MOUTH_VISIBILITY: "Miệng nhìn rõ", CHIN_VISIBILITY: "Cằm / hàm",
    SOURCE_MOUTH_STATE: "Trạng thái miệng", MOTION: "Chuyển động",
    LIGHTING: "Ánh sáng",
  };
  const ic = (s) => s === "PASS" ? `<span class="cr-ic pass">✓</span>` :
    s === "WARN" ? `<span class="cr-ic warn">⚠</span>` :
    s === "FAIL" ? `<span class="cr-ic fail">✗</span>` :
    `<span class="cr-ic na">—</span>`;
  // Explain, not just judge (spec V1.3.1 §10). Overall status as a short title,
  // a reassurance line, then 2-4 human-readable strengths and warnings up front.
  // Per-dimension rows live behind "Xem chi tiết" (progressive disclosure).
  const cls = d.overall === "PASS" ? "tot" : d.overall === "WARN" ? "warn" : "fail";
  const title = d.overall === "PASS" ? "TỐT" : d.overall === "WARN" ? "CẦN LƯU Ý" : "KHÔNG KHUYẾN NGHỊ";
  const reassurance = d.overall === "PASS" ? "Video phù hợp để tạo Avatar."
    : "Video vẫn có thể sử dụng.";
  const cats = d.categories || [];
  const passCats = cats.filter(c => c.status === "PASS");
  const warnCats = cats.filter(c => c.status === "WARN" || c.status === "FAIL");
  const strengths = passCats.slice(0, 4).map(c => `<div class="qs good">✓ ${esc(catLabel[c.category] || c.category)}</div>`).join("");
  const warns = warnCats.slice(0, 4).map(c => `<div class="qs warn">⚠ ${esc(catLabel[c.category] || c.category)}</div>`).join("");
  const rows = cats.map(c =>
    `<div class="compare-row">${ic(c.status)}<span class="cr-label">${esc(catLabel[c.category] || c.category)}</span><span class="cr-val">${esc(c.message || "")}</span></div>`).join("");
  $("#cQuality").innerHTML = `
    <div class="overall-result ${cls}"><span class="or-title">${title}</span><span class="or-sub">${reassurance}</span></div>
    ${strengths ? `<div class="qsection-t good" style="margin-top:12px">Điểm tốt</div>${strengths}` : ""}
    ${warns ? `<div class="qsection-t warn" style="margin-top:10px">Cần lưu ý</div>${warns}` : ""}
    <details class="tech" style="margin-top:14px">
      <summary>Xem chi tiết</summary>
      <div style="margin-top:10px">${rows}
      ${d.overall !== "PASS" ? `<div class="qhint" style="margin-top:10px">Cảnh báo chất lượng không chặn việc sử dụng. Bạn vẫn có thể dùng nguồn này.</div>` : ""}</div>
    </details>`;
  if (d.overall !== "PASS") createState.override = true;
  // Mouth-state manual confirmation (spec A10/A11). The automatic detector cannot
  // reliably separate talking vs neutral in the normal range, so the user
  // confirms explicitly. Raw automated evidence is stored separately and never
  // overwritten. (talking_proxy is an internal detail — never shown to users.)
  const mouthCat = cats.find(c => c.category === "SOURCE_MOUTH_STATE");
  const autoStatus = mouthCat ? mouthCat.status : "UNKNOWN";
  const autoValue = mouthCat ? (mouthCat.value != null ? mouthCat.value : mouthCat.note) : null;
  createState.mouthStateAuto = (autoValue != null ? String(autoValue) : null);
  renderMouthConfirm(autoStatus);
}
function renderMouthConfirm(autoStatus) {
  const box = $("#cMouth"); if (!box) return;
  // Mouth-state is a sub-question of the quality check (step 4). Labeled
  // clearly (spec V1.3.1 §11); talking_proxy is never mentioned to users.
  if (autoStatus === "PASS") {
    // Auto-detected neutral mouth — no need to ask.
    createState.mouthStateUser = "NOT_TALKING";
    createState.mouthStateProvenance = "AUTO";
    box.innerHTML = `<div class="sub-card">
      <div class="sub-title">Xác nhận trạng thái miệng</div>
      <div class="compare-row"><span class="cr-ic pass">✓</span>
      <span class="cr-val">Miệng trung tính trong video nguồn — phù hợp.</span></div>
      <div class="actions"><button class="ghost" onclick="resetCreate()">Chọn video khác</button>
      <button class="primary" onclick="showPrepare()">Tiếp tục</button></div></div>`;
    return;
  }
  const preTalk = (autoStatus === "WARN" || autoStatus === "FAIL");
  if (preTalk) createState.mouthStateUser = "TALKING";
  createState.mouthStateProvenance = preTalk ? "AUTO" : "UNKNOWN";
  const r = (val, label) => `<label class="mouth-opt"><input type="radio" name="mouth" value="${val}" ${createState.mouthStateUser === val ? 'checked' : ''} onchange="onMouthPick('${val}')"/> ${label}</label>`;
  box.innerHTML = `<div class="sub-card mouth-confirm-card">
    <div class="sub-title">Xác nhận trạng thái miệng</div>
    <div class="hint" style="margin-bottom:8px">Hệ thống chưa thể xác định chắc chắn nội dung này.</div>
    <div class="qhint" style="margin:4px 0 8px">Video này:</div>
    <div class="mouth-opts">
      ${r("NOT_TALKING", "Không nói")}
      ${r("TALKING", "Có nói")}
      ${r("UNSURE", "Tôi không chắc")}
    </div>
    <div id="cMouthResult"></div>
  </div>`;
  if (preTalk) onMouthPick("TALKING");
}
function onMouthPick(val) {
  createState.mouthStateUser = val;
  createState.mouthStateProvenance = "USER_CONFIRMED";
  const res = $("#cMouthResult"); if (!res) return;
  if (val === "TALKING") {
    res.innerHTML = `<div class="warn-box" style="margin-top:10px">⚠ Nhân vật đang nói trong video nguồn<br>
      <span class="muted2" style="font-size:12px">Video vẫn có thể sử dụng, nhưng nguồn không nói thường phù hợp hơn để tạo AI Avatar ổn định.</span></div>
      <div class="actions"><button class="ghost" onclick="resetCreate()">Chọn video khác</button>
      <button class="primary" onclick="showPrepare()">Vẫn sử dụng video này</button></div>`;
  } else {
    res.innerHTML = `<div class="actions" style="margin-top:10px"><button class="ghost" onclick="resetCreate()">Chọn video khác</button>
    <button class="primary" onclick="showPrepare()">Tiếp tục</button></div>`;
  }
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
    <input id="cName" placeholder="vd: doTrang_closeup" value="${esc((d.face_h_ratio||0) >= 0.16 ? "closeup" : "avatar")}" />
    <div class="qhint" style="margin:8px 0">Tên an toàn được tạo tự động. Không ghi đè avatar đã có.</div>
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
      <div class="ac-actions">${useBtn}${detailBtn}</div>
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
    <div class="qsection"><div class="qsection-t ${pqm.cls}">B. AVATAR ĐÃ CHUẨN BỊ — ${esc(pqm.short || pq.prepared_status)}</div>
      <div class="hint">Phân tích từ dữ liệu đã chuẩn bị (full_imgs, coords, mask) — KHÔNG phải chất lượng video nguồn.</div>
      ${pstrengths ? `<div class="qsection-t good" style="margin-top:8px">Điểm tốt</div>${pstrengths}` : ""}
      ${pwarns ? `<div class="qsection-t warn" style="margin-top:8px">Điểm cần lưu ý</div>${pwarns}` : ""}
    </div>` : "";
  // --- Section C: production confidence ---
  const rh = q.render_history || {};
  const prod = PROD_VI[q.production_confidence] || PROD_VI["CHƯA KIỂM CHỨNG"];
  const prodSection = `<div class="qsection"><div class="qsection-t ${prod.cls}">C. PRODUCTION — ${esc(prod.short)}</div>
    <div class="hint">${q.production_confidence === "CHƯA KIỂM CHỨNG" ? "Chưa có render thực tế nào được ghi nhận." : `Đã có ${rh.total||0} render hoàn tất (DB: ${rh.db_complete||0}, file: ${rh.external||0}).`}</div></div>`;
  // Per-dimension rows + technical metrics live behind "Xem đánh giá chi tiết"
  // (spec V1.3.1 §14: summary-first, dimensions in expanded detail area).
  const detailBlock = `
    <details class="tech" style="margin-top:14px">
      <summary>Xem đánh giá chi tiết</summary>
      <div style="margin-top:10px">
        <div class="adv-sub">A. Video nguồn</div>
        ${dims ? `<div class="dims">${dims}</div>` : `<div class="hint">Không đo được chất lượng nguồn (video nguồn gốc không còn).</div>`}
        ${pq.dimensions && pq.dimensions.length ? `<div class="adv-sub" style="margin-top:10px">B. Avatar đã chuẩn bị</div><div class="dims">${pdims}</div>` : ""}
        ${(q.face_h_ratio != null || (q.dimensions || []).some(d => d.value != null)) ? `
        <details class="advanced" style="margin-top:10px"><summary>Thông tin kỹ thuật</summary>
          ${q.face_h_ratio != null ? `<div class="kv"><span class="k">face_h_ratio (nguồn)</span><span class="v">${q.face_h_ratio}</span></div>` : ""}
          ${(pq.dimensions || []).filter(d => d.value != null && typeof d.value !== 'object').map(d => `<div class="kv"><span class="k">${esc(d.key)}</span><span class="v">${esc(d.value)}</span></div>`).join("")}
        </details>` : ""}
      </div>
    </details>`;
  modal(`<h2>${esc(aid)}</h2>
    <div class="summary-blocks">
      <div class="qsection"><div class="qsection-t ${qm.cls}">A. VIDEO NGUỒN — ${esc(qm.short || q.quality_status)}</div>
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
  el.innerHTML = `<h1 class="view-title">Lịch sử render</h1>
    <p class="view-sub">Video bạn tạo sẽ xuất hiện tại đây.</p>
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
  if (!jobs.length) {
    list.innerHTML = "";
    $("#jobsEmpty").innerHTML = `<div class="empty"><div class="big">🕘</div>
      <div class="e-title">Chưa có video nào</div>
      <div class="e-sub">Video bạn tạo sẽ xuất hiện tại đây.</div></div>`;
    return;
  }
  $("#jobsEmpty").textContent = "";
  list.innerHTML = jobs.map(j => jobCardHTML(j)).join("");
}
function jobCardHTML(j) {
  const stageTxt = j.error ? esc(j.error).slice(0, 160) : statusLabel(j.stage || j.status);
  const thumb = j.status === "complete" && j.output_path
    ? `<video class="jthumb" src="/api/render/jobs/${j.job_id}/preview" muted preload="metadata" playsinline></video>`
    : `<div class="jthumb" style="display:flex;align-items:center;justify-content:center;color:var(--muted2);font-size:20px">${j.status === "failed" ? "✗" : j.status === "timed_out" ? "⏱" : "—"}</div>`;
  let actions = "";
  // "Mở thư mục" opens a folder on the HOST machine — only meaningful on
  // localhost. For a remote collaborator (Cloudflare tunnel from another PC)
  // it would do nothing useful, so hide it there (spec V1.3.1 §16).
  if (j.status === "complete" && isLocalhost()) actions = `<button class="ghost tiny" onclick="openFolder('${j.job_id}')">Mở thư mục</button>`;
  else if (["failed","cancelled","timed_out"].includes(j.status)) actions = `<button class="ghost tiny" onclick="retryJob('${j.job_id}')">Thử lại</button>`;
  else if (j.status !== "complete") actions = `<button class="danger tiny" onclick="cancelJob('${j.job_id}')">Hủy</button>`;
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
        if (ms === "history_item" || tc.sync_mode === "history_match") syncBadge = `<span class="tag good">Match History</span>`;
        else if (ms === "history_matched") syncBadge = `<span class="tag good">Đồng bộ</span>`;
        else if (ms === "settings_only") syncBadge = `<span class="tag muted">Cài đặt giọng</span>`;
        else if (ms === "manual") syncBadge = `<span class="tag muted">Tùy chỉnh</span>`;
      }
    } catch (e) { /* ignore */ }
  }
  // Distinguish TEST vs VIDEO HOÀN CHỈNH visually.
  const testBadge = isMouthTest
    ? `<span class="tag warn">TEST KHẨU HÌNH</span>`
    : (isTest ? `<span class="tag warn">TEST</span>` : `<span class="tag good">VIDEO HOÀN CHỈNH</span>`);
  const kindLabel = isMouthTest ? "Test khẩu hình" : (j.kind === "test10s" ? "Kiểm tra 10s" : (j.script_name || "Video đầy đủ"));
  return `<div class="job ${isTest ? 'is-test' : 'is-prod'}" data-job="${j.job_id}">
    ${thumb}
    <div class="jbody">
      <div class="jtitle">${esc(kindLabel)} · ${esc(j.avatar_id)}</div>
      <div class="jsub">Giọng: ${voiceDisplay}${voiceName && provider === "ELEVENLABS" ? " · " + esc(voiceName) : ""} · ${fmtDur(j.duration_sec)}</div>
      <div class="jbadges">${testBadge} ${providerTag} ${syncBadge}</div>
      <div class="fstatus ${j.status}">${statusLabel(j.status)}${j.error ? " · " + stageTxt : ""}</div>
      ${["rendering","encoding","verifying","preparing_audio"].includes(j.status) && j.progress != null ? `<div class="progress" style="margin-top:6px"><div style="width:${j.progress}%"></div></div>` : ""}
    </div>
    <div class="row" style="flex-wrap:nowrap">
      ${actions}
      ${j.status === "complete" ? `<button class="ghost tiny" onclick="downloadJob('${j.job_id}','${esc(kindLabel)}')">Tải video</button>
      <button class="primary tiny" onclick="playJob('${j.job_id}')">▶ Xem video</button>` : ""}
    </div>
  </div>`;
}
async function playJob(id) {
  const j = await api(`/api/render/jobs/${id}`);
  if (!j.output_path) return toast("Không có file", "warn");
  let v = $("#playerModal"); if (v) v.remove();
  v = document.createElement("div"); v.id = "playerModal";
  v.style.cssText = "position:fixed;inset:0;background:rgba(16,24,40,.6);display:flex;align-items:center;justify-content:center;z-index:2000";
  v.innerHTML = `<div style="max-width:90vw"><video class="preview" style="max-width:90vw;max-height:85vh" src="/api/render/jobs/${id}/preview" controls autoplay></video><div style="text-align:center;margin-top:10px"><button class="ghost" onclick="this.closest('#playerModal').remove()">Đóng</button></div></div>`;
  v.onclick = (e) => { if (e.target === v) v.remove(); };
  document.body.appendChild(v);
}
async function downloadJob(id, name) {
  const a = document.createElement("a");
  a.href = `/api/render/jobs/${id}/preview`;
  a.download = `${name || "video"}.mp4`;
  document.body.appendChild(a); a.click(); a.remove();
}
async function openFolder(id) { await api(`/api/render/jobs/${id}/open-folder`, { method: "POST" }); }
async function retryJob(id) { const r = await api(`/api/render/jobs/${id}/retry`, { method: "POST" }); toast(r.ok ? "Đã xếp lại" : (r.error || "Lỗi"), r.ok ? "good" : "bad"); refreshJobs(); }
async function cancelJob(id) { const r = await api(`/api/render/jobs/${id}/cancel`, { method: "POST" }); toast(r.ok ? "Đã hủy" : (r.error || "Lỗi"), r.ok ? "good" : "bad"); refreshJobs(); }

// --------------------------------------------------------------------------- //
// SYSTEM STATUS — simple summary + advanced
function renderStatus() {
  const el = $("#content");
  const s = state.status || {};
  const allOk = s.truth_valid && s.renderer_ready && s.musetalk_ready;
  const partial = !allOk && s.truth_valid;
  const heroCls = allOk ? "" : partial ? "partial" : "bad";
  const heroTitle = allOk ? "HỆ THỐNG SẴN SÀNG" : partial ? "HOẠT ĐỘNG MỘT PHẦN" : "CHƯA SẴN SÀNG";
  const heroSub = allOk ? "Tất cả thành phần sẵn sàng để tạo video."
    : partial ? "Một số thành phần chưa sẵn sàng — kiểm tra chi tiết bên dưới."
    : "Hệ thống chưa sẵn sàng — kiểm tra chi tiết bên dưới.";
  const items = [
    { name: "AI Avatar", ok: s.renderer_ready, sub: s.renderer_ready ? "Sẵn sàng" : "Chưa sẵn sàng" },
    { name: "GPU", ok: (s.gpus && s.gpus.length), sub: (s.gpus || []).map(g => `GPU${g.id} ${g.state === "BUSY" ? "đang chạy" : "sẵn sàng"}`).join(" · ") || "—" },
    { name: "ElevenLabs", ok: s.elevenlabs_connected, sub: s.elevenlabs_connected ? "Đã kết nối" : "Chưa kết nối" },
    { name: "Edge TTS", ok: s.edge_tts_available, sub: s.edge_tts_available ? "Khả dụng" : "Không khả dụng" },
  ];
  const t = s.truth || {};
  el.innerHTML = `
    <h1 class="view-title">Trạng thái hệ thống</h1>
    <p class="view-sub">Kiểm tra nhanh trước khi tạo video.</p>
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
  el.innerHTML = `<h1 class="view-title">Cài đặt</h1>
    <p class="view-sub">Kết nối giọng và cấu hình tài khoản.</p>
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
      <h2>Giọng test miễn phí (Edge TTS)</h2>
      <div class="kv"><span class="k">Trạng thái</span><span class="v">${s.edge_tts_available ? '<span style="color:var(--good)">● Khả dụng</span>' : '<span style="color:var(--bad)">● Không khả dụng</span>'}</span></div>
      <div class="hint" style="margin-top:8px">Giọng test miễn phí dùng dịch vụ TTS online. Không gửi API key, video avatar hay ảnh đã chuẩn bị. Chỉ dùng để kiểm tra chuyển động miệng — không phải giọng production.</div>
    </div>
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
const QUEUE_LABEL = {
  queued: "Đang chờ", rendering: "Đang render", encoding: "Đang xử lý",
  verifying: "Đang kiểm tra", complete: "Hoàn tất", preparing_audio: "Đang tạo giọng",
};
async function refreshQueue() {
  const r = await api("/api/system/status");
  if (r && r.active_jobs !== undefined) { state.status = r; renderTopbar(); }
  const active = (r && r.active_jobs) || [];
  state.activeJobs = active;
  const bar = $("#queueItems"); if (!bar) return;
  if (!active.length) { bar.innerHTML = `<span class="muted">Đang nghỉ</span>`; }
  else {
    bar.innerHTML = active.map(j => {
      const ic = j.status === "rendering" ? "▶" : j.status === "complete" ? "✓" : "○";
      const lbl = QUEUE_LABEL[j.status] || statusLabel(j.stage || j.status);
      return `<div class="qitem">${ic} ${esc(j.script_name || j.kind)} · ${esc(j.avatar_id)}
        <div class="qbar"><div style="width:${j.progress || 0}%"></div></div>
        <span class="muted">${esc(lbl)}</span></div>`;
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
    return `<div class="qd-item">
      <div class="qd-name">${esc(j.script_name || j.kind || "Video")}</div>
      <div class="qd-sub">Avatar: ${esc(j.avatar_id || "—")}</div>
      <div class="qd-state">${esc(lbl)}</div>
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
  $$(".nav-item").forEach(b => b.addEventListener("click", () => switchView(b.dataset.view)));
  state.voiceId = ls.get("studio_voiceId", "");
  state.edgeVoice = ls.get("studio_edge_voice", "vi-VN-HoaiMyNeural");
  document.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter" && state.view === "quick") { e.preventDefault(); renderFull(); }
    if (e.key === "Escape") closeModal();
  });
  await loadStatus();
  await loadAvatars();
  await loadEdgeVoices();
  switchView("home");
  setInterval(refreshQueue, 2500);
  setInterval(loadAvatars, 15000);
})();