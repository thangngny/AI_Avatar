# AI Avatar Studio — Chia sẻ cho cộng sự đáng tin cậy (Trusted Collaborator Sharing)

> **Phiên bản:** V1.2.2 · Tag: `ai-avatar-studio-ui-v1.2.2`
> **Chế độ:** TRUSTED COLLABORATOR — LINK ONLY. Mở link là dùng được Studio đầy đủ.
> Đây KHÔNG phải chế độ pilot người dùng công khai, KHÔNG phải demo hạn chế.

Studio vẫn là **MỘT ứng dụng duy nhất**. Cloudflare Quick Tunnel chỉ là phương tiện
truy cập từ xa — không tách rành ngạch tính năng (local feature set vs remote
feature set). Cộng sự mở link và dùng Studio giống hệt owner ở localhost.

> **Không có mã truy cập trong chế độ chia sẻ mặc định.** Bất kỳ ai có link
> đang hoạt động đều có thể dùng Studio. Đây là quyết định của owner (TRUSTED
> COLLABORATOR MODE); URL rotation mỗi phiên là ranh giới thực tế duy nhất.

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

## 2. Cách dùng (operator) — LINK ONLY

1. **Double-click** `AI_Avatar_Studio_Share.bat`.
2. Đợi ~10–20 giây. Script sẽ:
   - kiểm tra repo + cloudflared,
   - khởi động Studio nếu chưa chạy (nếu đang chạy thì dùng lại, không dừng),
   - mở Cloudflare Quick Tunnel,
   - in **PUBLIC LINK** và **copy link vào clipboard** (không có mã truy cập).
3. Gửi **PUBLIC LINK** cho cộng sự.
4. Cộng sự mở link → Studio mở ngay, dùng đầy đủ. **Không đăng nhập, không mã.**
5. **Ctrl+C** (hoặc chạy `AI_Avatar_Studio_Stop_Sharing.bat`) để ngừng chia sẻ.
   URL cũ lập tức không truy cập được.

> Mặc định: **LINK ONLY** (không mã truy cập, không login). Bất kỳ ai có link đều
> dùng được Studio trong thời gian đang chia sẻ.
>
> Nếu muốn bật lại cổng mã truy cập (legacy, tùy chọn): `AI_Avatar_Studio_Share.bat --auth`.

---

## 3. Cộng sự dùng gì

Sau khi mở link (không đăng nhập), cộng sự có **đầy đủ** quyền giống owner:

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

Mục tiêu: chia sẻ tạm thời cho cộng sự đáng tin cậy. **Không** phải zero-trust.

- **LINK ONLY (mặc định): không có mã truy cập, không login.** Bất kỳ ai có link
  đang hoạt động đều dùng được Studio. Owner chấp nhận điều này. URL đổi mỗi
  phiên (Quick Tunnel random subdomain) là ranh giới thực tế chính.
- Cổng mã truy cập (legacy, tùy chọn `--auth`) vẫn còn nếu owner muốn khép kín:
  mã sinh bằng `secrets`, giữ trong RAM, session cookie `Secure; HttpOnly;
  SameSite=Lax` qua tunnel nhờ `ProxyFix` (X-Forwarded-Proto). Mặc định KHÔNG bật.
- **Không** trả plaintext API key ElevenLabs về browser; giữ nguyên masking sẵn có.
- **Không** endpoint filesystem tùy ý, giữ path-traversal guard `_within_allowed`.
- **Không** lộ đường dẫn raw-source gốc cho remote (sample ẩn `source_path` qua tunnel).
- `ProxyFix` (1 hop) vẫn giữ cho hành vi HTTPS bên ngoài đúng đắn
  (`request.is_secure`, scheme, host). An toàn vì origin chỉ bind 127.0.0.1.

---

## 5. Upload >100 MB (chunked)

Cloudflare Free proxy giới hạn ~100 MB/request. Upload raw source qua tunnel dùng
**chunked upload**: `POST /api/uploads/init` → lặp `POST /api/uploads/<id>/chunk`
(chunk transport-aware: 2 MiB qua tunnel để dưới timeout ~100s 524, 16 MiB local)
→ `POST /api/uploads/<id>/complete` (ghép nguyên tử + SHA1 vào
`data/input/avatar_sources/`), rồi đưa path local cho **pipeline analyze/prepare
hiện có** (không tạo importer thứ hai). UI hiển thị "ĐANG TẢI VIDEO 43% · Chunk
11/26", retry từng chunk lỗi. Cùng uploader dùng cho cả local và remote.

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
  này** (+ tắt gate nếu đang ở chế độ `--auth`); chỉ dừng Studio nếu **launcher
  tự khởi động** nó (ghi trong `diagnostics/share_runtime.json`). Không bao giờ
  `taskkill /IM python.exe`.
- `diagnostics/share_runtime.json` chỉ lưu PID/URL/thời gian — **không** lưu mã
  truy cập hay API key (mặc định không có mã nào cả).
- **URL đổi mỗi phiên** (Quick Tunnel sinh random subdomain).
- Quick Tunnel dành cho dev/test tạm thời. Muốn URL ổn định lâu dài: dùng
  **Named Cloudflare Tunnel** + hostname tùy chỉnh (sau này).

---

## 8. Kiến trúc

```
Cộng sự (browser) ──HTTPS──> Cloudflare Quick Tunnel ──> 127.0.0.1:8077
                                                              │
        [ access gate: OFF mặc định (LINK ONLY) | ON nếu --auth ]
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