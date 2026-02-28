"""
OliVideoFrameLimit — caps video duration to avoid OOM crashes.

Formula derived from transformer peak VRAM:

    max_frames = total_vram × safety / bytes_per_frame
    bytes_per_frame = TENSOR_COPIES × tokens_per_frame × hidden_dim × 2

Where:
    TENSOR_COPIES = 5  (Q, K, V, attention output, residual — calibrated
                        against empirical data: gives ~240 bytes/pixel for
                        Wan 1.3B hidden_dim=1536, close to the empirical 256)
    tokens_per_frame = (width ÷ 8) × (height ÷ 8)
    hidden_dim       = auto-detected from the connected model
    × 2              = float16 bytes

Why total VRAM (not free VRAM):
    ComfyUI offloads model weights layer by layer. Peak VRAM during inference
    is not "total − model_size" — it's the activation tensor size, which
    scales with total latent tokens (frames × spatial tokens).
"""

import torch

TENSOR_COPIES        = 5
TEMPORAL_COMPRESSION = 4  # frame counts must be n*4+1 (Wan, HunyuanVideo, CogVideoX…)


def _safe_getattr(obj, attr, default=None):
    """Get attribute without triggering ComfyUI model_config __getattr__ warnings.

    ComfyUI's model config objects log a WARNING for every attribute that doesn't
    exist, even when accessed via getattr(obj, attr, None). This helper checks
    __dict__ and the class hierarchy directly, bypassing __getattr__ entirely.
    """
    try:
        d = object.__getattribute__(obj, "__dict__")
        if attr in d:
            return d[attr]
    except (AttributeError, TypeError):
        pass
    for cls in type(obj).__mro__:
        if attr in cls.__dict__:
            v = cls.__dict__[attr]
            if isinstance(v, property):
                try:
                    return v.fget(obj)
                except Exception:
                    pass
            elif not callable(v) and not isinstance(v, (staticmethod, classmethod)):
                return v
    return default


def _get_model_info(model):
    """Return (class_name, hidden_dim, debug_lines) from a ComfyUI MODEL object."""
    if model is None:
        return None, None, []

    # Unwrap ModelPatcher layers
    m = model
    for accessor in ("model", "diffusion_model"):
        sub = getattr(m, accessor, None)
        if sub is not None:
            m = sub

    model_name = type(m).__name__

    # Build list of objects to search for hidden_dim
    search = [m]
    for attr in ("diffusion_model", "transformer", "model", "net", "backbone"):
        sub = getattr(m, attr, None)
        if sub is not None and sub is not m:
            search.append(sub)

    DIM_ATTRS = ("hidden_size", "dim", "embed_dim", "hidden_dim",
                 "d_model", "inner_dim", "width", "model_dim")

    found = {}  # attr -> value, deduplicated
    for obj in search:
        obj_name = type(obj).__name__
        for attr in DIM_ATTRS:
            val = _safe_getattr(obj, attr)
            if isinstance(val, int) and 64 <= val <= 32768:
                key = f"{obj_name}.{attr}"
                found[key] = val
        for cfg_attr in ("config", "model_config"):
            cfg = _safe_getattr(obj, cfg_attr)
            if cfg:
                for attr in DIM_ATTRS:
                    val = _safe_getattr(cfg, attr)
                    if isinstance(val, int) and 64 <= val <= 32768:
                        key = f"{obj_name}.{cfg_attr}.{attr}"
                        found[key] = val

    debug_lines = [f"  {k} = {v}" for k, v in found.items()]

    if found:
        hidden_dim = next(iter(found.values()))
        return model_name, hidden_dim, debug_lines

    # Fallback: estimate from parameter count
    # Transformer: params ≈ 12 × num_layers × hidden_dim²  (typical L ≈ 28)
    try:
        n = sum(p.numel() for p in m.parameters())
        est = int((n / (12 * 28)) ** 0.5)
        standards = (256, 512, 768, 1024, 1280, 1536, 2048, 3072, 4096, 5120, 8192)
        hidden_dim = min(standards, key=lambda x: abs(x - est))
        return model_name, hidden_dim, [f"  param count estimate: {hidden_dim}"]
    except Exception:
        return model_name, None, []


