# AI Avatar Studio — Chia sẻ cho cộng sự đáng tin cậy (Trusted Collaborator Sharing)

> **Phiên bản:** V1.2.0 · Tag: `ai-avatar-studio-ui-v1.2.0`
> **Chế độ:** TRUSTED COLLABORATOR — truy cập ĐẦY ĐỦ Studio sau khi đăng nhập.
> Đây KHÔNG phải chế độ pilot người dùng công khai, KHÔNG phải demo hạn chế.

Studio vẫn là **MỘT ứng dụng duy nhất**. Cloudflare Quick Tunnel chỉ là phương tiện
truy cập từ xa — không tách rành ngạch tính năng (local feature set vs remote
feature set). Sau khi đăng nhập, cộng sự dùng Studio giống hệt owner ở localhost.

---

## 1. Tổng quan

| | Owner | Cộng sự |
|---|---|---|
| URL | `http://127.0.0.1:8077` | `https://<random>.trycloudflare.com` |
| Backend | Cùng một Flask controller | Cùng một Flask controller |
| SQLite | `data/studio_runtime/studio.db` | cùng |
| Avatar Library | `data/avatars/` | cùng |
| Hàng đợi render / GPU | cùng workstation | cùng |
| ElevenLabs workspace/quota | cùng key đã cấu hình | cùng |
| Edge TTS | cùng | cùng |
| Lịch sử / Settings | cùng | cùng |

Cộng sự và owner nhìn thấy **cùng** mọi thứ — không tách tài khoản, không tách lịch sử.

---

## 2. Cách dùng (operator)

1. **Double-click** `AI_Avatar_Studio_Share.bat`.
2. Đợi ~10–20 giây. Script sẽ:
   - kiểm tra repo + cloudflared,
   - khởi động Studio nếu chưa chạy (nếu đang chạy thì dùng lại, không dừng),
   - sinh mã truy cập ngẫu nhiên (in-memory, không ghi disk),
   - mở Cloudflare Quick Tunnel,
   - in link + mã truy cập và **copy vào clipboard**.
3. Gửi **link + mã truy cập** cho cộng sự.
4. Cộng sự mở link → nhập mã → dùng đầy đủ Studio.
5. **Ctrl+C** trong cửa sổ launcher (hoặc chạy `AI_Avatar_Studio_Stop_Sharing.bat`)
   để ngừng chia sẻ. URL cũ lập tức không truy cập được.

> Mặc định **AUTH ON** (vì URL trycloudflare là URL Internet công khai).
> Tắt nếu thật sự cần: `AI_Avatar_Studio_Share.bat --no-auth`.

---

## 3. Cộng sự dùng gì

Sau đăng nhập, cộng sự có **đầy đủ** quyền giống owner:

- Tạo video nhanh (Quick Render) · Tạo AI Avatar mới · Thư viện AI Avatar · Lịch sử render · Cài đặt · Trạng thái hệ thống.
- ElevenLabs: chọn/nhập Voice ID, check giọng, preview, **render production dùng cùng quota** đã cấu hình.
- Edge TTS: test miễn phí (không quota).
- Test khẩu hình 10s, render thường, render dài, hàng đợi multi-GPU.
- Tạo Avatar: tải raw source lên (chunked, hỗ trợ >100 MB), phân tích, xác nhận miệng, Use Anyway, Prepare.
- Sample video "Video mẫu tạm thời" (V1.1.6) phát qua HTTPS, seek được.

**Không có** hạn chế nhân tạo: không tắt ElevenLabs, không tắt production render,
không ẩn Settings/History, không ép Edge-only, không cách ly avatar theo user.

---

## 4. Bảo mật (phạm vi hẹp)

Mục tiêu: **ngặn truy cập ngẫu nhiên** từ Internet, KHÔNG phải zero-trust doanh nghiệp.

