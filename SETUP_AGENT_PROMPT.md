# PROMPT HƯỚNG DẪN DÀNH CHO CODING AGENT (SETUP TRỌN GÓI MÁY MỚI RTX 5090)

> **Dành cho Agent:** Bạn đang nhận nhiệm vụ thiết lập trọn gói (turnkey setup) dự án **AI Avatar Studio** trên máy trạm mới (trang bị GPU NVIDIA RTX 5090 / 4090 / 3090, Windows 11).
> Dự án này là hệ thống tạo video AI Avatar chuyên nghiệp, tích hợp MuseTalk v1.5, ElevenLabs/Edge-TTS, và bộ điều khiển giao diện web nội bộ (port 8077).

---

## MỤC TIÊU CỦA BẠN (AGENT GOAL)
Thực hiện toàn bộ quy trình thiết lập từ A đến Z bằng terminal, đảm bảo hệ thống đạt trạng thái **100% READY** và người dùng chỉ cần nhấp đúp vào biểu tượng `AI_Avatar_Studio.exe` ngoài Desktop để sử dụng.

---

## QUY TRÌNH THỰC HIỆN TỪNG BƯỚC (STEP-BY-STEP EXECUTION)

### Bước 1: Kiểm tra Python hệ thống
Chạy lệnh kiểm tra phiên bản Python trên máy (yêu cầu Python 3.10 hoặc 3.11):
```powershell
python --version
```
*(Nếu chưa có Python, thông báo người dùng cài đặt Python 3.10+ hoặc dùng winget: `winget install Python.Python.3.10`)*

### Bước 2: Chạy công cụ tự động hóa thiết lập (One-Shot Setup)
Trong thư mục gốc của repository (`AI_avatar`), chạy lệnh:
```powershell
python tools/setup_new_machine.py
```
**Tệp này sẽ tự động:**
1. Khởi tạo môi trường ảo tại `..\runtime\venv`.
2. Tải và cài đặt PyTorch CUDA tương thích với kiến trúc Blackwell của RTX 5090 (cu124/cu126/cu128).
3. Cài đặt toàn bộ các thư viện AI (diffusers, transformers, accelerate, edge-tts, soundfile, playwright, v.v.).
4. Cài đặt trình duyệt Chromium cho Playwright.
5. Kiểm tra sự tồn tại của FFmpeg trong PATH.
6. Biên dịch tệp `AI_Avatar_Studio.exe` bằng `csc.exe` (trình biên dịch có sẵn của Windows).
7. Tự động tạo biểu tượng Shortcut ngoài màn hình Desktop cho người dùng.

### Bước 3: Kiểm tra các tệp Models & Dữ liệu Avatar (Weights & Assets)
Kiểm tra xem thư mục `models/` và `data/avatars/` đã có dữ liệu chưa:
```powershell
Get-ChildItem -Path models
Get-ChildItem -Path data/avatars
```
* **Nếu chưa có:** Hướng dẫn người dùng copy thư mục `models` (~8.6 GB) và `data/avatars` (~12.9 GB) từ máy cũ sang (qua LocalSend hoặc mạng LAN).

### Bước 4: Chạy kiểm định tiền kiểm (Preflight Verification)
Chạy kịch bản chẩn đoán của hệ thống:
```powershell
..\runtime\venv\Scripts\python.exe tools/verify_runtime.py
```
* **Kỳ vọng:** Kết quả trả về `STATUS: READY`, nhận diện chính xác card RTX 5090 và CUDA.

### Bước 5: Chạy toàn bộ bài kiểm tra hồi quy (Regression Tests)
Đảm bảo mã nguồn hoàn hảo và không có bất kỳ lỗi nào:
```powershell
..\runtime\venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
```
* **Kỳ vọng:** Toàn bộ 190 tests đều báo `OK`.

### Bước 6: Khởi chạy thử nghiệm và nghiệm thu
1. Khởi động máy chủ dưới nền:
   ```powershell
   Start-Process -FilePath "..\runtime\venv\Scripts\python.exe" -ArgumentList "run_studio.py --no-browser --port 8077"
   ```
2. Kiểm tra phản hồi API:
   ```powershell
   Invoke-RestMethod -Uri "http://127.0.0.1:8077/api/system/status"
   ```
3. Sau khi xác nhận thành công, tắt tiến trình thử nghiệm và thông báo cho người dùng biết hệ thống đã sẵn sàng 100%.

---

## TIÊU CHÍ HOÀN THÀNH (DEFINITION OF DONE)
1. Môi trường `runtime\venv` có PyTorch chạy nhận GPU RTX 5090.
2. FFmpeg hoạt động trong PATH.
3. Thư mục `models` và `data/avatars` đầy đủ.
4. Tệp `AI_Avatar_Studio.exe` hoạt động và có biểu tượng ngoài màn hình Desktop.
5. Báo cáo ngắn gọn cho người dùng biết hệ thống đã hoàn tất và hướng dẫn họ bấm vào icon Desktop để bắt đầu tạo video.
