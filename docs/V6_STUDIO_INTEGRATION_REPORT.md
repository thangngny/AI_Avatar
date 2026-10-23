# V6 STUDIO V2 INTEGRATION & WORKFLOW SPECIFICATION
**AI Avatar NextGen V2 — Photorealistic Production Engineering**  
**Date:** 23 October 2026  
**Auditor:** Principal Generative Video Scientist & Technical Lead  
**Workstation:** NVIDIA GeForce RTX 5090 Blackwell (`sm_120`), Windows 11 Pro  

---

## 1. STUDIO V2 APPLICATION ARCHITECTURE

The AI Avatar Studio V2 controller runs as an isolated microservice on `http://127.0.0.1:8178`:

```
[ Browser Client (http://127.0.0.1:8178) ]
                     |
       +-------------+-------------+
       |                           |
[ REST API / Web UI ]     [ Static Video Streaming ]
(/api/render, /preview)         (/renders/*.mp4)
       |
+------+----------------------------------------------------------+
|                      STUDIO V2 CONTROLLER CORE                  |
+-----------------------------------------------------------------+
| 1. Text Normalization: VietnameseTextNormalizer (Dates, Currency)|
| 2. Pacing & Tone: PerformanceDirector (Prosody & Segments)       |
| 3. Render Dispatcher: Job Queue & Concurrency Lock              |
| 4. Dual Engines:                                                |
|    - FAST: LongVideoGenerator (MuseTalk NextGen, ~22 FPS)       |
|    - QUALITY: QualityVideoGenerator (SoulX DiT 1.3B + GFPGAN)   |
| 5. Layout Engine: Square (1:1) / Vertical 1080x1920 (9:16)      |
| 6. Hardware Muxer: Dual 8th/9th Gen NVENC (CQ=16 Master)        |
| 7. Quality Gate: QualityControlGate (Frame & Audio Sync Verify) |
+-----------------------------------------------------------------+
```

---

## 2. API ENDPOINTS & FUNCTIONAL CAPABILITIES

| Route | HTTP Method | Payload / Arguments | Response / Function |
| :--- | :--- | :--- | :--- |
| `/` | `GET` | None | Web GUI operator console (HTML5 / ES6) |
| `/api/system/status` | `GET` | None | Workstation health, GPU status, active engines |
| `/api/avatars` | `GET` | None | Discovered avatar assets (`doTrang`, `mc_hamai`) |
| `/api/preview/normalize`| `POST` | `{"script": "..."}` | Normalizes raw Vietnamese script into phonetic text |
| `/api/preview/script` | `POST` | `{"script": "..."}` | Segments script and suggests pauses / head motion |
| `/api/render` | `POST` | `{avatar_id, script, audio_path, preset, layout}` | Enqueues background render job |
| `/api/render/jobs/<id>` | `GET` | None | Returns granular job status, phase, and progress |
| `/renders/<filename>` | `GET` | None | Streams rendered MP4 video with range-request support |

---

## 3. RENDER STATE MACHINE PROGRESSION

Jobs transition through a strictly defined state machine, eliminating arbitrary percentage jumps:

```
[ QUEUED ] (0%)
    ↓
[ VALIDATING ] (5%) - Input audio & avatar portrait check
    ↓
[ MODEL_LOADING ] (15%) - DiT 1.3B weights & VAE initialization
    ↓
[ GENERATING ] (15% - 70%) - Chunks 1..N neural diffusion inference
    ↓
[ ENHANCING ] (70% - 90%) - GFPGAN 50/50 linear blending & Lanczos-4 scaling
    ↓
[ COMPOSITING ] (90% - 95%) - Dynamic ambient wings canvas composition (if 9:16)
    ↓
[ TECHNICAL_QA ] (95% - 99%) - Container integrity, duration delta, and audio sync check
    ↓
[ COMPLETED ] (100%) - Atomic manifest written, video ready for playback & export
```

---

## 4. CONDITIONAL SAFETY GATE IMPLEMENTATION

To guarantee that the `QUALITY` engine is never activated prematurely before formal human operator sign-off, `run_studio_v2.py` implements an environment-level conditional lock:

```python
if preset == "QUALITY":
    quality_unlocked = os.environ.get("V2_ENABLE_QUALITY_ENGINE", "0") == "1"
    if not quality_unlocked:
        with JOB_LOCK:
            JOBS_DB[job_id]["status"] = "FAILED"
            JOBS_DB[job_id]["error"] = (
                "QUALITY mode (SoulX-FlashHead Pro 1.3B DiT + GFPGAN 50/50) is gated pending formal human acceptance. "
                "Set V2_ENABLE_QUALITY_ENGINE=1 after approving Mission 05 blind review package."
            )
        return
```

### Unlocking the Quality Gate:
Once the operator reviews the video deliverables and confirms visual quality, the gate is unlocked by:
```powershell
$env:V2_ENABLE_QUALITY_ENGINE = "1"
```
Or by setting `set V2_ENABLE_QUALITY_ENGINE=1` inside [`AI_Avatar_Studio_V2.bat`](file:///C:/Users/phuongpn/AI_Avatar_NextGen_V2/AI_Avatar_Studio_V2.bat).

---

## 5. GATE VERDICT: PASS
The Studio V2 platform is fully integrated, resilient, and responsive on port 8178 with end-to-end Vietnamese script-to-video capabilities.
