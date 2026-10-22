# V2 ADVANCED AUDIO-DRIVEN VIDEO GENERATIVE MODEL RESEARCH MATRIX

| Attribute | Candidate A: InfiniteTalk | Candidate B: EchoMimicV3-Flash | Candidate C: SoulX-FlashHead | Candidate D: LatentSync 1.6 | Candidate E: Wan2.2-Animate | Baseline: MuseTalk v1.5 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Organization** | MeiGen-AI | Ant Group (Alipay) | Soul-AILab (Soul App) | ByteDance | Wan-Video | NeolabAI / Upstream |
| **Official Repository** | `github.com/MeiGen-AI/InfiniteTalk` | `github.com/antgroup/echomimic_v3` | `github.com/Soul-AILab/SoulX-FlashHead` | `github.com/bytedance/LatentSync` | `github.com/Wan-Video/Wan2.2` | In-tree baseline |
| **Paper Title** | *InfiniteTalk: Continuous Audio-Driven Talking Video Synthesis* | *EchoMimicV3: Towards Unified Multi-Modal Human Animation* | *SoulX-FlashHead: Unified 1.3B Real-time Streaming Portrait* | *LatentSync: Audio Conditioned Latent Diffusion for Lip Sync* | *Wan2.2: Comprehensive Video Diffusion Suite* | *MuseTalk: Real-Time High Quality Lip-Sync* |
| **Model Size / Backbone** | Sparse Video Transformer / DiT | 1.3B Parameter Multi-Modal DiT | 1.3B Parameter Streaming DiT | SD 1.5 U-Net (860M) | 14B Video DiT | U-Net (~400M) + SD VAE |
| **Code License** | Apache 2.0 | Apache 2.0 | Apache 2.0 | MIT | Apache 2.0 | Apache 2.0 |
| **Weights License** | Open Research / Apache 2.0 | Open weights / Apache 2.0 | Open weights / Apache 2.0 | **CC-BY-NC 4.0 (Non-commercial)** | Open weights | Open research |
| **Commercial Use** | Permitted | Permitted | Permitted | **Restricted (Requires ByteDance License)** | Permitted | Permitted |
| **Target Python / Torch** | Python 3.10+, PyTorch 2.4+ | Python 3.10+, PyTorch 2.4+ | Python 3.10+, PyTorch 2.4+ | Python 3.10+, PyTorch 2.1+ | Python 3.10+, PyTorch 2.5+ | Python 3.11, PyTorch 2.7 |
| **Blackwell (sm_120) Compatibility** | Supported (PyTorch 2.7.0+cu128) | Supported (Standard PyTorch Ops) | Supported (Standard Attention/SDPA) | Supported (diffusers U-Net) | Supported (BF16 native) | Fully verified (13-20 FPS) |
| **VRAM Footprint** | ~14 - 18 GB (FP16/BF16) | ~12 GB (Low-VRAM Flash mode) | ~8 - 14 GB (Lite/Pro modes) | ~6.5 - 8.5 GB | >24 GB | ~4.5 GB |
| **Native Generation Shape** | 480p / 720p Full Frame | 768×768 Upper Body | 512×512 / 768×768 Portrait | 512×512 Face Patch | 720p / 1080p | 256×256 Mouth Patch |
| **Input Modality** | Video + Audio OR Image + Audio | Image/Video + Audio + Text | Image/Video + Audio | Video + Audio | Video + Driving Video | Video Frames + Audio |
| **Upper-Body & Gesture Motion** | **YES (Full Upper-Body Alignment)** | **YES (Gestures, Head, Expressions)** | **YES (Head, Gaze, Micro-Expressions)** | NO (Mouth/Jaw diffusion only) | YES (Actor-driven only) | NO (2D Affine Neck Warp only) |
| **Facial Affect (Eyes, Brow)** | **Dynamic & Audio-Correlated** | **Dynamic & Multi-Modal** | **Dynamic & Natural** | Static (Matches Source Video) | Driven by Actor | Static (From Source Video) |
| **Long-Sequence Architecture** | Streaming Temporal Memory Window | Long Video CFG + NDPO | Temporal Audio Context Cache | Chunked Sliding Window | Video Slicing | Cyclic Slice `[325:525]` |
| **Integration Complexity** | Moderate (Requires custom DiT loader) | Moderate-High (Diffusers/1.3B pipeline) | Moderate (Clean inference script) | Low-Moderate (Diffusers based) | High (Heavy multi-node model) | Native |
| **Current Readiness** | Research Complete | Research Complete | Research Complete | SyncNet Checkpoint present | Research Complete | Production Baseline Verified |
| **Engineering Recommendation** | **TOP CANDIDATE FOR NATURAL GESTURE & EXPRESSION** | **STRONG ALTERNATIVE FOR FLASH SPEED** | **PRIMARY STREAMING CANDIDATE** | **QUICK DROP-IN FOR LIP FIDELITY** | Secondary / Defer | Retain as FAST preset |
