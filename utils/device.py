import torch
import warnings

# Resolve the inference device as an INDEXED torch.device (cuda:<n>) instead of
# the bare `torch.device('cuda')`. Under CUDA_VISIBLE_DEVICES remapping the bare
# form resolves lazily to the *current* device, which is the device-binding bug
# that split tensors across cuda:0/cuda:1 (see base_avatar._resolve_heartbeat_
# device). Pinning an explicit index matches what app.configure_gpu_runtime sets
# via torch.cuda.set_device(primary), and lets the offline render script select
# the headless GPU without depending on the server startup path.
#
# Selection order:
#   1. LIVETALKING_GPU_ID env (set by config.py default; honors CUDA_VISIBLE_
#      DEVICES remapping — if only one GPU is visible, use index 0 regardless).
#   2. else the first visible CUDA device (index 0).
# MPS / CPU are the non-CUDA fallbacks (dev only; the realtime pipeline needs
# CUDA).
def initialize_device():
    if torch.cuda.is_available():
        count = torch.cuda.device_count()
        # env_int handles .env + os.environ; default 0 = first visible GPU.
        from utils.envconfig import env_int
        idx = env_int("LIVETALKING_GPU_ID", 0)
        if idx < 0 or idx >= count:
            warnings.warn(
                f"LIVETALKING_GPU_ID={idx} out of visible range [0,{count-1}]; "
                f"falling back to cuda:0"
            )
            idx = 0
        torch.cuda.set_device(idx)
        return torch.device(f"cuda:{idx}")
    elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return torch.device('mps')
    else:
        return torch.device('cpu')