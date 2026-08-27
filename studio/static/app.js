/* AI Avatar Studio — operator UI controller. Vanilla JS, no framework. */
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
  setTimeout(() => t.remove(), 4200);
};

const state = {
  view: "quick",
  status: null,
  avatars: [],
  selectedAvatar: null,
  scriptText: "",
  scriptInfo: null,
  voiceId: "",
  voiceMeta: null,
  voiceChecked: false,
  splitMode: "full",
  prepState: null,
};

// --------------------------------------------------------------------------- //
async function loadStatus() {
  state.status = await api("/api/system/status");
  renderTopbar();
  renderSysstatMini();
}
function renderTopbar() {
  const s = state.status;
  if (!s) return;
  let cls = "bad", txt = "NOT READY";
  if (s.truth_valid && s.renderer_ready && s.musetalk_ready) { cls = "good"; txt = "READY"; }
  else if (s.truth_valid) { cls = "warn"; txt = "PARTIAL"; }
  $("#statusDot").className = "dot " + cls;
  $("#statusText").textContent = txt;
}
function renderSysstatMini() {
  const s = state.status; if (!s) return;
  const g = (s.gpus || []).map(x => `GPU${x.id} ${x.state}`).join(" · ") || "—";
  $("#sysstatMini").innerHTML = `
    <div class="r"><span>Renderer</span><span>${s.renderer_ready ? "READY" : "—"}</span></div>
    <div class="r"><span>MuseTalk</span><span>${s.musetalk_ready ? "READY" : "—"}</span></div>
    <div class="r"><span>ElevenLabs</span><span>${s.elevenlabs_connected ? "ON" : "OFF"}</span></div>
    <div class="r"><span>${esc(g)}</span><span></span></div>
    <div class="r"><span>Truth</span><span>${s.truth_valid ? "VALID" : "INVALID"}</span></div>`;
}
async function loadAvatars() {
  const r = await api("/api/avatars");
  state.avatars = r.avatars || [];
}

