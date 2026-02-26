"""
OliVideoFrameLimit — caps video duration to avoid OOM crashes.

Formula derived from transformer peak VRAM:

    max_frames = total_vram × safety / bytes_per_frame
    bytes_per_frame = TENSOR_COPIES × tokens_per_frame × hidden_dim × 2

Where:
    TENSOR_COPIES = 5  (Q, K, V, attention output, residual — calibrated
                        against empirical data: gives ~240 bytes/pixel for
                        Wan 1.3B hidden_dim=1536, close to the empirical 256)
    tokens_per_frame = (width // 8) × (height // 8)
    hidden_dim       = auto-detected from the connected model
    × 2              = float16 bytes

Why total VRAM (not free VRAM):
    ComfyUI offloads model weights layer by layer. Peak VRAM during inference
    is not "total − model_size" — it's the activation tensor size, which
    scales with total latent tokens (frames × spatial tokens).
"""

import torch

TENSOR_COPIES = 5


def _get_hidden_dim(model):
    """
    Introspect hidden dimension from a ComfyUI MODEL object.
    Returns None if detection fails (caller should use a fallback).
    """
    if model is None:
        return None

    # Unwrap ModelPatcher layers
    m = model
    for accessor in ("model", "diffusion_model"):
        sub = getattr(m, accessor, None)
        if sub is not None:
            m = sub

    # Build list of objects to search
    search = [m]
    for attr in ("diffusion_model", "transformer", "model", "net", "backbone"):
        sub = getattr(m, attr, None)
        if sub is not None and sub is not m:
            search.append(sub)

    DIM_ATTRS = ("hidden_size", "dim", "embed_dim", "hidden_dim",
                 "d_model", "inner_dim", "width", "model_dim")

    for obj in search:
        # Direct attribute
        for attr in DIM_ATTRS:
            val = getattr(obj, attr, None)
            if isinstance(val, int) and 64 <= val <= 32768:
                return val
        # Via config sub-object
        for cfg_attr in ("config", "model_config"):
            cfg = getattr(obj, cfg_attr, None)
            if cfg:
                for attr in DIM_ATTRS:
                    val = getattr(cfg, attr, None)
                    if isinstance(val, int) and 64 <= val <= 32768:
                        return val

    # Fallback: estimate from parameter count
    # Transformer: params ≈ 12 × num_layers × hidden_dim²  (typical L ≈ 28)
    try:
        n = sum(p.numel() for p in m.parameters())
        est = int((n / (12 * 28)) ** 0.5)
        standards = (256, 512, 768, 1024, 1280, 1536, 2048, 3072, 4096, 5120, 8192)
        return min(standards, key=lambda x: abs(x - est))
    except Exception:
        return None


class OliVideoFrameLimit:

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "width":    ("INT",   {"default": 832,  "min": 64,  "max": 8192,   "step": 8}),
                "height":   ("INT",   {"default": 480,  "min": 64,  "max": 8192,   "step": 8}),
                "fps":      ("FLOAT", {"default": 16.0, "min": 1.0, "max": 120.0,  "step": 1.0}),
                "duration": ("FLOAT", {"default": 10.0,  "min": 0.1, "max": 3600.0, "step": 0.1}),
                "safety_margin": ("FLOAT", {
                    "default": 0.95, "min": 0.5, "max": 1.0, "step": 0.05,
                    "tooltip": "Fraction of total VRAM to budget (0.95 = 5% headroom).",
                }),
            },
            "optional": {
                "model": ("MODEL",),
            },
        }

    RETURN_TYPES = ("INT",           "FLOAT")
    RETURN_NAMES = ("capped_frames", "capped_duration")
    OUTPUT_NODE = True
    FUNCTION = "execute"
    CATEGORY = "Oli/utils"

    def execute(self, width, height, duration, fps,
                safety_margin=0.95, model=None):

        requested_frames = max(1, round(duration * fps))

        if not torch.cuda.is_available():
            info = "CUDA not available — no frame limit applied."
            return {"ui": {"text": [info]},
                    "result": (requested_frames, float(requested_frames / fps))}

        total_vram   = torch.cuda.get_device_properties(0).total_memory
        vram_gb      = total_vram / (1024 ** 3)
        vram_budget  = total_vram * safety_margin

        hidden_dim = _get_hidden_dim(model)
        if hidden_dim is None:
            hidden_dim  = 1536
            dim_source  = "fallback (connect model for auto-detection)"
        else:
            dim_source  = "auto-detected"

        tokens_per_frame = (width // 8) * (height // 8)
        bytes_per_frame  = TENSOR_COPIES * tokens_per_frame * hidden_dim * 2

        max_frames    = max(1, int(vram_budget / bytes_per_frame))
        actual_frames = min(requested_frames, max_frames)
        actual_duration = actual_frames / fps

        info = (
            f"VRAM {vram_gb:.1f} GB  |  dim {hidden_dim} ({dim_source})\n"
            f"requested {requested_frames} frames  →  capped {actual_frames} ({actual_duration:.2f}s)"
        )

        return {
            "ui": {"text": [info]},
            "result": (actual_frames, float(actual_duration)),
        }


NODE_CLASS_MAPPINGS = {
    "OliVideoFrameLimit": OliVideoFrameLimit,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "OliVideoFrameLimit": "Video Frame Limit (Oli)",
}
