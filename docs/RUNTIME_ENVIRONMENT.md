# AI Avatar Studio — Runtime Environment (V1.6.0)

## Canonical production runtime
- **Path (local):** `D:\CongThang_AI_Avatar\runtime\venv` (product-owned, on the large data drive)
- **Python:** 3.10.11 (base `C:\Users\Admin\AppData\Local\Programs\Python\Python310`)
- **Design:** self-contained venv (`include-system-site-packages = false`) — every production
  dependency is installed INTO the venv. No base-package mixing.
- **Torch:** `2.5.1+cu121` (CUDA 12.1) · torchvision `0.20.1+cu121` · GPU: 2x RTX 3090 (driver 610.88)
- **Dependency source of truth:** `requirements-handover.lock` (exact pins, captured from the
  proven env). Full freeze: `diagnostics/handover/pip_freeze_torch.txt`.

## Why a canonical, product-owned env
The previous runtime (`C:\CongThang\AI_avatar\latentsync_env`) lived **under the experimental
LatentSync repo tree** and was **partially destroyed** (pyvenv.cfg deleted + torch and most
site-packages removed), which broke the renderer (`import torch` → ModuleNotFoundError). The fix
is a product-owned, self-contained env recreated from the lock, with the studio's interpreter
references cut over to it. The old env is deprecated for AI Avatar (left in place, not deleted).

## Cutover (centralized — do NOT scatter paths)
- `studio/runtime.py` `_DEFAULT_TORCH_PYTHON` → `D:\CongThang_AI_Avatar\runtime\venv\Scripts\python.exe`
  (the single hardcoded renderer-interpreter default; `STUDIO_TORCH_PYTHON` still overrides)
- `AI_Avatar_Studio.bat` `STUDIO_PY` → the canonical interpreter (controller)
- The product uses **absolute interpreter paths** — it does NOT depend on shell activation,
  PATH ordering, or `python` resolving correctly. (Bare `python` → Python 3.14 on this machine,
  so never rely on it.)

## Build / verify (operator)
```
# Recreate from scratch (PowerShell):
.\tools\rebuild_runtime.ps1

# Verify the running product's renderer runtime (any python):
python tools\verify_runtime.py            # prints READY / NOT_READY
python tools\verify_runtime.py --json

# Full regression + truth:
<path-to-canonical-python>\python.exe -m unittest tests.test_studio tests.test_language_resolver tests.test_two_voice_lock
<path-to-canonical-python>\python.exe system_status.py
```

## What NOT to do
- Do NOT copy an existing venv to a new path — recreate from the lock.
- Do NOT install latest torch — pin `2.5.1+cu121` (matches the proven lock + CUDA 12.1 driver).
- Do NOT modify global PATH/registry to make production work — use the absolute canonical interpreter.
- Do NOT delete old environments without explicit user approval (see environment_cleanup_plan.md).
- Do NOT change MuseTalk / lipsync truth (hash `a5a0e55…`) to "fix" env problems.

## Reference
- Forensics: `diagnostics/runtime_environment_recovery/` (root_cause.md, environment_reference_graph.md)
- Manifest: `config/runtime_requirements_manifest.json`
- Lock: `requirements-handover.lock`