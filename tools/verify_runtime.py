#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AI Avatar Studio — runtime preflight / operator verification (V1.6.0).

One command answers: which Python is Studio using? which is the renderer using?
which Torch / CUDA? are GPUs visible? are dependencies healthy? is the renderer
ready?  -> READY / NOT_READY with evidence.

Read-only. No secrets. No MuseTalk model loading.

Usage (any python):
    python tools/verify_runtime.py
    python tools/verify_runtime.py --json
"""
import json
import os
import sys
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from studio import config, runtime

CANONICAL = config.CANONICAL_INTERPRETER


def _section(d, key, fn):
    try:
        d[key] = fn()
    except Exception as e:
        d[key] = {"ok": False, "error": f"{type(e).__name__}: {e}"}


def probe(python_exe):
    """Probe a python interpreter for the renderer stack (read-only)."""
    if not python_exe or not os.path.isfile(python_exe):
        return {"ok": False, "error": f"interpreter not found: {python_exe}"}
    code = (
        "import sys,json\n"
        "out={'version':sys.version.split()[0],'executable':sys.executable,'prefix':sys.prefix,'base_prefix':sys.base_prefix}\n"
        "try:\n"
        "  import torch; out['torch']=torch.__version__; out['torch_file']=torch.__file__; out['torch_cuda']=torch.version.cuda\n"
        "  out['cuda_available']=torch.cuda.is_available(); out['gpu_count']=torch.cuda.device_count()\n"
        "  out['gpus']=[torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())]\n"
        "  x=torch.tensor([1.,2.]).cuda(); out['cuda_op_ok']=bool((x*2).sum().item()==6.0); torch.cuda.synchronize()\n"
        "except Exception as e: out['torch_error']=f'{type(e).__name__}: {e}'\n"
        "for m in ['cv2','numpy','soundfile','flask','requests','diffusers','transformers','accelerate','omegaconf']:\n"
        "  try:\n"
        "    mod=__import__(m); out[m]={'version':getattr(mod,'__version__','?'),'file':getattr(mod,'__file__','?')}\n"
        "  except Exception as e: out[m]={'error':f'{type(e).__name__}: {e}'}\n"
        "print(json.dumps(out))\n"
    )
    try:
        r = subprocess.run([python_exe, "-c", code], capture_output=True, text=True,
                           timeout=120, env={**os.environ, "PYTHONIOENCODING": "utf-8"})
        try:
            return json.loads(r.stdout)
        except Exception:
            return {"ok": False, "error": (r.stderr or r.stdout)[:500]}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def main():
    as_json = "--json" in sys.argv
    renderer_py = runtime.torch_python()
    report = {
        "canonical_expected": CANONICAL,
        "studio_torch_python_env": os.environ.get("STUDIO_TORCH_PYTHON", "<unset>"),
        "renderer_interpreter": renderer_py,
        "renderer_matches_canonical": os.path.normcase(renderer_py) == os.path.normcase(CANONICAL),
    }
    report["renderer_probe"] = probe(renderer_py)
    rp = report["renderer_probe"]
    torch_ok = bool(rp.get("torch") and rp.get("cuda_available") and rp.get("cuda_op_ok"))
    deps_ok = all(isinstance(rp.get(m), dict) and "version" in rp.get(m, {})
                 for m in ("cv2", "numpy", "soundfile", "flask", "requests",
                           "diffusers", "transformers", "accelerate", "omegaconf"))
    torch_file = str(rp.get("torch_file", "")).lower()
    report["renderer_ready"] = bool(torch_ok and deps_ok)
    report["status"] = "READY" if report["renderer_ready"] and report["renderer_matches_canonical"] else "NOT_READY"

    if as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print("=" * 60)
        print("AI AVATAR STUDIO — RUNTIME PREFLIGHT")
        print("=" * 60)
        print(f"  Canonical expected : {CANONICAL}")
        print(f"  STUDIO_TORCH_PYTHON: {report['studio_torch_python_env']}")
        print(f"  Renderer interpreter: {renderer_py}")
        print(f"  Matches canonical   : {report['renderer_matches_canonical']}")
        print(f"  Python  : {rp.get('version')}  prefix: {rp.get('prefix')}")
        print(f"  Torch   : {rp.get('torch')}  CUDA: {rp.get('torch_cuda')}  ({rp.get('torch_file')})")
        print(f"  CUDA available: {rp.get('cuda_available')}  GPUs: {rp.get('gpu_count')} {rp.get('gpus')}")
        print(f"  CUDA op ok    : {rp.get('cuda_op_ok')}")
        for m in ("cv2", "numpy", "soundfile", "flask", "requests", "diffusers", "transformers", "accelerate", "omegaconf"):
            v = rp.get(m, {})
            print(f"  {m:<12}: {v.get('version','?')}  {v.get('file','')}")
        if "torch_error" in rp:
            print(f"  TORCH ERROR: {rp['torch_error']}")
        print("-" * 60)
        print(f"  STATUS: {report['status']}  (renderer_ready={report['renderer_ready']})")
        if report["status"] != "READY":
            print("  -> Production renderer runtime mismatch. Fix the canonical env / cutover before rendering.")
        print("=" * 60)
    sys.exit(0 if report["status"] == "READY" else 1)


if __name__ == "__main__":
    main()