// --------------------------------------------------------------------------- //
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
    <div class="pl">Lip-sync: <b>LOCKED</b></div>
    <div class="pl">Status: <b>Production Verified</b></div>
    <div class="locked">🔒 LOCKED</div>
  </div>`;
}
async function renderQuick() {
  const el = $("#content");
  el.innerHTML = `
    <h1 class="view-title">Quick Render</h1>
    <p class="view-sub">Avatar → Script → Voice → Test → Render</p>
    ${productionProfileHTML()}
    <div class="card" data-view="quick">
      <h2>Avatar</h2>
      <div class="avatar-select">
        <select id="qAvatar"></select>
        <button class="ghost" onclick="switchView('create')">＋ Add New Avatar</button>
      </div>
      <div id="qAvatarInfo" class="muted" style="margin-top:8px;font-size:12px"></div>
    </div>

    <div class="card">
      <h2>Script</h2>
      <div class="row">
        <label style="flex:1">Upload .docx / .txt
          <input type="file" id="qFile" accept=".txt,.docx" />
        </label>
      </div>
      <div class="section-label">or paste script</div>
      <textarea id="qScript" rows="6" placeholder="Paste your script here…"></textarea>
      <div id="qScriptInfo" class="muted" style="margin-top:8px;font-size:12px"></div>
    </div>

    <div class="card">
      <h2>ElevenLabs Voice ID</h2>
      <label>Paste Voice ID (e.g. pGapy9MNHCukzJtjavF0)</label>
      <div class="row">
        <input id="qVoice" placeholder="ElevenLabs Voice ID" style="flex:1" />
        <button id="qCheckVoice" onclick="checkVoice()">Check Voice</button>
        <button class="ghost" onclick="previewVoice()">▶ Preview Voice</button>
      </div>
      <div id="qVoiceInfo" style="margin-top:8px;font-size:12px"></div>
      <audio id="qPreview" style="display:none;margin-top:8px;width:100%" controls></audio>
    </div>

    <div class="card">
      <h2>Length</h2>
      <label>Render length</label>
      <select id="qSplit">
        <option value="full">Full Script</option>
        <option value="30s">First 30 seconds</option>
        <option value="1min">First 1 minute</option>
        <option value="3min">First 3 minutes</option>
        <option value="auto">Auto Split (sentence-safe)</option>
      </select>
    </div>

    <div class="actions">
      <button class="primary" id="qTestBtn" onclick="renderTest10s()">⏱ TEST 10s</button>
      <button class="primary" id="qRenderBtn" onclick="renderFull()">⬇ RENDER VIDEO</button>
    </div>`;
  // populate avatar select
  const sel = $("#qAvatar");
  sel.innerHTML = `<option value="">— Select avatar —</option>` +
    state.avatars.filter(a => a.ready).map(a =>
      `<option value="${esc(a.avatar_id)}">${esc(a.avatar_id)} · ${esc(a.avatar_type)}</option>`).join("");
  sel.onchange = () => {
    const a = state.avatars.find(x => x.avatar_id === sel.value);
    state.selectedAvatar = a;
    $("#qAvatarInfo").innerHTML = a ? `<span class="tag good">READY</span> ${esc(a.avatar_type)} · ${a.frame_count} frames` : "";
  };
  // restore state
  if (state.selectedAvatar) { sel.value = state.selectedAvatar.avatar_id; sel.onchange(); }
  $("#qScript").value = state.scriptText;
  $("#qScript").oninput = (e) => { state.scriptText = e.target.value; updateScriptInfo(); };
  $("#qVoice").value = state.voiceId;
  $("#qVoice").oninput = (e) => { state.voiceId = e.target.value; state.voiceChecked = false; state.voiceMeta = null; };
  $("#qSplit").value = state.splitMode;
  $("#qSplit").onchange = (e) => state.splitMode = e.target.value;
  $("#qFile").onchange = async (e) => {
    const f = e.target.files[0]; if (!f) return;
    const fd = new FormData(); fd.append("file", f);
    const r = await fetch("/api/script/parse", { method: "POST", body: fd });
    const d = await r.json();
    if (d.ok) {
      state.scriptText = d.text; state.scriptInfo = d;
      $("#qScript").value = d.text; updateScriptInfo();
      toast(`Loaded ${d.source}: ${d.words} words, ${d.estimated_duration_str}`, "good");
    } else toast(d.error || "Could not parse script", "bad");
  };
  updateScriptInfo();
}
function updateScriptInfo() {
  const txt = state.scriptText;
  if (!txt) { $("#qScriptInfo").textContent = ""; return; }
  const words = txt.split(/\s+/).filter(Boolean).length;
  const dur = words / 3.0;
  $("#qScriptInfo").textContent = `${words} words · ~${fmtDur(dur)}`;
}
async function checkVoice() {
  const vid = $("#qVoice").value.trim();
  if (!vid) return toast("Enter a Voice ID first", "warn");
  const info = $("#qVoiceInfo"); info.innerHTML = `<span class="muted">Checking…</span>`;
  const r = await api("/api/voice/check", { method: "POST", body: JSON.stringify({ voice_id: vid }) });
  if (r.ok) {
    state.voiceChecked = true; state.voiceMeta = r;
    const name = r.name ? `<b>${esc(r.name)}</b>` : `<span class="muted">(name not exposed by account)</span>`;
    const labels = r.labels && Object.keys(r.labels).length
      ? ` · ${esc(Object.values(r.labels).join(", "))}` : "";
    info.innerHTML = `<span class="tag good">✓ VALID</span> ${name}${labels}`;
  } else {
    state.voiceChecked = false; state.voiceMeta = null;
    info.innerHTML = `<span class="tag bad">✗ INVALID</span> <span class="muted">${esc(r.error || "Voice ID invalid or unavailable.")}</span>`;
  }
}
async function previewVoice() {
  const vid = $("#qVoice").value.trim();
  const txt = state.scriptText;
  if (!vid) return toast("Enter a Voice ID first", "warn");
  if (!txt) return toast("Add some script first", "warn");
  toast("Generating ~9s preview…");
  const r = await api("/api/voice/preview", { method: "POST", body: JSON.stringify({ voice_id: vid, script_text: txt }) });
  if (r.ok) {
    const a = $("#qPreview"); a.src = r.preview_url; a.style.display = "block"; a.play();
  } else toast(r.error || "Preview failed (no fallback voice used)", "bad");
}
async function renderTest10s() {
  const av = $("#qAvatar").value, vid = $("#qVoice").value.trim(), txt = state.scriptText;
  if (!av) return toast("Select an avatar", "warn");
  if (!vid) return toast("Enter a Voice ID", "warn");
  if (!txt) return toast("Add a script", "warn");
  $("#qTestBtn").disabled = true;
  const r = await api("/api/render/test", { method: "POST",
    body: JSON.stringify({ avatar_id: av, voice_id: vid, script_text: txt, voice_meta: state.voiceMeta }) });
  $("#qTestBtn").disabled = false;
  if (r.ok) { toast("10s test render queued", "good"); switchView("history"); }
  else toast(r.error || "Could not queue test render", "bad");
}
async function renderFull() {
  const av = $("#qAvatar").value, vid = $("#qVoice").value.trim(), txt = state.scriptText;
  if (!av) return toast("Select an avatar", "warn");
  if (!vid) return toast("Enter a Voice ID", "warn");
  if (!txt) return toast("Add a script", "warn");
  $("#qRenderBtn").disabled = true;
  const r = await api("/api/render", { method: "POST",
    body: JSON.stringify({ avatar_id: av, voice_id: vid, script_text: txt,
      split_mode: state.splitMode, voice_meta: state.voiceMeta }) });
  $("#qRenderBtn").disabled = false;
  if (r.ok) { toast(`Render queued (${(r.job_ids || []).length} part(s))`, "good"); switchView("history"); }
  else toast(r.error || "Could not queue render", "bad");
}

// --------------------------------------------------------------------------- //
// CREATE AVATAR
let createState = { videoPath: null, quality: null, override: false, prepAvatarId: null };
async function renderCreate() {
  const el = $("#content");
  el.innerHTML = `
    <h1 class="view-title">Create Avatar</h1>
    <p class="view-sub">Upload → Analyze → Quality Report → Decide → Prepare → Ready</p>
    <div class="card" data-view="create">
      <h2>1. Upload Video</h2>
      <div class="dropzone" id="cDrop">
        <div class="big">⬆</div>
        <div>Drop a video here or click to choose<br><span class="muted2">.mp4 .mov .avi .mkv .webm</span></div>
        <input type="file" id="cFile" accept="video/*,.mp4,.mov,.avi,.mkv,.webm" hidden />
      </div>
      <div id="cFileLabel" class="muted" style="margin-top:8px;font-size:12px"></div>
      <div class="actions">
        <button class="primary" id="cAnalyzeBtn" onclick="analyzeVideo()" disabled>Analyze</button>
      </div>
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
  $("#cFileLabel").innerHTML = `Uploading <b>${esc(f.name)}</b>…`;
  const r = await fetch("/api/avatar/analyze", { method: "POST", body: fd });
  const d = await r.json();
  $("#cFileLabel").innerHTML = `${esc(f.name)} · ${d.integrity ? d.integrity.width + "×" + d.integrity.height + " · " + d.integrity.duration + "s" : ""}`;
  if (d.technical_failure) {
    createState = { videoPath: null, quality: null, override: false, prepAvatarId: null };
    $("#cAnalyzeBtn").disabled = true;
    $("#cQuality").innerHTML = `<div class="card"><h2>Technical Problem</h2>
      <div class="bad-box">${esc(d.error || "Cannot process this video.")}</div>
      <div class="qhint">This is a technical failure, not a quality warning — the source cannot be used.</div></div>`;
    return;
  }
  createState.videoPath = d.video_path;
  createState.quality = d;
  $("#cAnalyzeBtn").disabled = false;
  renderQuality(d);
}
function renderQuality(d) {
  const ic = (s) => s === "PASS" ? `<span class="ic pass">✓</span>` :
    s === "WARN" ? `<span class="ic warn">⚠</span>` : `<span class="ic fail">✗</span>`;
  const rows = (d.categories || []).map(c =>
    `<div class="qrow"><span class="ql">${ic(c.status)} ${c.category.split("_").map(w=>w[0]+w.slice(1).toLowerCase()).join(" ")}</span>
      <span class="qr">${esc(c.message)}</span></div>`).join("");
  const overallCls = d.overall === "PASS" ? "pass" : d.overall === "WARN" ? "warn" : "fail";
  const overallTxt = d.overall === "PASS" ? "GOOD — this source is suitable." :
    d.overall === "WARN" ? "WARNING — usable, but lip-sync quality may be lower." : "POOR — quality is low; override to use anyway.";
  $("#cQuality").innerHTML = `<div class="card">
    <h2>Avatar Quality</h2>${rows}
    <div class="qoverall ${overallCls}">${overallTxt}</div>
    <div class="qhint">${d.overall === "PASS" ? "" : "Quality problems are warnings, not blocks. You may use this source anyway."}</div>
    <div class="actions">
      <button class="ghost" onclick="resetCreate()">Choose Another Video</button>
      <button class="primary" onclick="showPrepare()">${d.overall === "PASS" ? "Continue" : "Use Anyway & Prepare"}</button>
    </div>
  </div>`;
  if (d.overall !== "PASS") createState.override = true;
}
function resetCreate() {
  createState = { videoPath: null, quality: null, override: false, prepAvatarId: null };
  renderCreate();
}
function showPrepare() {
  const d = createState.quality || {};
  $("#cPrepare").innerHTML = `<div class="card">
    <h2>Prepare Avatar</h2>
    <label>Avatar Name</label>
    <input id="cName" placeholder="e.g. doTrang_closeup" value="${esc((d.face_h_ratio||0) >= 0.16 ? "closeup" : "avatar")}" />
    <div class="qhint" style="margin:8px 0">A safe avatar_id is generated from the name. Existing avatars are never overwritten.</div>
    <div class="actions">
      <button class="primary" id="cPrepBtn" onclick="prepareAvatar()">Prepare Avatar</button>
    </div>
    <div id="cPrepProgress"></div>
  </div>`;
}
async function prepareAvatar() {
  const name = $("#cName").value.trim();
  if (!name) return toast("Enter an avatar name", "warn");
  const q = createState.quality || {};
  const r = await api("/api/avatar/prepare", { method: "POST", body: JSON.stringify({
    video_path: createState.videoPath, avatar_name: name, allow_warning_override: createState.override,
    quality_result: q.raw, quality_warnings: q.warnings, overall: q.overall }) });
  if (!r.ok) return toast(r.error || "Preparation failed to start", "bad");
  createState.prepAvatarId = r.avatar_id;
  $("#cPrepBtn").disabled = true;
  toast("Preparing avatar…", "good");
  pollPrep();
}
async function pollPrep() {
  const aid = createState.prepAvatarId; if (!aid) return;
  const r = await api(`/api/avatar/prepare/${aid}/status`);
  const box = $("#cPrepProgress");
  if (!box) return;
  const pct = r.done ? 100 : 35;
  box.innerHTML = `<div class="stage">${esc(r.stage || "Working…")}</div>
    <div class="progress"><div style="width:${pct}%"></div></div>
    ${r.error ? `<div class="bad-box">${esc(r.error)}</div>` : ""}
    ${r.done && r.ready ? `<div class="qoverall pass">Avatar Ready</div>
      <div class="actions"><button class="primary" onclick="usePrepared('${esc(aid)}')">Use This Avatar</button></div>` : ""}`;
  if (r.done && r.ready) {
    await loadAvatars();
    return;
  }
  if (r.done && r.error && !r.ready) return;
  setTimeout(pollPrep, 1500);
}
function usePrepared(aid) {
  const a = state.avatars.find(x => x.avatar_id === aid);
  if (a && a.ready) { state.selectedAvatar = a; toast(`${aid} ready — selected`, "good"); }
  else toast(`${aid} not fully ready yet`, "warn");
  switchView("quick");
  setTimeout(() => { const sel = $("#qAvatar"); if (sel) { sel.value = aid; sel.onchange(); } }, 50);
}

