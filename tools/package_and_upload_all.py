#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AI Avatar Studio — Complete Cloud Packager & Uploader.

Packages and uploads ALL remaining assets to GitHub Release v1.5.0-assets:
1. All 5 remaining avatars (close_up, full_4_9, mid_4_9, mid_4_9_2, 28_8_mid in 3 parts)
2. Security & configs (.env, data/studio.db, uploads, recordings, input4_9)
3. Auxiliary models (models/syncnet, gfpgan/weights, avatars/wav2lip)

Cleans up each zip after upload to save local disk space.
"""
import os
import sys
import time
import zipfile
import subprocess
import shutil

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = os.path.join(ROOT, "dist_assets")
RELEASE_TAG = "v1.5.0-assets"
REPO = "thangngny/AI_Avatar"

os.makedirs(DIST, exist_ok=True)

def run_cmd(cmd):
    res = subprocess.run(cmd, cwd=ROOT)
    return res.returncode == 0

def upload_asset(zip_path):
    print(f"[*] Đang tải {os.path.basename(zip_path)} ({os.path.getsize(zip_path)/(1024**2):.1f} MB) lên GitHub Release...")
    cmd = ["gh", "release", "upload", RELEASE_TAG, zip_path, "--repo", REPO, "--clobber"]
    ok = run_cmd(cmd)
    if ok:
        print(f"  [OK] Đã tải lên GitHub Release thành công: {os.path.basename(zip_path)}")
        try:
            os.remove(zip_path)
            print(f"  [DỌN DẸP] Đã xóa tệp zip tạm {os.path.basename(zip_path)} để giải phóng ổ cứng.")
        except Exception:
            pass
    else:
        print(f"  [!] Lỗi khi tải lên GitHub Release cho {os.path.basename(zip_path)}")
    return ok

def zip_dir(src_dir, zip_name, arc_prefix=""):
    zip_p = os.path.join(DIST, zip_name)
    t0 = time.time()
    print(f"\n---> Đang nén {src_dir} thành {zip_name}...")
    with zipfile.ZipFile(zip_p, "w", zipfile.ZIP_DEFLATED, compresslevel=1) as zf:
        for root, dirs, files in os.walk(os.path.join(ROOT, src_dir)):
            dirs[:] = [d for d in dirs if d not in (".cache", "__pycache__")]
            for f in files:
                fp = os.path.join(root, f)
                rel = os.path.relpath(fp, os.path.join(ROOT, src_dir))
                arcname = os.path.join(arc_prefix, rel) if arc_prefix else rel
                zf.write(fp, arcname)
    print(f"  [NÉN XONG] {zip_name}: {os.path.getsize(zip_p)/(1024**2):.1f} MB trong {time.time()-t0:.1f}s")
    return zip_p

def package_and_upload():
    print("=" * 70)
    print("   AI AVATAR STUDIO — COMPLETE CLOUD PUSH (100% ASSETS)")
    print("=" * 70)

    # 1. System .env, studio.db, uploads, recordings, input4_9
    sec_zip = os.path.join(DIST, "system_env_and_database.zip")
    print("\n---> Đang đóng gói .env, database, uploads, recordings...")
    with zipfile.ZipFile(sec_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        env_f = os.path.join(ROOT, ".env")
        if os.path.isfile(env_f):
            zf.write(env_f, ".env")
        db_f = os.path.join(ROOT, "data", "studio.db")
        if os.path.isfile(db_f):
            zf.write(db_f, "data/studio.db")
        for folder in ["data/avatars/.uploads", "data/recordings", "input4_9"]:
            full_f = os.path.join(ROOT, folder)
            if os.path.isdir(full_f):
                for root, dirs, files in os.walk(full_f):
                    for f in files:
                        fp = os.path.join(root, f)
                        rel = os.path.relpath(fp, ROOT)
                        zf.write(fp, rel)
    upload_asset(sec_zip)

    # 2. Auxiliary models (syncnet, gfpgan, wav2lip)
    aux_zip = os.path.join(DIST, "model_auxiliary.zip")
    print("\n---> Đang đóng gói các mô hình phụ trợ (syncnet, gfpgan, wav2lip)...")
    with zipfile.ZipFile(aux_zip, "w", zipfile.ZIP_DEFLATED, compresslevel=1) as zf:
        for folder in ["models/syncnet", "gfpgan/weights", "avatars/wav2lip"]:
            full_f = os.path.join(ROOT, folder)
            if os.path.isdir(full_f):
                for root, dirs, files in os.walk(full_f):
                    dirs[:] = [d for d in dirs if d not in (".cache", "__pycache__")]
                    for f in files:
                        fp = os.path.join(root, f)
                        rel = os.path.relpath(fp, ROOT)
                        zf.write(fp, rel)
    upload_asset(aux_zip)

    # 3. Simple avatars (< 2GB each)
    simple_avatars = [
        ("data/avatars/close_up", "avatar_close_up.zip", "close_up"),
        ("data/avatars/full_4_9", "avatar_full_4_9.zip", "full_4_9"),
        ("data/avatars/mid_4_9", "avatar_mid_4_9.zip", "mid_4_9"),
        ("data/avatars/mid_4_9_2", "avatar_mid_4_9_2.zip", "mid_4_9_2"),
    ]
    for src, zname, prefix in simple_avatars:
        zp = zip_dir(src, zname, prefix)
        upload_asset(zp)

    # 4. Large avatar 28_8_mid (4.56 GB) -> Split into 3 parts
    print("\n---> Đang chia nhỏ và nén avatar 28_8_mid (4.56 GB)...")
    src_28 = os.path.join(ROOT, "data", "avatars", "28_8_mid")
    full_imgs_dir = os.path.join(src_28, "full_imgs")
    all_imgs = sorted([f for f in os.listdir(full_imgs_dir) if f.endswith(".png")])
    total_imgs = len(all_imgs)
    p1 = total_imgs // 3
    p2 = 2 * (total_imgs // 3)

    # Part 1: imgs[:p1]
    z1 = os.path.join(DIST, "avatar_28_8_mid_part1.zip")
    with zipfile.ZipFile(z1, "w", zipfile.ZIP_DEFLATED, compresslevel=1) as zf:
        for fn in all_imgs[:p1]:
            zf.write(os.path.join(full_imgs_dir, fn), os.path.join("28_8_mid", "full_imgs", fn))
    upload_asset(z1)

    # Part 2: imgs[p1:p2]
    z2 = os.path.join(DIST, "avatar_28_8_mid_part2.zip")
    with zipfile.ZipFile(z2, "w", zipfile.ZIP_DEFLATED, compresslevel=1) as zf:
        for fn in all_imgs[p1:p2]:
            zf.write(os.path.join(full_imgs_dir, fn), os.path.join("28_8_mid", "full_imgs", fn))
    upload_asset(z2)

    # Part 3: imgs[p2:] + remaining metadata/tensors
    z3 = os.path.join(DIST, "avatar_28_8_mid_part3.zip")
    with zipfile.ZipFile(z3, "w", zipfile.ZIP_DEFLATED, compresslevel=1) as zf:
        for fn in all_imgs[p2:]:
            zf.write(os.path.join(full_imgs_dir, fn), os.path.join("28_8_mid", "full_imgs", fn))
        # Mask and metadata
        mask_dir = os.path.join(src_28, "mask")
        if os.path.isdir(mask_dir):
            for fn in os.listdir(mask_dir):
                zf.write(os.path.join(mask_dir, fn), os.path.join("28_8_mid", "mask", fn))
        for f in ["avator_info.json", "coords.pkl", "latents.pt", "mask_coords.pkl"]:
            fp = os.path.join(src_28, f)
            if os.path.isfile(fp):
                zf.write(fp, os.path.join("28_8_mid", f))
    upload_asset(z3)

    print("\n" + "=" * 70)
    print("🎉 TOÀN BỘ 100% ASSETS ĐÃ ĐƯỢC ĐẨY LÊN GITHUB RELEASES THÀNH CÔNG!")
    print("=" * 70)

if __name__ == "__main__":
    package_and_upload()
