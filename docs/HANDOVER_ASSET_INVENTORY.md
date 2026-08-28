# AI Avatar Studio — Asset Inventory

Measured 2026-08-28 (real file sizes).

## A. IRREPLACEABLE — must back up
| Asset | Location | Size | Notes |
|---|---|---|---|
| ElevenLabs API key | `.env` (gitignored) | 1 KB | SECRET — never commit; included in backup bundle (store securely) |
| Studio database | `data/studio_runtime/studio.db` | 151 KB | jobs/history/avatar metadata; SQLite online-backup API |
| Raw customer source videos | `data/input/avatar_sources/` | 155 MB (9 files) | the original people videos |
| Prepared Avatar binaries | `data/avatars/` (19 dirs) | 34.9 GB | full_imgs + coords.pkl + latents.pt + mask.png per avatar |
| Locked production config | `config/render_truth.json` | 315 B | the lipsync truth |
| Sample video + manifest | `studio/static/assets/avatar_source_example/` | 3.5 MB | sample.mp4 + manifest.json (lineage) |
| Documentation / HDSD | `docs/`, repo | small | this handover set + UI guide |
| Git history | `.git/` | — | tags mark known-good releases |

## B. Reconstructable but expensive
| Asset | Location | Approx cost |
|---|---|---|
| Prepared Avatar cache | `data/avatars/` | ~20-30 min GPU per avatar (genavatar.py) |
| Master audio cache | `data/studio_runtime/temp/master/*.wav` | seconds (re-synthesize) |
| Render outputs | `D:\CongThang_AI_Avatar\renders\studio\` | minutes per render |

## C. Reinstallable
| Asset | Source |
|---|---|
| Python packages | `requirements-handover.lock` + pip (torch 2.5.1+cu121 / CUDA 12.1) |
| cloudflared | cloudflare download |
| ffmpeg/ffprobe | gyan.dev build (already on PATH) |
| Base models | HuggingFace / MuseTalk release / LatentSync release (see MODEL_MANIFEST.md) |

## D. Regeneratable (safe to delete)
| Asset | Location | Current |
|---|---|---|
| Temp previews/WAV | `data/studio_runtime/temp/` | small |
| Upload chunk staging | `data/studio_runtime/temp/uploads/` | 0 MB (cleaned on complete) |
| Per-job logs | `data/studio_runtime/logs/*.log` | small |
| Diagnostics | `diagnostics/` | 2.2 MB |

## Disk usage summary
- C: ~80 GB free (avatars 35 GB + models 8.85 GB live here) — watch this
- D: ~804 GB free (renders go here) — healthy
- E: ~84 GB free — 96% full, AVOID

## Largest observed render
99 MB (under `D:\CongThang_AI_Avatar\renders\`). Typical short test ~5-15 MB.

## Stale temp
None found (uploads staging cleaned on finalize; no chunks >1 day).