// --------------------------------------------------------------------------- //
// AVATAR LIBRARY
async function renderLibrary() {
  const el = $("#content");
  el.innerHTML = `<h1 class="view-title">Avatar Library</h1>
    <p class="view-sub">${state.avatars.length} prepared avatar(s)</p>
    <div class="grid" id="libGrid"></div>`;
  const grid = $("#libGrid");
  grid.innerHTML = state.avatars.map(a => `
    <div class="avatar-card">
      <img src="/api/avatars/${esc(a.avatar_id)}/thumbnail" onerror="this.style.opacity=.3" />
      <div class="meta">
        <div class="name">${esc(a.avatar_id)}</div>
        <div class="sub">${esc(a.avatar_type)} · ${a.frame_count} frames</div>
        <div class="sub" style="margin-top:6px">
          <span class="tag ${a.ready ? "good" : "bad"}">${a.ready ? "READY" : "INCOMPLETE"}</span>
          ${a.quality ? `<span class="tag ${a.quality === "PASS" ? "good" : a.quality === "WARN" ? "warn" : "bad"}">${esc(a.quality)}</span>` : ""}
        </div>
        <div class="actions" style="margin-top:10px">
          <button class="primary" ${a.ready ? "" : "disabled"} onclick="useAvatar('${esc(a.avatar_id)}')">Use Avatar</button>
          <button class="ghost" onclick="window.open('/api/avatars/${esc(a.avatar_id)}/thumbnail')">Thumbnail</button>
        </div>
      </div>
    </div>`).join("") || `<p class="muted">No prepared avatars found.</p>`;
}
function useAvatar(aid) {
  const a = state.avatars.find(x => x.avatar_id === aid);
  if (!a || !a.ready) return toast("Avatar not ready", "warn");
  state.selectedAvatar = a;
  switchView("quick");
  setTimeout(() => { const sel = $("#qAvatar"); if (sel) { sel.value = aid; sel.onchange(); } }, 50);
  toast(`${aid} selected`, "good");
}