- **Mã truy cập** sinh bằng `secrets`, giữ **trong RAM** (không ghi disk, §29).
- **Session cookie**: `HttpOnly`, `SameSite=Lax`; `Secure` bật khi origin là HTTPS
  thực (Quick Tunnel chuyển HTTP tới loopback origin nên cookie qua tunnel không
  có cờ Secure — đây là đặc điểm cố hữu của Quick Tunnel, không phải lỗ hổng).
- Session hết hạn khi **restart Studio** (secret_key sinh lại mỗi lần).
- **Owner miễn đăng nhập** khi vào `127.0.0.1` trực tiếp (phân biệt qua header
  `Cf-Connecting-IP`: có = qua tunnel → cần đăng nhập; không có = owner local).
  An toàn vì origin chỉ nghe trên 127.0.0.1 — không ai ngoài truy cập trực tiếp.
- Endpoint admin `/api/share/enable|disable` chỉ owner-direct (loopback, không
  qua tunnel) gọi được → cộng sự không thể tắt/mở gate.
- **Không** trả plaintext API key ElevenLabs về browser; giữ nguyên masking sẵn có.
- **Không** endpoint filesystem tùy ý, giữ path-traversal guard `_within_allowed`.
- **Không** lộ đường dẫn raw-source gốc cho remote (sample ẩn `source_path` qua tunnel).

---

## 5. Upload >100 MB (chunked)

Cloudflare Free proxy giới hạn ~100 MB/request. Upload raw source qua tunnel dùng
**chunked upload**: `POST /api/uploads/init` → lặp `POST /api/uploads/<id>/chunk`
(chunk 16 MiB, dưới ngưỡng Cloudflare) → `POST /api/uploads/<id>/complete` (ghép
nguyên tử + SHA1 vào `data/input/avatar_sources/`), rồi đưa path local cho
**pipeline analyze/prepare hiện có** (không tạo importer thứ hai). UI hiển thị
"ĐANG TẢI VIDEO 43% · Chunk 11/26". Cùng uploader dùng cho cả local và remote.

---

## 6. Media & playback

- Sample MP4, thumbnail, mouth-test MP4, render MP4, preview audio đều phục vụ
  qua HTTP endpoint an toàn (`/assets/...`, `/api/avatars/<id>/thumbnail`,
  `/api/render/jobs/<id>/preview`, …) — **không** để browser mở đường dẫn `D:\`/`C:\`.
- Hỗ trợ **Range/206** cho MP4 → seek bar hoạt động.
- UI dùng **polling** (không SSE) → tương thích Quick Tunnel.

---

## 7. Dừng & lưu ý

- Ctrl+C hoặc `AI_Avatar_Studio_Stop_Sharing.bat` chỉ dừng **cloudflared của phiên
  này** + tắt gate; chỉ dừng Studio nếu **launcher tự khởi động** nó (ghi trong
  `diagnostics/share_runtime.json`). Không bao giờ `taskkill /IM python.exe`.
- `diagnostics/share_runtime.json` chỉ lưu PID/URL/thời gian — **không** lưu mã
  truy cập hay API key.
- **URL đổi mỗi phiên** (Quick Tunnel sinh random subdomain).
- Quick Tunnel dành cho dev/test tạm thời. Muốn URL ổn định lâu dài: dùng
  **Named Cloudflare Tunnel** + hostname tùy chỉnh (sau này).

---

## 8. Kiến trúc

```
Cộng sự (browser) ──HTTPS──> Cloudflare Quick Tunnel ──> 127.0.0.1:8077
                                                              │
                 [ shared access gate (optional, auth ON) ]    │
                                                              ▼
                                              ── MỘT Flask controller ──
                                       (cùng SQLite, avatars, ElevenLabs,
                                        GPU queue, MuseTalk renderer, truth)
                                                              │
Owner (browser) ──HTTP──> 127.0.0.1:8077 ─────────────────────────┘
```

Production truth (`config/render_truth.json`) **không đổi**: MuseTalk v1.5,
gain 1.5, ctx 0, offset −3, 25 FPS, 1080×1920, CUDA Graph ON, WOLA ON,
Coverage Guard ON. Renderer không đổi. Lipsync không đổi.