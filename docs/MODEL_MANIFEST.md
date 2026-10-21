# Model Manifest

Full checksums in `diagnostics/handover/model_manifest.json`. All base models PRESENT (15/15), 1 optional missing.

| Logical name | Path | Size | Req? | SHA-256 (first 16) |
|---|---|---|---|---|
| MuseTalk v1.5 UNet | models/musetalkV15/unet.pth | 3.40 GB | REQUIRED | 7ebf6c98c181e208 |
| MuseTalk v1.5 config | models/musetalkV15/musetalk.json | 748 B | REQUIRED | 5b6923aee04d7169 |
| MuseTalk alt checkpoint | models/musetalk/pytorch_model.bin | 3.40 GB | optional | 0ee7d5ea03ea75d8 |
| Whisper tiny (audio2feature) | models/whisper/pytorch_model.bin | 151 MB | REQUIRED | 9607f98a2b22d9e2 |
| Whisper config | models/whisper/config.json | 1.98 KB | REQUIRED | ffdccec4f3211f4c |
| Whisper preprocessor | models/whisper/preprocessor_config.json | 185 KB | REQUIRED | 9b5cd03a36fbb8a6 |
| Stable Diffusion VAE | models/sd-vae/diffusion_pytorch_model.bin | 335 MB | REQUIRED | 1b4889b6b1d4ce7a |
| VAE config | models/sd-vae/config.json | 547 B | REQUIRED | 92d3dfb746fca211 |
| Face parsing BiSeNet | models/face-parse-bisent/79999_iter.pth | 53.3 MB | REQUIRED | 468e13ca13a9b43c |
| ResNet18 face-parse backbone | models/face-parse-bisent/resnet18-5c106cde.pth | 46.8 MB | REQUIRED | 5c106cde386e87d4 |
| DWPose | models/dwpose/dw-ll_ucoco_384.pth | 407 MB | optional | 0d9408b13cd863c4 |
| LatentSync SyncNet (bench) | models/syncnet/latentsync_syncnet.pt | 1.49 GB | optional | 38fa63bad3ed2332 |
| GFPGAN detection | gfpgan/weights/detection_Resnet50_Final.pth | 109 MB | optional | 6d1de9c2944f2ccd |
| GFPGAN parsing | gfpgan/weights/parsing_parsinet.pth | 85.3 MB | optional | 3d558d8d0e42c202 |
| **GFPGANv1.4 (face restore)** | models/GFPGANv1.4.pth | — | **MISSING (optional)** | — |

## Notes
- `models/musetalkV15/unet.pth` is the production UNet. `models/musetalk/pytorch_model.bin` is an alternate (v1.4-era) checkpoint, kept but not on the locked v1.5 path.
- `models/syncnet/latentsync_syncnet.pt` is the LatentSync SyncNet — used only by the experimental bench (`avatar_export/bench/syncnet_score.py`), NOT by production render. Per project memory it matches `syncnet_16_pixel.yaml` (not `_pixel_attn`).
- `GFPGANv1.4.pth` is only needed if `--gfpgan` face restoration is enabled (off by default).

## Recovery sources
- MuseTalk v1.5 / Whisper tiny / SD-VAE / face-parse / DWPose: HuggingFace (MuseTalk release).
- LatentSync SyncNet: LatentSync release.
- GFPGAN weights: GFPGAN release.

## Corruption detection
Re-run `python scripts/preflight.py --detail` (checks presence) or recompute checksums with `diagnostics/handover/_checksum_models.py` and compare to `model_manifest.json`.