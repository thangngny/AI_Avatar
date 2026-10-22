# V2 SYSTEM ARCHITECTURE SPECIFICATION
**Project:** AI Avatar NextGen V2 — Photorealistic Human Performance Studio  
**Date:** 2026-10-22  
**Target Root:** `C:\Users\phuongpn\AI_Avatar_NextGen_V2`  

---

## 1. High-Level Modular Architecture

```
                  ┌────────────────────────────────────────┐
                  │          V2 OPERATOR STUDIO            │
                  │   Web UI: http://127.0.0.1:8178        │
                  │   Controller: Flask (Port 8178/8177)   │
                  └──────────────────┬─────────────────────┘
                                     │ JSON Request
                                     ▼
                  ┌────────────────────────────────────────┐
                  │      V2 ENGINE ORCHESTRATOR            │
                  │   (Single-GPU Job Queue & Scheduling)  │
                  └──────┬───────────────────────────┬─────┘
                         │                           │
          ┌──────────────┴──────────┐   ┌────────────┴─────────────┐
          │   FAST ENGINE ADAPTER   │   │  QUALITY ENGINE ADAPTER  │
          │   (MuseTalk v1.5 NextGen│   │  (Diffusion-based Full   │
          │    Realtime Compositor) │   │   Head/Upper-Body Gen)   │
          └──────────────┬──────────┘   └────────────┬─────────────┘
                         │                           │
                         └──────────────┬────────────┘
                                        │
                                        ▼
                  ┌────────────────────────────────────────┐
                  │       V2 PERFORMANCE DIRECTOR          │
                  │ - Vietnamese Prosody & Phoneme Parsing │
                  │ - Audio-Driven Micro-Expressions       │
                  │ - Gaze & 3D Head Trajectory Planner   │
                  └─────────────────────┬──────────────────┘
                                        │
                                        ▼
                  ┌────────────────────────────────────────┐
                  │       POST-PROCESSING & EXPORT         │
                  │ - Bilateral Edge-Preserving Sharpening │
                  │ - Dual NVENC Gen 9 Hardware Encoder    │
                  │ - Isolated Output: D:\...\v2_renders   │
                  └────────────────────────────────────────┘
```

---

## 2. Directory & Module Organization

```
AI_Avatar_NextGen_V2/
├── app/                        # Controller & Web API
│   ├── api/                    # REST Endpoints (status, avatars, render, preview)
│   ├── core/                   # Single-instance guard, config loader, boot verification
│   └── studio/                 # Frontend assets, templates, static files
├── engines/                    # Unified Video Engine Abstraction
│   ├── base.py                 # Abstract BaseEngine interface
│   ├── musetalk_engine.py      # High-speed baseline (MuseTalk v1.5 FP16)
│   ├── latentsync_engine.py    # Diffusion lip-sync adapter (512x512)
│   ├── echomimic_engine.py     # Upper-body expressive audio animation adapter
│   ├── soulx_engine.py         # SoulX-FlashHead streaming/batch adapter
│   └── infinitetalk_engine.py  # Video-to-video audio conditioning adapter
├── audio/                      # Audio Processing & Voice Pipeline
│   ├── tts_service.py          # ElevenLabs / EdgeTTS multi-provider abstraction
│   ├── phoneme_aligner.py      # Vietnamese phonetic timing & labial phoneme detector
│   └── whisper_features.py     # Whisper audio feature extraction & WOLA chunking
├── quality/                    # Automated Quality Control & Post-Processing
│   ├── face_metrics.py         # SyncNet confidence, identity drift, blink detector
│   ├── blending.py             # Reinhard LAB color transfer, Lanczos-4, Gaussian feather
│   └── temporal_smoother.py    # Chunk seam blender, jitter suppressor
├── benchmarks/                 # Automated Benchmark Lab
│   ├── test_dataset/           # Standardized Vietnamese test audio & scripts
│   ├── run_benchmark.py        # Automated multi-engine evaluator
│   └── reports/                # Benchmark metrics, CSV, charts, side-by-side videos
├── configs/                    # Isolated Configuration
│   ├── studio_v2.json          # Studio server ports (8178/8177) & paths
│   ├── render_presets.json     # FAST, QUALITY, CINEMA preset definitions
│   └── engines/                # Per-engine hyperparameter configs
├── docs/                       # Engineering specifications & audit records
├── models -> C:\...\AI_Avatar\models         (Read-only NTFS Junction)
├── data/avatars -> C:\...\AI_Avatar\data\avatars (Read-only NTFS Junction)
└── v2_renders -> D:\CongThang_AI_Avatar\v2_renders (Target Output Directory)
```

---

## 3. Core Engine Interface (`engines/base.py`)

Every candidate engine adheres to a uniform lifecycle contract:

```python
class BaseVideoEngine(ABC):
    @abstractmethod
    def validate_environment(self) -> EngineHealth:
        """Check CUDA compatibility, weights existence, and VRAM headroom."""
        pass

    @abstractmethod
    def estimate_resources(self, request: RenderRequest) -> ResourceEstimate:
        """Estimate peak VRAM (GB) and expected render duration."""
        pass

    @abstractmethod
    def load_model(self, device: torch.device) -> None:
        """Load weights into GPU VRAM in optimal precision (FP16/BF16)."""
        pass

    @abstractmethod
    def render(self, request: RenderRequest, progress_callback: Callable) -> RenderResult:
        """Execute inference and export playable MP4."""
        pass

    @abstractmethod
    def release_resources(self) -> None:
        """Explicitly purge model weights from VRAM and call torch.cuda.empty_cache()."""
        pass
```

---

## 4. Multi-Engine Strategy: FAST vs. QUALITY

| Mode | Target Engine | Native Resolution | Frame Rate | Estimated Throughput | Focus |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **FAST (Baseline)** | MuseTalk v1.5 NextGen | 256×256 face on 1080p source | 25 / 60 FPS | **18 - 25 FPS** (Realtime) | Rapid drafting, low latency |
| **QUALITY (Cinema)** | Advanced Generative Diffusion (Candidate A/B/C) | 512×512 or 768×768 native | 25 FPS | **2 - 8 FPS** | Complete facial expression, micro-emotions, photorealism |

---

## 5. Security & Isolation Guarantee
1. **Zero Production Mutation:** V2 runs in an isolated directory tree.
2. **Dedicated Virtualenv:** `C:\Users\phuongpn\runtime_avatar_v2` is completely separate from `runtime_nextgen`.
3. **Dedicated Output Workspace:** Output files write exclusively to `D:\CongThang_AI_Avatar\v2_renders`.
4. **Port Separation:** V2 binds to `8178` (Web UI) and `8177` (API/Internal), preventing any conflict with V1's `8078/8077`.
