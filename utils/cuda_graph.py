###############################################################################
#  CUDA Graph runner for fixed-shape inference (MuseTalk UNet+VAE).
#
#  MuseTalk's inference batch has CONSTANT shapes every call:
#    latent   [batch_size, 8, 32, 32]  (fp16)
#    audio    [batch_size, 50, 384]    (fp16, after PE)
#    timesteps [batch_size]            (long, zeros)
#  so the whole UNet -> VAE forward is a perfect CUDA-graph candidate. The
#  kernel-launch + cuDNN-algorithm-setup overhead is a fixed per-batch cost
#  independent of batch size; for batch_size 8 at 25fps that overhead is a
#  large fraction of the ~0.18s unet time. Capturing it into a graph and
#  replaying eliminates the launch overhead — the dominant win for small
#  fixed-shape realtime inference (target: unet 0.18s -> ~0.10s).
#
#  Design:
#    - Static input buffers live on the inference device for the graph's whole
#      lifetime. Each replay copies fresh inputs into them (cheap, same-device).
#    - A few warmup eager iterations run BEFORE capture so cuDNN benchmark mode
#      has selected + cached the fastest conv algorithm; capturing after that
#      bakes the selected algo into the graph.
#    - Capture happens on a side stream (CUDA graph requirement); replay can be
#      called from any thread (the graph is replayed on the capture stream's
#      device, synchronized by reading the static output).
#    - If anything is unsupported (no CUDA, torch too old for torch.cuda.CUDAGraph,
#      OOM during capture, dynamic shape), capture() returns False and the caller
#      falls back to the eager path. Nothing here ever raises into the inference
#      loop — a graph failure degrades to the pre-graph performance, never a crash.
#
#  Caller contract:
#    runner = GraphRunner(device, capture_fn, warmup_iters=3)
#    ok = runner.capture(static_inputs)         # static_inputs: dict of pre-filled buffers
#    if ok: out = runner.replay({"latent": ..., "audio": ...})
#    else:  out = capture_fn(**fresh_inputs)    # eager fallback
###############################################################################

import torch
from utils.logger import logger


class GraphRunner:
    """Capture + replay a fixed-shape CUDA graph around `capture_fn`.

    Args:
        device: torch.device the graph runs on (must be CUDA).
        capture_fn: callable(**inputs) -> output. Must be deterministic in shape
            for a fixed set of input shapes (no data-dependent control flow that
            changes tensor shapes). For MuseTalk this is the UNet+VAE forward.
        warmup_iters: eager iterations to run before capture so cuDNN benchmark
            selects the fastest conv algo. 3 is enough for the constant MuseTalk
            conv shapes.
    """

    def __init__(self, device, capture_fn, warmup_iters: int = 3):
        self.device = device
        self.capture_fn = capture_fn
        self.warmup_iters = max(1, warmup_iters)
        self._graph = None
        self._static_inputs: dict = {}
        self._static_output = None
        self._capture_stream = None
        self._enabled = False
        self._label = "cuda_graph"

    @staticmethod
    def available() -> bool:
        """True if the torch build exposes CUDA graph capture + a CUDA device."""
        try:
            return torch.cuda.is_available() and hasattr(torch.cuda, "CUDAGraph")
        except Exception:
            return False

    def capture(self, static_inputs: dict, label: str = "cuda_graph") -> bool:
        """Capture the graph around capture_fn using pre-filled static input buffers.

        `static_inputs` maps argument name -> a tensor already on `self.device`
        with the EXACT shape/dtype every replay will use. The caller owns these
        buffers and must keep them alive; replay() copies fresh data into them
        in place. Returns True on success, False on any failure (caller falls
        back to eager).
        """
        self._label = label
        if not self.available():
            logger.info("%s: disabled (torch.cuda.CUDAGraph unavailable)", label)
            return False
        try:
            # Warmup on a side stream so the capture stream's allocator state is
            # clean. cuDNN benchmark needs a few iters to pick + cache the algo.
            side_stream = torch.cuda.Stream(device=self.device)
            with torch.cuda.stream(side_stream):
                for _ in range(self.warmup_iters):
                    with torch.no_grad():
                        _ = self.capture_fn(**static_inputs)
            side_stream.synchronize()

            self._graph = torch.cuda.CUDAGraph()
            self._static_inputs = {k: v for k, v in static_inputs.items()}
            # Capture on a fresh stream. make_graphed_callables would also work
            # but it wraps a single callable and we want explicit buffer control.
            self._capture_stream = torch.cuda.Stream(device=self.device)
            with torch.cuda.stream(self._capture_stream):
                # One warmup iter on the capture stream before recording, as the
                # CUDA docs recommend, so the stream's allocator is primed.
                with torch.no_grad():
                    _ = self.capture_fn(**self._static_inputs)
            self._capture_stream.synchronize()

            with torch.cuda.stream(self._capture_stream):
                for _ in range(1):
                    self._graph.capture_begin()
                    try:
                        with torch.no_grad():
                            self._static_output = self.capture_fn(**self._static_inputs)
                    finally:
                        self._graph.capture_end()
            self._capture_stream.synchronize()
            self._enabled = True
            logger.info(
                "%s: captured on %s (inputs=%s output=%s)",
                label, self.device,
                {k: tuple(v.shape) for k, v in self._static_inputs.items()},
                tuple(self._static_output.shape) if torch.is_tensor(self._static_output) else type(self._static_output).__name__,
            )
            return True
        except Exception as exc:
            # Never raise into the inference loop. A capture failure just means
            # we run eager (the pre-graph behavior) — log once and disable.
            self._enabled = False
            self._graph = None
            logger.warning("%s: capture failed -> eager fallback (%s)", label, exc)
            return False

    def replay(self, fresh_inputs: dict):
        """Replay the captured graph after copying fresh inputs into the static
        buffers. Returns the static output tensor (same buffer every call —
        copy it out before the next replay if you need to keep it). Caller must
        have matching shapes; if any shape differs, fall back to eager instead
        of calling this."""
        # Copy fresh inputs into the static buffers (in place, same device).
        for k, v in fresh_inputs.items():
            buf = self._static_inputs[k]
            if v.shape != buf.shape or v.dtype != buf.dtype:
                # Shape drift -> the graph would produce wrong output. The
                # caller is expected to guard against this, but defend anyway.
                raise ValueError(
                    f"{self._label}: input '{k}' shape/dtype changed "
                    f"{tuple(buf.shape)}/{buf.dtype} -> {tuple(v.shape)}/{v.dtype}; "
                    f"use eager path for dynamic shapes"
                )
            buf.copy_(v, non_blocking=True)
        self._graph.replay()
        return self._static_output

    @property
    def enabled(self) -> bool:
        return self._enabled