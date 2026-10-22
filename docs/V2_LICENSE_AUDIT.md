# V2 INTELLECTUAL PROPERTY & LICENSE AUDIT REPORT
**Date:** 2026-10-22  
**Target:** AI Avatar NextGen V2 System  

---

## 1. Engine & Model License Evaluation

| Component | Upstream Author / Entity | Source Code License | Model Weights License | Commercial Deployment Clearance | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **MuseTalk v1.5** | NeolabAI / Lipku | Apache-2.0 | Open Research | **PERMITTED** | Upstream LiveTalking / MuseTalk code is under Apache-2.0. |
| **InfiniteTalk** | MeiGen-AI | Apache-2.0 | Apache-2.0 | **PERMITTED** | Fully open-source DiT architecture for commercial & research audio-driven video. |
| **EchoMimicV3** | Ant Group (Alipay) | Apache-2.0 | Apache-2.0 | **PERMITTED** | Open model weights released on HuggingFace under Apache-2.0. |
| **SoulX-FlashHead** | Soul-AILab (Soul App) | Apache-2.0 | Apache-2.0 | **PERMITTED** | Open weights released under Apache-2.0. Highly permissive. |
| **LatentSync 1.6** | ByteDance | MIT | **CC-BY-NC 4.0** | **NON-COMMERCIAL ONLY** | Code is MIT, but official ByteDance checkpoints are strictly Non-Commercial. Commercial use requires custom-trained weights or commercial agreement. |
| **Whisper** | OpenAI | MIT | MIT | **PERMITTED** | Feature extraction weights are MIT licensed. |
| **GFPGAN** | Tencent ARC | Apache-2.0 | Non-Commercial / Research | **CAUTION** | Face restoration weights require clean commercial fallback (USM/Lanczos-4 preferred). |

---

## 2. Privacy & Personal Identity Governance

1. **Local Asset Protection:**
   - All human video recordings, voice samples, and face identity latents in `data/avatars/` are private company property.
   - **Zero External Egress:** Under no circumstances are video clips or face latents sent to public web services, third-party APIs, or public repositories.
2. **TTS Service Transmission:**
   - Text scripts sent to ElevenLabs API contain purely editorial presentation text, never personally identifiable biometric face data.
   - EdgeTTS operates over encrypted Microsoft Azure endpoints without persisting user scripts.

---

## 3. Engineering Decision on Licensing

1. **Production Engine Preference:**
   - **InfiniteTalk**, **SoulX-FlashHead**, and **EchoMimicV3** are cleared for production use under Apache-2.0.
   - **LatentSync** will be retained as an experimental benchmark reference due to its CC-BY-NC 4.0 weight restriction.
2. **Zero Third-Party Data Leakage:**
   - All benchmark datasets and outputs remain strictly on local storage (`D:\CongThang_AI_Avatar\v2_renders`).
