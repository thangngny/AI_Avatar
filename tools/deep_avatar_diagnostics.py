#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Comprehensive Deep Diagnostic Suite for NextGen AI Avatar Studio.

Performs 5 rigorous objective tests:
1. Audio-Visual Lip-Sync Temporal Alignment & Correlation (Sync Accuracy)
2. Seamless Face Boundary & Patch Transition Audit (Seamline / Box Edge Artifacts)
3. Color & Illumination Temporal Consistency (Skin Tone Flicker / Shimmer)
4. Forward Loop Boundary Continuity (Discontinuity / Jerk at loop seam)
5. Expressive Head Motion Smoothness & Jitter (Acceleration / Jerk Profiling)
"""
import os
import sys
import cv2
import json
import numpy as np
import soundfile as sf

def test_lip_sync_correlation(video_path: str, audio_path: str):
    """Test 1: Measures correlation between speech energy envelope and mouth aperture."""
    print("\n--- [TEST 1] Audio-Visual Lip-Sync Temporal Correlation ---")
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    # Read audio
    wav, sr = sf.read(audio_path, dtype="float32")
    if wav.ndim > 1:
        wav = wav.mean(axis=1)
        
    hop_length = int(sr / fps)
    audio_energy = []
    for i in range(total_frames):
        start = i * hop_length
        end = min(len(wav), (i + 1) * hop_length)
        if start < len(wav):
            chunk = wav[start:end]
            rms = np.sqrt(np.mean(chunk**2)) if len(chunk) > 0 else 0.0
        else:
            rms = 0.0
        audio_energy.append(rms)
    audio_energy = np.array(audio_energy)
    
    # Measure mouth vertical aperture (inner dark region inside mouth bounding box)
    # Avatar mouth region roughly y: 950-1350, x: 420-660
    mouth_openness = []
    frame_idx = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        # Crop mouth region
        h, w = frame.shape[:2]
        # In 1080x1920: y is approx 400:600 in 1080p? Let's check coord_list:
        # Coord 0 is [464, 343, 617, 564] (x1, y1, x2, y2)
        crop = frame[343:564, 464:617]
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        # Inner mouth is typically darker than skin/teeth (cavity)
        # Or measure gradient variance
        # Threshold dark cavity pixels
        dark_cavity = np.count_nonzero(gray < 55)
        mouth_openness.append(float(dark_cavity))
        frame_idx += 1
    cap.release()
    
    mouth_openness = np.array(mouth_openness)
    n = min(len(audio_energy), len(mouth_openness))
    audio_energy = audio_energy[:n]
    mouth_openness = mouth_openness[:n]
    
    # Cross-correlation at different lags (-5 to +5 frames)
    # to check if mouth opens exactly with audio or has lag
    lags = list(range(-6, 7))
    corrs = []
    norm_audio = (audio_energy - audio_energy.mean()) / (audio_energy.std() + 1e-6)
    norm_mouth = (mouth_openness - mouth_openness.mean()) / (mouth_openness.std() + 1e-6)
    
    for lag in lags:
        if lag < 0:
            c = np.mean(norm_audio[:lag] * norm_mouth[-lag:])
        elif lag > 0:
            c = np.mean(norm_audio[lag:] * norm_mouth[:-lag])
        else:
            c = np.mean(norm_audio * norm_mouth)
        corrs.append(float(c))
        
    best_lag_idx = int(np.argmax(corrs))
    best_lag = lags[best_lag_idx]
    best_corr = corrs[best_lag_idx]
    
    print(f"  > Measured frames: {n}")
    print(f"  > Peak Audio-Visual Correlation: {best_corr:.3f} at lag = {best_lag} frames ({-best_lag * (1000/fps):.1f} ms)")
    print(f"  > Lag 0 Correlation: {corrs[lags.index(0)]:.3f}")
    
    sync_status = "OPTIMAL" if abs(best_lag) <= 1 else ("ACCEPTABLE" if abs(best_lag) <= 2 else "DESYNC DETECTED")
    return {
        "sync_status": sync_status,
        "peak_correlation": round(best_corr, 3),
        "best_lag_frames": best_lag,
        "best_lag_ms": round(-best_lag * (1000/fps), 1),
        "zero_lag_correlation": round(corrs[lags.index(0)], 3)
    }


def test_seamline_and_boundary(video_path: str):
    """Test 2: Audits face patch composite boundary for seamlines, halo, or step discontinuities."""
    print("\n--- [TEST 2] Face Patch Composite Boundary & Seamline Audit ---")
    cap = cv2.VideoCapture(video_path)
    # Check boundary gradients around crop_box [375, 288, 705, 618]
    # Boundaries: y=288, y=618, x=375, x=705
    y_s, y_e, x_s, x_e = 288, 618, 375, 705
    
    seam_discontinuities = []
    frame_count = 0
    while True:
        ret, frame = cap.read()
        if not ret or frame_count >= 150:
            break
        
        # Check boundary edge step: difference between 2 pixels inside and 2 pixels outside the boundary
        # Top boundary y=288
        top_in = frame[y_s + 2, x_s:x_e].astype(float)
        top_out = frame[y_s - 2, x_s:x_e].astype(float)
        top_step = np.abs(top_in - top_out).mean()
        
        # Bottom boundary y=618
        bot_in = frame[y_e - 2, x_s:x_e].astype(float)
        bot_out = frame[y_e + 2, x_s:x_e].astype(float)
        bot_step = np.abs(bot_in - bot_out).mean()
        
        # Left boundary x=375
        left_in = frame[y_s:y_e, x_s + 2].astype(float)
        left_out = frame[y_s:y_e, x_s - 2].astype(float)
        left_step = np.abs(left_in - left_out).mean()
        
        # Right boundary x=705
        right_in = frame[y_s:y_e, x_e - 2].astype(float)
        right_out = frame[y_s:y_e, x_e + 2].astype(float)
        right_step = np.abs(right_in - right_out).mean()
        
        mean_step = (top_step + bot_step + left_step + right_step) / 4.0
        seam_discontinuities.append(mean_step)
        frame_count += 1
    cap.release()
    
    avg_seam = float(np.mean(seam_discontinuities))
    max_seam = float(np.max(seam_discontinuities))
    print(f"  > Average Boundary Step: {avg_seam:.2f} intensity units (Natural skin gradient < 5.0)")
    print(f"  > Peak Boundary Step: {max_seam:.2f} intensity units")
    seam_status = "PERFECT (Invisible)" if avg_seam < 4.0 else ("GOOD" if avg_seam < 7.0 else "VISIBLE SEAM")
    return {
        "seam_status": seam_status,
        "avg_boundary_step": round(avg_seam, 2),
        "peak_boundary_step": round(max_seam, 2)
    }


def test_skin_tone_flicker(video_path: str):
    """Test 3: Audits temporal skin tone & illumination flicker across consecutive frames."""
    print("\n--- [TEST 3] Skin Tone & Illumination Temporal Flicker Audit ---")
    cap = cv2.VideoCapture(video_path)
    
    chin_means = []
    cheek_means = []
    frame_count = 0
    while True:
        ret, frame = cap.read()
        if not ret or frame_count >= 200:
            break
        # Chin skin (blended region): approx y: 550-590, x: 500-580
        chin = frame[550:590, 500:580]
        # Cheek skin (unblended reference): approx y: 350-400, x: 380-430
        cheek = frame[350:400, 380:430]
        
        chin_means.append(chin.mean(axis=(0, 1)))
        cheek_means.append(cheek.mean(axis=(0, 1)))
        frame_count += 1
    cap.release()
    
    chin_means = np.array(chin_means)
    cheek_means = np.array(cheek_means)
    
    # Measure frame-to-frame delta (flicker)
    chin_flicker = np.abs(np.diff(chin_means, axis=0)).mean()
    cheek_flicker = np.abs(np.diff(cheek_means, axis=0)).mean()
    
    # Ratio of blended chin flicker to unblended cheek flicker
    flicker_ratio = chin_flicker / (cheek_flicker + 1e-6)
    
    print(f"  > Blended Chin Temporal Delta: {chin_flicker:.3f} RGB levels")
    print(f"  > Natural Cheek Temporal Delta: {cheek_flicker:.3f} RGB levels")
    print(f"  > Relative Flicker Ratio: {flicker_ratio:.2f}x")
    
    flicker_status = "ROCK SOLID (Zero Flicker)" if chin_flicker < 1.0 else ("NORMAL" if chin_flicker < 2.5 else "FLICKER DETECTED")
    return {
        "flicker_status": flicker_status,
        "chin_delta": round(float(chin_flicker), 3),
        "cheek_delta": round(float(cheek_flicker), 3),
        "relative_flicker_ratio": round(float(flicker_ratio), 2)
    }


def test_loop_boundary_continuity(video_path: str):
    """Test 4: Audits continuity at the forward loop wraparound points (e.g. frame 200, 400)."""
    print("\n--- [TEST 4] Forward Loop Wraparound Continuity Audit ---")
    cap = cv2.VideoCapture(video_path)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    frames = []
    for _ in range(min(total_frames, 450)):
        ret, f = cap.read()
        if not ret: break
        frames.append(f)
    cap.release()
    
    # Loop length is 200 frames (325:525 in source)
    loop_period = 200
    wrap_points = [loop_period * k for k in range(1, len(frames) // loop_period)]
    
    wrap_diffs = []
    normal_diffs = []
    for i in range(len(frames) - 1):
        # Measure body/shoulder area (y: 800-1400, x: 200-880) to ignore mouth movement
        diff = np.abs(frames[i][800:1400, 200:880].astype(float) - frames[i+1][800:1400, 200:880].astype(float)).mean()
        if (i + 1) in wrap_points:
            wrap_diffs.append(diff)
        else:
            normal_diffs.append(diff)
            
    avg_wrap = float(np.mean(wrap_diffs)) if wrap_diffs else 0.0
    avg_norm = float(np.mean(normal_diffs)) if normal_diffs else 0.0
    jump_ratio = avg_wrap / (avg_norm + 1e-6)
    
    print(f"  > Normal Frame-to-Frame Body Delta: {avg_norm:.3f}")
    print(f"  > Loop Seam Wraparound Delta: {avg_wrap:.3f}")
    print(f"  > Jump Discontinuity Ratio: {jump_ratio:.2f}x")
    
    loop_status = "PERFECT (Seamless Loop)" if jump_ratio < 1.5 else ("ACCEPTABLE" if jump_ratio < 2.5 else "LOOP JUMP DETECTED")
    return {
        "loop_status": loop_status,
        "normal_body_delta": round(avg_norm, 3),
        "wrap_body_delta": round(avg_wrap, 3),
        "jump_ratio": round(jump_ratio, 2)
    }


def test_expressive_motion_jerk(video_path: str):
    """Test 5: Profiles expressive motion dynamics for unnatural jerk or sudden head snaps."""
    print("\n--- [TEST 5] Expressive Motion Dynamics & Jerk Profiling ---")
    cap = cv2.VideoCapture(video_path)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    # Track head position across frames by template matching or centroid of nose/bridge
    # Nose bridge roughly at y: 350-420, x: 500-580 in 1080p
    ret, first_frame = cap.read()
    if not ret:
        cap.release()
        return {}
    template = first_frame[350:420, 500:580].copy()
    th, tw = template.shape[:2]
    
    positions = []
    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
    for _ in range(min(total_frames, 300)):
        ret, f = cap.read()
        if not ret: break
        # Search in window around nose
        search_roi = f[320:450, 470:610]
        res = cv2.matchTemplate(search_roi, template, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
        pos_y = 320 + max_loc[1]
        pos_x = 470 + max_loc[0]
        positions.append((pos_x, pos_y))
    cap.release()
    
    positions = np.array(positions)
    # Velocity = diff(positions)
    vel = np.diff(positions, axis=0)
    # Acceleration = diff(velocity)
    acc = np.diff(vel, axis=0)
    # Jerk = diff(acceleration)
    jerk = np.diff(acc, axis=0)
    
    max_acc = float(np.max(np.abs(acc)))
    max_jerk = float(np.max(np.abs(jerk)))
    mean_speed = float(np.mean(np.linalg.norm(vel, axis=1)))
    
    print(f"  > Average Head Velocity: {mean_speed:.2f} px/frame")
    print(f"  > Peak Acceleration: {max_acc:.2f} px/frame^2")
    print(f"  > Peak Jerk (Snap/Shake): {max_jerk:.2f} px/frame^3 (Smooth motion < 3.0)")
    
    jerk_status = "ORGANIC & SMOOTH" if max_jerk < 2.5 else ("MODERATE" if max_jerk < 4.0 else "JERKY / UNNATURAL")
    return {
        "jerk_status": jerk_status,
        "mean_speed_px": round(mean_speed, 2),
        "peak_acc": round(max_acc, 2),
        "peak_jerk": round(max_jerk, 2)
    }


def main():
    video_path = r"D:\CongThang_AI_Avatar\renders\demo_sota_crystal_sharp_25fps.mp4"
    audio_path = r"C:\Users\phuongpn\AI_Avatar_NextGen\renders\demo_elevenlabs_16k.wav"
    
    print("=" * 70)
    print("NEXTGEN AI AVATAR -- 5-DIMENSION DEEP QUALITY AUDIT SUITE")
    print("=" * 70)
    
    t1 = test_lip_sync_correlation(video_path, audio_path)
    t2 = test_seamline_and_boundary(video_path)
    t3 = test_skin_tone_flicker(video_path)
    t4 = test_loop_boundary_continuity(video_path)
    t5 = test_expressive_motion_jerk(video_path)
    
    report = {
        "test_1_lip_sync": t1,
        "test_2_seamline_boundary": t2,
        "test_3_skin_tone_flicker": t3,
        "test_4_loop_continuity": t4,
        "test_5_expressive_motion": t5
    }
    
    print("\n" + "=" * 70)
    print("DEEP DIAGNOSTIC AUDIT SUMMARY:")
    print("=" * 70)
    for k, v in report.items():
        status = [val for key, val in v.items() if "status" in key][0]
        print(f"  * {k.upper():<30}: {status}")
    print("=" * 70)
    
    out_file = r"D:\CongThang_AI_Avatar\renders\deep_diagnostic_report.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"\nSaved full report to: {out_file}")

if __name__ == "__main__":
    main()
