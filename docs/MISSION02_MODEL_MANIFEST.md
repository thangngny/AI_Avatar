# MISSION 02 — OFFICIAL MODEL MANIFEST: SOULX-FLASHHEAD PRO
**Project:** AI Avatar NextGen V2 — Photorealistic Performance Studio  
**Date:** 2026-10-22  
**Target Hardware:** NVIDIA GeForce RTX 5090 Blackwell 32GB (`sm_120`), Intel Core i9-14900KF, 128GB RAM  
**Target Architecture:** SoulX-FlashHead Pro (Oracle-Guided Streaming DiT)  

---

## 1. Executive Model & Architecture Specification

SoulX-FlashHead is a 1.3B-parameter audio-driven video diffusion transformer (DiT) developed by Soul-AILab, built upon Alibaba's Wan2.1 diffusion architecture and optimized for real-time streaming portrait generation.

### 1.1 Pro vs. Lite Checkpoint Distinction

| Feature / Dimension | **SoulX-FlashHead Model_Pro (Target)** | SoulX-FlashHead Model_Lite |
| :--- | :--- | :--- |
| **Backbone Weight File** | `Model_Pro/diffusion_pytorch_model.safetensors` | `Model_Lite/diffusion_pytorch_model.safetensors` |
| **Backbone Exact Size** | **6,030,864,656 bytes (~5.62 GB)** | 6,107,542,048 bytes (~5.69 GB) |
| **VAE Dependency** | **`VAE_Wan/Wan2.1_VAE.pth` (Wan 2.1 VAE)** | `VAE_LTX/diffusion_pytorch_model.safetensors` (LTX-Video 0.9 VAE) |
| **VAE File Size** | **507,609,880 bytes (~484 MB)** | 1,676,798,532 bytes (~1.56 GB) |
| **Visual Reconstruction** | **Significantly higher texture, eye and teeth fidelity** | Lower latent reconstruction detail |
| **Audio Chunk Stride** | **28 frames per chunk (33 frames first chunk)** | 24 frames per chunk (33 frames first chunk) |
| **Sampling Steps** | 4 steps (Distilled DiT) | 4 steps (Distilled DiT) |
| **Target Resolution** | $512 \times 512$ native portrait patch | $512 \times 512$ native portrait patch |

---

## 2. Comprehensive Licensing Audit

Official verification conducted against `Soul-AILab/SoulX-FlashHead` GitHub and Hugging Face model cards:

| Component | Source Origin | License | Commercial Usage |
| :--- | :--- | :--- | :--- |
| **SoulX Codebase** | `github.com/Soul-AILab/SoulX-FlashHead` | **Apache-2.0** | **PERMITTED** |
| **Model_Pro DiT Weights** | `Soul-AILab/SoulX-FlashHead-1_3B` (`Model_Pro/`) | **Apache-2.0** | **PERMITTED** |
| **Wan2.1 VAE Weights** | `Soul-AILab/SoulX-FlashHead-1_3B` (`VAE_Wan/`) | **Apache-2.0** | **PERMITTED** |
| **Wav2Vec2 Audio Encoder** | `facebook/wav2vec2-base-960h` | **Apache-2.0** | **PERMITTED** |
| *(Avoided) Model_Lite VAE* | `Soul-AILab/SoulX-FlashHead-1_3B` (`VAE_LTX/`) | Open-RAIL-M | Restricted by Open-RAIL-M |

> [!NOTE]
> **LEGAL AUDIT CONCLUSION:**  
> When deploying **Model_Pro**, every single sub-component (DiT weights, Wan 2.1 VAE, Wav2Vec2, and execution code) operates under the **Apache-2.0 license**. The entire inference pipeline is 100% cleared for commercial deployment without Open-RAIL-M contamination.

---

## 3. Exact File Inventory & Target Destination Paths

Repository Revision: `5fbd2e44ba08ab2deb28bd55cff2c15523e51ba5`

### 3.1 Model_Pro Core Weights
**Local Destination Root:** `C:\Users\phuongpn\AI_Avatar_NextGen_V2\weights\SoulX-FlashHead-1_3B\`

| Relative Subpath | Exact Expected Bytes | LFS SHA-256 Hash | Purpose |
| :--- | :--- | :--- | :--- |
| `config.json` | 99 | `75ecfcb904b614fd12edeaa66bcddbcbc425b043` | Root configuration |
| `model_index.json` | 77 | `32dfa9a8714bacb4779761b00b41f3441a23cbb1` | Pipeline index |
| `Model_Pro/config.json` | 353 | `24379b09c3399c1fbb4932548c04003f8f560442` | DiT Transformer Config |
| `Model_Pro/diffusion_pytorch_model.safetensors` | **6,030,864,656** | `e47e61b9023ea1aac60c0c0fff077289bc6cca443c71907e5a76a411480af250` | Primary 1.3B DiT Weights |
| `VAE_Wan/Wan2.1_VAE.pth` | **507,609,880** | `38071ab59bd94681c686fa51d75a1968f64e470262043be31f7a094e442fd981` | 3D Causal Wan2.1 VAE |

### 3.2 Acoustic Feature Extractor (Wav2Vec2)
**Local Destination Root:** `C:\Users\phuongpn\AI_Avatar_NextGen_V2\weights\wav2vec2-base-960h\`  
**Source Repository:** `facebook/wav2vec2-base-960h`

| Relative Subpath | Exact Expected Bytes | LFS SHA-256 Hash | Purpose |
| :--- | :--- | :--- | :--- |
| `config.json` | 1,596 | `8ca9cc7496e145e37d09cec17d0c3bf9b8523c8e` | Audio model configuration |
| `preprocessor_config.json` | 159 | `3f24dc078fcba55ee1d417a413847ead40c093a3` | Feature extractor config |
| `feature_extractor_config.json` | 158 | `52fdd74dc06f40033506e402269fbde5e7adc21d` | Tokenizer/feature mapping |
| `pytorch_model.bin` | **377,667,514** | `c34f9827b034a1b9141dbf6f652f8a60eda61cdf5771c9e05bfa99033c92cd96` | PyTorch Wav2Vec2 weights |

---

## 4. Execution Call Signature & Parameters

Inference command validated against `generate_video.py` on single RTX 5090 (`sm_120`):

```bash
python generate_video.py \
    --ckpt_dir C:\Users\phuongpn\AI_Avatar_NextGen_V2\weights\SoulX-FlashHead-1_3B \
    --wav2vec_dir C:\Users\phuongpn\AI_Avatar_NextGen_V2\weights\wav2vec2-base-960h \
    --model_type pro \
    --cond_image <path_to_authorized_mc_frame.png> \
    --audio_path <path_to_vietnamese_speech.wav> \
    --audio_encode_mode stream \
    --use_face_crop False \
    --save_file <output_path.mp4>
```

- Native Video Resolution: $512 \times 512$
- Target Frame Rate: $25.0 \text{ FPS}$
- Sampling Steps: 4 steps
- Expected VRAM Allocation: $\sim 13.5 \text{ GB}$ (well within the RTX 5090 32GB limit)
