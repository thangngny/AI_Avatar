# V2 DEPLOYMENT & OPERATOR GUIDE
**Project:** AI Avatar NextGen V2 — Photorealistic Human Performance Studio  

---

## 1. Quick Start for Operators

### Launching the Studio:
Double-click:
```bat
C:\Users\phuongpn\AI_Avatar_NextGen_V2\AI_Avatar_Studio_V2.bat
```
This automatically starts the V2 controller and opens your web browser at:
```
http://127.0.0.1:8178
```

---

## 2. Operator Workflow in UI

1. **Step 1 — Choose MC / Avatar:**  
   Select from the pre-verified avatars:
   - `doTrang_closeup` (High-detail 1080p close-up)
   - `mid_4_9` (Professional male broadcast medium shot)
   - `doTrang_fullbody` (Full presentation framing)
2. **Step 2 — Enter Vietnamese Script:**  
   Paste or type your editorial script.
3. **Step 3 — Performance Director Analysis:**  
   Click `Phân tích cảm xúc & Ngắt câu` to analyze speech pace, emphasis tokens, and bilateral lip closure pauses.
4. **Step 4 — Select Render Preset:**  
   - **FAST (18–25 FPS):** Realtime high-speed broadcast pipeline for rapid drafting.
   - **QUALITY (Cinema):** High-fidelity generative upper-body & facial micro-mimicry.
5. **Step 5 — Render & Preview:**  
   Click `Bắt đầu Render Video`. Monitor real-time progress, and immediately play or download the finished 1080p MP4.

---

## 3. CLI Direct Execution

To render via command line without opening the web browser:
```powershell
C:\Users\phuongpn\runtime_avatar_v2\Scripts\python.exe C:\Users\phuongpn\AI_Avatar_NextGen_V2\generate_video_from_script.py `
  --avatar_id doTrang_closeup `
  --audio C:\Users\phuongpn\AI_Avatar_NextGen_V2\assets\master_60s_vietnamese.wav `
  --output D:\CongThang_AI_Avatar\v2_renders\output_cli_broadcast.mp4 `
  --batch_size 32 `
  --expressive_motion `
  --smooth_60fps
```