// --------------------------------------------------------------------------- //
// RENDER HISTORY
async function renderHistory() {
  const el = $("#content");
  el.innerHTML = `<h1 class="view-title">Render History</h1><p class="view-sub">All render jobs</p>
    <div class="jobs" id="jobsList"></div><div class="muted" id="jobsEmpty"></div>`;
  await refreshJobs();
}
async function refreshJobs() {
  const r = await api("/api/render/jobs?limit=100");
  const list = $("#jobsList"); if (!list) return;
  const jobs = r.jobs || [];
  if (!jobs.length) { $("#jobsEmpty").textContent = "No render jobs yet."; list.innerHTML = ""; return; }
  $("#jobsEmpty").textContent = "";
  list.innerHTML = jobs.map(j => jobCardHTML(j)).join("");
}
function jobCardHTML(j) {
  const cls = `state-${j.status}`;
  const stageTxt = j.error ? esc(j.error).slice(0, 120) : esc(j.stage || "");
  const thumb = j.status === "complete" && j.output_path
    ? `<img class="jthumb" src="/api/render/jobs/${j.job_id}/preview" />` : `<div class="jthumb" style="display:flex;align-items:center;justify-content:center;color:var(--muted2)">—</div>`;
  let actions = "";
  if (j.status === "complete") {
    actions = `<button class="ghost" onclick="openFolder('${j.job_id}')">Open Folder</button>`;
  } else if (j.status === "failed" || j.status === "cancelled") {
    actions = `<button class="ghost" onclick="retryJob('${j.job_id}')">Retry</button>`;
  } else if (!["complete"].includes(j.status)) {
    actions = `<button class="danger" onclick="cancelJob('${j.job_id}')">Cancel</button>`;
  }
  const voiceName = j.voice_meta ? (JSON.parse(j.voice_meta).name || "") : "";
  return `<div class="job" data-job="${j.job_id}">
    ${thumb}
    <div class="jbody">
      <div class="jtitle">${esc(j.script_name || j.kind)} · ${esc(j.avatar_id)}${j.gpu_id !== null ? ` · GPU${j.gpu_id}` : ""}</div>
      <div class="jsub">${esc(j.voice_id)}${voiceName ? " · " + esc(voiceName) : ""} · ${fmtDur(j.duration_sec)}</div>
      <div class="jsub ${cls}">${esc(j.status)} · ${stageTxt}</div>
      ${["rendering","encoding","verifying","preparing_audio"].includes(j.status) && j.progress != null
        ? `<div class="progress" style="margin-top:6px"><div style="width:${j.progress}%"></div></div>` : ""}
    </div>
    <div class="row" style="flex-wrap:nowrap">${actions}
      ${j.status === "complete" ? `<button class="primary" onclick="playJob('${j.job_id}')">▶ Preview</button>` : ""}
    </div>
  </div>`;
}
async function playJob(id) {
  const j = await api(`/api/render/jobs/${id}`);
  if (!j.output_path) return toast("No output", "warn");
  const card = $(`[data-job="${id}"]`);
  let v = $("#playerModal"); if (v) v.remove();
  v = document.createElement("div"); v.id = "playerModal";
  v.style.cssText = "position:fixed;inset:0;background:rgba(0,0,0,.8);display:flex;align-items:center;justify-content:center;z-index:2000";
  v.innerHTML = `<div style="max-width:90vw"><video class="preview" style="max-width:90vw;max-height:85vh" src="/api/render/jobs/${id}/preview" controls autoplay></video><div style="text-align:center;margin-top:10px"><button class="ghost" onclick="this.closest('#playerModal').remove()">Close</button></div></div>`;
  v.onclick = (e) => { if (e.target === v) v.remove(); };
  document.body.appendChild(v);
}
async function openFolder(id) { await api(`/api/render/jobs/${id}/open-folder`, { method: "POST" }); }
async function retryJob(id) {
  const r = await api(`/api/render/jobs/${id}/retry`, { method: "POST" });
  toast(r.ok ? "Re-queued" : (r.error || "Failed"), r.ok ? "good" : "bad");
  refreshJobs();
}
async function cancelJob(id) {
  const r = await api(`/api/render/jobs/${id}/cancel`, { method: "POST" });
  toast(r.ok ? "Cancelled" : (r.error || "Failed"), r.ok ? "good" : "bad");
  refreshJobs();
}

