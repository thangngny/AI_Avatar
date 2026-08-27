# Avatar Library Master Audit (V1.1)

Generated 2026-08-27 from on-disk artifacts, `data/avatar_sources.json` lineage,
the real source-quality validator, and real render history. **No fabricated
values.** Machine-readable: `data/avatar_quality_audit.json`.

## Two distinct concepts (kept separate)

- **Technical status**: SẴN SÀNG (prepared artifacts complete, v15) / CHƯA HOÀN TẤT.
- **Source quality**: how suitable the *original video* is for avatar creation
  (RẤT TỐT / TỐT / CẢNH BÁO / KHÔNG KHUYẾN NGHỊ / CHƯA ĐỦ DỮ LIỆU / CHƯA CÓ DỮ LIỆU).
- **Production confidence**: what has actually been *proven by real renders*
  (CAO / TRUNG BÌNH / CHƯA KIỂM CHỨNG) — from DB jobs + on-disk render files.

READY ≠ quality. An avatar can be SẴN SÀNG but CẢNH BÁO, or have unknown source
quality yet high production confidence (real renders exist).

## Summary counts (real, from audit)

| Metric | Count |
|---|---|
| Total avatar dirs (excl. `.uploads`) | 18 |
| READY | 17 |
| INCOMPLETE | 1 (`30_7_fullbody`) |
| Source quality TỐT | 3 (`cu_recon_em10_jaw`, `cu_recon_em10_mouthchin`, `cu_recon_em20_jaw`) |
| Source quality CẢNH BÁO | 2 (`doTrang_closeup`, `doTrang_fullbody`) |
| Source quality KHÔNG KHUYẾN NGHỊ | 1 (`mc_hamai_mid` — static image) |
| Source quality CHƯA ĐỦ DỮ LIỆU (partial, render exists) | 1 (`close_up`) |
| Source quality CHƯA CÓ DỮ LIỆU (raw source missing) | 11 |
| Production confidence CAO (≥2 real renders) | 1 (`doTrang_closeup`, 7 renders) |
| Production confidence TRUNG BÌNH (1 real render) | 4 (`close_up`, `cu_recon_*`) |
| Production confidence CHƯA KIỂM CHỨNG (0 renders) | 13 |

## WHY some avatars show "Chưa có dữ liệu"

**Reason code: `RAW_SOURCE_MISSING` (11 avatars):** the original raw video
referenced by `avator_info.json video_path` / `data/avatar_sources.json` no
longer exists on disk (paths point to `D:\AI_avatar\…`, `D:\Noble\…`,
`C:\Users\Admin\Videos\30_7\…`, `D:\AI_avatar_ship\…` — all gone). The prepared
avatar survives; the source does not. Quality of the *source* cannot be
assessed without the source, so it is honestly reported as CHƯA CÓ DỮ LIỆU
(not guessed). Affected: `23_7_avt`, `30_7close`, `close_up` (→ partial, see
below), `close_up_16_7`, `fulbody_2_8`, `full_body_16_7`, `fullbody_30_7`,
`fullbody_30_7_25fps`, `fullbody_30_7_jaw`, `fullbody_30_7_mouth_chin`,
`fullbody_30_7_stable`.

None are `VALIDATOR_NEVER_RUN` (backfill ran for all with sources) or
`VALIDATOR_RESULT_LOST`. None are `LEGACY_AVATAR` placeholder. The 6 with
on-disk sources were all validated (`RAW_VALIDATOR`).

## Master table

| AVATAR_ID | TECH | SOURCE QUALITY | PROVENANCE | PROD CONF | RENDERS | RAW SRC | LINEAGE |
|---|---|---|---|---|---|---|---|
| 23_7_avt | READY | CHƯA CÓ DỮ LIỆU | UNKNOWN | CHƯA KIỂM CHỨNG | 0 | missing | MISSING |
| 30_7_fullbody | **INCOMPLETE** | — (not assessed) | UNKNOWN | CHƯA KIỂM CHỨNG | 0 | exists (.uploads copy) | RELOCATED_COPY_FOUND |
| 30_7close | READY | CHƯA CÓ DỮ LIỆU | UNKNOWN | CHƯA KIỂM CHỨNG | 0 | missing | MISSING |
| close_up | READY | CHƯA ĐỦ DỮ LIỆU | UNKNOWN | TRUNG BÌNH | 1 | missing | MISSING |
| close_up_16_7 | READY | CHƯA CÓ DỮ LIỆU | UNKNOWN | CHƯA KIỂM CHỨNG | 0 | missing | MISSING |
| cu_recon_em10_jaw | READY | TỐT | RAW_VALIDATOR | TRUNG BÌNH | 1 | exists (close_up_recon.mp4) | PRESENT |
| cu_recon_em10_mouthchin | READY | TỐT | RAW_VALIDATOR | TRUNG BÌNH | 1 | exists | PRESENT |
| cu_recon_em20_jaw | READY | TỐT | RAW_VALIDATOR | TRUNG BÌNH | 1 | exists | PRESENT |
| doTrang_closeup | READY | CẢNH BÁO | RAW_VALIDATOR | CAO | 7 | exists (input/1_Đồ_Trắng/Close Up.mp4) | PRESENT |
| doTrang_fullbody | READY | CẢNH BÁO | RAW_VALIDATOR | CHƯA KIỂM CHỨNG | 0 | exists | PRESENT |
| fulbody_2_8 | READY | CHƯA CÓ DỮ LIỆU | UNKNOWN | CHƯA KIỂM CHỨNG | 0 | missing | MISSING |
| full_body_16_7 | READY | CHƯA CÓ DỮ LIỆU | UNKNOWN | CHƯA KIỂM CHỨNG | 0 | missing | MISSING |
| fullbody_30_7 | READY | CHƯA CÓ DỮ LIỆU | UNKNOWN | CHƯA KIỂM CHỨNG | 0 | missing | MISSING |
| fullbody_30_7_25fps | READY | CHƯA CÓ DỮ LIỆU | UNKNOWN | CHƯA KIỂM CHỨNG | 0 | missing | MISSING |
| fullbody_30_7_jaw | READY | CHƯA CÓ DỮ LIỆU | UNKNOWN | CHƯA KIỂM CHỨNG | 0 | missing | MISSING |
| fullbody_30_7_mouth_chin | READY | CHƯA CÓ DỮ LIỆU | UNKNOWN | CHƯA KIỂM CHỨNG | 0 | missing | MISSING |
| fullbody_30_7_stable | READY | CHƯA CÓ DỮ LIỆU | UNKNOWN | CHƯA KIỂM CHỨNG | 0 | missing | MISSING |
| mc_hamai_mid | READY | KHÔNG KHUYẾN NGHỊ | RAW_VALIDATOR | CHƯA KIỂM CHỨNG | 0 | exists (MID_1.png — static image) | PRESENT |

