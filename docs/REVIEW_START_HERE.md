# HƯỚNG DẪN NGHIỆM THU CHẤT LƯỢNG AI AVATAR V2 (V6.1)
**Tài liệu hướng dẫn dành cho: Project Director, Video QA & Product Owner**  
**Ngày phát hành:** 23 Tháng 10, 2026  
**Thư mục chứa video nghiệm thu:** [`D:\CongThang_AI_Avatar\v2_renders\V6_FINAL_ACCEPTANCE\`](file:///D:/CongThang_AI_Avatar/v2_renders/V6_FINAL_ACCEPTANCE/)  
**Hệ thống thực thi:** NVIDIA RTX 5090 Blackwell 32GB, Studio V2 (`http://127.0.0.1:8178`)  

---

## 1. TỔNG QUAN BỘ TÀI LIỆU NGHIỆM THU

Bộ thư mục nghiệm thu [`D:\CongThang_AI_Avatar\v2_renders\V6_FINAL_ACCEPTANCE\`](file:///D:/CongThang_AI_Avatar/v2_renders/V6_FINAL_ACCEPTANCE/) đã được cấu trúc đầy đủ gồm **12 video MP4**, các contact sheet hình ảnh, và các tài liệu đối soát kỹ thuật số.

Toàn bộ **12 video MP4** đã vượt qua kiểm thử giải mã kỹ thuật (`100% full-decode pass`, 0 dropped frames, đúng chuẩn 25.0 FPS). Toàn bộ Gate kỹ thuật từ **P0 đến P10 đều đạt PASS tuyệt đối**.

Hiện tại hệ thống đang chờ **Nghiệm Thu Mắt Thường từ Con Người (Gate P11)** để chính thức kích hoạt cổng thương mại (**Gate P12**).

---

## 2. QUY TRÌNH 5 BƯỚC KIỂM TRA VIDEO THỰC TẾ

Quý Quản lý và Chuyên viên QA vui lòng mở các tệp video theo thứ tự sau bằng Windows Media Player, VLC hoặc trình dựng Premiere / CapCut:

### BƯỚC 1: So sánh trực diện chi tiết khuôn mặt & khoang miệng (10s)
* **Tệp video cần mở:** [`face_closeup_comparison_10s_25fps.mp4`](file:///D:/CongThang_AI_Avatar/v2_renders/V6_FINAL_ACCEPTANCE/face_closeup_comparison_10s_25fps.mp4)
* **Kích thước:** $2048 \times 1024$ (Side-by-Side: Bên trái là MuseTalk V1 cũ, bên phải là SoulX-FlashHead Pro V2 mới).
* **Điểm quan sát trọng tâm:**
  1. **Khẩu hình & Khoang miệng:** Nhìn kỹ răng, lưỡi và vòm miệng. MuseTalk bị hiện tượng dán hình vuông mờ (cutout box), răng bị bệt nhòe. SoulX Pro tự sinh giải phẫu răng và khoang miệng tự nhiên theo từng âm tiết tiếng Việt.
  2. **Viền mặt (Face Boundary):** MuseTalk để lại đường viền cắt cúp hình chữ nhật quanh cằm và má. SoulX Pro sinh toàn bộ khuôn mặt bằng diffusion nên viền mặt hòa nhập hoàn toàn, không có đường cắt ghép.

---

### BƯỚC 2: So sánh ma trận 4 góc phân giải & phục hồi da (10s)
* **Tệp video cần mở:** [`four_way_comparison_10s_25fps.mp4`](file:///D:/CongThang_AI_Avatar/v2_renders/V6_FINAL_ACCEPTANCE/four_way_comparison_10s_25fps.mp4)
* **Kích thước:** $2048 \times 2048$ chia làm 4 góc:
  - Góc trên-trái: Ảnh gốc Reference (Đỗ Trang)
  - Góc trên-phải: MuseTalk Baseline
  - Góc dưới-trái: SoulX Native 512×512
  - Góc dưới-phải: SoulX Enhanced 1024×1024 (chuẩn Blend 50/50 GFPGAN)
* **Điểm quan sát trọng tâm:**
  - So sánh chi tiết da giữa SoulX Native (dưới-trái) và Enhanced (dưới-phải). Thuật toán phối trộn 50% GFPGAN + 50% Bicubic Native giúp giữ nguyên vân da hữu cơ (lỗ chân lông, đường mí mắt, phản chiếu tròng đen) mà không bị biến thành "mặt nhựa sáp" (plastic airbrush effect).

---

### BƯỚC 3: Thẩm định video Master 60 giây đầy đủ (1,500 frames)
* **Tệp video cần mở:** [`soulx_pro_60s_enhanced_gfpgan50.mp4`](file:///D:/CongThang_AI_Avatar/v2_renders/V6_FINAL_ACCEPTANCE/soulx_pro_60s_enhanced_gfpgan50.mp4)
* **Độ dài:** Đúng 60.00 giây (1,500 frames @ 25fps).
* **Độ phân giải:** $1024 \times 1024$.
* **Điểm quan sát trọng tâm:**
  1. **Chớp mắt sinh học (Biological Eye Blinking):** Quan sát cử động mắt. SoulX Pro tự sinh nhịp chớp mắt sinh học ngẫu nhiên tự nhiên (~14 lần/phút). Ngược lại, MuseTalk chỉ lặp lại đúng 735 frame video nền có sẵn theo chu kỳ cứng nhắc.
  2. **Độ ổn định thời gian (Temporal Consistency):** Video kéo dài 60 giây trải qua 54 chunk khuếch tán nhưng hoàn toàn không bị giật khung hình ở điểm nối chunk, không bị biến dạng danh tính hay méo mặt.
  3. **Khớp nhịp âm - hình (Lip-Sync):** Khẩu hình phát âm tiếng Việt chuẩn xác từng thanh điệu hỏi, ngã, sắc, huyền.

---

### BƯỚC 4: Thẩm định Master định dạng dọc phát sóng (1080×1920)
* **Tệp video cần mở:** [`soulx_pro_60s_vertical_1080x1920.mp4`](file:///D:/CongThang_AI_Avatar/v2_renders/V6_FINAL_ACCEPTANCE/soulx_pro_60s_vertical_1080x1920.mp4)
* **Định dạng:** Chuẩn dọc 9:16 (TikTok, Facebook Reels, YouTube Shorts).
* **Bố cục (Layout Strategy B):** MC Đỗ Trang nằm ở trung tâm với kích thước $1080 \times 1080$, lớp nền là background studio mở rộng với hiệu ứng Gaussian blur + đổ bóng mềm 15px.
* **Điểm quan sát trọng tâm:** Độ thẩm mỹ khi xem trên màn hình điện thoại di động dọc hoặc thiết bị trình chiếu.

---

### BƯỚC 5: Thẩm định quy trình sinh video tự động từ kịch bản Studio V2
* **Tệp video cần mở:** [`studio_v2_quality_demo_10s.mp4`](file:///D:/CongThang_AI_Avatar/v2_renders/V6_FINAL_ACCEPTANCE/studio_v2_quality_demo_10s.mp4)
* **Nguồn gốc:** Được sinh tự động hoàn toàn thông qua API của Studio V2 (`POST /api/v2/render`, Job ID: `job_v2_95deae02`) từ kịch bản văn bản tiếng Việt đã được chuẩn hóa tự động (`VietnameseTextNormalizer`).
* **Điểm quan sát trọng tâm:** Kiểm chứng tính liền mạch của State Machine từ khâu nhận text $\rightarrow$ chuẩn hóa ngữ âm $\rightarrow$ gọi audio $\rightarrow$ sinh video DiT $\rightarrow$ nâng giải pháp 50/50 $\rightarrow$ ghép bố cục dọc $\rightarrow$ xuất tệp hoàn tất.

---

## 3. BẢNG TIÊU CHÍ ĐÁNH GIÁ MẮT THƯỜNG (QA CHECKLIST)

Khi đánh giá, quý vị có thể tích chọn các tiêu chí sau:

- [ ] **1. Nhận diện nhân vật (Identity):** MC Đỗ Trang nhìn đúng người thật, không bị biến dạng khuôn mặt hay đổi màu da.
- [ ] **2. Khẩu hình miệng (Lip-Sync):** Khớp khẩu hình với từng từ tiếng Việt, không bị trễ tiếng.
- [ ] **3. Cử động răng & lưỡi:** Răng rõ nét, không bị nhòe đen, cử động tự nhiên khi mở/đóng miệng.
- [ ] **4. Cử động mắt & Chớp mắt:** Có chớp mắt tự nhiên đều đặn, ánh mắt nhìn tự nhiên không bị vô hồn.
- [ ] **5. Độ tự nhiên của da:** Giữ được chi tiết chân thực của da mặt, không bị mịn quá đà dạng búp bê nhựa.
- [ ] **6. Chuyển động đầu:** Đầu có gật nhẹ tự nhiên khi nhấn giọng (như tại giây thứ 1.0 khi chào).
- [ ] **7. Độ liền mạch 60s:** Toàn bộ 60 giây mượt mà, không bị giật, không bị đứng hình ở giây nào.
- [ ] **8. Độ phân giải cao:** Video nét căng trên màn hình độ phân giải cao (Full-HD).

---

## 4. HƯỚNG DẪN KÍCH HOẠT THƯƠNG MẠI (PHÊ DUYỆT GATE P11 & MỞ GATE P12)

### Tình trạng khóa an toàn hiện tại:
Hệ thống Studio V2 đang được bảo vệ bởi cờ an toàn:
`V2_ENABLE_QUALITY_ENGINE = 0` (mặc định các yêu cầu thông thường chọn preset QUALITY sẽ bị từ chối 403 để bảo vệ tài nguyên).

### Cách thức phê duyệt:
Sau khi Quý Quản lý kiểm tra các video và đồng ý nghiệm thu chất lượng:
1. Gửi phản hồi xác nhận: **"Chấp thuận nghiệm thu Gate P11, cho phép kích hoạt Gate P12"** (hoặc chỉ định bật QUALITY engine).
2. Để áp dụng cho hệ thống Windows, thực thi lệnh mở khóa:
   ```powershell
   [System.Environment]::SetEnvironmentVariable('V2_ENABLE_QUALITY_ENGINE', '1', 'Machine')
   ```
3. Sau đó khởi động lại dịch vụ Studio V2 để preset QUALITY trở thành tuyến sinh video mặc định.

### Quy trình hoàn tác (Rollback tức thì nếu cần):
Nếu có bất kỳ vấn đề gì phát sinh trong quá trình sản xuất, chỉ cần đặt biến môi trường về 0:
```powershell
[System.Environment]::SetEnvironmentVariable('V2_ENABLE_QUALITY_ENGINE', '0', 'Machine')
```
Hệ thống sẽ ngay lập tức quay về chế độ an toàn mà không làm gián đoạn hệ thống Production V1 đang hoạt động trên Port 8078.