// --------------------------------------------------------------------------- //
// SETTINGS
async function renderSettings() {
  const s = state.status || {};
  const el = $("#content");
  el.innerHTML = `<h1 class="view-title">Settings</h1>
    <div class="card" data-view="settings">
      <h2>ElevenLabs</h2>
      <div class="kv"><span class="k">Connection</span><span class="v">${s.elevenlabs_connected ? '<span style="color:var(--good)">● Connected</span>' : '<span style="color:var(--bad)">● Not connected</span>'}</span></div>
      <div class="kv"><span class="k">API Key</span><span class="v">${esc(s.elevenlabs_key_masked)}</span></div>
      <div class="kv"><span class="k">TTS Model</span><span class="v">${esc(el_model_id())}</span></div>
      <div id="quotaRow" class="kv"><span class="k">Account quota</span><span class="v muted">checking…</span></div>
      <div style="margin-top:14px">
        <label>Update API Key (stored in .env, never logged)</label>
        <div class="row"><input id="sKey" type="password" placeholder="New ElevenLabs API key" style="flex:1" />
        <button class="primary" onclick="saveKey()">Update Key</button></div>
      </div>
    </div>
    <div class="card">
      <h2>System Status (read-only)</h2>
      <div class="kv"><span class="k">Production Renderer</span><span class="v">${s.renderer_ready ? "READY" : "—"}</span></div>
      <div class="kv"><span class="k">MuseTalk v1.5</span><span class="v">${s.musetalk_ready ? "READY" : "—"}</span></div>
      <div class="kv"><span class="k">ElevenLabs</span><span class="v">${s.elevenlabs_connected ? "CONNECTED" : "NOT CONNECTED"}</span></div>
      ${(s.gpus || []).map(g => `<div class="kv"><span class="k">GPU ${g.id} (${esc(g.name)})</span><span class="v">${g.state}</span></div>`).join("")}
      <div class="kv"><span class="k">Output Disk</span><span class="v">${s.renders_dir_writable ? "AVAILABLE" : "—"}</span></div>
      <div class="kv"><span class="k">Production Truth</span><span class="v">${s.truth_valid ? "VALID" : "INVALID"}</span></div>
      <div class="kv"><span class="k">Renders folder</span><span class="v">${esc(s.renders_dir)}</span></div>
    </div>
    <div class="card">
      <h2>Locked Production Profile (read-only)</h2>
      ${s.truth ? `<div class="kv"><span class="k">Pipeline</span><span class="v">MuseTalk v1.5</span></div>
      <div class="kv"><span class="k">Resolution</span><span class="v">${s.truth.resolution_width}×${s.truth.resolution_height}</span></div>
      <div class="kv"><span class="k">FPS</span><span class="v">${s.truth.fps}</span></div>
      <div class="kv"><span class="k">CUDA Graph</span><span class="v">${s.truth.cuda_graph ? "ON" : "OFF"}</span></div>
      <div class="kv"><span class="k">Long-audio WOLA</span><span class="v">${s.truth.long_audio_wola ? "ON" : "OFF"}</span></div>
      <div class="kv"><span class="k">Feature Coverage Guard</span><span class="v">${s.truth.feature_coverage_assertion ? "ON" : "OFF"}</span></div>` : `<div class="muted">Truth unavailable</div>`}
    </div>`;
  // Fetch LIVE account quota (uncached) and display it truthfully.
  fetch("/api/elevenlabs/quota").then(r => r.json()).then(q => {
    const row = $("#quotaRow"); if (!row) return;
    if (!q.ok) { row.querySelector(".v").textContent = q.error || "unavailable"; return; }
    const rem = (q.remaining == null) ? "—" : q.remaining;
    const reset = q.reset_date_utc ? ` · resets ${q.reset_date_utc}` : "";
    row.querySelector(".v").innerHTML = `tier ${esc(q.tier||"—")} · ${q.character_count}/${q.character_limit} chars · <b style="color:${q.remaining>0?'var(--good)':'var(--bad)'}">${rem} remaining</b>${reset}`;
  }).catch(() => { const row = $("#quotaRow"); if (row) row.querySelector(".v").textContent = "unavailable"; });
}
function el_model_id() { return state.status?.elevenlabs_model_id || "—"; }
async function saveKey() {
  const key = $("#sKey").value.trim();
  if (!key) return toast("Enter a key", "warn");
  const r = await api("/api/settings/elevenlabs", { method: "POST", body: JSON.stringify({ api_key: key }) });
  if (r.ok) { toast("Key saved — ElevenLabs connected", "good"); $("#sKey").value = ""; await loadStatus(); renderSettings(); }
  else toast(r.error || "Save failed", "bad");
}

