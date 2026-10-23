"""
AI Avatar Studio V2 - Photorealistic Human Performance Studio Controller
Operating on Port 8178 (Independent V2 Web UI & API Orchestrator).
"""
import os
import sys
import time
import json
import uuid
import threading
from typing import Dict, Any
from flask import Flask, request, jsonify, render_template_string, send_from_directory
import cv2

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, REPO_ROOT)

from engines.musetalk_engine import MuseTalkEngine
from audio.performance_director import PerformanceDirector
from audio.vietnamese_text_normalizer import VietnameseTextNormalizer
from core.long_video_generator import LongVideoGenerator
from core.quality_video_generator import QualityVideoGenerator
from quality.qc_gate import QualityControlGate

app = Flask("AI_Avatar_Studio_V2")

V2_RENDERS_DIR = r"D:\CongThang_AI_Avatar\v2_renders"
os.makedirs(V2_RENDERS_DIR, exist_ok=True)

# State
ENGINE = MuseTalkEngine(repo_root=REPO_ROOT)
DIRECTOR = PerformanceDirector()
NORMALIZER = VietnameseTextNormalizer()
GENERATOR = LongVideoGenerator(output_root=V2_RENDERS_DIR)
QUALITY_GENERATOR = QualityVideoGenerator(output_root=V2_RENDERS_DIR)
QC_GATE = QualityControlGate()

JOBS_DB: Dict[str, Dict[str, Any]] = {}
JOB_LOCK = threading.Lock()


def get_available_avatars():
    avatars_dir = os.path.join(REPO_ROOT, "data", "avatars")
    avatars = []
    if os.path.exists(avatars_dir):
        for entry in os.listdir(avatars_dir):
            full_p = os.path.join(avatars_dir, entry)
            if os.path.isdir(full_p) and not entry.startswith('.'):
                info_p = os.path.join(full_p, "avator_info.json")
                coords_p = os.path.join(full_p, "coords.pkl")
                latents_p = os.path.join(full_p, "latents.pt")
                ready = os.path.exists(coords_p) and os.path.exists(latents_p)
                avatars.append({
                    "avatar_id": entry,
                    "name": entry.replace('_', ' ').title(),
                    "ready": ready,
                    "type": "Close-Up" if "closeup" in entry.lower() else ("Full-Body" if "full" in entry.lower() else "Medium")
                })
    return sorted(avatars, key=lambda x: (not x["ready"], x["avatar_id"]))


@app.route("/api/system/status", methods=["GET"])
def system_status():
    env_info = ENGINE.validate_environment()
    return jsonify({
        "status": "READY",
        "system_name": "AI Avatar NextGen V2 Studio",
        "port": 8178,
        "runtime": sys.executable,
        "gpu_name": env_info.get("gpu_name", "NVIDIA RTX 5090"),
        "cuda_ready": env_info.get("cuda_available", True),
        "engine_ready": env_info.get("ready", True),
        "available_engines": ["FAST (MuseTalk v1.5 NextGen)", "QUALITY (DiT Generative Performance)"],
        "active_jobs_count": sum(1 for j in JOBS_DB.values() if j.get("status") == "RENDERING"),
        "total_jobs_completed": sum(1 for j in JOBS_DB.values() if j.get("status") == "COMPLETED"),
        "renders_dir": V2_RENDERS_DIR
    })


@app.route("/api/avatars", methods=["GET"])
def list_avatars():
    return jsonify({"avatars": get_available_avatars()})


@app.route("/api/preview/script", methods=["POST"])
def preview_script():
    data = request.json or {}
    script = data.get("script", "")
    plan = DIRECTOR.analyze_script(script)
    return jsonify({
        "overall_sentiment": plan.overall_sentiment,
        "estimated_duration_sec": plan.estimated_duration_sec,
        "total_segments": plan.total_segments,
        "segments": [
            {
                "id": s.segment_id,
                "text": s.text,
                "tone": s.tone,
                "pace": s.pace_rate,
                "pause_ms": s.pause_after_ms,
                "head_motion": s.suggested_head_motion,
                "emphasis": s.emphasis_words
            }
            for s in plan.segments
        ]
    })