## Special audit: close_up

- Technical: **READY** (980 full_imgs, 980 masks, all artifacts, v15/jaw).
- Source quality: **CHƯA ĐỦ DỮ LIỆU** — raw original is missing
  (`D:\Noble\livetalking\…musetalk_4872_697362812.mp4` gone). The source cannot
  be re-graded from raw.
- Production confidence: **TRUNG BÌNH** — 1 on-disk render
  (`D:\CongThang_AI_Avatar\renders\source_opt\ab\close_up.mp4`).
- **Historical audit evidence (supplementary, on disk):**
  `archive/reports/SYSTEM_BEST_RAW_AVATAR_SOURCE_AUDIT.md` grades the surviving
  `close_up` prepared proxy as **A+ (86.6)**, neutral mouth, +2.5% face /
  +39% sharper than the best stored raw, and states it should be **kept in
  production**. This is real historical evidence, but it does **not** inflate
  the on-disk render count (1).
- **Should UI still say only "Chưa có dữ liệu"?** **NO / PARTIAL.** The V1.1
  UI now shows source = CHƯA ĐỦ DỦ LIỆU + production = TRUNG BÌNH (1 render),
  with a "Đã kiểm chứng" badge. This is more honest than a bare "no data".
- Recommended: do **not** re-prepare close_up (raw is gone and prepared is the
  validated baseline).

## Special audit: cu_recon_em10_jaw (recommendation)

- V1.1 previously marked it ★ KHUYẾN NGHỊ. **This was overstated** — it is the
  best *among avatars with current validator data*, not the global best.
- 11 of 17 READY avatars lack source-quality data (raw source missing), so
  they were excluded from the comparison. A global ★ implies certainty
  beyond the available evidence.
- **Fix applied (V1.1 audit):** the recommendation is now confidence-gated.
  When any READY avatar lacks quality data, the best-evaluated avatar shows
  **"TỐT NHẤT TRONG NHÓM ĐÃ ĐÁNH GIÁ"** (not global ★). A global ★ KHUYẾN NGHỊ
  is only shown when **all** READY avatars have real source-quality data.
- `cu_recon_em10_jaw` (TỐT, 3 cu_recon tie on face ratio) → now shows the
  partial-group label.

## Special audit: doTrang_closeup

- Source quality: **CẢNH BÁO** (motion + lighting) — real validator result.
- Production confidence: **CAO** — 7 real completed UI renders
  (1080×1920, 25fps, audio+video verified in prior acceptance).
- The UI now shows **both honestly**: source CẢNH BÁO + "Đã kiểm chứng (7)".
  Source warnings are NOT erased; real render success is shown alongside.

## Special audit: mc_hamai_mid

- Source is a **static image** (`input_25_8/Input/MID/Ver 1/MID_1.png`), not a
  video. The validator treated it as a 1-frame "video".
- Result: KHÔNG KHUYẾN NGHỊ (mờ / blurred) — this is **partially an artifact**
  of the validator being designed for video (a single photo lacks the temporal
  metrics; "motion"/"lighting flicker" are not meaningful for a photo). The
  sharpness/face-size metrics are still meaningful.
- Honest handling: kept as KHÔNG KHUYẾN NGHỊ but the audit flags that
  motion/lighting dimensions are not meaningful for a static-image source.
  Production confidence: CHƯA KIỂM CHỮNG (no renders).

## Recommendation rule (final)

- No global numeric score (no 87/100 — no authoritative scoring model exists).
- Categorical source quality + production confidence + real strengths/warnings.
- Global ★ only when all READY avatars have real source-quality data;
  otherwise the best-evaluated gets "TỐT NHẤT TRONG NHÓM ĐÃ ĐÁNH GIÁ".
- Avatars with real render history show "Đã kiểm chứng (N)".

## Limitations / honest unknowns

- 11 avatars lost their raw source → source quality unknowable (not guessed).
  A prepared-data analysis (method 2) could derive prepared face size /
  sharpness from `full_imgs` + `coords.pkl`, but those are *prepared* metrics,
  not *source* metrics (source talking state, original camera motion, raw
  resolution are not recoverable). Not implemented to avoid mislabeling.
- `close_up` has strong historical baseline evidence (A+) not reflected in
  the on-disk render count (1). The UI uses on-disk evidence only.
- `mc_hamai_mid` is a photo; validator motion/lighting dims not meaningful.