// --------------------------------------------------------------------------- //
// Queue bar (live)
async function refreshQueue() {
  const r = await api("/api/system/status");
  if (r && r.active_jobs !== undefined) {
    state.status = r; renderTopbar(); renderSysstatMini();
  }
  const active = (r && r.active_jobs) || [];
  const bar = $("#queueItems");
  if (!bar) return;
  if (!active.length) { bar.innerHTML = `<span class="muted">Idle</span>`; return; }
  bar.innerHTML = active.map(j => {
    const ic = j.status === "rendering" ? "▶" : j.status === "complete" ? "✓" : "○";
    return `<div class="qitem">${ic} ${esc(j.script_name || j.kind)} ${esc(j.avatar_id)}
      <div class="qbar"><div style="width:${j.progress || 0}%"></div></div>
      <span class="muted">${esc((j.stage || "").slice(0, 24))}</span></div>`;
  }).join("");
  if (state.view === "history") refreshJobs();
}

// --------------------------------------------------------------------------- //
// init
(async function init() {
  $$(".nav-item").forEach(b => b.addEventListener("click", () => switchView(b.dataset.view)));
  await loadStatus();
  await loadAvatars();
  switchView("quick");
  setInterval(refreshQueue, 2500);
  setInterval(loadAvatars, 15000);
})();