@app.route("/api/preview/normalize", methods=["POST"])
def normalize_text():
    data = request.json or {}
    script = data.get("script", "")
    normalized = NORMALIZER.normalize(script)
    return jsonify({
        "original": script,
        "normalized": normalized
    })


@app.route("/api/render", methods=["POST"])
def dispatch_render():
    data = request.json or {}
    avatar_id = data.get("avatar_id", "doTrang_closeup")
    audio_path = data.get("audio_path")
    script = data.get("script")
    preset = data.get("preset", "FAST")
    layout = data.get("layout", "square")
    expressive = data.get("expressive_motion", True)
    smooth_60fps = data.get("smooth_60fps", False)

    # Normalize script if provided
    if script:
        script = NORMALIZER.normalize(script)

    job_id = f"job_v2_{uuid.uuid4().hex[:8]}"

    # Fallback to default benchmark audio if no audio provided
    if not audio_path:
        audio_path = os.path.join(REPO_ROOT, "assets", "demo_elevenlabs_16k.wav")

    out_file = f"{job_id}_{avatar_id}.mp4"
    output_path = os.path.join(V2_RENDERS_DIR, out_file)

    with JOB_LOCK:
        JOBS_DB[job_id] = {
            "job_id": job_id,
            "avatar_id": avatar_id,
            "preset": preset,
            "layout": layout,
            "status": "QUEUED",
            "progress": 0.0,
            "created_at": time.time(),
            "output_path": output_path
        }

    def render_worker():
        with JOB_LOCK:
            JOBS_DB[job_id]["status"] = "VALIDATING"
            JOBS_DB[job_id]["progress"] = 0.05

        make_vertical = (layout == "vertical")

        if preset == "QUALITY":
            # Gated: check if human sign-off has officially unlocked QUALITY mode
            quality_unlocked = os.environ.get("V2_ENABLE_QUALITY_ENGINE", "0") == "1"
            if not quality_unlocked:
                with JOB_LOCK:
                    JOBS_DB[job_id]["status"] = "FAILED"
                    JOBS_DB[job_id]["error"] = (
                        "QUALITY mode (SoulX-FlashHead Pro 1.3B DiT + GFPGAN 50/50) is gated pending formal human acceptance. "
                        "Set V2_ENABLE_QUALITY_ENGINE=1 after approving Mission 05 blind review package."
                    )
                return

            with JOB_LOCK:
                JOBS_DB[job_id]["status"] = "MODEL_LOADING"
                JOBS_DB[job_id]["progress"] = 0.15

            def on_progress(p):
                with JOB_LOCK:
                    if p < 0.70:
                        JOBS_DB[job_id]["status"] = "GENERATING"
                    elif p < 0.90:
                        JOBS_DB[job_id]["status"] = "ENHANCING"
                    else:
                        JOBS_DB[job_id]["status"] = "COMPOSITING"
                    JOBS_DB[job_id]["progress"] = p

            res = QUALITY_GENERATOR.render_quality_video(
                job_id=job_id,
                avatar_id=avatar_id,
                master_audio_path=audio_path,
                final_output_path=output_path,
                make_vertical=make_vertical,
                progress_callback=on_progress
            )
        else:
            with JOB_LOCK:
                JOBS_DB[job_id]["status"] = "GENERATING"
                JOBS_DB[job_id]["progress"] = 0.20

            res = GENERATOR.render_long_video(
                job_id=job_id,
                avatar_id=avatar_id,
                master_audio_path=audio_path,
                final_output_path=output_path,
                expressive=expressive,
                smooth_60fps=smooth_60fps
            )

        with JOB_LOCK:
            if res.get("success"):
                JOBS_DB[job_id]["status"] = "TECHNICAL_QA"
                JOBS_DB[job_id]["progress"] = 0.95
                qc = QC_GATE.verify_video(output_path, audio_path)
                JOBS_DB[job_id]["status"] = "COMPLETED"
                JOBS_DB[job_id]["progress"] = 1.0
                JOBS_DB[job_id]["duration_sec"] = res.get("duration_sec")
                JOBS_DB[job_id]["net_fps"] = res.get("net_fps")
                JOBS_DB[job_id]["qc"] = qc
            else:
                JOBS_DB[job_id]["status"] = "FAILED"
                JOBS_DB[job_id]["error"] = res.get("error", "Unknown render error")

    threading.Thread(target=render_worker, daemon=True).start()

    return jsonify({"job_id": job_id, "status": "QUEUED", "output_path": output_path})


