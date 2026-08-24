# Quick local TEST launcher — EdgeTTS (free, no ElevenLabs key needed).
#
# Boots the realtime server on the headless GPU1 (remapped to logical cuda:0)
# with EdgeTTS vi-VN-HoaiMyNeural, batch_size 16, CUDA Graphs, telemetry ON.
# Use this to test FPS / lip-sync / avatar quality WITHOUT paying ElevenLabs.
# EdgeTTS needs internet (it streams from Microsoft's free endpoint) but costs
# nothing and needs no API key / .env.
#
# Usage (from the repo root, in the musetalk venv):
#   .\run_test.ps1
# Then open http://127.0.0.1:8010/dashboard.html and type text to speak.
#
# To render an offline MP4 instead (also free EdgeTTS):
#   python generate_video_from_script.py --script script_example.txt `
#       --avatar_id fullbody_30_7_25fps `
#       --output D:\CongThang_AI_Avatar\renders\test.mp4 --batch_size 16

$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

# GPU 1 = headless card on the 2x3090 dev box (avoids the GPU0 driver crash under
# parallel CUDA + DWM/Chrome contention). Remapped to logical cuda:0.
$env:CUDA_DEVICE_ORDER = "PCI_BUS_ID"
$env:CUDA_VISIBLE_DEVICES = "1"

$env:NOBLE_RAG_DISABLED = "1"
$env:LIVETALKING_MULTI_GPU = "false"
$env:LIVETALKING_GPU_ID = "0"
$env:LIVETALKING_GPU_IDS = "0"
$env:LIVETALKING_CUDA_GRAPH = "true"
$env:LIVETALKING_TTS_REALTIME_PACING = "true"
$env:LIVETALKING_TTS_MAX_BUFFER_SEC = "2.0"
$env:LIVETALKING_TTS_MAX_ASR_BUFFER_SEC = "1.2"
$env:LIVETALKING_AUDIO_JITTER_FRAMES = "2"
$env:LIVETALKING_GPU_HEARTBEAT_INTERVAL_SEC = "0.10"
$env:LIVETALKING_GPU_HEARTBEAT_ITERS = "8"
$env:LIVETALKING_GPU_HEARTBEAT_IDLE_GRACE_SEC = "2.5"
$env:LIVETALKING_WHISPER_WARMUP = "true"
$env:LIVETALKING_H264_PRESET = "ultrafast"
$env:LIVETALKING_OUTPUT_SAMPLE_RATE = "48000"
$env:LIVETALKING_VISUAL_TRANSITION = "true"

# Pick a python. Prefer the musetalk venv if present, else system python.
$py = Join-Path $root "venv_musetalk\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = "python" }

$avatarId = "fullbody_30_7_25fps"
if (-not (Test-Path (Join-Path $root "data\avatars\$avatarId"))) {
    # Fall back to the first complete musetalk avatar if the preferred one is absent.
    $avRoot = Join-Path $root "data\avatars"
    if (Test-Path $avRoot) {
        foreach ($d in (Get-ChildItem -Path $avRoot -Directory | Sort-Object Name)) {
            if ((Test-Path "$($d.FullName)\full_imgs") -and (Test-Path "$($d.FullName)\coords.pkl") -and (Test-Path "$($d.FullName)\latents.pt")) {
                $avatarId = $d.Name; break
            }
        }
    }
}

Write-Host "Test launch: model=musetalk avatar=$avatarId tts=edgetts gpu=GPU1 batch_size=16 cuda_graph=true" -ForegroundColor Cyan
Write-Host "Open http://127.0.0.1:8010/dashboard.html after 'start http server' appears." -ForegroundColor DarkGray

& $py app.py `
    --model musetalk `
    --avatar_id $avatarId `
    --tts edgetts `
    --transport webrtc `
    --listenport 8010 `
    --gpu_id 0 `
    --batch_size 16 `
    --enable_telemetry `
    --telemetry_interval 0.5