class OliVideoFrameLimit:

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "width":    ("INT",   {"default": 832,  "min": 64,  "max": 8192,   "step": 8}),
                "height":   ("INT",   {"default": 480,  "min": 64,  "max": 8192,   "step": 8}),
                "fps":      ("FLOAT", {"default": 16.0, "min": 1.0, "max": 120.0,  "step": 1.0}),
                "duration": ("FLOAT", {"default": 10.0, "min": 0.1, "max": 3600.0, "step": 0.1}),
                "safety_margin": ("FLOAT", {
                    "default": 0.95, "min": 0.5, "max": 1.0, "step": 0.05,
                    "tooltip": "Fraction of total VRAM to budget (0.95 = 5% headroom).",
                }),
            },
            "optional": {
                "model": ("MODEL",),
            },
        }

    RETURN_TYPES = ("INT",   "INT",    "INT",    "FLOAT", "FLOAT")
    RETURN_NAMES = ("width", "height", "frames", "fps",   "duration")
    OUTPUT_NODE = True
    FUNCTION = "execute"
    CATEGORY = "Oli/utils"

    def execute(self, width, height, duration, fps,
                safety_margin=0.95, model=None):

        requested_frames = max(1, round(duration * fps) + 1)  # +1: reference frame

        if not torch.cuda.is_available():
            info = "CUDA not available — no frame limit applied."
            return {"ui": {"text": [info]},
                    "result": (width, height, requested_frames, float(fps), float(duration))}

        total_vram  = torch.cuda.get_device_properties(0).total_memory
        vram_gb     = total_vram / (1024 ** 3)
        vram_budget = total_vram * safety_margin

        model_name, hidden_dim, debug_lines = _get_model_info(model)
        dim_detected = hidden_dim is not None
        if not dim_detected:
            hidden_dim = 1536
            model_label = "generic"
        else:
            model_label = model_name or "connected"

        spatial_tokens = (width // 8) * (height // 8)

        def snap(f):
            n = (f - 1) // TEMPORAL_COMPRESSION
            return max(1, n * TEMPORAL_COMPRESSION + 1)

        if dim_detected:
            # Known model: the 3D VAE compresses TEMPORAL_COMPRESSION physical frames
            # into one latent frame before attention, so budget is in latent-frame units.
            bytes_per_latent_frame = TENSOR_COPIES * spatial_tokens * hidden_dim * 2
            max_latent_frames   = max(1, int(vram_budget / bytes_per_latent_frame))
            max_physical_frames = (max_latent_frames - 1) * TEMPORAL_COMPRESSION + 1
        else:
            # Generic fallback: no temporal compression assumed; calibrated at
            # ~256 bytes/pixel for hidden_dim=1536, matching empirical data.
            bytes_per_frame = TENSOR_COPIES * spatial_tokens * hidden_dim * 2
            max_physical_frames = max(1, int(vram_budget / bytes_per_frame))

        actual_frames   = snap(min(requested_frames, max_physical_frames))
        actual_duration = (actual_frames - 1) / fps  # -1: reference frame

        info = (
            f"CUDA VRAM: {vram_gb:.1f} GB\n"
            f"model: {model_label}\n"
            f"dim: {hidden_dim}\n"
            f"requested: {requested_frames} frames\n"
            f"capped: {actual_frames} frames ({actual_duration:.2f}s)"
        )

        return {
            "ui": {"text": [info]},
            "result": (width, height, actual_frames, float(fps), float(actual_duration)),
        }


NODE_CLASS_MAPPINGS = {
    "OliVideoFrameLimit": OliVideoFrameLimit,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "OliVideoFrameLimit": "Video Frame Limit (Oli)",
}