@app.route("/api/render/jobs", methods=["GET"])
def list_jobs():
    with JOB_LOCK:
        return jsonify({"jobs": list(JOBS_DB.values())})


@app.route("/api/render/jobs/<job_id>", methods=["GET"])
def get_job(job_id):
    with JOB_LOCK:
        job = JOBS_DB.get(job_id)
        if not job:
            return jsonify({"error": "Job not found"}), 404
        return jsonify(job)


@app.route("/renders/<path:filename>", methods=["GET"])
def serve_render(filename):
    return send_from_directory(V2_RENDERS_DIR, filename)


HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8">
  <title>AI Avatar Studio V2 — Photorealistic Performance Studio</title>
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    :root {
      --bg: #0f1117;
      --card-bg: #1a1d27;
      --accent: #6366f1;
      --accent-hover: #4f46e5;
      --text: #f3f4f6;
      --muted: #9ca3af;
      --border: #2d3142;
      --success: #10b981;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; }
    body { background-color: var(--bg); color: var(--text); padding: 24px; }
    .header { display: flex; justify-content: space-between; align-items: center; padding-bottom: 20px; border-bottom: 1px solid var(--border); margin-bottom: 24px; }
    .badge { background: #312e81; color: #c7d2fe; padding: 4px 12px; border-radius: 9999px; font-size: 13px; font-weight: 600; }
    .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }
    .card { background: var(--card-bg); border: 1px solid var(--border); border-radius: 12px; padding: 20px; }
    h2 { font-size: 18px; margin-bottom: 16px; color: #fff; display: flex; align-items: center; gap: 8px; }
    label { display: block; font-size: 13px; color: var(--muted); margin-bottom: 6px; font-weight: 500; }
    select, textarea, input { width: 100%; background: #13151f; border: 1px solid var(--border); border-radius: 8px; padding: 10px 14px; color: #fff; font-size: 14px; margin-bottom: 16px; }
    textarea { height: 110px; resize: vertical; }
    .btn { background: var(--accent); color: #fff; border: none; padding: 12px 24px; border-radius: 8px; font-weight: 600; cursor: pointer; transition: 0.2s; width: 100%; font-size: 15px; }
    .btn:hover { background: var(--accent-hover); }
    .preset-selector { display: flex; gap: 12px; margin-bottom: 16px; }
    .preset-btn { flex: 1; padding: 10px; border: 1px solid var(--border); background: #13151f; color: var(--muted); border-radius: 8px; cursor: pointer; text-align: center; font-weight: 600; font-size: 13px; }
    .preset-btn.active { border-color: var(--accent); color: #fff; background: #282b3d; }
    .plan-box { background: #13151f; border: 1px solid var(--border); border-radius: 8px; padding: 12px; font-size: 13px; margin-bottom: 16px; max-height: 140px; overflow-y: auto; }
    .seg-item { padding: 4px 0; border-bottom: 1px solid #1f2333; color: #d1d5db; }
    .status-bar { display: flex; gap: 16px; font-size: 13px; color: var(--muted); margin-top: 12px; }
    .status-val { color: var(--success); font-weight: 600; }
    video { width: 100%; border-radius: 8px; background: #000; border: 1px solid var(--border); }
  </style>
</head>
<body>
  <div class="header">
    <div>
      <h1 style="font-size: 22px; font-weight: 700;">AI Avatar Studio V2</h1>
      <p style="color: var(--muted); font-size: 13px; margin-top: 4px;">Photorealistic Human Performance Studio (RTX 5090 Blackwell Edition)</p>
    </div>
    <div style="display: flex; gap: 10px; align-items: center;">
      <span class="badge">Port 8178</span>
      <span class="badge" style="background: #064e3b; color: #a7f3d0;">RTX 5090 (32GB) Ready</span>
    </div>
  </div>

  <div class="grid">
    <!-- Operator Controls -->
    <div class="card">
      <h2>1. Cấu hình kịch bản & Avatar</h2>
      
      <label>CHỌN MC / AVATAR</label>
      <select id="avatarSelect">
        <option value="doTrang_closeup">Đỗ Trang (Cận Cảnh - 1080p Portrait)</option>
        <option value="mid_4_9">MC Thời Sự Nam (Trung Cảnh - 1080p)</option>
        <option value="doTrang_fullbody">Đỗ Trang (Toàn Thân)</option>
        <option value="full_4_9">MC Nam (Toàn Thân)</option>
      </select>

      <label>KỊCH BẢN TIẾNG VIỆT</label>
      <textarea id="scriptText" placeholder="Nhập kịch bản phát thanh hoặc quảng cáo tiếng Việt...">Chào mừng quý vị đã quay trở lại với AI Avatar NextGen V2! Hôm nay chúng tôi rất vinh dự được giới thiệu phiên bản mới với chất lượng chuyển động khuôn mặt và khẩu hình tự nhiên vượt bậc.</textarea>

      <div style="display: flex; gap: 8px; margin-bottom: 12px;">
        <button type="button" class="btn" style="background: #374151; font-size: 13px; padding: 8px; flex: 1;" onclick="normalizeScript()">✨ Chuẩn hóa tiếng Việt (Số, Ngày, Viết tắt)</button>
        <button type="button" class="btn" style="background: #1f2937; font-size: 13px; padding: 8px; flex: 1;" onclick="analyzeScript()">🎭 Phân tích cảm xúc & Ngắt câu</button>
      </div>

      <div class="plan-box" id="normBox" style="display: none; background: #111827; border-left: 3px solid #10b981; margin-bottom: 12px;"></div>
      <div class="plan-box" id="planBox" style="display: none; margin-bottom: 12px;"></div>

      <label>ĐỊNH DẠNG KHUNG HÌNH (CANVAS LAYOUT)</label>
      <select id="layoutSelect">
        <option value="square">1:1 Vuông Master (1024×1024 — Tối ưu chi tiết khuôn mặt)</option>
        <option value="vertical">9:16 Full-HD Dọc (1080×1920 — Dynamic Ambient Wings cho TikTok/Shorts)</option>
      </select>

      <label>CHẾ ĐỘ KẾT XUẤT (RENDER PRESET)</label>
      <div class="preset-selector">
        <div class="preset-btn active" id="btnFast" onclick="setPreset('FAST')">
          ⚡ FAST (18–25 FPS)<br><span style="font-size: 11px; font-weight: 400;">MuseTalk NextGen</span>
        </div>
        <div class="preset-btn" id="btnQuality" onclick="setPreset('QUALITY')">
          ✨ QUALITY (Cinema)<br><span style="font-size: 11px; font-weight: 400;">Full-Body DiT</span>
        </div>
      </div>

      <div style="display: flex; gap: 16px; margin-bottom: 20px;">
        <label style="display: flex; align-items: center; gap: 8px; cursor: pointer; color: #fff;">
          <input type="checkbox" id="chkExpressive" checked style="width: auto; margin: 0;">
          Cử động đầu 6-DoF biểu cảm
        </label>
        <label style="display: flex; align-items: center; gap: 8px; cursor: pointer; color: #fff;">
          <input type="checkbox" id="chk60fps" checked style="width: auto; margin: 0;">
          Mượt mà 60 FPS Ultra-Smooth
        </label>
      </div>

      <button type="button" class="btn" id="btnRender" onclick="startRender()">🚀 BẮT ĐẦU RENDER VIDEO</button>
    </div>

    <!-- Live Monitor & Output Player -->
    <div class="card">
      <h2>2. Giám sát & Kết quả kết xuất</h2>
      
      <div id="renderStatusBox" style="padding: 12px; background: #13151f; border-radius: 8px; margin-bottom: 16px; border: 1px solid var(--border);">
        <div style="font-weight: 600; color: #fff;" id="statusText">Trạng thái: Sẵn sàng</div>
        <div style="font-size: 12px; color: var(--muted); margin-top: 4px;" id="statusDetail">Chưa có tác vụ nào đang chạy.</div>
      </div>

      <label>VIDEO KẾT XUẤT HOÀN THIỆN</label>
      <video id="player" controls poster="">
        <source src="/renders/bench_TEST_A_NEXTGEN_V2_doTrang_closeup.mp4" type="video/mp4">
        Trình duyệt không hỗ trợ video thẻ.
      </video>

      <div class="status-bar">
        <div>GPU: <span class="status-val">RTX 5090 (32GB)</span></div>
        <div>Độ phân giải: <span class="status-val">1080×1920 Full HD</span></div>
        <div>Tốc độ: <span class="status-val">~20 FPS Realtime</span></div>
      </div>
    </div>
  </div>

  <script>
    let currentPreset = 'FAST';

    function setPreset(p) {
      currentPreset = p;
      document.getElementById('btnFast').classList.toggle('active', p === 'FAST');
      document.getElementById('btnQuality').classList.toggle('active', p === 'QUALITY');
    }

    async function normalizeScript() {
      const script = document.getElementById('scriptText').value;
      const res = await fetch('/api/preview/normalize', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({script})
      });
      const data = await res.json();
      const box = document.getElementById('normBox');
      box.style.display = 'block';
      box.innerHTML = `<strong>Kịch bản chuẩn hóa phát âm:</strong><br><span style="color: #6ee7b7;">${data.normalized}</span>`;
      document.getElementById('scriptText').value = data.normalized;
    }

    async function analyzeScript() {
      const script = document.getElementById('scriptText').value;
      const res = await fetch('/api/preview/script', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({script})
      });
      const data = await res.json();
      const box = document.getElementById('planBox');
      box.style.display = 'block';
      box.innerHTML = `<strong>Phân tích:</strong> ${data.overall_sentiment.toUpperCase()} | Ước tính: ~${data.estimated_duration_sec}s (${data.total_segments} phân đoạn)<br>` +
        data.segments.map(s => `<div class="seg-item">• [${s.tone}] (Nghỉ ${s.pause_ms}ms, Đầu: ${s.head_motion}): ${s.text}</div>`).join('');
    }

    async function startRender() {
      const avatar = document.getElementById('avatarSelect').value;
      const script = document.getElementById('scriptText').value;
      const layout = document.getElementById('layoutSelect').value;
      const expressive = document.getElementById('chkExpressive').checked;
      const smooth60 = document.getElementById('chk60fps').checked;

      document.getElementById('statusText').innerText = 'Đang gửi tác vụ render...';
      document.getElementById('btnRender').disabled = true;

      const res = await fetch('/api/render', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          avatar_id: avatar,
          script: script,
          preset: currentPreset,
          layout: layout,
          expressive_motion: expressive,
          smooth_60fps: smooth60
        })
      });
      const data = await res.json();
      const jobId = data.job_id;

      // Poll status with granular phase display
      const timer = setInterval(async () => {
        const jRes = await fetch(`/api/render/jobs/${jobId}`);
        const jData = await jRes.json();
        document.getElementById('statusText').innerText = `Giai đoạn: [${jData.status}]`;
        document.getElementById('statusDetail').innerText = `Tác vụ: ${jobId} | Tiến độ: ${Math.round(jData.progress * 100)}%`;

        if (jData.status === 'COMPLETED') {
          clearInterval(timer);
          document.getElementById('btnRender').disabled = false;
          document.getElementById('statusText').innerText = `Trạng thái: Hoàn thành!`;
          document.getElementById('statusDetail').innerText = `Hoàn thành! Thời lượng: ${jData.duration_sec}s (${jData.net_fps} FPS)`;
          const player = document.getElementById('player');
          player.src = `/renders/${jobId}_${avatar}.mp4`;
          player.play();
        } else if (jData.status === 'FAILED') {
          clearInterval(timer);
          document.getElementById('btnRender').disabled = false;
          document.getElementById('statusText').innerText = `Trạng thái: Thất bại`;
          document.getElementById('statusDetail').innerText = `Lỗi: ${jData.error}`;
        }
      }, 2000);
    }
  </script>
</body>
</html>
"""


@app.route("/", methods=["GET"])
def index():
    return render_template_string(HTML_TEMPLATE)


if __name__ == "__main__":
    port = int(os.environ.get("STUDIO_PORT", 8178))
    print(f"\n=======================================================")
    print(f"AI AVATAR STUDIO V2 CONTROLLER ACTIVE")
    print(f"Listening on: http://127.0.0.1:{port}")
    print(f"Isolated Output: {V2_RENDERS_DIR}")
    print(f"=======================================================\n")
    app.run(host="127.0.0.1", port=port, debug=False, threaded=True)
