# MISSION 02 — WEIGHT TRANSFER DIAGNOSTICS & VERIFICATION AUDIT
**Project:** AI Avatar NextGen V2 — Photorealistic Performance Studio  
**Date:** 2026-10-22  
**Target Hardware:** NVIDIA GeForce RTX 5090 Blackwell 32GB (`sm_120`), Intel Core i9-14900KF, 128GB RAM  

---

## 1. Empirical Transfer Method Benchmarking

Comprehensive diagnostic tests were executed across multiple protocol backends and model hubs to isolate the optimal download pipeline:

| Transfer Method | Endpoint / Protocol | Measured Speed | Range Header Honor | Outcome / Status |
| :--- | :--- | :--- | :--- | :--- |
| **Direct Hugging Face (urllib single-thread)** | `huggingface.co/resolve/main` | $65 - 110 \text{ KB/s}$ | Verified (206 Partial Content) | Heavily throttled by single-stream ISP routing |
| **ModelScope API** | `modelscope.cn/api/v1/models` | $65 \text{ KB/s}$ | Timeouts on large chunks | Unstable handshake over SSL |
| **`hf-mirror.com` Reverse Proxy** | `hf-mirror.com` | Redirected | HTTP 308 Permanent Redirect | Redirects back to official Hugging Face CDN |
| **Hugging Face Hub + `hf_transfer`** | Official Hugging Face CDN | **$3.40 - 5.60 \text{ MB/s}$** | **YES (HTTP 206)** | **30x–50x speedup; successfully saturated link** |
| **Direct Chunked HTTP Range Requests** | Official S3/CloudFront CDN | **$\sim 1.0 \text{ MB/s}$** | **YES (HTTP 206)** | **Resumable with byte boundary protection** |

---

## 2. Server Range Request Compliance & Boundary Guard

Every download routine was tested against HTTP `Range` headers:
```http
GET /Soul-AILab/SoulX-FlashHead-1_3B/resolve/main/VAE_Wan/Wan2.1_VAE.pth HTTP/1.1
Host: huggingface.co
Range: bytes=0-1023
```
**Server Response:**
```http
HTTP/1.1 206 Partial Content
Content-Range: bytes 0-1023/507609880
Accept-Ranges: bytes
Content-Length: 1024
```

> [!IMPORTANT]
> **CONCATENATION SAFETY IMPLEMENTED:**  
> The downloader explicitly checks `response.status == 206`. If a mirror or proxy falls back to `200 OK` (ignoring the Range header), the script aborts appending to avoid corrupting partial files with whole-file stream duplication.

---

## 3. Checkpoint Staging & Verification Results

All acquired weights were staged on high-speed NVMe storage (`D:\CongThang_AI_Avatar\staging_weights\`), SHA-256 verified, and copied to production targets:

### 3.1 Acoustic Model: `facebook/wav2vec2-base-960h`
- **Location:** `C:\Users\phuongpn\AI_Avatar_NextGen_V2\weights\wav2vec2-base-960h\`
- **Expected Bytes:** 377,667,514 bytes
- **Actual Bytes on Disk:** **377,667,514 bytes**
- **Expected SHA-256:** `c34f9827b034a1b9141dbf6f652f8a60eda61cdf5771c9e05bfa99033c92cd96`
- **Computed SHA-256:** `C34F9827B034A1B9141DBF6F652F8A60EDA61CDF5771C9E05BFA99033C92CD96`
- **GPU Verification:** Loaded into RTX 5090 Blackwell VRAM via `Wav2Vec2Model.from_pretrained(..., local_files_only=True)`. **PASSED (100% Functional).**

### 3.2 Visual Decoder: Wan 2.1 Causal VAE (`Wan2.1_VAE.pth`)
- **Location:** `C:\Users\phuongpn\AI_Avatar_NextGen_V2\weights\SoulX-FlashHead-1_3B\VAE_Wan\Wan2.1_VAE.pth`
- **Expected Bytes:** 507,609,880 bytes
- **Actual Bytes on Disk:** **507,609,880 bytes**
- **State Dict Integrity:** Verified via `torch.load(..., weights_only=False)` -> **194 layers loaded** (`encoder.conv1.weight`, etc.).
- **GPU Verification:** Instantiated inside `WanVAE` on `cuda:0` in `bfloat16`. Successfully executed 33-frame causal tensor encoding $[1, 3, 33, 512, 512] \to [16, 9, 64, 64]$ and full decoding back to $[1, 3, 33, 512, 512]$. **PASSED (100% Functional).**

### 3.3 Root & Model Configurations
- `config.json` (99 bytes) — **VERIFIED**
- `model_index.json` (77 bytes) — **VERIFIED**
- `Model_Pro/config.json` (353 bytes) — **VERIFIED**

### 3.4 Primary DiT Transformer: `Model_Pro/diffusion_pytorch_model.safetensors`
- **Status:** In Progress / Staging Pending
- **Expected Bytes:** **6,030,864,656 bytes (~5.62 GB)**
- **LFS SHA-256:** `e47e61b9023ea1aac60c0c0fff077289bc6cca443c71907e5a76a411480af250`
- **Time Remaining at ~1.0–3.5 MB/s:** $\sim 28 - 90 \text{ minutes}$.

---

## 4. Operator-Assisted Fast Staging Instructions

For operators wishing to immediately complete staging without waiting for background transfers:
1. Download the verified file via IDM or multi-stream browser from:
   `https://huggingface.co/Soul-AILab/SoulX-FlashHead-1_3B/resolve/main/Model_Pro/diffusion_pytorch_model.safetensors`
2. Place the file at:
   `C:\Users\phuongpn\AI_Avatar_NextGen_V2\weights\SoulX-FlashHead-1_3B\Model_Pro\diffusion_pytorch_model.safetensors`
3. Verify file size is exactly **6,030,864,656 bytes**.
